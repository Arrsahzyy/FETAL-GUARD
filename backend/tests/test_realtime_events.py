from datetime import datetime, timedelta, timezone

import pytest

from core.realtime import (
    enqueue_realtime_event,
    purge_expired_realtime_events,
    sanitize_realtime_event_payload,
)
from core.tenancy import DEFAULT_ORGANIZATION_ID, ensure_default_organization
from models.organization_membership import OrganizationMembership
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from models.realtime_event import RealtimeEvent, RealtimeEventCursor


def create_patient_profile(client, headers, name: str):
    response = client.post(
        "/patients",
        headers=headers,
        json={"name": name, "age": 29, "gestational_age_weeks": 31},
    )
    assert response.status_code == 201
    return response.json()


def test_patient_event_cursor_is_incremental_and_ingestion_retry_is_idempotent(
    client,
    auth_headers,
    db_session,
):
    headers = auth_headers(email="realtime-patient@example.com", role="patient")
    patient = create_patient_profile(client, headers, "Pasien Realtime")
    request_body = {"client_session_id": "realtime-session-0001"}

    first_session = client.post("/sessions", headers=headers, json=request_body)
    retried_session = client.post("/sessions", headers=headers, json=request_body)
    assert first_session.status_code == 201
    assert retried_session.status_code == 201
    assert retried_session.json()["id"] == first_session.json()["id"]

    packet = {
        "payload": {"p": [1000, 1010]},
        "ingestion_id": "realtime-packet-0001",
    }
    first_packet = client.post(
        f"/sessions/{first_session.json()['id']}/data",
        headers=headers,
        json=packet,
    )
    retried_packet = client.post(
        f"/sessions/{first_session.json()['id']}/data",
        headers=headers,
        json=packet,
    )
    assert first_packet.status_code == 201
    assert retried_packet.status_code == 201
    assert retried_packet.json()["was_duplicate"] is True

    first_page = client.get(
        "/realtime/patient/events",
        headers=headers,
        params={"after_cursor": 0, "limit": 1},
    )
    assert first_page.status_code == 200
    assert first_page.json()["has_more"] is True
    assert [event["event_type"] for event in first_page.json()["events"]] == [
        "session.started"
    ]

    second_page = client.get(
        "/realtime/patient/events",
        headers=headers,
        params={"after_cursor": first_page.json()["next_cursor"]},
    )
    assert second_page.status_code == 200
    assert [event["event_type"] for event in second_page.json()["events"]] == [
        "telemetry.updated"
    ]
    assert second_page.json()["next_cursor"] > first_page.json()["next_cursor"]
    telemetry_data = second_page.json()["events"][0]["data"]
    assert telemetry_data["sample_count"] == 2
    assert "payload" not in telemetry_data
    assert "samples" not in telemetry_data

    events = (
        db_session.query(RealtimeEvent)
        .filter(RealtimeEvent.patient_id == patient["id"])
        .order_by(RealtimeEvent.cursor.asc())
        .all()
    )
    assert [event.event_type for event in events] == [
        "session.started",
        "telemetry.updated",
    ]


def test_patient_event_feed_bootstraps_at_latest_authorized_watermark(client, auth_headers):
    headers = auth_headers(email="realtime-bootstrap@example.com", role="patient")
    create_patient_profile(client, headers, "Pasien Bootstrap")
    assert client.post("/sessions", headers=headers).status_code == 201

    baseline = client.get("/realtime/patient/events", headers=headers)

    assert baseline.status_code == 200
    assert baseline.json()["events"] == []
    assert baseline.json()["next_cursor"] >= 1


