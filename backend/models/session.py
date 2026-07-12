import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from db.database import Base


class MonitoringSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'error')", name="ck_sessions_status"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    start_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="active")

    patient = relationship("Patient", back_populates="sessions")
    data_chunks = relationship("SensorDataChunk", back_populates="session", cascade="all, delete-orphan")
    sensor_summary = relationship(
        "SessionSensorSummary",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    notifications = relationship("Notification", back_populates="session", cascade="all, delete-orphan")
