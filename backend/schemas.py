from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)
    role: Literal["patient", "doctor", "receptionist"]

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(ch.isupper() for ch in value)
        has_lower = any(ch.islower() for ch in value)
        has_digit = any(ch.isdigit() for ch in value)
        has_special = any(not ch.isalnum() for ch in value)
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "Password must include uppercase, lowercase, number, and special character"
            )
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: int
    role: str
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    name: str


class PatientBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=130)
    gender: Literal["male", "female", "other"]
    symptoms: str = Field(min_length=2, max_length=800)
    priority: Literal["normal", "emergency"] = "normal"
    doctor_id: int = Field(gt=0)

    @field_validator("name", "symptoms")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned


class PatientCreate(PatientBase):
    pass


class PatientOut(PatientBase):
    id: int
    status: str
    queue_number: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_date: datetime


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentOut(AppointmentBase):
    id: int
    status: str
    model_config = ConfigDict(from_attributes=True)


class QueuePatient(BaseModel):
    id: int
    name: str
    priority: str
    status: str
    queue_number: int
    symptoms: str
    estimated_wait_minutes: int
    waiting_minutes: int = 0
    escalation_required: bool = False
    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    total_patients: int
    waiting: int
    emergency: int
    completed: int
    total_patients_today: int
    average_wait_minutes: int
    emergency_percentage: float
    completion_rate: float
    overdue_emergencies: int = 0


class ReceptionRegisterPatient(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=130)
    gender: Literal["male", "female", "other"]
    symptoms: str = Field(min_length=2, max_length=800)
    priority: Literal["normal", "emergency"] = "normal"
    doctor_id: int = Field(gt=0)

    @field_validator("name", "symptoms")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned


class UpdatePriority(BaseModel):
    priority: Literal["normal", "emergency"]


class DoctorOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class LiveQueueStatus(BaseModel):
    patient: QueuePatient
    current_token_id: Optional[int]
    current_token_queue_number: Optional[int]
    waiting_count: int
    doctor_average_service_minutes: int


class AuditLogOut(BaseModel):
    id: int
    user_id: int
    action: str
    patient_id: Optional[int]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
