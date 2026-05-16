import uuid, logging
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.models.failure import Failure, FailureStatus
from app.classifier.classifier import classify_trace_async
from app.agents.patch_bot import run_patch_bot_async
from app.eval_writer.eval_synthesizer import synthesize_eval_async
from app.shadow_runner.shadow_runner import run_shadow_eval_async
from app.api.ws import broadcast
from app.api.auth import require_api_key

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

async def process_trace(failure_id: str, trace: dict):
    """Full pipeline: classify → patch → eval → shadow. Uses its own DB session."""
    db = SessionLocal()
    try:
        failure = db.query(Failure).filter(Failure.id == failure_id).first()
        if not failure:
            return
        # 1. Classify
        result = await classify_trace_async(trace)
        failure.failure_type       = result.get("failure_type")
        failure.failure_category   = result.get("failure_category")
        failure.severity           = result.get("severity", "medium")
        failure.title              = result.get("title")
        failure.description        = result.get("description")
        failure.root_cause_summary = result.get("root_cause_summary")
        failure.trace_evidence     = result.get("trace_evidence", [])
        failure.status             = FailureStatus.classified
        db.commit()
        await broadcast({"event": "failure_classified", "failure_id": failure_id,
                         "failure_type": failure.failure_type, "severity": failure.severity})
        # 2. Patch bot (opens its own session internally)
        log.info("process_trace: starting patch bot for %s", failure_id)
        await run_patch_bot_async(failure_id)
        log.info("process_trace: patch bot done for %s", failure_id)
        # 3. Synthesize eval (opens its own session internally)
        log.info("process_trace: starting eval synthesizer for %s", failure_id)
        await synthesize_eval_async(failure_id)
        log.info("process_trace: eval synthesizer done for %s", failure_id)
        # 4. Shadow runner — find the eval case just created
        from app.models.eval_case import EvalCase
        db.expire_all()
        ec_list = db.query(EvalCase).filter(EvalCase.failure_id == failure_id).all()
        if ec_list:
            log.info("process_trace: starting shadow runner for %s", failure_id)
            await run_shadow_eval_async(ec_list[-1].id)
    except Exception as e:
        log.error("process_trace FAILED for %s: %s", failure_id, e, exc_info=True)
    finally:
        db.close()

