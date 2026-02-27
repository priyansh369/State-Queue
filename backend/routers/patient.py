from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from ..ml_engine import compute_patient_eta_minutes, compute_queue_estimates, estimate_next_service_minutes
from ..realtime import emit_queue_update
from ..services.hospital import (
    create_appointment_for_patient,
    create_patient_with_queue,
    map_queue_patient,
)
from ..ws_payloads import patient_payload

router = APIRouter(prefix="/patient", tags=["patient"])


@router.post("/book", response_model=schemas.PatientOut)
def book_appointment(
    patient_in: schemas.PatientCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.PATIENT)),
):
    try:
        patient = create_patient_with_queue(
            db,
            name=patient_in.name,
            age=patient_in.age,
            gender=patient_in.gender,
            symptoms=patient_in.symptoms,
            priority=patient_in.priority,
            doctor_id=patient_in.doctor_id,
        )
        create_appointment_for_patient(db, patient_id=patient.id, doctor_id=patient_in.doctor_id)
        db.commit()
        db.refresh(patient)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to allocate queue number. Please retry.",
        )

    emit_queue_update(
        background_tasks,
        event_type="NEW_APPOINTMENT",
        data=patient_payload(patient),
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
    return map_queue_patient(db, patient, queue_number=token_number, estimated_wait_minutes=estimated_wait)


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
        patient=map_queue_patient(
            db,
            patient,
            queue_number=token_number,
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

