from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import require_role
from ..database import get_db
from ..ml_engine import compute_patient_eta_minutes, compute_queue_estimates
from ..realtime import emit_queue_update
from ..services.hospital import (
    create_appointment_for_patient,
    create_patient_with_queue,
    dashboard_analytics,
    map_queue_patient,
    write_audit_log,
)
from ..ws_payloads import patient_payload

router = APIRouter(prefix="/reception", tags=["reception"])


@router.post("/register-patient", response_model=schemas.PatientOut)
def register_patient(
    patient_in: schemas.ReceptionRegisterPatient,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
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


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_full_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
    doctor_id: int | None = None,
):
    if doctor_id is not None:
        estimates = compute_queue_estimates(db, doctor_id)
        return [
            map_queue_patient(
                db,
                e.patient,
                queue_number=idx + 1,
                estimated_wait_minutes=e.eta_minutes,
            )
            for idx, e in enumerate(estimates)
        ]

    patients = (
        db.query(models.Patient)
        .filter(models.Patient.status == models.StatusEnum.WAITING)
        .order_by(
            case((models.Patient.priority == models.PriorityEnum.EMERGENCY, 0), else_=1).asc(),
            models.Patient.created_at.asc(),
        )
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
        map_queue_patient(
            db,
            p,
            queue_number=token_by_id.get(p.id, p.queue_number),
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
    write_audit_log(
        db,
        user_id=current_user.id,
        action=f"CHANGE_PRIORITY_TO_{body.priority.upper()}",
        patient_id=patient.id,
    )
    db.commit()
    db.refresh(patient)
    emit_queue_update(
        background_tasks,
        event_type="PRIORITY_CHANGED",
        data=patient_payload(patient),
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

    write_audit_log(
        db,
        user_id=current_user.id,
        action="CANCEL_APPOINTMENT",
        patient_id=patient.id,
    )
    db.commit()
    emit_queue_update(
        background_tasks,
        event_type="APPOINTMENT_CANCELLED",
        data=patient_payload(patient),
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
    analytics = dashboard_analytics(db)
    return schemas.DashboardStats(
        total_patients=total_patients,
        waiting=waiting,
        emergency=emergency,
        completed=completed,
        **analytics,
    )


@router.get("/audit-logs", response_model=list[schemas.AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST)),
    limit: int = 100,
):
    safe_limit = max(1, min(limit, 200))
    logs = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.timestamp.desc())
        .limit(safe_limit)
        .all()
    )
    return logs