def test_clinician_event_feed_only_contains_currently_assigned_patients(
    client,
    auth_headers,
    db_session,
):
    assigned_headers = auth_headers(email="realtime-assigned@example.com", role="patient")
    hidden_headers = auth_headers(email="realtime-hidden@example.com", role="patient")
    assigned = create_patient_profile(client, assigned_headers, "Pasien Ditugaskan")
    hidden = create_patient_profile(client, hidden_headers, "Pasien Tidak Ditugaskan")
    assert client.post("/sessions", headers=assigned_headers).status_code == 201
    assert client.post("/sessions", headers=hidden_headers).status_code == 201

    clinician_headers = auth_headers(email="realtime-clinician@example.com", role="clinician")
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == clinician_id,
            OrganizationMembership.organization_id == DEFAULT_ORGANIZATION_ID,
            OrganizationMembership.ended_at.is_(None),
        )
        .one()
    )
    db_session.add(
        PatientClinicianAssignment(
            organization_id=DEFAULT_ORGANIZATION_ID,
            patient_id=assigned["id"],
            clinician_membership_id=membership.id,
            clinician_user_id=clinician_id,
            care_role="primary",
        )
    )
    db_session.commit()

    response = client.get(
        "/realtime/clinician/events",
        headers=clinician_headers,
        params={"after_cursor": 0},
    )
    assert response.status_code == 200
    assert {event["patient_id"] for event in response.json()["events"]} == {
        assigned["id"]
    }
    assert hidden["id"] not in {
        event["patient_id"] for event in response.json()["events"]
    }

    hidden_filter = client.get(
        "/realtime/clinician/events",
        headers=clinician_headers,
        params={"after_cursor": 0, "patient_id": hidden["id"]},
    )
    assert hidden_filter.status_code == 200
    assert hidden_filter.json()["events"] == []


def test_event_sequence_and_idempotency_are_facility_scoped(db_session, create_user):
    organization = ensure_default_organization(db_session)
    first_user = create_user(email="cursor-one@example.com", role="patient")
    second_user = create_user(email="cursor-two@example.com", role="patient")
    first_patient = Patient(
        organization_id=organization.id,
        user_id=first_user.id,
        name="Pasien Cursor Satu",
        age=28,
        gestational_age_weeks=30,
    )
    second_patient = Patient(
        organization_id=organization.id,
        user_id=second_user.id,
        name="Pasien Cursor Dua",
        age=30,
        gestational_age_weeks=32,
    )
    db_session.add_all([first_patient, second_patient])
    db_session.flush()

    first = enqueue_realtime_event(
        db_session,
        organization_id=organization.id,
        patient_id=first_patient.id,
        event_type="session.started",
        resource_id="session-cursor-one",
        idempotency_key="session.started:cursor-one",
        payload={"has_device": False, "status": "active"},
    )
    retried = enqueue_realtime_event(
        db_session,
        organization_id=organization.id,
        patient_id=first_patient.id,
        event_type="session.started",
        resource_id="session-cursor-one",
        idempotency_key="session.started:cursor-one",
        payload={"has_device": False, "status": "active"},
    )
    second = enqueue_realtime_event(
        db_session,
        organization_id=organization.id,
        patient_id=second_patient.id,
        event_type="session.started",
        resource_id="session-cursor-two",
        idempotency_key="session.started:cursor-two",
        payload={"has_device": False, "status": "active"},
    )
    db_session.commit()

    assert retried.id == first.id
    assert (first.cursor, second.cursor) == (1, 2)
    assert db_session.query(RealtimeEvent).count() == 2
    cursor_state = db_session.get(RealtimeEventCursor, organization.id)
    assert cursor_state.last_cursor == 2


def test_expired_event_cleanup_is_bounded_and_cursor_is_not_reset(
    db_session,
    create_user,
):
    organization = ensure_default_organization(db_session)
    user = create_user(email="retention-patient@example.com", role="patient")
    patient = Patient(
        organization_id=organization.id,
        user_id=user.id,
        name="Pasien Retensi",
        age=28,
        gestational_age_weeks=30,
    )
    db_session.add(patient)
    db_session.flush()
    expired_time = datetime.now(timezone.utc) - timedelta(days=10)
    enqueue_realtime_event(
        db_session,
        organization_id=organization.id,
        patient_id=patient.id,
        event_type="session.completed",
        resource_id="expired-session",
        idempotency_key="session.completed:expired",
        payload={"status": "completed"},
        occurred_at=expired_time,
    )
    active = enqueue_realtime_event(
        db_session,
        organization_id=organization.id,
        patient_id=patient.id,
        event_type="session.started",
        resource_id="active-session",
        idempotency_key="session.started:active",
        payload={"has_device": False, "status": "active"},
    )
    db_session.commit()

    deleted = purge_expired_realtime_events(db_session, batch_size=1)
    db_session.commit()

    assert deleted == 1
    assert [event.id for event in db_session.query(RealtimeEvent).all()] == [active.id]
    cursor_state = db_session.get(RealtimeEventCursor, organization.id)
    assert cursor_state.last_cursor == 2


def test_realtime_payload_rejects_raw_or_unknown_fields():
    with pytest.raises(ValueError, match="Unsupported realtime event metadata"):
        sanitize_realtime_event_payload(
            "telemetry.updated",
            {"samples": {"p": [1000, 1010]}},
        )
