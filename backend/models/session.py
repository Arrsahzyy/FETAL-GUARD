import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from db.database import Base


class MonitoringSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'error')", name="ck_sessions_status"),
        CheckConstraint(
            "(device_id IS NULL AND device_assignment_id IS NULL) OR "
            "(device_id IS NOT NULL AND device_assignment_id IS NOT NULL)",
            name="ck_sessions_device_assignment_binding",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_sessions_patient_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_sessions_device_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["device_assignment_id", "patient_id", "device_id", "organization_id"],
            [
                "device_assignments.id",
                "device_assignments.patient_id",
                "device_assignments.device_id",
                "device_assignments.organization_id",
            ],
            name="fk_sessions_device_assignment_snapshot",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_sessions_identity_scope"),
        Index(
            "uq_sessions_active_patient",
            "patient_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_sessions_client_session_id",
            "patient_id",
            "client_session_id",
            unique=True,
            sqlite_where=text("client_session_id IS NOT NULL"),
            postgresql_where=text("client_session_id IS NOT NULL"),
        ),
        Index(
            "uq_sessions_active_device",
            "device_id",
            unique=True,
            sqlite_where=text("status = 'active' AND device_id IS NOT NULL"),
            postgresql_where=text("status = 'active' AND device_id IS NOT NULL"),
        ),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), index=True, nullable=False)
    patient_id = Column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    device_id = Column(
        String(36),
        ForeignKey("devices.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    device_assignment_id = Column(String(36), index=True, nullable=True)
    client_session_id = Column(String(80), nullable=True)
    start_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    last_data_at = Column(DateTime(timezone=True), nullable=True)
    last_captured_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="active")

    patient = relationship(
        "Patient",
        back_populates="sessions",
        foreign_keys=[patient_id, organization_id],
        overlaps="device,device_assignment",
    )
    device = relationship(
        "Device",
        back_populates="sessions",
        foreign_keys=[device_id, organization_id],
        overlaps="patient,sessions,device_assignment",
    )
    device_assignment = relationship(
        "DeviceAssignment",
        back_populates="sessions",
        foreign_keys=[device_assignment_id],
        overlaps="device,patient",
    )
    data_chunks = relationship(
        "SensorDataChunk",
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="[SensorDataChunk.session_id, SensorDataChunk.organization_id]",
        overlaps="device",
    )
    sensor_summary = relationship(
        "SessionSensorSummary",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[SessionSensorSummary.session_id, SessionSensorSummary.organization_id]",
        overlaps="device,sensor_summaries",
    )
    notifications = relationship(
        "Notification",
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="[Notification.session_id, Notification.organization_id]",
    )
