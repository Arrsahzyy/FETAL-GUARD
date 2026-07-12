from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator

from core.security import BCRYPT_MAX_PASSWORD_BYTES


class UserRole(str, Enum):
    patient = "patient"
    clinician = "clinician"
    admin = "admin"


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.patient

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).strip().lower()


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_bcrypt_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes")
        return value


class UserResponse(UserBase):
    id: str
    is_active: bool = True
    must_reset_password: bool = False
    password_changed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password_bcrypt_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes")
        return value


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)


class TokenData(BaseModel):
    sub: str | None = None
    role: str | None = None
