import json
from datetime import datetime, timezone

from core.tenancy import DEFAULT_ORGANIZATION_ID
from models.access_audit_event import AccessAuditEvent
from models.admin_audit_log import AdminAuditLog
from models.alert_event import AlertEvent
from models.device_assignment import DeviceAssignment
from models.notification import Notification
from models.organization import Organization
from models.organization_membership import OrganizationMembership
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment


SECOND_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000002"


def bearer_headers(client, email: str, password: str = "password123", organization_id: str | None = None):
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    if organization_id:
        headers["X-Organization-ID"] = organization_id
    return headers


def add_second_organization(db_session) -> Organization:
    organization = Organization(
        id=SECOND_ORGANIZATION_ID,
        slug="hospital-secondary",
        name="Hospital Secondary",
    )
    db_session.add(organization)
    db_session.commit()
    return organization


def move_staff_to_second_organization(db_session, user, membership_role: str):
    default_membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == DEFAULT_ORGANIZATION_ID,
            OrganizationMembership.ended_at.is_(None),
        )
        .one()
    )
    default_membership.ended_at = datetime.now(timezone.utc)
    membership = OrganizationMembership(
        organization_id=SECOND_ORGANIZATION_ID,
        user_id=user.id,
        role=membership_role,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def create_patient_in_organization(db_session, user, organization_id: str, name: str) -> Patient:
    patient = Patient(
        organization_id=organization_id,
        user_id=user.id,
        name=name,
        age=29,
        gestational_age_weeks=31,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_admin_and_clinician_cannot_cross_facility_boundary(client, create_user, db_session):
    add_second_organization(db_session)
    patient_user = create_user(email="tenant-b-patient@example.com", role="patient")
    patient = create_patient_in_organization(
        db_session,
        patient_user,
        SECOND_ORGANIZATION_ID,
        "Pasien Fasilitas B",
    )
    clinician_b = create_user(email="tenant-b-clinician@example.com", role="clinician")
    move_staff_to_second_organization(db_session, clinician_b, "clinician")
    admin_b = create_user(email="tenant-b-admin@example.com", role="admin")
    move_staff_to_second_organization(db_session, admin_b, "org_admin")
    admin_a = create_user(email="tenant-a-admin@example.com", role="admin")

    admin_a_headers = bearer_headers(client, admin_a.email)
    forbidden_assignment = client.post(
        "/admin/patient-assignments",
        headers=admin_a_headers,
        json={"patient_id": patient.id, "clinician_id": clinician_b.id},
    )
    assert forbidden_assignment.status_code == 404

    admin_b_headers = bearer_headers(client, admin_b.email, organization_id=SECOND_ORGANIZATION_ID)
    assignment = client.post(
        "/admin/patient-assignments",
        headers=admin_b_headers,
        json={"patient_id": patient.id, "clinician_id": clinician_b.id},
    )
    assert assignment.status_code == 201
    assert assignment.json()["organization_id"] == SECOND_ORGANIZATION_ID

    clinician_b_headers = bearer_headers(
        client,
        clinician_b.email,
        organization_id=SECOND_ORGANIZATION_ID,
    )
    visible = client.get("/clinician/patients", headers=clinician_b_headers)
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()["items"]] == [patient.id]

    wrong_context = client.get(
        "/clinician/patients",
        headers={**clinician_b_headers, "X-Organization-ID": DEFAULT_ORGANIZATION_ID},
    )
    assert wrong_context.status_code == 403


def test_device_registration_and_assignment_are_facility_scoped(
    client,
    create_user,
    db_session,
):
    add_second_organization(db_session)
    patient_user = create_user(email="tenant-device-patient@example.com", role="patient")
    patient = create_patient_in_organization(
        db_session,
        patient_user,
        SECOND_ORGANIZATION_ID,
        "Pasien Perangkat Fasilitas B",
    )
    admin_a = create_user(email="tenant-device-admin-a@example.com", role="admin")
    admin_b = create_user(email="tenant-device-admin-b@example.com", role="admin")
    move_staff_to_second_organization(db_session, admin_b, "org_admin")
    admin_a_headers = bearer_headers(client, admin_a.email)
    admin_b_headers = bearer_headers(
        client,
        admin_b.email,
        organization_id=SECOND_ORGANIZATION_ID,
    )
    request_body = {
        "device_uid": "FG-BELT-TENANT-B",
        "patient_id": patient.id,
        "display_name": "FETAL-GUARD Fasilitas B",
        "status": "active",
    }

    cross_facility = client.post("/devices", headers=admin_a_headers, json=request_body)
    allowed = client.post("/devices", headers=admin_b_headers, json=request_body)

    assert cross_facility.status_code == 404
    assert allowed.status_code == 201
    assert allowed.json()["organization_id"] == SECOND_ORGANIZATION_ID
    assignment = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == allowed.json()["id"])
        .one()
    )
    assert assignment.organization_id == SECOND_ORGANIZATION_ID
    assert assignment.patient_id == patient.id

    patient_headers = bearer_headers(client, patient_user.email)
    patient_devices = client.get("/devices/me", headers=patient_headers)
    assert patient_devices.status_code == 200
    assert [item["id"] for item in patient_devices.json()] == [allowed.json()["id"]]


