from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.config import settings  # noqa: E402
from db.database import Base  # noqa: E402
import models.patient  # noqa: F401, E402
import models.patient_clinician_assignment  # noqa: F401, E402
import models.device  # noqa: F401, E402
import models.session_sensor_summary  # noqa: F401, E402
import models.sensor_data  # noqa: F401, E402
import models.session  # noqa: F401, E402
import models.notification  # noqa: F401, E402
import models.user  # noqa: F401, E402
import models.auth_login_attempt  # noqa: F401, E402
import models.auth_refresh_token  # noqa: F401, E402
import models.admin_audit_log  # noqa: F401, E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.SQLALCHEMY_DATABASE_URI,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
