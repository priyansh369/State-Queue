from typing import Set
from fastapi import WebSocket

# Simple in-memory broadcaster for development only.
connected: Set[WebSocket] = set()

async def register(ws: WebSocket):
    await ws.accept()
    connected.add(ws)


async def unregister(ws: WebSocket):
    connected.discard(ws)


async def broadcast(message: dict):
    """Send JSON message to all connected websockets. Silently drops closed sockets."""
    to_remove = []
    for ws in list(connected):
        try:
            await ws.send_json(message)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        connected.discard(ws)
