"""Server-derived vitals and the alerts produced from them.

Covers the property that matters clinically: numbers shown to a clinician come
from raw samples the backend holds, and an alert only ever fires from those --
never from a value the uploading client supplied, and never from a window whose
signal quality is too poor to act on.
"""

from datetime import datetime, timedelta, timezone
import math

import pytest

from core.device_auth import build_signing_message, sign_packet
from models.notification import Notification
from models.session_sensor_summary import SessionSensorSummary
from services.alerting import (
    FHR_REFERENCE_RANGE_BPM,
    MATERNAL_HR_REFERENCE_RANGE_BPM,
    MIN_ALERTING_SIGNAL_QUALITY,
    evaluate_rules,
)
from tests.test_devices import create_active_session, register_device

PIEZO_RATE_HZ = 200
PPG_RATE_HZ = 100
CHUNK_SECONDS = 1.0


def beat_channel(bpm, sample_rate_hz, seconds, offset_index=0, amplitude=800, baseline=2048):
    total = int(sample_rate_hz * seconds)
    period = sample_rate_hz * 60.0 / bpm
    samples = []
    for step in range(total):
        index = offset_index + step
        phase = (index % period) / period
        envelope = math.exp(-((phase * 8.0) ** 2))
        samples.append(
            int(baseline + amplitude * envelope * math.sin(2 * math.pi * 12 * index / sample_rate_hz))
        )
    return samples


def flat_channel(sample_rate_hz, seconds, value=2048):
    return [value] * int(sample_rate_hz * seconds)


def interleave(channels):
    interleaved = []
    for frame in zip(*channels):
        interleaved.extend(frame)
    return interleaved


def build_window_chunk(index, fhr_bpm, maternal_bpm, captured_at, noisy=False):
    """One second of telemetry v2, phase-continuous with the preceding chunk."""
    piezo_offset = int(index * PIEZO_RATE_HZ * CHUNK_SECONDS)
    ppg_offset = int(index * PPG_RATE_HZ * CHUNK_SECONDS)

    if noisy:
        beat = [
            2048 + (((position * 7919) % 977) - 488)
            for position in range(piezo_offset, piezo_offset + int(PIEZO_RATE_HZ * CHUNK_SECONDS))
        ]
    else:
        beat = beat_channel(fhr_bpm, PIEZO_RATE_HZ, CHUNK_SECONDS, offset_index=piezo_offset)

    quiet = flat_channel(PIEZO_RATE_HZ, CHUNK_SECONDS)
    piezo = interleave([quiet, quiet, beat, quiet])

    ppg = beat_channel(
        maternal_bpm, PPG_RATE_HZ, CHUNK_SECONDS, offset_index=ppg_offset, baseline=50000
    )
    fsr_count = 50
    fsr = [700] * fsr_count

    return {
        "payload": {
            "t": int(captured_at.timestamp() * 1000),
            "p": piezo,
            "fsr": fsr,
            "hr_ir": ppg,
            "hr_red": ppg,
        },
        "schema_version": 2,
        "ingestion_id": f"derive-{index}",
        "boot_id": "boot-derive-0001",
        "sequence_number": index,
        "captured_at": captured_at.isoformat(),
        "sample_rates_hz": {
            "p": PIEZO_RATE_HZ,
            "fsr": fsr_count,
            "hr_ir": PPG_RATE_HZ,
            "hr_red": PPG_RATE_HZ,
        },
        "channel_layout": {"p": 4},
        "device_uid": "FG-DERIVE-01",
        "source": "ble",
        "is_simulated": False,
    }


