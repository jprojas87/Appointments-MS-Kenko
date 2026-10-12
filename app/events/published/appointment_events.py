"""Contrato de AppointmentScheduled, AppointmentRescheduled y AppointmentCancelled.

Los eventos son autosuficientes: incluyen la cita completa con nombres de médico y sede.
"""

import datetime as dt
import uuid
from typing import Any

from app.domain.rules import format_hhmm, to_utc_iso
from app.events.envelope import EventEnvelope, build_event
from app.repositories.appointment_repository import AppointmentRecord


def appointment_payload(record: AppointmentRecord) -> dict[str, Any]:
    return {
        "appointmentId": str(record.appointment_id),
        "type": record.type.value,
        "date": record.date.isoformat(),
        "weekday": record.weekday,
        "startTime": format_hhmm(record.start_time),
        "endTime": format_hhmm(record.end_time),
        "physician": {
            "physicianId": str(record.physician_id),
            "name": record.physician_name,
        },
        "medicalCenter": {
            "medicalCenterId": str(record.medical_center_id),
            "name": record.medical_center_name,
            "location": record.medical_center_location,
        },
    }


def appointment_scheduled(
    user_id: uuid.UUID, scheduled_at: dt.datetime, record: AppointmentRecord
) -> EventEnvelope:
    data = {
        "userId": str(user_id),
        "scheduledAt": to_utc_iso(scheduled_at),
        "appointment": appointment_payload(record),
    }
    return build_event("AppointmentScheduled", data, occurred_at=scheduled_at)


def appointment_rescheduled(
    user_id: uuid.UUID,
    rescheduled_at: dt.datetime,
    previous: AppointmentRecord,
    current: AppointmentRecord,
) -> EventEnvelope:
    data = {
        "userId": str(user_id),
        "rescheduledAt": to_utc_iso(rescheduled_at),
        "previousAppointment": appointment_payload(previous),
        "appointment": appointment_payload(current),
    }
    return build_event("AppointmentRescheduled", data, occurred_at=rescheduled_at)


def appointment_cancelled(
    user_id: uuid.UUID, cancelled_at: dt.datetime, record: AppointmentRecord
) -> EventEnvelope:
    data = {
        "userId": str(user_id),
        "cancelledAt": to_utc_iso(cancelled_at),
        "appointment": appointment_payload(record),
    }
    return build_event("AppointmentCancelled", data, occurred_at=cancelled_at)
