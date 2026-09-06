"""Gestational age that advances with the calendar.

`patients.gestational_age_weeks` is what someone typed at intake. Read back
unchanged it is wrong the day after: a pregnancy does not pause between app
opens. Every read path derives the *current* value here instead.

Anchoring, in order of preference:

1. **Last menstrual period.** A fixed calendar date; the current week is just
   `(today - LMP) / 7`. This never drifts and survives profile edits.
2. **The recorded value + when it was recorded.** `gestational_age_recorded_at`
   is stamped whenever `gestational_age_weeks` is written, so editing the
   number later re-anchors the clock rather than silently rewinding it.
3. **Creation date**, for rows created before the recorded-at column existed.

Past 42 completed weeks a pregnancy is post-term; `is_post_term` lets the UI
say so instead of printing an ever-growing number. 45 caps a value that has
run away because the anchor itself is stale or wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# Clinical convention: a term pregnancy is 37-42 weeks; 40 weeks (280 days)
# from the LMP is the estimated due date.
GESTATION_TERM_WEEKS = 42
GESTATION_DUE_DATE_DAYS = 280
# A derived value this large means the anchor is wrong, not that someone is
# 46 weeks pregnant. Clamp so the UI never shows nonsense.
GESTATION_MAX_WEEKS = 45
GESTATION_MIN_WEEKS = 1


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        # Normalise to UTC before dropping the time so an anchor recorded late
        # in the day in one zone does not land a day early in another.
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(timezone.utc).date()
    return value


def current_gestational_age_weeks(
    *,
    last_menstrual_period: date | None,
    recorded_weeks: int | None,
    recorded_on: date | datetime | None,
    as_of: date | None = None,
) -> int | None:
    """Completed weeks of gestation as of `as_of` (default: today, UTC).

    Returns ``None`` only when there is nothing to anchor to (no LMP and no
    recorded value). The result is clamped to
    ``[GESTATION_MIN_WEEKS, GESTATION_MAX_WEEKS]``.
    """
    reference = as_of or datetime.now(timezone.utc).date()
    lmp = _as_date(last_menstrual_period)

    if lmp is not None and lmp <= reference:
        weeks = (reference - lmp).days // 7
    elif recorded_weeks is not None:
        anchor = _as_date(recorded_on) or reference
        elapsed_weeks = max(0, (reference - anchor).days // 7)
        weeks = recorded_weeks + elapsed_weeks
    else:
        return None

    return max(GESTATION_MIN_WEEKS, min(weeks, GESTATION_MAX_WEEKS))


def is_post_term(weeks: int | None) -> bool:
    return weeks is not None and weeks > GESTATION_TERM_WEEKS


def estimated_due_date(
    *,
    last_menstrual_period: date | None,
    explicit_due_date: date | None = None,
) -> date | None:
    """Prefer an explicitly recorded EDD; otherwise LMP + 280 days."""
    if explicit_due_date is not None:
        return explicit_due_date
    lmp = _as_date(last_menstrual_period)
    if lmp is None:
        return None
    return lmp + timedelta(days=GESTATION_DUE_DATE_DAYS)


@dataclass(frozen=True)
class GestationView:
    current_weeks: int | None
    recorded_weeks: int | None
    is_post_term: bool
    estimated_due_date: date | None


def gestation_view(patient, *, as_of: date | None = None) -> GestationView:
    """Everything the API needs about one patient's gestational timeline.

    ``patient`` is the ORM row; only the timeline fields are touched, so this
    stays cheap to call in a list serializer.
    """
    recorded_weeks = getattr(patient, "gestational_age_weeks", None)
    recorded_on = (
        getattr(patient, "gestational_age_recorded_at", None)
        or getattr(patient, "created_at", None)
    )
    lmp = getattr(patient, "last_menstrual_period", None)
    current = current_gestational_age_weeks(
        last_menstrual_period=lmp,
        recorded_weeks=recorded_weeks,
        recorded_on=recorded_on,
        as_of=as_of,
    )
    return GestationView(
        current_weeks=current,
        recorded_weeks=recorded_weeks,
        is_post_term=is_post_term(current),
        estimated_due_date=estimated_due_date(
            last_menstrual_period=lmp,
            explicit_due_date=getattr(patient, "estimated_due_date", None),
        ),
    )
