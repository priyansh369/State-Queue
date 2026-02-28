from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from ..ml_engine import compute_queue_estimates
from ..realtime import emit_queue_update
from ..services.hospital import dashboard_analytics, map_queue_patient, write_audit_log
from ..ws_payloads import patient_payload

router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_doctor_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    estimates = compute_queue_estimates(db, current_user.id)
    return [
        map_queue_patient(
            db,
            e.patient,
            queue_number=idx + 1,
            estimated_wait_minutes=e.eta_minutes,
        )
        for idx, e in enumerate(estimates)
    ]


@router.get("/patient/{id}", response_model=schemas.PatientOut)
def get_patient_details(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = (
        db.query(models.Patient)
        .filter(
            models.Patient.id == id,
            models.Patient.doctor_id == current_user.id,
        )
        .first()
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return patient


@router.put("/complete/{id}", response_model=schemas.PatientOut)
def complete_patient(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = (
        db.query(models.Patient)
        .filter(
            models.Patient.id == id,
            models.Patient.doctor_id == current_user.id,
        )
        .first()
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    now = datetime.utcnow()
    patient.status = models.StatusEnum.COMPLETED
    patient.completed_at = now
    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == id)
        .order_by(models.Appointment.appointment_date.desc())
        .first()
    )

    # Best-effort start time for duration math (even if "Start" wasn't clicked).
    started = patient.started_serving_at
    if not started:
        started = (
            (appointment.started_at if appointment else None)
            or (appointment.appointment_date if appointment else None)
            or patient.created_at
            or now
        )
        if started > now:
            started = now
        patient.started_serving_at = started

    db.add(patient)

    if appointment:
        appointment.status = models.StatusEnum.COMPLETED
        appointment.completed_at = now
        if not appointment.started_at:
            appointment.started_at = started
        db.add(appointment)

    write_audit_log(
        db,
        user_id=current_user.id,
        action="MARK_PATIENT_COMPLETED",
        patient_id=patient.id,
    )
    db.commit()
    db.refresh(patient)

    emit_queue_update(
        background_tasks,
        event_type="STATUS_UPDATED",
        data=patient_payload(patient),
    )
    return patient


@router.put("/start/{id}", response_model=schemas.PatientOut)
def start_serving_patient(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = (
        db.query(models.Patient)
        .filter(
            models.Patient.id == id,
            models.Patient.doctor_id == current_user.id,
        )
        .first()
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if patient.status != models.StatusEnum.WAITING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not waiting")

    # Optional correctness: only allow starting the top-of-queue patient
    top = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == current_user.id,
            models.Patient.status == models.StatusEnum.WAITING,
        )
        .order_by(
            case((models.Patient.priority == models.PriorityEnum.EMERGENCY, 0), else_=1).asc(),
            models.Patient.created_at.asc(),
        )
        .first()
    )
    if top and top.id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only the next patient in queue can be started",
        )

    now = datetime.utcnow()
    if not patient.started_serving_at:
        patient.started_serving_at = now
        db.add(patient)

    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == id)
        .order_by(models.Appointment.appointment_date.desc())
        .first()
    )
    if appointment and not appointment.started_at:
        appointment.started_at = now
        db.add(appointment)

    db.commit()
    db.refresh(patient)

    emit_queue_update(
        background_tasks,
        event_type="STATUS_UPDATED",
        data=patient_payload(patient),
    )
    return patient


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def doctor_dashboard_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    total_patients = (
        db.query(models.Patient)
        .filter(models.Patient.doctor_id == current_user.id)
        .count()
    )
    waiting = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == current_user.id,
            models.Patient.status == models.StatusEnum.WAITING,
        )
        .count()
    )
    emergency = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == current_user.id,
            models.Patient.status == models.StatusEnum.WAITING,
            models.Patient.priority == models.PriorityEnum.EMERGENCY,
        )
        .count()
    )
    completed = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == current_user.id,
            models.Patient.status == models.StatusEnum.COMPLETED,
        )
        .count()
    )
    analytics = dashboard_analytics(db, doctor_id=current_user.id)
    return schemas.DashboardStats(
        total_patients=total_patients,
        waiting=waiting,
        emergency=emergency,
        completed=completed,
        **analytics,
    )

