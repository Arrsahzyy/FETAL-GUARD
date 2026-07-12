from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

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


class SessionUpdate(BaseModel):
    status: SessionEndStatus = SessionEndStatus.completed


class SessionResponse(BaseModel):
    id: str
    patient_id: str
    start_time: datetime
    end_time: datetime | None = None
    status: SessionStatus
    sensor_summary: SessionSensorSummaryResponse | None = None

    model_config = {"from_attributes": True}
