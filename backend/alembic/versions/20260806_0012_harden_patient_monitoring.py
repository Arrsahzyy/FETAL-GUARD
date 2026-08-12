"""Harden patient profile, monitoring sessions, and sensor ingestion."""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0012"
down_revision = "20260705_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))

    patient_columns = (
        sa.Column("national_id", sa.String(length=16), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("blood_type", sa.String(length=3), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone_number", sa.String(length=24), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=24), nullable=True),
        sa.Column("last_menstrual_period", sa.Date(), nullable=True),
        sa.Column("estimated_due_date", sa.Date(), nullable=True),
        sa.Column("gravida", sa.Integer(), nullable=True),
        sa.Column("para", sa.Integer(), nullable=True),
        sa.Column("abortus", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("pre_pregnancy_weight_kg", sa.Float(), nullable=True),
        sa.Column("current_weight_kg", sa.Float(), nullable=True),
        sa.Column("previous_delivery_type", sa.String(length=32), nullable=True),
        sa.Column("previous_pregnancy_complications", sa.Text(), nullable=True),
        sa.Column("has_hypertension", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_diabetes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_heart_condition", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_asthma", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_allergies", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allergy_details", sa.Text(), nullable=True),
        sa.Column("current_medications", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("patients") as batch_op:
        for column in patient_columns:
            batch_op.add_column(column)
        batch_op.create_index("ix_patients_national_id", ["national_id"], unique=True)

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("client_session_id", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("last_data_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_device_id_devices",
            "devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_sessions_device_id", ["device_id"], unique=False)

    op.create_index(
        "uq_sessions_active_patient",
        "sessions",
        ["patient_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_sessions_client_session_id",
        "sessions",
        ["patient_id", "client_session_id"],
        unique=True,
        sqlite_where=sa.text("client_session_id IS NOT NULL"),
        postgresql_where=sa.text("client_session_id IS NOT NULL"),
    )

    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("ingestion_id", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("boot_id", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("sequence_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_session_data_chunks_device_id_devices",
            "devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_session_data_chunks_device_id", ["device_id"], unique=False)

    # Existing development chunks receive their stable server id as ingestion id.
    op.execute("UPDATE session_data_chunks SET ingestion_id = id WHERE ingestion_id IS NULL")
    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.alter_column("ingestion_id", existing_type=sa.String(length=80), nullable=False)
        batch_op.create_unique_constraint(
            "uq_session_data_chunks_ingestion_id",
            ["session_id", "ingestion_id"],
        )
        batch_op.create_unique_constraint(
            "uq_session_data_chunks_device_sequence",
            ["device_id", "boot_id", "sequence_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.drop_constraint("uq_session_data_chunks_device_sequence", type_="unique")
        batch_op.drop_constraint("uq_session_data_chunks_ingestion_id", type_="unique")
        batch_op.drop_index("ix_session_data_chunks_device_id")
        batch_op.drop_constraint("fk_session_data_chunks_device_id_devices", type_="foreignkey")
        for column_name in (
            "captured_at",
            "schema_version",
            "sequence_number",
            "boot_id",
            "ingestion_id",
            "device_id",
        ):
            batch_op.drop_column(column_name)

    op.drop_index("uq_sessions_client_session_id", table_name="sessions")
    op.drop_index("uq_sessions_active_patient", table_name="sessions")
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_device_id")
        batch_op.drop_constraint("fk_sessions_device_id_devices", type_="foreignkey")
        batch_op.drop_column("last_data_at")
        batch_op.drop_column("client_session_id")
        batch_op.drop_column("device_id")

    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_index("ix_patients_national_id")
        for column_name in (
            "updated_at",
            "current_medications",
            "allergy_details",
            "has_allergies",
            "has_asthma",
            "has_heart_condition",
            "has_diabetes",
            "has_hypertension",
            "previous_pregnancy_complications",
            "previous_delivery_type",
            "current_weight_kg",
            "pre_pregnancy_weight_kg",
            "height_cm",
            "abortus",
            "para",
            "gravida",
            "estimated_due_date",
            "last_menstrual_period",
            "emergency_contact_phone",
            "emergency_contact_name",
            "phone_number",
            "address",
            "blood_type",
            "birth_date",
            "national_id",
        ):
            batch_op.drop_column(column_name)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("auth_version")
