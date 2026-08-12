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
    text,
)
from sqlalchemy.orm import relationship

from db.database import Base


class PatientClinicianAssignment(Base):
    __tablename__ = "patient_clinician_assignments"
    __table_args__ = (
        CheckConstraint(
            "care_role IN ('primary', 'supporting')",
            name="ck_patient_clinician_assignments_care_role",
        ),
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_patient_clinician_assignments_valid_interval",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_patient_clinician_assignments_version",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_patient_assignments_patient_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["clinician_membership_id", "organization_id", "clinician_user_id"],
            [
                "organization_memberships.id",
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_patient_assignments_clinician_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_patient_assignments_active_clinician",
            "patient_id",
            "clinician_user_id",
            unique=True,
            sqlite_where=text("ends_at IS NULL"),
            postgresql_where=text("ends_at IS NULL"),
        ),
        Index(
            "uq_patient_assignments_active_primary",
            "patient_id",
            unique=True,
            sqlite_where=text("ends_at IS NULL AND care_role = 'primary'"),
            postgresql_where=text("ends_at IS NULL AND care_role = 'primary'"),
        ),
        Index(
            "ix_patient_assignments_clinician_active_patient",
            "clinician_user_id",
            "ends_at",
            "patient_id",
        ),
        Index(
            "ix_patient_assignments_org_active_patient",
            "organization_id",
            "ends_at",
            "patient_id",
        ),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), index=True, nullable=False)
    patient_id = Column(String(36), index=True, nullable=False)
    clinician_membership_id = Column(String(36), index=True, nullable=False)
    clinician_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    assigned_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ended_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    care_role = Column(String(32), nullable=False, default="primary")
    version = Column(Integer, nullable=False, default=1)
    starts_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = relationship("Patient", back_populates="clinician_assignments")
    clinician = relationship("User", foreign_keys=[clinician_user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    ended_by = relationship("User", foreign_keys=[ended_by_user_id])
    clinician_membership = relationship("OrganizationMembership", foreign_keys=[clinician_membership_id])

    @property
    def is_active(self) -> bool:
        return self.ends_at is None
