import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from db.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(80), nullable=False, index=True)
    target_user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    target_email = Column(String(255), nullable=True, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
