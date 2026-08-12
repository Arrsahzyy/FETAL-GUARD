import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    event,
)

from db.database import Base


REALTIME_EVENT_TYPES = (
    "ai.analysis.updated",
    "alert.created",
    "alert.updated",
    "care_assignment.updated",
    "device.updated",
    "session.completed",
    "session.started",
    "telemetry.updated",
)


class RealtimeEventCursor(Base):
    """Per-facility sequence state used to avoid cross-tenant cursor leakage."""

    __tablename__ = "realtime_event_cursors"
    __table_args__ = (
        CheckConstraint("last_cursor >= 0", name="ck_realtime_event_cursors_nonnegative"),
    )

    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_cursor = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RealtimeEvent(Base):
    """Append-only, minimal event log consumed by authorized polling clients.

    Raw sensor samples, patient demographics, alert messages, device UIDs, and
    credentials do not belong in ``payload``. Producers must use the strict
    allow-list in :mod:`core.realtime`.
    """

    __tablename__ = "realtime_events"
    __table_args__ = (
        CheckConstraint("cursor > 0", name="ck_realtime_events_positive_cursor"),
        CheckConstraint(
            "event_type IN ("
            "'ai.analysis.updated', 'alert.created', 'alert.updated', 'care_assignment.updated', "
            "'device.updated', 'session.completed', 'session.started', "
            "'telemetry.updated')",
            name="ck_realtime_events_type",
        ),
        CheckConstraint(
            "resource_type IN ('ai_analysis', 'alert', 'care_assignment', 'device', 'session')",
            name="ck_realtime_events_resource_type",
        ),
        CheckConstraint(
            "expires_at > occurred_at",
            name="ck_realtime_events_retention_window",
        ),
        CheckConstraint(
            "length(CAST(payload AS TEXT)) <= 4096",
            name="ck_realtime_events_payload_size",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_realtime_events_patient_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "cursor",
            name="uq_realtime_events_org_cursor",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_realtime_events_org_idempotency",
        ),
        Index(
            "ix_realtime_events_org_cursor",
            "organization_id",
            "cursor",
        ),
        Index(
            "ix_realtime_events_patient_cursor",
            "patient_id",
            "cursor",
        ),
        Index(
            "ix_realtime_events_expiry_cursor",
            "expires_at",
            "cursor",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    patient_id = Column(String(36), nullable=False)
    cursor = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    idempotency_key = Column(String(180), nullable=False)
    event_type = Column(String(48), nullable=False)
    resource_type = Column(String(32), nullable=False)
    resource_id = Column(String(80), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


@event.listens_for(RealtimeEvent, "before_update")
def prevent_realtime_event_update(_mapper, _connection, _target: RealtimeEvent) -> None:
    raise ValueError("Realtime event history is append-only")


@event.listens_for(RealtimeEvent, "before_delete")
def prevent_realtime_event_delete(_mapper, _connection, _target: RealtimeEvent) -> None:
    raise ValueError("Realtime event history cannot be deleted through the ORM")
