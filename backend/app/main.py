import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.models import failure, patch, eval_case   # noqa: F401 — register models with SQLAlchemy
from app.api import failures, patches, evals, webhook
from app.api.ws import connect, disconnect

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic (run via `alembic upgrade head` in Dockerfile CMD)
    from app.langsmith_poller import start_poller
    from app.db.database import SessionLocal
    from app.models.failure import Failure, FailureStatus
    from app.api.webhook import process_trace
    asyncio.create_task(start_poller())
    # Re-queue any failures that were mid-pipeline when the server last restarted
    db = SessionLocal()
    try:
        stuck = db.query(Failure).filter(
            Failure.status == FailureStatus.classified
        ).all()
        for f in stuck:
            asyncio.create_task(process_trace(f.id, f.raw_trace or {}))
    finally:
        db.close()
    yield

app = FastAPI(title="TraceGuard AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(failures.router)
app.include_router(patches.router)
app.include_router(evals.router)
app.include_router(webhook.router)

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