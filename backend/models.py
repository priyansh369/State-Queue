from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRoleEnum(str):
    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"


class PriorityEnum(str):
    NORMAL = "normal"
    EMERGENCY = "emergency"


class StatusEnum(str):
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)

    doctor_patients = relationship("Patient", back_populates="doctor")
    doctor_appointments = relationship("Appointment", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("doctor_id", "queue_number", name="uq_patient_doctor_queue"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    symptoms = Column(String, nullable=False)
    priority = Column(String, nullable=False, default=PriorityEnum.NORMAL)
    status = Column(String, nullable=False, default=StatusEnum.WAITING)
    queue_number = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_serving_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    doctor = relationship("User", back_populates="doctor_patients")
    appointments = relationship("Appointment", back_populates="patient")
    audit_logs = relationship("AuditLog", back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appointment_date = Column(DateTime, nullable=False)  # legacy "booked at"
    status = Column(String, nullable=False, default=StatusEnum.WAITING)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("User", back_populates="doctor_appointments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    patient = relationship("Patient", back_populates="audit_logs")

