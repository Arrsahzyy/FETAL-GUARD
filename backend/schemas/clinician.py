from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from schemas.session import SessionResponse


class NotificationRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class NotificationStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    in_review = "in_review"
    resolved = "resolved"
    false_positive = "false_positive"
    archived = "archived"


class PatientSummaryResponse(BaseModel):
    id: str
    user_id: str
    name: str
    age: int
    gestational_age_weeks: int
    latest_session: SessionResponse | None = None
    active_sessions: list[SessionResponse] = Field(default_factory=list)


class PatientListResponse(BaseModel):
    items: list[PatientSummaryResponse]
    total: int
    limit: int
    offset: int


class AlertAcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AlertStatusUpdateRequest(BaseModel):
    status: NotificationStatus
    note: str | None = Field(default=None, max_length=500)


class NotificationResponse(BaseModel):
    id: str
    session_id: str
    message: str
    risk_level: NotificationRiskLevel
    status: NotificationStatus = NotificationStatus.open
    created_at: datetime
    is_acknowledged: bool
    acknowledged_at: datetime | None = None
    acknowledged_by_user_id: str | None = None
    acknowledgement_note: str | None = None
    
    # Enrichment fields for clinician view
    patient_id: str | None = None
    patient_name: str | None = None

    model_config = {"from_attributes": True}
