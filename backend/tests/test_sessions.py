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
    assert data["patient_id"]
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


def test_patient_can_upload_sensor_chunks_repeatedly(client, auth_headers):
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
        assert data["payload"]["p"] == payload["p"]
        assert data["timestamp"]


def test_sensor_chunk_can_store_simulation_metadata(client, auth_headers):
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
    assert data["payload"]["source"] == "mock"
    assert data["payload"]["is_simulated"] is True
    assert data["payload"]["samples"]["hr_ir"] == [1000]


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
