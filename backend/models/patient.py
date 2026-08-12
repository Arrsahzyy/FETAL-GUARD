import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base
from core.identifiers import generate_patient_code


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_patients_identity_scope"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    patient_code = Column(String(15), unique=True, index=True, nullable=False, default=generate_patient_code)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gestational_age_weeks = Column(Integer, nullable=False)
    medical_history = Column(Text, nullable=True)
    national_id = Column(String(16), nullable=True, unique=True, index=True)
    birth_date = Column(Date, nullable=True)
    blood_type = Column(String(3), nullable=True)
    address = Column(Text, nullable=True)
    phone_number = Column(String(24), nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(24), nullable=True)
    last_menstrual_period = Column(Date, nullable=True)
    estimated_due_date = Column(Date, nullable=True)
    gravida = Column(Integer, nullable=True)
    para = Column(Integer, nullable=True)
    abortus = Column(Integer, nullable=True)
    height_cm = Column(Float, nullable=True)
    pre_pregnancy_weight_kg = Column(Float, nullable=True)
    current_weight_kg = Column(Float, nullable=True)
    previous_delivery_type = Column(String(32), nullable=True)
    previous_pregnancy_complications = Column(Text, nullable=True)
    has_hypertension = Column(Boolean, nullable=False, default=False)
    has_diabetes = Column(Boolean, nullable=False, default=False)
    has_heart_condition = Column(Boolean, nullable=False, default=False)
    has_asthma = Column(Boolean, nullable=False, default=False)
    has_allergies = Column(Boolean, nullable=False, default=False)
    allergy_details = Column(Text, nullable=True)
    current_medications = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="patient_profile")
    organization = relationship("Organization", back_populates="patients")
    sessions = relationship(
        "MonitoringSession",
        back_populates="patient",
        cascade="all, delete-orphan",
        foreign_keys="[MonitoringSession.patient_id, MonitoringSession.organization_id]",
        overlaps="device,device_assignment",
    )
    devices = relationship(
        "Device",
        back_populates="patient",
        foreign_keys="Device.patient_id",
        overlaps="assignments,device_assignments",
    )
    device_assignments = relationship(
        "DeviceAssignment",
        back_populates="patient",
        order_by="DeviceAssignment.starts_at",
        foreign_keys="[DeviceAssignment.patient_id, DeviceAssignment.organization_id]",
        overlaps="device,assignments",
    )
    clinician_assignments = relationship(
        "PatientClinicianAssignment",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
