from __future__ import annotations

from datetime import datetime, timezone

import models, schemas
from mongo import next_id, utcnow


def _utc_today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).replace(tzinfo=None)


def waiting_minutes(patient: dict) -> int:
    return waiting_seconds(patient) // 60


def waiting_seconds(patient: dict) -> int:
    created_at = patient.get("created_at") or utcnow()
    delta = utcnow() - created_at
    return max(int(delta.total_seconds()), 0)


def escalation_required(patient: dict) -> bool:
    return (
        patient.get("status") == models.StatusEnum.WAITING
        and patient.get("priority") == models.PriorityEnum.EMERGENCY
        and waiting_seconds(patient) > 10 * 60
    )


def map_queue_patient(
    _db,
    patient: dict,
    queue_number: int,
    estimated_wait_minutes: int | None = None,
) -> schemas.QueuePatient:
    estimated = int(max(estimated_wait_minutes or 0, 0))
    priority = patient.get("priority", models.PriorityEnum.NORMAL)
    return schemas.QueuePatient(
        id=patient["id"],
        name=patient["name"],
        doctor_id=patient["doctor_id"],
        priority=priority,
        priority_rank=0 if priority == models.PriorityEnum.EMERGENCY else 1,
        status=patient.get("status", models.StatusEnum.WAITING),
        queue_number=queue_number,
        symptoms=patient.get("symptoms", ""),
        estimated_wait_minutes=estimated,
        estimated_time=f"{estimated} min",
        waiting_minutes=waiting_minutes(patient),
        waiting_seconds=waiting_seconds(patient),
        escalation_required=escalation_required(patient),
    )


def create_patient_with_queue(
    db,
    *,
    name: str,
    age: int,
    gender: str,
    contact_number: str,
    symptoms: str,
    priority: str,
    doctor_id: int,
    user_id: int | None = None,
) -> dict:
    next_queue = (
        db.patients.find_one({"doctor_id": doctor_id}, {"queue_number": 1}, sort=[("queue_number", -1)])
        or {}
    ).get("queue_number", 0) + 1
    patient = {
        "id": next_id("patients"),
        "name": name,
        "age": age,
        "gender": gender,
        "contact_number": contact_number,
        "symptoms": symptoms,
        "priority": priority,
        "status": models.StatusEnum.WAITING,
        "queue_number": next_queue,
        "doctor_id": doctor_id,
        "user_id": user_id,
        "created_at": utcnow(),
        "started_serving_at": None,
        "completed_at": None,
    }
    db.patients.insert_one(patient)
    return patient


def create_appointment_for_patient(db, *, patient_id: int, doctor_id: int) -> dict:
    appointment = {
        "id": next_id("appointments"),
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": utcnow(),
        "status": models.StatusEnum.WAITING,
        "created_at": utcnow(),
        "started_at": None,
        "completed_at": None,
    }
    db.appointments.insert_one(appointment)
    return appointment


def write_audit_log(db, *, user_id: int, action: str, patient_id: int | None = None) -> None:
    db.audit_logs.insert_one(
        {
            "id": next_id("audit_logs"),
            "user_id": user_id,
            "action": action,
            "patient_id": patient_id,
            "timestamp": utcnow(),
        }
    )


def dashboard_analytics(db, *, doctor_id: int | None = None) -> dict[str, float | int]:
    today_start = _utc_today_start()
    base_filter = {}
    if doctor_id is not None:
        base_filter["doctor_id"] = doctor_id

    today_filter = dict(base_filter)
    today_filter["created_at"] = {"$gte": today_start}

    total_today = db.patients.count_documents(today_filter)
    emergency_today = db.patients.count_documents(
        {**today_filter, "priority": models.PriorityEnum.EMERGENCY}
    )
    completed_today = db.patients.count_documents(
        {**today_filter, "status": models.StatusEnum.COMPLETED}
    )

    overdue = list(
        db.patients.find(
            {
                **base_filter,
                "status": models.StatusEnum.WAITING,
                "priority": models.PriorityEnum.EMERGENCY,
            }
        )
    )
    overdue_count = sum(1 for p in overdue if escalation_required(p))

    completed_rows = list(
        db.patients.find(
            {
                **today_filter,
                "status": models.StatusEnum.COMPLETED,
                "completed_at": {"$ne": None},
            },
            {"created_at": 1, "completed_at": 1},
        )
    )
    durations = []
    for row in completed_rows:
        created = row.get("created_at")
        completed = row.get("completed_at")
        if created and completed and completed >= created:
            durations.append((completed - created).total_seconds() / 60)
    avg_wait = int(round(sum(durations) / len(durations))) if durations else 0

    emergency_percentage = round((emergency_today / total_today) * 100, 2) if total_today else 0.0
    completion_rate = round((completed_today / total_today) * 100, 2) if total_today else 0.0

    return {
        "total_patients_today": total_today,
        "average_wait_minutes": avg_wait,
        "emergency_percentage": emergency_percentage,
        "completion_rate": completion_rate,
        "overdue_emergencies": overdue_count,
    }
