"""
Healthbuddy-AI — Main FastAPI Application.

Entry point for the application. Configures:
- CORS middleware
- Static file serving (frontend)
- API route registration (chat, documents, auth, symptoms, analytics)
- Startup/shutdown lifecycle events
- Database initialization
- Global exception handling
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app import __version__
from app.core.config import settings
from app.core.logging_config import logger
from app.core.database import init_db, SessionLocal
from app.core.middleware import (
    RequestSizeLimitMiddleware,
    RateLimitMiddleware,
    RequestContextLoggingMiddleware,
    CSRFProtectionMiddleware,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.v1 import chat, documents, auth, symptoms, analytics, personalization, compliance, integrations, admin, usage
from app.models.schemas import HealthCheckResponse
from app.core.metrics import render_prometheus_metrics
from app.services.vector_store import vector_store_service
from app.services.rag_service import rag_service
from app.services.document_processor import DocumentProcessor
from app.services.llm_provider import check_provider_connectivity
from app.services.redis_client import get_redis_status


# ==========================================
# Sentry — Error Tracking (optional)
# ==========================================

def _init_sentry():
    """Initialise Sentry if DSN is configured. Scrubs PHI before sending."""
    if not settings.is_sentry_configured:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        _PHI_FIELDS = {"email", "username", "password", "otp", "token", "full_name"}

        def _before_send(event, hint):
            # Strip PHI from request data
            req = event.get("request", {})
            for section in ("data", "query_string"):
                if isinstance(req.get(section), dict):
                    for field in _PHI_FIELDS:
                        req[section].pop(field, None)
            return event

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.environment,
            release=__version__,
            before_send=_before_send,
            send_default_pii=False,  # never auto-send user PII
        )
        logger.info("Sentry initialised (env=%s)", settings.environment)
    except ImportError:
        logger.warning("sentry-sdk not installed — skipping Sentry init")
    except Exception as e:
        logger.warning("Sentry init failed: %s", e)


_init_sentry()




# ==========================================
# Lifecycle Events
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    _validate_production_security()

    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token

    # --- STARTUP ---
    logger.info("=" * 60)
    logger.info(f"Starting Healthbuddy-AI v{__version__}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info("=" * 60)

    _run_startup_checks()

    if settings.db_run_migrations_on_startup:
        _run_startup_migrations()

    # Keep create_all only for local/dev convenience.
    if settings.db_auto_create_on_startup:
        init_db()
        logger.info("Database initialized via create_all")
    else:
        logger.info("Database auto-create disabled; expecting schema managed by migrations")

    prewarm_vector_store = settings.preload_vector_store_on_startup or (
        settings.is_production and settings.prewarm_vector_store_in_production
    )
    prewarm_models = settings.preload_models_on_startup or (
        settings.is_production and settings.prewarm_models_in_production
    )

    # Initialize vector store and optional sample corpus preload.
    if prewarm_vector_store:
        vector_store_service.initialize()
        if vector_store_service.get_total_chunks() == 0:
            _load_sample_knowledge_base()
        logger.info("Vector store preloaded")
    else:
        logger.info("Vector store preload disabled; will initialize lazily")

    # Initialize RAG service (loads LLM) only when enabled.
    if prewarm_models:
        try:
            rag_service.initialize()
            logger.info("RAG service ready")
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            logger.warning("Chat will not work until the LLM is loaded successfully")
    else:
        logger.info("Model preload disabled; LLM will initialize on first chat request")

    logger.info("Application startup complete")

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down Healthbuddy-AI...")


def _load_sample_knowledge_base():
    """Load sample health documents into the vector store on first run."""
    sample_dir = Path("./data/knowledge_base")
    if not sample_dir.exists():
        logger.info("No sample knowledge base found, skipping")
        return

    logger.info("Loading sample knowledge base...")
    processor = DocumentProcessor()
    chunks = processor.process_directory(str(sample_dir))

    if chunks:
        vector_store_service.add_documents(chunks)
        logger.info(f"Loaded {len(chunks)} chunks from sample knowledge base")


def _validate_production_security():
    """Fail fast when production security settings are unsafe."""
    if settings.environment != "production":
        return

    if not settings.strict_production_checks:
        logger.warning("Production strict checks are disabled")
        return

    weak_defaults = {
        "change-me-in-production",
        "change-me-in-production-with-a-long-random-secret",
        "replace_with_a_long_random_secret_key",
    }

    if settings.secret_key in weak_defaults or len(settings.secret_key) < 32:
        raise RuntimeError(
            "Invalid SECRET_KEY for production. Set a random secret with at least 32 characters."
        )

    if "*" in settings.cors_origins_list:
        raise RuntimeError(
            "Invalid CORS_ORIGINS for production. Use explicit allowed origins, not '*'."
        )

    if any("localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origins_list):
        raise RuntimeError(
            "Invalid CORS_ORIGINS for production. Replace localhost origins with real frontend hostnames."
        )

    if settings.database_url.startswith("sqlite"):
        raise RuntimeError(
            "Invalid DATABASE_URL for production. Use PostgreSQL (or equivalent) instead of SQLite."
        )

    if settings.access_token_expire_minutes > 120:
        raise RuntimeError(
            "ACCESS_TOKEN_EXPIRE_MINUTES too high for production. Use <= 120 minutes."
        )

    _validate_required_env_for_provider()


def _validate_required_env_for_provider():
    """Validate provider-specific required environment variables."""
    if settings.llm_provider == "groq" and not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

    if settings.llm_provider == "openai" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    if settings.llm_provider == "huggingface" and not settings.hf_token:
        raise RuntimeError("HF_TOKEN is required when LLM_PROVIDER=huggingface")


def _run_startup_checks():
    """Probe critical dependencies at startup for faster failure diagnosis."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Startup check: database connectivity OK")
    finally:
        db.close()

    if settings.llm_provider == "groq" and not settings.groq_api_key:
        logger.warning("Startup check: GROQ_API_KEY missing; provider calls may fallback/fail")
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        logger.warning("Startup check: OPENAI_API_KEY missing; provider calls may fallback/fail")

    if settings.startup_provider_connectivity_check:
        ok, detail = check_provider_connectivity(timeout_seconds=settings.llm_request_timeout_seconds)
        if ok:
            logger.info("Startup check: %s", detail)
        else:
            if settings.startup_provider_check_fail_fast:
                raise RuntimeError(f"Startup provider connectivity check failed: {detail}")
            logger.warning("Startup check: %s", detail)

    # Vector store check remains lazy when preload is disabled.
    if settings.preload_vector_store_on_startup:
        logger.info("Startup check: vector store preload enabled")
    else:
        logger.info("Startup check: vector store preload disabled (lazy init)")


