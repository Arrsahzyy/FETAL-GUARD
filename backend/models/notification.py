import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String
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
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    message = Column(String(500), nullable=False)
    risk_level = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    acknowledgement_note = Column(String(500), nullable=True)

    session = relationship("MonitoringSession", back_populates="notifications")
    acknowledged_by = relationship("User")

    @property
    def patient_id(self) -> str | None:
        return self.session.patient_id if self.session else None

    @property
    def patient_name(self) -> str | None:
        return self.session.patient.name if self.session and self.session.patient else None
