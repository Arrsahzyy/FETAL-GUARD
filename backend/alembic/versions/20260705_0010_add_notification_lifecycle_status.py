from alembic import op
import sqlalchemy as sa

revision = "20260705_0010"
down_revision = "20260705_0009"
branch_labels = None
depends_on = None

ALLOWED_STATUSES = "'open', 'acknowledged', 'in_review', 'resolved', 'false_positive', 'archived'"


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open")
        )

    op.execute(
        "UPDATE notifications "
        "SET status = CASE WHEN is_acknowledged = 1 THEN 'acknowledged' ELSE 'open' END"
    )

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("status", server_default=None, existing_type=sa.String(length=32))
        batch_op.create_check_constraint(
            "ck_notifications_status",
            f"status IN ({ALLOWED_STATUSES})",
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("ck_notifications_status", type_="check")
        batch_op.drop_column("status")
