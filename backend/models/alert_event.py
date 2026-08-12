import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class AlertEvent(Base):
    """Immutable history for a clinician alert lifecycle transition."""

    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("notification_id", "version", name="uq_alert_events_notification_version"),
        ForeignKeyConstraint(
            ["notification_id", "organization_id"],
            ["notifications.id", "notifications.organization_id"],
            name="fk_alert_events_notification_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_alert_events_notification_created", "notification_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id = Column(
        String(36),
        ForeignKey("notifications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    note = Column(Text, nullable=True)
    version = Column(Integer, nullable=False)
    request_id = Column(String(80), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    notification = relationship(
        "Notification",
        back_populates="events",
        foreign_keys=[notification_id, organization_id],
    )
