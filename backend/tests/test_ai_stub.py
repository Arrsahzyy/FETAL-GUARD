from datetime import datetime, timezone


def create_sensor_chunk(client, headers):
    patient_response = client.post(
        "/patients",
        headers=headers,
        json={
            "name": "Dewi Anggraini",
            "age": 30,
            "gestational_age_weeks": 34,
            "medical_history": None,
        },
    )
    assert patient_response.status_code == 201

    session_response = client.post("/sessions", headers=headers)
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    chunk_response = client.post(
        f"/sessions/{session_id}/data",
        headers=headers,
        json={
            "payload": {"t": 1620000000000, "fsr": [312, 318]}
        },
    )
    assert chunk_response.status_code == 201
    return chunk_response.json()


def test_ai_predict_is_disabled_until_model_is_validated(client, auth_headers):
    headers = auth_headers(email="ai-patient@example.com", role="patient")
    chunk = create_sensor_chunk(client, headers)

    response = client.post(
        "/ai/predict",
        headers=headers,
        json={"sensor_data_chunk_id": chunk["id"]},
    )

    assert response.status_code == 503
    assert "not available" in response.json()["detail"].lower()


def test_patient_ai_status_is_fail_closed_while_pipeline_is_disabled(client, auth_headers):
    patient_headers = auth_headers(email="ai-status-patient@example.com", role="patient")
    response = client.get("/ai/status", headers=patient_headers)

    assert response.status_code == 200
    assert response.json() == {"patient_results_enabled": False}


def test_patient_ai_status_rejects_clinician_role(client, auth_headers):
    clinician_headers = auth_headers(email="ai-status-clinician@example.com", role="clinician")
    response = client.get("/ai/status", headers=clinician_headers)

    assert response.status_code == 403


def test_ai_predict_requires_valid_jwt(client):
    response = client.post("/ai/predict", json={"sensor_data_chunk_id": "missing"})

    assert response.status_code == 401


def test_ai_predict_scopes_clinician_chunk_access_by_assignment(client, auth_headers, db_session):
    patient_headers = auth_headers(email="ai-scope-patient@example.com", role="patient")
    chunk = create_sensor_chunk(client, patient_headers)
    clinician_headers = auth_headers(email="ai-scope-clinician@example.com", role="clinician")

    unassigned_response = client.post(
        "/ai/predict",
        headers=clinician_headers,
        json={"sensor_data_chunk_id": chunk["id"]},
    )
    assert unassigned_response.status_code == 404

    clinician_me = client.get("/auth/me", headers=clinician_headers)
    patient_sessions = client.get("/sessions", headers=patient_headers)
    assert clinician_me.status_code == 200
    assert patient_sessions.status_code == 200

    from models.organization_membership import OrganizationMembership
    from models.patient import Patient
    from models.patient_clinician_assignment import PatientClinicianAssignment

    patient = db_session.query(Patient).filter(
        Patient.id == patient_sessions.json()[0]["patient_id"]
    ).one()
    membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == patient.organization_id,
        OrganizationMembership.user_id == clinician_me.json()["id"],
        OrganizationMembership.ended_at.is_(None),
    ).one()
    assignment = PatientClinicianAssignment(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        clinician_membership_id=membership.id,
        clinician_user_id=clinician_me.json()["id"],
        assigned_by_user_id=None,
    )
    db_session.add(assignment)
    db_session.commit()

    assigned_response = client.post(
        "/ai/predict",
        headers=clinician_headers,
        json={"sensor_data_chunk_id": chunk["id"]},
    )
    assert assigned_response.status_code == 503
    assert "not available" in assigned_response.json()["detail"].lower()

    assignment.ends_at = datetime.now(timezone.utc)
    db_session.commit()
    ended_assignment_response = client.post(
        "/ai/predict",
        headers=clinician_headers,
        json={"sensor_data_chunk_id": chunk["id"]},
    )
    assert ended_assignment_response.status_code == 404
