from alembic import op
import sqlalchemy as sa

revision = "20260705_0008"
down_revision = "20260705_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_clinician_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["clinician_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "clinician_user_id", name="uq_patient_clinician_assignment"),
    )
    op.create_index(op.f("ix_patient_clinician_assignments_id"), "patient_clinician_assignments", ["id"], unique=False)
    op.create_index(
        op.f("ix_patient_clinician_assignments_patient_id"),
        "patient_clinician_assignments",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_clinician_assignments_clinician_user_id"),
        "patient_clinician_assignments",
        ["clinician_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_clinician_assignments_clinician_user_id"), table_name="patient_clinician_assignments")
    op.drop_index(op.f("ix_patient_clinician_assignments_patient_id"), table_name="patient_clinician_assignments")
    op.drop_index(op.f("ix_patient_clinician_assignments_id"), table_name="patient_clinician_assignments")
    op.drop_table("patient_clinician_assignments")
