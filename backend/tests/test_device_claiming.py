"""Self-service device claiming.

The property under test is the one that motivated the design: a patient can bind
a belt to themselves without an admin, but *only* by proving physical possession
of it. Everything else here exists to make sure that proof cannot be bypassed,
guessed, raced, or stolen from another patient.
"""

from datetime import datetime, timezone

import pytest

from core.device_claim import (
    CLAIM_CODE_ALPHABET,
    CLAIM_CODE_LENGTH,
    generate_claim_code,
    hash_claim_code,
    normalize_claim_code,
    verify_claim_code,
)
from models.device import Device
from models.device_assignment import DeviceAssignment
from tests.test_devices import create_active_session, create_patient_profile, register_device


def issue_claim_code(client, admin_headers, device_id):
    response = client.post(f"/devices/{device_id}/claim-code", headers=admin_headers)
    assert response.status_code == 201, response.json()
    return response.json()["claim_code"]


def setup_unclaimed_device(client, auth_headers, suffix, device_uid=None):
    """Register a device with no patient bound, as a factory-provisioned belt."""
    admin_headers = auth_headers(email=f"claim-admin-{suffix}@example.com", role="admin")
    device_uid = device_uid or f"FG-CLAIM-{suffix.upper()}"
    response = client.post(
        "/devices",
        headers=admin_headers,
        json={
            "device_uid": device_uid,
            "display_name": "FETAL-GUARD Belt",
            "hardware_revision": "bench-demo",
            "firmware_version": "demo-0.1",
            "status": "registered",
        },
    )
    assert response.status_code == 201, response.json()
    device = response.json()
    return admin_headers, device, issue_claim_code(client, admin_headers, device["id"])


def claim(client, patient_headers, device_uid, claim_code):
    return client.post(
        "/devices/claim",
        headers=patient_headers,
        json={"device_uid": device_uid, "claim_code": claim_code},
    )


# ── code encoding ───────────────────────────────────────────────────────────


def test_generated_codes_are_grouped_and_use_the_unambiguous_alphabet():
    code = generate_claim_code()

    assert code[4] == "-"
    assert len(normalize_claim_code(code)) == CLAIM_CODE_LENGTH
    assert all(character in CLAIM_CODE_ALPHABET for character in normalize_claim_code(code))
    for excluded in "ILOU":
        assert excluded not in CLAIM_CODE_ALPHABET


def test_generated_codes_are_not_predictable():
    codes = {generate_claim_code() for _ in range(200)}

    assert len(codes) == 200


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("4h7k-n2qp", "4H7KN2QP"),
        ("4H7K N2QP", "4H7KN2QP"),
        ("  4H7KN2QP  ", "4H7KN2QP"),
        ("4H7K_N2QP", "4H7KN2QP"),
        # Shapes a person confuses when reading a sticker.
        ("4H7K-N2QI", "4H7KN2Q1"),
        ("4H7K-N2QL", "4H7KN2Q1"),
        ("4H7K-N2QO", "4H7KN2Q0"),
    ],
)
def test_hand_typed_codes_are_folded_to_canonical_form(typed, expected):
    assert normalize_claim_code(typed) == expected


@pytest.mark.parametrize("invalid", ["", "SHORT", "4H7K-N2QP-EXTRA", "4H7K-N2Q!", 12345678])
def test_malformed_codes_are_rejected_before_any_comparison(invalid):
    with pytest.raises(ValueError):
        normalize_claim_code(invalid)


def test_verification_is_case_and_format_insensitive_but_value_sensitive():
    code = generate_claim_code()
    hashed = hash_claim_code(code)

    assert verify_claim_code(code, hashed)
    assert verify_claim_code(code.lower().replace("-", " "), hashed)
    assert not verify_claim_code(generate_claim_code(), hashed)
    assert not verify_claim_code(code, None)
    assert not verify_claim_code("not-a-code", hashed)


