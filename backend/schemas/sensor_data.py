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

from datetime import datetime, timezone
from typing import Annotated, Any
import uuid

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
            bool(self.p),
            bool(self.fsr),
            bool(self.hr_ir),
            bool(self.hr_red),
        ])
        if not has_data:
            raise ValueError(
                "At least one sensor channel (p, fsr, hr_ir, hr_red) must be present."
            )
        return self


class SensorSampleRates(BaseModel):
    """Native sample rate for each raw channel in a telemetry v2 chunk."""

    p: float | None = Field(default=None, gt=0, le=10_000)
    fsr: float | None = Field(default=None, gt=0, le=10_000)
    hr_ir: float | None = Field(default=None, gt=0, le=10_000)
    hr_red: float | None = Field(default=None, gt=0, le=10_000)


class SensorChannelLayout(BaseModel):
    """Channel cardinality needed to reconstruct interleaved samples."""

    p: int | None = Field(default=None, ge=1, le=8)


class SensorDataChunkCreate(BaseModel):
    """Top-level schema for a sensor data chunk upload.

    'payload' is the structured sensor data.  'source' and 'is_simulated'
    are metadata for traceability (distinguishing real device data from
    test/simulation data ingested during development).
    """

    payload: SensorChannels
    schema_version: int = Field(default=1, ge=1, le=10)
    ingestion_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=8, max_length=80)
    boot_id: str | None = Field(default=None, min_length=8, max_length=80)
    sequence_number: int | None = Field(default=None, ge=0, le=2**63 - 1)
    captured_at: datetime | None = None
    sample_rate_hz: float | None = Field(default=None, gt=0, le=10_000)
    sample_rates_hz: SensorSampleRates | None = None
    channel_layout: SensorChannelLayout | None = None
    device_uid: str | None = Field(default=None, min_length=3, max_length=80)
    # Lowercase hex HMAC-SHA256 produced by the device over its identity tuple and
    # sample digest. Verified in the ingestion route against the device's
    # provisioned secret; see core.device_auth.
    packet_signature: str | None = Field(default=None, min_length=64, max_length=64)
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

    @field_validator("packet_signature")
    @classmethod
    def normalize_packet_signature(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or not all(character in "0123456789abcdef" for character in normalized):
            raise ValueError("packet_signature must be a 64-character hexadecimal HMAC-SHA256 digest")
        return normalized

    @field_validator("ingestion_id", "boot_id")
    @classmethod
    def normalize_packet_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not all(character.isalnum() or character in "-_" for character in normalized):
            raise ValueError("Packet identifiers may only contain letters, numbers, hyphens, and underscores")
        return normalized

    @field_validator("captured_at")
    @classmethod
    def require_timezone_on_captured_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must include a timezone offset")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def require_device_uid_for_device_sources(self) -> "SensorDataChunkCreate":
        is_device_source = self.source in {"device", "ble", "mqtt"}
        if is_device_source and not self.device_uid:
            raise ValueError("device_uid is required for device, BLE, or MQTT sensor uploads")
        if is_device_source:
            required_fields = {
                "ingestion_id": "ingestion_id",
                "boot_id": self.boot_id,
                "sequence_number": self.sequence_number,
                "captured_at": self.captured_at,
            }
            if self.schema_version == 1:
                required_fields["sample_rate_hz"] = self.sample_rate_hz
            else:
                required_fields["sample_rates_hz"] = self.sample_rates_hz
            missing = [
                name for name, value in required_fields.items()
                if (name == "ingestion_id" and name not in self.model_fields_set) or value is None
            ]
            if missing:
                raise ValueError(f"Device uploads require packet metadata: {', '.join(missing)}")

        if self.schema_version >= 2:
            if self.sample_rate_hz is not None:
                raise ValueError("Telemetry v2 must use sample_rates_hz instead of sample_rate_hz")
            rates = self.sample_rates_hz.model_dump(exclude_none=True) if self.sample_rates_hz else {}
            channels = self.payload.model_dump(exclude_none=True)
            present_channels = {
                name for name in ("p", "fsr", "hr_ir", "hr_red") if channels.get(name)
            }
            missing_rates = sorted(present_channels - set(rates))
            if missing_rates:
                raise ValueError(
                    "Telemetry v2 requires a native sample rate for: "
                    + ", ".join(missing_rates)
                )
            if "p" in present_channels:
                if self.channel_layout is None or self.channel_layout.p != 4:
                    raise ValueError("Telemetry v2 piezo data requires channel_layout.p=4")
                if len(self.payload.p or []) % 4 != 0:
                    raise ValueError("Telemetry v2 piezo samples must be interleaved in groups of four")
            if ("hr_ir" in present_channels) != ("hr_red" in present_channels):
                raise ValueError("Telemetry v2 maternal PPG requires paired hr_ir and hr_red channels")
            if "hr_ir" in present_channels and len(self.payload.hr_ir or []) != len(self.payload.hr_red or []):
                raise ValueError("Telemetry v2 maternal PPG channels must have equal lengths")

        if self.source == "mock" and self.is_simulated is not True:
            raise ValueError("Mock sensor uploads must set is_simulated=true")
        if is_device_source and self.is_simulated is True:
            raise ValueError("Device, BLE, and MQTT uploads cannot be marked as simulated")
        if self.is_simulated is True and self.source != "mock":
            raise ValueError("Simulated uploads must use source=mock")
        if self.summary is not None and self.source != "mock":
            raise ValueError(
                "Derived sensor summaries are not accepted from untrusted device or manual uploads"
            )
        return self

    def to_stored_payload(self) -> dict[str, Any]:
        """Serialise the chunk to the format stored in the database."""
        channels = self.payload.model_dump(exclude_none=True)
        stored_payload = {
            "schema_version": self.schema_version,
            "ingestion_id": self.ingestion_id,
            "source": self.source or "manual",
            "is_simulated": bool(self.is_simulated),
            "samples": channels,
        }
        if self.boot_id:
            stored_payload["boot_id"] = self.boot_id
        if self.sequence_number is not None:
            stored_payload["sequence_number"] = self.sequence_number
        if self.captured_at:
            stored_payload["captured_at"] = self.captured_at.isoformat()
        if self.sample_rate_hz is not None:
            stored_payload["sample_rate_hz"] = self.sample_rate_hz
        if self.sample_rates_hz is not None:
            stored_payload["sample_rates_hz"] = self.sample_rates_hz.model_dump(exclude_none=True)
        if self.channel_layout is not None:
            stored_payload["channel_layout"] = self.channel_layout.model_dump(exclude_none=True)
        if self.device_uid:
            stored_payload["device_uid"] = self.device_uid
        return stored_payload


class SensorDataChunkResponse(BaseModel):
    id: str
    organization_id: str
    session_id: str
    timestamp: datetime
    device_id: str | None = None
    ingestion_id: str
    boot_id: str | None = None
    sequence_number: int | None = None
    schema_version: int
    captured_at: datetime | None = None
    was_duplicate: bool = False

    model_config = {"from_attributes": True}
