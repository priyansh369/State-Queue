from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: int
    role: str

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    name: str


class PatientBase(BaseModel):
    name: str
    age: int
    gender: str
    symptoms: str
    priority: str = "normal"
    doctor_id: int


class PatientCreate(PatientBase):
    pass


class PatientOut(PatientBase):
    id: int
    status: str
    queue_number: int
    created_at: datetime

    class Config:
        orm_mode = True


class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_date: datetime


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentOut(AppointmentBase):
    id: int
    status: str

    class Config:
        orm_mode = True


class QueuePatient(BaseModel):
    id: int
    name: str
    priority: str
    status: str
    queue_number: int
    symptoms: str
    estimated_wait_minutes: int

    class Config:
        orm_mode = True


class DashboardStats(BaseModel):
    total_patients: int
    waiting: int
    emergency: int
    completed: int


class ReceptionRegisterPatient(BaseModel):
    name: str
    age: int
    gender: str
    symptoms: str
    priority: str = "normal"
    doctor_id: int


class UpdatePriority(BaseModel):
    priority: str

