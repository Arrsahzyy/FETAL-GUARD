"""Add fail-closed hybrid AI model, job, result, and review infrastructure.

Revision ID: 20260811_0017
Revises: 20260809_0016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0017"
down_revision = "20260809_0016"
branch_labels = None
depends_on = None


def _replace_realtime_constraints() -> None:
    with op.batch_alter_table("realtime_events") as batch:
        batch.drop_constraint("ck_realtime_events_type", type_="check")
        batch.drop_constraint("ck_realtime_events_resource_type", type_="check")
        batch.create_check_constraint(
            "ck_realtime_events_type",
            "event_type IN ("
            "'ai.analysis.updated', 'alert.created', 'alert.updated', "
            "'care_assignment.updated', 'device.updated', 'session.completed', "
            "'session.started', 'telemetry.updated')",
        )
        batch.create_check_constraint(
            "ck_realtime_events_resource_type",
            "resource_type IN ('ai_analysis', 'alert', 'care_assignment', 'device', 'session')",
        )


def _enable_postgresql_rls() -> None:
    uid = "NULLIF(current_setting('app.current_user_id', true), '')"
    mid = "NULLIF(current_setting('app.current_membership_id', true), '')"
    oid = "NULLIF(current_setting('app.current_organization_id', true), '')"
    role = "NULLIF(current_setting('app.current_membership_role', true), '')"
    worker = "current_user = 'fetal_guard_ai_worker'"

    for table in (
        "ai_model_versions",
        "ai_inference_jobs",
        "ai_analysis_results",
        "ai_analysis_reviews",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    staff_job = f"""(
      ai_inference_jobs.organization_id = {oid}
      AND (
        {role} = 'supervisor'
        OR (
          {role} = 'clinician'
          AND EXISTS (
            SELECT 1 FROM patient_clinician_assignments a
            WHERE a.patient_id = ai_inference_jobs.patient_id
              AND a.organization_id = ai_inference_jobs.organization_id
              AND a.clinician_membership_id = {mid}
              AND a.clinician_user_id = {uid}
              AND a.starts_at <= CURRENT_TIMESTAMP
              AND a.ends_at IS NULL
          )
        )
      )
    )"""
    patient_job = f"""EXISTS (
      SELECT 1 FROM patients p
      WHERE p.id = ai_inference_jobs.patient_id
        AND p.organization_id = ai_inference_jobs.organization_id
        AND p.user_id = {uid}
    )"""
    patient_result = f"""(
      ai_analysis_results.visibility = 'patient'
      AND EXISTS (
        SELECT 1 FROM patients p
        WHERE p.id = ai_analysis_results.patient_id
          AND p.organization_id = ai_analysis_results.organization_id
          AND p.user_id = {uid}
      )
    )"""
    staff_result = f"""(
      ai_analysis_results.visibility IN ('clinician', 'patient')
      AND ai_analysis_results.organization_id = {oid}
      AND (
        {role} = 'supervisor'
        OR (
          {role} = 'clinician'
          AND EXISTS (
            SELECT 1 FROM patient_clinician_assignments a
            WHERE a.patient_id = ai_analysis_results.patient_id
              AND a.organization_id = ai_analysis_results.organization_id
              AND a.clinician_membership_id = {mid}
              AND a.clinician_user_id = {uid}
              AND a.starts_at <= CURRENT_TIMESTAMP
              AND a.ends_at IS NULL
          )
        )
      )
    )"""
    staff_review = f"""(
      ai_analysis_reviews.organization_id = {oid}
      AND (
        {role} = 'supervisor'
        OR (
          {role} = 'clinician'
          AND EXISTS (
            SELECT 1 FROM patient_clinician_assignments a
            WHERE a.patient_id = ai_analysis_reviews.patient_id
              AND a.organization_id = ai_analysis_reviews.organization_id
              AND a.clinician_membership_id = {mid}
              AND a.clinician_user_id = {uid}
              AND a.starts_at <= CURRENT_TIMESTAMP
              AND a.ends_at IS NULL
          )
        )
      )
    )"""

    statements = (
        f"CREATE POLICY ai_model_versions_runtime_select ON ai_model_versions "
        f"FOR SELECT USING ({uid} IS NOT NULL OR {worker})",
        f"CREATE POLICY ai_jobs_staff_select ON ai_inference_jobs "
        f"FOR SELECT USING ({staff_job})",
        f"CREATE POLICY ai_jobs_patient_select ON ai_inference_jobs "
        f"FOR SELECT USING ({patient_job})",
        f"CREATE POLICY ai_jobs_patient_insert ON ai_inference_jobs "
        f"FOR INSERT WITH CHECK ({patient_job})",
        f"CREATE POLICY ai_jobs_worker_all ON ai_inference_jobs "
        f"FOR ALL USING ({worker}) WITH CHECK ({worker})",
        f"CREATE POLICY ai_results_patient_select ON ai_analysis_results "
        f"FOR SELECT USING ({patient_result})",
        f"CREATE POLICY ai_results_staff_select ON ai_analysis_results "
        f"FOR SELECT USING ({staff_result})",
        f"CREATE POLICY ai_results_worker_all ON ai_analysis_results "
        f"FOR ALL USING ({worker}) WITH CHECK ({worker})",
        f"CREATE POLICY ai_reviews_staff_select ON ai_analysis_reviews "
        f"FOR SELECT USING ({staff_review})",
        f"CREATE POLICY ai_reviews_staff_insert ON ai_analysis_reviews "
        f"FOR INSERT WITH CHECK ({staff_review})",
        f"CREATE POLICY ai_reviews_staff_update ON ai_analysis_reviews "
        f"FOR UPDATE USING ({staff_review}) WITH CHECK ({staff_review})",
        f"CREATE POLICY ai_reviews_worker_select ON ai_analysis_reviews "
        f"FOR SELECT USING ({worker})",
        f"CREATE POLICY session_data_chunks_worker_select ON session_data_chunks "
        f"FOR SELECT USING ({worker})",
        f"CREATE POLICY realtime_event_cursors_worker_all ON realtime_event_cursors "
        f"FOR ALL USING ({worker}) WITH CHECK ({worker})",
        f"CREATE POLICY realtime_events_worker_select ON realtime_events "
        f"FOR SELECT USING ({worker})",
        f"CREATE POLICY realtime_events_worker_insert ON realtime_events "
        f"FOR INSERT WITH CHECK ({worker})",
    )
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    op.create_table(
        "ai_model_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("architecture", sa.String(length=64), nullable=False),
        sa.Column("preprocessing_version", sa.String(length=64), nullable=False),
        sa.Column("input_schema_version", sa.Integer(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_uri", sa.String(length=500), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("deployment_slot", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "validation_status IN ('experimental', 'analytical_validated', "
            "'clinical_validated', 'retired')",
            name="ck_ai_model_versions_validation_status",
        ),
        sa.CheckConstraint(
            "length(artifact_sha256) = 64",
            name="ck_ai_model_versions_artifact_hash",
        ),
        sa.CheckConstraint(
            "input_schema_version > 0",
            name="ck_ai_model_versions_input_schema_version",
        ),
        sa.CheckConstraint(
            "deployment_slot IN ('research', 'shadow', 'clinician', 'patient')",
            name="ck_ai_model_versions_deployment_slot",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_name",
            "version",
            name="uq_ai_model_versions_name_version",
        ),
    )
    op.create_index(
        "uq_ai_model_versions_active_slot",
        "ai_model_versions",
        ["deployment_slot"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "ai_inference_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("model_version_id", sa.String(length=36), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'rejected')",
            name="ck_ai_inference_jobs_status",
        ),
        sa.CheckConstraint("window_ended_at > window_started_at", name="ck_ai_inference_jobs_window"),
        sa.CheckConstraint("attempts >= 0", name="ck_ai_inference_jobs_attempts"),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["ai_model_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_ai_inference_jobs_patient_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_ai_inference_jobs_session_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_ai_inference_jobs_device_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_ai_inference_jobs_identity_scope"),
        sa.UniqueConstraint(
            "session_id",
            "window_started_at",
            "model_version_id",
            name="uq_ai_inference_jobs_window_model",
        ),
    )
    op.create_index(
        "ix_ai_inference_jobs_queue",
        "ai_inference_jobs",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_ai_inference_jobs_patient_window",
        "ai_inference_jobs",
        ["patient_id", "window_started_at"],
    )
    for column in ("organization_id", "patient_id", "session_id", "device_id", "model_version_id"):
        op.create_index(f"ix_ai_inference_jobs_{column}", "ai_inference_jobs", [column])

    op.create_table(
        "ai_analysis_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("model_version_id", sa.String(length=36), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("preprocessing_version", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_status", sa.String(length=16), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("fhr_bpm", sa.Float(), nullable=True),
        sa.Column("maternal_hr_bpm", sa.Float(), nullable=True),
        sa.Column("contraction_probability", sa.Float(), nullable=True),
        sa.Column("screening_status", sa.String(length=32), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quality_status IN ('usable', 'limited', 'unusable')",
            name="ck_ai_analysis_results_quality_status",
        ),
        sa.CheckConstraint(
            "screening_status IN ('routine_monitoring', 'needs_observation', "
            "'review_with_clinician', 'insufficient_signal')",
            name="ck_ai_analysis_results_screening_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('shadow', 'clinician', 'patient')",
            name="ck_ai_analysis_results_visibility",
        ),
        sa.CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="ck_ai_analysis_results_quality_score",
        ),
        sa.CheckConstraint(
            "uncertainty IS NULL OR (uncertainty >= 0 AND uncertainty <= 1)",
            name="ck_ai_analysis_results_uncertainty",
        ),
        sa.CheckConstraint(
            "contraction_probability IS NULL OR "
            "(contraction_probability >= 0 AND contraction_probability <= 1)",
            name="ck_ai_analysis_results_contraction_probability",
        ),
        sa.CheckConstraint("window_ended_at > window_started_at", name="ck_ai_analysis_results_window"),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["ai_model_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_ai_analysis_results_patient_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_ai_analysis_results_session_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_ai_analysis_results_device_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["ai_inference_jobs.id", "ai_inference_jobs.organization_id"],
            name="fk_ai_analysis_results_job_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "patient_id", name="uq_ai_analysis_results_identity_scope"
        ),
        sa.UniqueConstraint("job_id", name="uq_ai_analysis_results_job"),
    )
    op.create_index(
        "ix_ai_analysis_results_patient_created",
        "ai_analysis_results",
        ["patient_id", "created_at"],
    )
    op.create_index(
        "ix_ai_analysis_results_session_window",
        "ai_analysis_results",
        ["session_id", "window_started_at"],
    )
    for column in ("organization_id", "patient_id", "session_id", "device_id", "model_version_id"):
        op.create_index(f"ix_ai_analysis_results_{column}", "ai_analysis_results", [column])

    op.create_table(
        "ai_analysis_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_result_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_membership_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'dismissed', 'needs_followup')",
            name="ck_ai_analysis_reviews_decision",
        ),
        sa.CheckConstraint("version > 0", name="ck_ai_analysis_reviews_version"),
        sa.ForeignKeyConstraint(
            ["analysis_result_id", "organization_id", "patient_id"],
            ["ai_analysis_results.id", "ai_analysis_results.organization_id", "ai_analysis_results.patient_id"],
            name="fk_ai_analysis_reviews_result_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_membership_id", "organization_id", "reviewer_user_id"],
            ["organization_memberships.id", "organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_ai_analysis_reviews_reviewer_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_result_id", name="uq_ai_analysis_reviews_result"),
    )
    op.create_index(
        "ix_ai_analysis_reviews_patient_updated",
        "ai_analysis_reviews",
        ["patient_id", "updated_at"],
    )
    op.create_index("ix_ai_analysis_reviews_organization_id", "ai_analysis_reviews", ["organization_id"])
    op.create_index("ix_ai_analysis_reviews_patient_id", "ai_analysis_reviews", ["patient_id"])

    _replace_realtime_constraints()
    if op.get_bind().dialect.name == "postgresql":
        _enable_postgresql_rls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        policies = (
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
        )
        for table_name, policy_name in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")

    with op.batch_alter_table("realtime_events") as batch:
        batch.drop_constraint("ck_realtime_events_type", type_="check")
        batch.drop_constraint("ck_realtime_events_resource_type", type_="check")
        batch.create_check_constraint(
            "ck_realtime_events_type",
            "event_type IN ('alert.created', 'alert.updated', 'care_assignment.updated', "
            "'device.updated', 'session.completed', 'session.started', 'telemetry.updated')",
        )
        batch.create_check_constraint(
            "ck_realtime_events_resource_type",
            "resource_type IN ('alert', 'care_assignment', 'device', 'session')",
        )

    op.drop_table("ai_analysis_reviews")
    op.drop_table("ai_analysis_results")
    op.drop_table("ai_inference_jobs")
    op.drop_table("ai_model_versions")
