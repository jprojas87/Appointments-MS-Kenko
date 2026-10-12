"""Reglas de negocio y constantes de dominio.

Fechas y horas de las citas se interpretan en America/Bogota. Los timestamps de eventos
se emiten en UTC con sufijo Z.
"""

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.domain.exceptions import BusinessRuleError

BUSINESS_TIMEZONE = ZoneInfo("America/Bogota")

WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class SchedulingRules:
    min_hours_before_cancel_or_reschedule: int
    max_days_ahead_to_schedule: int


def now_in_business_timezone() -> dt.datetime:
    return dt.datetime.now(BUSINESS_TIMEZONE)


def starts_at(day: dt.date, start: dt.time) -> dt.datetime:
    return dt.datetime.combine(day, start, tzinfo=BUSINESS_TIMEZONE)


def ensure_schedulable(
    day: dt.date, start: dt.time, now: dt.datetime, rules: SchedulingRules
) -> None:
    if starts_at(day, start) <= now:
        raise BusinessRuleError("La cita ya ocurrió o está en curso")
    last_day = now.date() + dt.timedelta(days=rules.max_days_ahead_to_schedule)
    if day > last_day:
        raise BusinessRuleError(
            f"Solo se pueden agendar citas con hasta "
            f"{rules.max_days_ahead_to_schedule} días de anticipación"
        )


def ensure_modifiable(
    day: dt.date, start: dt.time, now: dt.datetime, rules: SchedulingRules
) -> None:
    hours = rules.min_hours_before_cancel_or_reschedule
    if starts_at(day, start) - now < dt.timedelta(hours=hours):
        raise BusinessRuleError(
            f"Solo se puede cancelar o reagendar con al menos {hours} horas de anticipación"
        )


def format_hhmm(value: dt.time) -> str:
    return value.strftime("%H:%M")


def to_utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
