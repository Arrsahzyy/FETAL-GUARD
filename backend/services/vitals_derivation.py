"""Derive session vitals on the server from raw channels the backend stores.

The ingestion schema refuses client-supplied clinical summaries, so before this
existed the FHR, maternal HR, and signal quality shown to a clinician were never
populated at all for real device sessions. This module fills them from the same
raw samples the server holds, which means a number on the dashboard can always be
traced back to stored evidence.

**The estimators are unvalidated** -- see `services.signal_processing`. Values
produced here are technical estimates, not clinical measurements.

Only telemetry v2 can be used. A v1 frame carries a single 1 Hz snapshot per
channel, which cannot resolve a heartbeat at any rate; sessions that only ever
send v1 are recorded as `unsupported_schema` rather than being given a guess.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession
from models.session_sensor_summary import SessionSensorSummary
from services.signal_processing import (
    MIN_WINDOW_SECONDS,
    PIEZO_CHANNEL_COUNT,
    classify_contraction_indicator,
    estimate_fetal_heart_rate,
    estimate_maternal_heart_rate,
)

# Re-deriving on every packet would repeat the same query and arithmetic several
# times a second for no new information.
MIN_DERIVATION_INTERVAL_SECONDS = 5.0
# Long enough for the slowest rate in the search range, short enough that a
# recovering signal is reflected quickly.
DERIVATION_WINDOW_SECONDS = 20.0
# Hard ceiling so a chatty device cannot turn one upload into an unbounded read.
MAX_CHUNKS_PER_WINDOW = 80


def _normalize(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _should_derive(summary: SessionSensorSummary | None, reference_time: datetime) -> bool:
    """Throttle on how far the *signal* has advanced, not on wall-clock time.

    Wall-clock throttling breaks whenever packets arrive faster than they were
    captured -- an offline queue flushing a minute of buffered telemetry in one
    burst would derive from the first packet and then suppress every other one,
    leaving the summary stale despite a full window having just arrived.
    """
    if summary is None or summary.derived_at is None:
        return True
    elapsed = (reference_time - _normalize(summary.derived_at)).total_seconds()
    return elapsed >= MIN_DERIVATION_INTERVAL_SECONDS


def collect_recent_window(
    db: Session,
    session_id: str,
    reference_time: datetime,
) -> tuple[dict[str, list[int]], dict[str, float], bool]:
    """Concatenate the newest stored chunks into one contiguous channel window.

    Returns the channels, their per-channel sample rates, and whether any usable
    telemetry v2 chunk was seen at all.
    """
    window_start = reference_time - timedelta(seconds=DERIVATION_WINDOW_SECONDS)
    recent = (
        db.query(SensorDataChunk)
        .filter(
            SensorDataChunk.session_id == session_id,
            SensorDataChunk.captured_at.is_not(None),
            SensorDataChunk.captured_at >= window_start,
        )
        .order_by(SensorDataChunk.captured_at.desc())
        .limit(MAX_CHUNKS_PER_WINDOW)
        .all()
    )
    # Query descending to take the newest, then replay in capture order so the
    # concatenated signal runs forward in time.
    recent.reverse()

    channels: dict[str, list[int]] = {}
    rates: dict[str, float] = {}
    saw_v2 = False

    for chunk in recent:
        payload = chunk.payload if isinstance(chunk.payload, dict) else {}
        if payload.get("schema_version") != 2:
            continue
        samples = payload.get("samples")
        chunk_rates = payload.get("sample_rates_hz")
        if not isinstance(samples, dict) or not isinstance(chunk_rates, dict):
            continue
        saw_v2 = True
        for name in ("p", "fsr", "hr_ir", "hr_red"):
            values = samples.get(name)
            rate = chunk_rates.get(name)
            if not isinstance(values, list) or not values:
                continue
            if not isinstance(rate, (int, float)) or rate <= 0:
                continue
            # A device that changes a channel's rate mid-window would make the
            # concatenation meaningless, so the first rate seen wins and later
            # chunks at a different rate are skipped for that channel.
            if name in rates and abs(rates[name] - float(rate)) > 1e-6:
                continue
            rates.setdefault(name, float(rate))
            channels.setdefault(name, []).extend(int(value) for value in values)

    return channels, rates, saw_v2


def derive_session_vitals(
    db: Session,
    monitoring_session: MonitoringSession,
    summary: SessionSensorSummary,
    reference_time: datetime | None = None,
) -> bool:
    """Recompute the stored summary's clinical fields from recent raw samples.

    ``reference_time`` anchors both the throttle and the window to the newest
    sample's capture time, so buffered telemetry is analysed over the span it was
    actually recorded rather than the instant it happened to be uploaded.

    Fails closed: every clinical field is cleared when the current window cannot
    support it, because a stale reassuring number is worse than an empty field.

    Returns whether the summary was actually recomputed, so callers that react to
    new values -- alerting in particular -- can run exactly when those values
    change instead of on every packet the throttle skips.
    """
    reference_time = _normalize(
        reference_time
        or monitoring_session.last_captured_at
        or datetime.now(timezone.utc)
    )
    if not _should_derive(summary, reference_time):
        return False

    channels, rates, saw_v2 = collect_recent_window(db, monitoring_session.id, reference_time)
    summary.derived_at = reference_time

    if not saw_v2:
        summary.derivation_status = "unsupported_schema"
        summary.fhr_estimate_bpm = None
        summary.maternal_hr_bpm = None
        summary.signal_quality_index = None
        return True

    fetal = None
    if channels.get("p") and rates.get("p"):
        fetal = estimate_fetal_heart_rate(
            channels["p"], rates["p"], channel_count=PIEZO_CHANNEL_COUNT
        )

    maternal = None
    if channels.get("hr_ir") and rates.get("hr_ir"):
        maternal = estimate_maternal_heart_rate(channels["hr_ir"], rates["hr_ir"])

    summary.fhr_estimate_bpm = fetal.bpm if fetal else None
    summary.maternal_hr_bpm = maternal.bpm if maternal else None
    # Quality describes the fetal channel, which is the measurement the belt
    # exists to make and the one a clinician reads this index against.
    summary.signal_quality_index = round(fetal.quality, 4) if fetal else None

    if channels.get("fsr"):
        summary.contraction_indicator = classify_contraction_indicator(channels["fsr"])

    if fetal or maternal:
        summary.derivation_status = "derived"
    elif channels.get("p") and rates.get("p") and (
        len(channels["p"]) / (rates["p"] * PIEZO_CHANNEL_COUNT) >= MIN_WINDOW_SECONDS
    ):
        # Enough signal arrived to attempt an estimate and none was usable.
        summary.derivation_status = "insufficient_signal"
    else:
        summary.derivation_status = "pending"

    return True
