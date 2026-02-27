from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from ..ml_engine import compute_patient_eta_minutes, compute_queue_estimates
from ..realtime import emit_queue_update

router = APIRouter(prefix="/reception", tags=["reception"])


@router.post("/register-patient", response_model=schemas.PatientOut)
def register_patient(
    patient_in: schemas.ReceptionRegisterPatient,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
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

    # Create appointment record so ML has a consistent source.
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
        reason="walkin_registered",
        doctor_id=patient.doctor_id,
        patient_id=patient.id,
    )
    return patient


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_full_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
    doctor_id: int | None = None,
):
    if doctor_id is not None:
        estimates = compute_queue_estimates(db, doctor_id)
        return [
            schemas.QueuePatient(
                id=e.patient.id,
                name=e.patient.name,
                priority=e.patient.priority,
                status=e.patient.status,
                queue_number=idx + 1,
                symptoms=e.patient.symptoms,
                estimated_wait_minutes=e.eta_minutes,
            )
            for idx, e in enumerate(estimates)
        ]

    patients = (
        db.query(models.Patient)
        .filter(models.Patient.status == models.StatusEnum.WAITING)
        .order_by(models.Patient.priority.desc(), models.Patient.queue_number.asc())
        .all()
    )
    # build per-doctor token positions for display
    token_by_id: dict[int, int] = {}
    computed_doctors: set[int] = set()
    for p in patients:
        if p.doctor_id is None or p.doctor_id in computed_doctors:
            continue
        computed_doctors.add(p.doctor_id)
        for idx, e in enumerate(compute_queue_estimates(db, p.doctor_id)):
            token_by_id[e.patient.id] = idx + 1

    return [
        schemas.QueuePatient(
            id=p.id,
            name=p.name,
            priority=p.priority,
            status=p.status,
            queue_number=token_by_id.get(p.id, p.queue_number),
            symptoms=p.symptoms,
            estimated_wait_minutes=compute_patient_eta_minutes(db, p),
        )
        for p in patients
    ]


@router.put("/update-priority/{id}", response_model=schemas.PatientOut)
def update_priority(
    id: int,
    body: schemas.UpdatePriority,
    background_tasks: BackgroundTasks,
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
    emit_queue_update(
        background_tasks,
        reason="priority_updated",
        doctor_id=patient.doctor_id,
        patient_id=patient.id,
    )
    return patient


@router.delete("/cancel/{id}")
def cancel_patient(
    id: int,
    background_tasks: BackgroundTasks,
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
    emit_queue_update(
        background_tasks,
        reason="patient_cancelled",
        doctor_id=patient.doctor_id,
        patient_id=patient.id,
    )
    return {"detail": "Cancelled"}


@router.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
):
    doctors = (
        db.query(models.User)
        .filter(models.User.role == models.UserRoleEnum.DOCTOR)
        .order_by(models.User.name.asc())
        .all()
    )
    return doctors


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

