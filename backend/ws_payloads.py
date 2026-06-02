from __future__ import annotations

import models


def patient_payload(patient) -> dict:
    get = patient.get if isinstance(patient, dict) else lambda k, d=None: getattr(patient, k, d)
    priority = get("priority")
    created_at = get("created_at")
    return {
        "id": get("id"),
        "name": get("name"),
        "age": get("age"),
        "gender": get("gender"),
        "contact_number": get("contact_number"),
        "symptoms": get("symptoms"),
        "priority": priority,
        "priority_rank": 0 if priority == models.PriorityEnum.EMERGENCY else 1,
        "status": get("status"),
        "queue_number": get("queue_number"),
        "doctor_id": get("doctor_id"),
        "created_at": created_at.isoformat() if created_at else None,
    }
