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


def test_public_register_rejects_admin_role(client):
    response = client.post(
        "/auth/register",
        json={"email": "public-admin@example.com", "password": "password123", "role": "admin"},
    )

    assert response.status_code == 403
    assert "administrator" in response.json()["detail"]


def test_patient_cannot_provision_clinician(auth_headers, client):
    patient_headers = auth_headers(email="admin-denied-patient@example.com", role="patient")

    response = client.post(
        "/admin/clinicians",
        json={"email": "nakes-denied@example.com", "temporary_password": "password123"},
        headers=patient_headers,
    )

    assert response.status_code == 403


def test_clinician_cannot_provision_clinician(auth_headers, client):
    clinician_headers = auth_headers(email="admin-denied-clinician@example.com", role="clinician")

    response = client.post(
        "/admin/clinicians",
        json={"email": "nakes-denied-2@example.com", "temporary_password": "password123"},
        headers=clinician_headers,
    )

    assert response.status_code == 403


def test_admin_can_provision_and_list_clinician(auth_headers, client, login_user):
    admin_headers = auth_headers(email="admin@example.com", role="admin")

    response = client.post(
        "/admin/clinicians",
        json={"email": "new-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["temporary_password"] == "password123"
    assert data["user"]["email"] == "new-clinician@example.com"
    assert data["user"]["role"] == "clinician"
    assert data["user"]["is_active"] is True
    assert data["user"]["must_reset_password"] is True
    assert data["membership_id"]

    login_response = login_user(email="new-clinician@example.com", password="password123")
    assert login_response.status_code == 200

    list_response = client.get("/admin/clinicians", headers=admin_headers)
    assert list_response.status_code == 200
    clinicians = list_response.json()
    assert clinicians["total"] == 1
    assert clinicians["limit"] == 25
    assert clinicians["offset"] == 0
    assert any(item["email"] == "new-clinician@example.com" for item in clinicians["items"])
    listed_clinician = next(
        item for item in clinicians["items"] if item["email"] == "new-clinician@example.com"
    )
    assert listed_clinician["membership_id"] == data["membership_id"]
    assert listed_clinician["membership_role"] == "clinician"

    audit_response = client.get("/admin/audit-logs", headers=admin_headers)
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert audit_logs[0]["action"] == "clinician.provisioned"
    assert audit_logs[0]["target_email"] == "new-clinician@example.com"


def test_admin_can_provision_supervisor_but_cannot_assign_it_as_patient_clinician(
    auth_headers,
    client,
):
    admin_headers = auth_headers(email="admin-supervisor@example.com", role="admin")
    patient_headers = auth_headers(email="supervisor-scope-patient@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers, name="Pasien Scope Supervisor")

    provision_response = client.post(
        "/admin/clinicians",
        json={
            "email": "facility-supervisor@example.com",
            "temporary_password": "password123",
            "membership_role": "supervisor",
        },
        headers=admin_headers,
    )
    assert provision_response.status_code == 201
    supervisor_id = provision_response.json()["user"]["id"]

    listed = client.get("/admin/clinicians", headers=admin_headers)
    assert listed.status_code == 200
    supervisor = next(item for item in listed.json()["items"] if item["id"] == supervisor_id)
    assert supervisor["membership_role"] == "supervisor"

    assignment = client.post(
        "/admin/patient-assignments",
        json={
            "patient_id": patient["id"],
            "clinician_id": supervisor_id,
            "care_role": "primary",
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 404

    deactivate = client.post(
        f"/admin/clinicians/{supervisor_id}/deactivate",
        headers=admin_headers,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False


def test_inactive_user_cannot_login_or_use_existing_token(client, create_user, login_user):
    inactive_user = create_user(
        email="inactive-clinician@example.com",
        password="password123",
        role="clinician",
        is_active=False,
    )

    login_response = login_user(email="inactive-clinician@example.com", password="password123")
    assert login_response.status_code == 403

    from core.security import create_access_token

    token = create_access_token(subject=inactive_user.id, role="clinician")
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_deactivate_and_reactivate_clinician(auth_headers, client, login_user):
    admin_headers = auth_headers(email="admin-status@example.com", role="admin")
    provision_response = client.post(
        "/admin/clinicians",
        json={"email": "status-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )
    assert provision_response.status_code == 201
    clinician_id = provision_response.json()["user"]["id"]
    initial_login = login_user(email="status-clinician@example.com", password="password123")
    assert initial_login.status_code == 200
    initial_tokens = initial_login.json()
    initial_headers = {"Authorization": f"Bearer {initial_tokens['access_token']}"}

    deactivate_response = client.post(
        f"/admin/clinicians/{clinician_id}/deactivate",
        headers=admin_headers,
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    inactive_access = client.get("/auth/me", headers=initial_headers)
    inactive_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": initial_tokens["refresh_token"]},
    )
    assert inactive_access.status_code == 403
    assert inactive_refresh.status_code == 401

    blocked_login = login_user(email="status-clinician@example.com", password="password123")
    assert blocked_login.status_code == 403

    activate_response = client.post(
        f"/admin/clinicians/{clinician_id}/activate",
        headers=admin_headers,
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True

    reactivated_old_access = client.get("/auth/me", headers=initial_headers)
    reactivated_old_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": initial_tokens["refresh_token"]},
    )
    assert reactivated_old_access.status_code == 401
    assert reactivated_old_refresh.status_code == 401

    login_response = login_user(email="status-clinician@example.com", password="password123")
    assert login_response.status_code == 200

    audit_response = client.get("/admin/audit-logs?limit=5", headers=admin_headers)
    actions = [item["action"] for item in audit_response.json()]
    assert "clinician.deactivated" in actions
    assert "clinician.activated" in actions


def test_admin_can_reset_clinician_password(auth_headers, client, login_user):
    admin_headers = auth_headers(email="admin-reset-clinician@example.com", role="admin")
    provision_response = client.post(
        "/admin/clinicians",
        json={"email": "reset-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )
    assert provision_response.status_code == 201
    clinician_id = provision_response.json()["user"]["id"]
    initial_login = login_user(email="reset-clinician@example.com", password="password123")
    assert initial_login.status_code == 200
    initial_tokens = initial_login.json()
    initial_headers = {"Authorization": f"Bearer {initial_tokens['access_token']}"}

    reset_response = client.post(
        f"/admin/clinicians/{clinician_id}/reset-password",
        json={"temporary_password": "password456"},
        headers=admin_headers,
    )
    assert reset_response.status_code == 200
    reset_data = reset_response.json()
    assert reset_data["temporary_password"] == "password456"
    assert reset_data["user"]["must_reset_password"] is True

    old_access = client.get("/auth/me", headers=initial_headers)
    old_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": initial_tokens["refresh_token"]},
    )
    assert old_access.status_code == 401
    assert old_refresh.status_code == 401

    old_login = login_user(email="reset-clinician@example.com", password="password123")
    assert old_login.status_code == 401
    new_login = login_user(email="reset-clinician@example.com", password="password456")
    assert new_login.status_code == 200

    audit_response = client.get("/admin/audit-logs?limit=5", headers=admin_headers)
    assert audit_response.json()[0]["action"] == "clinician.password_reset"


def test_patient_cannot_deactivate_or_reset_clinician(auth_headers, client):
    admin_headers = auth_headers(email="admin-protect-action@example.com", role="admin")
    patient_headers = auth_headers(email="patient-protect-action@example.com", role="patient")
    provision_response = client.post(
        "/admin/clinicians",
        json={"email": "protected-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )
    clinician_id = provision_response.json()["user"]["id"]

    deactivate_response = client.post(
        f"/admin/clinicians/{clinician_id}/deactivate",
        headers=patient_headers,
    )
    reset_response = client.post(
        f"/admin/clinicians/{clinician_id}/reset-password",
        json={"temporary_password": "password456"},
        headers=patient_headers,
    )

    assert deactivate_response.status_code == 403
    assert reset_response.status_code == 403


def test_admin_provision_rejects_duplicate_email(auth_headers, client):
    admin_headers = auth_headers(email="admin-duplicate@example.com", role="admin")
    payload = {"email": "duplicate-clinician@example.com", "temporary_password": "password123"}

    first_response = client.post("/admin/clinicians", json=payload, headers=admin_headers)
    second_response = client.post("/admin/clinicians", json=payload, headers=admin_headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 400


def test_admin_must_change_temporary_password_before_provisioning(client, create_user, login_user):
    create_user(
        email="admin-reset-required@example.com",
        password="password123",
        role="admin",
        must_reset_password=True,
    )
    login_response = login_user(email="admin-reset-required@example.com", password="password123")
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked_response = client.post(
        "/admin/clinicians",
        json={"email": "blocked-clinician@example.com", "temporary_password": "password123"},
        headers=headers,
    )
    assert blocked_response.status_code == 403

    reset_response = client.post(
        "/auth/password",
        json={"current_password": "password123", "new_password": "password456"},
        headers=headers,
    )
    assert reset_response.status_code == 200

    new_login_response = login_user(email="admin-reset-required@example.com", password="password456")
    new_token = new_login_response.json()["access_token"]
    unblocked_response = client.post(
        "/admin/clinicians",
        json={"email": "unblocked-clinician@example.com", "temporary_password": "password123"},
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert unblocked_response.status_code == 201


def test_admin_can_bulk_provision_clinicians(auth_headers, client, login_user):
    admin_headers = auth_headers(email="admin-bulk@example.com", role="admin")

    response = client.post(
        "/admin/clinicians/bulk",
        json={"emails": ["bulk-one@example.com", "bulk-two@example.com"]},
        headers=admin_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["clinicians"]) == 2

    for provisioned in data["clinicians"]:
        assert provisioned["user"]["role"] == "clinician"
        assert provisioned["user"]["must_reset_password"] is True
        assert provisioned["temporary_password"]
        login_response = login_user(
            email=provisioned["user"]["email"],
            password=provisioned["temporary_password"],
        )
        assert login_response.status_code == 200


def test_admin_bulk_provision_rejects_duplicate_input(auth_headers, client):
    admin_headers = auth_headers(email="admin-bulk-duplicate@example.com", role="admin")

    response = client.post(
        "/admin/clinicians/bulk",
        json={"emails": ["same@example.com", "same@example.com"]},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_admin_list_clinicians_supports_search_and_pagination(auth_headers, client):
    admin_headers = auth_headers(email="admin-search@example.com", role="admin")
    for email in ("alpha-nakes@example.com", "beta-nakes@example.com", "gamma-nakes@example.com"):
        response = client.post(
            "/admin/clinicians",
            json={"email": email, "temporary_password": "password123"},
            headers=admin_headers,
        )
        assert response.status_code == 201

    first_page = client.get("/admin/clinicians?limit=2&offset=0", headers=admin_headers)
    assert first_page.status_code == 200
    first_page_data = first_page.json()
    assert first_page_data["total"] == 3
    assert len(first_page_data["items"]) == 2

    search_response = client.get("/admin/clinicians?q=beta", headers=admin_headers)
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["email"] == "beta-nakes@example.com"


def test_patient_cannot_read_admin_audit_logs(auth_headers, client):
    patient_headers = auth_headers(email="audit-denied-patient@example.com", role="patient")

    response = client.get("/admin/audit-logs", headers=patient_headers)

    assert response.status_code == 403


def test_admin_can_assign_and_unassign_patient_to_clinician(auth_headers, client):
    admin_headers = auth_headers(email="admin-assign@example.com", role="admin")
    patient_headers = auth_headers(email="assigned-patient@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers, name="Nur Aisyah")
    clinician_response = client.post(
        "/admin/clinicians",
        json={"email": "assigned-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )
    assert clinician_response.status_code == 201
    clinician = clinician_response.json()["user"]

    empty_list_response = client.get("/admin/patients", headers=admin_headers)
    assert empty_list_response.status_code == 200
    assert empty_list_response.json()["items"][0]["assigned_clinicians"] == []

    assign_response = client.post(
        "/admin/patient-assignments",
        json={"patient_id": patient["id"], "clinician_id": clinician["id"]},
        headers=admin_headers,
    )
    assert assign_response.status_code == 201
    assignment = assign_response.json()
    assert assignment["patient_id"] == patient["id"]
    assert assignment["clinician_id"] == clinician["id"]
    assert assignment["assigned_by_user_id"] is not None

    duplicate_response = client.post(
        "/admin/patient-assignments",
        json={"patient_id": patient["id"], "clinician_id": clinician["id"]},
        headers=admin_headers,
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "PRIMARY_CLINICIAN_ALREADY_ASSIGNED"

    list_response = client.get("/admin/patients?q=nur", headers=admin_headers)
    assert list_response.status_code == 200
    patient_item = list_response.json()["items"][0]
    assert patient_item["name"] == "Nur Aisyah"
    assert patient_item["assigned_clinicians"][0]["email"] == "assigned-clinician@example.com"

    unassign_response = client.delete(
        f"/admin/patient-assignments/{assignment['id']}",
        headers=admin_headers,
    )
    assert unassign_response.status_code == 200
    assert unassign_response.json()["id"] == assignment["id"]

    audit_response = client.get("/admin/audit-logs?limit=5", headers=admin_headers)
    actions = [item["action"] for item in audit_response.json()]
    assert "patient.assigned_to_clinician" in actions
    assert "patient.unassigned_from_clinician" in actions


def test_admin_assignment_rejects_inactive_clinician(auth_headers, client):
    admin_headers = auth_headers(email="admin-inactive-assignment@example.com", role="admin")
    patient_headers = auth_headers(email="inactive-assignment-patient@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers, name="Mira Putri")
    clinician_response = client.post(
        "/admin/clinicians",
        json={"email": "inactive-assignment-clinician@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    )
    clinician_id = clinician_response.json()["user"]["id"]
    deactivate_response = client.post(
        f"/admin/clinicians/{clinician_id}/deactivate",
        headers=admin_headers,
    )
    assert deactivate_response.status_code == 200

    assign_response = client.post(
        "/admin/patient-assignments",
        json={"patient_id": patient["id"], "clinician_id": clinician_id},
        headers=admin_headers,
    )

    assert assign_response.status_code == 400


def test_primary_assignment_conflict_does_not_block_supporting_clinician(auth_headers, client):
    admin_headers = auth_headers(email="admin-care-role@example.com", role="admin")
    patient_headers = auth_headers(email="care-role-patient@example.com", role="patient")
    patient = create_patient_profile(client, patient_headers, name="Pasien Care Role")
    primary = client.post(
        "/admin/clinicians",
        json={"email": "care-role-primary@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    ).json()["user"]
    supporting = client.post(
        "/admin/clinicians",
        json={"email": "care-role-supporting@example.com", "temporary_password": "password123"},
        headers=admin_headers,
    ).json()["user"]

    first_primary = client.post(
        "/admin/patient-assignments",
        json={"patient_id": patient["id"], "clinician_id": primary["id"], "care_role": "primary"},
        headers=admin_headers,
    )
    second_primary = client.post(
        "/admin/patient-assignments",
        json={
            "patient_id": patient["id"],
            "clinician_id": supporting["id"],
            "care_role": "primary",
        },
        headers=admin_headers,
    )
    supporting_assignment = client.post(
        "/admin/patient-assignments",
        json={
            "patient_id": patient["id"],
            "clinician_id": supporting["id"],
            "care_role": "supporting",
        },
        headers=admin_headers,
    )

    assert first_primary.status_code == 201
    assert second_primary.status_code == 409
    assert second_primary.json()["detail"]["code"] == "PRIMARY_CLINICIAN_ALREADY_ASSIGNED"
    assert supporting_assignment.status_code == 201
    assert supporting_assignment.json()["care_role"] == "supporting"


def test_non_admin_cannot_manage_patient_assignments(auth_headers, client):
    patient_headers = auth_headers(email="assignment-denied-patient@example.com", role="patient")

    list_response = client.get("/admin/patients", headers=patient_headers)
    assign_response = client.post(
        "/admin/patient-assignments",
        json={"patient_id": "patient-id", "clinician_id": "clinician-id"},
        headers=patient_headers,
    )

    assert list_response.status_code == 403
    assert assign_response.status_code == 403
