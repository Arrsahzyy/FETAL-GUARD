from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings


def _sqlite_connect_args(database_uri: str) -> dict[str, bool]:
    if database_uri.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    connect_args=_sqlite_connect_args(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    import models.user  # noqa: F401
    import models.auth_login_attempt  # noqa: F401
    import models.auth_refresh_token  # noqa: F401
    import models.admin_audit_log  # noqa: F401
    import models.device  # noqa: F401
    import models.patient  # noqa: F401
    import models.patient_clinician_assignment  # noqa: F401
    import models.session  # noqa: F401
    import models.session_sensor_summary  # noqa: F401
    import models.sensor_data  # noqa: F401
    import models.notification  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
