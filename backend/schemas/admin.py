from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from core.security import BCRYPT_MAX_PASSWORD_BYTES


class AdminClinicianCreate(BaseModel):
    email: EmailStr
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).strip().lower()

    @field_validator("temporary_password")
    @classmethod
    def validate_password_bcrypt_size(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes")
        return value


class AdminClinicianBulkCreate(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=100)

    @field_validator("emails", mode="after")
    @classmethod
    def normalize_emails(cls, value: list[EmailStr]) -> list[str]:
        normalized = [str(item).strip().lower() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Email list contains duplicate addresses")
        return normalized


class AdminUserSummary(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool = True
    must_reset_password: bool = False
    password_changed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminClinicianListResponse(BaseModel):
    items: list[AdminUserSummary]
    total: int
    limit: int
    offset: int


class AdminAssignedClinicianSummary(AdminUserSummary):
    assignment_id: str


class AdminPatientSummary(BaseModel):
    id: str
    user_id: str
    name: str
    age: int
    gestational_age_weeks: int
    created_at: datetime
    assigned_clinicians: list[AdminAssignedClinicianSummary] = Field(default_factory=list)


class AdminPatientListResponse(BaseModel):
    items: list[AdminPatientSummary]
    total: int
    limit: int
    offset: int


class AdminPatientAssignmentCreate(BaseModel):
    patient_id: str
    clinician_id: str


class AdminPatientAssignmentResponse(BaseModel):
    id: str
    patient_id: str
    clinician_id: str
    assigned_by_user_id: str | None = None
    created_at: datetime
    patient: AdminPatientSummary
    clinician: AdminUserSummary


class AdminClinicianProvisionResponse(BaseModel):
    user: AdminUserSummary
    temporary_password: str


class AdminClinicianPasswordReset(BaseModel):
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("temporary_password")
    @classmethod
    def validate_password_bcrypt_size(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes")
        return value


class AdminClinicianBulkProvisionResponse(BaseModel):
    clinicians: list[AdminClinicianProvisionResponse]


class AdminAuditLogSummary(BaseModel):
    id: str
    actor_user_id: str
    action: str
    target_user_id: str | None = None
    target_email: str | None = None
    details: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
