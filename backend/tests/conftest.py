import importlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-fetal-guard-auth-suite")
os.environ.setdefault("AUTO_CREATE_DB", "false")

from db.database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from models.user import User  # noqa: E402

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def import_model_modules() -> None:
    for module_name in (
        "models.user",
        "models.auth_login_attempt",
        "models.auth_refresh_token",
        "models.admin_audit_log",
        "models.device",
        "models.patient",
        "models.patient_clinician_assignment",
        "models.session",
        "models.session_sensor_summary",
        "models.sensor_data",
        "models.notification",
    ):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    import_model_modules()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def register_user(client):
    def _register(email="test@example.com", password="password123", role="patient"):
        return client.post(
            "/auth/register",
            json={"email": email, "password": password, "role": role},
        )

    return _register


@pytest.fixture
def create_user(db_session):
    def _create_user(
        email="test@example.com",
        password="password123",
        role="patient",
        must_reset_password=False,
        is_active=True,
    ):
        user = User(
            email=email.strip().lower(),
            hashed_password=get_password_hash(password),
            role=role,
            must_reset_password=must_reset_password,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def login_user(client):
    def _login(email="test@example.com", password="password123"):
        return client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )

    return _login


@pytest.fixture
def auth_headers(register_user, create_user, login_user):
    def _headers(email="patient@example.com", password="password123", role="patient"):
        if role == "patient":
            register_response = register_user(email=email, password=password, role=role)
            assert register_response.status_code == 201
        else:
            create_user(email=email, password=password, role=role)
        login_response = login_user(email=email, password=password)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _headers
