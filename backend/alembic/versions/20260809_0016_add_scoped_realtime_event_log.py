"""Add the scoped persistent realtime event log.

Revision ID: 20260809_0016
Revises: 20260809_0015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0016"
down_revision = "20260809_0015"
branch_labels = None
depends_on = None


def _create_postgresql_guards_and_rls() -> None:
    uid = "NULLIF(current_setting('app.current_user_id', true), '')"
    mid = "NULLIF(current_setting('app.current_membership_id', true), '')"
    oid = "NULLIF(current_setting('app.current_organization_id', true), '')"
    role = "NULLIF(current_setting('app.current_membership_role', true), '')"

    op.execute(
        """
        CREATE FUNCTION fetal_guard_guard_realtime_event_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE'
             AND OLD.expires_at <= CURRENT_TIMESTAMP
             AND NULLIF(current_setting('app.realtime_retention_purge', true), '') = 'on'
          THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'realtime event history is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_realtime_events_append_only
        BEFORE UPDATE OR DELETE ON realtime_events
        FOR EACH ROW EXECUTE FUNCTION fetal_guard_guard_realtime_event_history()
        """
    )
    op.execute(
        """
        CREATE FUNCTION fetal_guard_guard_realtime_cursor()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' AND NEW.last_cursor <> 1 THEN
            RAISE EXCEPTION 'realtime cursor must start at one';
          END IF;
          IF TG_OP = 'DELETE'
             OR (TG_OP = 'UPDATE' AND NEW.last_cursor <> OLD.last_cursor + 1)
          THEN
            RAISE EXCEPTION 'realtime cursor must advance exactly once';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_realtime_event_cursors_monotonic
        BEFORE INSERT OR UPDATE OR DELETE ON realtime_event_cursors
        FOR EACH ROW EXECUTE FUNCTION fetal_guard_guard_realtime_cursor()
        """
    )

    op.execute("ALTER TABLE realtime_event_cursors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE realtime_events ENABLE ROW LEVEL SECURITY")

    cursor_actor = f"""(
      (organization_id = {oid} AND {role} IN ('clinician', 'supervisor', 'org_admin'))
      OR EXISTS (
        SELECT 1 FROM patients p
        WHERE p.organization_id = realtime_event_cursors.organization_id
          AND p.user_id = {uid}
      )
    )"""
    event_patient = f"""EXISTS (
      SELECT 1 FROM patients p
      WHERE p.id = realtime_events.patient_id
        AND p.organization_id = realtime_events.organization_id
        AND p.user_id = {uid}
    )"""
    event_staff = f"""(
      realtime_events.organization_id = {oid}
      AND (
        {role} IN ('supervisor', 'org_admin')
        OR (
          {role} = 'clinician'
          AND EXISTS (
            SELECT 1 FROM patient_clinician_assignments a
            WHERE a.patient_id = realtime_events.patient_id
              AND a.organization_id = realtime_events.organization_id
              AND a.clinician_membership_id = {mid}
              AND a.clinician_user_id = {uid}
              AND a.starts_at <= CURRENT_TIMESTAMP
              AND a.ends_at IS NULL
          )
        )
      )
    )"""

    statements = (
        f"CREATE POLICY realtime_cursor_actor_select ON realtime_event_cursors "
        f"FOR SELECT USING ({cursor_actor})",
        f"CREATE POLICY realtime_cursor_actor_insert ON realtime_event_cursors "
        f"FOR INSERT WITH CHECK ({cursor_actor})",
        f"CREATE POLICY realtime_cursor_actor_update ON realtime_event_cursors "
        f"FOR UPDATE USING ({cursor_actor}) WITH CHECK ({cursor_actor})",
        f"CREATE POLICY realtime_events_patient_select ON realtime_events "
        f"FOR SELECT USING ({event_patient})",
        f"CREATE POLICY realtime_events_staff_select ON realtime_events "
        f"FOR SELECT USING ({event_staff})",
        f"CREATE POLICY realtime_events_patient_insert ON realtime_events "
        f"FOR INSERT WITH CHECK ({event_patient})",
        f"CREATE POLICY realtime_events_staff_insert ON realtime_events "
        f"FOR INSERT WITH CHECK ({event_staff})",
        "CREATE POLICY realtime_events_expired_delete ON realtime_events "
        "FOR DELETE USING ("
        "expires_at <= CURRENT_TIMESTAMP AND "
        "NULLIF(current_setting('app.realtime_retention_purge', true), '') = 'on'"
        ")",
    )
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    event_cursor_type = (
        sa.Integer()
        if op.get_bind().dialect.name == "sqlite"
        else sa.BigInteger()
    )
    op.create_table(
        "realtime_event_cursors",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("last_cursor", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_cursor >= 0",
            name="ck_realtime_event_cursors_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_realtime_event_cursors_organization_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_table(
        "realtime_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("cursor", event_cursor_type, nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cursor > 0", name="ck_realtime_events_positive_cursor"),
        sa.CheckConstraint(
            "event_type IN ("
            "'alert.created', 'alert.updated', 'care_assignment.updated', "
            "'device.updated', 'session.completed', 'session.started', "
            "'telemetry.updated')",
            name="ck_realtime_events_type",
        ),
        sa.CheckConstraint(
            "resource_type IN ('alert', 'care_assignment', 'device', 'session')",
            name="ck_realtime_events_resource_type",
        ),
        sa.CheckConstraint(
            "expires_at > occurred_at",
            name="ck_realtime_events_retention_window",
        ),
        sa.CheckConstraint(
            "length(CAST(payload AS TEXT)) <= 4096",
            name="ck_realtime_events_payload_size",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_realtime_events_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_realtime_events_patient_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "cursor",
            name="uq_realtime_events_org_cursor",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_realtime_events_org_idempotency",
        ),
    )
    op.create_index(
        "ix_realtime_events_org_cursor",
        "realtime_events",
        ["organization_id", "cursor"],
    )
    op.create_index(
        "ix_realtime_events_patient_cursor",
        "realtime_events",
        ["patient_id", "cursor"],
    )
    op.create_index(
        "ix_realtime_events_expiry_cursor",
        "realtime_events",
        ["expires_at", "cursor"],
    )

    if op.get_bind().dialect.name == "postgresql":
        _create_postgresql_guards_and_rls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        policies = (
            ("realtime_event_cursors", "realtime_cursor_actor_select"),
            ("realtime_event_cursors", "realtime_cursor_actor_insert"),
            ("realtime_event_cursors", "realtime_cursor_actor_update"),
            ("realtime_events", "realtime_events_patient_select"),
            ("realtime_events", "realtime_events_staff_select"),
            ("realtime_events", "realtime_events_patient_insert"),
            ("realtime_events", "realtime_events_staff_insert"),
            ("realtime_events", "realtime_events_expired_delete"),
        )
        for table_name, policy_name in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
        op.execute("ALTER TABLE realtime_events DISABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE realtime_event_cursors DISABLE ROW LEVEL SECURITY")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_realtime_events_append_only ON realtime_events"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_realtime_event_cursors_monotonic "
            "ON realtime_event_cursors"
        )
        op.execute("DROP FUNCTION IF EXISTS fetal_guard_guard_realtime_event_history()")
        op.execute("DROP FUNCTION IF EXISTS fetal_guard_guard_realtime_cursor()")

    op.drop_index("ix_realtime_events_expiry_cursor", table_name="realtime_events")
    op.drop_index("ix_realtime_events_patient_cursor", table_name="realtime_events")
    op.drop_index("ix_realtime_events_org_cursor", table_name="realtime_events")
    op.drop_table("realtime_events")
    op.drop_table("realtime_event_cursors")