def test_claim_code_is_never_stored_in_plain_text(client, auth_headers, db_session):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "hash")

    stored = db_session.query(Device).filter(Device.id == device["id"]).one()

    assert stored.claim_code_hash is not None
    assert normalize_claim_code(claim_code) not in stored.claim_code_hash
    assert stored.claim_code_hash.startswith("$2")


# ── the happy path ──────────────────────────────────────────────────────────


def test_patient_claims_an_unclaimed_belt_with_its_printed_code(client, auth_headers):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "ok")
    patient_headers = auth_headers(email="claim-ok@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Klaim")

    response = claim(client, patient_headers, device["device_uid"], claim_code)

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["patient_id"] is not None
    # A belt shipped as 'registered' becomes usable once someone holds it.
    assert body["status"] == "active"

    listed = client.get("/devices/me", headers=patient_headers).json()
    assert [item["device_uid"] for item in listed] == [device["device_uid"]]


def test_claiming_creates_an_auditable_assignment_row(client, auth_headers, db_session):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "assign")
    patient_headers = auth_headers(email="claim-assign@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Assign")

    claim(client, patient_headers, device["device_uid"], claim_code)

    assignments = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .all()
    )
    assert len(assignments) == 1
    assert assignments[0].ends_at is None
    assert assignments[0].assigned_by_user_id is not None


def test_reclaiming_a_belt_you_already_hold_is_idempotent(client, auth_headers, db_session):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "idem")
    patient_headers = auth_headers(email="claim-idem@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Idem")

    first = claim(client, patient_headers, device["device_uid"], claim_code)
    second = claim(client, patient_headers, device["device_uid"], claim_code)

    assert first.status_code == 201
    assert second.status_code == 201
    assignments = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .all()
    )
    assert len(assignments) == 1, "a retry must not open a second ownership interval"


# ── the guarantees that make it safe ────────────────────────────────────────


def test_wrong_code_cannot_claim_the_belt(client, auth_headers):
    _, device, _ = setup_unclaimed_device(client, auth_headers, "wrong")
    patient_headers = auth_headers(email="claim-wrong@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Salah")

    response = claim(client, patient_headers, device["device_uid"], generate_claim_code())

    assert response.status_code == 404
    assert client.get("/devices/me", headers=patient_headers).json() == []


def test_unknown_and_wrong_code_are_indistinguishable(client, auth_headers):
    """Otherwise the endpoint becomes an oracle for enumerating device UIDs."""
    _, device, _ = setup_unclaimed_device(client, auth_headers, "oracle")
    patient_headers = auth_headers(email="claim-oracle@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Oracle")

    wrong_code = claim(client, patient_headers, device["device_uid"], generate_claim_code())
    unknown_uid = claim(client, patient_headers, "FG-DOES-NOT-EXIST", generate_claim_code())

    assert wrong_code.status_code == unknown_uid.status_code == 404
    assert wrong_code.json()["detail"] == unknown_uid.json()["detail"]


def test_a_belt_held_by_another_patient_cannot_be_claimed(client, auth_headers):
    """The 5-identical-belts case: knowing the code must not override ownership."""
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "taken")
    first_headers = auth_headers(email="claim-holder@example.com", role="patient")
    create_patient_profile(client, first_headers, name="Ayu Pemegang")
    assert claim(client, first_headers, device["device_uid"], claim_code).status_code == 201

    second_headers = auth_headers(email="claim-thief@example.com", role="patient")
    create_patient_profile(client, second_headers, name="Ayu Kedua")
    response = claim(client, second_headers, device["device_uid"], claim_code)

    assert response.status_code == 409
    assert client.get("/devices/me", headers=second_headers).json() == []