def test_multiple_facilities_require_explicit_context_and_supervisor_is_facility_scoped(
    client,
    create_user,
    db_session,
):
    add_second_organization(db_session)
    supervisor = create_user(email="multi-supervisor@example.com", role="clinician")
    second_membership = OrganizationMembership(
        organization_id=SECOND_ORGANIZATION_ID,
        user_id=supervisor.id,
        role="supervisor",
    )
    db_session.add(second_membership)
    patient_user = create_user(email="supervisor-patient@example.com", role="patient")
    patient = create_patient_in_organization(
        db_session,
        patient_user,
        SECOND_ORGANIZATION_ID,
        "Pasien Dalam Fasilitas Supervisor",
    )
    db_session.commit()

    headers = bearer_headers(client, supervisor.email)
    missing_context = client.get("/clinician/patients", headers=headers)
    assert missing_context.status_code == 400
    assert missing_context.json()["detail"]["code"] == "FACILITY_CONTEXT_REQUIRED"

    scoped = client.get(
        "/clinician/patients",
        headers={**headers, "X-Organization-ID": SECOND_ORGANIZATION_ID},
    )
    assert scoped.status_code == 200
    assert [item["id"] for item in scoped.json()["items"]] == [patient.id]


def test_unassignment_is_temporal_and_immediately_revokes_clinician_scope(
    client,
    auth_headers,
    db_session,
):
    patient_headers = auth_headers(email="temporal-patient@example.com", role="patient")
    patient_response = client.post(
        "/patients",
        headers=patient_headers,
        json={"name": "Pasien Temporal", "age": 28, "gestational_age_weeks": 30},
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.json()["id"]

    clinician_headers = auth_headers(email="temporal-clinician@example.com", role="clinician")
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    admin_headers = auth_headers(email="temporal-admin@example.com", role="admin")
    assignment_response = client.post(
        "/admin/patient-assignments",
        headers=admin_headers,
        json={"patient_id": patient_id, "clinician_id": clinician_id},
    )
    assert assignment_response.status_code == 201
    assignment_id = assignment_response.json()["id"]

    before = client.get("/clinician/patients", headers=clinician_headers)
    assert before.json()["total"] == 1

    ended = client.delete(f"/admin/patient-assignments/{assignment_id}", headers=admin_headers)
    assert ended.status_code == 200
    assert ended.json()["ends_at"] is not None

    after = client.get("/clinician/patients", headers=clinician_headers)
    assert after.status_code == 200
    assert after.json()["total"] == 0

    stored_assignment = db_session.get(PatientClinicianAssignment, assignment_id)
    assert stored_assignment is not None
    assert stored_assignment.ends_at is not None
    assert stored_assignment.ended_by_user_id is not None


def test_clinical_list_read_creates_scoped_access_audit(client, auth_headers, db_session):
    clinician_headers = auth_headers(email="audit-clinician@example.com", role="clinician")

    response = client.get(
        "/clinician/patients",
        headers={**clinician_headers, "X-Request-ID": "audit-request-001"},
    )
    assert response.status_code == 200
    event = (
        db_session.query(AccessAuditEvent)
        .filter(AccessAuditEvent.request_id == "audit-request-001")
        .one()
    )
    assert event.action == "clinical.patient_list.read"
    assert event.organization_id == DEFAULT_ORGANIZATION_ID
    assert event.outcome == "success"


def test_alert_update_uses_optimistic_version_and_immutable_events(
    client,
    auth_headers,
    db_session,
):
    patient_headers = auth_headers(email="version-patient@example.com", role="patient")
    patient_response = client.post(
        "/patients",
        headers=patient_headers,
        json={"name": "Pasien Versioned", "age": 27, "gestational_age_weeks": 29},
    )
    session_response = client.post("/sessions", headers=patient_headers)
    assert patient_response.status_code == 201
    assert session_response.status_code == 201

    alert = Notification(
        session_id=session_response.json()["id"],
        message="Indikasi awal perlu ditinjau",
        risk_level="medium",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    clinician_headers = auth_headers(email="version-clinician@example.com", role="clinician")
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    admin_headers = auth_headers(email="version-admin@example.com", role="admin")
    assignment = client.post(
        "/admin/patient-assignments",
        headers=admin_headers,
        json={"patient_id": patient_response.json()["id"], "clinician_id": clinician_id},
    )
    assert assignment.status_code == 201

    first_update = client.patch(
        f"/clinician/alerts/{alert.id}/status",
        headers=clinician_headers,
        json={
            "status": "in_review",
            "note": "Ditinjau oleh nakes penanggung jawab.",
            "expected_version": 1,
        },
    )
    stale_update = client.patch(
        f"/clinician/alerts/{alert.id}/status",
        headers=clinician_headers,
        json={
            "status": "resolved",
            "note": "Update dengan versi lama.",
            "expected_version": 1,
        },
    )

    assert first_update.status_code == 200
    assert first_update.json()["version"] == 2
    assert stale_update.status_code == 409
    assert stale_update.json()["detail"]["code"] == "ALERT_VERSION_CONFLICT"
    events = (
        db_session.query(AlertEvent)
        .filter(AlertEvent.notification_id == alert.id)
        .order_by(AlertEvent.version.asc())
        .all()
    )
    assert [(event.from_status, event.to_status, event.version) for event in events] == [
        ("open", "in_review", 2)
    ]


def test_inactive_facility_is_removed_from_memberships_and_rejected_as_scope(
    client,
    create_user,
    db_session,
):
    organization = add_second_organization(db_session)
    clinician = create_user(email="inactive-facility-clinician@example.com", role="clinician")
    move_staff_to_second_organization(db_session, clinician, "clinician")
    headers = bearer_headers(client, clinician.email, organization_id=SECOND_ORGANIZATION_ID)

    organization.is_active = False
    db_session.commit()

    memberships = client.get("/organizations/me", headers=headers)
    scoped_request = client.get("/clinician/patients", headers=headers)

    assert memberships.status_code == 200
    assert memberships.json()["items"] == []
    assert scoped_request.status_code == 403
    assert scoped_request.json()["detail"]["code"] == "SCOPE_REVOKED"


def test_facility_admin_cannot_mutate_identity_used_by_another_facility(
    client,
    create_user,
    db_session,
):
    add_second_organization(db_session)
    clinician = create_user(email="shared-clinician@example.com", role="clinician")
    db_session.add(
        OrganizationMembership(
            organization_id=SECOND_ORGANIZATION_ID,
            user_id=clinician.id,
            role="clinician",
        )
    )
    db_session.commit()
    admin = create_user(email="facility-admin@example.com", role="admin")
    admin_headers = bearer_headers(client, admin.email)

    deactivate = client.post(
        f"/admin/clinicians/{clinician.id}/deactivate",
        headers=admin_headers,
    )
    reset_password = client.post(
        f"/admin/clinicians/{clinician.id}/reset-password",
        headers=admin_headers,
        json={},
    )

    assert deactivate.status_code == 409
    assert deactivate.json()["detail"]["code"] == "CENTRAL_IDENTITY_ADMIN_REQUIRED"
    assert reset_password.status_code == 409
    assert reset_password.json()["detail"]["code"] == "CENTRAL_IDENTITY_ADMIN_REQUIRED"
    db_session.refresh(clinician)
    assert clinician.is_active is True
    assert clinician.auth_version == 0


def test_clinician_statistics_only_aggregate_authorized_active_records(
    client,
    auth_headers,
    db_session,
):
    clinician_headers = auth_headers(email="stats-clinician@example.com", role="clinician")
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    admin_headers = auth_headers(email="stats-admin@example.com", role="admin")

    assigned_patient_headers = auth_headers(email="stats-assigned@example.com", role="patient")
    assigned_patient = client.post(
        "/patients",
        headers=assigned_patient_headers,
        json={"name": "Pasien Ditugaskan", "age": 30, "gestational_age_weeks": 32},
    ).json()
    assigned_session = client.post("/sessions", headers=assigned_patient_headers).json()
    assignment = client.post(
        "/admin/patient-assignments",
        headers=admin_headers,
        json={"patient_id": assigned_patient["id"], "clinician_id": clinician_id},
    )
    assert assignment.status_code == 201

    unassigned_patient_headers = auth_headers(email="stats-unassigned@example.com", role="patient")
    unassigned_patient = client.post(
        "/patients",
        headers=unassigned_patient_headers,
        json={"name": "Pasien Tidak Ditugaskan", "age": 31, "gestational_age_weeks": 33},
    ).json()
    unassigned_session = client.post("/sessions", headers=unassigned_patient_headers).json()

    db_session.add_all(
        [
            Notification(
                session_id=assigned_session["id"],
                message="Perlu observasi oleh nakes",
                risk_level="high",
                status="open",
            ),
            Notification(
                session_id=assigned_session["id"],
                message="Riwayat sudah selesai",
                risk_level="high",
                status="resolved",
                is_acknowledged=True,
            ),
            Notification(
                session_id=unassigned_session["id"],
                message="Tidak boleh masuk agregat nakes lain",
                risk_level="high",
                status="open",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/clinician/statistics", headers=clinician_headers)

    assert response.status_code == 200
    assert response.json() == {
        "total_patients": 1,
        "active_monitoring": 1,
        "high_priority_patients": 1,
        "open_alerts": 1,
    }
    assert unassigned_patient["id"] != assigned_patient["id"]


def test_facility_membership_revocation_is_atomic_idempotent_and_preserves_other_facility(
    client,
    create_user,
    db_session,
):
    add_second_organization(db_session)
    clinician = create_user(email="revocation-shared-clinician@example.com", role="clinician")
    membership_a = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == clinician.id,
            OrganizationMembership.organization_id == DEFAULT_ORGANIZATION_ID,
            OrganizationMembership.ended_at.is_(None),
        )
        .one()
    )
    membership_b = OrganizationMembership(
        organization_id=SECOND_ORGANIZATION_ID,
        user_id=clinician.id,
        role="clinician",
    )
    db_session.add(membership_b)

    admin_a = create_user(email="revocation-admin-a@example.com", role="admin")
    admin_b = create_user(email="revocation-admin-b@example.com", role="admin")
    move_staff_to_second_organization(db_session, admin_b, "org_admin")
    patient_a_user = create_user(email="revocation-patient-a@example.com", role="patient")
    patient_b_user = create_user(email="revocation-patient-b@example.com", role="patient")
    patient_a = create_patient_in_organization(
        db_session,
        patient_a_user,
        DEFAULT_ORGANIZATION_ID,
        "Pasien Revokasi A",
    )
    patient_b = create_patient_in_organization(
        db_session,
        patient_b_user,
        SECOND_ORGANIZATION_ID,
        "Pasien Revokasi B",
    )
    db_session.commit()
    db_session.refresh(membership_b)

    admin_a_headers = bearer_headers(
        client,
        admin_a.email,
        organization_id=DEFAULT_ORGANIZATION_ID,
    )
    admin_b_headers = bearer_headers(
        client,
        admin_b.email,
        organization_id=SECOND_ORGANIZATION_ID,
    )
    clinician_a_headers = bearer_headers(
        client,
        clinician.email,
        organization_id=DEFAULT_ORGANIZATION_ID,
    )
    clinician_b_headers = bearer_headers(
        client,
        clinician.email,
        organization_id=SECOND_ORGANIZATION_ID,
    )

    assignment_a_response = client.post(
        "/admin/patient-assignments",
        headers=admin_a_headers,
        json={"patient_id": patient_a.id, "clinician_id": clinician.id},
    )
    assignment_b_response = client.post(
        "/admin/patient-assignments",
        headers=admin_b_headers,
        json={"patient_id": patient_b.id, "clinician_id": clinician.id},
    )
    assert assignment_a_response.status_code == 201
    assert assignment_b_response.status_code == 201
    assignment_a_id = assignment_a_response.json()["id"]
    assignment_b_id = assignment_b_response.json()["id"]

    before_a = client.get("/clinician/patients", headers=clinician_a_headers)
    before_b = client.get("/clinician/patients", headers=clinician_b_headers)
    assert [item["id"] for item in before_a.json()["items"]] == [patient_a.id]
    assert [item["id"] for item in before_b.json()["items"]] == [patient_b.id]

    cross_facility_attempt = client.delete(
        f"/admin/clinician-memberships/{membership_a.id}",
        headers=admin_b_headers,
    )
    assert cross_facility_attempt.status_code == 404
    assert cross_facility_attempt.json()["detail"]["code"] == "CLINICIAN_MEMBERSHIP_NOT_FOUND"

    revoked = client.delete(
        f"/admin/clinician-memberships/{membership_a.id}",
        headers=admin_a_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["membership_id"] == membership_a.id
    assert revoked.json()["organization_id"] == DEFAULT_ORGANIZATION_ID
    assert revoked.json()["clinician_id"] == clinician.id
    assert revoked.json()["ended_assignment_count"] == 1
    assert revoked.json()["already_revoked"] is False
    assert revoked.json()["ended_by_user_id"] == admin_a.id

    db_session.expire_all()
    stored_membership_a = db_session.get(OrganizationMembership, membership_a.id)
    first_ended_at = stored_membership_a.ended_at
    assert first_ended_at is not None

    repeated = client.delete(
        f"/admin/clinician-memberships/{membership_a.id}",
        headers=admin_a_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["ended_assignment_count"] == 0
    assert repeated.json()["already_revoked"] is True

    db_session.expire_all()
    stored_membership_a = db_session.get(OrganizationMembership, membership_a.id)
    stored_membership_b = db_session.get(OrganizationMembership, membership_b.id)
    stored_assignment_a = db_session.get(PatientClinicianAssignment, assignment_a_id)
    stored_assignment_b = db_session.get(PatientClinicianAssignment, assignment_b_id)
    stored_clinician = db_session.get(type(clinician), clinician.id)
    assert stored_membership_a.ended_at == first_ended_at
    assert stored_membership_a.ended_by_user_id == admin_a.id
    assert stored_membership_b.ended_at is None
    assert stored_assignment_a.ends_at is not None
    assert stored_assignment_a.ended_by_user_id == admin_a.id
    assert stored_assignment_a.version == 2
    assert stored_assignment_b.ends_at is None
    assert stored_assignment_b.version == 1
    assert stored_clinician.is_active is True
    assert stored_clinician.auth_version == 0

    denied_a = client.get("/clinician/patients", headers=clinician_a_headers)
    still_allowed_b = client.get("/clinician/patients", headers=clinician_b_headers)
    assert denied_a.status_code == 403
    assert denied_a.json()["detail"]["code"] == "SCOPE_REVOKED"
    assert still_allowed_b.status_code == 200
    assert [item["id"] for item in still_allowed_b.json()["items"]] == [patient_b.id]

    audit_events = (
        db_session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.organization_id == DEFAULT_ORGANIZATION_ID,
            AdminAuditLog.action == "clinician.facility_access_revoked",
            AdminAuditLog.target_user_id == clinician.id,
        )
        .all()
    )
    assert len(audit_events) == 1
    assert audit_events[0].target_email is None
    assert json.loads(audit_events[0].details) == {
        "ended_assignment_count": 1,
        "membership_id": membership_a.id,
        "repaired_previously_ended_membership": False,
    }
