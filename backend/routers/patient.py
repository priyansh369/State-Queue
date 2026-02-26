from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db

router = APIRouter(prefix="/patient", tags=["patient"])


AVERAGE_SERVICE_MINUTES = 10


def _compute_estimated_wait(
    db: Session, patient: models.Patient, doctor_id: int
) -> int:
    waiting_patients = (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == doctor_id,
            models.Patient.status == models.StatusEnum.WAITING,
        )
        .order_by(
            models.Patient.priority.desc(),  # emergency > normal
            models.Patient.queue_number.asc(),
        )
        .all()
    )
    position = 0
    for idx, p in enumerate(waiting_patients):
        if p.id == patient.id:
            position = idx
            break
    return position * AVERAGE_SERVICE_MINUTES


@router.post("/book", response_model=schemas.PatientOut)
def book_appointment(
    patient_in: schemas.PatientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.PATIENT)),
):
    # Assign next queue number
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

    # Create appointment record (same created_at as appointment date for simplicity)
    appointment = models.Appointment(
        patient_id=patient.id,
        doctor_id=patient_in.doctor_id,
        appointment_date=datetime.utcnow(),
        status=models.StatusEnum.WAITING,
    )
    db.add(appointment)
    db.commit()

    return patient


@router.get("/status/{id}", response_model=schemas.QueuePatient)
def get_status(id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    estimated_wait = _compute_estimated_wait(db, patient, patient.doctor_id)
    return schemas.QueuePatient(
        id=patient.id,
        name=patient.name,
        priority=patient.priority,
        status=patient.status,
        queue_number=patient.queue_number,
        symptoms=patient.symptoms,
        estimated_wait_minutes=estimated_wait,
    )


@router.get("/appointments/{id}", response_model=list[schemas.AppointmentOut])
def get_appointments(id: int, db: Session = Depends(get_db)):
    appointments = (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == id)
        .order_by(models.Appointment.appointment_date.desc())
        .all()
    )
    return appointments

