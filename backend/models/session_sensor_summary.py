import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
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
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_session_sensor_summaries_session_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_session_sensor_summaries_device_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_session_sensor_summaries_identity_scope"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), index=True, nullable=False)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    device_id = Column(
        String(36),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fhr_estimate_bpm = Column(Integer, nullable=True)
    maternal_hr_bpm = Column(Integer, nullable=True)
    signal_quality_index = Column(Float, nullable=True)
    contraction_indicator = Column(String(32), nullable=False, default="unknown")
    sample_count = Column(Integer, nullable=False, default=0)
    source = Column(String(32), nullable=False, default="manual")
    is_simulated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship(
        "MonitoringSession",
        back_populates="sensor_summary",
        foreign_keys=[session_id, organization_id],
        overlaps="device,sensor_summaries",
    )
    device = relationship(
        "Device",
        back_populates="sensor_summaries",
        foreign_keys=[device_id, organization_id],
        overlaps="session,sensor_summary",
    )
