import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class SensorDataChunk(Base):
    __tablename__ = "session_data_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_session_data_chunks_session_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_session_data_chunks_device_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_session_data_chunks_identity_scope"),
        UniqueConstraint("session_id", "ingestion_id", name="uq_session_data_chunks_ingestion_id"),
        UniqueConstraint(
            "device_id",
            "boot_id",
            "sequence_number",
            name="uq_session_data_chunks_device_sequence",
        ),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), index=True, nullable=False)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    device_id = Column(
        String(36),
        ForeignKey("devices.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    ingestion_id = Column(String(80), nullable=False)
    boot_id = Column(String(80), nullable=True)
    sequence_number = Column(Integer, nullable=True)
    schema_version = Column(Integer, nullable=False, default=1)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    payload = Column(JSON, nullable=False)

    session = relationship(
        "MonitoringSession",
        back_populates="data_chunks",
        foreign_keys=[session_id, organization_id],
        overlaps="device",
    )
