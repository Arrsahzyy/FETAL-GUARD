import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from db.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('patient', 'clinician', 'admin')", name="ck_users_role"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="patient")
    is_active = Column(Boolean, nullable=False, default=True)
    must_reset_password = Column(Boolean, nullable=False, default=False)
    auth_version = Column(Integer, nullable=False, default=0)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    patient_profile = relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")
    organization_memberships = relationship(
        "OrganizationMembership",
        foreign_keys="OrganizationMembership.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
