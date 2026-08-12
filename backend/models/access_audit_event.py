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
    Text,
)

from db.database import Base


class AccessAuditEvent(Base):
    """Append-only security and clinical-access audit event.

    Payloads must contain identifiers and operational metadata only. Raw
    telemetry, credentials, tokens, and complete patient records must never be
    copied into ``details``.
    """

    __tablename__ = "access_audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'denied', 'error')",
            name="ck_access_audit_events_outcome",
        ),
        ForeignKeyConstraint(
            ["actor_membership_id", "organization_id", "actor_user_id"],
            [
                "organization_memberships.id",
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_access_audit_events_actor_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_access_audit_events_patient_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_access_audit_events_org_created", "organization_id", "created_at"),
        Index("ix_access_audit_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_access_audit_events_patient_created", "patient_id", "created_at"),
        Index("ix_access_audit_events_request", "request_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=False,
    )
    actor_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_membership_id = Column(
        String(36),
        ForeignKey("organization_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    patient_id = Column(
        String(36),
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(100), nullable=False)
    resource_type = Column(String(80), nullable=False)
    resource_id = Column(String(80), nullable=True)
    purpose = Column(String(80), nullable=True)
    outcome = Column(String(32), nullable=False)
    request_id = Column(String(80), nullable=True)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
