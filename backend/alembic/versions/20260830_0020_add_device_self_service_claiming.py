"""Add self-service device claiming.

Binding a belt to a patient previously required an admin to create the
assignment. These columns let the patient do it themselves by entering the claim
code printed on the device, which proves physical possession without putting an
admin in the normal path. device_claim_attempts throttles guessing against the
short code.

Revision ID: 20260830_0020
Revises: 20260830_0019
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0020"
down_revision = "20260830_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("claim_code_hash", sa.String(length=128), nullable=True))
    op.add_column(
        "devices",
        sa.Column("claim_code_set_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "device_claim_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_uid", sa.String(length=80), nullable=False),
        sa.Column("client_key", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=True),
        sa.Column("was_successful", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_claim_attempts_id", "device_claim_attempts", ["id"])
    op.create_index("ix_device_claim_attempts_patient_id", "device_claim_attempts", ["patient_id"])
    op.create_index("ix_device_claim_attempts_created_at", "device_claim_attempts", ["created_at"])
    op.create_index(
        "ix_device_claim_attempts_device_created",
        "device_claim_attempts",
        ["device_uid", "created_at"],
    )
    op.create_index(
        "ix_device_claim_attempts_client_created",
        "device_claim_attempts",
        ["client_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_claim_attempts_client_created", table_name="device_claim_attempts")
    op.drop_index("ix_device_claim_attempts_device_created", table_name="device_claim_attempts")
    op.drop_index("ix_device_claim_attempts_created_at", table_name="device_claim_attempts")
    op.drop_index("ix_device_claim_attempts_patient_id", table_name="device_claim_attempts")
    op.drop_index("ix_device_claim_attempts_id", table_name="device_claim_attempts")
    op.drop_table("device_claim_attempts")
    op.drop_column("devices", "claim_code_set_at")
    op.drop_column("devices", "claim_code_hash")
