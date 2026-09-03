"""Rule-based alert production from derived session vitals.

Until this existed the alert lifecycle -- statuses, acknowledgement, audit trail,
optimistic concurrency -- was fully built but had no producer: nothing in the
application ever created a Notification row, so a clinician could never receive
an alert no matter what the sensors reported.

Rules are deliberately simple and reference-range based. They do not diagnose:
they say a reading sits outside the display reference range in AGENTS.md and
should be looked at. Copy stays in screening language ("perlu observasi",
"segera tinjau"), never diagnostic language.

Safety properties:

* Alerts are only raised from backend-derived values, never from anything a
  client supplied.
* A window whose signal quality is below `MIN_ALERTING_SIGNAL_QUALITY` raises
  nothing. An unreliable measurement must not generate clinical work, and it must
  not generate false reassurance either -- it simply produces no alert.
* One open alert per session per rule. Re-evaluating on every packet must not
  bury a clinician under duplicates of the same finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.realtime import enqueue_realtime_event
from models.notification import Notification
from models.session import MonitoringSession
from models.session_sensor_summary import SessionSensorSummary

# Display reference ranges from AGENTS.md section 8. These are reference ranges
# for presentation, not diagnostic thresholds, and must not be changed without
# explicit approval.
FHR_REFERENCE_RANGE_BPM = (110, 160)
MATERNAL_HR_REFERENCE_RANGE_BPM = (60, 100)

# Below this the measurement is not trustworthy enough to act on.
MIN_ALERTING_SIGNAL_QUALITY = 0.5

# How far outside the reference range escalates from "observe" to "review now".
FHR_URGENT_MARGIN_BPM = 20


@dataclass(frozen=True)
class AlertRule:
    """One evaluated finding, ready to be persisted if it is not already open."""

    code: str
    risk_level: str
    message: str


def _fhr_rule(fhr_bpm: int) -> AlertRule | None:
    low, high = FHR_REFERENCE_RANGE_BPM
    if low <= fhr_bpm <= high:
        return None

    urgent = fhr_bpm < low - FHR_URGENT_MARGIN_BPM or fhr_bpm > high + FHR_URGENT_MARGIN_BPM
    direction = "di bawah" if fhr_bpm < low else "di atas"
    return AlertRule(
        code="fhr_outside_reference_range",
        risk_level="high" if urgent else "medium",
        message=(
            f"Estimasi DJJ {fhr_bpm} bpm berada {direction} rentang rujukan "
            f"{low}-{high} bpm. "
            + ("Segera tinjau kondisi pasien." if urgent else "Perlu observasi lanjutan.")
            + " Estimasi teknis dari sinyal perangkat, belum tervalidasi klinis."
        ),
    )


def _maternal_rule(maternal_bpm: int) -> AlertRule | None:
    low, high = MATERNAL_HR_REFERENCE_RANGE_BPM
    if low <= maternal_bpm <= high:
        return None

    direction = "di bawah" if maternal_bpm < low else "di atas"
    return AlertRule(
        code="maternal_hr_outside_reference_range",
        risk_level="medium",
        message=(
            f"Estimasi denyut jantung ibu {maternal_bpm} bpm berada {direction} "
            f"rentang rujukan {low}-{high} bpm. Perlu observasi lanjutan. "
            "Estimasi teknis dari sinyal perangkat, belum tervalidasi klinis."
        ),
    )


def evaluate_rules(summary: SessionSensorSummary) -> list[AlertRule]:
    """Return the findings supported by this summary, newest derivation only."""
    if summary.derivation_status != "derived":
        return []
    quality = summary.signal_quality_index
    if quality is None or quality < MIN_ALERTING_SIGNAL_QUALITY:
        return []

    rules: list[AlertRule] = []
    if summary.fhr_estimate_bpm is not None:
        rule = _fhr_rule(summary.fhr_estimate_bpm)
        if rule is not None:
            rules.append(rule)
    if summary.maternal_hr_bpm is not None:
        rule = _maternal_rule(summary.maternal_hr_bpm)
        if rule is not None:
            rules.append(rule)
    return rules


def _has_open_alert(db: Session, session_id: str, code: str) -> bool:
    """One unresolved alert per rule per session, so re-evaluation cannot spam.

    Matched on `rule_code`, not on message text: the copy is user-facing and
    translated, and keying deduplication to it would silently flood a clinician
    with duplicates the moment the wording changed.
    """
    return (
        db.query(Notification.id)
        .filter(
            Notification.session_id == session_id,
            Notification.rule_code == code,
            Notification.status.in_(("open", "acknowledged", "in_review")),
        )
        .first()
        is not None
    )


def evaluate_session_alerts(
    db: Session,
    monitoring_session: MonitoringSession,
    summary: SessionSensorSummary,
    now: datetime | None = None,
) -> list[Notification]:
    """Create alerts for any newly-detected finding on this session."""
    now = now or datetime.now(timezone.utc)
    created: list[Notification] = []

    for rule in evaluate_rules(summary):
        if _has_open_alert(db, monitoring_session.id, rule.code):
            continue

        alert = Notification(
            organization_id=monitoring_session.organization_id,
            session_id=monitoring_session.id,
            message=rule.message,
            rule_code=rule.code,
            risk_level=rule.risk_level,
            status="open",
            created_at=now,
            updated_at=now,
        )
        db.add(alert)
        db.flush()
        created.append(alert)

        enqueue_realtime_event(
            db,
            organization_id=monitoring_session.organization_id,
            patient_id=monitoring_session.patient_id,
            event_type="alert.created",
            resource_id=alert.id,
            idempotency_key=f"alert.created:{alert.id}",
            payload={"risk_level": rule.risk_level, "status": "open"},
            occurred_at=now,
        )

    return created
