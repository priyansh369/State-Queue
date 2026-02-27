from __future__ import annotations

from . import models


def patient_payload(patient: models.Patient) -> dict:
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "symptoms": patient.symptoms,
        "priority": patient.priority,
        "status": patient.status,
        "queue_number": patient.queue_number,
        "doctor_id": patient.doctor_id,
        "created_at": patient.created_at.isoformat() if patient.created_at else None,
    }
