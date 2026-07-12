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
