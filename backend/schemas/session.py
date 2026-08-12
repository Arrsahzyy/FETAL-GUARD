from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.device import normalize_device_uid

from schemas.sensor_summary import SessionSensorSummaryResponse


class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    error = "error"


class SessionEndStatus(str, Enum):
    completed = "completed"
    error = "error"


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_uid: str | None = Field(default=None, min_length=3, max_length=80)
    client_session_id: str | None = Field(default=None, min_length=8, max_length=80)

    @field_validator("device_uid")
    @classmethod
    def normalize_device_uid_field(cls, value: str | None) -> str | None:
        return normalize_device_uid(value) if value else None

    @field_validator("client_session_id")
    @classmethod
    def normalize_client_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not all(character.isalnum() or character in "-_" for character in normalized):
            raise ValueError("client_session_id may only contain letters, numbers, hyphens, and underscores")
        return normalized


class SessionUpdate(BaseModel):
    status: SessionEndStatus = SessionEndStatus.completed


class SessionResponse(BaseModel):
    id: str
    organization_id: str
    patient_id: str
    device_id: str | None = None
    device_assignment_id: str | None = None
    client_session_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    last_data_at: datetime | None = None
    last_captured_at: datetime | None = None
    status: SessionStatus
    sensor_summary: SessionSensorSummaryResponse | None = None

    model_config = {"from_attributes": True}
