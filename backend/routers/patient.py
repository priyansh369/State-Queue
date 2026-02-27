from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from ..ml_engine import compute_patient_eta_minutes, compute_queue_estimates, estimate_next_service_minutes
from ..realtime import emit_queue_update

router = APIRouter(prefix="/patient", tags=["patient"])


@router.post("/book", response_model=schemas.PatientOut)
def book_appointment(
    patient_in: schemas.PatientCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.PATIENT)),
):
    # Assign next token number for this doctor (per-doctor queue)
    max_queue = (
        db.query(models.Patient.queue_number)
        .filter(models.Patient.doctor_id == patient_in.doctor_id)
        .order_by(models.Patient.queue_number.desc())
        .first()
    )
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

    emit_queue_update(
        background_tasks,
        reason="patient_booked",
        doctor_id=patient.doctor_id,
        patient_id=patient.id,
    )

    return patient


@router.get("/status/{id}", response_model=schemas.QueuePatient)
def get_status(id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # token number is the current position in the doctor's queue (1..n)
    estimates = compute_queue_estimates(db, patient.doctor_id)
    token_number = next(
        (idx + 1 for idx, e in enumerate(estimates) if e.patient.id == patient.id),
        patient.queue_number,
    )
    estimated_wait = compute_patient_eta_minutes(db, patient)
    return schemas.QueuePatient(
        id=patient.id,
        name=patient.name,
        priority=patient.priority,
        status=patient.status,
        queue_number=token_number,
        symptoms=patient.symptoms,
        estimated_wait_minutes=estimated_wait,
    )


@router.get("/live-status/{id}", response_model=schemas.LiveQueueStatus)
def get_live_status(id: int, db: Session = Depends(get_db)):
    """
    Single source of truth for Patient dashboard.
    Returns: now serving token, waiting count, and ML-based ETA for this patient.
    """
    patient = db.query(models.Patient).filter(models.Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    estimates = compute_queue_estimates(db, patient.doctor_id)
    now_serving = estimates[0].patient if estimates else None
    token_number = next(
        (idx + 1 for idx, e in enumerate(estimates) if e.patient.id == patient.id),
        patient.queue_number,
    )

    eta = compute_patient_eta_minutes(db, patient)
    avg_service = int(round(estimate_next_service_minutes(db, patient.doctor_id)))

    return schemas.LiveQueueStatus(
        patient=schemas.QueuePatient(
            id=patient.id,
            name=patient.name,
            priority=patient.priority,
            status=patient.status,
            queue_number=token_number,
            symptoms=patient.symptoms,
            estimated_wait_minutes=eta,
        ),
        current_token_id=now_serving.id if now_serving else None,
        current_token_queue_number=1 if now_serving else None,
        waiting_count=len(estimates),
        doctor_average_service_minutes=avg_service,
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

