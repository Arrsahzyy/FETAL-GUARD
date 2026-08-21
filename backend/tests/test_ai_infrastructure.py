from datetime import datetime, timedelta, timezone

import pytest

from services import ai_pipeline
from models.ai_analysis import AIAnalysisResult, AIInferenceJob, AIModelVersion
from models.organization_membership import OrganizationMembership
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from services.ai_pipeline import (
    AIWorkerOutput,
    assert_ai_pipeline_ready,
    claim_next_inference_job,
    complete_inference_job,
    publish_analysis_result,
    publish_reviewed_analysis_results,
)


def create_patient_session(client, headers, *, name: str):
    profile_response = client.post(
        "/patients",
        headers=headers,
        json={
            "name": name,
            "age": 29,
            "gestational_age_weeks": 32,
            "medical_history": None,
        },
    )
    assert profile_response.status_code == 201
    session_response = client.post("/sessions", headers=headers)
    assert session_response.status_code == 201
    return profile_response.json(), session_response.json()


def create_model_job_result(
    db_session,
    *,
    patient: Patient,
    session_id: str,
    visibility: str,
    validation_status: str = "experimental",
):
    now = datetime.now(timezone.utc)
    model = AIModelVersion(
        model_name="fetal-guard-hybrid",
        version=f"test-{patient.id}-{visibility}",
        architecture="cnn_lstm_multitask",
        preprocessing_version="test-preprocessing-v1",
        input_schema_version=2,
        artifact_sha256="a" * 64,
        manifest_uri="file:///test/manifest.json",
        validation_status=validation_status,
        deployment_slot={
            "shadow": "research",
            "clinician": "clinician",
            "patient": "patient",
        }[visibility],
        is_active=True,
        created_at=now,
        activated_at=now,
    )
    db_session.add(model)
    db_session.flush()
    job = AIInferenceJob(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        session_id=session_id,
        device_id=None,
        model_version_id=model.id,
        window_started_at=now - timedelta(seconds=60),
        window_ended_at=now,
        input_hash="b" * 64,
        status="completed",
        attempts=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(job)
    db_session.flush()
    result = AIAnalysisResult(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        session_id=session_id,
        device_id=None,
        job_id=job.id,
        model_version_id=model.id,
        model_version=model.version,
        preprocessing_version=model.preprocessing_version,
        window_started_at=job.window_started_at,
        window_ended_at=job.window_ended_at,
        quality_status="limited",
        quality_score=0.72,
        fhr_bpm=None,
        maternal_hr_bpm=None,
        contraction_probability=None,
        screening_status="insufficient_signal",
        uncertainty=0.45,
        reasons=["partial_sensor_coverage"],
        visibility=visibility,
        is_simulated=False,
        created_at=now,
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(model)
    db_session.refresh(job)
    db_session.refresh(result)
    return model, job, result


def assign_patient(db_session, client, clinician_headers, patient: Patient):
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == patient.organization_id,
            OrganizationMembership.user_id == clinician_id,
            OrganizationMembership.ended_at.is_(None),
        )
        .one()
    )
    db_session.add(
        PatientClinicianAssignment(
            organization_id=patient.organization_id,
            patient_id=patient.id,
            clinician_membership_id=membership.id,
            clinician_user_id=clinician_id,
        )
    )
    db_session.commit()
    return clinician_id


def test_patient_results_are_owner_scoped_and_hide_shadow_results(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="ai-owner@example.com", role="patient")
    owner_profile, owner_session = create_patient_session(client, owner_headers, name="AI Owner")
    other_headers = auth_headers(email="ai-other@example.com", role="patient")
    create_patient_session(client, other_headers, name="AI Other")
    owner = db_session.get(Patient, owner_profile["id"])
    _, _, visible_result = create_model_job_result(
        db_session,
        patient=owner,
        session_id=owner_session["id"],
        visibility="patient",
    )
    create_model_job_result(
        db_session,
        patient=owner,
        session_id=owner_session["id"],
        visibility="shadow",
    )

    owner_response = client.get("/ai/results", headers=owner_headers)
    other_response = client.get("/ai/results", headers=other_headers)

    assert owner_response.status_code == 200
    assert [item["id"] for item in owner_response.json()["items"]] == [visible_result.id]
    assert owner_response.json()["items"][0]["visibility"] == "patient"
    assert other_response.status_code == 200
    assert other_response.json()["items"] == []


