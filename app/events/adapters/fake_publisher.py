from app.events.envelope import EventEnvelope


class FakePublisher:
    """Publicador en memoria para desarrollo y pruebas. Sustituido por EventBridge en la fase 4.

    `failures` simula fallos transitorios: las primeras N publicaciones lanzan error.
    """

    def __init__(self, failures: int = 0) -> None:
        self.events: list[EventEnvelope] = []
        self._failures_left = failures

    def publish(self, event: EventEnvelope) -> None:
        if self._failures_left > 0:
            self._failures_left -= 1
            raise RuntimeError("Fallo simulado al publicar el evento")
        self.events.append(event)
