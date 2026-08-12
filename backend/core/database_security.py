from sqlalchemy import text
from sqlalchemy.orm import Session


RLS_PROTECTED_TABLES = frozenset(
    {
        "access_audit_events",
        "admin_audit_logs",
        "ai_analysis_results",
        "ai_analysis_reviews",
        "ai_inference_jobs",
        "ai_model_versions",
        "alert_events",
        "devices",
        "device_assignments",
        "notifications",
        "organization_memberships",
        "patient_clinician_assignments",
        "patients",
        "realtime_event_cursors",
        "realtime_events",
        "session_data_chunks",
        "session_sensor_summaries",
        "sessions",
    }
)

RLS_REQUIRED_POLICIES = frozenset(
    {
        ("ai_model_versions", "ai_model_versions_runtime_select"),
        ("ai_inference_jobs", "ai_jobs_staff_select"),
        ("ai_inference_jobs", "ai_jobs_patient_select"),
        ("ai_inference_jobs", "ai_jobs_patient_insert"),
        ("ai_inference_jobs", "ai_jobs_worker_all"),
        ("ai_analysis_results", "ai_results_patient_select"),
        ("ai_analysis_results", "ai_results_staff_select"),
        ("ai_analysis_results", "ai_results_worker_all"),
        ("ai_analysis_reviews", "ai_reviews_staff_select"),
        ("ai_analysis_reviews", "ai_reviews_staff_insert"),
        ("ai_analysis_reviews", "ai_reviews_staff_update"),
        ("ai_analysis_reviews", "ai_reviews_worker_select"),
        ("session_data_chunks", "session_data_chunks_worker_select"),
        ("realtime_event_cursors", "realtime_event_cursors_worker_all"),
        ("realtime_events", "realtime_events_worker_select"),
        ("realtime_events", "realtime_events_worker_insert"),
        ("organization_memberships", "memberships_self_read"),
        ("organization_memberships", "memberships_facility_read"),
        ("organization_memberships", "memberships_facility_insert"),
        ("organization_memberships", "memberships_facility_update"),
        ("patients", "patients_self_select"),
        ("patients", "patients_self_insert"),
        ("patients", "patients_self_update"),
        ("patients", "patients_staff_select"),
        ("patient_clinician_assignments", "assignments_staff_select"),
        ("patient_clinician_assignments", "assignments_admin_insert"),
        ("patient_clinician_assignments", "assignments_admin_update"),
        ("devices", "devices_patient_select"),
        ("devices", "devices_staff_select"),
        ("devices", "devices_admin_insert"),
        ("devices", "devices_admin_update"),
        ("device_assignments", "device_assignments_patient_select"),
        ("device_assignments", "device_assignments_staff_select"),
        ("device_assignments", "device_assignments_admin_insert"),
        ("device_assignments", "device_assignments_admin_update"),
        ("sessions", "sessions_patient_select"),
        ("sessions", "sessions_patient_insert"),
        ("sessions", "sessions_patient_update"),
        ("sessions", "sessions_staff_select"),
        ("session_data_chunks", "chunks_patient_select"),
        ("session_data_chunks", "chunks_patient_insert"),
        ("session_data_chunks", "chunks_staff_select"),
        ("session_sensor_summaries", "summaries_patient_select"),
        ("session_sensor_summaries", "summaries_patient_insert"),
        ("session_sensor_summaries", "summaries_patient_update"),
        ("session_sensor_summaries", "summaries_staff_select"),
        ("notifications", "notifications_patient_select"),
        ("notifications", "notifications_staff_select"),
        ("notifications", "notifications_staff_update"),
        ("alert_events", "alert_events_staff_select"),
        ("alert_events", "alert_events_staff_insert"),
        ("access_audit_events", "access_audit_actor_insert"),
        ("access_audit_events", "access_audit_privileged_select"),
        ("admin_audit_logs", "admin_audit_admin_insert"),
        ("admin_audit_logs", "admin_audit_privileged_select"),
        ("realtime_event_cursors", "realtime_cursor_actor_select"),
        ("realtime_event_cursors", "realtime_cursor_actor_insert"),
        ("realtime_event_cursors", "realtime_cursor_actor_update"),
        ("realtime_events", "realtime_events_patient_select"),
        ("realtime_events", "realtime_events_staff_select"),
        ("realtime_events", "realtime_events_patient_insert"),
        ("realtime_events", "realtime_events_staff_insert"),
        ("realtime_events", "realtime_events_expired_delete"),
    }
)

