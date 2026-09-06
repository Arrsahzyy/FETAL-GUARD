"""Unit tests for core.gestation — the calendar-advancing gestational age."""

from datetime import date, datetime, timedelta, timezone

import pytest

from core.gestation import (
    GESTATION_MAX_WEEKS,
    current_gestational_age_weeks,
    estimated_due_date,
    gestation_view,
    is_post_term,
)


class _FakePatient:
    def __init__(self, **kw):
        self.gestational_age_weeks = kw.get("gestational_age_weeks")
        self.gestational_age_recorded_at = kw.get("gestational_age_recorded_at")
        self.created_at = kw.get("created_at")
        self.last_menstrual_period = kw.get("last_menstrual_period")
        self.estimated_due_date = kw.get("estimated_due_date")


TODAY = date(2026, 9, 7)


def test_lmp_is_the_preferred_anchor_and_advances_with_the_calendar():
    lmp = TODAY - timedelta(weeks=8)  # exactly 8 weeks ago
    assert current_gestational_age_weeks(
        last_menstrual_period=lmp, recorded_weeks=8, recorded_on=lmp, as_of=TODAY
    ) == 8
    # ...and two months later the same LMP reads higher, no write needed.
    later = TODAY + timedelta(days=61)
    assert current_gestational_age_weeks(
        last_menstrual_period=lmp, recorded_weeks=8, recorded_on=lmp, as_of=later
    ) == 8 + 61 // 7


def test_without_lmp_the_recorded_value_carries_forward_from_when_it_was_set():
    recorded_on = TODAY - timedelta(days=21)  # 3 whole weeks ago
    assert current_gestational_age_weeks(
        last_menstrual_period=None,
        recorded_weeks=30,
        recorded_on=recorded_on,
        as_of=TODAY,
    ) == 33


def test_recorded_on_falls_back_to_none_meaning_no_elapsed_time():
    assert current_gestational_age_weeks(
        last_menstrual_period=None, recorded_weeks=30, recorded_on=None, as_of=TODAY
    ) == 30


def test_a_future_lmp_is_ignored_and_the_recorded_value_is_used():
    assert current_gestational_age_weeks(
        last_menstrual_period=TODAY + timedelta(days=10),
        recorded_weeks=12,
        recorded_on=TODAY,
        as_of=TODAY,
    ) == 12


def test_result_is_clamped_so_a_stale_profile_cannot_show_nonsense():
    ancient = TODAY - timedelta(days=800)
    assert current_gestational_age_weeks(
        last_menstrual_period=ancient,
        recorded_weeks=None,
        recorded_on=None,
        as_of=TODAY,
    ) == GESTATION_MAX_WEEKS


def test_returns_none_when_there_is_nothing_to_anchor_to():
    assert current_gestational_age_weeks(
        last_menstrual_period=None, recorded_weeks=None, recorded_on=None, as_of=TODAY
    ) is None


def test_minimum_is_one_week():
    assert current_gestational_age_weeks(
        last_menstrual_period=TODAY,  # zero days elapsed
        recorded_weeks=None,
        recorded_on=None,
        as_of=TODAY,
    ) == 1


def test_tz_aware_anchor_is_normalised_to_utc_before_dropping_the_time():
    recorded = datetime(2026, 8, 17, 23, 0, tzinfo=timezone(timedelta(hours=7)))
    # 2026-08-17 16:00 UTC -> anchor date 2026-08-17, exactly 3 weeks before TODAY
    assert current_gestational_age_weeks(
        last_menstrual_period=None,
        recorded_weeks=20,
        recorded_on=recorded,
        as_of=TODAY,
    ) == 23


@pytest.mark.parametrize(
    "weeks,expected", [(None, False), (37, False), (42, False), (43, True), (45, True)]
)
def test_is_post_term(weeks, expected):
    assert is_post_term(weeks) is expected


def test_estimated_due_date_prefers_explicit_then_derives_from_lmp():
    explicit = date(2027, 1, 1)
    assert estimated_due_date(
        last_menstrual_period=date(2026, 4, 1), explicit_due_date=explicit
    ) == explicit
    assert estimated_due_date(
        last_menstrual_period=date(2026, 4, 1), explicit_due_date=None
    ) == date(2026, 4, 1) + timedelta(days=280)
    assert estimated_due_date(last_menstrual_period=None, explicit_due_date=None) is None


def test_gestation_view_from_orm_row_prefers_recorded_at_over_created_at():
    patient = _FakePatient(
        gestational_age_weeks=30,
        gestational_age_recorded_at=TODAY - timedelta(days=14),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),  # much older, must be ignored
        last_menstrual_period=None,
    )
    view = gestation_view(patient, as_of=TODAY)
    assert view.current_weeks == 32
    assert view.recorded_weeks == 30
    assert view.is_post_term is False


def test_gestation_view_uses_created_at_when_recorded_at_is_missing():
    patient = _FakePatient(
        gestational_age_weeks=41,
        gestational_age_recorded_at=None,
        created_at=datetime(2026, 8, 24, tzinfo=timezone.utc),  # 2 weeks before TODAY
        last_menstrual_period=None,
    )
    view = gestation_view(patient, as_of=TODAY)
    assert view.current_weeks == 43
    assert view.is_post_term is True
