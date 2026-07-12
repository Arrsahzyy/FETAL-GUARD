from alembic import op
import sqlalchemy as sa

revision = "20260626_0004"
down_revision = "0e069566736d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    check_names = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "ck_users_role" in check_names:
            batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint(
            "ck_users_role",
            "role IN ('patient', 'clinician', 'admin')",
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    check_names = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "ck_users_role" in check_names:
            batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint(
            "ck_users_role",
            "role IN ('patient', 'clinician')",
        )
