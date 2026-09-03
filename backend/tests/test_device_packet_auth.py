"""Device packet authentication.

A device UID is a public label, so these tests pin the property that actually
matters: a packet is only stored when it carries an HMAC the backend can
reproduce from the secret it provisioned for that specific device.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from api.routes import sessions as session_routes
from core.device_auth import (
    build_signing_message,
    captured_at_to_epoch_ms,
    compute_payload_digest,
    generate_device_secret,
    sign_packet,
    verify_packet_signature,
)
from tests.test_devices import create_active_session, register_device


PAYLOAD = {"p": [2048, 2051, 2046, 2053], "fsr": [512]}

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "telemetry"
# Fixture key documented in contracts/telemetry/README.md. Authenticates nothing.
GOLDEN_TEST_SECRET = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"


def load_golden(relative_path):
    return json.loads((CONTRACTS_DIR / relative_path).read_text(encoding="utf-8"))


def provision_signing_key(client, admin_headers, device_id):
    response = client.post(f"/devices/{device_id}/signing-key", headers=admin_headers)
    assert response.status_code == 201
    return response.json()["packet_secret"]


def signed_packet(device_uid, secret, sequence_number, payload=None, captured_at=None):
    payload = payload if payload is not None else dict(PAYLOAD)
    captured_at = captured_at or datetime.now(timezone.utc)
    packet = {
        "payload": payload,
        "schema_version": 1,
        "ingestion_id": f"signed-{device_uid}-{sequence_number}",
        "boot_id": "boot-signed-0001",
        "sequence_number": sequence_number,
        "captured_at": captured_at.isoformat(),
        "sample_rate_hz": 100,
        "source": "ble",
        "device_uid": device_uid,
        "is_simulated": False,
    }
    packet["packet_signature"] = sign_packet(
        secret,
        build_signing_message(
            device_uid=device_uid,
            boot_id=packet["boot_id"],
            sequence_number=sequence_number,
            captured_at=captured_at,
            schema_version=1,
            channels=payload,
        ),
    )
    return packet


def setup_provisioned_device(client, auth_headers, suffix):
    patient_headers = auth_headers(email=f"sig-patient-{suffix}@example.com", role="patient")
    admin_headers = auth_headers(email=f"sig-admin-{suffix}@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name=f"Pasien {suffix}")
    device_uid = f"FG-SIGNED-{suffix.upper()}"
    device = register_device(client, admin_headers, session_data["patient_id"], device_uid=device_uid)
    secret = provision_signing_key(client, admin_headers, device["id"])
    return patient_headers, admin_headers, session_data, device, device_uid, secret


def upload(client, patient_headers, session_data, packet):
    return client.post(
        f"/sessions/{session_data['id']}/data",
        headers=patient_headers,
        json=packet,
    )


# ── signing primitives ──────────────────────────────────────────────────────


def test_payload_digest_separates_absent_channel_from_empty_channel():
    assert compute_payload_digest({"p": [1, 2]}) != compute_payload_digest({"p": [1, 2], "fsr": [0]})
    assert compute_payload_digest({"p": [1, 2]}) == compute_payload_digest({"p": [1, 2], "fsr": []})


def test_signature_verification_rejects_malformed_digests():
    secret = generate_device_secret()
    message = "FGSIG1|FG-A|boot-1|1|0|1|deadbeef"
    signature = sign_packet(secret, message)

    assert verify_packet_signature(secret, signature, message) is True
    assert verify_packet_signature(secret, signature.upper(), message) is True
    assert verify_packet_signature(secret, "short", message) is False
    assert verify_packet_signature(secret, "", message) is False
    assert verify_packet_signature("", signature, message) is False
    assert verify_packet_signature(generate_device_secret(), signature, message) is False


def test_signed_message_binds_every_identity_field():
    base = {
        "device_uid": "FG-A",
        "boot_id": "boot-1",
        "sequence_number": 7,
        "captured_at": datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        "schema_version": 1,
        "channels": {"p": [1]},
    }
    baseline = build_signing_message(**base)

    for field, value in (
        ("device_uid", "FG-B"),
        ("boot_id", "boot-2"),
        ("sequence_number", 8),
        ("captured_at", datetime(2026, 8, 30, 12, 0, 1, tzinfo=timezone.utc)),
        ("schema_version", 2),
        ("channels", {"p": [2]}),
    ):
        assert build_signing_message(**{**base, field: value}) != baseline


@pytest.mark.parametrize("millisecond", [0, 1, 234, 499, 500, 501, 999])
def test_captured_at_converts_to_exact_milliseconds(millisecond):
    """`timestamp() * 1000` truncates a millisecond low for many values, which would
    make otherwise valid device signatures fail at random."""
    captured_at = datetime(2026, 8, 30, 12, 34, 56, millisecond * 1000, tzinfo=timezone.utc)

    assert captured_at_to_epoch_ms(captured_at) % 1000 == millisecond


def test_signed_message_is_independent_of_timezone_representation():
    utc = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    shifted = utc.astimezone(timezone(timedelta(hours=7)))
    common = {
        "device_uid": "FG-A",
        "boot_id": "boot-1",
        "sequence_number": 1,
        "schema_version": 1,
        "channels": {"p": [1]},
    }

    assert build_signing_message(captured_at=utc, **common) == build_signing_message(
        captured_at=shifted, **common
    )


@pytest.mark.parametrize(
    "relative_path",
    ["v1/golden-esp32.json", "v2/golden-esp32-window.json"],
)
def test_golden_fixture_signature_matches_the_shared_signing_scheme(relative_path):
    """Pins the wire format both the firmware and the backend must reproduce.

    This proves the backend and the fixtures agree; it does not prove the C++ in
    fetalguard.ino emits the same bytes, which needs real hardware.
    """
    packet = load_golden(relative_path)

    message = build_signing_message(
        device_uid=packet["device_uid"],
        boot_id=packet["boot_id"],
        sequence_number=packet["sequence_number"],
        captured_at=datetime.fromisoformat(packet["captured_at"].replace("Z", "+00:00")),
        schema_version=packet["schema_version"],
        channels=packet["channels"],
    )

    assert verify_packet_signature(GOLDEN_TEST_SECRET, packet["packet_signature"], message)


def test_golden_fixture_signature_breaks_when_a_sample_changes():
    packet = load_golden("v1/golden-esp32.json")
    tampered = dict(packet["channels"])
    tampered["fsr"] = [513]

    message = build_signing_message(
        device_uid=packet["device_uid"],
        boot_id=packet["boot_id"],
        sequence_number=packet["sequence_number"],
        captured_at=datetime.fromisoformat(packet["captured_at"].replace("Z", "+00:00")),
        schema_version=packet["schema_version"],
        channels=tampered,
    )

    assert not verify_packet_signature(GOLDEN_TEST_SECRET, packet["packet_signature"], message)


# ── ingestion enforcement ───────────────────────────────────────────────────


def test_correctly_signed_packet_from_provisioned_device_is_stored(client, auth_headers):
    patient_headers, _, session_data, _, device_uid, secret = setup_provisioned_device(
        client, auth_headers, "ok"
    )

    response = upload(client, patient_headers, session_data, signed_packet(device_uid, secret, 1))

    assert response.status_code == 201, response.json()


def test_provisioned_device_rejects_unsigned_packet(client, auth_headers):
    patient_headers, _, session_data, _, device_uid, secret = setup_provisioned_device(
        client, auth_headers, "unsigned"
    )
    packet = signed_packet(device_uid, secret, 1)
    packet.pop("packet_signature")

    response = upload(client, patient_headers, session_data, packet)

    assert response.status_code == 401
    assert "signed" in response.json()["detail"].lower()


def test_tampered_payload_invalidates_the_signature(client, auth_headers):
    patient_headers, _, session_data, _, device_uid, secret = setup_provisioned_device(
        client, auth_headers, "tampered"
    )
    packet = signed_packet(device_uid, secret, 1)
    packet["payload"] = {"p": [4095, 4095, 4095, 4095], "fsr": [4095]}

    response = upload(client, patient_headers, session_data, packet)

    assert response.status_code == 401


def test_signature_from_another_devices_key_is_rejected(client, auth_headers):
    patient_headers, _, session_data, _, device_uid, _ = setup_provisioned_device(
        client, auth_headers, "foreign"
    )
    packet = signed_packet(device_uid, generate_device_secret(), 1)

    response = upload(client, patient_headers, session_data, packet)

    assert response.status_code == 401


def test_signature_cannot_be_replayed_under_a_different_sequence_number(client, auth_headers):
    patient_headers, _, session_data, _, device_uid, secret = setup_provisioned_device(
        client, auth_headers, "replay"
    )
    original = signed_packet(device_uid, secret, 1)
    replay = signed_packet(device_uid, secret, 2)
    replay["packet_signature"] = original["packet_signature"]

    assert upload(client, patient_headers, session_data, original).status_code == 201
    assert upload(client, patient_headers, session_data, replay).status_code == 401


def test_unprovisioned_device_still_uploads_while_signing_is_optional(client, auth_headers):
    patient_headers = auth_headers(email="sig-legacy-patient@example.com", role="patient")
    admin_headers = auth_headers(email="sig-legacy-admin@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name="Pasien Legacy")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-LEGACY-01")
    packet = signed_packet("FG-LEGACY-01", generate_device_secret(), 1)
    packet.pop("packet_signature")

    response = upload(client, patient_headers, session_data, packet)

    assert response.status_code == 201


def test_unprovisioned_device_is_refused_when_deployment_requires_signing(
    client, auth_headers, monkeypatch
):
    patient_headers = auth_headers(email="sig-required-patient@example.com", role="patient")
    admin_headers = auth_headers(email="sig-required-admin@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name="Pasien Wajib Tanda Tangan")
    register_device(client, admin_headers, session_data["patient_id"], device_uid="FG-REQUIRED-01")
    packet = signed_packet("FG-REQUIRED-01", generate_device_secret(), 1)
    packet.pop("packet_signature")
    monkeypatch.setattr(session_routes.settings, "REQUIRE_DEVICE_PACKET_SIGNATURE", True)

    response = upload(client, patient_headers, session_data, packet)

    assert response.status_code == 403
    assert "provisioned signing key" in response.json()["detail"]


# ── key provisioning ────────────────────────────────────────────────────────


def test_signing_key_is_disclosed_once_and_never_readable_again(client, auth_headers):
    patient_headers, admin_headers, _, device, _, secret = setup_provisioned_device(
        client, auth_headers, "once"
    )

    listing = client.get("/devices", headers=admin_headers).json()
    patient_view = client.get("/devices/me", headers=patient_headers).json()
    provisioned = next(item for item in listing["items"] if item["id"] == device["id"])

    assert len(secret) == 64
    assert provisioned["packet_secret_provisioned_at"] is not None
    assert all("packet_secret" not in item for item in listing["items"])
    assert all("packet_secret" not in item for item in patient_view)


def test_rotating_the_key_invalidates_signatures_from_the_previous_key(client, auth_headers):
    patient_headers, admin_headers, session_data, device, device_uid, old_secret = (
        setup_provisioned_device(client, auth_headers, "rotate")
    )

    new_secret = provision_signing_key(client, admin_headers, device["id"])
    stale = upload(client, patient_headers, session_data, signed_packet(device_uid, old_secret, 1))
    fresh = upload(client, patient_headers, session_data, signed_packet(device_uid, new_secret, 2))

    assert new_secret != old_secret
    assert stale.status_code == 401
    assert fresh.status_code == 201


def test_key_rotation_is_refused_during_an_active_bound_session(client, auth_headers):
    patient_headers, admin_headers, session_data, device, device_uid, secret = (
        setup_provisioned_device(client, auth_headers, "bound")
    )
    assert upload(client, patient_headers, session_data, signed_packet(device_uid, secret, 1)).status_code == 201

    response = client.post(f"/devices/{device['id']}/signing-key", headers=admin_headers)

    assert response.status_code == 409


@pytest.mark.parametrize("role", ["patient", "clinician"])
def test_only_device_managers_can_provision_a_signing_key(client, auth_headers, role):
    admin_headers = auth_headers(email="sig-guard-admin@example.com", role="admin")
    owner_headers = auth_headers(email="sig-guard-owner@example.com", role="patient")
    session_data = create_active_session(client, owner_headers, name="Pasien Guard")
    device = register_device(
        client, admin_headers, session_data["patient_id"], device_uid="FG-GUARD-01"
    )
    caller_headers = auth_headers(email=f"sig-guard-caller-{role}@example.com", role=role)

    response = client.post(f"/devices/{device['id']}/signing-key", headers=caller_headers)

    assert response.status_code == 403
