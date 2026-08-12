from datetime import datetime

from pydantic import BaseModel, Field


class RealtimeEventResponse(BaseModel):
    cursor: int = Field(ge=1)
    event_id: str
    event_type: str
    patient_id: str
    resource_type: str
    resource_id: str
    occurred_at: datetime
    data: dict


class RealtimeEventPageResponse(BaseModel):
    events: list[RealtimeEventResponse]
    next_cursor: int = Field(ge=0)
    has_more: bool
    retry_after_ms: int = Field(ge=1000, le=60000)
