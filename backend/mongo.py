from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.server_api import ServerApi

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "statq")

_client = MongoClient(MONGODB_URI, server_api=ServerApi("1"))
db: Database = _client[MONGODB_DB]


def get_db() -> Database:
    return db


def collection(name: str) -> Collection:
    return db[name]


def ping_database() -> dict[str, str]:
    db.client.admin.command("ping")
    return {
        "status": "ok",
        "database": db.name,
    }


def utcnow() -> datetime:
    return datetime.utcnow()


def next_id(counter_name: str) -> int:
    row = db.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(row["seq"])


def ensure_indexes() -> None:
    db.users.create_index([("id", ASCENDING)], unique=True)
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.users.create_index([("role", ASCENDING)])
    db.users.create_index([("name", ASCENDING)])

    db.patients.create_index([("id", ASCENDING)], unique=True)
    db.patients.create_index([("doctor_id", ASCENDING), ("queue_number", ASCENDING)], unique=True)
    db.patients.create_index([("status", ASCENDING), ("doctor_id", ASCENDING)])
    db.patients.create_index([("created_at", DESCENDING)])

    db.appointments.create_index([("id", ASCENDING)], unique=True)
    db.appointments.create_index([("patient_id", ASCENDING), ("appointment_date", DESCENDING)])
    db.appointments.create_index([("doctor_id", ASCENDING), ("status", ASCENDING)])

    db.audit_logs.create_index([("id", ASCENDING)], unique=True)
    db.audit_logs.create_index([("timestamp", DESCENDING)])
    db.audit_logs.create_index([("patient_id", ASCENDING)])

    db.opd_tokens.create_index([("id", ASCENDING)], unique=True)
    db.opd_tokens.create_index([("doctor_id", ASCENDING), ("created_at", ASCENDING)])
    db.opd_tokens.create_index([("patient_id", ASCENDING)])
    db.opd_tokens.create_index([("status", ASCENDING), ("doctor_id", ASCENDING)])

    # Guard token uniqueness per doctor per day.
    db.opd_tokens.create_index(
        [("doctor_id", ASCENDING), ("token_day", ASCENDING), ("token_number", ASCENDING)],
        unique=True,
    )


def safe_insert_one(coll: Collection, doc: dict) -> dict:
    try:
        coll.insert_one(doc)
        return doc
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate key") from exc
