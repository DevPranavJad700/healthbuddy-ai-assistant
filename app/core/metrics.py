"""
Prometheus metrics helpers.
"""

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "healthbuddy_http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY_SECONDS = Histogram(
    "healthbuddy_http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

CHAT_PROVIDER_FAILURES = Counter(
    "healthbuddy_chat_provider_failures_total",
    "Total chat failures caused by provider/model availability",
)

CHAT_FALLBACK_RESPONSES = Counter(
    "healthbuddy_chat_fallback_responses_total",
    "Total number of safe fallback responses served",
)

CHAT_ZERO_SOURCE_EVENTS_TOTAL = Counter(
    "healthbuddy_chat_zero_source_events_total",
    "Total zero-source RAG events while corpus is available",
    ["mode", "phase"],
)

AUTH_LOGIN_TOTAL = Counter(
    "healthbuddy_auth_login_total",
    "Authentication login attempts by outcome",
    ["outcome"],
)

AUTH_TOKEN_REFRESH_TOTAL = Counter(
    "healthbuddy_auth_token_refresh_total",
    "Authentication token refresh attempts by outcome",
    ["outcome"],
)

CLINICIAN_REVIEW_EVENTS_TOTAL = Counter(
    "healthbuddy_clinician_review_events_total",
    "Clinician review workflow events",
    ["event"],
)


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
