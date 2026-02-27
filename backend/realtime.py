from __future__ import annotations

from fastapi import BackgroundTasks

from .socket_manager import manager


def emit_queue_update(
    background_tasks: BackgroundTasks,
    *,
    reason: str,
    doctor_id: int | None = None,
    patient_id: int | None = None,
) -> None:
    background_tasks.add_task(
        manager.broadcast_json,
        {
            "type": "queue_update",
            "reason": reason,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
        },
    )

