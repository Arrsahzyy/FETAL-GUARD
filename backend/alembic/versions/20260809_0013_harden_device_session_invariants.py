"""Enforce a single active monitoring session for each device."""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0013"
down_revision = "20260806_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    conflicting_devices = connection.execute(
        sa.text(
            "SELECT device_id "
            "FROM sessions "
            "WHERE status = 'active' AND device_id IS NOT NULL "
            "GROUP BY device_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if conflicting_devices:
        device_ids = ", ".join(str(row[0]) for row in conflicting_devices)
        raise RuntimeError(
            "Cannot enforce one active session per device while conflicting "
            f"sessions exist for device(s): {device_ids}. Resolve them explicitly first."
        )

    mismatched_sessions = connection.execute(
        sa.text(
            "SELECT s.id "
            "FROM sessions AS s "
            "LEFT JOIN devices AS d ON d.id = s.device_id "
            "WHERE s.status = 'active' AND s.device_id IS NOT NULL "
            "AND (d.id IS NULL OR d.patient_id IS NULL OR d.patient_id <> s.patient_id)"
        )
    ).fetchall()
    if mismatched_sessions:
        session_ids = ", ".join(str(row[0]) for row in mismatched_sessions)
        raise RuntimeError(
            "Cannot enforce active device-session ownership while session/device "
            f"assignments conflict for session(s): {session_ids}. Resolve them explicitly first."
        )

    op.add_column(
        "sessions",
        sa.Column("last_captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_sessions_active_device",
        "sessions",
        ["device_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active' AND device_id IS NOT NULL"),
        postgresql_where=sa.text("status = 'active' AND device_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sessions_active_device", table_name="sessions")
    op.drop_column("sessions", "last_captured_at")
