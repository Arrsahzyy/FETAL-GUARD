import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import relationship

from db.database import Base


class DeviceAssignment(Base):
    """Append-only patient ownership interval for a physical device.

    ``Device.patient_id`` remains a denormalized pointer for fast registry
    rendering.  Authorization and session provenance must use this table.
    An assignment row may only transition once, from active to ended.
    """

    __tablename__ = "device_assignments"
    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_device_assignments_valid_interval",
        ),
        CheckConstraint(
            "(ends_at IS NULL AND version = 1) "
            "OR (ends_at IS NOT NULL AND version = 2)",
            name="ck_device_assignments_lifecycle_version",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_device_assignments_device_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_device_assignments_patient_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "patient_id",
            "device_id",
            "organization_id",
            name="uq_device_assignments_session_snapshot",
        ),
        Index(
            "uq_device_assignments_active_device",
            "device_id",
            unique=True,
            sqlite_where=text("ends_at IS NULL"),
            postgresql_where=text("ends_at IS NULL"),
        ),
        Index(
            "ix_device_assignments_org_patient_active",
            "organization_id",
            "patient_id",
            "ends_at",
        ),
        Index(
            "ix_device_assignments_device_started",
            "device_id",
            "starts_at",
        ),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=False, index=True)
    patient_id = Column(String(36), nullable=False, index=True)
    assigned_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ended_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    version = Column(Integer, nullable=False, default=1)
    starts_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    device = relationship(
        "Device",
        back_populates="assignments",
        foreign_keys=[device_id, organization_id],
        overlaps="patient",
    )
    patient = relationship(
        "Patient",
        back_populates="device_assignments",
        foreign_keys=[patient_id, organization_id],
        overlaps="device,assignments",
    )
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    ended_by = relationship("User", foreign_keys=[ended_by_user_id])
    sessions = relationship(
        "MonitoringSession",
        back_populates="device_assignment",
        foreign_keys="MonitoringSession.device_assignment_id",
    )

    @property
    def is_active(self) -> bool:
        return self.ends_at is None


@event.listens_for(DeviceAssignment, "before_update")
def prevent_device_assignment_rewrite(_mapper, _connection, target: DeviceAssignment) -> None:
    """Keep historical ownership immutable outside the one-way close transition."""

    state = inspect(target)
    changed = {
        attribute.key
        for attribute in state.attrs
        if attribute.history.has_changes()
    }
    allowed = {"ends_at", "ended_by_user_id", "version"}
    if not changed or not changed.issubset(allowed):
        raise ValueError("Device assignment history is immutable")

    previous_end_values = state.attrs.ends_at.history.deleted
    previous_version_values = state.attrs.version.history.deleted
    previous_end = previous_end_values[0] if previous_end_values else None
    previous_version = previous_version_values[0] if previous_version_values else 1
    if (
        previous_end is not None
        or target.ends_at is None
        or previous_version != 1
        or target.version != 2
    ):
        raise ValueError("Device assignment may only transition once from active to ended")


@event.listens_for(DeviceAssignment, "before_delete")
def prevent_device_assignment_delete(_mapper, _connection, _target: DeviceAssignment) -> None:
    raise ValueError("Device assignment history cannot be deleted")