def test_claim_code_rotation_invalidates_the_previous_code(client, auth_headers):
    admin_headers, device, old_code = setup_unclaimed_device(client, auth_headers, "rotate")
    new_code = issue_claim_code(client, admin_headers, device["id"])
    patient_headers = auth_headers(email="claim-rotate@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Rotasi")

    stale = claim(client, patient_headers, device["device_uid"], old_code)
    fresh = claim(client, patient_headers, device["device_uid"], new_code)

    assert new_code != old_code
    assert stale.status_code == 404
    assert fresh.status_code == 201


def test_device_without_a_claim_code_cannot_be_claimed(client, auth_headers):
    admin_headers = auth_headers(email="claim-nocode-admin@example.com", role="admin")
    response = client.post(
        "/devices",
        headers=admin_headers,
        json={"device_uid": "FG-NO-CODE-01", "display_name": "Belt", "status": "registered"},
    )
    assert response.status_code == 201
    patient_headers = auth_headers(email="claim-nocode@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Tanpa Kode")

    assert claim(client, patient_headers, "FG-NO-CODE-01", generate_claim_code()).status_code == 404


@pytest.mark.parametrize("blocked_status", ["retired", "lost", "maintenance"])
def test_withdrawn_devices_cannot_be_claimed(client, auth_headers, blocked_status):
    admin_headers, device, claim_code = setup_unclaimed_device(
        client, auth_headers, f"status{blocked_status}"
    )
    patch = client.patch(
        f"/devices/{device['id']}", headers=admin_headers, json={"status": blocked_status}
    )
    assert patch.status_code == 200
    patient_headers = auth_headers(email=f"claim-{blocked_status}@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Status")

    response = claim(client, patient_headers, device["device_uid"], claim_code)

    assert response.status_code == 409


def test_repeated_wrong_codes_are_rate_limited(client, auth_headers):
    _, device, _ = setup_unclaimed_device(client, auth_headers, "brute")
    patient_headers = auth_headers(email="claim-brute@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Brute")

    statuses = [
        claim(client, patient_headers, device["device_uid"], generate_claim_code()).status_code
        for _ in range(8)
    ]

    assert 429 in statuses, "an 8-character code must not be guessable without throttling"
    assert statuses.index(429) <= 6


def test_a_correct_code_still_works_after_a_few_typos(client, auth_headers):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "typo")
    patient_headers = auth_headers(email="claim-typo@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Typo")

    for _ in range(2):
        assert claim(
            client, patient_headers, device["device_uid"], generate_claim_code()
        ).status_code == 404

    assert claim(client, patient_headers, device["device_uid"], claim_code).status_code == 201


@pytest.mark.parametrize("role", ["clinician", "admin"])
def test_only_patients_can_claim_a_device(client, auth_headers, role):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, f"role{role}")
    caller_headers = auth_headers(email=f"claim-role-{role}@example.com", role=role)

    response = claim(client, caller_headers, device["device_uid"], claim_code)

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["patient", "clinician"])
def test_only_device_managers_can_issue_a_claim_code(client, auth_headers, role):
    admin_headers, device, _ = setup_unclaimed_device(client, auth_headers, f"issue{role}")
    caller_headers = auth_headers(email=f"claim-issue-{role}@example.com", role=role)

    response = client.post(f"/devices/{device['id']}/claim-code", headers=caller_headers)

    assert response.status_code == 403


def test_claim_code_is_never_returned_by_listing_endpoints(client, auth_headers):
    admin_headers, device, _ = setup_unclaimed_device(client, auth_headers, "leak")
    patient_headers = auth_headers(email="claim-leak@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Leak")

    listing = client.get("/devices", headers=admin_headers).json()
    entry = next(item for item in listing["items"] if item["id"] == device["id"])

    assert "claim_code" not in entry
    assert "claim_code_hash" not in entry
    assert entry["claim_code_set_at"] is not None


# ── releasing and handover ──────────────────────────────────────────────────