def _run_startup_migrations():
    """Run alembic migrations programmatically when configured."""
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Startup migrations: alembic upgrade head completed")
    except Exception as e:
        raise RuntimeError(f"Failed to run startup migrations: {e}") from e


# ==========================================
# FastAPI App
# ==========================================

docs_url = None if settings.environment == "production" else "/api/docs"
redoc_url = None if settings.environment == "production" else "/api/redoc"

app = FastAPI(
    title="Healthbuddy-AI",
    description=(
        "A production-grade AI health chatbot powered by RAG "
        "(Retrieval-Augmented Generation) with a custom PyTorch transformer "
        "and HuggingFace models. Features: Symptom Checker, Emergency Detection, "
        "Medical Safety Guardrails, Report Summarization, JWT Authentication, "
        "Analytics Dashboard, and Explainable AI."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)


# ==========================================
# Middleware
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RequestSizeLimitMiddleware,
    max_bytes=settings.max_request_size_mb * 1024 * 1024,
)

app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_requests_per_minute,
    route_overrides=settings.rate_limit_route_overrides_map,
    exempt_prefixes=[
        "/api/health",
        "/api/live",
        "/api/ready",
        "/api/metrics",
        "/api/docs",
        "/api/redoc",
        "/static",
    ],
)

app.add_middleware(RequestContextLoggingMiddleware)

app.add_middleware(
    CSRFProtectionMiddleware,
    allowed_origins=settings.cors_origins_list,
)

if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/static/"):
        response.headers.setdefault(
            "Cache-Control",
            f"public, max-age={settings.static_asset_cache_seconds}, immutable",
        )
    elif path in {"/", "/index.html"}:
        response.headers.setdefault("Cache-Control", "no-store")

    return response


