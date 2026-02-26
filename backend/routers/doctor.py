from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from .patient import _compute_estimated_wait

router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_doctor_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patients = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == current_user.id,
            models.Patient.status == models.StatusEnum.WAITING,
        )
        .order_by(
            models.Patient.priority.desc(),
            models.Patient.queue_number.asc(),
        )
        .all()
    )

    result: list[schemas.QueuePatient] = []
    for p in patients:
        estimated_wait = _compute_estimated_wait(db, p, current_user.id)
        result.append(
            schemas.QueuePatient(
                id=p.id,
                name=p.name,
                priority=p.priority,
                status=p.status,
                queue_number=p.queue_number,
                symptoms=p.symptoms,
                estimated_wait_minutes=estimated_wait,
            )
        )
    return result


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
    patient.status = models.StatusEnum.COMPLETED
    db.add(patient)

    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == id)
        .order_by(models.Appointment.appointment_date.desc())
        .first()
    )
    if appointment:
        appointment.status = models.StatusEnum.COMPLETED
        db.add(appointment)

    db.commit()
    db.refresh(patient)
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
    return schemas.DashboardStats(
        total_patients=total_patients,
        waiting=waiting,
        emergency=emergency,
        completed=completed,
    )

