"""Reglas de negocio y constantes de dominio.

Fechas y horas de las citas se interpretan en America/Bogota. Las reglas de
anticipación se añaden en la fase 3.
"""

from zoneinfo import ZoneInfo

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
