from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DeviceStatus(str, Enum):
    registered = "registered"
    active = "active"
    maintenance = "maintenance"
    retired = "retired"
    lost = "lost"


def normalize_device_uid(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Device UID cannot be blank")
    return normalized


class DeviceCreate(BaseModel):
    device_uid: str = Field(min_length=3, max_length=80)
    patient_id: str | None = Field(default=None, max_length=36)
    display_name: str = Field(default="FETAL-GUARD Belt", min_length=1, max_length=120)
    hardware_revision: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=80)
    status: DeviceStatus = DeviceStatus.registered

    @field_validator("device_uid")
    @classmethod
    def normalize_uid(cls, value: str) -> str:
        return normalize_device_uid(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Display name cannot be blank")
        return normalized


class DeviceUpdate(BaseModel):
    patient_id: str | None = Field(default=None, max_length=36)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    hardware_revision: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=80)
    status: DeviceStatus | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Display name cannot be blank")
        return normalized


class DeviceResponse(BaseModel):
    id: str
    device_uid: str
    patient_id: str | None = None
    display_name: str
    hardware_revision: str | None = None
    firmware_version: str | None = None
    status: DeviceStatus
    registered_at: datetime
    assigned_at: datetime | None = None
    last_seen_at: datetime | None = None

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    total: int
    limit: int
    offset: int
