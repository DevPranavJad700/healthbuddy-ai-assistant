"""
Custom middleware for production hardening.
"""

from collections import defaultdict, deque
from contextvars import ContextVar
from threading import Lock
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import logger
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY_SECONDS


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get()


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length above the configured limit."""

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": "Request body too large.",
                            }
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "invalid_content_length",
                            "message": "Invalid Content-Length header.",
                        }
                    },
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP/user rate limiting — Redis sliding window with in-memory fallback."""

    def __init__(
        self,
        app,
        requests_per_minute: int,
        exempt_prefixes: list[str] | None = None,
        route_overrides: dict[str, int] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        self.hits = defaultdict(deque)   # in-memory fallback
        self.lock = Lock()
        self.exempt_prefixes = tuple(exempt_prefixes or [])
        self.route_overrides = route_overrides or {}
        self._redis = None
        self._redis_checked = False

    def _get_redis(self):
        """Lazy-fetch Redis (avoids import cycle at class definition time)."""
        if not self._redis_checked:
            try:
                from app.services.redis_client import get_redis
                self._redis = get_redis()
            except Exception:
                self._redis = None
            self._redis_checked = True
        return self._redis

    def _resolve_limit(self, path: str) -> int:
        for prefix, override in self.route_overrides.items():
            if path.startswith(prefix):
                return override
        return self.requests_per_minute

    def _resolve_bucket(self, path: str) -> str:
        for prefix in self.route_overrides:
            if path.startswith(prefix):
                return prefix
        return "*"

    @staticmethod
    def _resolve_subject_key(request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token:
                try:
                    from app.core.security import decode_access_token

                    payload = decode_access_token(token)
                    user_id = payload.get("user_id") if payload else None
                    if user_id is not None:
                        return f"user:{user_id}"
                except Exception:
                    pass
        return f"ip:{ip}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.exempt_prefixes and path.startswith(self.exempt_prefixes):
            return await call_next(request)

        subject_key = self._resolve_subject_key(request)
        limit = self._resolve_limit(path)
        bucket = self._resolve_bucket(path)
        now = time.time()

        # --- Redis sliding window (atomic, shared across all workers) ---
        r = self._get_redis()
        if r is not None:
            try:
                redis_key = f"hb:rl:{subject_key}:{bucket}"
                pipe = r.pipeline()
                cutoff = now - self.window_seconds
                pipe.zremrangebyscore(redis_key, "-inf", cutoff)   # evict old
                pipe.zadd(redis_key, {str(now): now})              # record hit
                pipe.zcard(redis_key)                               # count window
                pipe.expire(redis_key, 61)                         # auto-expire
                results = pipe.execute()
                count = int(results[2])
                
                remaining = max(0, limit - count)
                if count > limit:
                    return JSONResponse(
                        status_code=429,
                        content={"error": {"code": "rate_limit_exceeded",
                                           "message": "Rate limit exceeded. Please retry later."}},
                        headers={
                            "Retry-After": "60",
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0"
                        },
                    )
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                return response
            except Exception:
                pass  # Redis error → fall through to in-memory

        # --- In-memory fallback (single-worker dev mode) ---
        with self.lock:
            q = self.hits[(subject_key, bucket)]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "rate_limit_exceeded",
                                       "message": "Rate limit exceeded. Please retry later."}},
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0"
                    },
                )
            q.append(now)
            remaining = limit - len(q)

        # Periodic cleanup: evict stale keys every ~500 requests
        if len(self.hits) > 10_000:
            with self.lock:
                stale_cutoff = now - self.window_seconds * 2
                stale_keys = [
                    k for k, dq in self.hits.items()
                    if not dq or dq[-1] < stale_cutoff
                ]
                for k in stale_keys:
                    del self.hits[k]

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class RequestContextLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request ID and emit structured request logs."""

    @staticmethod
    def _resolve_subject_and_session(request: Request) -> tuple[str, str]:
        subject = "anonymous"
        session_id = request.headers.get("X-Session-ID", "") or request.query_params.get("session_id", "")

        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token:
                try:
                    from app.core.security import decode_access_token

                    payload = decode_access_token(token)
                    if payload:
                        user_id = payload.get("user_id")
                        if user_id is not None:
                            subject = f"user:{user_id}"
                        else:
                            subject = "authenticated"
                except Exception:
                    subject = "authenticated"

        return subject, session_id or "-"

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id
        subject, session_id = self._resolve_subject_and_session(request)

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            normalized_path = request.url.path
            REQUEST_COUNT.labels(
                method=request.method,
                path=normalized_path,
                status=str(status_code),
            ).inc()
            REQUEST_LATENCY_SECONDS.labels(
                method=request.method,
                path=normalized_path,
            ).observe(elapsed_ms / 1000.0)
            logger.info(
                "request_id=%s subject=%s session_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
                request_id,
                subject,
                session_id,
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
            )
            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response


# ==========================================
# CSRF Protection Middleware
# ==========================================

class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Lightweight CSRF protection for state-mutating requests.

    Verifies that POST/PUT/PATCH/DELETE requests from browsers include
    a matching Origin or Referer header. API clients using Bearer tokens
    are exempt since CSRF attacks cannot set Authorization headers.
    """

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    EXEMPT_PATHS = {"/api/v1/auth/google/callback"}

    def __init__(self, app, allowed_origins: list[str] | None = None):
        super().__init__(app)
        self.allowed_origins = set()
        for origin in (allowed_origins or []):
            parsed = origin.strip().rstrip("/").lower()
            if parsed:
                self.allowed_origins.add(parsed)

    async def dispatch(self, request: Request, call_next):
        if request.method not in self.MUTATING_METHODS:
            return await call_next(request)

        # Bearer-token API clients are not vulnerable to CSRF
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        # Exempt specific callback paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check Origin header (preferred) or Referer
        origin = request.headers.get("origin", "").strip().rstrip("/").lower()
        referer = request.headers.get("referer", "").strip().lower()
        host = request.headers.get("host", "").strip().lower()

        if origin:
            from urllib.parse import urlparse
            origin_netloc = urlparse(origin).netloc.lower()
            if origin not in self.allowed_origins and origin_netloc != host:
                logger.warning("CSRF: rejected origin=%s path=%s", origin, request.url.path)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: origin not allowed"},
                )
        elif referer:
            # Extract origin from referer
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            ref_origin = f"{parsed.scheme}://{parsed.netloc}".lower()
            if ref_origin not in self.allowed_origins and parsed.netloc.lower() != host:
                logger.warning("CSRF: rejected referer=%s path=%s", ref_origin, request.url.path)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: referer not allowed"},
                )
        # If neither Origin nor Referer, the request is likely from a non-browser
        # client (curl, Postman) which is not vulnerable to CSRF — allow it.

        return await call_next(request)


# ==========================================
# HTTPS Redirect Middleware (Production)
# ==========================================

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    In production, redirect all HTTP requests to HTTPS.
    Respects X-Forwarded-Proto from reverse proxies (nginx, AWS ALB).
    """

    async def dispatch(self, request: Request, call_next):
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "http":
            url = request.url.replace(scheme="https")
            from starlette.responses import RedirectResponse
            return RedirectResponse(url=str(url), status_code=301)
        return await call_next(request)


# ==========================================
# Security Headers Middleware
# ==========================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard security headers including Content-Security-Policy.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        script_src = "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"
        if not settings.is_production:
            script_src += " 'unsafe-eval'"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src {script_src}; "
            f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data:;"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

