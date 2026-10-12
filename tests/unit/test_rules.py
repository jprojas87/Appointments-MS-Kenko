import datetime as dt

import pytest

from app.domain.exceptions import BusinessRuleError
from app.domain.rules import (
    BUSINESS_TIMEZONE,
    SchedulingRules,
    ensure_modifiable,
    ensure_schedulable,
    format_hhmm,
    to_utc_iso,
)

RULES = SchedulingRules(min_hours_before_cancel_or_reschedule=24, max_days_ahead_to_schedule=90)
NOW = dt.datetime(2026, 10, 12, 10, 0, tzinfo=BUSINESS_TIMEZONE)


def test_schedulable_rejects_appointment_that_already_started() -> None:
    with pytest.raises(BusinessRuleError):
        ensure_schedulable(dt.date(2026, 10, 12), dt.time(10, 0), NOW, RULES)


def test_schedulable_accepts_later_today() -> None:
    ensure_schedulable(dt.date(2026, 10, 12), dt.time(10, 30), NOW, RULES)


def test_schedulable_respects_max_days_ahead() -> None:
    last_allowed = dt.date(2026, 10, 12) + dt.timedelta(days=90)
    ensure_schedulable(last_allowed, dt.time(9, 0), NOW, RULES)
    with pytest.raises(BusinessRuleError):
        ensure_schedulable(last_allowed + dt.timedelta(days=1), dt.time(9, 0), NOW, RULES)


def test_modifiable_requires_minimum_hours_in_advance() -> None:
    exactly_24h = dt.date(2026, 10, 13)
    ensure_modifiable(exactly_24h, dt.time(10, 0), NOW, RULES)
    with pytest.raises(BusinessRuleError):
        ensure_modifiable(exactly_24h, dt.time(9, 59), NOW, RULES)


def test_modifiable_rejects_past_appointments() -> None:
    with pytest.raises(BusinessRuleError):
        ensure_modifiable(dt.date(2026, 10, 11), dt.time(9, 0), NOW, RULES)


def test_format_hhmm_uses_short_time() -> None:
    assert format_hhmm(dt.time(9, 5)) == "09:05"


def test_to_utc_iso_converts_bogota_to_utc_with_z() -> None:
    assert to_utc_iso(NOW) == "2026-10-12T15:00:00Z"
