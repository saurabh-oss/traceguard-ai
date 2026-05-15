"""
Polls the LangSmith API for failed runs and feeds them into TraceGuard's
classify → patch → eval → shadow pipeline.

Runs as a background task started in main.py lifespan.
Deduplicates by run_id so each failure is only processed once.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from langsmith import Client
from app.config import settings
from app.db.database import SessionLocal
from app.models.failure import Failure, FailureStatus
from app.api.webhook import process_trace

log = logging.getLogger("traceguard.poller")

POLL_INTERVAL_SECONDS = 60
LOOKBACK_MINUTES = 10


def _langsmith_run_to_trace(run) -> dict:
    """Convert a LangSmith Run object to the trace dict TraceGuard expects."""
    return {
        "id": str(run.id),
        "run_type": run.run_type,
        "name": run.name,
        "inputs": run.inputs or {},
        "outputs": run.outputs or {},
        "error": run.error or "",
        "child_runs": [
            {
                "run_type": getattr(c, "run_type", ""),
                "name": getattr(c, "name", ""),
                "inputs": getattr(c, "inputs", {}),
                "error": getattr(c, "error", ""),
            }
            for c in (run.child_runs or [])[:15]
        ],
        "latency_ms": int(run.total_cost * 1000) if run.total_cost else None,
    }


def _already_processed(run_id: str, db) -> bool:
    return db.query(Failure).filter(Failure.run_id == run_id).first() is not None


async def poll_once(client: Client):
    since = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    db = SessionLocal()
    new_count = 0
    try:
        runs = list(client.list_runs(
            project_name=settings.langchain_project,
            error=True,
            start_time=since,
            execution_order=1,  # only root runs, not child spans
        ))
        for run in runs:
            run_id = str(run.id)
            if _already_processed(run_id, db):
                continue
            trace = _langsmith_run_to_trace(run)
            failure = Failure(
                raw_trace=trace,
                run_id=run_id,
                status=FailureStatus.new,
            )
            db.add(failure)
            db.commit()
            db.refresh(failure)
            # Fire pipeline in background so poll loop isn't blocked
            asyncio.create_task(process_trace(failure.id, trace))
            new_count += 1
            log.info(f"New failure queued: run_id={run_id}")
    except Exception as e:
        log.error(f"Poll error: {e}")
    finally:
        db.close()
    if new_count:
        log.info(f"Poll complete: {new_count} new failure(s) queued")


async def start_poller():
    if not settings.langchain_api_key or settings.langchain_api_key.startswith("lsv2_your"):
        log.warning("LANGCHAIN_API_KEY not set — LangSmith poller disabled")
        return

    log.info(f"LangSmith poller started — project: {settings.langchain_project}, interval: {POLL_INTERVAL_SECONDS}s")
    client = Client(api_key=settings.langchain_api_key)
    while True:
        await poll_once(client)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
