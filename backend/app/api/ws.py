from fastapi import WebSocket
from typing import List

active_connections: List[WebSocket] = []

async def connect(ws: WebSocket):
    await ws.accept()
    active_connections.append(ws)

def disconnect(ws: WebSocket):
    if ws in active_connections:
        active_connections.remove(ws)

async def broadcast(message: dict):
    import json
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.append(ws)
    for ws in dead:
        disconnect(ws)