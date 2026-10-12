import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db_session

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db_session)]) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.error("health_database_check_failed", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "checks": {"process": "ok", "database": "error"}},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "checks": {"process": "ok", "database": "ok"}},
    )
