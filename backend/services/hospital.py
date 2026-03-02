from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models, schemas
from ml_engine import compute_patient_eta_minutes


def _utc_today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).replace(tzinfo=None)


def waiting_minutes(patient: models.Patient) -> int:
    return waiting_seconds(patient) // 60


def waiting_seconds(patient: models.Patient) -> int:
    delta = datetime.utcnow() - patient.created_at
    return max(int(delta.total_seconds()), 0)


def escalation_required(patient: models.Patient) -> bool:
    return (
        patient.status == models.StatusEnum.WAITING
        and patient.priority == models.PriorityEnum.EMERGENCY
        and waiting_seconds(patient) > 10 * 60
    )


def map_queue_patient(
    db: Session,
    patient: models.Patient,
    queue_number: int,
    estimated_wait_minutes: int | None = None,
) -> schemas.QueuePatient:
    estimated = (
        estimated_wait_minutes
        if estimated_wait_minutes is not None
        else compute_patient_eta_minutes(db, patient)
    )
    return schemas.QueuePatient(
        id=patient.id,
        name=patient.name,
        doctor_id=patient.doctor_id,
        priority=patient.priority,
        priority_rank=0 if patient.priority == models.PriorityEnum.EMERGENCY else 1,
        status=patient.status,
        queue_number=queue_number,
        symptoms=patient.symptoms,
        estimated_wait_minutes=estimated,
        estimated_time=f"{estimated} min",
        waiting_minutes=waiting_minutes(patient),
        waiting_seconds=waiting_seconds(patient),
        escalation_required=escalation_required(patient),
    )


def create_patient_with_queue(
    db: Session,
    *,
    name: str,
    age: int,
    gender: str,
    contact_number: str,
    symptoms: str,
    priority: str,
    doctor_id: int,
) -> models.Patient:
    for _ in range(3):
        max_queue = (
            db.query(func.max(models.Patient.queue_number))
            .filter(models.Patient.doctor_id == doctor_id)
            .scalar()
        )
        next_queue = (max_queue or 0) + 1
        patient = models.Patient(
            name=name,
            age=age,
            gender=gender,
            contact_number=contact_number,
            symptoms=symptoms,
            priority=priority,
            status=models.StatusEnum.WAITING,
            queue_number=next_queue,
            doctor_id=doctor_id,
        )
        db.add(patient)
        try:
            db.flush()
            return patient
        except IntegrityError:
            db.rollback()

    raise IntegrityError("Failed to allocate unique queue number", {}, None)


def create_appointment_for_patient(db: Session, *, patient_id: int, doctor_id: int) -> None:
    db.add(
        models.Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=datetime.utcnow(),
            status=models.StatusEnum.WAITING,
        )
    )


def write_audit_log(db: Session, *, user_id: int, action: str, patient_id: int | None = None) -> None:
    db.add(models.AuditLog(user_id=user_id, action=action, patient_id=patient_id))


def dashboard_analytics(db: Session, *, doctor_id: int | None = None) -> dict[str, float | int]:
    filters = []
    if doctor_id is not None:
        filters.append(models.Patient.doctor_id == doctor_id)

    today_start = _utc_today_start()
    today_filters = filters + [models.Patient.created_at >= today_start]

    total_today = db.query(models.Patient).filter(*today_filters).count()
    emergency_today = (
        db.query(models.Patient)
        .filter(*today_filters, models.Patient.priority == models.PriorityEnum.EMERGENCY)
        .count()
    )
    completed_today = (
        db.query(models.Patient)
        .filter(*today_filters, models.Patient.status == models.StatusEnum.COMPLETED)
        .count()
    )
    overdue_emergencies = (
        db.query(models.Patient)
        .filter(
            *filters,
            models.Patient.status == models.StatusEnum.WAITING,
            models.Patient.priority == models.PriorityEnum.EMERGENCY,
            models.Patient.created_at <= datetime.utcnow().replace(second=0, microsecond=0),
        )
        .all()
    )
    overdue_count = sum(1 for p in overdue_emergencies if escalation_required(p))

    avg_wait_query = (
        db.query(
            func.avg(
                (func.julianday(models.Patient.completed_at) - func.julianday(models.Patient.created_at))
                * 24
                * 60
            )
        )
        .filter(
            *today_filters,
            models.Patient.status == models.StatusEnum.COMPLETED,
            models.Patient.completed_at.isnot(None),
        )
        .scalar()
    )
    avg_wait = int(round(avg_wait_query or 0))

    emergency_percentage = round((emergency_today / total_today) * 100, 2) if total_today else 0.0
    completion_rate = round((completed_today / total_today) * 100, 2) if total_today else 0.0

    return {
        "total_patients_today": total_today,
        "average_wait_minutes": avg_wait,
        "emergency_percentage": emergency_percentage,
        "completion_rate": completion_rate,
        "overdue_emergencies": overdue_count,
    }
