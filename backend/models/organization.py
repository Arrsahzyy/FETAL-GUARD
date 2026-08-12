import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from db.database import Base


class Organization(Base):
    """Hospital/facility security boundary.

    The opaque ``id`` is used for authorization and foreign keys. ``slug`` is
    an administrative identifier only and must never be trusted as proof of
    membership.
    """

    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(80), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    memberships = relationship("OrganizationMembership", back_populates="organization")
    patients = relationship("Patient", back_populates="organization")
