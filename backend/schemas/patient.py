from datetime import date, datetime
import re

from pydantic import BaseModel, Field, field_validator, model_validator


_PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,20}$")
_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
_DELIVERY_TYPES = {"normal", "cesarean", "vacuum", "forceps"}


class PatientProfileFields(BaseModel):
    national_id: str | None = Field(default=None, min_length=16, max_length=16)
    birth_date: date | None = None
    blood_type: str | None = Field(default=None, max_length=3)
    address: str | None = Field(default=None, max_length=1000)
    phone_number: str | None = Field(default=None, max_length=24)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=24)
    last_menstrual_period: date | None = None
    estimated_due_date: date | None = None
    gravida: int | None = Field(default=None, ge=1, le=20)
    para: int | None = Field(default=None, ge=0, le=20)
    abortus: int | None = Field(default=None, ge=0, le=20)
    height_cm: float | None = Field(default=None, ge=100, le=220)
    pre_pregnancy_weight_kg: float | None = Field(default=None, ge=20, le=300)
    current_weight_kg: float | None = Field(default=None, ge=20, le=350)
    previous_delivery_type: str | None = Field(default=None, max_length=32)
    previous_pregnancy_complications: str | None = Field(default=None, max_length=2000)
    has_hypertension: bool = False
    has_diabetes: bool = False
    has_heart_condition: bool = False
    has_asthma: bool = False
    has_allergies: bool = False
    allergy_details: str | None = Field(default=None, max_length=1000)
    current_medications: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "address",
        "emergency_contact_name",
        "previous_pregnancy_complications",
        "allergy_details",
        "current_medications",
        mode="before",
    )
    @classmethod
    def blank_text_to_none(cls, value):
        if isinstance(value, str):
            normalized = " ".join(value.strip().split())
            return normalized or None
        return value

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.isdigit() or len(normalized) != 16:
            raise ValueError("National ID must contain exactly 16 digits")
        return normalized

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"[\s()-]", "", value)
        if not _PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Phone number must contain 8 to 20 digits and may start with +")
        return normalized

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in _BLOOD_TYPES:
            raise ValueError("Unsupported blood type")
        return normalized

    @field_validator("previous_delivery_type")
    @classmethod
    def validate_delivery_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in _DELIVERY_TYPES:
            raise ValueError("Unsupported previous delivery type")
        return normalized

    @model_validator(mode="after")
    def validate_related_profile_fields(self):
        today = date.today()
        if self.birth_date and self.birth_date >= today:
            raise ValueError("Birth date must be in the past")
        if self.last_menstrual_period and self.last_menstrual_period > today:
            raise ValueError("Last menstrual period cannot be in the future")
        if self.last_menstrual_period and self.estimated_due_date:
            if self.estimated_due_date <= self.last_menstrual_period:
                raise ValueError("Estimated due date must be after the last menstrual period")
        if self.gravida is not None:
            previous_outcomes = (self.para or 0) + (self.abortus or 0)
            if previous_outcomes > self.gravida:
                raise ValueError("Para plus abortus cannot exceed gravida")
        if not self.has_allergies and self.allergy_details:
            raise ValueError("allergy_details requires has_allergies=true")
        return self


class PatientCreate(PatientProfileFields):
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


class PatientUpdate(PatientProfileFields):
    model_config = {"extra": "forbid"}

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
    patient_code: str
    user_id: str
    name: str
    age: int
    gestational_age_weeks: int
    medical_history: str | None = None
    national_id: str | None = None
    birth_date: date | None = None
    blood_type: str | None = None
    address: str | None = None
    phone_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    last_menstrual_period: date | None = None
    estimated_due_date: date | None = None
    gravida: int | None = None
    para: int | None = None
    abortus: int | None = None
    height_cm: float | None = None
    pre_pregnancy_weight_kg: float | None = None
    current_weight_kg: float | None = None
    previous_delivery_type: str | None = None
    previous_pregnancy_complications: str | None = None
    has_hypertension: bool = False
    has_diabetes: bool = False
    has_heart_condition: bool = False
    has_asthma: bool = False
    has_allergies: bool = False
    allergy_details: str | None = None
    current_medications: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientNotificationResponse(BaseModel):
    id: str
    session_id: str
    message: str
    risk_level: str
    status: str
    created_at: datetime
    is_acknowledged: bool
    acknowledged_at: datetime | None = None

    model_config = {"from_attributes": True}
