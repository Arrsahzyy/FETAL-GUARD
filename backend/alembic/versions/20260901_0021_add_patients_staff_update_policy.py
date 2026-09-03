"""Add the missing staff UPDATE row-level security policy on patients.

Migration 20260809_0015 gave patients a `patients_staff_select` policy but no
matching UPDATE policy, unlike every other admin-managed table (devices,
patient_clinician_assignments, organization_memberships all have `*_admin_update`).

PostgreSQL applies the UPDATE policy's USING clause to `SELECT ... FOR UPDATE`
row locks, so admin code paths that lock a patient row before mutating related
records (e.g. `get_patient_or_404` in api/routes/admin.py, used by
POST /admin/patient-assignments) silently matched zero rows and returned
"Patient not found". This adds the policy so supervisors and org admins can lock
patient rows inside their own organization.

Revision ID: 20260901_0021
Revises: 20260830_0020
"""

from alembic import op


revision = "20260901_0021"
down_revision = "20260830_0020"
branch_labels = None
depends_on = None


_OID = "NULLIF(current_setting('app.current_organization_id', true), '')"
_ROLE = "NULLIF(current_setting('app.current_membership_role', true), '')"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Idempotent: a manual hotfix may already have created this policy on the
    # live database before this migration ran.
    op.execute("DROP POLICY IF EXISTS patients_staff_update ON patients")
    op.execute(
        f"""
        CREATE POLICY patients_staff_update ON patients FOR UPDATE
        USING (organization_id = {_OID} AND {_ROLE} IN ('supervisor', 'org_admin'))
        WITH CHECK (organization_id = {_OID} AND {_ROLE} IN ('supervisor', 'org_admin'))
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS patients_staff_update ON patients")
