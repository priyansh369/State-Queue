from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _existing_columns(engine: Engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # row format: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}


def _add_column(engine: Engine, table: str, column: str, ddl_type: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def ensure_schema(engine: Engine) -> None:
    """
    Lightweight SQLite "migration" for hackathon velocity.

    SQLAlchemy's create_all() won't add missing columns on existing tables,
    so we do a best-effort ALTER TABLE ADD COLUMN for the few fields we need.
    """
    # patients: started_serving_at, completed_at
    try:
        patient_cols = _existing_columns(engine, "patients")
        if "started_serving_at" not in patient_cols:
            _add_column(engine, "patients", "started_serving_at", "DATETIME")
        if "completed_at" not in patient_cols:
            _add_column(engine, "patients", "completed_at", "DATETIME")
    except Exception:
        # table might not exist yet; create_all will handle it
        pass

    # appointments: created_at, started_at, completed_at
    try:
        appt_cols = _existing_columns(engine, "appointments")
        if "created_at" not in appt_cols:
            _add_column(engine, "appointments", "created_at", "DATETIME")
        if "started_at" not in appt_cols:
            _add_column(engine, "appointments", "started_at", "DATETIME")
        if "completed_at" not in appt_cols:
            _add_column(engine, "appointments", "completed_at", "DATETIME")
    except Exception:
        pass

    # audit_logs table + indexes
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    patient_id INTEGER,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(patient_id) REFERENCES patients(id)
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_audit_patient_id ON audit_logs(patient_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
        )

    # enforce per-doctor queue uniqueness
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_doctor_queue "
                    "ON patients(doctor_id, queue_number)"
                )
            )
    except Exception:
        # Existing duplicate rows can block adding this index.
        pass

