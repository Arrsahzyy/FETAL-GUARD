"""Track backend-derived vitals and the rule that raised each alert.

Clinical values in session_sensor_summaries used to be writable only by the
client, and were therefore never populated for real device uploads. They are now
derived server-side from stored raw channels, so the summary records when that
derivation last ran and why it produced no value, letting the UI distinguish
"still collecting" from "signal not good enough".

notifications.rule_code identifies which rule produced an alert, so re-evaluating
a session on every packet can suppress duplicates by code instead of by matching
user-facing message text, which would break silently whenever the copy changed.

Revision ID: 20260830_0019
Revises: 20260830_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0019"
down_revision = "20260830_0018"
branch_labels = None
depends_on = None

DERIVATION_STATUSES = (
    "pending",
    "derived",
    "insufficient_signal",
    "unsupported_schema",
)


def upgrade() -> None:
    op.add_column(
        "session_sensor_summaries",
        sa.Column("derived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "session_sensor_summaries",
        sa.Column(
            "derivation_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    with op.batch_alter_table("session_sensor_summaries") as batch:
        batch.create_check_constraint(
            "ck_session_sensor_summaries_derivation_status",
            "derivation_status IN ('" + "', '".join(DERIVATION_STATUSES) + "')",
        )

    op.add_column(
        "notifications",
        sa.Column("rule_code", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_notifications_session_rule_code",
        "notifications",
        ["session_id", "rule_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_session_rule_code", table_name="notifications")
    op.drop_column("notifications", "rule_code")
    with op.batch_alter_table("session_sensor_summaries") as batch:
        batch.drop_constraint(
            "ck_session_sensor_summaries_derivation_status", type_="check"
        )
    op.drop_column("session_sensor_summaries", "derivation_status")
    op.drop_column("session_sensor_summaries", "derived_at")
