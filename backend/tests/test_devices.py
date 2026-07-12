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
        json={
            "payload": {"t": 1234, "p": [1024]},
            "source": "device",
            "device_uid": "FG-BELT-UNKNOWN",
        },
    )
    inactive_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            "payload": {"t": 1234, "p": [1024]},
            "source": "device",
            "device_uid": "FG-BELT-INACTIVE",
        },
    )

    assert unknown_response.status_code == 404
    assert inactive_response.status_code == 403


def test_device_upload_updates_session_sensor_summary(client, auth_headers):
    patient_headers = auth_headers(email="device-summary-patient@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Ringkasan Sensor")
    admin_headers = auth_headers(email="device-summary-admin@example.com", role="admin")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-BELT-SUMMARY")

    first_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            "payload": {"t": 1234, "p": [1024, 1000], "fsr": [300], "hr_ir": [10000]},
            "source": "device",
            "device_uid": "FG-BELT-SUMMARY",
            "summary": {
                "fhr_estimate_bpm": 142,
                "maternal_hr_bpm": 82,
                "signal_quality_index": 0.84,
                "contraction_indicator": "mild",
            },
        },
    )
    second_response = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            "payload": {"t": 1235, "p": [1028], "fsr": [310]},
            "source": "device",
            "device_uid": "FG-BELT-SUMMARY",
        },
    )
    sessions_response = client.get("/sessions", headers=patient_headers)
    patient_devices_response = client.get("/devices/me", headers=patient_headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    summary = sessions_response.json()[0]["sensor_summary"]
    assert summary["fhr_estimate_bpm"] == 142
    assert summary["maternal_hr_bpm"] == 82
    assert summary["signal_quality_index"] == 0.84
    assert summary["contraction_indicator"] == "mild"
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
            "payload": {"t": 1234, "p": [1024], "fsr": [300]},
            "source": "device",
            "device_uid": "FG-BELT-CLINICIAN",
            "summary": {
                "fhr_estimate_bpm": 138,
                "signal_quality_index": 0.76,
                "contraction_indicator": "none",
            },
        },
    )
    assert upload_response.status_code == 201
    clinician_headers = auth_headers(email="device-clinician-summary-nakes@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    assign_patient_to_clinician(client, admin_headers, session_data["patient_id"], clinician_id)

    response = client.get("/clinician/patients", headers=clinician_headers)

    assert response.status_code == 200
    latest_session = response.json()["items"][0]["latest_session"]
    assert latest_session["sensor_summary"]["fhr_estimate_bpm"] == 138
    assert latest_session["sensor_summary"]["signal_quality_index"] == 0.76


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
        json={
            "payload": {"t": 1234, "p": [1024]},
            "source": "device",
            "device_uid": "FG-BELT-OWNER",
        },
    )

    assert response.status_code == 403
