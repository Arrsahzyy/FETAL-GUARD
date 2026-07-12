FORBIDDEN_MEDICAL_TERMS = ("abnormal", "gawat janin", "penyakit", "diagnosis")
SAFE_CLASSIFICATIONS = {
    "Dalam Batas Normal",
    "Waspada",
    "Perlu Observasi",
    "Rujuk ke Faskes",
}


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


def test_ai_predict_returns_safe_screening_stub_response(client, auth_headers):
    headers = auth_headers(email="ai-patient@example.com", role="patient")
    chunk = create_sensor_chunk(client, headers)

    response = client.post(
        "/ai/predict",
        headers=headers,
        json={"sensor_data_chunk_id": chunk["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["risk_score"] <= 1.0
    assert data["classification"] in SAFE_CLASSIFICATIONS
    assert "skrining awal" in data["message"].lower()

    serialized = str(data).lower()
    assert all(term not in serialized for term in FORBIDDEN_MEDICAL_TERMS)


def test_ai_predict_requires_valid_jwt(client):
    response = client.post("/ai/predict", json={"sensor_data_chunk_id": "missing"})

    assert response.status_code == 401
