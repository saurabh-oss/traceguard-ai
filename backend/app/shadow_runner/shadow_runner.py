import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import get_llm
from app.db.database import SessionLocal
from app.models.eval_case import EvalCase
from app.models.patch import Patch, PatchStatus
from app.models.failure import Failure, FailureStatus
from app.api.ws import broadcast

log = logging.getLogger(__name__)

_JUDGE_SYSTEM = """You are an LLM evaluation judge assessing agent output quality.
Return ONLY valid JSON:
{"score": <float 0.0-1.0>, "reasoning": "<one sentence>"}

Scoring guide:
0.0-0.2  complete failure / error / empty output
0.3-0.5  partial / unreliable output
0.6-0.8  mostly correct with minor issues
0.9-1.0  correct, reliable, well-formed output"""


async def _llm_judge(llm, task_input: dict, output: str, context: str) -> tuple[float, str]:
    prompt = (
        f"Task input:\n{json.dumps(task_input, indent=2)}\n\n"
        f"Agent output:\n{output[:1200]}\n\n"
        f"Context: {context}\n\n"
        "Score the quality of this output."
    )
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=_JUDGE_SYSTEM),
            HumanMessage(content=prompt),
        ])
        m = re.search(r"\{[\s\S]*\}", resp.content)
        if m:
            r = json.loads(m.group())
            return float(r.get("score", 0.5)), r.get("reasoning", "")
    except Exception as e:
        log.warning("LLM judge error: %s", e)
    return 0.5, "Could not assess"


def _record_langsmith_feedback(run_id: str, score_before: float,
                                score_after: float,
                                reason_before: str, reason_after: str) -> bool:
    """Write before/after quality scores back to the LangSmith run as feedback."""
    if not settings.langchain_api_key or not run_id:
        return False
    try:
        from langsmith import Client
        client = Client(api_key=settings.langchain_api_key)
        client.create_feedback(run_id=run_id,
                               key="traceguard/quality_before",
                               score=score_before,
                               comment=reason_before)
        client.create_feedback(run_id=run_id,
                               key="traceguard/quality_after_patch",
                               score=score_after,
                               comment=f"Projected post-patch: {reason_after}")
        return True
    except Exception as e:
        log.warning("LangSmith feedback error: %s", e)
        return False


async def run_shadow_eval_async(eval_id: str):
    db = SessionLocal()
    try:
        ec = db.query(EvalCase).filter(EvalCase.id == eval_id).first()
        if not ec:
            return

        failure = db.query(Failure).filter(Failure.id == ec.failure_id).first()
        patch = db.query(Patch).filter(
            Patch.failure_id == ec.failure_id,
            Patch.status.in_([PatchStatus.pr_opened, PatchStatus.approved]),
        ).first()

        await broadcast({"event": "shadow_run_started", "eval_id": eval_id})

        llm = get_llm(temperature=0)

        raw_trace   = (failure.raw_trace or {}) if failure else {}
        task_input  = raw_trace.get("inputs") or ec.test_input or {}
        failure_ctx = (
            f"{failure.failure_type} failure — {failure.root_cause_summary}"
            if failure else "unknown failure"
        )

        # ── Before: score the original (failing) trace output ──────────────
        before_output = (
            raw_trace.get("error")
            or str(raw_trace.get("outputs") or "(no output)")
        )
        score_before, reason_before = await _llm_judge(
            llm,
            task_input=task_input,
            output=before_output,
            context=f"This is the ORIGINAL failing output. {failure_ctx}",
        )

        # ── After: score patched code's projected behavior ──────────────────
        # We ask the judge to evaluate the patched code + explanation as a
        # proxy for how the agent will behave after the fix is merged.
        after_output = (
            f"Patched code:\n{patch.patched_code}\n\nFix explanation: {patch.explanation}"
            if patch
            else f"Expected correct output: {ec.expected_output}"
        )
        score_after, reason_after = await _llm_judge(
            llm,
            task_input=task_input,
            output=after_output,
            context=(
                f"This is the AUTO-PATCHED code fixing the {failure_ctx}. "
                f"Expected output: {ec.expected_output}"
            ),
        )

        score_before = round(min(max(score_before, 0.0), 1.0), 3)
        score_after  = round(min(max(score_after,  0.0), 1.0), 3)

        # ── Write real feedback to LangSmith ────────────────────────────────
        langsmith_ok = _record_langsmith_feedback(
            run_id=failure.run_id if failure else None,
            score_before=score_before, score_after=score_after,
            reason_before=reason_before, reason_after=reason_after,
        )

        ec.shadow_score_before = score_before
        ec.shadow_score_after  = score_after

        improvement = (score_after - score_before) / max(score_before, 0.01)
        if improvement >= 0.10 and patch:
            ec.auto_promoted = "yes"
            patch.status = PatchStatus.merged
            if failure:
                failure.status = FailureStatus.resolved
            db.commit()
            await broadcast({
                "event": "shadow_auto_promoted", "eval_id": eval_id,
                "score_before": score_before, "score_after": score_after,
                "improvement_pct": round(improvement * 100, 1),
                "langsmith_feedback": langsmith_ok,
            })
        else:
            ec.auto_promoted = "no"
            db.commit()
            await broadcast({
                "event": "shadow_run_complete", "eval_id": eval_id,
                "score_before": score_before, "score_after": score_after,
                "auto_promoted": False,
                "langsmith_feedback": langsmith_ok,
            })

    except Exception as e:
        log.exception("Shadow eval error for eval_id=%s", eval_id)
        await broadcast({"event": "shadow_error", "eval_id": eval_id, "error": str(e)})
    finally:
        db.close()
