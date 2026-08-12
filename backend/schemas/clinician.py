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
    patient_code: str
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


class ClinicianStatisticsResponse(BaseModel):
    total_patients: int
    active_monitoring: int
    high_priority_patients: int
    open_alerts: int


class AlertAcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)


class AlertStatusUpdateRequest(BaseModel):
    status: NotificationStatus
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)


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
    version: int = 1
    updated_at: datetime
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    resolved_by_user_id: str | None = None
    resolved_at: datetime | None = None
    
    # Enrichment fields for clinician view
    patient_id: str | None = None
    patient_name: str | None = None

    model_config = {"from_attributes": True}
