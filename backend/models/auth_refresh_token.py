import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String

from db.database import Base


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    client_key = Column(String(64), nullable=True, index=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    replaced_by_token_id = Column(
        String(36),
        ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
