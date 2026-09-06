"""Stamp when gestational_age_weeks was last recorded.

Gestational age is now advanced with the calendar on every read (see
core.gestation). When the patient has no LMP the fallback anchor is the date
the number was entered, which must survive later edits to unrelated profile
fields — updated_at cannot serve, it moves on any change. This column is set
only when gestational_age_weeks itself is written. Existing rows are
backfilled to their creation date, the best anchor available in hindsight.

Revision ID: 20260907_0022
Revises: 20260901_0021
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0022"
down_revision = "20260901_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("gestational_age_recorded_at", sa.Date(), nullable=True),
    )
    op.execute(
        "UPDATE patients "
        "SET gestational_age_recorded_at = CAST(created_at AS DATE) "
        "WHERE gestational_age_recorded_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("patients", "gestational_age_recorded_at")
