import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from db.database import SessionLocal, engine, Base
from models.admin_audit_log import AdminAuditLog  # noqa: F401
from models.auth_login_attempt import AuthLoginAttempt  # noqa: F401
from models.auth_refresh_token import AuthRefreshToken  # noqa: F401
from models.device import Device  # noqa: F401
from models.notification import Notification  # noqa: F401
from models.patient import Patient  # noqa: F401
from models.patient_clinician_assignment import PatientClinicianAssignment  # noqa: F401
from models.sensor_data import SensorDataChunk  # noqa: F401
from models.session import MonitoringSession  # noqa: F401
from models.session_sensor_summary import SessionSensorSummary  # noqa: F401
from models.user import User
from core.security import get_password_hash

def seed_clinician():
    # Pastikan tabel dibuat (aman jika sudah ada)
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    
    email = "dokter@fetalguard.com"
    password = "admin123"
    
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = get_password_hash(password)
            db.commit()
            print(f"Akun Nakes diperbarui: {email}")
            print(f"Password baru: {password}")
            return

        new_clinician = User(
            email=email,
            hashed_password=get_password_hash(password),
            role="clinician"
        )
        db.add(new_clinician)
        db.commit()
        print(f"Berhasil membuat akun Nakes!")
        print(f"Email: {email}")
        print(f"Password: {password}")
    except Exception as e:
        print(f"Gagal seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_clinician()
