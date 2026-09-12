"""
Usage Service — Daily query quota tracking per user.

Uses Redis (preferred) for atomic, cross-worker counters with automatic
midnight-UTC reset. Falls back to in-memory for development.

Quota tiers:
  Free  → DAILY_FREE_QUERY_LIMIT (default: 50) queries/day
  Admin → unlimited
"""

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.logging_config import logger
from app.services.redis_client import get_redis

# ---- in-memory fallback ----
_mem_usage: dict[int, dict] = {}


class QuotaExceeded(Exception):
    """Raised when a user exceeds their daily query quota."""
    def __init__(self, used: int, limit: int, resets_at: str):
        self.used = used
        self.limit = limit
        self.resets_at = resets_at
        super().__init__(f"Daily query limit reached ({used}/{limit}). Resets at {resets_at}.")


def _midnight_utc_ttl() -> int:
    """Seconds until next midnight UTC."""
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def _redis_key(user_id: int) -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"hb:usage:{user_id}:{today}"


def get_quota_status(user_id: int, is_admin: bool = False) -> dict:
    """Return current usage status for a user."""
    limit = settings.daily_free_query_limit
    resets_at = (
        (datetime.now(UTC) + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )

    if is_admin:
        return {"used": 0, "limit": -1, "unlimited": True, "resets_at": resets_at}

    r = get_redis()
    if r is not None:
        try:
            used = int(r.get(_redis_key(user_id)) or 0)
            return {"used": used, "limit": limit, "unlimited": False, "resets_at": resets_at}
        except Exception as e:
            logger.warning("Redis quota read failed: %s", e)

    # In-memory fallback
    today = datetime.now(UTC).date().isoformat()
    record = _mem_usage.get(user_id, {})
    if record.get("date") != today:
        record = {"date": today, "count": 0}
        _mem_usage[user_id] = record
    return {"used": record["count"], "limit": limit, "unlimited": False, "resets_at": resets_at}


def check_and_increment_quota(user_id: int, is_admin: bool = False) -> dict:
    """
    Check if user has quota remaining, increment counter, return status.
    Raises QuotaExceeded if the limit is reached.
    """
    limit = settings.daily_free_query_limit
    resets_at = (
        (datetime.now(UTC) + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )

    if is_admin:
        return {"used": 0, "limit": -1, "unlimited": True, "resets_at": resets_at}

    r = get_redis()
    if r is not None:
        try:
            key = _redis_key(user_id)
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = pipe.execute()
            used = int(results[0])
            ttl = int(results[1])

            # Set TTL on first increment for this day
            if ttl < 0:
                r.expire(key, _midnight_utc_ttl())

            if used > limit:
                # Decrement back (don't count the rejected request)
                r.decr(key)
                raise QuotaExceeded(used=limit, limit=limit, resets_at=resets_at)

            return {"used": used, "limit": limit, "unlimited": False, "resets_at": resets_at}
        except QuotaExceeded:
            raise
        except Exception as e:
            logger.warning("Redis quota check failed, allowing request: %s", e)

    # In-memory fallback
    today = datetime.now(UTC).date().isoformat()
    record = _mem_usage.setdefault(user_id, {"date": today, "count": 0})
    if record.get("date") != today:
        record.update({"date": today, "count": 0})

    record["count"] += 1
    if record["count"] > limit:
        record["count"] = limit  # cap at limit
        raise QuotaExceeded(used=limit, limit=limit, resets_at=resets_at)

    return {"used": record["count"], "limit": limit, "unlimited": False, "resets_at": resets_at}


def reset_quota(user_id: int):
    """Admin: manually reset a user's daily quota."""
    r = get_redis()
    if r is not None:
        try:
            r.delete(_redis_key(user_id))
            return
        except Exception as e:
            logger.warning("Redis quota reset failed: %s", e)
    _mem_usage.pop(user_id, None)