@router.post("/langsmith")
async def langsmith_webhook(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Real LangSmith Engine webhook endpoint."""
    run_id = payload.get("id")
    if run_id:
        existing = db.query(Failure).filter(Failure.run_id == run_id).first()
        if existing:
            return {"status": "duplicate", "failure_id": existing.id}
    failure = Failure(raw_trace=payload, run_id=run_id, status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, payload)
    return {"status": "accepted", "failure_id": failure.id}

@router.post("/ingest")
async def ingest_failure(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db),
                         _: None = Depends(require_api_key)):
    """Generic intake endpoint — accepts failures from any monitoring tool (Langfuse, Helicone, custom).

    Expected payload (all fields optional except at least one of error/outputs):
      run_id, name, error, inputs, outputs, latency_ms, child_runs, source
    """
    run_id = payload.get("run_id") or payload.get("id")
    if run_id:
        existing = db.query(Failure).filter(Failure.run_id == run_id).first()
        if existing:
            return {"status": "duplicate", "failure_id": existing.id}
    trace = {
        "id":         run_id,
        "name":       payload.get("name", "unknown"),
        "inputs":     payload.get("inputs", payload.get("input", {})),
        "outputs":    payload.get("outputs", payload.get("output", {})),
        "error":      payload.get("error", ""),
        "child_runs": payload.get("child_runs", []),
        "latency_ms": payload.get("latency_ms"),
    }
    failure = Failure(raw_trace=trace, run_id=run_id, status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, trace)
    source = payload.get("source", "generic")
    return {"status": "accepted", "failure_id": failure.id, "source": source}


@router.post("/langfuse")
async def langfuse_webhook(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Langfuse webhook receiver.

    Langfuse sends: {"type": "...", "data": {"id": ..., "name": ..., "input": ...,
                      "output": ..., "observations": [...]}}
    We surface the first observation with a non-empty statusMessage as the error.
    """
    data = payload.get("data", payload)
    run_id = data.get("id")
    if run_id:
        existing = db.query(Failure).filter(Failure.run_id == run_id).first()
        if existing:
            return {"status": "duplicate", "failure_id": existing.id}

    # Extract error from observations (Langfuse stores errors in statusMessage)
    error_text = ""
    for obs in (data.get("observations") or []):
        msg = obs.get("statusMessage") or obs.get("status_message", "")
        if msg:
            error_text = msg
            break

    trace = {
        "id":         run_id,
        "name":       data.get("name", "unknown"),
        "inputs":     data.get("input", {}),
        "outputs":    data.get("output", {}),
        "error":      error_text or data.get("statusMessage", ""),
        "child_runs": [],
        "latency_ms": data.get("latency"),
    }
    failure = Failure(raw_trace=trace, run_id=run_id, status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, trace)
    return {"status": "accepted", "failure_id": failure.id}


@router.post("/helicone")
async def helicone_webhook(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Helicone webhook receiver.

    Helicone sends per-request events. We ingest only requests with a non-empty error field.
    Expected shape: {"requestId": ..., "model": ..., "prompt": ...,
                     "response": ..., "error": ..., "latency": ..., "properties": {}}
    """
    error_text = payload.get("error", "") or ""
    status_code = payload.get("statusCode") or payload.get("status_code", 200)
    if not error_text and int(status_code) < 400:
        return {"status": "skipped", "reason": "no error in payload"}

    run_id = payload.get("requestId") or payload.get("request_id")
    if run_id:
        existing = db.query(Failure).filter(Failure.run_id == run_id).first()
        if existing:
            return {"status": "duplicate", "failure_id": existing.id}

    trace = {
        "id":         run_id,
        "name":       payload.get("model", "helicone-agent"),
        "inputs":     {"prompt": payload.get("prompt", "")},
        "outputs":    {"response": payload.get("response", "")},
        "error":      error_text or f"HTTP {status_code}",
        "child_runs": [],
        "latency_ms": payload.get("latency"),
    }
    failure = Failure(raw_trace=trace, run_id=run_id, status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, trace)
    return {"status": "accepted", "failure_id": failure.id, "source": "helicone"}


@router.post("/arize")
async def arize_webhook(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Arize Phoenix webhook receiver.

    Arize Phoenix span format:
    {"span_id": ..., "name": ..., "status": "ERROR", "status_message": ...,
     "input": {"value": ...}, "output": {"value": ...}, "latency_ms": ...}
    """
    status = payload.get("status", "").upper()
    status_message = payload.get("status_message") or payload.get("statusMessage", "")
    if status not in ("ERROR", "UNSET") and not status_message:
        return {"status": "skipped", "reason": "span has no error status"}

    run_id = payload.get("span_id") or payload.get("spanId")
    if run_id:
        existing = db.query(Failure).filter(Failure.run_id == run_id).first()
        if existing:
            return {"status": "duplicate", "failure_id": existing.id}

    inp = payload.get("input", {})
    out = payload.get("output", {})
    trace = {
        "id":         run_id,
        "name":       payload.get("name", "arize-span"),
        "inputs":     inp if isinstance(inp, dict) else {"value": inp},
        "outputs":    out if isinstance(out, dict) else {"value": out},
        "error":      status_message or f"Span status: {status}",
        "child_runs": [],
        "latency_ms": payload.get("latency_ms"),
    }
    failure = Failure(raw_trace=trace, run_id=run_id, status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, trace)
    return {"status": "accepted", "failure_id": failure.id, "source": "arize"}


@router.post("/simulate")
async def simulate_webhook(payload: dict, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Simulate a failure for demo/testing — injects a realistic trace."""
    hint = payload.pop("failure_hint", "infinite_loop")
    trace = _build_demo_trace(hint, payload)
    failure = Failure(raw_trace=trace, run_id=trace.get("id"), status=FailureStatus.new)
    db.add(failure)
    db.commit()
    db.refresh(failure)
    bg.add_task(process_trace, failure.id, trace)
    return {"status": "simulated", "failure_id": failure.id, "failure_hint": hint}

def _build_demo_trace(hint: str, extra: dict) -> dict:
    base = {"id": str(uuid.uuid4()), "run_type": "chain", "name": "DemoAgent",
            "inputs": extra.get("input", {"input": "test query"}),
            "outputs": extra.get("outputs", {}),
            "error": extra.get("error", ""),
            "child_runs": extra.get("child_runs", []),
            "latency_ms": extra.get("latency_ms", 4500)}
    if hint == "infinite_loop":
        base["child_runs"] = [{"run_type": "tool", "name": "search_tool",
                                "inputs": {"query": f"query {i}"},
                                "error": ""} for i in range(12)]
        base["error"] = "Agent stopped due to iteration limit of 10."
    elif hint == "hallucination":
        base["outputs"] = {"output": "Dr. Smith published this in Nature 2024 [doi:10.1038/fake-doi]. The paper showed 99.9% accuracy."}
    elif hint == "context_overflow":
        base["error"] = "This model's maximum context length is 128000 tokens. Your messages resulted in 145230 tokens."
    elif hint == "empty_response":
        base["outputs"] = {}
    return base