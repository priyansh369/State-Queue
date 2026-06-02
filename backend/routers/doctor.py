from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

import models, schemas
from auth_utils import require_role
from database import get_db
from ml_engine import compute_queue_estimates
from realtime import emit_queue_update
from sms_notifications import notify_now_serving_soon_sms, notify_status_updated_sms
from services.hospital import dashboard_analytics, map_queue_patient, write_audit_log
from ws_payloads import patient_payload

router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("/availability", response_model=schemas.DoctorOut)
def get_my_availability(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    doctor = db.users.find_one({"id": current_user["id"]})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return {"id": doctor["id"], "name": doctor["name"], "is_available": doctor.get("is_available", True)}


@router.put("/availability", response_model=schemas.DoctorOut)
def update_my_availability(
    body: schemas.UpdateDoctorAvailability,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    doctor = db.users.find_one({"id": current_user["id"]})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    db.users.update_one({"id": doctor["id"]}, {"$set": {"is_available": body.is_available}})
    write_audit_log(
        db,
        user_id=doctor["id"],
        action="DOCTOR_MARKED_AVAILABLE" if body.is_available else "DOCTOR_MARKED_UNAVAILABLE",
    )
    emit_queue_update(
        background_tasks,
        event_type="DOCTOR_AVAILABILITY_CHANGED",
        data={"doctor_id": doctor["id"], "is_available": body.is_available},
    )
    return {"id": doctor["id"], "name": doctor["name"], "is_available": body.is_available}


@router.get("/queue", response_model=list[schemas.QueuePatient])
def get_doctor_queue(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    estimates = compute_queue_estimates(db, current_user["id"])
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
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = db.patients.find_one({"id": id, "doctor_id": current_user["id"]})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return patient


@router.put("/complete/{id}", response_model=schemas.PatientOut)
def complete_patient(
    id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = db.patients.find_one({"id": id, "doctor_id": current_user["id"]})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    now = datetime.utcnow()
    appointment = db.appointments.find_one({"patient_id": id}, sort=[("appointment_date", -1)])
    started = patient.get("started_serving_at")
    if not started:
        started = (
            (appointment or {}).get("started_at")
            or (appointment or {}).get("appointment_date")
            or patient.get("created_at")
            or now
        )
        if started > now:
            started = now
    db.patients.update_one(
        {"id": id},
        {
            "$set": {
                "status": models.StatusEnum.COMPLETED,
                "completed_at": now,
                "started_serving_at": started,
            }
        },
    )
    patient["status"] = models.StatusEnum.COMPLETED
    patient["completed_at"] = now
    patient["started_serving_at"] = started

    if appointment:
        db.appointments.update_one(
            {"id": appointment["id"]},
            {
                "$set": {
                    "status": models.StatusEnum.COMPLETED,
                    "completed_at": now,
                    "started_at": appointment.get("started_at") or started,
                }
            },
        )

    token = db.opd_tokens.find_one(
        {
            "patient_id": patient["id"],
            "doctor_id": current_user["id"],
            "status": {"$in": [models.OpdTokenStatusEnum.WAITING, models.OpdTokenStatusEnum.IN_PROGRESS]},
        },
        sort=[("created_at", 1), ("id", 1)],
    )
    if token:
        db.opd_tokens.update_one(
            {"id": token["id"]},
            {"$set": {"status": models.OpdTokenStatusEnum.COMPLETED, "completed_at": now}},
        )

    write_audit_log(
        db,
        user_id=current_user["id"],
        action="MARK_PATIENT_COMPLETED",
        patient_id=patient["id"],
    )
    emit_queue_update(
        background_tasks,
        event_type="STATUS_UPDATED",
        data=patient_payload(patient),
    )
    background_tasks.add_task(
        notify_status_updated_sms,
        patient.get("contact_number"),
        status="COMPLETED",
        doctor_name=current_user.get("name"),
    )
    estimates = compute_queue_estimates(db, current_user["id"])
    soon_items = [(e.patient["id"], e.patient.get("contact_number"), e.eta_minutes) for e in estimates]
    background_tasks.add_task(
        notify_now_serving_soon_sms,
        soon_items,
        doctor_name=current_user.get("name"),
    )
    return patient


@router.put("/start/{id}", response_model=schemas.PatientOut)
def start_serving_patient(
    id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    patient = db.patients.find_one({"id": id, "doctor_id": current_user["id"]})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if patient.get("status") != models.StatusEnum.WAITING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not waiting")

    top = sorted(
        list(db.patients.find({"doctor_id": current_user["id"], "status": models.StatusEnum.WAITING})),
        key=lambda p: (
            0 if p.get("priority") == models.PriorityEnum.EMERGENCY else 1,
            p.get("created_at"),
        ),
    )
    if top and top[0]["id"] != patient["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only the next patient in queue can be started")

    now = datetime.utcnow()
    if not patient.get("started_serving_at"):
        db.patients.update_one({"id": id}, {"$set": {"started_serving_at": now}})
        patient["started_serving_at"] = now

    appointment = db.appointments.find_one({"patient_id": id}, sort=[("appointment_date", -1)])
    if appointment and not appointment.get("started_at"):
        db.appointments.update_one({"id": appointment["id"]}, {"$set": {"started_at": now}})

    token = db.opd_tokens.find_one(
        {
            "patient_id": patient["id"],
            "doctor_id": current_user["id"],
            "status": models.OpdTokenStatusEnum.WAITING,
        },
        sort=[("created_at", 1), ("id", 1)],
    )
    if token:
        db.opd_tokens.update_one(
            {"id": token["id"]},
            {"$set": {"status": models.OpdTokenStatusEnum.IN_PROGRESS, "called_at": now}},
        )

    emit_queue_update(
        background_tasks,
        event_type="STATUS_UPDATED",
        data=patient_payload(patient),
    )
    background_tasks.add_task(
        notify_status_updated_sms,
        patient.get("contact_number"),
        status="STARTED",
        doctor_name=current_user.get("name"),
    )
    estimates = compute_queue_estimates(db, current_user["id"])
    soon_items = [(e.patient["id"], e.patient.get("contact_number"), e.eta_minutes) for e in estimates]
    background_tasks.add_task(
        notify_now_serving_soon_sms,
        soon_items,
        doctor_name=current_user.get("name"),
    )
    return patient


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def doctor_dashboard_stats(
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.DOCTOR)),
):
    total_patients = db.patients.count_documents({"doctor_id": current_user["id"]})
    waiting = db.patients.count_documents({"doctor_id": current_user["id"], "status": models.StatusEnum.WAITING})
    emergency = db.patients.count_documents(
        {
            "doctor_id": current_user["id"],
            "status": models.StatusEnum.WAITING,
            "priority": models.PriorityEnum.EMERGENCY,
        }
    )
    completed = db.patients.count_documents({"doctor_id": current_user["id"], "status": models.StatusEnum.COMPLETED})
    analytics = dashboard_analytics(db, doctor_id=current_user["id"])
    return schemas.DashboardStats(
        total_patients=total_patients,
        waiting=waiting,
        emergency=emergency,
        completed=completed,
        **analytics,
    )
