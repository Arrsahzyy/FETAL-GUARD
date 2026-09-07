"""The synthetic telemetry frame `fetalguard-demo/fetalguard-demo.ino` emits, end to end.

`stream_session` in `test_vitals_and_alerting` already proves a full-size v2 window
derives vitals and raises alerts. The one link those tests skip is the signature:
they register a device but never provision a key, so `enforce_device_packet_authentication`
returns early. This module adds that link — every packet is signed with a
provisioned device secret exactly as the ESP32-S3 running the demo sketch will —
so `compute_payload_digest` / `build_signing_message` are exercised over a real
ESP32 window (200x4 piezo + 50 fsr + 100 + 100 ppg), not the four-value fixtures
in `test_device_packet_auth`.

It does NOT prove the C++ emits identical bytes on hardware — that stays for the
runbook (`docs/ops/esp32-synthetic-e2e-runbook.md`).
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.device_auth import build_signing_message, sign_packet
from models.notification import Notification
from tests.test_devices import create_active_session, register_device
from tests.test_device_packet_auth import provision_signing_key
from tests.test_vitals_and_alerting import build_window_chunk, get_summary

# Must start with "FETAL-GUARD": the app scans BLE with namePrefix "FETAL-GUARD"
# (src/hooks/useBluetooth.js), so a "FG-BENCH-02" belt never shows up.
DEVICE_UID = "FETAL-GUARD-BENCH-02"


def _sign(chunk, secret):
    signed = dict(chunk)
    signed["device_uid"] = DEVICE_UID
    signed["packet_signature"] = sign_packet(
        secret,
        build_signing_message(
            device_uid=DEVICE_UID,
            boot_id=signed["boot_id"],
            sequence_number=signed["sequence_number"],
            captured_at=datetime.fromisoformat(signed["captured_at"]),
            schema_version=signed["schema_version"],
            channels=signed["payload"],
        ),
    )
    return signed


def _stream_signed(client, auth_headers, *, suffix, fhr_bpm, seconds=14):
    patient_headers = auth_headers(email=f"bench-demo-{suffix}@example.com", role="patient")
    admin_headers = auth_headers(email=f"bench-demo-admin-{suffix}@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name=f"Bench demo {suffix}")
    device = register_device(
        client, admin_headers, session_data["patient_id"], device_uid=DEVICE_UID
    )
    secret = provision_signing_key(client, admin_headers, device["id"])

    start = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    for index in range(seconds):
        captured_at = start + timedelta(seconds=index)
        chunk = build_window_chunk(index, fhr_bpm, 82, captured_at)
        response = client.post(
            f"/sessions/{session_data['id']}/data",
            headers=patient_headers,
            json=_sign(chunk, secret),
        )
        assert response.status_code == 201, response.json()
    return patient_headers, session_data


def test_signed_full_size_demo_window_ingests_and_derives(client, auth_headers, db_session):
    _, session_data = _stream_signed(client, auth_headers, suffix="ok", fhr_bpm=140)

    summary = get_summary(db_session, session_data["id"])
    assert summary.derivation_status == "derived"
    assert summary.fhr_estimate_bpm == pytest.approx(140, rel=0.08)
    assert summary.maternal_hr_bpm == pytest.approx(82, rel=0.10)


def test_one_flipped_sample_breaks_the_full_size_signature(client, auth_headers):
    """A tampered value in a real-size window must fail verification, not slip
    through because the digest only sampled part of the array."""
    patient_headers = auth_headers(email="bench-demo-tamper@example.com", role="patient")
    admin_headers = auth_headers(email="bench-demo-tamper-admin@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name="Bench tamper")
    device = register_device(
        client, admin_headers, session_data["patient_id"], device_uid=DEVICE_UID
    )
    secret = provision_signing_key(client, admin_headers, device["id"])

    captured_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    chunk = _sign(build_window_chunk(0, 140, 82, captured_at), secret)
    chunk["payload"]["hr_ir"][-1] += 1  # one count, deep in a 100-sample channel

    response = client.post(
        f"/sessions/{session_data['id']}/data", headers=patient_headers, json=chunk
    )
    assert response.status_code == 401


def test_signed_demo_drift_raises_a_clinician_alert(client, auth_headers, db_session):
    # DEMO_DRIFT_ENABLED walks FHR below 110 mid-session; the synthetic bench
    # signal must then produce the same alert a real out-of-range reading would.
    _, session_data = _stream_signed(client, auth_headers, suffix="drift", fhr_bpm=95)

    alerts = (
        db_session.query(Notification)
        .filter(Notification.session_id == session_data["id"])
        .all()
    )
    assert alerts, "an out-of-range synthetic window raised no alert"
    assert any(alert.risk_level in {"medium", "high"} for alert in alerts)
