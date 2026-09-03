import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String

from db.database import Base


class DeviceClaimAttempt(Base):
    """Failed device-claim attempts, used to rate limit claim-code guessing.

    Kept separate from AuthLoginAttempt: the two have different scopes (a device
    UID and a caller, rather than an email and a caller) and mixing them would
    let claim failures lock a patient out of logging in, and pollute login
    security metrics with hardware pairing noise.

    Rows are pruned once they fall outside the rate-limit window; this is a
    throttling ledger, not an audit trail. Real audit lives in access_audit_events.
    """

    __tablename__ = "device_claim_attempts"
    __table_args__ = (
        Index("ix_device_claim_attempts_device_created", "device_uid", "created_at"),
        Index("ix_device_claim_attempts_client_created", "client_key", "created_at"),
    )

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # Stored as submitted-and-normalized, not as a foreign key: a guess may name a
    # device UID that does not exist, and those attempts must still be counted.
    device_uid = Column(String(80), nullable=False)
    client_key = Column(String(128), nullable=False)
    patient_id = Column(String(36), nullable=True, index=True)
    was_successful = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
