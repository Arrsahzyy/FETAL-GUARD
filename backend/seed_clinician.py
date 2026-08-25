import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from db.database import SessionLocal, engine, Base
from core.config import settings
from core.refresh_tokens import revoke_all_refresh_tokens
from core.tenancy import ensure_default_organization
from models.access_audit_event import AccessAuditEvent  # noqa: F401
from models.admin_audit_log import AdminAuditLog  # noqa: F401
from models.ai_analysis import (  # noqa: F401
    AIAnalysisResult,
    AIAnalysisReview,
    AIInferenceJob,
    AIModelVersion,
)
from models.alert_event import AlertEvent  # noqa: F401
from models.auth_login_attempt import AuthLoginAttempt  # noqa: F401
from models.auth_refresh_token import AuthRefreshToken  # noqa: F401
from models.device import Device  # noqa: F401
from models.device_assignment import DeviceAssignment  # noqa: F401
from models.notification import Notification  # noqa: F401
from models.organization import Organization  # noqa: F401
from models.organization_membership import OrganizationMembership
from models.patient import Patient  # noqa: F401
from models.patient_clinician_assignment import PatientClinicianAssignment  # noqa: F401
from models.realtime_event import RealtimeEvent, RealtimeEventCursor  # noqa: F401
from models.sensor_data import SensorDataChunk  # noqa: F401
from models.session import MonitoringSession  # noqa: F401
from models.session_sensor_summary import SessionSensorSummary  # noqa: F401
from models.user import User
from core.security import get_password_hash


def _required_environment_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} wajib disetel untuk menjalankan seed clinician.")
    return value


def _load_seed_credentials() -> tuple[str, str]:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "seed_clinician dinonaktifkan di production; gunakan provisioning admin yang teraudit."
        )

    email = _required_environment_value("FG_CLINICIAN_EMAIL").lower()
    password = _required_environment_value("FG_CLINICIAN_PASSWORD")
    if "@" not in email:
        raise RuntimeError("FG_CLINICIAN_EMAIL harus berupa alamat email yang valid.")
    if len(password) < 8:
        raise RuntimeError("FG_CLINICIAN_PASSWORD minimal 8 karakter.")
    return email, password


def seed_clinician() -> None:
    email, password = _load_seed_credentials()
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.role != "clinician":
                raise RuntimeError("Email seed sudah digunakan oleh akun dengan role berbeda.")
            organization = ensure_default_organization(db)
            membership = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == organization.id,
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.ended_at.is_(None),
                )
                .first()
            )
            if membership is not None and membership.role != "clinician":
                raise RuntimeError("Akun clinician memiliki membership aktif dengan role yang tidak sesuai.")
            if membership is None:
                db.add(
                    OrganizationMembership(
                        organization_id=organization.id,
                        user_id=user.id,
                        role="clinician",
                        granted_by_user_id=None,
                    )
                )
            user.hashed_password = get_password_hash(password)
            user.must_reset_password = True
            user.auth_version = (user.auth_version or 0) + 1
            revoke_all_refresh_tokens(db, user.id, commit=False)
            db.commit()
            print("Akun clinician development diperbarui dan wajib mengganti password saat login.")
            return

        new_clinician = User(
            email=email,
            hashed_password=get_password_hash(password),
            role="clinician",
            must_reset_password=True,
        )
        db.add(new_clinician)
        db.flush()
        organization = ensure_default_organization(db)
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=new_clinician.id,
                role="clinician",
                granted_by_user_id=None,
            )
        )
        db.commit()
        print("Akun clinician development dibuat dan wajib mengganti password saat login.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_clinician()
