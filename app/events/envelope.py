import datetime as dt
from dataclasses import dataclass
from typing import Any

import uuid_utils

from app.core.logging import correlation_id_var
from app.domain.rules import to_utc_iso

SOURCE = "kenko.appointments"
EVENT_VERSION = "1"


@dataclass(frozen=True)
class EventEnvelope:
    detail_type: str
    detail: dict[str, Any]
    source: str = SOURCE

    @property
    def event_id(self) -> str:
        return str(self.detail["metadata"]["eventId"])

    @property
    def user_id(self) -> str:
        return str(self.detail["data"]["userId"])


def build_event(detail_type: str, data: dict[str, Any], occurred_at: dt.datetime) -> EventEnvelope:
    metadata = {
        "eventId": str(uuid_utils.uuid7()),
        "eventVersion": EVENT_VERSION,
        "occurredAt": to_utc_iso(occurred_at),
        "correlationId": correlation_id_var.get() or str(uuid_utils.uuid7()),
    }
    return EventEnvelope(detail_type=detail_type, detail={"metadata": metadata, "data": data})
