from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

import models, schemas
from auth_utils import require_role
from database import get_db
from ml_engine import compute_patient_eta_minutes, compute_queue_estimates
from realtime import emit_queue_update
from sms_notifications import notify_new_appointment_sms
from services.hospital import (
    create_appointment_for_patient,
    create_patient_with_queue,
    dashboard_analytics,
    map_queue_patient,
    write_audit_log,
)
from services.opd import create_opd_token
from ws_payloads import patient_payload

router = APIRouter(prefix="/reception", tags=["reception"])


@router.post("/register-patient", response_model=schemas.PatientOut)
def register_patient(
    patient_in: schemas.ReceptionRegisterPatient,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    doctor = db.users.find_one({"id": patient_in.doctor_id, "role": models.UserRoleEnum.DOCTOR})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if not doctor.get("is_available", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected doctor is currently unavailable",
        )

    patient = create_patient_with_queue(
        db,
        name=patient_in.name,
        age=patient_in.age,
        gender=patient_in.gender,
        contact_number=patient_in.contact_number,
        symptoms=patient_in.symptoms,
        priority=patient_in.priority,
        doctor_id=patient_in.doctor_id,
    )
    create_appointment_for_patient(db, patient_id=patient["id"], doctor_id=patient_in.doctor_id)
    create_opd_token(db, patient_id=patient["id"], doctor_id=patient_in.doctor_id)

    emit_queue_update(
        background_tasks,
        event_type="NEW_APPOINTMENT",
        data=patient_payload(patient),
    )
    eta = compute_patient_eta_minutes(db, patient)
    background_tasks.add_task(
        notify_new_appointment_sms,
        patient.get("contact_number"),
        queue_number=patient.get("queue_number"),
        eta_minutes=eta,
        doctor_name=doctor.get("name"),
    )
    return patient


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_full_queue(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
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

    patients = list(db.patients.find({"status": models.StatusEnum.WAITING}))
    patients = sorted(
        patients,
        key=lambda p: (
            0 if p.get("priority") == models.PriorityEnum.EMERGENCY else 1,
            p.get("created_at"),
        ),
    )
    token_by_id: dict[int, int] = {}
    computed_doctors: set[int] = set()
    for p in patients:
        doctor = p.get("doctor_id")
        if doctor is None or doctor in computed_doctors:
            continue
        computed_doctors.add(doctor)
        for idx, e in enumerate(compute_queue_estimates(db, doctor)):
            token_by_id[e.patient["id"]] = idx + 1

    return [
        map_queue_patient(
            db,
            p,
            queue_number=token_by_id.get(p["id"], p.get("queue_number", 0)),
            estimated_wait_minutes=compute_patient_eta_minutes(db, p),
        )
        for p in patients
    ]


@router.put("/update-priority/{id}", response_model=schemas.PatientOut)
def update_priority(
    id: int,
    body: schemas.UpdatePriority,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    if body.priority not in [models.PriorityEnum.NORMAL, models.PriorityEnum.EMERGENCY]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid priority")
    patient = db.patients.find_one({"id": id})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.patients.update_one({"id": id}, {"$set": {"priority": body.priority}})
    patient["priority"] = body.priority
    write_audit_log(
        db,
        user_id=current_user["id"],
        action=f"CHANGE_PRIORITY_TO_{body.priority.upper()}",
        patient_id=patient["id"],
    )
    emit_queue_update(
        background_tasks,
        event_type="PRIORITY_CHANGED",
        data=patient_payload(patient),
    )
    return patient


@router.put("/transfer/{id}", response_model=schemas.PatientOut)
def transfer_patient(
    id: int,
    body: schemas.TransferPatient,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    patient = db.patients.find_one({"id": id})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if patient.get("status") != models.StatusEnum.WAITING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only waiting patients can be transferred")
    if patient.get("doctor_id") == body.doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient is already assigned to this doctor")

    target_doctor = db.users.find_one({"id": body.doctor_id, "role": models.UserRoleEnum.DOCTOR})
    if not target_doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target doctor not found")
    if not target_doctor.get("is_available", True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target doctor is currently unavailable")

    max_queue_doc = db.patients.find_one({"doctor_id": body.doctor_id}, {"queue_number": 1}, sort=[("queue_number", -1)])
    next_queue = (max_queue_doc or {}).get("queue_number", 0) + 1
    db.patients.update_one({"id": id}, {"$set": {"doctor_id": body.doctor_id, "queue_number": next_queue}})
    patient["doctor_id"] = body.doctor_id
    patient["queue_number"] = next_queue

    appointment = db.appointments.find_one(
        {"patient_id": id, "status": models.StatusEnum.WAITING},
        sort=[("appointment_date", -1)],
    )
    if appointment:
        db.appointments.update_one({"id": appointment["id"]}, {"$set": {"doctor_id": body.doctor_id}})

    write_audit_log(
        db,
        user_id=current_user["id"],
        action=f"TRANSFER_PATIENT_TO_DOCTOR_{body.doctor_id}",
        patient_id=patient["id"],
    )
    emit_queue_update(
        background_tasks,
        event_type="PATIENT_TRANSFERRED",
        data=patient_payload(patient),
    )
    return patient


@router.delete("/cancel/{id}")
def cancel_patient(
    id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    patient = db.patients.find_one({"id": id})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.patients.update_one({"id": id}, {"$set": {"status": models.StatusEnum.CANCELLED}})
    patient["status"] = models.StatusEnum.CANCELLED

    appointment = db.appointments.find_one({"patient_id": id}, sort=[("appointment_date", -1)])
    if appointment:
        db.appointments.update_one({"id": appointment["id"]}, {"$set": {"status": models.StatusEnum.CANCELLED}})

    write_audit_log(
        db,
        user_id=current_user["id"],
        action="CANCEL_APPOINTMENT",
        patient_id=patient["id"],
    )
    emit_queue_update(
        background_tasks,
        event_type="APPOINTMENT_CANCELLED",
        data=patient_payload(patient),
    )
    return {"detail": "Cancelled"}


@router.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
    include_unavailable: bool = True,
):
    query = {"role": models.UserRoleEnum.DOCTOR}
    if not include_unavailable:
        query["is_available"] = True
    doctors = list(
        db.users.find(query, {"_id": 0, "id": 1, "name": 1, "is_available": 1}).sort("name", 1)
    )
    return doctors


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def reception_dashboard_stats(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    total_patients = db.patients.count_documents({})
    waiting = db.patients.count_documents({"status": models.StatusEnum.WAITING})
    emergency = db.patients.count_documents(
        {"status": models.StatusEnum.WAITING, "priority": models.PriorityEnum.EMERGENCY}
    )
    completed = db.patients.count_documents({"status": models.StatusEnum.COMPLETED})
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
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
    limit: int = 100,
):
    safe_limit = max(1, min(limit, 200))
    logs = list(db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(safe_limit))
    return logs
