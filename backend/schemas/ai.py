from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SafeAIClassification(str, Enum):
    within_expected_range = "Dalam Batas Normal"
    watchful = "Waspada"
    observation_needed = "Perlu Observasi"


class AIPredictRequest(BaseModel):
    sensor_data_chunk_id: str = Field(min_length=1)


class AIPredictResponse(BaseModel):
    sensor_data_chunk_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    classification: SafeAIClassification
    message: str
    is_stub: bool = True


class AIQualityStatus(str, Enum):
    usable = "usable"
    limited = "limited"
    unusable = "unusable"


class AIScreeningStatus(str, Enum):
    routine_monitoring = "routine_monitoring"
    needs_observation = "needs_observation"
    review_with_clinician = "review_with_clinician"
    insufficient_signal = "insufficient_signal"


class AIResultVisibility(str, Enum):
    shadow = "shadow"
    clinician = "clinician"
    patient = "patient"


class AIReviewDecision(str, Enum):
    confirmed = "confirmed"
    dismissed = "dismissed"
    needs_followup = "needs_followup"


class AIAnalysisReviewRequest(BaseModel):
    decision: AIReviewDecision
    note: str | None = Field(default=None, max_length=2000)
    expected_version: int = Field(default=0, ge=0)


class AIAnalysisReviewResponse(BaseModel):
    id: str
    analysis_result_id: str
    reviewer_user_id: str
    decision: AIReviewDecision
    note: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAnalysisResultResponse(BaseModel):
    id: str
    patient_id: str
    session_id: str
    device_id: str | None = None
    window_started_at: datetime
    window_ended_at: datetime
    quality_status: AIQualityStatus
    quality_score: float = Field(ge=0, le=1)
    fhr_bpm: float | None = None
    maternal_hr_bpm: float | None = None
    contraction_probability: float | None = Field(default=None, ge=0, le=1)
    screening_status: AIScreeningStatus
    uncertainty: float | None = Field(default=None, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    visibility: AIResultVisibility
    is_simulated: bool
    model_version: str
    preprocessing_version: str
    created_at: datetime
    review: AIAnalysisReviewResponse | None = None


class AIAnalysisResultPage(BaseModel):
    items: list[AIAnalysisResultResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
