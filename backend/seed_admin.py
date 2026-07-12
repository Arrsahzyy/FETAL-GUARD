import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import get_password_hash
from db.database import Base, SessionLocal, engine
from models.notification import Notification  # noqa: F401
from models.patient import Patient  # noqa: F401
from models.sensor_data import SensorDataChunk  # noqa: F401
from models.session import MonitoringSession  # noqa: F401
from models.user import User


def seed_admin() -> None:
    Base.metadata.create_all(bind=engine)

    email = os.getenv("FG_ADMIN_EMAIL", "admin@fetalguard.com").strip().lower()
    uses_default_password = "FG_ADMIN_PASSWORD" not in os.environ
    if settings.ENVIRONMENT == "production" and uses_default_password:
        raise RuntimeError("FG_ADMIN_PASSWORD wajib disetel saat ENVIRONMENT=production.")

    password = os.getenv("FG_ADMIN_PASSWORD", "admin12345")

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = get_password_hash(password)
            user.role = "admin"
            user.must_reset_password = True
            db.commit()
            print(f"Akun admin diperbarui: {email}")
            print(f"Password sementara: {password}")
            print("Admin wajib mengganti password setelah login pertama.")
            return

        admin_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            role="admin",
            must_reset_password=True,
        )
        db.add(admin_user)
        db.commit()
        print("Berhasil membuat akun admin.")
        print(f"Email: {email}")
        print(f"Password sementara: {password}")
        print("Admin wajib mengganti password setelah login pertama.")
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError("Gagal membuat akun admin karena constraint database. Jalankan migration terbaru terlebih dahulu.") from exc
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
