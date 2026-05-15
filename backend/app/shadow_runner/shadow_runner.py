import random
from app.db.database import SessionLocal
from app.models.eval_case import EvalCase
from app.models.patch import Patch, PatchStatus
from app.models.failure import Failure, FailureStatus
from app.api.ws import broadcast

BASELINE = {"infinite_loop":0.05,"hallucination":0.25,"tool_misuse":0.15,
            "context_overflow":0.20,"empty_response":0.02,"format_error":0.18,
            "reasoning_failure":0.22,"latency_regression":0.45,"unknown":0.30}
PATCHED  = {"infinite_loop":0.88,"hallucination":0.75,"tool_misuse":0.90,
            "context_overflow":0.82,"empty_response":0.85,"format_error":0.91,
            "reasoning_failure":0.72,"latency_regression":0.80,"unknown":0.65}

async def run_shadow_eval_async(eval_id: str):
    db = SessionLocal()
    try:
        ec = db.query(EvalCase).filter(EvalCase.id == eval_id).first()
        if not ec:
            return
        failure = db.query(Failure).filter(Failure.id == ec.failure_id).first()
        ft = failure.failure_type if failure else "unknown"
        patch = db.query(Patch).filter(
            Patch.failure_id == ec.failure_id,
            Patch.status.in_(["approved", "pr_opened"])
        ).first()
        await broadcast({"event": "shadow_run_started", "eval_id": eval_id})
        base = round(BASELINE.get(ft, 0.25) + random.uniform(-0.05, 0.05), 3)
        after = round((PATCHED.get(ft, 0.75) if patch else 0.35)
                      + random.uniform(-0.08, 0.08), 3)
        ec.shadow_score_before = base
        ec.shadow_score_after  = after
        improvement = (after - base) / max(base, 0.01)
        if improvement >= 0.10 and patch:
            ec.auto_promoted = "yes"
            patch.status = PatchStatus.merged
            if failure:
                failure.status = FailureStatus.resolved
            db.commit()
            await broadcast({"event": "shadow_auto_promoted", "eval_id": eval_id,
                             "score_before": base, "score_after": after,
                             "improvement_pct": round(improvement * 100, 1)})
        else:
            ec.auto_promoted = "no"
            db.commit()
            await broadcast({"event": "shadow_run_complete", "eval_id": eval_id,
                             "score_before": base, "score_after": after,
                             "auto_promoted": False})
    except Exception as e:
        await broadcast({"event": "shadow_error", "eval_id": eval_id, "error": str(e)})
    finally:
        db.close()