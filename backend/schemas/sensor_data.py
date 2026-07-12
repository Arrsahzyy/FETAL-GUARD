"""Sensor data schemas for Fetal Guard.

SensorDataChunkCreate validates incoming data chunks from ESP32 hardware.
The expected payload format (per Technical Roadmap Section 3.6) is:

    {
        "t": <unix_timestamp_ms: int>,
        "p": [<piezo_int>, ...],   # 4-channel piezo, up to 4000 pts/s
        "fsr": [<fsr_int>, ...],   # FSR408 pressure, up to 50 pts/s
        "hr_ir": [<ir_int>, ...],  # MAX30102 IR, up to 100 pts/s
        "hr_red": [<red_int>, ...] # MAX30102 Red, up to 100 pts/s
    }

All channel arrays are optional to support devices in partial-sensor
configurations (e.g., piezo-only, or BLE compact-mode). However, at
least one channel must be present.

Safe boundaries per channel enforce that a single chunk cannot trigger
Out-Of-Memory conditions. The limits (5000 pts) correspond to ~5 seconds
of full-rate piezo data per channel, which is sufficient for the 1-second
transmission window defined in the Roadmap.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.device import normalize_device_uid
from schemas.sensor_summary import SensorSummaryCreate

# ── per-channel limits (safety guard against OOM / malformed payloads) ──────
_MAX_PTS_PER_CHANNEL = 5_000
_MAX_TIMESTAMP_MS = 2**53 - 1   # JS Number.MAX_SAFE_INTEGER

# ── legacy generic alias kept for any code that still imports it ─────────────
SensorPayload = dict[str, Any] | list[Any]


class SensorChannels(BaseModel):
    """Typed representation of one ESP32 transmission window.

    All channels are optional so that a device in partial-sensor mode
    (e.g., running only piezo during calibration) can still submit data.
    At least one channel must be present.
    """

    t: Annotated[int, Field(ge=0, le=_MAX_TIMESTAMP_MS)] | None = Field(
        default=None,
        description="Unix timestamp in milliseconds at time of acquisition.",
    )
    p: list[Annotated[int, Field(ge=0, le=4095)]] | None = Field(
        default=None,
        description="Piezo ADC readings (12-bit, 4 channels interleaved or per-channel list).",
    )
    fsr: list[Annotated[int, Field(ge=0, le=4095)]] | None = Field(
        default=None,
        description="FSR408 ADC readings (12-bit).",
    )
    hr_ir: list[Annotated[int, Field(ge=0, le=262143)]] | None = Field(
        default=None,
        description="MAX30102 IR channel raw counts (18-bit).",
    )
    hr_red: list[Annotated[int, Field(ge=0, le=262143)]] | None = Field(
        default=None,
        description="MAX30102 Red channel raw counts (18-bit).",
    )

    @field_validator("p", "fsr", "hr_ir", "hr_red", mode="after")
    @classmethod
    def _check_channel_length(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) > _MAX_PTS_PER_CHANNEL:
            raise ValueError(
                f"Channel exceeds maximum of {_MAX_PTS_PER_CHANNEL} data points per chunk."
            )
        return value

    @model_validator(mode="after")
    def _require_at_least_one_channel(self) -> "SensorChannels":
        has_data = any([
            self.p is not None,
            self.fsr is not None,
            self.hr_ir is not None,
            self.hr_red is not None,
        ])
        if not has_data:
            raise ValueError(
                "At least one sensor channel (p, fsr, hr_ir, hr_red) must be present."
            )
        return self


class SensorDataChunkCreate(BaseModel):
    """Top-level schema for a sensor data chunk upload.

    'payload' is the structured sensor data.  'source' and 'is_simulated'
    are metadata for traceability (distinguishing real device data from
    test/simulation data ingested during development).
    """

    payload: SensorChannels
    device_uid: str | None = Field(default=None, min_length=3, max_length=80)
    source: str | None = Field(default=None, max_length=32)
    is_simulated: bool | None = None
    summary: SensorSummaryCreate | None = None

    @field_validator("device_uid")
    @classmethod
    def normalize_device_uid_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_device_uid(value)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"mock", "device", "ble", "mqtt", "manual"}:
            raise ValueError("Source must be one of: mock, device, ble, mqtt, manual")
        return normalized

    @model_validator(mode="after")
    def require_device_uid_for_device_sources(self) -> "SensorDataChunkCreate":
        if self.source in {"device", "ble", "mqtt"} and not self.device_uid:
            raise ValueError("device_uid is required for device, BLE, or MQTT sensor uploads")
        return self

    def to_stored_payload(self) -> dict[str, Any]:
        """Serialise the chunk to the format stored in the database."""
        channels = self.payload.model_dump(exclude_none=True)
        if self.source is None and self.is_simulated is None and self.device_uid is None:
            return channels
        stored_payload = {
            "source": self.source or "manual",
            "is_simulated": bool(self.is_simulated),
            "samples": channels,
        }
        if self.device_uid:
            stored_payload["device_uid"] = self.device_uid
        return stored_payload


class SensorDataChunkResponse(BaseModel):
    id: str
    session_id: str
    timestamp: datetime
    payload: Any

    model_config = {"from_attributes": True}
