"""Add organization boundaries, temporal care assignments, and access audit history.

Revision ID: 20260809_0014
Revises: 20260809_0013
"""

from __future__ import annotations

import hashlib
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260809_0014"
down_revision = "20260809_0013"
branch_labels = None
depends_on = None


DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ORGANIZATION_SLUG = "fetal-guard-primary"
DEFAULT_ORGANIZATION_NAME = "FETAL-GUARD Primary Facility"


def _patient_code(patient_id: str, occupied: set[str]) -> str:
    """Build a stable opaque code without exposing a UUID prefix."""

    nonce = 0
    while True:
        material = patient_id if nonce == 0 else f"{patient_id}:{nonce}"
        suffix = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12].upper()
        code = f"FG-{suffix}"
        if code not in occupied:
            occupied.add(code)
            return code
        nonce += 1


def _create_assignment_table() -> None:
    op.create_table(
        "patient_clinician_assignments_v2",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_membership_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("ended_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("care_role", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "care_role IN ('primary', 'supporting')",
            name="ck_patient_clinician_assignments_care_role",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_patient_clinician_assignments_valid_interval",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_patient_clinician_assignments_version",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_patient_assignments_patient_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["clinician_membership_id", "organization_id", "clinician_user_id"],
            [
                "organization_memberships.id",
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_patient_assignments_clinician_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clinician_user_id"],
            ["users.id"],
            name="fk_patient_assignments_clinician_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name="fk_patient_assignments_assigned_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_user_id"],
            ["users.id"],
            name="fk_patient_assignments_ended_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    connection = op.get_bind()

    # Validate legacy business invariants before the first DDL statement.
    # SQLite DDL is not fully transactional, so a late application-level
    # failure could otherwise leave a half-upgraded database at revision 0013.
    invalid_assignments = connection.execute(
        sa.text(
            "SELECT a.id "
            "FROM patient_clinician_assignments AS a "
            "LEFT JOIN users AS u ON u.id = a.clinician_user_id "
            "WHERE u.id IS NULL OR u.role <> 'clinician'"
        )
    ).fetchall()
    if invalid_assignments:
        invalid_ids = ", ".join(str(row[0]) for row in invalid_assignments)
        raise RuntimeError(
            "Cannot migrate assignments owned by a missing or non-clinician identity. "
            f"Resolve assignment(s): {invalid_ids}"
        )

    if connection.dialect.name == "sqlite":
        foreign_key_violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise RuntimeError(
                "Cannot migrate a SQLite database with foreign-key violations. "
                "Repair the records reported by PRAGMA foreign_key_check first."
            )

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    connection.execute(
        sa.text(
            "INSERT INTO organizations (id, slug, name, is_active, created_at) "
            "VALUES (:id, :slug, :name, :is_active, CURRENT_TIMESTAMP)"
        ),
        {
            "id": DEFAULT_ORGANIZATION_ID,
            "slug": DEFAULT_ORGANIZATION_SLUG,
            "name": DEFAULT_ORGANIZATION_NAME,
            "is_active": True,
        },
    )

    with op.batch_alter_table("patients") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("patient_code", sa.String(length=15), nullable=True))

    connection.execute(
        sa.text("UPDATE patients SET organization_id = :organization_id WHERE organization_id IS NULL"),
        {"organization_id": DEFAULT_ORGANIZATION_ID},
    )
    occupied_codes: set[str] = set()
    patient_rows = connection.execute(sa.text("SELECT id FROM patients ORDER BY id")).fetchall()
    for row in patient_rows:
        patient_id = str(row[0])
        connection.execute(
            sa.text("UPDATE patients SET patient_code = :code WHERE id = :patient_id"),
            {"code": _patient_code(patient_id, occupied_codes), "patient_id": patient_id},
        )

    with op.batch_alter_table("patients") as batch_op:
        batch_op.alter_column(
            "organization_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
        batch_op.alter_column(
            "patient_code",
            existing_type=sa.String(length=15),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_patients_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_patients_identity_scope",
            ["id", "organization_id"],
        )
        batch_op.create_index("ix_patients_organization_id", ["organization_id"], unique=False)
        batch_op.create_index("ix_patients_patient_code", ["patient_code"], unique=True)

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("granted_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_user_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "role IN ('clinician', 'supervisor', 'org_admin', 'auditor')",
            name="ck_organization_memberships_role",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= created_at",
            name="ck_organization_memberships_valid_interval",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_memberships_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_organization_memberships_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="fk_organization_memberships_granted_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_user_id"],
            ["users.id"],
            name="fk_organization_memberships_ended_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "user_id",
            name="uq_organization_memberships_identity_scope",
        ),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_memberships_user_id",
        "organization_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_memberships_org_role_active",
        "organization_memberships",
        ["organization_id", "role", "ended_at"],
        unique=False,
    )
    op.create_index(
        "uq_organization_memberships_active_user_org",
        "organization_memberships",
        ["user_id", "organization_id"],
        unique=True,
        sqlite_where=sa.text("ended_at IS NULL"),
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    membership_by_user: dict[str, str] = {}
    staff_rows = connection.execute(
        sa.text("SELECT id, role, created_at FROM users WHERE role IN ('clinician', 'admin')")
    ).fetchall()
    for user_id_raw, role, created_at in staff_rows:
        user_id = str(user_id_raw)
        membership_id = str(uuid.uuid4())
        membership_by_user[user_id] = membership_id
        connection.execute(
            sa.text(
                "INSERT INTO organization_memberships "
                "(id, organization_id, user_id, role, created_at) "
                "VALUES (:id, :organization_id, :user_id, :role, :created_at)"
            ),
            {
                "id": membership_id,
                "organization_id": DEFAULT_ORGANIZATION_ID,
                "user_id": user_id,
                "role": "org_admin" if role == "admin" else "clinician",
                "created_at": created_at,
            },
        )

    assignment_rows = connection.execute(
        sa.text(
            "SELECT id, patient_id, clinician_user_id, assigned_by_user_id, created_at "
            "FROM patient_clinician_assignments "
            "ORDER BY patient_id, created_at, id"
        )
    ).fetchall()
    _create_assignment_table()
    primary_patient_ids: set[str] = set()
    for assignment_id, patient_id, clinician_user_id_raw, assigned_by_user_id, created_at in assignment_rows:
        clinician_user_id = str(clinician_user_id_raw)
        membership_id = membership_by_user.get(clinician_user_id)
        if membership_id is None:
            raise RuntimeError(
                "Cannot migrate patient assignment because its clinician has no staff membership: "
                f"{clinician_user_id}"
            )
        patient_id_string = str(patient_id)
        care_role = "primary" if patient_id_string not in primary_patient_ids else "supporting"
        primary_patient_ids.add(patient_id_string)
        connection.execute(
            sa.text(
                "INSERT INTO patient_clinician_assignments_v2 "
                "(id, organization_id, patient_id, clinician_membership_id, clinician_user_id, "
                "assigned_by_user_id, care_role, version, starts_at, created_at) "
                "VALUES (:id, :organization_id, :patient_id, :membership_id, :clinician_user_id, "
                ":assigned_by_user_id, :care_role, 1, :starts_at, :created_at)"
            ),
            {
                "id": assignment_id,
                "organization_id": DEFAULT_ORGANIZATION_ID,
                "patient_id": patient_id,
                "membership_id": membership_id,
                "clinician_user_id": clinician_user_id,
                "assigned_by_user_id": assigned_by_user_id,
                "care_role": care_role,
                "starts_at": created_at,
                "created_at": created_at,
            },
        )
    op.drop_table("patient_clinician_assignments")
    op.rename_table("patient_clinician_assignments_v2", "patient_clinician_assignments")
    op.create_index(
        "ix_patient_clinician_assignments_id",
        "patient_clinician_assignments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_patient_id",
        "patient_clinician_assignments",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_clinician_user_id",
        "patient_clinician_assignments",
        ["clinician_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_clinician_membership_id",
        "patient_clinician_assignments",
        ["clinician_membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_organization_id",
        "patient_clinician_assignments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_patient_assignments_active_clinician",
        "patient_clinician_assignments",
        ["patient_id", "clinician_user_id"],
        unique=True,
        sqlite_where=sa.text("ends_at IS NULL"),
        postgresql_where=sa.text("ends_at IS NULL"),
    )
    op.create_index(
        "uq_patient_assignments_active_primary",
        "patient_clinician_assignments",
        ["patient_id"],
        unique=True,
        sqlite_where=sa.text("ends_at IS NULL AND care_role = 'primary'"),
        postgresql_where=sa.text("ends_at IS NULL AND care_role = 'primary'"),
    )
    op.create_index(
        "ix_patient_assignments_clinician_active_patient",
        "patient_clinician_assignments",
        ["clinician_user_id", "ends_at", "patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_assignments_org_active_patient",
        "patient_clinician_assignments",
        ["organization_id", "ends_at", "patient_id"],
        unique=False,
    )

    with op.batch_alter_table("admin_audit_logs") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_admin_audit_logs_organization",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_admin_audit_logs_organization_id", ["organization_id"], unique=False)
    connection.execute(
        sa.text("UPDATE admin_audit_logs SET organization_id = :organization_id"),
        {"organization_id": DEFAULT_ORGANIZATION_ID},
    )

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        )
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("resolved_by_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_notifications_reviewed_by_user",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_notifications_resolved_by_user",
            "users",
            ["resolved_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_notifications_reviewed_by_user_id", ["reviewed_by_user_id"], unique=False)
        batch_op.create_index("ix_notifications_resolved_by_user_id", ["resolved_by_user_id"], unique=False)

    op.create_table(
        "access_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_membership_id", sa.String(length=36), nullable=True),
        sa.Column("patient_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["actor_membership_id"], ["organization_memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_access_audit_events_org_created",
        "access_audit_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_access_audit_events_actor_created",
        "access_audit_events",
        ["actor_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_access_audit_events_patient_created",
        "access_audit_events",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_access_audit_events_request", "access_audit_events", ["request_id"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("notification_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "version", name="uq_alert_events_notification_version"),
    )
    op.create_index("ix_alert_events_notification_id", "alert_events", ["notification_id"], unique=False)
    op.create_index("ix_alert_events_organization_id", "alert_events", ["organization_id"], unique=False)
    op.create_index("ix_alert_events_actor_user_id", "alert_events", ["actor_user_id"], unique=False)
    op.create_index(
        "ix_alert_events_notification_created",
        "alert_events",
        ["notification_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    ended_assignments = connection.execute(
        sa.text(
            "SELECT id FROM patient_clinician_assignments "
            "WHERE ends_at IS NOT NULL LIMIT 1"
        )
    ).fetchone()
    if ended_assignments:
        raise RuntimeError(
            "Downgrade would reactivate ended patient-clinician access. Export and "
            "explicitly reconcile temporal assignments before downgrading."
        )
    duplicate_assignments = connection.execute(
        sa.text(
            "SELECT patient_id, clinician_user_id FROM patient_clinician_assignments "
            "GROUP BY patient_id, clinician_user_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicate_assignments:
        raise RuntimeError(
            "Downgrade would discard temporal assignment history. Export or consolidate "
            "duplicate patient-clinician assignment intervals first."
        )

    access_audit_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM access_audit_events")
    ).scalar_one()
    alert_event_count = connection.execute(sa.text("SELECT COUNT(*) FROM alert_events")).scalar_one()
    if access_audit_count or alert_event_count:
        raise RuntimeError(
            "Downgrade would destroy security or clinical audit history. Export the "
            "append-only audit tables through the approved retention workflow first."
        )

    op.drop_index("ix_alert_events_notification_created", table_name="alert_events")
    op.drop_index("ix_alert_events_actor_user_id", table_name="alert_events")
    op.drop_index("ix_alert_events_organization_id", table_name="alert_events")
    op.drop_index("ix_alert_events_notification_id", table_name="alert_events")
    op.drop_table("alert_events")

    op.drop_index("ix_access_audit_events_request", table_name="access_audit_events")
    op.drop_index("ix_access_audit_events_patient_created", table_name="access_audit_events")
    op.drop_index("ix_access_audit_events_actor_created", table_name="access_audit_events")
    op.drop_index("ix_access_audit_events_org_created", table_name="access_audit_events")
    op.drop_table("access_audit_events")

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_resolved_by_user_id")
        batch_op.drop_index("ix_notifications_reviewed_by_user_id")
        batch_op.drop_constraint("fk_notifications_resolved_by_user", type_="foreignkey")
        batch_op.drop_constraint("fk_notifications_reviewed_by_user", type_="foreignkey")
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("resolved_by_user_id")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("version")

    with op.batch_alter_table("admin_audit_logs") as batch_op:
        batch_op.drop_index("ix_admin_audit_logs_organization_id")
        batch_op.drop_constraint("fk_admin_audit_logs_organization", type_="foreignkey")
        batch_op.drop_column("organization_id")

    op.create_table(
        "patient_clinician_assignments_legacy",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("clinician_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["clinician_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "patient_id", "clinician_user_id", name="uq_patient_clinician_assignment"
        ),
    )
    connection.execute(
        sa.text(
            "INSERT INTO patient_clinician_assignments_legacy "
            "(id, patient_id, clinician_user_id, assigned_by_user_id, created_at) "
            "SELECT id, patient_id, clinician_user_id, assigned_by_user_id, created_at "
            "FROM patient_clinician_assignments"
        )
    )
    op.drop_table("patient_clinician_assignments")
    op.rename_table("patient_clinician_assignments_legacy", "patient_clinician_assignments")
    op.create_index(
        "ix_patient_clinician_assignments_id",
        "patient_clinician_assignments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_patient_id",
        "patient_clinician_assignments",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_clinician_assignments_clinician_user_id",
        "patient_clinician_assignments",
        ["clinician_user_id"],
        unique=False,
    )

    op.drop_index("uq_organization_memberships_active_user_org", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_org_role_active", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_organization_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")

    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_index("ix_patients_patient_code")
        batch_op.drop_index("ix_patients_organization_id")
        batch_op.drop_constraint("uq_patients_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_patients_organization_id", type_="foreignkey")
        batch_op.drop_column("patient_code")
        batch_op.drop_column("organization_id")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
