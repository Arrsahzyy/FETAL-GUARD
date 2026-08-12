"""Scope device/session data and enable PostgreSQL row-level security.

Revision ID: 20260809_0015
Revises: 20260809_0014
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import groupby
import uuid

from alembic import context, op
import sqlalchemy as sa


revision = "20260809_0015"
down_revision = "20260809_0014"
branch_labels = None
depends_on = None


DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def _aware(value: datetime | str) -> datetime:
    """Normalize timestamps returned by both PostgreSQL and SQLite drivers."""

    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _iter_device_session_histories(connection):
    statement = sa.text(
            "SELECT s.id, s.device_id, s.patient_id, s.status, s.start_time, s.end_time, "
            "p.organization_id AS patient_organization_id, "
            "d.patient_id AS current_patient_id, d.status AS device_status, "
            "d.assigned_at, d.registered_at, "
            "current_patient.organization_id AS current_patient_organization_id "
            "FROM sessions AS s "
            "JOIN patients AS p ON p.id = s.patient_id "
            "JOIN devices AS d ON d.id = s.device_id "
            "LEFT JOIN patients AS current_patient ON current_patient.id = d.patient_id "
            "WHERE s.device_id IS NOT NULL "
            "ORDER BY s.device_id, s.start_time, s.id"
        ).execution_options(stream_results=True)
    rows = connection.execute(statement).mappings()
    for device_id, grouped_rows in groupby(rows, key=lambda row: str(row["device_id"])):
        # Only one device history is retained at a time. Large hospitals can
        # therefore run the preflight without loading every historical session
        # into application memory.
        yield device_id, [dict(row) for row in grouped_rows]


def _validate_device_session_history(connection) -> None:
    """Reject legacy provenance that cannot be reconstructed without guessing."""

    invalid_intervals: list[str] = []
    overlapping_sessions: list[str] = []
    cross_facility_devices: list[str] = []
    invalid_current_assignments: list[str] = []

    for device_id, rows in _iter_device_session_histories(connection):
        patient_organizations = {
            str(row["patient_organization_id"])
            for row in rows
            if row["patient_organization_id"] is not None
        }
        current_organization = rows[0]["current_patient_organization_id"]
        if len(patient_organizations) > 1 or (
            current_organization is not None
            and any(str(current_organization) != value for value in patient_organizations)
        ):
            cross_facility_devices.append(device_id)

        previous: dict | None = None
        for row in rows:
            start_time = _aware(row["start_time"])
            end_time = _aware(row["end_time"]) if row["end_time"] is not None else None
            if row["status"] == "active":
                if end_time is not None:
                    invalid_intervals.append(str(row["id"]))
                if row["device_status"] != "active":
                    invalid_current_assignments.append(str(row["id"]))
                if row["current_patient_id"] is None or str(row["current_patient_id"]) != str(
                    row["patient_id"]
                ):
                    invalid_current_assignments.append(str(row["id"]))
            elif end_time is None or end_time <= start_time:
                invalid_intervals.append(str(row["id"]))

            if previous is not None:
                previous_end = (
                    _aware(previous["end_time"])
                    if previous["end_time"] is not None
                    else None
                )
                if previous_end is None or start_time < previous_end:
                    overlapping_sessions.extend((str(previous["id"]), str(row["id"])))
            previous = row

        current_patient_id = rows[0]["current_patient_id"]
        assigned_at_value = rows[0]["assigned_at"]
        registered_at_value = rows[0]["registered_at"]
        assigned_at = _aware(assigned_at_value) if assigned_at_value is not None else None
        registered_at = _aware(registered_at_value)
        if assigned_at is not None and assigned_at < registered_at:
            invalid_current_assignments.append(device_id)

        if current_patient_id is None:
            continue

        current_patient_id = str(current_patient_id)
        if assigned_at is not None:
            for row in rows:
                start_time = _aware(row["start_time"])
                end_time = _aware(row["end_time"]) if row["end_time"] is not None else None
                if start_time < assigned_at:
                    if end_time is None or end_time > assigned_at:
                        invalid_current_assignments.append(str(row["id"]))
                elif str(row["patient_id"]) != current_patient_id:
                    invalid_current_assignments.append(str(row["id"]))
        elif str(rows[-1]["patient_id"]) != current_patient_id:
            # Without an assignment timestamp, a current pointer which does not
            # match the final observed session has no defensible cutover point.
            invalid_current_assignments.append(device_id)

    if invalid_intervals:
        raise RuntimeError(
            "Device session intervals are invalid for assignment-history migration: "
            + ", ".join(sorted(set(invalid_intervals)))
        )
    if overlapping_sessions:
        raise RuntimeError(
            "Overlapping sessions make device assignment history ambiguous: "
            + ", ".join(sorted(set(overlapping_sessions)))
        )
    if cross_facility_devices:
        raise RuntimeError(
            "A physical device cannot be assigned across facilities without an explicit "
            "transfer record: "
            + ", ".join(sorted(set(cross_facility_devices)))
        )
    if invalid_current_assignments:
        raise RuntimeError(
            "Current device ownership conflicts with session history or its assignment "
            "timestamp: "
            + ", ".join(sorted(set(invalid_current_assignments)))
        )


def _preflight(connection) -> None:
    _validate_device_session_history(connection)

    invalid_device_assignment_cache = connection.execute(
        sa.text(
            "SELECT id FROM devices WHERE "
            "(patient_id IS NULL AND assigned_at IS NOT NULL) "
            "OR (assigned_at IS NOT NULL AND assigned_at < registered_at) LIMIT 1"
        )
    ).fetchone()
    if invalid_device_assignment_cache:
        raise RuntimeError(
            "Device patient/assigned_at cache is inconsistent and must be reconciled "
            "before assignment history is created"
        )

    organization_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM organizations")
    ).scalar_one()
    if organization_count > 1:
        ambiguous_orphan_devices = connection.execute(
            sa.text(
                "SELECT d.id FROM devices AS d "
                "WHERE d.patient_id IS NULL AND NOT EXISTS ("
                "SELECT 1 FROM sessions AS s WHERE s.device_id = d.id)"
            )
        ).fetchall()
        if ambiguous_orphan_devices:
            device_ids = ", ".join(str(row[0]) for row in ambiguous_orphan_devices)
            raise RuntimeError(
                "Unassigned devices without session provenance cannot be placed into one of "
                f"multiple facilities: {device_ids}"
            )
        ambiguous_audit_events = connection.execute(
            sa.text(
                "SELECT id FROM access_audit_events "
                "WHERE organization_id IS NULL AND actor_membership_id IS NULL "
                "AND patient_id IS NULL LIMIT 1"
            )
        ).fetchone()
        if ambiguous_audit_events:
            raise RuntimeError(
                "Unscoped access audit history cannot be assigned safely in a "
                "multi-facility database"
            )

    mismatched_chunk_devices = connection.execute(
        sa.text(
            "SELECT c.id FROM session_data_chunks AS c "
            "JOIN sessions AS s ON s.id = c.session_id "
            "WHERE c.device_id IS NOT NULL "
            "AND (s.device_id IS NULL OR c.device_id <> s.device_id) LIMIT 1"
        )
    ).fetchone()
    mismatched_summary_devices = connection.execute(
        sa.text(
            "SELECT summary.id FROM session_sensor_summaries AS summary "
            "JOIN sessions AS s ON s.id = summary.session_id "
            "WHERE summary.device_id IS NOT NULL "
            "AND (s.device_id IS NULL OR summary.device_id <> s.device_id) LIMIT 1"
        )
    ).fetchone()
    if mismatched_chunk_devices or mismatched_summary_devices:
        raise RuntimeError(
            "Sensor records reference a device different from their monitoring session"
        )

    invalid_audit_outcomes = connection.execute(
        sa.text(
            "SELECT id FROM access_audit_events "
            "WHERE outcome NOT IN ('success', 'denied', 'error') LIMIT 1"
        )
    ).fetchone()
    if invalid_audit_outcomes:
        raise RuntimeError("Access audit events contain an unsupported outcome value")

    mismatched_audit_scope = connection.execute(
        sa.text(
            "SELECT e.id "
            "FROM access_audit_events AS e "
            "LEFT JOIN organization_memberships AS m ON m.id = e.actor_membership_id "
            "LEFT JOIN patients AS p ON p.id = e.patient_id "
            "WHERE (m.id IS NOT NULL AND ("
            "e.actor_user_id IS NULL OR m.user_id <> e.actor_user_id "
            "OR (e.organization_id IS NOT NULL AND m.organization_id <> e.organization_id))) "
            "OR (p.id IS NOT NULL AND e.organization_id IS NOT NULL "
            "AND p.organization_id <> e.organization_id) "
            "OR (m.id IS NOT NULL AND p.id IS NOT NULL "
            "AND m.organization_id <> p.organization_id) "
            "LIMIT 1"
        )
    ).fetchone()
    if mismatched_audit_scope:
        raise RuntimeError("Access audit history contains cross-organization identifiers")

    mismatched_alert_scope = connection.execute(
        sa.text(
            "SELECT e.id FROM alert_events AS e "
            "JOIN notifications AS n ON n.id = e.notification_id "
            "JOIN sessions AS s ON s.id = n.session_id "
            "JOIN patients AS p ON p.id = s.patient_id "
            "WHERE e.organization_id IS NOT NULL "
            "AND e.organization_id <> p.organization_id LIMIT 1"
        )
    ).fetchone()
    if mismatched_alert_scope:
        raise RuntimeError("Alert event history contains a cross-organization identifier")

    if connection.dialect.name == "sqlite":
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "Cannot migrate a SQLite database with foreign-key violations; "
                "repair PRAGMA foreign_key_check output first"
            )


def _create_device_assignments_table() -> None:
    op.create_table(
        "device_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("ended_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_device_assignments_valid_interval",
        ),
        sa.CheckConstraint(
            "(ends_at IS NULL AND version = 1) OR "
            "(ends_at IS NOT NULL AND version = 2)",
            name="ck_device_assignments_lifecycle_version",
        ),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_device_assignments_device_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_device_assignments_patient_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "patient_id",
            "device_id",
            "organization_id",
            name="uq_device_assignments_session_snapshot",
        ),
    )
    op.create_index("ix_device_assignments_id", "device_assignments", ["id"], unique=False)
    op.create_index(
        "ix_device_assignments_organization_id",
        "device_assignments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_device_assignments_device_id",
        "device_assignments",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_device_assignments_patient_id",
        "device_assignments",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "uq_device_assignments_active_device",
        "device_assignments",
        ["device_id"],
        unique=True,
        sqlite_where=sa.text("ends_at IS NULL"),
        postgresql_where=sa.text("ends_at IS NULL"),
    )
    op.create_index(
        "ix_device_assignments_org_patient_active",
        "device_assignments",
        ["organization_id", "patient_id", "ends_at"],
        unique=False,
    )
    op.create_index(
        "ix_device_assignments_device_started",
        "device_assignments",
        ["device_id", "starts_at"],
        unique=False,
    )


def _backfill_device_assignment_history(connection) -> None:
    devices = sa.table(
        "devices",
        sa.column("id", sa.String(36)),
        sa.column("organization_id", sa.String(36)),
        sa.column("patient_id", sa.String(36)),
        sa.column("registered_at", sa.DateTime(timezone=True)),
        sa.column("assigned_at", sa.DateTime(timezone=True)),
    )
    sessions = sa.table(
        "sessions",
        sa.column("id", sa.String(36)),
        sa.column("organization_id", sa.String(36)),
        sa.column("patient_id", sa.String(36)),
        sa.column("device_id", sa.String(36)),
        sa.column("device_assignment_id", sa.String(36)),
        sa.column("status", sa.String(32)),
        sa.column("start_time", sa.DateTime(timezone=True)),
        sa.column("end_time", sa.DateTime(timezone=True)),
    )
    assignments = sa.table(
        "device_assignments",
        sa.column("id", sa.String(36)),
        sa.column("organization_id", sa.String(36)),
        sa.column("device_id", sa.String(36)),
        sa.column("patient_id", sa.String(36)),
        sa.column("version", sa.Integer()),
        sa.column("starts_at", sa.DateTime(timezone=True)),
        sa.column("ends_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    device_rows = connection.execute(sa.select(devices)).mappings().all()

    def persist_assignment(
        *,
        device_id: str,
        organization_id: str,
        patient_id: str,
        starts_at: datetime,
        ends_at: datetime | None,
        rows: list[dict],
    ) -> None:
        assignment_id = str(uuid.uuid4())
        connection.execute(
            assignments.insert().values(
                id=assignment_id,
                organization_id=organization_id,
                device_id=device_id,
                patient_id=patient_id,
                version=1 if ends_at is None else 2,
                starts_at=starts_at,
                ends_at=ends_at,
                created_at=starts_at,
            )
        )
        if rows:
            connection.execute(
                sessions.update()
                .where(sessions.c.id.in_([str(row["id"]) for row in rows]))
                .values(device_assignment_id=assignment_id)
            )

    def persist_historical_runs(
        *,
        device_id: str,
        organization_id: str,
        rows: list[dict],
    ) -> None:
        runs: list[list[dict]] = []
        for row in rows:
            if not runs or str(runs[-1][-1]["patient_id"]) != str(row["patient_id"]):
                runs.append([row])
            else:
                runs[-1].append(row)
        for run in runs:
            end_times = [_aware(row["end_time"]) for row in run if row["end_time"] is not None]
            if len(end_times) != len(run):
                raise RuntimeError(
                    f"Historical device assignment {device_id}/{run[0]['patient_id']} "
                    "has no safe end time"
                )
            persist_assignment(
                device_id=device_id,
                organization_id=organization_id,
                patient_id=str(run[0]["patient_id"]),
                starts_at=_aware(run[0]["start_time"]),
                ends_at=max(end_times),
                rows=run,
            )

    for device in device_rows:
        device_id = str(device["id"])
        organization_id = str(device["organization_id"])
        rows = [
            dict(row)
            for row in connection.execute(
                sa.select(sessions)
                .where(sessions.c.device_id == device_id)
                .order_by(sessions.c.start_time, sessions.c.id)
            ).mappings()
        ]
        current_patient_id = (
            str(device["patient_id"]) if device["patient_id"] is not None else None
        )
        if current_patient_id is None:
            persist_historical_runs(
                device_id=device_id,
                organization_id=organization_id,
                rows=rows,
            )
            continue

        assigned_at = (
            _aware(device["assigned_at"]) if device["assigned_at"] is not None else None
        )
        if assigned_at is not None:
            historical_rows = [row for row in rows if _aware(row["start_time"]) < assigned_at]
            current_rows = [row for row in rows if _aware(row["start_time"]) >= assigned_at]
            current_starts_at = assigned_at
        elif rows:
            final_run_start = len(rows) - 1
            while (
                final_run_start > 0
                and str(rows[final_run_start - 1]["patient_id"]) == current_patient_id
            ):
                final_run_start -= 1
            historical_rows = rows[:final_run_start]
            current_rows = rows[final_run_start:]
            current_starts_at = _aware(current_rows[0]["start_time"])
        else:
            historical_rows = []
            current_rows = []
            current_starts_at = _aware(device["registered_at"])

        persist_historical_runs(
            device_id=device_id,
            organization_id=organization_id,
            rows=historical_rows,
        )
        persist_assignment(
            device_id=device_id,
            organization_id=organization_id,
            patient_id=current_patient_id,
            starts_at=current_starts_at,
            ends_at=None,
            rows=current_rows,
        )


def _create_postgresql_integrity_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fetal_guard_reject_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'FETAL-GUARD audit history is append-only';
        END;
        $$
        """
    )
    for table_name in ("access_audit_events", "alert_events"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION fetal_guard_reject_audit_mutation()"
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fetal_guard_guard_device_assignment_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Device assignment history cannot be deleted';
          END IF;
          IF TG_OP = 'UPDATE' THEN
            IF OLD.ends_at IS NOT NULL
               OR NEW.ends_at IS NULL
               OR OLD.version <> 1
               OR NEW.version <> 2
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
               OR NEW.device_id IS DISTINCT FROM OLD.device_id
               OR NEW.patient_id IS DISTINCT FROM OLD.patient_id
               OR NEW.assigned_by_user_id IS DISTINCT FROM OLD.assigned_by_user_id
               OR NEW.starts_at IS DISTINCT FROM OLD.starts_at
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
              RAISE EXCEPTION 'Invalid device assignment history mutation';
            END IF;
          END IF;
          IF EXISTS (
            SELECT 1 FROM device_assignments existing
            WHERE existing.device_id = NEW.device_id
              AND existing.id <> NEW.id
              AND tstzrange(existing.starts_at, existing.ends_at, '[)')
                  && tstzrange(NEW.starts_at, NEW.ends_at, '[)')
          ) THEN
            RAISE EXCEPTION 'Overlapping device assignment history is not permitted';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_device_assignments_history_guard
        BEFORE INSERT OR UPDATE OR DELETE ON device_assignments
        FOR EACH ROW EXECUTE FUNCTION fetal_guard_guard_device_assignment_history()
        """
    )


def _enable_postgresql_rls() -> None:
    uid = "NULLIF(current_setting('app.current_user_id', true), '')"
    mid = "NULLIF(current_setting('app.current_membership_id', true), '')"
    oid = "NULLIF(current_setting('app.current_organization_id', true), '')"
    role = "NULLIF(current_setting('app.current_membership_role', true), '')"

    protected_tables = (
        "organization_memberships",
        "patients",
        "patient_clinician_assignments",
        "devices",
        "device_assignments",
        "sessions",
        "session_data_chunks",
        "session_sensor_summaries",
        "notifications",
        "alert_events",
        "access_audit_events",
        "admin_audit_logs",
    )
    for table_name in protected_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

    statements = [
        f"""CREATE POLICY memberships_self_read ON organization_memberships FOR SELECT
        USING (user_id = {uid})""",
        f"""CREATE POLICY memberships_facility_read ON organization_memberships FOR SELECT
        USING (organization_id = {oid} AND {role} IN ('org_admin', 'auditor'))""",
        f"""CREATE POLICY memberships_facility_insert ON organization_memberships FOR INSERT
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY memberships_facility_update ON organization_memberships FOR UPDATE
        USING (organization_id = {oid} AND {role} = 'org_admin')
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY patients_self_select ON patients FOR SELECT USING (user_id = {uid})""",
        f"""CREATE POLICY patients_self_insert ON patients FOR INSERT WITH CHECK (user_id = {uid})""",
        f"""CREATE POLICY patients_self_update ON patients FOR UPDATE
        USING (user_id = {uid}) WITH CHECK (user_id = {uid})""",
        f"""CREATE POLICY patients_staff_select ON patients FOR SELECT USING (
          organization_id = {oid} AND (
            {role} IN ('supervisor', 'org_admin') OR
            ({role} = 'clinician' AND EXISTS (
              SELECT 1 FROM patient_clinician_assignments a
              WHERE a.patient_id = patients.id
                AND a.organization_id = patients.organization_id
                AND a.clinician_membership_id = {mid}
                AND a.clinician_user_id = {uid}
                AND a.ends_at IS NULL
                AND a.starts_at <= CURRENT_TIMESTAMP
            ))
          ))""",
        f"""CREATE POLICY assignments_staff_select ON patient_clinician_assignments FOR SELECT
        USING (organization_id = {oid} AND (
          {role} IN ('supervisor', 'org_admin') OR
          ({role} = 'clinician' AND clinician_membership_id = {mid} AND clinician_user_id = {uid})
        ))""",
        f"""CREATE POLICY assignments_admin_insert ON patient_clinician_assignments FOR INSERT
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY assignments_admin_update ON patient_clinician_assignments FOR UPDATE
        USING (organization_id = {oid} AND {role} = 'org_admin')
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY devices_patient_select ON devices FOR SELECT USING (EXISTS (
          SELECT 1 FROM patients p WHERE p.id = devices.patient_id AND p.user_id = {uid}
        ))""",
        f"""CREATE POLICY devices_staff_select ON devices FOR SELECT USING (
          organization_id = {oid} AND (
            {role} IN ('supervisor', 'org_admin') OR
            ({role} = 'clinician' AND EXISTS (
              SELECT 1 FROM patients p WHERE p.id = devices.patient_id
            ))
          ))""",
        f"""CREATE POLICY devices_admin_insert ON devices FOR INSERT
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY devices_admin_update ON devices FOR UPDATE
        USING (organization_id = {oid} AND {role} = 'org_admin')
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY device_assignments_patient_select ON device_assignments FOR SELECT
        USING (EXISTS (SELECT 1 FROM patients p
          WHERE p.id = device_assignments.patient_id AND p.user_id = {uid}))""",
        f"""CREATE POLICY device_assignments_staff_select ON device_assignments FOR SELECT
        USING (organization_id = {oid} AND (
          {role} IN ('supervisor', 'org_admin') OR
          ({role} = 'clinician' AND EXISTS (
            SELECT 1 FROM patients p WHERE p.id = device_assignments.patient_id
          ))
        ))""",
        f"""CREATE POLICY device_assignments_admin_insert ON device_assignments FOR INSERT
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY device_assignments_admin_update ON device_assignments FOR UPDATE
        USING (organization_id = {oid} AND {role} = 'org_admin')
        WITH CHECK (organization_id = {oid} AND {role} = 'org_admin')""",
        f"""CREATE POLICY sessions_patient_select ON sessions FOR SELECT USING (EXISTS (
          SELECT 1 FROM patients p WHERE p.id = sessions.patient_id AND p.user_id = {uid}
        ))""",
        f"""CREATE POLICY sessions_patient_insert ON sessions FOR INSERT WITH CHECK (EXISTS (
          SELECT 1 FROM patients p WHERE p.id = sessions.patient_id AND p.user_id = {uid}
        ))""",
        f"""CREATE POLICY sessions_patient_update ON sessions FOR UPDATE
        USING (EXISTS (SELECT 1 FROM patients p WHERE p.id = sessions.patient_id AND p.user_id = {uid}))
        WITH CHECK (EXISTS (SELECT 1 FROM patients p WHERE p.id = sessions.patient_id AND p.user_id = {uid}))""",
        f"""CREATE POLICY sessions_staff_select ON sessions FOR SELECT USING (
          organization_id = {oid} AND EXISTS (SELECT 1 FROM patients p WHERE p.id = sessions.patient_id)
        )""",
        f"""CREATE POLICY chunks_patient_select ON session_data_chunks FOR SELECT USING (EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = session_data_chunks.session_id
        ))""",
        f"""CREATE POLICY chunks_patient_insert ON session_data_chunks FOR INSERT WITH CHECK (EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = session_data_chunks.session_id
        ))""",
        f"""CREATE POLICY chunks_staff_select ON session_data_chunks FOR SELECT USING (
          organization_id = {oid} AND EXISTS (
            SELECT 1 FROM sessions s WHERE s.id = session_data_chunks.session_id
          ))""",
        f"""CREATE POLICY summaries_patient_select ON session_sensor_summaries FOR SELECT USING (EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = session_sensor_summaries.session_id
        ))""",
        f"""CREATE POLICY summaries_patient_insert ON session_sensor_summaries FOR INSERT WITH CHECK (EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = session_sensor_summaries.session_id
        ))""",
        f"""CREATE POLICY summaries_patient_update ON session_sensor_summaries FOR UPDATE
        USING (EXISTS (SELECT 1 FROM sessions s WHERE s.id = session_sensor_summaries.session_id))
        WITH CHECK (EXISTS (SELECT 1 FROM sessions s WHERE s.id = session_sensor_summaries.session_id))""",
        f"""CREATE POLICY summaries_staff_select ON session_sensor_summaries FOR SELECT USING (
          organization_id = {oid} AND EXISTS (
            SELECT 1 FROM sessions s WHERE s.id = session_sensor_summaries.session_id
          ))""",
        f"""CREATE POLICY notifications_patient_select ON notifications FOR SELECT USING (EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = notifications.session_id
        ))""",
        f"""CREATE POLICY notifications_staff_select ON notifications FOR SELECT USING (
          organization_id = {oid} AND EXISTS (
            SELECT 1 FROM sessions s WHERE s.id = notifications.session_id
          ))""",
        f"""CREATE POLICY notifications_staff_update ON notifications FOR UPDATE
        USING (organization_id = {oid} AND {role} IN ('clinician', 'supervisor') AND EXISTS (
          SELECT 1 FROM sessions s WHERE s.id = notifications.session_id
        ))
        WITH CHECK (organization_id = {oid} AND {role} IN ('clinician', 'supervisor'))""",
        f"""CREATE POLICY alert_events_staff_select ON alert_events FOR SELECT USING (
          organization_id = {oid} AND EXISTS (
            SELECT 1 FROM notifications n WHERE n.id = alert_events.notification_id
          ))""",
        f"""CREATE POLICY alert_events_staff_insert ON alert_events FOR INSERT WITH CHECK (
          organization_id = {oid} AND actor_user_id = {uid}
          AND {role} IN ('clinician', 'supervisor')
          AND EXISTS (SELECT 1 FROM notifications n WHERE n.id = alert_events.notification_id)
        )""",
        f"""CREATE POLICY access_audit_actor_insert ON access_audit_events FOR INSERT WITH CHECK (
          organization_id = {oid} AND actor_user_id = {uid}
          AND actor_membership_id = {mid}
        )""",
        f"""CREATE POLICY access_audit_privileged_select ON access_audit_events FOR SELECT USING (
          organization_id = {oid} AND {role} IN ('org_admin', 'auditor')
        )""",
        f"""CREATE POLICY admin_audit_admin_insert ON admin_audit_logs FOR INSERT WITH CHECK (
          organization_id = {oid} AND actor_user_id = {uid} AND {role} = 'org_admin'
        )""",
        f"""CREATE POLICY admin_audit_privileged_select ON admin_audit_logs FOR SELECT USING (
          organization_id = {oid} AND {role} IN ('org_admin', 'auditor')
        )""",
    ]
    for statement in statements:
        op.execute(statement)


def _disable_postgresql_rls() -> None:
    policies = {
        "organization_memberships": (
            "memberships_self_read",
            "memberships_facility_read",
            "memberships_facility_insert",
            "memberships_facility_update",
        ),
        "patients": (
            "patients_self_select",
            "patients_self_insert",
            "patients_self_update",
            "patients_staff_select",
        ),
        "patient_clinician_assignments": (
            "assignments_staff_select",
            "assignments_admin_insert",
            "assignments_admin_update",
        ),
        "devices": (
            "devices_patient_select",
            "devices_staff_select",
            "devices_admin_insert",
            "devices_admin_update",
        ),
        "device_assignments": (
            "device_assignments_patient_select",
            "device_assignments_staff_select",
            "device_assignments_admin_insert",
            "device_assignments_admin_update",
        ),
        "sessions": (
            "sessions_patient_select",
            "sessions_patient_insert",
            "sessions_patient_update",
            "sessions_staff_select",
        ),
        "session_data_chunks": (
            "chunks_patient_select",
            "chunks_patient_insert",
            "chunks_staff_select",
        ),
        "session_sensor_summaries": (
            "summaries_patient_select",
            "summaries_patient_insert",
            "summaries_patient_update",
            "summaries_staff_select",
        ),
        "notifications": (
            "notifications_patient_select",
            "notifications_staff_select",
            "notifications_staff_update",
        ),
        "alert_events": ("alert_events_staff_select", "alert_events_staff_insert"),
        "access_audit_events": ("access_audit_actor_insert", "access_audit_privileged_select"),
        "admin_audit_logs": ("admin_audit_admin_insert", "admin_audit_privileged_select"),
    }
    for table_name, table_policies in policies.items():
        for policy_name in table_policies:
            op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Revision 20260809_0015 requires an online database connection because it "
            "validates and reconstructs legacy device-assignment history before DDL"
        )

    connection = op.get_bind()
    _preflight(connection)

    op.add_column("devices", sa.Column("organization_id", sa.String(length=36), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE devices SET organization_id = COALESCE(("
            "SELECT p.organization_id FROM patients AS p WHERE p.id = devices.patient_id"
            "), (SELECT p.organization_id FROM sessions AS s "
            "JOIN patients AS p ON p.id = s.patient_id "
            "WHERE s.device_id = devices.id ORDER BY s.start_time, s.id LIMIT 1), "
            ":default_org)"
        ),
        {"default_org": DEFAULT_ORGANIZATION_ID},
    )
    with op.batch_alter_table("devices") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            "fk_devices_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_devices_patient_scope",
            "patients",
            ["patient_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint("uq_devices_identity_scope", ["id", "organization_id"])
        batch_op.create_index("ix_devices_organization_id", ["organization_id"], unique=False)

    _create_device_assignments_table()

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("device_assignment_id", sa.String(length=36), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE sessions SET organization_id = ("
            "SELECT p.organization_id FROM patients AS p WHERE p.id = sessions.patient_id)"
        )
    )
    _backfill_device_assignment_history(connection)
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_check_constraint(
            "ck_sessions_device_assignment_binding",
            "(device_id IS NULL AND device_assignment_id IS NULL) OR "
            "(device_id IS NOT NULL AND device_assignment_id IS NOT NULL)",
        )
        batch_op.create_foreign_key(
            "fk_sessions_patient_scope",
            "patients",
            ["patient_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_sessions_device_scope",
            "devices",
            ["device_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_sessions_device_assignment_snapshot",
            "device_assignments",
            ["device_assignment_id", "patient_id", "device_id", "organization_id"],
            ["id", "patient_id", "device_id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint("uq_sessions_identity_scope", ["id", "organization_id"])
        batch_op.create_index("ix_sessions_organization_id", ["organization_id"], unique=False)
        batch_op.create_index("ix_sessions_device_assignment_id", ["device_assignment_id"], unique=False)

    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE session_data_chunks SET organization_id = ("
            "SELECT s.organization_id FROM sessions AS s WHERE s.id = session_data_chunks.session_id)"
        )
    )
    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            "fk_session_data_chunks_session_scope",
            "sessions",
            ["session_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_session_data_chunks_device_scope",
            "devices",
            ["device_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_session_data_chunks_identity_scope", ["id", "organization_id"]
        )
        batch_op.create_index("ix_session_data_chunks_organization_id", ["organization_id"], unique=False)

    with op.batch_alter_table("session_sensor_summaries") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE session_sensor_summaries SET organization_id = ("
            "SELECT s.organization_id FROM sessions AS s "
            "WHERE s.id = session_sensor_summaries.session_id)"
        )
    )
    with op.batch_alter_table("session_sensor_summaries") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            "fk_session_sensor_summaries_session_scope",
            "sessions",
            ["session_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_session_sensor_summaries_device_scope",
            "devices",
            ["device_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_session_sensor_summaries_identity_scope", ["id", "organization_id"]
        )
        batch_op.create_index(
            "ix_session_sensor_summaries_organization_id", ["organization_id"], unique=False
        )

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE notifications SET organization_id = ("
            "SELECT s.organization_id FROM sessions AS s WHERE s.id = notifications.session_id)"
        )
    )
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            "fk_notifications_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_notifications_session_scope",
            "sessions",
            ["session_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint("uq_notifications_identity_scope", ["id", "organization_id"])
        batch_op.create_index("ix_notifications_organization_id", ["organization_id"], unique=False)

    connection.execute(
        sa.text(
            "UPDATE alert_events SET organization_id = ("
            "SELECT n.organization_id FROM notifications AS n "
            "WHERE n.id = alert_events.notification_id)"
        )
    )
    with op.batch_alter_table("alert_events") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            "fk_alert_events_notification_scope",
            "notifications",
            ["notification_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )

    connection.execute(
        sa.text(
            "UPDATE access_audit_events SET organization_id = COALESCE("
            "access_audit_events.organization_id, "
            "(SELECT m.organization_id FROM organization_memberships AS m "
            " WHERE m.id = access_audit_events.actor_membership_id), "
            "(SELECT p.organization_id FROM patients AS p "
            " WHERE p.id = access_audit_events.patient_id), "
            ":default_org)"
        ),
        {"default_org": DEFAULT_ORGANIZATION_ID},
    )
    with op.batch_alter_table("access_audit_events") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_check_constraint(
            "ck_access_audit_events_outcome",
            "outcome IN ('success', 'denied', 'error')",
        )
        batch_op.create_foreign_key(
            "fk_access_audit_events_actor_scope",
            "organization_memberships",
            ["actor_membership_id", "organization_id", "actor_user_id"],
            ["id", "organization_id", "user_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_access_audit_events_patient_scope",
            "patients",
            ["patient_id", "organization_id"],
            ["id", "organization_id"],
            ondelete="RESTRICT",
        )

    notification_rows = connection.execute(
        sa.text(
            "SELECT n.id, n.organization_id, n.status, n.version, n.created_at, n.updated_at, "
            "n.acknowledged_at, n.acknowledged_by_user_id, n.reviewed_at, n.reviewed_by_user_id, "
            "n.resolved_at, n.resolved_by_user_id "
            "FROM notifications AS n "
            "WHERE n.status <> 'open' AND NOT EXISTS ("
            "SELECT 1 FROM alert_events AS e WHERE e.notification_id = n.id)"
        )
    ).mappings().all()
    for notification in notification_rows:
        actor_user_id = (
            notification["resolved_by_user_id"]
            or notification["reviewed_by_user_id"]
            or notification["acknowledged_by_user_id"]
        )
        event_time = (
            notification["resolved_at"]
            or notification["reviewed_at"]
            or notification["acknowledged_at"]
            or notification["updated_at"]
            or notification["created_at"]
        )
        connection.execute(
            sa.text(
                "INSERT INTO alert_events "
                "(id, notification_id, organization_id, actor_user_id, from_status, to_status, "
                "version, created_at) VALUES "
                "(:id, :notification_id, :organization_id, :actor_user_id, NULL, :to_status, "
                ":version, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "notification_id": notification["id"],
                "organization_id": notification["organization_id"],
                "actor_user_id": actor_user_id,
                "to_status": notification["status"],
                "version": notification["version"],
                "created_at": event_time,
            },
        )

    if connection.dialect.name == "postgresql":
        _create_postgresql_integrity_triggers()
        _enable_postgresql_rls()


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Revision 20260809_0015 downgrade requires an online database connection to "
            "verify that no immutable device-assignment history would be destroyed"
        )

    connection = op.get_bind()
    assignment_count = connection.execute(sa.text("SELECT COUNT(*) FROM device_assignments")).scalar_one()
    if assignment_count:
        raise RuntimeError(
            "Downgrade would destroy immutable device assignment history. Export and reconcile "
            "device/session provenance before downgrading."
        )

    if connection.dialect.name == "postgresql":
        _disable_postgresql_rls()
        op.execute("DROP TRIGGER IF EXISTS trg_device_assignments_history_guard ON device_assignments")
        op.execute("DROP FUNCTION IF EXISTS fetal_guard_guard_device_assignment_history()")
        op.execute("DROP TRIGGER IF EXISTS trg_alert_events_append_only ON alert_events")
        op.execute("DROP TRIGGER IF EXISTS trg_access_audit_events_append_only ON access_audit_events")
        op.execute("DROP FUNCTION IF EXISTS fetal_guard_reject_audit_mutation()")

    with op.batch_alter_table("access_audit_events") as batch_op:
        batch_op.drop_constraint("fk_access_audit_events_patient_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_access_audit_events_actor_scope", type_="foreignkey")
        batch_op.drop_constraint("ck_access_audit_events_outcome", type_="check")
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=True)

    with op.batch_alter_table("alert_events") as batch_op:
        batch_op.drop_constraint("fk_alert_events_notification_scope", type_="foreignkey")
        batch_op.alter_column("organization_id", existing_type=sa.String(length=36), nullable=True)

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_organization_id")
        batch_op.drop_constraint("uq_notifications_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_notifications_session_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_notifications_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("session_sensor_summaries") as batch_op:
        batch_op.drop_index("ix_session_sensor_summaries_organization_id")
        batch_op.drop_constraint("uq_session_sensor_summaries_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_session_sensor_summaries_device_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_session_sensor_summaries_session_scope", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("session_data_chunks") as batch_op:
        batch_op.drop_index("ix_session_data_chunks_organization_id")
        batch_op.drop_constraint("uq_session_data_chunks_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_session_data_chunks_device_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_session_data_chunks_session_scope", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_device_assignment_id")
        batch_op.drop_index("ix_sessions_organization_id")
        batch_op.drop_constraint("uq_sessions_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_sessions_device_assignment_snapshot", type_="foreignkey")
        batch_op.drop_constraint("fk_sessions_device_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_sessions_patient_scope", type_="foreignkey")
        batch_op.drop_constraint("ck_sessions_device_assignment_binding", type_="check")
        batch_op.drop_column("device_assignment_id")
        batch_op.drop_column("organization_id")

    op.drop_index("ix_device_assignments_device_started", table_name="device_assignments")
    op.drop_index("ix_device_assignments_org_patient_active", table_name="device_assignments")
    op.drop_index("uq_device_assignments_active_device", table_name="device_assignments")
    op.drop_index("ix_device_assignments_patient_id", table_name="device_assignments")
    op.drop_index("ix_device_assignments_device_id", table_name="device_assignments")
    op.drop_index("ix_device_assignments_organization_id", table_name="device_assignments")
    op.drop_index("ix_device_assignments_id", table_name="device_assignments")
    op.drop_table("device_assignments")

    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_index("ix_devices_organization_id")
        batch_op.drop_constraint("uq_devices_identity_scope", type_="unique")
        batch_op.drop_constraint("fk_devices_patient_scope", type_="foreignkey")
        batch_op.drop_constraint("fk_devices_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")
