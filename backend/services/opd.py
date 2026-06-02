from __future__ import annotations

from datetime import datetime

import models
from pymongo import ReturnDocument
from mongo import next_id, utcnow


def _token_day(value: datetime | None = None) -> str:
    dt = value or utcnow()
    return dt.strftime("%Y-%m-%d")


def _today_token_max(db, doctor_id: int) -> int:
    row = db.opd_tokens.find_one(
        {
            "doctor_id": doctor_id,
            "token_day": _token_day(),
        },
        {"token_number": 1},
        sort=[("token_number", -1)],
    )
    return int((row or {}).get("token_number", 0))


def create_opd_token(
    db,
    *,
    patient_id: int,
    doctor_id: int,
) -> dict:
    now = utcnow()
    token = {
        "id": next_id("opd_tokens"),
        "token_number": _today_token_max(db, doctor_id) + 1,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "status": models.OpdTokenStatusEnum.WAITING,
        "created_at": now,
        "called_at": None,
        "completed_at": None,
        "token_day": _token_day(now),
    }
    db.opd_tokens.insert_one(token)
    return token


def list_doctor_tokens(
    db,
    *,
    doctor_id: int,
    include_completed: bool = True,
) -> list[dict]:
    query = {"doctor_id": doctor_id}
    if not include_completed:
        query["status"] = {"$ne": models.OpdTokenStatusEnum.COMPLETED}
    return list(db.opd_tokens.find(query).sort([("created_at", 1), ("id", 1)]))


def call_next_waiting_token(db, *, doctor_id: int) -> dict | None:
    token = db.opd_tokens.find_one_and_update(
        {
            "doctor_id": doctor_id,
            "status": models.OpdTokenStatusEnum.WAITING,
        },
        {"$set": {"status": models.OpdTokenStatusEnum.IN_PROGRESS, "called_at": utcnow()}},
        sort=[("created_at", 1), ("id", 1)],
        return_document=ReturnDocument.AFTER,
    )
    return token


def complete_token(db, *, token: dict) -> dict:
    db.opd_tokens.update_one(
        {"id": token["id"]},
        {"$set": {"status": models.OpdTokenStatusEnum.COMPLETED, "completed_at": utcnow()}},
    )
    token["status"] = models.OpdTokenStatusEnum.COMPLETED
    token["completed_at"] = utcnow()
    return token


def waiting_screen_summary(
    db,
    *,
    doctor_id: int,
    limit_upcoming: int = 10,
) -> tuple[dict, dict | None, dict | None, list[dict]]:
    doctor = db.users.find_one({"id": doctor_id, "role": models.UserRoleEnum.DOCTOR})
    if not doctor:
        raise ValueError("Doctor not found")

    now_serving = db.opd_tokens.find_one(
        {"doctor_id": doctor_id, "status": models.OpdTokenStatusEnum.IN_PROGRESS},
        sort=[("called_at", -1), ("id", -1)],
    )
    waiting_tokens = list(
        db.opd_tokens.find(
            {"doctor_id": doctor_id, "status": models.OpdTokenStatusEnum.WAITING}
        ).sort([("created_at", 1), ("id", 1)]).limit(max(1, limit_upcoming))
    )
    next_token = waiting_tokens[0] if waiting_tokens else None
    return doctor, now_serving, next_token, waiting_tokens
