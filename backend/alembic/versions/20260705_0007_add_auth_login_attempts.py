from alembic import op
import sqlalchemy as sa

revision = "20260705_0007"
down_revision = "20260705_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("client_key", sa.String(length=64), nullable=False),
        sa.Column("was_successful", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_login_attempts_id"), "auth_login_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_auth_login_attempts_email"), "auth_login_attempts", ["email"], unique=False)
    op.create_index(op.f("ix_auth_login_attempts_client_key"), "auth_login_attempts", ["client_key"], unique=False)
    op.create_index(op.f("ix_auth_login_attempts_created_at"), "auth_login_attempts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_login_attempts_created_at"), table_name="auth_login_attempts")
    op.drop_index(op.f("ix_auth_login_attempts_client_key"), table_name="auth_login_attempts")
    op.drop_index(op.f("ix_auth_login_attempts_email"), table_name="auth_login_attempts")
    op.drop_index(op.f("ix_auth_login_attempts_id"), table_name="auth_login_attempts")
    op.drop_table("auth_login_attempts")