RLS_REQUIRED_PRIVILEGES = {
    "ai_model_versions": ("SELECT",),
    "ai_inference_jobs": ("SELECT", "INSERT"),
    "ai_analysis_results": ("SELECT",),
    "ai_analysis_reviews": ("SELECT", "INSERT", "UPDATE"),
    "organization_memberships": ("SELECT", "INSERT", "UPDATE"),
    "patients": ("SELECT", "INSERT", "UPDATE"),
    "patient_clinician_assignments": ("SELECT", "INSERT", "UPDATE"),
    "devices": ("SELECT", "INSERT", "UPDATE"),
    "device_assignments": ("SELECT", "INSERT", "UPDATE"),
    "sessions": ("SELECT", "INSERT", "UPDATE"),
    "session_data_chunks": ("SELECT", "INSERT"),
    "session_sensor_summaries": ("SELECT", "INSERT", "UPDATE"),
    "notifications": ("SELECT", "UPDATE"),
    "alert_events": ("SELECT", "INSERT"),
    "access_audit_events": ("SELECT", "INSERT"),
    "admin_audit_logs": ("SELECT", "INSERT"),
    "realtime_event_cursors": ("SELECT", "INSERT", "UPDATE"),
    "realtime_events": ("SELECT", "INSERT"),
}

RLS_FORBIDDEN_API_PRIVILEGES = {
    "ai_inference_jobs": ("UPDATE",),
    "ai_analysis_results": ("INSERT", "UPDATE"),
}


def assert_postgresql_runtime_isolation(db: Session) -> None:
    """Fail readiness when the runtime role could bypass tenant RLS.

    Migrations must run with a separate owner role. The API role must be a
    non-owner with NOBYPASSRLS; otherwise PostgreSQL silently bypasses enabled
    policies and application-level scoping becomes the only barrier.
    """

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return

    role_row = db.execute(
        text(
            "SELECT current_user AS role_name, rolbypassrls, rolsuper "
            "FROM pg_roles WHERE rolname = current_user"
        )
    ).mappings().one()
    if role_row["rolbypassrls"] or role_row["rolsuper"]:
        raise RuntimeError("The API database role must be NOSUPERUSER and NOBYPASSRLS")

    table_rows = db.execute(
        text(
            "SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled, "
            "pg_get_userbyid(c.relowner) = current_user AS runtime_is_owner, "
            "has_table_privilege(current_user, c.oid, 'SELECT') AS can_select, "
            "has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert, "
            "has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update "
            "FROM pg_class AS c "
            "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relkind = 'r' "
            "AND c.relname = ANY(:table_names)"
        ),
        {"table_names": sorted(RLS_PROTECTED_TABLES)},
    ).mappings().all()
    by_name = {row["table_name"]: row for row in table_rows}
    missing = sorted(RLS_PROTECTED_TABLES - set(by_name))
    disabled = sorted(name for name, row in by_name.items() if not row["rls_enabled"])
    owned = sorted(name for name, row in by_name.items() if row["runtime_is_owner"])
    policy_rows = db.execute(
        text(
            "SELECT tablename AS table_name, policyname AS policy_name "
            "FROM pg_policies WHERE schemaname = current_schema() "
            "AND tablename = ANY(:table_names)"
        ),
        {"table_names": sorted(RLS_PROTECTED_TABLES)},
    ).mappings().all()
    existing_policies = {
        (row["table_name"], row["policy_name"])
        for row in policy_rows
    }
    missing_policies = sorted(RLS_REQUIRED_POLICIES - existing_policies)

    privilege_columns = {
        "SELECT": "can_select",
        "INSERT": "can_insert",
        "UPDATE": "can_update",
    }
    missing_privileges = []
    for table_name, privileges in RLS_REQUIRED_PRIVILEGES.items():
        table_row = by_name.get(table_name)
        if table_row is None:
            continue
        for privilege in privileges:
            if not table_row[privilege_columns[privilege]]:
                missing_privileges.append(f"{table_name}:{privilege}")
    excessive_privileges = []
    for table_name, privileges in RLS_FORBIDDEN_API_PRIVILEGES.items():
        table_row = by_name.get(table_name)
        if table_row is None:
            continue
        for privilege in privileges:
            if table_row[privilege_columns[privilege]]:
                excessive_privileges.append(f"{table_name}:{privilege}")

    if (
        missing
        or disabled
        or owned
        or missing_policies
        or missing_privileges
        or excessive_privileges
    ):
        failures = []
        if missing:
            failures.append(f"missing tables: {', '.join(missing)}")
        if disabled:
            failures.append(f"RLS disabled: {', '.join(disabled)}")
        if owned:
            failures.append(f"runtime role owns tables: {', '.join(owned)}")
        if missing_policies:
            failures.append(
                "missing policies: "
                + ", ".join(f"{table}.{policy}" for table, policy in missing_policies)
            )
        if missing_privileges:
            failures.append(
                "missing privileges: " + ", ".join(missing_privileges)
            )
        if excessive_privileges:
            failures.append(
                "excessive API privileges: " + ", ".join(excessive_privileges)
            )
        raise RuntimeError("Unsafe PostgreSQL tenant isolation (" + "; ".join(failures) + ")")
