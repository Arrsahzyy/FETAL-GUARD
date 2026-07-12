def create_patient_profile(client, headers, name="Ayu Lestari"):
    return client.post(
        "/patients",
        headers=headers,
        json={
            "name": name,
            "age": 28,
            "gestational_age_weeks": 32,
            "medical_history": None,
        },
    )


def create_active_session(client, headers, name="Ayu Lestari"):
    patient_response = create_patient_profile(client, headers, name=name)
    assert patient_response.status_code == 201

    session_response = client.post("/sessions", headers=headers)
    assert session_response.status_code == 201
    return session_response.json()


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


def test_patient_role_cannot_access_clinician_patient_dashboard(client, auth_headers):
    patient_headers = auth_headers(email="patient-dashboard@example.com", role="patient")

    response = client.get("/clinician/patients", headers=patient_headers)

    assert response.status_code == 403


def test_patient_role_cannot_access_clinician_alerts(client, auth_headers):
    patient_headers = auth_headers(email="patient-alerts-dashboard@example.com", role="patient")

    response = client.get("/clinician/alerts", headers=patient_headers)

    assert response.status_code == 403


def test_clinician_must_change_temporary_password_before_dashboard(client, create_user, login_user):
    create_user(
        email="clinician-reset-required@example.com",
        password="password123",
        role="clinician",
        must_reset_password=True,
    )
    login_response = login_user(email="clinician-reset-required@example.com", password="password123")
    token = login_response.json()["access_token"]

    response = client.get(
        "/clinician/patients",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_clinician_can_read_patient_dashboard_with_active_session(client, auth_headers):
    patient_headers = auth_headers(email="dashboard-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Siti Rahma")
    unassigned_patient_headers = auth_headers(email="dashboard-unassigned-patient@example.com", role="patient")
    create_active_session(client, unassigned_patient_headers, name="Tidak Ditugaskan")
    clinician_headers = auth_headers(email="dashboard-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="dashboard-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, active_session["patient_id"], clinician_id)

    response = client.get("/clinician/patients", headers=clinician_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["limit"] == 25
    assert data["offset"] == 0
    assert data["items"][0]["name"] == "Siti Rahma"
    assert data["items"][0]["latest_session"]["id"] == active_session["id"]
    assert data["items"][0]["latest_session"]["status"] == "active"
    assert data["items"][0]["active_sessions"][0]["id"] == active_session["id"]


def test_clinician_patient_dashboard_supports_search_and_pagination(client, auth_headers):
    first_patient_headers = auth_headers(email="dashboard-search-one@example.com", role="patient")
    second_patient_headers = auth_headers(email="dashboard-search-two@example.com", role="patient")
    create_active_session(client, first_patient_headers, name="Siti Rahma")
    second_session = create_active_session(client, second_patient_headers, name="Ayu Lestari")
    unassigned_patient_headers = auth_headers(email="dashboard-search-unassigned@example.com", role="patient")
    create_active_session(client, unassigned_patient_headers, name="Ayu Tidak Ditugaskan")
    clinician_headers = auth_headers(email="dashboard-search-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="dashboard-search-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, second_session["patient_id"], clinician_id)

    first_page = client.get("/clinician/patients?limit=1&offset=0", headers=clinician_headers)
    search_response = client.get("/clinician/patients?q=ayu", headers=clinician_headers)
    patient_code = second_session["patient_id"].replace("-", "")[:6]
    code_search_response = client.get(f"/clinician/patients?q=FG-{patient_code}", headers=clinician_headers)

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 1
    assert len(first_page.json()["items"]) == 1
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    assert search_response.json()["items"][0]["name"] == "Ayu Lestari"
    assert code_search_response.status_code == 200
    assert code_search_response.json()["total"] == 1
    assert code_search_response.json()["items"][0]["id"] == second_session["patient_id"]


def test_clinician_patient_dashboard_supports_server_filters(client, auth_headers, db_session):
    from models.notification import Notification

    high_patient_headers = auth_headers(email="filter-high-patient@example.com", role="patient")
    medium_patient_headers = auth_headers(email="filter-medium-patient@example.com", role="patient")
    low_patient_headers = auth_headers(email="filter-low-patient@example.com", role="patient")
    high_session = create_active_session(client, high_patient_headers, name="High Risk Patient")
    medium_session = create_active_session(client, medium_patient_headers, name="Medium Risk Patient")
    low_session = create_active_session(client, low_patient_headers, name="Routine Patient")
    end_response = client.patch(
        f"/sessions/{medium_session['id']}",
        headers=medium_patient_headers,
        json={"status": "completed"},
    )
    assert end_response.status_code == 200
    db_session.add_all(
        [
            Notification(
                session_id=high_session["id"],
                message="Indikasi awal prioritas tinggi",
                risk_level="high",
            ),
            Notification(
                session_id=medium_session["id"],
                message="Indikasi awal perlu observasi",
                risk_level="medium",
            ),
        ]
    )
    db_session.commit()
    clinician_headers = auth_headers(email="filter-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="filter-admin@example.com", role="admin")
    for patient_id in (high_session["patient_id"], medium_session["patient_id"], low_session["patient_id"]):
        assign_patient_to_clinician(client, admin_headers, patient_id, clinician_id)

    high_response = client.get("/clinician/patients?risk=high", headers=clinician_headers)
    medium_response = client.get("/clinician/patients?risk=medium", headers=clinician_headers)
    low_response = client.get("/clinician/patients?risk=low", headers=clinician_headers)
    active_response = client.get("/clinician/patients?status=active&sort=name", headers=clinician_headers)
    inactive_response = client.get("/clinician/patients?status=inactive", headers=clinician_headers)
    alerts_response = client.get("/clinician/patients?risk=alerts", headers=clinician_headers)

    assert high_response.status_code == 200
    assert [item["name"] for item in high_response.json()["items"]] == ["High Risk Patient"]
    assert [item["name"] for item in medium_response.json()["items"]] == ["Medium Risk Patient"]
    assert [item["name"] for item in low_response.json()["items"]] == ["Routine Patient"]
    assert [item["name"] for item in active_response.json()["items"]] == ["High Risk Patient", "Routine Patient"]
    assert [item["name"] for item in inactive_response.json()["items"]] == ["Medium Risk Patient"]
    assert alerts_response.json()["total"] == 2


def test_clinician_alerts_return_only_medium_and_high_notifications(client, auth_headers, db_session):
    from models.notification import Notification

    patient_headers = auth_headers(email="alert-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Rina Putri")
    db_session.add_all(
        [
            Notification(
                session_id=active_session["id"],
                message="Indikasi awal perlu observasi",
                risk_level="medium",
            ),
            Notification(
                session_id=active_session["id"],
                message="Indikasi awal perlu rujuk ke faskes",
                risk_level="high",
            ),
            Notification(
                session_id=active_session["id"],
                message="Indikasi awal dalam batas normal",
                risk_level="low",
            ),
        ]
    )
    db_session.commit()
    clinician_headers = auth_headers(email="alert-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="alert-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, active_session["patient_id"], clinician_id)

    response = client.get("/clinician/alerts", headers=clinician_headers)

    assert response.status_code == 200
    data = response.json()
    assert [item["risk_level"] for item in data] == ["high", "medium"]
    assert all("Indikasi awal" in item["message"] for item in data)


def test_clinician_alerts_support_server_filters(client, auth_headers, db_session):
    from datetime import datetime, timezone

    from models.notification import Notification

    patient_headers = auth_headers(email="alert-filter-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Alert Filter Patient")
    open_high = Notification(
        session_id=active_session["id"],
        message="Indikasi awal prioritas tinggi",
        risk_level="high",
    )
    handled_medium = Notification(
        session_id=active_session["id"],
        message="Indikasi awal telah ditangani",
        risk_level="medium",
        is_acknowledged=True,
        acknowledged_at=datetime.now(timezone.utc),
    )
    db_session.add_all([open_high, handled_medium])
    db_session.commit()
    db_session.refresh(open_high)
    db_session.refresh(handled_medium)
    clinician_headers = auth_headers(email="alert-filter-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="alert-filter-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, active_session["patient_id"], clinician_id)

    open_response = client.get("/clinician/alerts?acknowledged=open", headers=clinician_headers)
    handled_medium_response = client.get(
        "/clinician/alerts?risk=medium&acknowledged=acknowledged",
        headers=clinician_headers,
    )
    patient_scoped_response = client.get(
        f"/clinician/alerts?risk=all&patient_id={active_session['patient_id']}",
        headers=clinician_headers,
    )

    assert open_response.status_code == 200
    assert [item["id"] for item in open_response.json()] == [open_high.id]
    assert handled_medium_response.status_code == 200
    assert [item["id"] for item in handled_medium_response.json()] == [handled_medium.id]
    assert patient_scoped_response.status_code == 200
    assert {item["id"] for item in patient_scoped_response.json()} == {open_high.id, handled_medium.id}


def test_clinician_can_acknowledge_alert_with_actor_and_note(client, auth_headers, db_session):
    from models.notification import Notification

    patient_headers = auth_headers(email="ack-alert-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Maya Putri")
    alert = Notification(
        session_id=active_session["id"],
        message="Indikasi awal perlu observasi nakes",
        risk_level="medium",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    clinician_headers = auth_headers(email="ack-alert-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="ack-alert-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, active_session["patient_id"], clinician_id)

    response = client.post(
        f"/clinician/alerts/{alert.id}/acknowledge",
        json={"note": "Dihubungi untuk tindak lanjut terjadwal."},
        headers=clinician_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_acknowledged"] is True
    assert data["status"] == "acknowledged"
    assert data["acknowledged_at"] is not None
    assert data["acknowledged_by_user_id"] is not None
    assert data["acknowledgement_note"] == "Dihubungi untuk tindak lanjut terjadwal."
    assert data["patient_name"] == "Maya Putri"


def test_clinician_can_update_alert_lifecycle_status(client, auth_headers, db_session):
    from models.notification import Notification

    patient_headers = auth_headers(email="status-alert-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Status Alert Patient")
    alert = Notification(
        session_id=active_session["id"],
        message="Indikasi awal membutuhkan tinjauan",
        risk_level="high",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    clinician_headers = auth_headers(email="status-alert-clinician@example.com", role="clinician")
    clinician_id = get_current_user_id(client, clinician_headers)
    admin_headers = auth_headers(email="status-alert-admin@example.com", role="admin")
    assign_patient_to_clinician(client, admin_headers, active_session["patient_id"], clinician_id)

    review_response = client.patch(
        f"/clinician/alerts/{alert.id}/status",
        json={"status": "in_review", "note": "Sedang ditinjau bersama bidan penanggung jawab."},
        headers=clinician_headers,
    )
    resolved_response = client.patch(
        f"/clinician/alerts/{alert.id}/status",
        json={"status": "resolved", "note": "Tindak lanjut selesai, tetap pantau rutin."},
        headers=clinician_headers,
    )
    resolved_filter_response = client.get(
        "/clinician/alerts?status=resolved",
        headers=clinician_headers,
    )

    assert review_response.status_code == 200
    review_data = review_response.json()
    assert review_data["status"] == "in_review"
    assert review_data["is_acknowledged"] is True
    assert review_data["acknowledged_by_user_id"] == clinician_id
    assert review_data["acknowledgement_note"] == "Sedang ditinjau bersama bidan penanggung jawab."
    assert resolved_response.status_code == 200
    assert resolved_response.json()["status"] == "resolved"
    assert resolved_response.json()["acknowledgement_note"] == "Tindak lanjut selesai, tetap pantau rutin."
    assert [item["id"] for item in resolved_filter_response.json()] == [alert.id]


def test_clinician_cannot_acknowledge_unassigned_alert(client, auth_headers, db_session):
    from models.notification import Notification

    patient_headers = auth_headers(email="unassigned-alert-patient@example.com", role="patient")
    active_session = create_active_session(client, patient_headers, name="Pasien Tidak Ditugaskan")
    alert = Notification(
        session_id=active_session["id"],
        message="Indikasi awal perlu observasi nakes",
        risk_level="medium",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    clinician_headers = auth_headers(email="unassigned-alert-clinician@example.com", role="clinician")

    response = client.post(
        f"/clinician/alerts/{alert.id}/acknowledge",
        json={"note": "Mencoba akses alert tidak ditugaskan."},
        headers=clinician_headers,
    )
    status_response = client.patch(
        f"/clinician/alerts/{alert.id}/status",
        json={"status": "resolved", "note": "Mencoba menutup alert tidak ditugaskan."},
        headers=clinician_headers,
    )

    assert response.status_code == 404
    assert status_response.status_code == 404
