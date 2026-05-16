import asyncio, json, logging, time
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)
from app.config import settings
from app.models import failure, patch, eval_case   # noqa: F401 — register models with SQLAlchemy
from app.api import failures, patches, evals, webhook, stats
from app.api.ws import connect, disconnect

_RATE_LIMITS = {
    "/api/webhook/simulate": (10,  60),
    "/api/webhook/ingest":   (60,  60),
    "/api/webhook/langsmith":(120, 60),
    "/api/webhook/langfuse": (120, 60),
    "/api/webhook/helicone": (120, 60),
    "/api/webhook/arize":    (120, 60),
}

class _RateLimiter:
    """Pure ASGI middleware — skips WebSocket scopes entirely so WS upgrades are never blocked."""
    def __init__(self, app):
        self.app  = app
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path   = scope.get("path", "")
            method = scope.get("method", "")
            limit  = _RATE_LIMITS.get(path)
            if limit and method == "POST":
                calls, period = limit
                client = scope.get("client")
                ip     = client[0] if client else "unknown"
                key    = f"{ip}:{path}"
                now    = time.time()
                self._hits[key] = [t for t in self._hits[key] if now - t < period]
                if len(self._hits[key]) >= calls:
                    body = json.dumps({"detail": "Rate limit exceeded"}).encode()
                    await send({"type": "http.response.start", "status": 429,
                                "headers": [[b"content-type", b"application/json"]]})
                    await send({"type": "http.response.body", "body": body})
                    return
                self._hits[key].append(now)
        await self.app(scope, receive, send)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Belt-and-suspenders: create any tables Alembic may have skipped
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
    # Re-queue failures stuck mid-pipeline, staggered to avoid Groq burst
    async def _resume_stuck():
        await asyncio.sleep(5)  # let server finish starting up first
        db = SessionLocal()
        try:
            stuck = db.query(Failure).filter(
                Failure.status == FailureStatus.classified
            ).all()
            for i, f in enumerate(stuck):
                await asyncio.sleep(i * 10)  # 10s gap between each re-queued task
                asyncio.create_task(process_trace(f.id, f.raw_trace or {}))
        finally:
            db.close()
    asyncio.create_task(_resume_stuck())
    yield

app = FastAPI(title="TraceGuard AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(_RateLimiter)
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