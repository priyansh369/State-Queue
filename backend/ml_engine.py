from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import case
from sqlalchemy.orm import Session

import models


MIN_SERVICE_MINUTES = 4.0
MAX_SERVICE_MINUTES = 45.0
DEFAULT_SERVICE_MINUTES = 10.0
HISTORY_LIMIT = 40


@dataclass(frozen=True)
class QueueEstimate:
    patient: models.Patient
    eta_minutes: int


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _duration_minutes(appt: models.Appointment) -> float | None:
    # Prefer true durations.
    if appt.started_at and appt.completed_at and appt.completed_at > appt.started_at:
        return (appt.completed_at - appt.started_at).total_seconds() / 60.0

    # Fallbacks for older rows (hackathon-safe).
    if appt.completed_at and appt.appointment_date and appt.completed_at > appt.appointment_date:
        return (appt.completed_at - appt.appointment_date).total_seconds() / 60.0

    if appt.completed_at and appt.created_at and appt.completed_at > appt.created_at:
        return (appt.completed_at - appt.created_at).total_seconds() / 60.0

    return None


def _linear_regression_next(values: list[float]) -> float:
    """
    Lightweight linear regression without ML libs.
    Predicts the next value in the series.
    """
    n = len(values)
    if n < 3:
        # not enough signal, use mean
        return sum(values) / n

    xs = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n

    num = 0.0
    den = 0.0
    for x, y in zip(xs, values):
        dx = x - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x

    pred = slope * n + intercept
    return pred


def _ewma(values: Iterable[float], alpha: float) -> float:
    it = iter(values)
    try:
        s = float(next(it))
    except StopIteration:
        return DEFAULT_SERVICE_MINUTES
    for v in it:
        s = alpha * float(v) + (1 - alpha) * s
    return s


def estimate_next_service_minutes(db: Session, doctor_id: int) -> float:
    """
    "ML regression engine":
    - Extract recent completed appointment durations for the doctor
    - Predict next service duration using a blend of Linear Regression + EWMA
    """
    appts = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status == models.StatusEnum.COMPLETED,
            models.Appointment.completed_at.isnot(None),
        )
        .order_by(models.Appointment.completed_at.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )

    durations = []
    for a in reversed(appts):  # oldest -> newest
        d = _duration_minutes(a)
        if d and d > 0:
            durations.append(float(d))

    if len(durations) < 3:
        return DEFAULT_SERVICE_MINUTES

    # Regression captures trend (speeding up/slowing down), EWMA captures recency.
    reg_pred = _linear_regression_next(durations)
    ewma_pred = _ewma(durations[-15:], alpha=0.35)

    # Blend: favor EWMA slightly for stability.
    pred = 0.4 * reg_pred + 0.6 * ewma_pred
    pred = _clamp(pred, MIN_SERVICE_MINUTES, MAX_SERVICE_MINUTES)
    return pred


def doctor_queue(db: Session, doctor_id: int) -> list[models.Patient]:
    priority_rank = case(
        (models.Patient.priority == models.PriorityEnum.EMERGENCY, 0),
        else_=1,
    )
    return (
        db.query(models.Patient)
        .filter(
            models.Patient.doctor_id == doctor_id,
            models.Patient.status == models.StatusEnum.WAITING,
        )
        .order_by(priority_rank.asc(), models.Patient.created_at.asc())
        .all()
    )


def compute_queue_estimates(db: Session, doctor_id: int) -> list[QueueEstimate]:
    """
    Returns ordered queue with ETA for each patient based on predicted throughput.

    ETA for each patient = remaining time of now-serving + sum(predicted times of patients ahead).
    """
    q = doctor_queue(db, doctor_id)
    if not q:
        return []

    estimates: list[QueueEstimate] = []
    for idx, p in enumerate(q):
        # Queue ETA baseline: each position adds 10 minutes.
        # Emergency gets reduced ETA while still remaining non-negative.
        eta = idx * 10
        if p.priority == models.PriorityEnum.EMERGENCY and eta > 0:
            eta = max(0, eta - 5)
        estimates.append(QueueEstimate(patient=p, eta_minutes=int(eta)))
    return estimates


def compute_patient_eta_minutes(db: Session, patient: models.Patient) -> int:
    if patient.status != models.StatusEnum.WAITING:
        return 0
    estimates = compute_queue_estimates(db, patient.doctor_id)
    for e in estimates:
        if e.patient.id == patient.id:
            return e.eta_minutes
    # not found (doctor mismatch or already removed)
    return 0

