"""Liveness and readiness endpoints."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.redis import get_redis
from app.db.session import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    """The app process is alive. Does not touch any dependency."""
    return {"status": "ok"}


def _check_postgres() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Readiness check failed: postgres")
        return False


def _check_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        logger.exception("Readiness check failed: redis")
        return False


@router.get("/ready")
def ready() -> JSONResponse:
    """The app can reach PostgreSQL and Redis. Returns 503 if either is down."""
    checks = {
        "postgres": "ok" if _check_postgres() else "unavailable",
        "redis": "ok" if _check_redis() else "unavailable",
    }
    healthy = all(status == "ok" for status in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "unavailable", "checks": checks},
    )
