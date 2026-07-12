from alembic import op
import sqlalchemy as sa

revision = "20260705_0011"
down_revision = "20260705_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_uid", sa.String(length=80), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("hardware_revision", sa.String(length=80), nullable=True),
        sa.Column("firmware_version", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('registered', 'active', 'maintenance', 'retired', 'lost')",
            name="ck_devices_status",
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_id"), "devices", ["id"], unique=False)
    op.create_index(op.f("ix_devices_device_uid"), "devices", ["device_uid"], unique=True)
    op.create_index(op.f("ix_devices_patient_id"), "devices", ["patient_id"], unique=False)
    op.create_index(op.f("ix_devices_status"), "devices", ["status"], unique=False)

    op.create_table(
        "session_sensor_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("fhr_estimate_bpm", sa.Integer(), nullable=True),
        sa.Column("maternal_hr_bpm", sa.Integer(), nullable=True),
        sa.Column("signal_quality_index", sa.Float(), nullable=True),
        sa.Column("contraction_indicator", sa.String(length=32), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "contraction_indicator IN ('unknown', 'none', 'mild', 'regular', 'strong')",
            name="ck_session_sensor_summaries_contraction_indicator",
        ),
        sa.CheckConstraint(
            "signal_quality_index IS NULL OR (signal_quality_index >= 0 AND signal_quality_index <= 1)",
            name="ck_session_sensor_summaries_signal_quality_index",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_session_sensor_summaries_id"), "session_sensor_summaries", ["id"], unique=False)
    op.create_index(
        op.f("ix_session_sensor_summaries_session_id"),
        "session_sensor_summaries",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_session_sensor_summaries_device_id"),
        "session_sensor_summaries",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_session_sensor_summaries_device_id"), table_name="session_sensor_summaries")
    op.drop_index(op.f("ix_session_sensor_summaries_session_id"), table_name="session_sensor_summaries")
    op.drop_index(op.f("ix_session_sensor_summaries_id"), table_name="session_sensor_summaries")
    op.drop_table("session_sensor_summaries")
    op.drop_index(op.f("ix_devices_status"), table_name="devices")
    op.drop_index(op.f("ix_devices_patient_id"), table_name="devices")
    op.drop_index(op.f("ix_devices_device_uid"), table_name="devices")
    op.drop_index(op.f("ix_devices_id"), table_name="devices")
    op.drop_table("devices")