def test_clinician_results_require_assignment_and_review_uses_optimistic_version(
    client,
    auth_headers,
    db_session,
):
    patient_headers = auth_headers(email="ai-review-patient@example.com", role="patient")
    patient_profile, session = create_patient_session(client, patient_headers, name="AI Review")
    patient = db_session.get(Patient, patient_profile["id"])
    _, _, result = create_model_job_result(
        db_session,
        patient=patient,
        session_id=session["id"],
        visibility="clinician",
    )
    clinician_headers = auth_headers(email="ai-review-clinician@example.com", role="clinician")

    denied = client.get(
        f"/ai/clinician/patients/{patient.id}/results",
        headers=clinician_headers,
    )
    assert denied.status_code == 404

    assign_patient(db_session, client, clinician_headers, patient)
    allowed = client.get(
        f"/ai/clinician/patients/{patient.id}/results",
        headers=clinician_headers,
    )
    first_review = client.patch(
        f"/ai/clinician/results/{result.id}/review",
        headers=clinician_headers,
        json={
            "decision": "needs_followup",
            "note": "Perlu observasi dan pemeriksaan lanjutan.",
            "expected_version": 0,
        },
    )
    stale_review = client.patch(
        f"/ai/clinician/results/{result.id}/review",
        headers=clinician_headers,
        json={
            "decision": "confirmed",
            "note": "Permintaan lama tidak boleh menimpa tinjauan terbaru.",
            "expected_version": 0,
        },
    )

    assert allowed.status_code == 200
    assert [item["id"] for item in allowed.json()["items"]] == [result.id]
    assert first_review.status_code == 200
    assert first_review.json()["version"] == 1
    assert stale_review.status_code == 409
    assert stale_review.json()["detail"]["code"] == "AI_REVIEW_VERSION_CONFLICT"


def test_worker_output_and_publication_are_fail_closed(db_session, client, auth_headers):
    with pytest.raises(ValueError, match="Unusable signal"):
        AIWorkerOutput(
            quality_status="unusable",
            quality_score=0.1,
            screening_status="routine_monitoring",
            reasons=("signal_missing",),
        ).validate()

    patient_headers = auth_headers(email="ai-gate-patient@example.com", role="patient")
    patient_profile, session = create_patient_session(client, patient_headers, name="AI Gate")
    patient = db_session.get(Patient, patient_profile["id"])
    model, job, _ = create_model_job_result(
        db_session,
        patient=patient,
        session_id=session["id"],
        visibility="shadow",
    )
    existing = db_session.query(AIAnalysisResult).filter(AIAnalysisResult.job_id == job.id).one()
    db_session.delete(existing)
    job.status = "processing"
    db_session.commit()

    completed = complete_inference_job(
        db_session,
        job=job,
        output=AIWorkerOutput(
            quality_status="usable",
            quality_score=0.91,
            screening_status="needs_observation",
            reasons=("screening_model_signal",),
            uncertainty=0.21,
        ),
    )
    assert completed.visibility == "shadow"
    with pytest.raises(RuntimeError, match="clinically validated"):
        publish_analysis_result(db_session, result=completed, visibility="clinician")

    model.validation_status = "clinical_validated"
    completed.is_simulated = True
    with pytest.raises(RuntimeError, match="Simulated AI results"):
        publish_analysis_result(db_session, result=completed, visibility="patient")
    completed.is_simulated = False
    with pytest.raises(RuntimeError, match="clinician review"):
        publish_analysis_result(db_session, result=completed, visibility="patient")
    published = publish_analysis_result(db_session, result=completed, visibility="clinician")
    db_session.commit()
    assert published.visibility == "clinician"


