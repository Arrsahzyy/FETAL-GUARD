from alembic import op
import sqlalchemy as sa

revision = "20260621_0003"
down_revision = "20260621_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="ck_notifications_risk_level"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_session_id"), "notifications", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_session_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
