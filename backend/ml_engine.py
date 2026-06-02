from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import models


@dataclass
class QueueEstimate:
    patient: dict
    eta_minutes: int


def _utc_today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).replace(tzinfo=None)


def _duration_minutes(appt: dict) -> float | None:
    started_at = appt.get("started_at") or appt.get("appointment_date")
    completed_at = appt.get("completed_at")
    if not started_at or not completed_at:
        return None
    if completed_at < started_at:
        return None
    return (completed_at - started_at).total_seconds() / 60.0


def estimate_next_service_minutes(db, doctor_id: int) -> float:
    completed = list(
        db.appointments.find(
            {
                "doctor_id": doctor_id,
                "status": models.StatusEnum.COMPLETED,
                "completed_at": {"$ne": None},
            }
        ).sort("completed_at", -1).limit(30)
    )
    durations = [d for d in (_duration_minutes(a) for a in completed) if d is not None]
    if not durations:
        return 10.0
    return max(4.0, min(sum(durations) / len(durations), 45.0))


def _doctor_completed_today_count(db, doctor_id: int) -> int:
    return db.appointments.count_documents(
        {
            "doctor_id": doctor_id,
            "status": models.StatusEnum.COMPLETED,
            "completed_at": {"$gte": _utc_today_start()},
        }
    )


def doctor_queue(db, doctor_id: int) -> list[dict]:
    rows = list(
        db.patients.find(
            {
                "doctor_id": doctor_id,
                "status": models.StatusEnum.WAITING,
            }
        )
    )
    return sorted(
        rows,
        key=lambda p: (
            0 if p.get("priority") == models.PriorityEnum.EMERGENCY else 1,
            p.get("created_at"),
        ),
    )


def compute_queue_estimates(db, doctor_id: int) -> list[QueueEstimate]:
    queue = doctor_queue(db, doctor_id)
    if not queue:
        return []

    service_minutes = estimate_next_service_minutes(db, doctor_id)
    completed_today = _doctor_completed_today_count(db, doctor_id)
    load_factor = max(0.8, min(1.25, 1.0 - (completed_today / 200.0)))

    eta = 0.0
    out: list[QueueEstimate] = []
    for p in queue:
        out.append(QueueEstimate(patient=p, eta_minutes=int(round(max(eta, 0)))))
        slot = service_minutes * (
            0.7 if p.get("priority") == models.PriorityEnum.EMERGENCY else 1.0
        )
        eta += slot * load_factor
    return out


def compute_patient_eta_minutes(db, patient: dict) -> int:
    if patient.get("status") != models.StatusEnum.WAITING:
        return 0
    estimates = compute_queue_estimates(db, patient["doctor_id"])
    for row in estimates:
        if row.patient.get("id") == patient.get("id"):
            return int(max(row.eta_minutes, 0))
    return 0
