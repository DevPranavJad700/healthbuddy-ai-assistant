"""
Redis Client — Singleton connection pool for all Redis operations.

Provides a single shared Redis connection used by:
- OTP store (email verification, password reset)
- Rate limiter (sliding window)
- Auth protection (brute-force lockout)
- Response cache (RAG query deduplication)
- Usage metering (daily quota tracking)

Falls back gracefully to None if Redis is unavailable,
allowing in-memory fallbacks in each service.
"""

import redis
from app.core.config import settings
from app.core.logging_config import logger

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Return the singleton Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.redis_url:
        logger.info("REDIS_URL not set — all Redis features using in-memory fallback")
        return None

    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis connected: %s", settings.redis_url.split("@")[-1])  # hide credentials
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable (%s) — using in-memory fallbacks", e)
        return None


def reset_redis_client():
    """Force re-connect on next call. Useful after Redis restarts."""
    global _redis_client
    _redis_client = None
