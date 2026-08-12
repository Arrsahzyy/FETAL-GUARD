import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from db.database import Base


class OrganizationMembership(Base):
    """Time-bounded staff membership within one hospital/facility."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('clinician', 'supervisor', 'org_admin', 'auditor')",
            name="ck_organization_memberships_role",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= created_at",
            name="ck_organization_memberships_valid_interval",
        ),
        Index(
            "uq_organization_memberships_active_user_org",
            "user_id",
            "organization_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_organization_memberships_org_role_active",
            "organization_id",
            "role",
            "ended_at",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "user_id",
            name="uq_organization_memberships_identity_scope",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)
    granted_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)
    ended_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", foreign_keys=[user_id], back_populates="organization_memberships")
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])
    ended_by = relationship("User", foreign_keys=[ended_by_user_id])

    @property
    def is_active(self) -> bool:
        return self.ended_at is None
