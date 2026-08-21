from models.alert_event import AlertEvent
from models.notification import Notification
from models.sensor_data import SensorDataChunk
from core.tenancy import DEFAULT_ORGANIZATION_ID


def create_patient_profile(client, headers):
    return client.post(
        "/patients",
        headers=headers,
        json={
            "name": "Ayu Lestari",
            "age": 28,
            "gestational_age_weeks": 32,
            "medical_history": "Tidak ada catatan khusus",
        },
    )


def create_active_session(client, headers):
    patient_response = create_patient_profile(client, headers)
    assert patient_response.status_code == 201

    session_response = client.post("/sessions", headers=headers)
    assert session_response.status_code == 201
    return session_response.json()


def test_patient_can_create_profile(client, auth_headers):
    headers = auth_headers(email="profile@example.com")

    response = create_patient_profile(client, headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Ayu Lestari"
    assert data["age"] == 28
    assert data["gestational_age_weeks"] == 32
    assert data["medical_history"] == "Tidak ada catatan khusus"
    assert data["user_id"]


def test_patient_can_read_own_profile(client, auth_headers):
    headers = auth_headers(email="profile-me@example.com")
    create_patient_profile(client, headers)

    response = client.get("/patients/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ayu Lestari"
    assert data["gestational_age_weeks"] == 32


def test_patient_can_update_own_profile(client, auth_headers):
    headers = auth_headers(email="profile-update@example.com")
    create_patient_profile(client, headers)

    response = client.patch(
        "/patients/me",
        headers=headers,
        json={
            "name": "Ayu Permata",
            "gestational_age_weeks": 34,
            "medical_history": "Riwayat kesehatan singkat untuk pemantauan awal",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ayu Permata"
    assert data["age"] == 28
    assert data["gestational_age_weeks"] == 34
    assert data["medical_history"] == "Riwayat kesehatan singkat untuk pemantauan awal"


def test_patient_can_delete_completed_monitoring_data(client, auth_headers, db_session):
    headers = auth_headers(email="monitoring-delete@example.com")
    active_session = create_active_session(client, headers)
    chunk = SensorDataChunk(
        organization_id=DEFAULT_ORGANIZATION_ID,
        session_id=active_session["id"],
        ingestion_id="delete-test-chunk",
        schema_version=1,
        payload={"source": "test"},
    )
    notification = Notification(
        organization_id=DEFAULT_ORGANIZATION_ID,
        session_id=active_session["id"],
        message="Perlu cek ulang posisi sabuk",
        risk_level="medium",
        status="open",
    )
    db_session.add_all([chunk, notification])
    db_session.flush()
    db_session.add(AlertEvent(
        notification_id=notification.id,
        organization_id=DEFAULT_ORGANIZATION_ID,
        to_status="open",
        version=1,
    ))
    db_session.commit()
    completed = client.patch(
        f"/sessions/{active_session['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200

    response = client.delete("/patients/me/monitoring-data", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "deleted_sessions": 1,
        "deleted_alerts": 1,
        "deleted_sensor_chunks": 1,
        "deleted_ai_results": 0,
    }
    assert client.get("/sessions", headers=headers).json() == []
    assert client.get("/patients/me", headers=headers).status_code == 200


def test_patient_monitoring_data_deletion_rejects_active_session(client, auth_headers):
    headers = auth_headers(email="monitoring-delete-active@example.com")
    create_active_session(client, headers)

    response = client.delete("/patients/me/monitoring-data", headers=headers)

    assert response.status_code == 409
    assert "active monitoring session" in response.json()["detail"]


def test_patient_monitoring_data_deletion_rejects_non_patient(client, auth_headers):
    clinician_headers = auth_headers(
        email="monitoring-delete-clinician@example.com",
        role="clinician",
    )

    response = client.delete(
        "/patients/me/monitoring-data",
        headers=clinician_headers,
    )

    assert response.status_code == 403


def test_patient_can_persist_structured_profile_fields(client, auth_headers):
    headers = auth_headers(email="profile-structured@example.com")
    create_patient_profile(client, headers)

    response = client.patch(
        "/patients/me",
        headers=headers,
        json={
            "national_id": "1234567890123456",
            "birth_date": "1997-04-12",
            "blood_type": "O+",
            "phone_number": "+6281234567890",
            "emergency_contact_name": "Keluarga Pasien",
            "emergency_contact_phone": "081234567891",
            "last_menstrual_period": "2026-01-01",
            "estimated_due_date": "2026-10-08",
            "gravida": 2,
            "para": 1,
            "abortus": 0,
            "height_cm": 160,
            "current_weight_kg": 62.5,
            "has_allergies": True,
            "allergy_details": "Lateks",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["national_id"] == "1234567890123456"
    assert data["blood_type"] == "O+"
    assert data["allergy_details"] == "Lateks"
    assert data["current_weight_kg"] == 62.5


def test_patient_profile_rejects_null_non_nullable_fields(client, auth_headers):
    headers = auth_headers(email="profile-null@example.com")
    create_patient_profile(client, headers)

    response = client.patch("/patients/me", headers=headers, json={"name": None})

    assert response.status_code == 422


def test_patient_profile_partial_update_validates_merged_state(client, auth_headers):
    headers = auth_headers(email="profile-merged-validation@example.com")
    create_patient_profile(client, headers)
    initial = client.patch(
        "/patients/me",
        headers=headers,
        json={
            "gravida": 2,
            "para": 1,
            "abortus": 0,
            "has_allergies": True,
            "allergy_details": "Lateks",
        },
    )
    assert initial.status_code == 200

    impossible_obstetric_history = client.patch(
        "/patients/me",
        headers=headers,
        json={"para": 3},
    )
    uncleared_allergy_details = client.patch(
        "/patients/me",
        headers=headers,
        json={"has_allergies": False},
    )

    assert impossible_obstetric_history.status_code == 422
    assert uncleared_allergy_details.status_code == 422


def test_patient_profile_update_rejects_clinician_role(client, auth_headers):
    clinician_headers = auth_headers(email="profile-clinician@example.com", role="clinician")

    response = client.patch(
        "/patients/me",
        headers=clinician_headers,
        json={"name": "Nakes"},
    )

    assert response.status_code == 403


def test_patient_profile_update_requires_existing_profile(client, auth_headers):
    headers = auth_headers(email="profile-missing@example.com")

    response = client.patch(
        "/patients/me",
        headers=headers,
        json={"name": "Ayu Permata"},
    )

    assert response.status_code == 404


def test_patient_can_start_monitoring_session(client, auth_headers):
    headers = auth_headers(email="session-start@example.com")
    create_patient_profile(client, headers)

    response = client.post("/sessions", headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "active"
    assert data["organization_id"] == DEFAULT_ORGANIZATION_ID
    assert data["patient_id"]
    assert data["device_assignment_id"] is None
    assert data["start_time"]
    assert data["end_time"] is None


def test_patient_cannot_start_multiple_active_monitoring_sessions(client, auth_headers):
    headers = auth_headers(email="session-active-conflict@example.com")
    create_patient_profile(client, headers)

    first_response = client.post("/sessions", headers=headers)
    second_response = client.post("/sessions", headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert "active monitoring session" in second_response.json()["detail"]


def test_patient_can_restore_only_their_active_monitoring_session(client, auth_headers):
    owner_headers = auth_headers(email="session-active-owner@example.com")
    active_session = create_active_session(client, owner_headers)
    other_headers = auth_headers(email="session-active-other@example.com")
    create_patient_profile(client, other_headers)

    owner_response = client.get("/sessions/active", headers=owner_headers)
    other_response = client.get("/sessions/active", headers=other_headers)

    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == active_session["id"]
    assert other_response.status_code == 404


def test_patient_can_upload_sensor_chunks_repeatedly(client, auth_headers, db_session):
    headers = auth_headers(email="chunk-upload@example.com")
    session_data = create_active_session(client, headers)
    session_id = session_data["id"]
    chunk_payloads = [
        {"t": 1620000000000, "p": [1024, 980], "fsr": [312, 318]},
        {"t": 1620000001000, "p": [1000, 990], "fsr": [330, 335]},
    ]

    for payload in chunk_payloads:
        response = client.post(
            f"/sessions/{session_id}/data",
            headers=headers,
            json={"payload": payload},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"] == session_id
        assert "payload" not in data
        assert data["timestamp"]

    stored_chunks = (
        db_session.query(SensorDataChunk)
        .filter(SensorDataChunk.session_id == session_id)
        .order_by(SensorDataChunk.timestamp.asc())
        .all()
    )
    assert [chunk.payload["samples"]["p"] for chunk in stored_chunks] == [
        payload["p"] for payload in chunk_payloads
    ]


def test_sensor_chunk_rejects_empty_channel_arrays(client, auth_headers):
    headers = auth_headers(email="empty-chunk@example.com")
    session_data = create_active_session(client, headers)

    response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=headers,
        json={"payload": {"p": [], "fsr": []}},
    )

    assert response.status_code == 422


def test_sensor_chunk_ingestion_id_is_idempotent(client, auth_headers):
    headers = auth_headers(email="idempotent-chunk@example.com")
    session_data = create_active_session(client, headers)
    request_body = {
        "payload": {"p": [1000, 1010]},
        "ingestion_id": "manual-packet-0001",
    }

    first = client.post(f"/sessions/{session_data['id']}/data", headers=headers, json=request_body)
    second = client.post(f"/sessions/{session_data['id']}/data", headers=headers, json=request_body)
    sessions = client.get("/sessions", headers=headers).json()

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["was_duplicate"] is True
    assert sessions[0]["sensor_summary"]["sample_count"] == 2


def test_session_creation_is_idempotent_by_client_session_id(client, auth_headers):
    headers = auth_headers(email="idempotent-session@example.com")
    create_patient_profile(client, headers)
    body = {"client_session_id": "client-session-0001"}

    first = client.post("/sessions", headers=headers, json=body)
    second = client.post("/sessions", headers=headers, json=body)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_sensor_chunk_can_store_simulation_metadata(client, auth_headers, db_session):
    headers = auth_headers(email="simulated-chunk@example.com")
    session_data = create_active_session(client, headers)
    payload = {"t": 12345, "hr_ir": [1000]}

    response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=headers,
        json={"payload": payload, "source": "mock", "is_simulated": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert "payload" not in data
    stored = db_session.query(SensorDataChunk).filter(SensorDataChunk.id == data["id"]).one()
    assert stored.payload["source"] == "mock"
    assert stored.payload["is_simulated"] is True
    assert stored.payload["samples"]["hr_ir"] == [1000]


def test_patient_cannot_upload_to_completed_session(client, auth_headers):
    headers = auth_headers(email="completed-upload@example.com")
    session_data = create_active_session(client, headers)
    session_id = session_data["id"]
    complete_response = client.patch(
        f"/sessions/{session_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert complete_response.status_code == 200

    response = client.post(
        f"/sessions/{session_id}/data",
        headers=headers,
        json={"payload": {"t": 1234, "fsr": [312]}},
    )

    assert response.status_code == 400


def test_patient_cannot_access_another_patient_session(client, auth_headers):
    owner_headers = auth_headers(email="session-owner@example.com")
    owned_session = create_active_session(client, owner_headers)

    intruder_headers = auth_headers(email="session-intruder@example.com")
    create_patient_profile(client, intruder_headers)

    upload_response = client.post(
        f"/sessions/{owned_session['id']}/data",
        headers=intruder_headers,
        json={"payload": {"t": 1234, "fsr": [312]}},
    )
    complete_response = client.patch(
        f"/sessions/{owned_session['id']}",
        headers=intruder_headers,
        json={"status": "completed"},
    )

    assert upload_response.status_code == 404
    assert complete_response.status_code == 404


def test_sensor_chunk_rejects_oversized_payload(client, auth_headers):
    headers = auth_headers(email="oversized-chunk@example.com")
    session_data = create_active_session(client, headers)

    response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=headers,
        json={"payload": {"t": 1234, "p": [1] * 6000}},
    )

    assert response.status_code == 422


def test_sensor_chunk_rejects_invalid_contract(client, auth_headers):
    headers = auth_headers(email="invalid-contract@example.com")
    session_data = create_active_session(client, headers)
    session_id = session_data["id"]

    # Missing all data channels
    response = client.post(
        f"/sessions/{session_id}/data",
        headers=headers,
        json={"payload": {"t": 1234}},
    )
    assert response.status_code == 422

    # Wrong data types
    response = client.post(
        f"/sessions/{session_id}/data",
        headers=headers,
        json={"payload": {"t": "wrong_type", "p": [1024]}},
    )
    assert response.status_code == 422


def test_patient_can_complete_monitoring_session(client, auth_headers):
    headers = auth_headers(email="session-complete@example.com")
    session_data = create_active_session(client, headers)

    response = client.patch(
        f"/sessions/{session_data['id']}",
        headers=headers,
        json={"status": "completed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["end_time"] is not None


def test_sessions_endpoints_reject_unauthorized_requests(client):
    assert client.post("/patients", json={"name": "Ayu", "age": 28, "gestational_age_weeks": 32}).status_code == 401
    assert client.get("/patients/me").status_code == 401
    assert client.post("/sessions").status_code == 401
    assert client.patch("/sessions/missing", json={"status": "completed"}).status_code == 401
    assert client.post("/sessions/missing/data", json={"payload": []}).status_code == 401
