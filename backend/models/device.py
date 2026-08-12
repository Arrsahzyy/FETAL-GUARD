import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('registered', 'active', 'maintenance', 'retired', 'lost')",
            name="ck_devices_status",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_devices_patient_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_devices_identity_scope"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_uid = Column(String(80), unique=True, index=True, nullable=False)
    patient_id = Column(
        String(36),
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_name = Column(String(120), nullable=False, default="FETAL-GUARD Belt")
    hardware_revision = Column(String(80), nullable=True)
    firmware_version = Column(String(80), nullable=True)
    status = Column(String(32), nullable=False, default="registered", index=True)
    registered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship(
        "Patient",
        back_populates="devices",
        foreign_keys=[patient_id],
        overlaps="assignments,device_assignments",
    )
    assignments = relationship(
        "DeviceAssignment",
        back_populates="device",
        order_by="DeviceAssignment.starts_at",
        foreign_keys="[DeviceAssignment.device_id, DeviceAssignment.organization_id]",
        overlaps="patient,device_assignments",
    )
    sessions = relationship(
        "MonitoringSession",
        back_populates="device",
        foreign_keys="[MonitoringSession.device_id, MonitoringSession.organization_id]",
        overlaps="patient,sessions,device_assignment",
    )
    sensor_summaries = relationship(
        "SessionSensorSummary",
        back_populates="device",
        foreign_keys="[SessionSensorSummary.device_id, SessionSensorSummary.organization_id]",
        overlaps="session,sensor_summary",
    )
