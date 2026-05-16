import asyncio, logging, time
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)
from app.config import settings
from app.models import failure, patch, eval_case   # noqa: F401 — register models with SQLAlchemy
from app.api import failures, patches, evals, webhook, stats
from app.api.ws import connect, disconnect

# Simple per-IP rate limiting — applied inside route handlers, not as middleware
_rate_hits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMITS = {
    "/api/webhook/simulate": (10,  60),
    "/api/webhook/ingest":   (60,  60),
    "/api/webhook/langsmith":(120, 60),
    "/api/webhook/langfuse": (120, 60),
    "/api/webhook/helicone": (120, 60),
    "/api/webhook/arize":    (120, 60),
}

def check_rate_limit(request: Request) -> JSONResponse | None:
    """Returns 429 JSONResponse if the caller is over limit, else None."""
    limit = _RATE_LIMITS.get(request.url.path)
    if not limit:
        return None
    calls, period = limit
    ip  = request.client.host if request.client else "unknown"
    key = f"{ip}:{request.url.path}"
    now = time.time()
    _rate_hits[key] = [t for t in _rate_hits[key] if now - t < period]
    if len(_rate_hits[key]) >= calls:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    _rate_hits[key].append(now)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.database import engine, Base
    import app.models.failure   # noqa: F401
    import app.models.patch     # noqa: F401
    import app.models.eval_case  # noqa: F401
    Base.metadata.create_all(bind=engine, checkfirst=True)
    from app.langsmith_poller import start_poller
    from app.db.database import SessionLocal
    from app.models.failure import Failure, FailureStatus
    from app.api.webhook import process_trace
    asyncio.create_task(start_poller())
    async def _resume_stuck():
        await asyncio.sleep(5)
        db = SessionLocal()
        try:
            stuck = db.query(Failure).filter(
                Failure.status == FailureStatus.classified
            ).all()
            for i, f in enumerate(stuck):
                await asyncio.sleep(i * 10)
                asyncio.create_task(process_trace(f.id, f.raw_trace or {}))
        finally:
            db.close()
    asyncio.create_task(_resume_stuck())
    yield


app = FastAPI(title="TraceGuard AI", version="1.0.0", lifespan=lifespan)

# Only CORSMiddleware — no custom middleware that could interfere with WS upgrades
app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(failures.router)
app.include_router(patches.router)
app.include_router(evals.router)
app.include_router(webhook.router)
app.include_router(stats.router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await connect(ws)
    log.info("WebSocket connected: %s", ws.client)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WebSocket error: %s", e)
    finally:
        disconnect(ws)
        log.info("WebSocket disconnected: %s", ws.client)


@app.get("/health")
def health():
    return {"status": "ok", "service": "TraceGuard AI"}
