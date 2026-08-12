from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from core.tenancy import DEFAULT_ORGANIZATION_ID
from models.device import Device
from models.device_assignment import DeviceAssignment
from models.session import MonitoringSession


def create_patient_profile(client, headers, name="Ayu Lestari"):
    response = client.post(
        "/patients",
        headers=headers,
        json={
            "name": name,
            "age": 28,
            "gestational_age_weeks": 32,
            "medical_history": None,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_active_session(client, headers, name="Ayu Lestari"):
    create_patient_profile(client, headers, name=name)
    session_response = client.post("/sessions", headers=headers)
    assert session_response.status_code == 201
    return session_response.json()


def register_device(client, admin_headers, patient_id, device_uid="FG-BELT-001", status="active"):
    response = client.post(
        "/devices",
        headers=admin_headers,
        json={
            "device_uid": device_uid,
            "patient_id": patient_id,
            "display_name": "FETAL-GUARD Belt Unit 1",
            "hardware_revision": "belt-v1",
            "firmware_version": "0.1.0",
            "status": status,
        },
    )
    assert response.status_code == 201
    return response.json()


def device_packet(device_uid, sequence_number, payload):
    return {
        "payload": payload,
        "schema_version": 1,
        "ingestion_id": f"packet-{device_uid}-{sequence_number}",
        "boot_id": "boot-session-0001",
        "sequence_number": sequence_number,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "sample_rate_hz": 100,
        "source": "device",
        "device_uid": device_uid,
        "is_simulated": False,
    }


def get_current_user_id(client, headers):
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def assign_patient_to_clinician(client, admin_headers, patient_id, clinician_id):
    response = client.post(
        "/admin/patient-assignments",
        headers=admin_headers,
        json={"patient_id": patient_id, "clinician_id": clinician_id},
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_register_assign_and_list_patient_device(client, auth_headers):
    patient_headers = auth_headers(email="device-patient@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers)
    admin_headers = auth_headers(email="device-admin@example.com", role="admin")

    device = register_device(client, admin_headers, patient["id"])
    patient_devices_response = client.get("/devices/me", headers=patient_headers)
    admin_list_response = client.get("/devices?q=fg-belt-001", headers=admin_headers)

    assert device["device_uid"] == "FG-BELT-001"
    assert device["patient_id"] == patient["id"]
    assert patient_devices_response.status_code == 200
    assert patient_devices_response.json()[0]["device_uid"] == "FG-BELT-001"
    assert admin_list_response.status_code == 200
    assert admin_list_response.json()["total"] == 1


def test_device_registration_creates_authoritative_temporal_assignment(
    client,
    auth_headers,
    db_session,
):
    patient_headers = auth_headers(email="device-assignment-owner@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers)
    admin_headers = auth_headers(email="device-assignment-admin@example.com", role="admin")

    device = register_device(
        client,
        admin_headers,
        patient["id"],
        device_uid="FG-BELT-ASSIGNMENT-HISTORY",
    )

    assignment = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .one()
    )
    assert assignment.organization_id == DEFAULT_ORGANIZATION_ID
    assert assignment.patient_id == patient["id"]
    assert assignment.ends_at is None
    assert assignment.version == 1
    assert assignment.assigned_by_user_id == get_current_user_id(client, admin_headers)


def test_device_reassignment_closes_history_and_creates_new_interval_atomically(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-history-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers, name="Pemilik Pertama")
    replacement_headers = auth_headers(email="device-history-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers, name="Pemilik Kedua")
    admin_headers = auth_headers(email="device-history-admin@example.com", role="admin")
    admin_id = get_current_user_id(client, admin_headers)
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-TEMPORAL-HANDOVER",
    )

    response = client.patch(
        f"/devices/{device['id']}",
        headers=admin_headers,
        json={"patient_id": replacement["id"]},
    )

    assert response.status_code == 200
    assert response.json()["patient_id"] == replacement["id"]
    db_session.expire_all()
    assignments = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .order_by(DeviceAssignment.starts_at.asc(), DeviceAssignment.id.asc())
        .all()
    )
    assert len(assignments) == 2
    previous = next(item for item in assignments if item.patient_id == owner["id"])
    current = next(item for item in assignments if item.patient_id == replacement["id"])
    assert previous.ends_at is not None
    assert previous.ended_by_user_id == admin_id
    assert previous.version == 2
    assert current.ends_at is None
    assert current.version == 1
    assert current.assigned_by_user_id == admin_id

    owner_devices = client.get("/devices/me", headers=owner_headers)
    replacement_devices = client.get("/devices/me", headers=replacement_headers)
    assert owner_devices.status_code == 200
    assert owner_devices.json() == []
    assert [item["id"] for item in replacement_devices.json()] == [device["id"]]


def test_device_assignment_history_rejects_rewrite_or_delete(
    client,
    auth_headers,
    db_session,
):
    patient_headers = auth_headers(email="device-immutable-owner@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers)
    admin_headers = auth_headers(email="device-immutable-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        patient["id"],
        device_uid="FG-BELT-IMMUTABLE",
    )
    assignment = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .one()
    )

    assignment.patient_id = "00000000-0000-0000-0000-000000000099"
    with pytest.raises(ValueError, match="immutable"):
        db_session.commit()
    db_session.rollback()

    assignment = db_session.get(DeviceAssignment, assignment.id)
    db_session.delete(assignment)
    with pytest.raises(ValueError, match="cannot be deleted"):
        db_session.commit()
    db_session.rollback()


def test_database_prevents_two_active_assignments_for_one_device(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-unique-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers)
    replacement_headers = auth_headers(email="device-unique-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers)
    admin_headers = auth_headers(email="device-unique-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-UNIQUE-ACTIVE-ASSIGNMENT",
    )

    db_session.add(
        DeviceAssignment(
            organization_id=DEFAULT_ORGANIZATION_ID,
            device_id=device["id"],
            patient_id=replacement["id"],
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_patient_cannot_access_global_device_registry(client, auth_headers):
    patient_headers = auth_headers(email="device-registry-patient@example.com", role="patient")
    create_patient_profile(client, patient_headers)

    response = client.get("/devices", headers=patient_headers)

    assert response.status_code == 403


def test_device_source_requires_device_uid(client, auth_headers):
    patient_headers = auth_headers(email="device-source-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers)

    response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={"payload": {"t": 1234, "p": [1024]}, "source": "device"},
    )

    assert response.status_code == 422


def test_sensor_upload_rejects_unregistered_or_inactive_device(client, auth_headers):
    patient_headers = auth_headers(email="device-inactive-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers)
    admin_headers = auth_headers(email="device-inactive-admin@example.com", role="admin")
    register_device(
        client,
        admin_headers,
        session_data["patient_id"],
        device_uid="FG-BELT-INACTIVE",
        status="maintenance",
    )

    unknown_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=device_packet("FG-BELT-UNKNOWN", 1, {"t": 1234, "p": [1024]}),
    )
    inactive_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=device_packet("FG-BELT-INACTIVE", 2, {"t": 1234, "p": [1024]}),
    )

    assert unknown_response.status_code == 404
    assert inactive_response.status_code == 403


def test_device_upload_updates_provenance_without_trusting_client_summary(client, auth_headers):
    patient_headers = auth_headers(email="device-summary-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Ringkasan Sensor")
    admin_headers = auth_headers(email="device-summary-admin@example.com", role="admin")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-BELT-SUMMARY")

    first_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            **device_packet(
                "FG-BELT-SUMMARY",
                1,
                {"t": 1234, "p": [1024, 1000], "fsr": [300], "hr_ir": [10000]},
            ),
        },
    )
    second_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=device_packet("FG-BELT-SUMMARY", 2, {"t": 1235, "p": [1028], "fsr": [310]}),
    )
    sessions_response = client.get("/sessions", headers=patient_headers)
    patient_devices_response = client.get("/devices/me", headers=patient_headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    summary = sessions_response.json()[0]["sensor_summary"]
    assert summary["fhr_estimate_bpm"] is None
    assert summary["maternal_hr_bpm"] is None
    assert summary["signal_quality_index"] is None
    assert summary["contraction_indicator"] == "unknown"
    assert summary["sample_count"] == 6
    assert summary["source"] == "device"
    assert summary["is_simulated"] is False
    assert patient_devices_response.json()[0]["last_seen_at"] is not None


def test_clinician_patient_summary_includes_session_sensor_summary(client, auth_headers):
    patient_headers = auth_headers(email="device-clinician-summary-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Pasien Dengan Ringkasan")
    admin_headers = auth_headers(email="device-clinician-summary-admin@example.com", role="admin")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-BELT-CLINICIAN")
    upload_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            **device_packet("FG-BELT-CLINICIAN", 1, {"t": 1234, "p": [1024], "fsr": [300]}),
        },
    )
    assert upload_response.status_code == 201
    clinician_headers = auth_headers(email="device-clinician-summary-nakes@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    assign_patient_to_clinician(client, admin_headers, session_data["patient_id"], clinician_id)

    response = client.get("/clinician/patients", headers=clinician_headers)

    assert response.status_code == 200
    latest_session = response.json()["items"][0]["latest_session"]
    assert latest_session["sensor_summary"]["fhr_estimate_bpm"] is None
    assert latest_session["sensor_summary"]["signal_quality_index"] is None


def test_device_upload_rejects_untrusted_derived_summary(client, auth_headers):
    patient_headers = auth_headers(email="device-untrusted-summary@example.com", role="patient")
    session_data = create_active_session(client, patient_headers)
    admin_headers = auth_headers(email="device-untrusted-summary-admin@example.com", role="admin")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-BELT-UNTRUSTED")
    body = device_packet("FG-BELT-UNTRUSTED", 1, {"p": [1024]})
    body["summary"] = {"fhr_estimate_bpm": 142}

    response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=body,
    )

    assert response.status_code == 422


def test_device_upload_rejects_timestamp_outside_session_window(client, auth_headers):
    patient_headers = auth_headers(email="device-timestamp-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers)
    admin_headers = auth_headers(email="device-timestamp-admin@example.com", role="admin")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-BELT-CLOCK")

    future_body = device_packet("FG-BELT-CLOCK", 1, {"p": [1024]})
    future_body["captured_at"] = (datetime.now(timezone.utc) + timedelta(minutes=6)).isoformat()
    old_body = device_packet("FG-BELT-CLOCK", 2, {"p": [1024]})
    old_body["captured_at"] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()

    future_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=future_body,
    )
    old_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=old_body,
    )

    assert future_response.status_code == 422
    assert old_response.status_code == 422


