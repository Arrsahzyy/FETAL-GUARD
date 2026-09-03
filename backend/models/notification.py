import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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
    select,
)
from sqlalchemy.orm import relationship

from db.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="ck_notifications_risk_level"),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_review', 'resolved', 'false_positive', 'archived')",
            name="ck_notifications_status",
        ),
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_notifications_session_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_notifications_identity_scope"),
        Index("ix_notifications_session_rule_code", "session_id", "rule_code"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message = Column(String(500), nullable=False)
    # Identifies the rule that produced this alert so re-evaluation can suppress
    # duplicates by code rather than by matching translated message text.
    # Null for alerts created before rule-based production existed. Indexed
    # together with session_id in __table_args__, matching the dedup lookup.
    rule_code = Column(String(64), nullable=True)
    risk_level = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    acknowledgement_note = Column(String(500), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reviewed_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship(
        "MonitoringSession",
        back_populates="notifications",
        foreign_keys=[session_id, organization_id],
    )
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
    events = relationship(
        "AlertEvent",
        back_populates="notification",
        passive_deletes=True,
        foreign_keys="[AlertEvent.notification_id, AlertEvent.organization_id]",
    )

    @property
    def patient_id(self) -> str | None:
        return self.session.patient_id if self.session else None

    @property
    def patient_name(self) -> str | None:
        return self.session.patient.name if self.session and self.session.patient else None


@event.listens_for(Notification, "before_insert")
def populate_notification_organization(_mapper, connection, target: Notification) -> None:
    if target.organization_id:
        return
    from models.session import MonitoringSession

    organization_id = connection.execute(
        select(MonitoringSession.organization_id).where(MonitoringSession.id == target.session_id)
    ).scalar_one_or_none()
    if organization_id is None:
        raise ValueError("Notification requires a valid organization-scoped session")
    target.organization_id = organization_id