def stream_session(client, auth_headers, suffix, fhr_bpm=140, maternal_bpm=78, seconds=14, noisy=False):
    patient_headers = auth_headers(email=f"derive-{suffix}@example.com", role="patient")
    admin_headers = auth_headers(email=f"derive-admin-{suffix}@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name=f"Pasien {suffix}")
    register_device(
        client, admin_headers, session_data["patient_id"], device_uid="FG-DERIVE-01"
    )

    start = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    for index in range(seconds):
        captured_at = start + timedelta(seconds=index)
        chunk = build_window_chunk(index, fhr_bpm, maternal_bpm, captured_at, noisy=noisy)
        response = client.post(
            f"/sessions/{session_data['id']}/data",
            headers=patient_headers,
            json=chunk,
        )
        assert response.status_code == 201, response.json()

    return patient_headers, admin_headers, session_data


def get_summary(db_session, session_id):
    return (
        db_session.query(SessionSensorSummary)
        .filter(SessionSensorSummary.session_id == session_id)
        .one()
    )


# ── rule evaluation ─────────────────────────────────────────────────────────


def make_summary(**overrides):
    values = {
        "derivation_status": "derived",
        "signal_quality_index": 0.9,
        "fhr_estimate_bpm": 140,
        "maternal_hr_bpm": 80,
    }
    values.update(overrides)
    return SessionSensorSummary(**values)


def test_no_alert_while_readings_sit_inside_the_reference_ranges():
    assert evaluate_rules(make_summary()) == []


@pytest.mark.parametrize("fhr", [FHR_REFERENCE_RANGE_BPM[0] - 5, FHR_REFERENCE_RANGE_BPM[1] + 5])
def test_fhr_outside_the_reference_range_raises_an_observation_alert(fhr):
    rules = evaluate_rules(make_summary(fhr_estimate_bpm=fhr))

    assert [rule.code for rule in rules] == ["fhr_outside_reference_range"]
    assert rules[0].risk_level == "medium"
    assert "belum tervalidasi klinis" in rules[0].message


@pytest.mark.parametrize("fhr", [60, 220])
def test_fhr_far_outside_the_reference_range_escalates(fhr):
    rules = evaluate_rules(make_summary(fhr_estimate_bpm=fhr))

    assert rules[0].risk_level == "high"
    assert "Segera tinjau" in rules[0].message


def test_maternal_hr_outside_the_reference_range_raises_an_alert():
    rules = evaluate_rules(make_summary(maternal_hr_bpm=MATERNAL_HR_REFERENCE_RANGE_BPM[1] + 15))

    assert [rule.code for rule in rules] == ["maternal_hr_outside_reference_range"]


def test_poor_signal_quality_raises_nothing_even_when_far_out_of_range():
    """An unreliable measurement must not create clinical work."""
    rules = evaluate_rules(
        make_summary(fhr_estimate_bpm=60, signal_quality_index=MIN_ALERTING_SIGNAL_QUALITY - 0.01)
    )

    assert rules == []


def test_undervied_summary_raises_nothing():
    for status in ("pending", "insufficient_signal", "unsupported_schema"):
        assert evaluate_rules(make_summary(derivation_status=status, fhr_estimate_bpm=60)) == []


def test_alert_language_avoids_diagnostic_claims():
    for fhr in (60, 100, 200):
        message = evaluate_rules(make_summary(fhr_estimate_bpm=fhr))[0].message
        lowered = message.lower()
        for forbidden in ("diagnosis", "mendiagnosis", "gawat janin", "terbukti", "dipastikan"):
            assert forbidden not in lowered, f"{forbidden!r} leaked into alert copy"


# ── end-to-end derivation ───────────────────────────────────────────────────


def test_backend_derives_vitals_from_stored_raw_channels(client, auth_headers, db_session):
    _, _, session_data = stream_session(client, auth_headers, "ok", fhr_bpm=140, maternal_bpm=78)

    summary = get_summary(db_session, session_data["id"])

    assert summary.derivation_status == "derived"
    assert summary.fhr_estimate_bpm == pytest.approx(140, rel=0.08)
    assert summary.maternal_hr_bpm == pytest.approx(78, rel=0.10)
    assert summary.signal_quality_index is not None
    assert summary.derived_at is not None


def test_noisy_signal_reports_insufficient_rather_than_a_number(client, auth_headers, db_session):
    _, _, session_data = stream_session(client, auth_headers, "noisy", noisy=True)

    summary = get_summary(db_session, session_data["id"])

    assert summary.fhr_estimate_bpm is None
    assert summary.derivation_status in {"insufficient_signal", "derived"}
    if summary.derivation_status == "insufficient_signal":
        assert summary.signal_quality_index is None


def test_out_of_range_fhr_creates_exactly_one_open_alert(client, auth_headers, db_session):
    _, _, session_data = stream_session(client, auth_headers, "brady", fhr_bpm=95, maternal_bpm=78)

    alerts = (
        db_session.query(Notification)
        .filter(Notification.session_id == session_data["id"])
        .all()
    )

    fhr_alerts = [alert for alert in alerts if alert.rule_code == "fhr_outside_reference_range"]
    assert len(fhr_alerts) == 1, "re-evaluating every packet must not duplicate one finding"
    assert fhr_alerts[0].status == "open"


def test_in_range_session_creates_no_alerts(client, auth_headers, db_session):
    _, _, session_data = stream_session(client, auth_headers, "calm", fhr_bpm=140, maternal_bpm=78)

    alerts = (
        db_session.query(Notification)
        .filter(Notification.session_id == session_data["id"])
        .all()
    )

    assert alerts == []


def test_derived_alert_reaches_the_assigned_clinician(client, auth_headers):
    patient_headers, admin_headers, session_data = stream_session(
        client, auth_headers, "clinician", fhr_bpm=95
    )
    clinician_headers = auth_headers(email="derive-nakes@example.com", role="clinician")
    clinician_id = client.get("/auth/me", headers=clinician_headers).json()["id"]
    assign = client.post(
        "/admin/patient-assignments",
        headers=admin_headers,
        json={"patient_id": session_data["patient_id"], "clinician_id": clinician_id},
    )
    assert assign.status_code == 201

    response = client.get("/clinician/alerts", headers=clinician_headers)

    assert response.status_code == 200
    payload = response.json()
    alerts = payload["items"] if isinstance(payload, dict) else payload
    assert any(alert["patient_id"] == session_data["patient_id"] for alert in alerts)
