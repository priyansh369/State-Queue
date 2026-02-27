from __future__ import annotations

from fastapi import BackgroundTasks

from .websocket_manager import manager


def emit_queue_update(
    background_tasks: BackgroundTasks,
    *,
    event_type: str,
    data: dict,
) -> None:
    background_tasks.add_task(
        manager.broadcast,
        {
            "type": event_type,
            "data": data,
        },
    )

