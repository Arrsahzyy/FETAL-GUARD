from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ContractionIndicator(str, Enum):
    unknown = "unknown"
    none = "none"
    mild = "mild"
    regular = "regular"
    strong = "strong"


class SensorSummaryCreate(BaseModel):
    fhr_estimate_bpm: int | None = Field(default=None, ge=30, le=240)
    maternal_hr_bpm: int | None = Field(default=None, ge=30, le=220)
    signal_quality_index: float | None = Field(default=None, ge=0, le=1)
    contraction_indicator: ContractionIndicator | None = None


class SessionSensorSummaryResponse(BaseModel):
    id: str
    session_id: str
    device_id: str | None = None
    fhr_estimate_bpm: int | None = None
    maternal_hr_bpm: int | None = None
    signal_quality_index: float | None = None
    contraction_indicator: ContractionIndicator = ContractionIndicator.unknown
    sample_count: int
    source: str
    is_simulated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