def test_clinical_worker_result_is_visible_to_clinician_then_published_after_review(
    db_session,
    client,
    auth_headers,
    monkeypatch,
):
    patient_headers = auth_headers(email="ai-patient-feed@example.com", role="patient")
    patient_profile, session = create_patient_session(
        client,
        patient_headers,
        name="AI Patient Feed",
    )
    patient = db_session.get(Patient, patient_profile["id"])
    model, job, existing = create_model_job_result(
        db_session,
        patient=patient,
        session_id=session["id"],
        visibility="clinician",
        validation_status="clinical_validated",
    )
    db_session.delete(existing)
    job.status = "processing"
    db_session.commit()

    monkeypatch.setattr(ai_pipeline.settings, "AI_PIPELINE_MODE", "clinician")
    monkeypatch.setattr(ai_pipeline.settings, "AI_ACTIVE_MODEL_VERSION_ID", model.id)
    model.validation_status = "experimental"
    with pytest.raises(RuntimeError, match="clinical validation"):
        assert_ai_pipeline_ready(db_session)
    model.validation_status = "clinical_validated"
    assert_ai_pipeline_ready(db_session)
    result = complete_inference_job(
        db_session,
        job=job,
        output=AIWorkerOutput(
            quality_status="usable",
            quality_score=0.93,
            screening_status="routine_monitoring",
            reasons=("screening_model_signal",),
            fhr_bpm=142,
            maternal_hr_bpm=82,
            uncertainty=0.12,
        ),
    )
    db_session.commit()
    assert result.visibility == "clinician"
    assert model.deployment_slot == "clinician"

    patient_events_before_review = client.get(
        "/realtime/patient/events",
        headers=patient_headers,
        params={"after_cursor": 0},
    )
    assert patient_events_before_review.status_code == 200
    assert not any(
        event["event_type"] == "ai.analysis.updated"
        for event in patient_events_before_review.json()["events"]
    )

    clinician_headers = auth_headers(
        email="ai-patient-feed-clinician@example.com",
        role="clinician",
    )
    assign_patient(db_session, client, clinician_headers, patient)
    review_response = client.patch(
        f"/ai/clinician/results/{result.id}/review",
        headers=clinician_headers,
        json={
            "decision": "confirmed",
            "note": "Hasil dapat dibagikan sebagai skrining awal kepada pasien.",
            "expected_version": 0,
        },
    )
    before_publication = client.get("/ai/results", headers=patient_headers)

    assert review_response.status_code == 200
    assert before_publication.status_code == 200
    assert before_publication.json()["items"] == []

    published = publish_reviewed_analysis_results(db_session)
    db_session.commit()
    after_publication = client.get("/ai/results", headers=patient_headers)

    assert [item.id for item in published] == [result.id]
    assert after_publication.status_code == 200
    assert [item["id"] for item in after_publication.json()["items"]] == [result.id]
    assert after_publication.json()["items"][0]["visibility"] == "patient"
    patient_events_after_publication = client.get(
        "/realtime/patient/events",
        headers=patient_headers,
        params={"after_cursor": 0},
    )
    patient_ai_events = [
        event
        for event in patient_events_after_publication.json()["events"]
        if event["event_type"] == "ai.analysis.updated"
    ]
    assert patient_ai_events
    assert all(event["data"]["visibility"] == "patient" for event in patient_ai_events)

    dismissed_response = client.patch(
        f"/ai/clinician/results/{result.id}/review",
        headers=clinician_headers,
        json={
            "decision": "dismissed",
            "note": "Hasil tidak lagi digunakan setelah tinjauan lanjutan.",
            "expected_version": 1,
        },
    )
    assert dismissed_response.status_code == 200
    assert dismissed_response.json()["version"] == 2

    reconciled = publish_reviewed_analysis_results(db_session)
    db_session.commit()
    after_retraction = client.get("/ai/results", headers=patient_headers)

    assert [item.id for item in reconciled] == [result.id]
    assert after_retraction.status_code == 200
    assert after_retraction.json()["items"] == []
    db_session.refresh(result)
    assert result.visibility == "clinician"
    patient_events_after_retraction = client.get(
        "/realtime/patient/events",
        headers=patient_headers,
        params={"after_cursor": 0},
    )
    assert patient_events_after_retraction.status_code == 200
    assert len(
        [
            event
            for event in patient_events_after_retraction.json()["events"]
            if event["event_type"] == "ai.analysis.updated"
        ]
    ) >= 2


def test_worker_reclaims_an_abandoned_processing_job(db_session, client, auth_headers):
    patient_headers = auth_headers(email="ai-lease-patient@example.com", role="patient")
    patient_profile, session = create_patient_session(client, patient_headers, name="AI Lease")
    patient = db_session.get(Patient, patient_profile["id"])
    _, job, result = create_model_job_result(
        db_session,
        patient=patient,
        session_id=session["id"],
        visibility="shadow",
    )
    db_session.delete(result)
    job.status = "processing"
    job.attempts = 1
    job.locked_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    reclaimed = claim_next_inference_job(db_session)

    assert reclaimed is not None
    assert reclaimed.id == job.id
    assert reclaimed.status == "processing"
    assert reclaimed.attempts == 2