def test_patient_releases_a_belt_so_the_next_patient_can_claim_it(client, auth_headers):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "handover")
    first_headers = auth_headers(email="claim-first@example.com", role="patient")
    create_patient_profile(client, first_headers, name="Ayu Pertama")
    assert claim(client, first_headers, device["device_uid"], claim_code).status_code == 201

    released = client.post(f"/devices/me/{device['id']}/release", headers=first_headers)

    second_headers = auth_headers(email="claim-second@example.com", role="patient")
    create_patient_profile(client, second_headers, name="Ayu Kedua")
    reclaimed = claim(client, second_headers, device["device_uid"], claim_code)

    assert released.status_code == 200
    assert released.json()["patient_id"] is None
    assert reclaimed.status_code == 201
    assert client.get("/devices/me", headers=first_headers).json() == []


def test_releasing_preserves_the_previous_ownership_interval(client, auth_headers, db_session):
    """Handover must not erase who held the belt when earlier sessions were recorded."""
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "history")
    patient_headers = auth_headers(email="claim-history@example.com", role="patient")
    create_patient_profile(client, patient_headers, name="Ayu Riwayat")
    claim(client, patient_headers, device["device_uid"], claim_code)

    client.post(f"/devices/me/{device['id']}/release", headers=patient_headers)

    assignments = (
        db_session.query(DeviceAssignment)
        .filter(DeviceAssignment.device_id == device["id"])
        .all()
    )
    assert len(assignments) == 1
    assert assignments[0].ends_at is not None
    assert assignments[0].ended_by_user_id is not None


def test_a_patient_cannot_release_a_belt_they_do_not_hold(client, auth_headers):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "notyours")
    holder_headers = auth_headers(email="claim-holder2@example.com", role="patient")
    create_patient_profile(client, holder_headers, name="Ayu Pemilik")
    claim(client, holder_headers, device["device_uid"], claim_code)

    other_headers = auth_headers(email="claim-other@example.com", role="patient")
    create_patient_profile(client, other_headers, name="Ayu Lain")
    response = client.post(f"/devices/me/{device['id']}/release", headers=other_headers)

    assert response.status_code == 403
    assert client.get("/devices/me", headers=holder_headers).json()[0]["id"] == device["id"]


def test_release_is_refused_during_an_active_monitoring_session(client, auth_headers):
    _, device, claim_code = setup_unclaimed_device(client, auth_headers, "insession")
    patient_headers = auth_headers(email="claim-insession@example.com", role="patient")
    session_data = create_active_session(client, patient_headers, name="Ayu Sesi")
    assert claim(client, patient_headers, device["device_uid"], claim_code).status_code == 201

    upload = client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json={
            "payload": {"p": [2048, 2051, 2046, 2053], "fsr": [512]},
            "schema_version": 1,
            "ingestion_id": "claim-session-packet-1",
            "boot_id": "boot-claim-0001",
            "sequence_number": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "sample_rate_hz": 100,
            "device_uid": device["device_uid"],
            "source": "ble",
            "is_simulated": False,
        },
    )
    assert upload.status_code == 201, upload.json()

    response = client.post(f"/devices/me/{device['id']}/release", headers=patient_headers)

    assert response.status_code == 409


def test_claiming_an_already_registered_device_of_another_patient_is_refused(
    client, auth_headers
):
    """Admin-assigned belts keep working, and stay protected from self-service takeover."""
    owner_headers = auth_headers(email="claim-admin-owner@example.com", role="patient")
    admin_headers = auth_headers(email="claim-admin-owner-admin@example.com", role="admin")
    owner = create_patient_profile(client, owner_headers, name="Ayu Admin-Assigned")
    device = register_device(client, admin_headers, owner["id"], device_uid="FG-ADMIN-OWNED")
    claim_code = issue_claim_code(client, admin_headers, device["id"])

    intruder_headers = auth_headers(email="claim-intruder@example.com", role="patient")
    create_patient_profile(client, intruder_headers, name="Ayu Penyusup")
    response = claim(client, intruder_headers, "FG-ADMIN-OWNED", claim_code)

    assert response.status_code == 409
