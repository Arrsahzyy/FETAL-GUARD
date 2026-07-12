import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String

from db.database import Base


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), index=True, nullable=False)
    client_key = Column(String(64), index=True, nullable=False)
    was_successful = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
