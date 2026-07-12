from alembic import op
import sqlalchemy as sa

revision = "20260705_0009"
down_revision = "20260705_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_key", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["auth_refresh_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_refresh_tokens_id"), "auth_refresh_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_auth_refresh_tokens_user_id"), "auth_refresh_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_auth_refresh_tokens_token_hash"), "auth_refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_auth_refresh_tokens_client_key"), "auth_refresh_tokens", ["client_key"], unique=False)
    op.create_index(op.f("ix_auth_refresh_tokens_expires_at"), "auth_refresh_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_auth_refresh_tokens_revoked_at"), "auth_refresh_tokens", ["revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_refresh_tokens_revoked_at"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_expires_at"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_client_key"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_token_hash"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_user_id"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_id"), table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
