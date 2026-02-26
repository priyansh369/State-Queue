from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from .patient import _compute_estimated_wait

router = APIRouter(prefix="/reception", tags=["reception"])


@router.post("/register-patient", response_model=schemas.PatientOut)
def register_patient(
    patient_in: schemas.ReceptionRegisterPatient,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    max_queue = db.query(models.Patient.queue_number).order_by(
        models.Patient.queue_number.desc()
    ).first()
    next_queue = (max_queue[0] if max_queue else 0) + 1

    patient = models.Patient(
        name=patient_in.name,
        age=patient_in.age,
        gender=patient_in.gender,
        symptoms=patient_in.symptoms,
        priority=patient_in.priority,
        status=models.StatusEnum.WAITING,
        queue_number=next_queue,
        doctor_id=patient_in.doctor_id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_full_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    patients = (
        db.query(models.Patient)
        .filter(models.Patient.status == models.StatusEnum.WAITING)
        .order_by(
            models.Patient.priority.desc(),
            models.Patient.queue_number.asc(),
        )
        .all()
    )
    result: list[schemas.QueuePatient] = []
    for p in patients:
        estimated = _compute_estimated_wait(db, p, p.doctor_id)
        result.append(
            schemas.QueuePatient(
                id=p.id,
                name=p.name,
                priority=p.priority,
                status=p.status,
                queue_number=p.queue_number,
                symptoms=p.symptoms,
                estimated_wait_minutes=estimated,
            )
        )
    return result


@router.put("/update-priority/{id}", response_model=schemas.PatientOut)
def update_priority(
    id: int,
    body: schemas.UpdatePriority,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    if body.priority not in [
        models.PriorityEnum.NORMAL,
        models.PriorityEnum.EMERGENCY,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid priority",
        )
    patient = db.query(models.Patient).filter(models.Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    patient.priority = body.priority
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/cancel/{id}")
def cancel_patient(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    patient = db.query(models.Patient).filter(models.Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    patient.status = models.StatusEnum.CANCELLED
    db.add(patient)

    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == id)
        .order_by(models.Appointment.appointment_date.desc())
        .first()
    )
    if appointment:
        appointment.status = models.StatusEnum.CANCELLED
        db.add(appointment)

    db.commit()
    return {"detail": "Cancelled"}


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def reception_dashboard_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    total_patients = db.query(models.Patient).count()
    waiting = (
        db.query(models.Patient)
        .filter(models.Patient.status == models.StatusEnum.WAITING)
        .count()
    )
    emergency = (
        db.query(models.Patient)
        .filter(
            models.Patient.status == models.StatusEnum.WAITING,
            models.Patient.priority == models.PriorityEnum.EMERGENCY,
        )
        .count()
    )
    completed = (
        db.query(models.Patient)
        .filter(models.Patient.status == models.StatusEnum.COMPLETED)
        .count()
    )
    return schemas.DashboardStats(
        total_patients=total_patients,
        waiting=waiting,
        emergency=emergency,
        completed=completed,
    )