# ==========================================
# Global Exception Handler
# ==========================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler to prevent leaking stack traces."""
    exc_str = str(exc).lower()
    if "auth" in exc_str or "token" in exc_str:
        error_class = "auth"
    elif "validation" in exc_str:
        error_class = "validation"
    elif "sqlite" in exc_str or "database" in exc_str:
        error_class = "dependency"
    elif "model" in exc_str or "transformer" in exc_str:
        error_class = "model"
    else:
        error_class = "unknown"

    logger.error(
        "Unhandled exception class=%s path=%s detail=%s",
        error_class,
        request.url.path,
        exc,
        exc_info=True,
    )
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal server error occurred. Please try again.",
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    code = f"http_{exc.status_code}"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    # Ensure details are JSON serializable (convert to string if needed)
    try:
        details = exc.errors()
    except Exception:
        details = str(exc)
        
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": request_id,
                "details": details,
            }
        },
    )


# ==========================================
# API Routes
# ==========================================

app.include_router(chat.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(symptoms.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(personalization.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")


# ==========================================
# Health Check
# ==========================================

@app.get(
    "/api/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health check",
)
async def health_check() -> HealthCheckResponse:
    """Check application health and status."""
    return HealthCheckResponse(
        status="healthy",
        version=__version__,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        documents_loaded=vector_store_service.get_total_chunks(),
        vector_store_ready=vector_store_service.is_ready(),
        redis_status=get_redis_status(),
    )


@app.get("/api/live", tags=["Health"], summary="Liveness check")
async def liveness_check():
    """Liveness probe for container orchestrators."""
    return {"status": "alive"}


@app.get("/api/ready", tags=["Health"], summary="Readiness check")
async def readiness_check():
    """Readiness probe that ensures key runtime components are initialized."""
    require_vector_ready = settings.preload_vector_store_on_startup or (
        settings.is_production and settings.prewarm_vector_store_in_production
    )
    require_model_ready = settings.preload_models_on_startup or (
        settings.is_production and settings.prewarm_models_in_production
    )

    vector_ready = vector_store_service.is_ready() or not require_vector_ready
    model_ready = rag_service.is_ready() or not require_model_ready
    ready = vector_ready and model_ready
    if ready:
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/api/startup-diagnostics", tags=["Health"], summary="Startup diagnostics")
async def startup_diagnostics():
    """Detailed runtime diagnostics for startup readiness and environment posture."""
    diagnostics = {
        "environment": settings.environment,
        "strict_production_checks": settings.strict_production_checks,
        "llm_provider": settings.llm_provider,
        "provider_keys": {
            "groq_api_key_present": bool(settings.groq_api_key),
            "openai_api_key_present": bool(settings.openai_api_key),
            "hf_token_present": bool(settings.hf_token),
        },
        "startup_flags": {
            "preload_vector_store_on_startup": settings.preload_vector_store_on_startup,
            "preload_models_on_startup": settings.preload_models_on_startup,
            "prewarm_vector_store_in_production": settings.prewarm_vector_store_in_production,
            "prewarm_models_in_production": settings.prewarm_models_in_production,
        },
        "runtime": {
            "vector_store_ready": vector_store_service.is_ready(),
            "documents_loaded": vector_store_service.get_total_chunks(),
            "rag_service_ready": rag_service.is_ready(),
        },
    }

    return diagnostics


@app.get("/api/metrics", include_in_schema=False)
async def metrics_endpoint():
    payload, content_type = render_prometheus_metrics()
    return Response(content=payload, media_type=content_type)


# ==========================================
# Static Files (Frontend)
# ==========================================

# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend application."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Healthbuddy-AI API is running. Visit /api/docs for API documentation."}


@app.get("/privacy", include_in_schema=False)
async def serve_privacy_notice():
    """Serve the privacy notice used by the frontend consent flow."""
    privacy_path = frontend_dir / "privacy.html"
    if privacy_path.exists():
        return FileResponse(str(privacy_path))
    return {"detail": "Privacy notice not found."}


@app.get("/terms", include_in_schema=False)
async def serve_terms_notice():
    """Serve terms of use for health-adjacent assistant behavior."""
    terms_path = frontend_dir / "terms.html"
    if terms_path.exists():
        return FileResponse(str(terms_path))
    return {"detail": "Terms of use not found."}
