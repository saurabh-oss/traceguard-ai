import asyncio, time
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.models import failure, patch, eval_case   # noqa: F401 — register models with SQLAlchemy
from app.api import failures, patches, evals, webhook, stats
from app.api.ws import connect, disconnect

# Simple in-process rate limiter for webhook endpoints
class _RateLimiter(BaseHTTPMiddleware):
    _LIMITS = {
        "/api/webhook/simulate": (10, 60),   # 10 req / 60 s
        "/api/webhook/ingest":   (60, 60),   # 60 req / 60 s
        "/api/webhook/langsmith":(120, 60),
        "/api/webhook/langfuse": (120, 60),
        "/api/webhook/helicone": (120, 60),
        "/api/webhook/arize":    (120, 60),
    }
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        limit = self._LIMITS.get(request.url.path)
        if limit and request.method == "POST":
            calls, period = limit
            key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
            now = time.time()
            self._hits[key] = [t for t in self._hits[key] if now - t < period]
            if len(self._hits[key]) >= calls:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            self._hits[key].append(now)
        return await call_next(request)

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
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        disconnect(ws)

@app.get("/health")
def health():
    return {"status": "ok", "service": "TraceGuard AI"}