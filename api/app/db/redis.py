"""Redis client (used as a cache)."""

from functools import lru_cache

from redis import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    password = settings.redis_password.get_secret_value() if settings.redis_password else None
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=password,
        socket_connect_timeout=settings.dependency_timeout_seconds,
        socket_timeout=settings.dependency_timeout_seconds,
        decode_responses=True,
    )
