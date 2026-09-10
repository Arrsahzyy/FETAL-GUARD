def test_patient_ai_status_is_fail_closed_while_pipeline_is_disabled(client, auth_headers):
    patient_headers = auth_headers(email="ai-status-patient@example.com", role="patient")
    response = client.get("/ai/status", headers=patient_headers)

    assert response.status_code == 200
    assert response.json() == {"patient_results_enabled": False}


def test_patient_ai_status_rejects_clinician_role(client, auth_headers):
    clinician_headers = auth_headers(email="ai-status-clinician@example.com", role="clinician")
    response = client.get("/ai/status", headers=clinician_headers)

    assert response.status_code == 403
