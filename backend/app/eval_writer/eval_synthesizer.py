import json, re
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.db.database import SessionLocal
from app.models.failure import Failure
from app.models.eval_case import EvalCase
from app.api.ws import broadcast

SYS = """You are TraceGuard AI. Generate a LangSmith evaluator for this failure.
Return ONLY valid JSON:
{
  "evaluator_name": "snake_case_name",
  "evaluator_code": "def evaluate(run, example):\\n  ...\\n  return {'score': float, 'comment': str}",
  "test_input": {"input": "...", "context": "..."},
  "expected_output": "what correct output looks like"
}"""

async def synthesize_eval_async(failure_id: str):
    db = SessionLocal()
    try:
        failure = db.query(Failure).filter(Failure.id == failure_id).first()
        if not failure:
            return
        llm = ChatGroq(model=settings.groq_model, temperature=0.2,
                       api_key=settings.groq_api_key)
        resp = await llm.ainvoke([
            SystemMessage(content=SYS),
            HumanMessage(content=f"Failure type: {failure.failure_type}\n"
                         f"Root cause: {failure.root_cause_summary}\n"
                         f"Evidence: {json.dumps(failure.trace_evidence or [])}")
        ])
        m = re.search(r"\{[\s\S]*\}", resp.content)
        result = json.loads(m.group()) if m else {}
        ec = EvalCase(failure_id=failure_id,
                      evaluator_name=result.get("evaluator_name", f"eval_{failure.failure_type}"),
                      evaluator_code=result.get("evaluator_code", ""),
                      test_input=result.get("test_input", {}),
                      expected_output=result.get("expected_output", ""))
        db.add(ec)
        db.commit()
        db.refresh(ec)
        await broadcast({"event": "eval_generated", "failure_id": failure_id,
                         "eval_id": ec.id, "evaluator_name": ec.evaluator_name})
    except Exception as e:
        await broadcast({"event": "eval_error", "failure_id": failure_id, "error": str(e)})
    finally:
        db.close()