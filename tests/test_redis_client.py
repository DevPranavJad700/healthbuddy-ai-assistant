"""Tests for Redis client and connection pool resilience."""

import pytest
from app.services.redis_client import get_redis_status, get_redis, reset_redis_client


def test_redis_status_structure():
    reset_redis_client()
    status = get_redis_status()
    assert isinstance(status, dict)
    assert "configured" in status
    assert "connected" in status
    assert "mode" in status
    assert status["mode"] in {"cluster", "standalone", "memory_fallback"}


def test_redis_graceful_fallback():
    # If no Redis is running locally, get_redis returns None gracefully without crashing
    reset_redis_client()
    client = get_redis()
    # It either connects to a local instance or returns None
    assert client is None or hasattr(client, "ping")
