import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import get_password_hash
from core.tenancy import ensure_default_organization
from db.database import Base, SessionLocal, engine
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


def _required_environment_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} wajib disetel untuk menjalankan bootstrap admin.")
    return value


def _load_seed_credentials() -> tuple[str, str]:
    if settings.ENVIRONMENT == "production":
        allow_bootstrap = os.getenv("FG_ALLOW_ADMIN_BOOTSTRAP", "").strip().lower()
        if allow_bootstrap != "true":
            raise RuntimeError(
                "Bootstrap admin production dinonaktifkan. Set FG_ALLOW_ADMIN_BOOTSTRAP=true hanya untuk bootstrap terkontrol."
            )

    email = _required_environment_value("FG_ADMIN_EMAIL").lower()
    password = _required_environment_value("FG_ADMIN_PASSWORD")
    if "@" not in email:
        raise RuntimeError("FG_ADMIN_EMAIL harus berupa alamat email yang valid.")
    if len(password) < 8:
        raise RuntimeError("FG_ADMIN_PASSWORD minimal 8 karakter.")
    return email, password


def seed_admin() -> None:
    email, password = _load_seed_credentials()
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.role != "admin":
                raise RuntimeError("Email bootstrap sudah digunakan oleh akun dengan role berbeda.")
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
            if membership is not None and membership.role != "org_admin":
                raise RuntimeError("Akun admin memiliki membership aktif dengan role yang tidak sesuai.")
            if membership is None:
                db.add(
                    OrganizationMembership(
                        organization_id=organization.id,
                        user_id=user.id,
                        role="org_admin",
                        granted_by_user_id=user.id,
                    )
                )
                db.commit()
            print("Akun admin dan membership sudah tersedia; bootstrap tidak mengubah credential yang ada.")
            return

        admin_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            role="admin",
            must_reset_password=True,
        )
        db.add(admin_user)
        db.flush()
        organization = ensure_default_organization(db)
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=admin_user.id,
                role="org_admin",
                granted_by_user_id=admin_user.id,
            )
        )
        db.commit()
        print("Akun admin dibuat dan wajib mengganti password saat login pertama.")
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError("Gagal membuat akun admin karena constraint database. Jalankan migration terbaru terlebih dahulu.") from exc
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
