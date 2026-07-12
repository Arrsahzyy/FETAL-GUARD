import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from db.database import Base


class SessionSensorSummary(Base):
    __tablename__ = "session_sensor_summaries"
    __table_args__ = (
        CheckConstraint(
            "contraction_indicator IN ('unknown', 'none', 'mild', 'regular', 'strong')",
            name="ck_session_sensor_summaries_contraction_indicator",
        ),
        CheckConstraint(
            "signal_quality_index IS NULL OR (signal_quality_index >= 0 AND signal_quality_index <= 1)",
            name="ck_session_sensor_summaries_signal_quality_index",
        ),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    fhr_estimate_bpm = Column(Integer, nullable=True)
    maternal_hr_bpm = Column(Integer, nullable=True)
    signal_quality_index = Column(Float, nullable=True)
    contraction_indicator = Column(String(32), nullable=False, default="unknown")
    sample_count = Column(Integer, nullable=False, default=0)
    source = Column(String(32), nullable=False, default="manual")
    is_simulated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("MonitoringSession", back_populates="sensor_summary")
    device = relationship("Device", back_populates="sensor_summaries")
