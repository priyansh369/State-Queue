from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

import models, schemas
from auth_utils import require_role
from database import get_db
from realtime import emit_queue_update
from services.opd import (
    call_next_waiting_token,
    complete_token,
    create_opd_token,
    list_doctor_tokens,
    waiting_screen_summary,
)

router = APIRouter(prefix="/tokens", tags=["tokens"])


def _to_token_out(db, token: dict) -> schemas.OpdTokenOut:
    patient = db.patients.find_one({"id": token["patient_id"]}, {"name": 1})
    doctor = db.users.find_one({"id": token["doctor_id"]}, {"name": 1})
    return schemas.OpdTokenOut(
        id=token["id"],
        token_number=token["token_number"],
        patient_id=token["patient_id"],
        doctor_id=token["doctor_id"],
        status=token["status"],
        created_at=token["created_at"],
        called_at=token.get("called_at"),
        completed_at=token.get("completed_at"),
        patient_name=(patient or {}).get("name"),
        doctor_name=(doctor or {}).get("name"),
    )


@router.post("/generate", response_model=schemas.OpdTokenOut)
def generate_token(
    body: schemas.CreateTokenRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    patient = db.patients.find_one({"id": body.patient_id})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    doctor = db.users.find_one({"id": body.doctor_id, "role": models.UserRoleEnum.DOCTOR})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    active = db.opd_tokens.find_one(
        {"patient_id": patient["id"], "status": {"$ne": models.OpdTokenStatusEnum.COMPLETED}}
    )
    if active:
        return _to_token_out(db, active)

    token = create_opd_token(db, patient_id=patient["id"], doctor_id=doctor["id"])
    emit_queue_update(
        background_tasks,
        event_type="TOKEN_GENERATED",
        data={
            "doctor_id": token["doctor_id"],
            "patient_id": token["patient_id"],
            "token_id": token["id"],
            "token_number": token["token_number"],
            "status": token["status"],
        },
    )
    return _to_token_out(db, token)


@router.get("", response_model=list[schemas.OpdTokenOut])
def get_tokens(
    doctor_id: int | None = Query(default=None, gt=0),
    include_completed: bool = True,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.DOCTOR, models.UserRoleEnum.ADMIN)),
):
    effective_doctor_id = doctor_id
    if current_user.get("role") == models.UserRoleEnum.DOCTOR:
        effective_doctor_id = current_user["id"]
    if not effective_doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doctor_id is required")
    tokens = list_doctor_tokens(db, doctor_id=effective_doctor_id, include_completed=include_completed)
    return [_to_token_out(db, token) for token in tokens]


@router.post("/call-next", response_model=schemas.OpdTokenOut)
def call_next_token(
    background_tasks: BackgroundTasks,
    doctor_id: int | None = Query(default=None, gt=0),
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.DOCTOR, models.UserRoleEnum.ADMIN)),
):
    effective_doctor_id = doctor_id
    if current_user.get("role") == models.UserRoleEnum.DOCTOR:
        effective_doctor_id = current_user["id"]
    if not effective_doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doctor_id is required")

    token = call_next_waiting_token(db, doctor_id=effective_doctor_id)
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No waiting token found")

    now = datetime.utcnow()
    patient = db.patients.find_one({"id": token["patient_id"]})
    if patient and not patient.get("started_serving_at"):
        db.patients.update_one({"id": patient["id"]}, {"$set": {"started_serving_at": now}})
    appointment = db.appointments.find_one({"patient_id": token["patient_id"]}, sort=[("appointment_date", -1)])
    if appointment and not appointment.get("started_at"):
        db.appointments.update_one({"id": appointment["id"]}, {"$set": {"started_at": now}})

    emit_queue_update(
        background_tasks,
        event_type="TOKEN_CALLED",
        data={
            "doctor_id": token["doctor_id"],
            "patient_id": token["patient_id"],
            "token_id": token["id"],
            "token_number": token["token_number"],
            "status": token["status"],
        },
    )
    return _to_token_out(db, token)


@router.post("/{token_id}/complete", response_model=schemas.OpdTokenOut)
def mark_token_complete(
    token_id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.DOCTOR, models.UserRoleEnum.ADMIN)),
):
    token = db.opd_tokens.find_one({"id": token_id})
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if current_user.get("role") == models.UserRoleEnum.DOCTOR and token["doctor_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    complete_token(db, token=token)
    now = datetime.utcnow()
    patient = db.patients.find_one({"id": token["patient_id"]})
    appointment = db.appointments.find_one({"patient_id": token["patient_id"]}, sort=[("appointment_date", -1)])
    if patient:
        db.patients.update_one(
            {"id": patient["id"]},
            {"$set": {"status": models.StatusEnum.COMPLETED, "completed_at": patient.get("completed_at") or now}},
        )
    if appointment:
        db.appointments.update_one(
            {"id": appointment["id"]},
            {"$set": {"status": models.StatusEnum.COMPLETED, "completed_at": appointment.get("completed_at") or now}},
        )

    emit_queue_update(
        background_tasks,
        event_type="TOKEN_COMPLETED",
        data={
            "doctor_id": token["doctor_id"],
            "patient_id": token["patient_id"],
            "token_id": token["id"],
            "token_number": token["token_number"],
            "status": models.OpdTokenStatusEnum.COMPLETED,
        },
    )
    latest = db.opd_tokens.find_one({"id": token_id})
    return _to_token_out(db, latest)


@router.get("/waiting-screen/{doctor_id}", response_model=schemas.WaitingScreenSummary)
def get_waiting_screen(
    doctor_id: int,
    db=Depends(get_db),
):
    try:
        doctor, now_serving, next_token, upcoming = waiting_screen_summary(
            db,
            doctor_id=doctor_id,
            limit_upcoming=12,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    return schemas.WaitingScreenSummary(
        doctor_id=doctor["id"],
        doctor_name=doctor["name"],
        now_serving=_to_token_out(db, now_serving) if now_serving else None,
        next_token=_to_token_out(db, next_token) if next_token else None,
        upcoming_tokens=[_to_token_out(db, t) for t in upcoming],
        refreshed_at=datetime.utcnow(),
    )


@router.get("/generation-candidates", response_model=list[schemas.PatientOut])
def token_generation_candidates(
    doctor_id: int = Query(gt=0),
    db=Depends(get_db),
    current_user=Depends(require_role(models.UserRoleEnum.RECEPTIONIST, models.UserRoleEnum.ADMIN)),
):
    patients = list(
        db.patients.find(
            {"doctor_id": doctor_id, "status": models.StatusEnum.WAITING},
            {"_id": 0},
        ).sort("created_at", 1)
    )
    if not patients:
        return []
    patient_ids = [p["id"] for p in patients]
    active_ids = {
        row["patient_id"]
        for row in db.opd_tokens.find(
            {"patient_id": {"$in": patient_ids}, "status": {"$ne": models.OpdTokenStatusEnum.COMPLETED}},
            {"patient_id": 1},
        )
    }
    return [p for p in patients if p["id"] not in active_ids]
