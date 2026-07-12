import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from db.database import Base


class PatientClinicianAssignment(Base):
    __tablename__ = "patient_clinician_assignments"
    __table_args__ = (
        UniqueConstraint("patient_id", "clinician_user_id", name="uq_patient_clinician_assignment"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    clinician_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    assigned_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = relationship("Patient", back_populates="clinician_assignments")
    clinician = relationship("User", foreign_keys=[clinician_user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
