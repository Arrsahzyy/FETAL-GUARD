import pytest
from pydantic import ValidationError

from core.config import Settings


def production_settings(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "s" * 48,
        "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://user:password@db/fetal_guard",
        "AUTO_CREATE_DB": False,
        "BACKEND_CORS_ORIGINS": ["https://patient.example.test"],
        "TRUSTED_HOSTS": ["api.example.test"],
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "REFRESH_TOKEN_EXPIRE_DAYS": 14,
        "PATIENT_SELF_REGISTRATION_MODE": "disabled",
        "REQUIRE_POSTGRES_RLS": True,
        "REQUIRE_DEVICE_PACKET_SIGNATURE": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_config_accepts_secure_baseline():
    settings = production_settings()

    assert settings.ENVIRONMENT == "production"
    assert settings.AUTO_CREATE_DB is False


@pytest.mark.parametrize(
    ("override", "expected_message"),
    [
        ({"SECRET_KEY": None}, "SECRET_KEY is required"),
        ({"SQLALCHEMY_DATABASE_URI": "sqlite:///unsafe.db"}, "SQLite is not supported"),
        ({"AUTO_CREATE_DB": True}, "AUTO_CREATE_DB must be false"),
        ({"BACKEND_CORS_ORIGINS": ["http://patient.example.test"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": ["*"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": ["null"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": ["file://patient-app"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": ["capacitor://localhost"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": ["https://*.example.test"]}, "must use HTTPS"),
        ({"BACKEND_CORS_ORIGINS": []}, "must use HTTPS"),
        ({"TRUSTED_HOSTS": ["*"]}, "must be explicit"),
        ({"TRUSTED_HOSTS": []}, "must be explicit"),
        ({"TRUSTED_HOSTS": ["   "]}, "must be explicit"),
        (
            {"TRUSTED_HOSTS": ["localhost", "127.0.0.1", "testserver"]},
            "must not include the testserver host",
        ),
        (
            {"TRUSTED_HOSTS": ["api.example.test", "testserver"]},
            "must not include the testserver host",
        ),
        (
            {"TRUSTED_HOSTS": ["localhost", "127.0.0.1"]},
            "must name the deployment hostname",
        ),
        ({"ACCESS_TOKEN_EXPIRE_MINUTES": 61}, "may not exceed 60 minutes"),
        ({"REFRESH_TOKEN_EXPIRE_DAYS": 31}, "may not exceed 30 days"),
        (
            {
                "PATIENT_SELF_REGISTRATION_MODE": "single_facility",
                "PATIENT_REGISTRATION_ORGANIZATION_ID": None,
            },
            "PATIENT_REGISTRATION_ORGANIZATION_ID is required",
        ),
        ({"REQUIRE_POSTGRES_RLS": False}, "REQUIRE_POSTGRES_RLS must be true"),
        (
            {"REQUIRE_DEVICE_PACKET_SIGNATURE": False},
            "REQUIRE_DEVICE_PACKET_SIGNATURE must be true",
        ),
    ],
)
def test_production_config_rejects_unsafe_values(override, expected_message):
    with pytest.raises(ValidationError, match=expected_message):
        production_settings(**override)


def test_production_allows_loopback_probe_host_alongside_the_deployment_host():
    settings = production_settings(TRUSTED_HOSTS=["api.example.test", "127.0.0.1"])

    assert "api.example.test" in settings.TRUSTED_HOSTS


def test_production_allows_explicit_single_facility_patient_registration():
    settings = production_settings(
        PATIENT_SELF_REGISTRATION_MODE="single_facility",
        PATIENT_REGISTRATION_ORGANIZATION_ID="00000000-0000-0000-0000-000000000010",
    )

    assert settings.PATIENT_REGISTRATION_ORGANIZATION_ID.endswith("0010")
