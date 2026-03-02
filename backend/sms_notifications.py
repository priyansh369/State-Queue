from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import Iterable

import requests


_recent_soon_notifications: dict[int, datetime] = {}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _twilio_config() -> tuple[str, str, str] | None:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not sid or not token or not from_number:
        return None
    return sid, token, from_number


def _sanitize_phone(number: str | None) -> str | None:
    if not number:
        return None
    cleaned = number.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        core = cleaned[1:]
    else:
        core = cleaned
    if not core.isdigit() or len(core) < 10 or len(core) > 15:
        return None
    return f"+{core}" if not cleaned.startswith("+") else cleaned


def send_sms(to_number: str | None, message: str) -> None:
    """
    Sends SMS through Twilio. Safe no-op if SMS is disabled or config is missing.
    """
    if not _env_flag("SMS_ENABLED", default=False):
        return
    cfg = _twilio_config()
    to_phone = _sanitize_phone(to_number)
    if not cfg or not to_phone or not message:
        return

    sid, token, from_number = cfg
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        response = requests.post(
            url,
            auth=(sid, token),
            data={"From": from_number, "To": to_phone, "Body": message},
            timeout=10,
        )
        if response.status_code >= 400:
            print(f"[sms] Twilio error {response.status_code}: {response.text[:250]}")
    except Exception as exc:
        print(f"[sms] send failed: {exc}")


def notify_new_appointment_sms(
    to_number: str | None,
    *,
    queue_number: int,
    eta_minutes: int,
    doctor_name: str | None = None,
) -> None:
    doctor_label = f" with Dr. {doctor_name}" if doctor_name else ""
    body = (
        f"Appointment confirmed{doctor_label}. "
        f"Queue #{queue_number}. Estimated wait: {eta_minutes} minutes."
    )
    send_sms(to_number, body)


def notify_status_updated_sms(
    to_number: str | None,
    *,
    status: str,
    doctor_name: str | None = None,
) -> None:
    doctor_label = f" by Dr. {doctor_name}" if doctor_name else ""
    status_key = (status or "").upper()
    if status_key == "STARTED":
        body = f"Your consultation is starting now{doctor_label}. Please proceed."
    elif status_key == "COMPLETED":
        body = f"Your consultation has been completed{doctor_label}. Thank you."
    else:
        body = f"Your appointment status changed to {status_key or 'UPDATED'}{doctor_label}."
    send_sms(to_number, body)


def _should_send_soon(patient_id: int) -> bool:
    cooldown_min = int(os.getenv("SMS_SOON_COOLDOWN_MINUTES", "15"))
    now = datetime.utcnow()
    prev = _recent_soon_notifications.get(patient_id)
    if prev and now - prev < timedelta(minutes=cooldown_min):
        return False
    _recent_soon_notifications[patient_id] = now
    return True


def notify_now_serving_soon_sms(
    queue_items: Iterable[tuple[int, str | None, int]],
    *,
    doctor_name: str | None = None,
) -> None:
    """
    queue_items: iterable of (patient_id, contact_number, eta_minutes)
    """
    threshold = int(os.getenv("SMS_SOON_THRESHOLD_MINUTES", "10"))
    doctor_label = f" for Dr. {doctor_name}" if doctor_name else ""
    for patient_id, contact_number, eta_minutes in queue_items:
        if eta_minutes <= 0 or eta_minutes > threshold:
            continue
        if not _should_send_soon(patient_id):
            continue
        body = (
            f"You're coming up soon{doctor_label}. "
            f"Please be ready. Estimated wait: {eta_minutes} minutes."
        )
        send_sms(contact_number, body)