def test_patient_cannot_upload_with_another_patient_device(client, auth_headers):
    owner_headers = auth_headers(email="device-owner@example.com", role="patient")
    owner_session = create_active_session(client, owner_headers, name="Pemilik Device")
    intruder_headers = auth_headers(email="device-intruder@example.com", role="patient")
    intruder_session = create_active_session(client, intruder_headers, name="Pasien Lain")
    admin_headers = auth_headers(email="device-owner-admin@example.com", role="admin")
    register_device(client, admin_headers, owner_session["patient_id"], device_uid="FG-BELT-OWNER")

    response = client.post(
        f"/sessions/{intruder_session['id']}/data",
        headers=intruder_headers,
        json=device_packet("FG-BELT-OWNER", 1, {"t": 1234, "p": [1024]}),
    )

    assert response.status_code == 403


def test_admin_cannot_reassign_device_during_active_session(client, auth_headers):
    owner_headers = auth_headers(email="device-reassign-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers, name="Pemilik Aktif")
    replacement_headers = auth_headers(email="device-reassign-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers, name="Pemilik Berikutnya")
    admin_headers = auth_headers(email="device-reassign-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-REASSIGN",
    )
    session_response = client.post(
        "/sessions",
        headers=owner_headers,
        json={"device_uid": device["device_uid"]},
    )
    assert session_response.status_code == 201

    response = client.patch(
        f"/devices/{device['id']}",
        headers=admin_headers,
        json={"patient_id": replacement["id"]},
    )

    assert response.status_code == 409
    assert "active monitoring session" in response.json()["detail"]
    listed = client.get(
        f"/devices?patient_id={owner['id']}",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["patient_id"] == owner["id"]


def test_admin_cannot_make_device_unavailable_during_active_session(client, auth_headers):
    patient_headers = auth_headers(email="device-status-owner@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers, name="Pemilik Status Aktif")
    admin_headers = auth_headers(email="device-status-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        patient["id"],
        device_uid="FG-BELT-STATUS-CONFLICT",
    )
    session_response = client.post(
        "/sessions",
        headers=patient_headers,
        json={"device_uid": device["device_uid"]},
    )
    assert session_response.status_code == 201

    response = client.patch(
        f"/devices/{device['id']}",
        headers=admin_headers,
        json={"status": "maintenance"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ACTIVE_SESSION_DEVICE_STATE_CONFLICT"
    listed = client.get(f"/devices?q={device['device_uid']}", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "active"


def test_completed_session_keeps_assignment_snapshot_after_device_handover(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-snapshot-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers, name="Pemilik Sesi Historis")
    replacement_headers = auth_headers(email="device-snapshot-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers, name="Pemilik Baru")
    admin_headers = auth_headers(email="device-snapshot-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-SESSION-SNAPSHOT",
    )

    started = client.post(
        "/sessions",
        headers=owner_headers,
        json={"device_uid": device["device_uid"]},
    )
    assert started.status_code == 201
    original_assignment_id = started.json()["device_assignment_id"]
    assert original_assignment_id
    completed = client.patch(
        f"/sessions/{started.json()['id']}",
        headers=owner_headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200

    handed_over = client.patch(
        f"/devices/{device['id']}",
        headers=admin_headers,
        json={"patient_id": replacement["id"]},
    )
    assert handed_over.status_code == 200

    history = client.get("/sessions", headers=owner_headers)
    assert history.status_code == 200
    assert history.json()[0]["device_id"] == device["id"]
    assert history.json()[0]["device_assignment_id"] == original_assignment_id
    db_session.expire_all()
    historical_assignment = db_session.get(DeviceAssignment, original_assignment_id)
    assert historical_assignment.ends_at is not None
    assert historical_assignment.patient_id == owner["id"]

    replacement_session = client.post(
        "/sessions",
        headers=replacement_headers,
        json={"device_uid": device["device_uid"]},
    )
    assert replacement_session.status_code == 201
    assert replacement_session.json()["device_assignment_id"] != original_assignment_id


def test_session_assignment_composite_fk_rejects_patient_snapshot_mismatch(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-fk-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers)
    replacement_headers = auth_headers(email="device-fk-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers)
    admin_headers = auth_headers(email="device-fk-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-COMPOSITE-FK",
    )
    assignment = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"], DeviceAssignment.ends_at.is_(None))
        .one()
    )

    db_session.add(
        MonitoringSession(
            organization_id=DEFAULT_ORGANIZATION_ID,
            patient_id=replacement["id"],
            device_id=device["id"],
            device_assignment_id=assignment.id,
            status="completed",
            end_time=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_device_cache_pointer_is_never_trusted_without_active_assignment(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-cache-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers)
    replacement_headers = auth_headers(email="device-cache-next@example.com", role="patient")
    replacement = create_patient_profile(client, replacement_headers)
    admin_headers = auth_headers(email="device-cache-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-CACHE-IS-NOT-AUTHORITY",
    )

    stored_device = db_session.get(Device, device["id"])
    stored_device.patient_id = replacement["id"]
    db_session.commit()

    replacement_attempt = client.post(
        "/sessions",
        headers=replacement_headers,
        json={"device_uid": device["device_uid"]},
    )
    owner_attempt = client.post(
        "/sessions",
        headers=owner_headers,
        json={"device_uid": device["device_uid"]},
    )
    owner_registry = client.get("/devices/me", headers=owner_headers)
    replacement_registry = client.get("/devices/me", headers=replacement_headers)

    assert replacement_attempt.status_code == 403
    assert owner_attempt.status_code == 409
    assert owner_attempt.json()["detail"]["code"] == "DEVICE_ASSIGNMENT_CACHE_CONFLICT"
    assert owner_registry.json() == []
    assert replacement_registry.json() == []


def test_database_prevents_two_active_sessions_for_one_device(
    client,
    auth_headers,
    db_session,
):
    owner_headers = auth_headers(email="device-db-owner@example.com", role="patient")
    owner = create_patient_profile(client, owner_headers, name="Pemilik Database")
    second_headers = auth_headers(email="device-db-second@example.com", role="patient")
    second_patient = create_patient_profile(client, second_headers, name="Pasien Kedua")
    admin_headers = auth_headers(email="device-db-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        owner["id"],
        device_uid="FG-BELT-DB-UNIQUE",
    )
    first = client.post(
        "/sessions",
        headers=owner_headers,
        json={"device_uid": device["device_uid"]},
    )
    assert first.status_code == 201
    assignment = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"], DeviceAssignment.ends_at.is_(None))
        .one()
    )

    db_session.add(MonitoringSession(
        organization_id=DEFAULT_ORGANIZATION_ID,
        patient_id=second_patient["id"],
        device_id=device["id"],
        device_assignment_id=assignment.id,
        status="active",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unbound_session_cannot_switch_device_after_first_packet(client, auth_headers):
    patient_headers = auth_headers(email="device-bind-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Binding Perangkat")
    admin_headers = auth_headers(email="device-bind-admin@example.com", role="admin")
    first_device = register_device(
        client,
        admin_headers,
        session_data["patient_id"],
        device_uid="FG-BELT-BIND-ONE",
    )
    second_device = register_device(
        client,
        admin_headers,
        session_data["patient_id"],
        device_uid="FG-BELT-BIND-TWO",
    )

    first = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=device_packet(first_device["device_uid"], 1, {"p": [1024]}),
    )
    second = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=device_packet(second_device["device_uid"], 1, {"p": [1025]}),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "different device" in second.json()["detail"]
    stored_session = client.get("/sessions", headers=patient_headers).json()[0]
    assert stored_session["device_id"] == first_device["id"]


def test_device_packet_timestamp_must_follow_sequence_order(client, auth_headers):
    patient_headers = auth_headers(email="device-order-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Urutan Paket")
    admin_headers = auth_headers(email="device-order-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        session_data["patient_id"],
        device_uid="FG-BELT-TIMELINE",
    )
    captured_at = datetime.now(timezone.utc)
    first_body = device_packet(device["device_uid"], 1, {"p": [1024]})
    first_body["captured_at"] = captured_at.isoformat()
    second_body = device_packet(device["device_uid"], 2, {"p": [1025]})
    second_body["captured_at"] = (captured_at - timedelta(seconds=1)).isoformat()

    first = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=first_body,
    )
    second = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=second_body,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "preceding device sequence" in second.json()["detail"]
    summary = client.get("/sessions", headers=patient_headers).json()[0]["sensor_summary"]
    assert summary["sample_count"] == 1


def test_production_ingestion_rejects_manual_and_simulated_sources(
    client,
    auth_headers,
    monkeypatch,
):
    patient_headers = auth_headers(email="device-production-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Ingestion Production")
    admin_headers = auth_headers(email="device-production-admin@example.com", role="admin")
    device = register_device(
        client,
        admin_headers,
        session_data["patient_id"],
        device_uid="FG-BELT-PRODUCTION",
    )

    from api.routes import sessions as session_routes

    monkeypatch.setattr(session_routes.settings, "ENVIRONMENT", "production")
    manual = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={"payload": {"p": [1024]}},
    )
    simulated = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={"payload": {"p": [1024]}, "source": "mock", "is_simulated": True},
    )
    real_body = device_packet(device["device_uid"], 1, {"p": [1024]})
    real_body["payload"]["t"] = int(
        datetime.fromisoformat(real_body["captured_at"]).timestamp() * 1000
    )
    real_device = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=real_body,
    )
    mismatched_timestamp_body = device_packet(device["device_uid"], 2, {"p": [1025], "t": 0})
    mismatched_timestamp = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=mismatched_timestamp_body,
    )

    assert manual.status_code == 422
    assert simulated.status_code == 422
    assert real_device.status_code == 201
    assert mismatched_timestamp.status_code == 422
