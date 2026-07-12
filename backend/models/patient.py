import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gestational_age_weeks = Column(Integer, nullable=False)
    medical_history = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="patient_profile")
    sessions = relationship("MonitoringSession", back_populates="patient", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="patient")
    clinician_assignments = relationship(
        "PatientClinicianAssignment",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
