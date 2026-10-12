import datetime as dt
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.routes import appointments, catalog, health
from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, correlation_id_middleware
from app.db.session import create_db_engine, create_session_factory
from app.domain.rules import now_in_business_timezone
from app.events.adapters.fake_publisher import FakePublisher
from app.events.publisher import EventPublisher

API_PREFIX = "/api/v1"
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    publisher: EventPublisher | None = None,
    clock: Callable[[], dt.datetime] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.database_url)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("service_started", extra={"environment": settings.environment})
        try:
            yield
        finally:
            engine.dispose()
            logger.info("service_stopped")

    app = FastAPI(
        title="appointments-service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.state.publisher = publisher or FakePublisher()
    app.state.clock = clock or now_in_business_timezone
    app.middleware("http")(correlation_id_middleware)
    register_exception_handlers(app)

    api_router = APIRouter(prefix=API_PREFIX)
    api_router.include_router(health.router)
    api_router.include_router(appointments.router)
    api_router.include_router(catalog.router)
    app.include_router(api_router)
    return app
