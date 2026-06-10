from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import models

db = None


def utcnow() -> datetime:
    return datetime.utcnow()


def get_mongo_dependencies():
    from db_migrate import ensure_schema
    from mongo import db as mongo_db

    return mongo_db, ensure_schema


DEFAULT_SOURCE_CANDIDATES = (
    Path("backend/hospital.db"),
    Path("backend/hospital_recovered_blob.db"),
    Path("backend/hospital_recovered.db"),
    Path("hospital.db"),
    Path("hospital_recovered_blob.db"),
    Path("hospital_recovered.db"),
)


def resolve_source(source_arg: str | None) -> Path:
    if source_arg:
        path = Path(source_arg)
        if not path.exists():
            raise FileNotFoundError(f"SQLite source not found: {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"SQLite source is empty: {path}")
        return path

    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    raise FileNotFoundError("No non-empty SQLite database source was found.")


def parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def load_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    cur = conn.cursor()
    rows = cur.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    return [row_to_dict(row) for row in rows]


def migrate_users(rows: list[dict], migrated_at: datetime) -> list[dict]:
    docs = []
    for row in rows:
        docs.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "email": row["email"],
                "password": row["password"],
                "role": row["role"],
                "is_available": bool(row.get("is_available", 1)),
                "created_at": migrated_at,
            }
        )
    return docs


def migrate_patients(rows: list[dict]) -> list[dict]:
    docs = []
    for row in rows:
        docs.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "age": int(row["age"]),
                "gender": row["gender"],
                "contact_number": row.get("contact_number"),
                "symptoms": row["symptoms"],
                "priority": row["priority"],
                "status": row["status"],
                "queue_number": int(row["queue_number"]),
                "doctor_id": int(row["doctor_id"]),
                "user_id": None,
                "created_at": parse_datetime(row.get("created_at")),
                "started_serving_at": parse_datetime(row.get("started_serving_at")),
                "completed_at": parse_datetime(row.get("completed_at")),
            }
        )
    return docs


def migrate_appointments(rows: list[dict]) -> list[dict]:
    docs = []
    for row in rows:
        docs.append(
            {
                "id": int(row["id"]),
                "patient_id": int(row["patient_id"]),
                "doctor_id": int(row["doctor_id"]),
                "appointment_date": parse_datetime(row["appointment_date"]),
                "status": row["status"],
                "created_at": parse_datetime(row.get("created_at")),
                "started_at": parse_datetime(row.get("started_at")),
                "completed_at": parse_datetime(row.get("completed_at")),
            }
        )
    return docs


def migrate_audit_logs(rows: list[dict]) -> list[dict]:
    docs = []
    for row in rows:
        docs.append(
            {
                "id": int(row["id"]),
                "user_id": int(row["user_id"]),
                "action": row["action"],
                "patient_id": int(row["patient_id"]) if row.get("patient_id") is not None else None,
                "timestamp": parse_datetime(row["timestamp"]),
            }
        )
    return docs


def token_day(value: datetime | None) -> str:
    dt = value or utcnow()
    return dt.strftime("%Y-%m-%d")


def token_status_for_patient(patient: dict) -> str:
    status = patient.get("status")
    if status == models.StatusEnum.WAITING:
        if patient.get("started_serving_at") and not patient.get("completed_at"):
            return models.OpdTokenStatusEnum.IN_PROGRESS
        return models.OpdTokenStatusEnum.WAITING
    return models.OpdTokenStatusEnum.COMPLETED


def migrate_opd_tokens(patients: list[dict]) -> list[dict]:
    docs = []
    for patient in patients:
        created_at = patient.get("created_at") or utcnow()
        docs.append(
            {
                "id": int(patient["id"]),
                "token_number": int(patient.get("queue_number", 0)),
                "patient_id": int(patient["id"]),
                "doctor_id": int(patient["doctor_id"]),
                "status": token_status_for_patient(patient),
                "created_at": created_at,
                "called_at": patient.get("started_serving_at"),
                "completed_at": patient.get("completed_at"),
                "token_day": token_day(created_at),
            }
        )
    return docs


def replace_many(collection_name: str, docs: list[dict]) -> int:
    assert db is not None
    coll = db[collection_name]
    for doc in docs:
        coll.replace_one({"id": doc["id"]}, doc, upsert=True)
    return len(docs)


def reset_target() -> None:
    assert db is not None
    for name in ("users", "patients", "appointments", "audit_logs", "opd_tokens", "counters"):
        db[name].delete_many({})


def sync_counters(users: list[dict], patients: list[dict], appointments: list[dict], audit_logs: list[dict], opd_tokens: list[dict]) -> None:
    assert db is not None
    counter_values = {
        "users": max((doc["id"] for doc in users), default=0),
        "patients": max((doc["id"] for doc in patients), default=0),
        "appointments": max((doc["id"] for doc in appointments), default=0),
        "audit_logs": max((doc["id"] for doc in audit_logs), default=0),
        "opd_tokens": max((doc["id"] for doc in opd_tokens), default=0),
    }
    for counter_name, seq in counter_values.items():
        db.counters.replace_one({"_id": counter_name}, {"_id": counter_name, "seq": int(seq)}, upsert=True)


def main() -> None:
    global db
    parser = argparse.ArgumentParser(description="Migrate historical SQLite data into MongoDB.")
    parser.add_argument("--source", help="Path to the SQLite database file.")
    parser.add_argument(
        "--reset-target",
        action="store_true",
        help="Delete current Mongo collections before importing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and map SQLite rows without writing to MongoDB.",
    )
    args = parser.parse_args()

    source = resolve_source(args.source)
    conn = sqlite3.connect(source)
    conn.row_factory = sqlite3.Row

    users_rows = load_rows(conn, "users")
    patients_rows = load_rows(conn, "patients")
    appointments_rows = load_rows(conn, "appointments")
    audit_logs_rows = load_rows(conn, "audit_logs")

    migrated_at = utcnow()
    users = migrate_users(users_rows, migrated_at)
    patients = migrate_patients(patients_rows)
    appointments = migrate_appointments(appointments_rows)
    audit_logs = migrate_audit_logs(audit_logs_rows)
    opd_tokens = migrate_opd_tokens(patients)

    print(f"SQLite source: {source}")
    print(
        "Prepared documents:",
        {
            "users": len(users),
            "patients": len(patients),
            "appointments": len(appointments),
            "audit_logs": len(audit_logs),
            "opd_tokens": len(opd_tokens),
        },
    )

    if args.dry_run:
        print("Dry run complete. No MongoDB writes were performed.")
        return

    db, ensure_schema = get_mongo_dependencies()
    ensure_schema()
    if args.reset_target:
        reset_target()

    replace_many("users", users)
    replace_many("patients", patients)
    replace_many("appointments", appointments)
    replace_many("audit_logs", audit_logs)
    replace_many("opd_tokens", opd_tokens)
    sync_counters(users, patients, appointments, audit_logs, opd_tokens)
    ensure_schema()

    print("Migration complete.")


if __name__ == "__main__":
    main()
