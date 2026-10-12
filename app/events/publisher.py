import logging
import time
from collections.abc import Callable
from typing import Protocol

from app.events.envelope import EventEnvelope

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    def publish(self, event: EventEnvelope) -> None: ...


def publish_with_retry(
    publisher: EventPublisher,
    event: EventEnvelope,
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Publica con backoff acotado. La operación de negocio ya está confirmada: un fallo
    definitivo se registra en logs y no revierte nada.
    """
    for attempt in range(1, attempts + 1):
        try:
            publisher.publish(event)
        except Exception:
            logger.error(
                "event_publish_failed",
                exc_info=True,
                extra={
                    "eventId": event.event_id,
                    "eventType": event.detail_type,
                    "userId": event.user_id,
                    "attempt": attempt,
                },
            )
            if attempt < attempts:
                sleep(min(max_delay_seconds, base_delay_seconds * 2 ** (attempt - 1)))
            continue
        logger.info(
            "event_published",
            extra={
                "eventId": event.event_id,
                "eventType": event.detail_type,
                "userId": event.user_id,
                "attempt": attempt,
            },
        )
        return True
    return False
