"""
In-memory authentication abuse protection (throttling and lockouts).
"""

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.core.config import settings
from app.core.logging_config import logger

try:
    import redis
except Exception:  # pragma: no cover - optional dependency at runtime
    redis = None


class AuthProtectionService:
    """Tracks failed login attempts by username and IP."""

    def __init__(self):
        self._attempts_by_user = defaultdict(deque)
        self._attempts_by_ip = defaultdict(deque)
        self._locked_until_user = {}
        self._locked_until_ip = {}
        self._lock = Lock()
        self._redis = None

        if settings.redis_url and redis is not None:
            try:
                self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("Auth protection backend: redis")
            except Exception as e:
                logger.warning(f"Redis unavailable for auth protection, falling back to memory: {e}")
                self._redis = None
        else:
            logger.info("Auth protection backend: in-memory")

    @property
    def _window_seconds(self) -> int:
        return int(timedelta(minutes=settings.auth_lockout_minutes).total_seconds())

    def _lock_user_key(self, username: str) -> str:
        return f"hb:auth:lock:user:{username}"

    def _lock_ip_key(self, ip: str) -> str:
        return f"hb:auth:lock:ip:{ip}"

    def _fail_user_key(self, username: str) -> str:
        return f"hb:auth:fail:user:{username}"

    def _fail_ip_key(self, ip: str) -> str:
        return f"hb:auth:fail:ip:{ip}"

    def _prune(self, queue: deque, now: datetime, window: timedelta):
        cutoff = now - window
        while queue and queue[0] < cutoff:
            queue.popleft()

    def _is_locked(self, key: str, lock_map: dict[str, datetime], now: datetime) -> bool:
        until = lock_map.get(key)
        if until and now < until:
            return True
        if until and now >= until:
            lock_map.pop(key, None)
        return False

    def check_allowed(self, username: str, ip: str) -> tuple[bool, str | None]:
        if self._redis is not None:
            try:
                if self._redis.exists(self._lock_user_key(username)):
                    return False, "Too many failed login attempts for this username. Try again later."
                if self._redis.exists(self._lock_ip_key(ip)):
                    return False, "Too many failed login attempts from this IP. Try again later."
                return True, None
            except Exception as e:
                logger.warning(f"Redis auth check failed, using in-memory fallback: {e}")

        now = datetime.now(UTC)
        with self._lock:
            if self._is_locked(username, self._locked_until_user, now):
                return False, "Too many failed login attempts for this username. Try again later."
            if self._is_locked(ip, self._locked_until_ip, now):
                return False, "Too many failed login attempts from this IP. Try again later."
        return True, None

    def record_failure(self, username: str, ip: str):
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                user_key = self._fail_user_key(username)
                ip_key = self._fail_ip_key(ip)

                pipe.incr(user_key)
                pipe.expire(user_key, self._window_seconds)
                pipe.incr(ip_key)
                pipe.expire(ip_key, self._window_seconds)
                user_count, _, ip_count, _ = pipe.execute()

                if int(user_count) >= settings.auth_max_attempts:
                    self._redis.set(self._lock_user_key(username), "1", ex=self._window_seconds)
                if int(ip_count) >= settings.auth_max_attempts:
                    self._redis.set(self._lock_ip_key(ip), "1", ex=self._window_seconds)
                return
            except Exception as e:
                logger.warning(f"Redis auth failure-record failed, using in-memory fallback: {e}")

        now = datetime.now(UTC)
        window = timedelta(minutes=settings.auth_lockout_minutes)
        lockout_duration = timedelta(minutes=settings.auth_lockout_minutes)

        with self._lock:
            user_q = self._attempts_by_user[username]
            ip_q = self._attempts_by_ip[ip]
            self._prune(user_q, now, window)
            self._prune(ip_q, now, window)
            user_q.append(now)
            ip_q.append(now)

            if len(user_q) >= settings.auth_max_attempts:
                self._locked_until_user[username] = now + lockout_duration
            if len(ip_q) >= settings.auth_max_attempts:
                self._locked_until_ip[ip] = now + lockout_duration

    def record_success(self, username: str, ip: str):
        if self._redis is not None:
            try:
                self._redis.delete(
                    self._fail_user_key(username),
                    self._fail_ip_key(ip),
                    self._lock_user_key(username),
                    self._lock_ip_key(ip),
                )
                return
            except Exception as e:
                logger.warning(f"Redis auth success-record failed, using in-memory fallback: {e}")

        with self._lock:
            self._attempts_by_user.pop(username, None)
            self._attempts_by_ip.pop(ip, None)
            self._locked_until_user.pop(username, None)
            self._locked_until_ip.pop(ip, None)

    def snapshot(self) -> dict:
        """Return lightweight lockout/failure stats for operations dashboards."""
        if self._redis is not None:
            # Redis keys can be large; return backend marker + unknown counts cheaply.
            return {
                "backend": "redis",
                "locked_users": None,
                "locked_ips": None,
                "tracked_user_failures": None,
                "tracked_ip_failures": None,
            }

        with self._lock:
            return {
                "backend": "memory",
                "locked_users": len(self._locked_until_user),
                "locked_ips": len(self._locked_until_ip),
                "tracked_user_failures": len(self._attempts_by_user),
                "tracked_ip_failures": len(self._attempts_by_ip),
            }


auth_protection_service = AuthProtectionService()
