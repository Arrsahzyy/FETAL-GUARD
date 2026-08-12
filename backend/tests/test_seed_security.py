import pytest
from sqlalchemy.orm import sessionmaker

import seed_admin
import seed_clinician
from core.security import verify_password
from models.organization_membership import OrganizationMembership
from models.user import User


def test_clinician_seed_is_disabled_in_production(monkeypatch):
    monkeypatch.setattr(seed_clinician.settings, "ENVIRONMENT", "production")
    monkeypatch.setenv("FG_CLINICIAN_EMAIL", "clinician@example.test")
    monkeypatch.setenv("FG_CLINICIAN_PASSWORD", "temporary-password")

    with pytest.raises(RuntimeError, match="dinonaktifkan di production"):
        seed_clinician._load_seed_credentials()


@pytest.mark.parametrize(
    ("module", "email_variable", "password_variable"),
    [
        (seed_admin, "FG_ADMIN_EMAIL", "FG_ADMIN_PASSWORD"),
        (seed_clinician, "FG_CLINICIAN_EMAIL", "FG_CLINICIAN_PASSWORD"),
    ],
)
def test_seed_credentials_do_not_have_defaults(
    monkeypatch,
    module,
    email_variable,
    password_variable,
):
    monkeypatch.setattr(module.settings, "ENVIRONMENT", "development")
    monkeypatch.delenv(email_variable, raising=False)
    monkeypatch.delenv(password_variable, raising=False)

    with pytest.raises(RuntimeError, match=email_variable):
        module._load_seed_credentials()


def test_admin_production_bootstrap_requires_explicit_gate(monkeypatch):
    monkeypatch.setattr(seed_admin.settings, "ENVIRONMENT", "production")
    monkeypatch.setenv("FG_ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setenv("FG_ADMIN_PASSWORD", "temporary-password")
    monkeypatch.delenv("FG_ALLOW_ADMIN_BOOTSTRAP", raising=False)

    with pytest.raises(RuntimeError, match="dinonaktifkan"):
        seed_admin._load_seed_credentials()

    monkeypatch.setenv("FG_ALLOW_ADMIN_BOOTSTRAP", "true")
    assert seed_admin._load_seed_credentials() == (
        "admin@example.test",
        "temporary-password",
    )


def configure_seed_test_database(monkeypatch, module, db_session):
    test_engine = db_session.get_bind()
    monkeypatch.setattr(module, "engine", test_engine)
    monkeypatch.setattr(module, "SessionLocal", sessionmaker(bind=test_engine))


def test_clinician_seed_creates_membership_without_disclosing_password(
    monkeypatch,
    capsys,
    db_session,
):
    configure_seed_test_database(monkeypatch, seed_clinician, db_session)
    monkeypatch.setattr(seed_clinician.settings, "ENVIRONMENT", "development")
    monkeypatch.setenv("FG_CLINICIAN_EMAIL", "seed-clinician@example.test")
    monkeypatch.setenv("FG_CLINICIAN_PASSWORD", "clinician-secret-123")

    seed_clinician.seed_clinician()

    seeded_user = db_session.query(User).filter(User.email == "seed-clinician@example.test").one()
    membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == seeded_user.id,
        OrganizationMembership.ended_at.is_(None),
    ).one()
    output = capsys.readouterr().out
    assert seeded_user.must_reset_password is True
    assert membership.role == "clinician"
    assert "clinician-secret-123" not in output


def test_admin_seed_creates_membership_without_disclosing_or_resetting_password(
    monkeypatch,
    capsys,
    db_session,
):
    configure_seed_test_database(monkeypatch, seed_admin, db_session)
    monkeypatch.setattr(seed_admin.settings, "ENVIRONMENT", "development")
    monkeypatch.setenv("FG_ADMIN_EMAIL", "seed-admin@example.test")
    monkeypatch.setenv("FG_ADMIN_PASSWORD", "admin-secret-123")

    seed_admin.seed_admin()
    monkeypatch.setenv("FG_ADMIN_PASSWORD", "replacement-secret-456")
    seed_admin.seed_admin()

    seeded_user = db_session.query(User).filter(User.email == "seed-admin@example.test").one()
    membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == seeded_user.id,
        OrganizationMembership.ended_at.is_(None),
    ).one()
    output = capsys.readouterr().out
    assert membership.role == "org_admin"
    assert verify_password("admin-secret-123", seeded_user.hashed_password) is True
    assert verify_password("replacement-secret-456", seeded_user.hashed_password) is False
    assert "admin-secret-123" not in output
    assert "replacement-secret-456" not in output
