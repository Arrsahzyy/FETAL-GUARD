"""Add per-device packet signing secrets.

Device UIDs are public labels, so UID matching alone cannot prove a telemetry
packet came from the provisioned belt. These columns hold the symmetric secret
used by core.device_auth to verify an HMAC over each packet. Existing devices are
backfilled as NULL: they keep working outside production, where
enforce_device_packet_authentication requires a provisioned secret.

Revision ID: 20260830_0018
Revises: 20260811_0017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0018"
down_revision = "20260811_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("packet_secret", sa.String(length=128), nullable=True))
    op.add_column(
        "devices",
        sa.Column("packet_secret_provisioned_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("devices", "packet_secret_provisioned_at")
    op.drop_column("devices", "packet_secret")
