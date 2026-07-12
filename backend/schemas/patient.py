from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age: int = Field(ge=10, le=60)
    gestational_age_weeks: int = Field(ge=1, le=42)
    medical_history: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    age: int | None = Field(default=None, ge=10, le=60)
    gestational_age_weeks: int | None = Field(default=None, ge=1, le=42)
    medical_history: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


class PatientResponse(BaseModel):
    id: str
    user_id: str
    name: str
    age: int
    gestational_age_weeks: int
    medical_history: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
