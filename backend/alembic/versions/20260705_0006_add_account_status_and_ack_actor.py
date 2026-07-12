from alembic import op
import sqlalchemy as sa

revision = "20260705_0006"
down_revision = "20260630_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("acknowledged_by_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("acknowledgement_note", sa.String(length=500), nullable=True))
        batch_op.create_index(
            op.f("ix_notifications_acknowledged_by_user_id"),
            ["acknowledged_by_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_notifications_acknowledged_by_user_id_users",
            "users",
            ["acknowledged_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint(
            "fk_notifications_acknowledged_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_notifications_acknowledged_by_user_id"))
        batch_op.drop_column("acknowledgement_note")
        batch_op.drop_column("acknowledged_by_user_id")
    op.drop_column("users", "is_active")
