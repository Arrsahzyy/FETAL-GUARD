import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)

from db.database import Base


class AIModelVersion(Base):
    __tablename__ = "ai_model_versions"
    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('experimental', 'analytical_validated', 'clinical_validated', 'retired')",
            name="ck_ai_model_versions_validation_status",
        ),
        CheckConstraint(
            "length(artifact_sha256) = 64",
            name="ck_ai_model_versions_artifact_hash",
        ),
        CheckConstraint(
            "input_schema_version > 0",
            name="ck_ai_model_versions_input_schema_version",
        ),
        CheckConstraint(
            "deployment_slot IN ('research', 'shadow', 'clinician', 'patient')",
            name="ck_ai_model_versions_deployment_slot",
        ),
        UniqueConstraint("model_name", "version", name="uq_ai_model_versions_name_version"),
        Index(
            "uq_ai_model_versions_active_slot",
            "deployment_slot",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String(120), nullable=False)
    version = Column(String(64), nullable=False)
    architecture = Column(String(64), nullable=False, default="cnn_lstm_multitask")
    preprocessing_version = Column(String(64), nullable=False)
    input_schema_version = Column(Integer, nullable=False)
    artifact_sha256 = Column(String(64), nullable=False)
    manifest_uri = Column(String(500), nullable=False)
    validation_status = Column(String(32), nullable=False, default="experimental")
    deployment_slot = Column(String(32), nullable=False, default="research")
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    activated_at = Column(DateTime(timezone=True), nullable=True)


class AIInferenceJob(Base):
    __tablename__ = "ai_inference_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'rejected')",
            name="ck_ai_inference_jobs_status",
        ),
        CheckConstraint(
            "window_ended_at > window_started_at",
            name="ck_ai_inference_jobs_window",
        ),
        CheckConstraint("attempts >= 0", name="ck_ai_inference_jobs_attempts"),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_ai_inference_jobs_patient_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_ai_inference_jobs_session_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_ai_inference_jobs_device_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_ai_inference_jobs_identity_scope"),
        UniqueConstraint(
            "session_id",
            "window_started_at",
            "model_version_id",
            name="uq_ai_inference_jobs_window_model",
        ),
        Index("ix_ai_inference_jobs_queue", "status", "next_attempt_at", "created_at"),
        Index("ix_ai_inference_jobs_patient_window", "patient_id", "window_started_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    patient_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=True, index=True)
    model_version_id = Column(
        String(36),
        ForeignKey("ai_model_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    window_ended_at = Column(DateTime(timezone=True), nullable=False)
    input_hash = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"
    __table_args__ = (
        CheckConstraint(
            "quality_status IN ('usable', 'limited', 'unusable')",
            name="ck_ai_analysis_results_quality_status",
        ),
        CheckConstraint(
            "screening_status IN ('routine_monitoring', 'needs_observation', "
            "'review_with_clinician', 'insufficient_signal')",
            name="ck_ai_analysis_results_screening_status",
        ),
        CheckConstraint(
            "visibility IN ('shadow', 'clinician', 'patient')",
            name="ck_ai_analysis_results_visibility",
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="ck_ai_analysis_results_quality_score",
        ),
        CheckConstraint(
            "uncertainty IS NULL OR (uncertainty >= 0 AND uncertainty <= 1)",
            name="ck_ai_analysis_results_uncertainty",
        ),
        CheckConstraint(
            "contraction_probability IS NULL OR "
            "(contraction_probability >= 0 AND contraction_probability <= 1)",
            name="ck_ai_analysis_results_contraction_probability",
        ),
        CheckConstraint(
            "window_ended_at > window_started_at",
            name="ck_ai_analysis_results_window",
        ),
        ForeignKeyConstraint(
            ["patient_id", "organization_id"],
            ["patients.id", "patients.organization_id"],
            name="fk_ai_analysis_results_patient_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["sessions.id", "sessions.organization_id"],
            name="fk_ai_analysis_results_session_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_ai_analysis_results_device_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["ai_inference_jobs.id", "ai_inference_jobs.organization_id"],
            name="fk_ai_analysis_results_job_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "patient_id",
            name="uq_ai_analysis_results_identity_scope",
        ),
        UniqueConstraint("job_id", name="uq_ai_analysis_results_job"),
        Index("ix_ai_analysis_results_patient_created", "patient_id", "created_at"),
        Index("ix_ai_analysis_results_session_window", "session_id", "window_started_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    patient_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=True, index=True)
    job_id = Column(String(36), nullable=False)
    model_version_id = Column(
        String(36),
        ForeignKey("ai_model_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    model_version = Column(String(64), nullable=False)
    preprocessing_version = Column(String(64), nullable=False)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    window_ended_at = Column(DateTime(timezone=True), nullable=False)
    quality_status = Column(String(16), nullable=False)
    quality_score = Column(Float, nullable=False)
    fhr_bpm = Column(Float, nullable=True)
    maternal_hr_bpm = Column(Float, nullable=True)
    contraction_probability = Column(Float, nullable=True)
    screening_status = Column(String(32), nullable=False)
    uncertainty = Column(Float, nullable=True)
    reasons = Column(JSON, nullable=False, default=list)
    visibility = Column(String(16), nullable=False, default="shadow")
    is_simulated = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AIAnalysisReview(Base):
    __tablename__ = "ai_analysis_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('confirmed', 'dismissed', 'needs_followup')",
            name="ck_ai_analysis_reviews_decision",
        ),
        CheckConstraint("version > 0", name="ck_ai_analysis_reviews_version"),
        ForeignKeyConstraint(
            ["analysis_result_id", "organization_id", "patient_id"],
            ["ai_analysis_results.id", "ai_analysis_results.organization_id", "ai_analysis_results.patient_id"],
            name="fk_ai_analysis_reviews_result_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["reviewer_membership_id", "organization_id", "reviewer_user_id"],
            ["organization_memberships.id", "organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_ai_analysis_reviews_reviewer_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("analysis_result_id", name="uq_ai_analysis_reviews_result"),
        Index("ix_ai_analysis_reviews_patient_updated", "patient_id", "updated_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    patient_id = Column(String(36), nullable=False, index=True)
    analysis_result_id = Column(String(36), nullable=False)
    reviewer_membership_id = Column(String(36), nullable=False)
    reviewer_user_id = Column(String(36), nullable=False)
    decision = Column(String(24), nullable=False)
    note = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
