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

import time
from typing import Any

try:
    import redis
    from redis.connection import ConnectionPool
except ImportError:
    redis = None
    ConnectionPool = None

from app.core.config import settings
from app.core.logging_config import logger

_redis_pool: Any = None
_redis_client: Any = None
_last_connect_fail_time: float = 0.0
CONNECT_COOLDOWN_SECONDS: float = 15.0


def _get_pool():
    """Create or return existing connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    if redis is None or not settings.redis_url:
        return None

    try:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
            retry_on_timeout=False,
            health_check_interval=30,
            max_connections=50,
        )
        return _redis_pool
    except Exception as e:
        logger.warning("Failed to initialize Redis connection pool (%s)", e)
        return None


def get_redis(ping: bool = True):
    """Return the singleton Redis client, or None if unavailable."""
    global _redis_client, _last_connect_fail_time
    if redis is None or not settings.redis_url:
        return None
    if _redis_client is not None:
        if not ping:
            return _redis_client
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
            _last_connect_fail_time = time.time()

    # Circuit breaker: avoid hammering offline Redis on every request
    if time.time() - _last_connect_fail_time < CONNECT_COOLDOWN_SECONDS:
        return None

    pool = _get_pool()
    if pool is None:
        _last_connect_fail_time = time.time()
        return None

    try:
        client = redis.Redis(connection_pool=pool)
        if ping:
            client.ping()
        _redis_client = client
        _last_connect_fail_time = 0.0
        logger.info("Redis connected: %s", settings.redis_url.split("@")[-1])  # hide credentials
        return _redis_client
    except Exception as e:
        _last_connect_fail_time = time.time()
        logger.warning("Redis unavailable (%s) — using in-memory fallbacks", e)
        _redis_client = None
        return None


def get_redis_status() -> dict:
    """Return detailed health and connectivity metrics for Redis without redundant pings."""
    global _redis_client, _last_connect_fail_time
    if redis is None or not settings.redis_url:
        return {
            "configured": False,
            "connected": False,
            "mode": "memory_fallback",
            "latency_ms": None,
        }

    # Fast path: if already in circuit breaker cooldown, return immediately without socket wait
    if _redis_client is None and (time.time() - _last_connect_fail_time < CONNECT_COOLDOWN_SECONDS):
        return {
            "configured": True,
            "connected": False,
            "mode": "memory_fallback",
            "latency_ms": None,
        }

    # Fetch client without pre-ping to eliminate double-ping latency
    client = get_redis(ping=False)
    if client is None:
        return {
            "configured": True,
            "connected": False,
            "mode": "memory_fallback",
            "latency_ms": None,
        }

    try:
        t0 = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Check if running in cluster mode
        try:
            info = client.info()
            cluster_enabled = info.get("cluster_enabled", 0) == 1
            mode = "cluster" if cluster_enabled else "standalone"
        except Exception:
            mode = "standalone"

        return {
            "configured": True,
            "connected": True,
            "mode": mode,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        _redis_client = None
        _last_connect_fail_time = time.time()
        logger.warning("Redis health check ping failed: %s", e)
        return {
            "configured": True,
            "connected": False,
            "mode": "memory_fallback",
            "latency_ms": None,
        }


def reset_redis_client():
    """Force re-connect on next call. Useful after Redis restarts."""
    global _redis_client, _redis_pool, _last_connect_fail_time
    _redis_client = None
    _redis_pool = None
    _last_connect_fail_time = 0.0
