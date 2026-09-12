"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Healthbuddy-AI application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM Configuration ---
    llm_provider: Literal["huggingface", "custom", "ollama", "openai", "groq"] = "huggingface"
    llm_model: str = "gpt2"
    device: str = "auto"
    max_new_tokens: int = 256
    llm_request_timeout_seconds: int = 45
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 1.5
    llm_retry_backoff_max_seconds: float = 12.0
    llm_retry_jitter_ratio: float = 0.25
    llm_rate_limit_extra_backoff_seconds: float = 2.0
    startup_provider_connectivity_check: bool = True
    startup_provider_check_fail_fast: bool = False
    openai_api_key: str = ""
    groq_api_key: str = ""
    hf_token: str = ""
    secret_key: str = "replace_with_a_long_random_secret_key"

    @property
    def is_secret_key_insecure(self) -> bool:
        """Check if the SECRET_KEY is still a placeholder or too short."""
        weak = {"replace_with_a_long_random_secret_key", "replace_with_a_local_dev_secret_min_32_chars", "changeme", "secret"}
        return self.secret_key.strip().lower() in weak or len(self.secret_key) < 32

    @property
    def is_smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_minutes: int = 10080
    environment: Literal["development", "staging", "production"] = "development"
    strict_production_checks: bool = True
    auth_max_attempts: int = 5
    auth_lockout_minutes: int = 15
    auth_min_password_length: int = 10
    admin_usernames: str = "admin"
    redis_url: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_oauth_scope: str = "openid email profile"

    # --- Embedding Model ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Vector Store Configuration ---
    vector_store_type: Literal["chroma", "pgvector"] = "chroma"
    pgvector_collection_name: str = "healthbuddy_docs"

    # --- ChromaDB ---
    chroma_db_path: str = "./data/chroma_db"
    chroma_collection_name: str = "healthbuddy_docs"

    # --- Database ---
    database_url: str = "sqlite:///./data/healthbuddy.db"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def effective_database_url(self) -> str:
        url = self.database_url
        if self.is_production and url.startswith("sqlite"):
            # In production, we should ideally use PostgreSQL.
            # This is a warning/soft-enforcement.
            pass
        
        # SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # --- Document Processing ---
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_retrieval_results: int = 5

    # --- Server ---
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8000
    log_level: str = "info"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    max_request_size_mb: int = 10
    upload_max_size_mb: int = 10
    strict_upload_mime_check: bool = True
    allowed_upload_mime_types: str = "application/pdf,text/plain,text/markdown"
    rate_limit_requests_per_minute: int = 60
    rate_limit_route_overrides: str = "/api/v1/auth/login=10,/api/v1/chat=40"
    static_asset_cache_seconds: int = 31536000
    preload_vector_store_on_startup: bool = False
    preload_models_on_startup: bool = False
    prewarm_vector_store_in_production: bool = True
    prewarm_models_in_production: bool = True
    db_auto_create_on_startup: bool = True
    db_run_migrations_on_startup: bool = False
    default_input_tokens_per_char: float = 0.25
    default_output_tokens_per_char: float = 0.25
    cost_rate_input_per_1k_tokens_usd: float = 0.0005
    cost_rate_output_per_1k_tokens_usd: float = 0.0015
    response_cache_ttl_seconds: int = 180
    response_cache_max_entries: int = 500
    data_retention_days: int = 365
    audit_retention_days: int = 365
    consent_retention_days: int = 730
    consent_policy_version: str = "2026.04"
    require_stored_consent_for_sensitive: bool = True
    require_terms_acceptance_for_chat: bool = True
    terms_policy_version: str = "2026.04"
    audit_snapshot_signing_key: str = ""

    # --- Email Verification ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@healthbuddy.ai"
    email_verification_required: bool = False

    # --- Chat Limits ---
    max_chat_message_length: int = 2000

    # --- Sentry Error Tracking ---
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05  # 5% of transactions

    # --- Age Gate & Legal ---
    min_user_age: int = 18
    tos_version: str = "2026.05"
    require_tos_acceptance: bool = True

    # --- Daily Query Quota ---
    daily_free_query_limit: int = 50
    quota_enabled: bool = True

    # --- Stripe (Payments — optional) ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_premium_price_id: str = ""

    # --- ARQ (Background Tasks) ---
    arq_queue_name: str = "healthbuddy:arq"
    use_arq_for_emails: bool = False  # Enable once Redis + ARQ worker is running

    @property
    def is_redis_configured(self) -> bool:
        return bool(self.redis_url)

    @property
    def is_sentry_configured(self) -> bool:
        return bool(self.sentry_dsn)

    # --- Custom Transformer ---
    custom_model_path: str = "./data/checkpoints/transformer_best.pt"

    @property
    def chroma_db_abs_path(self) -> Path:
        return Path(self.chroma_db_path).resolve()

    @property
    def custom_model_abs_path(self) -> Path:
        return Path(self.custom_model_path).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["http://localhost:8000"]

    @property
    def allowed_upload_mime_types_list(self) -> list[str]:
        mime_types = [m.strip().lower() for m in self.allowed_upload_mime_types.split(",") if m.strip()]
        return mime_types or ["application/pdf", "text/plain", "text/markdown"]

    @property
    def admin_usernames_list(self) -> list[str]:
        names = [u.strip().lower() for u in self.admin_usernames.split(",") if u.strip()]
        return names

    @property
    def rate_limit_route_overrides_map(self) -> dict[str, int]:
        """Parse per-prefix rate limits from RATE_LIMIT_ROUTE_OVERRIDES.

        Format: /path/prefix=limit,/other/prefix=limit
        """
        mapping: dict[str, int] = {}
        for pair in self.rate_limit_route_overrides.split(","):
            item = pair.strip()
            if not item or "=" not in item:
                continue
            prefix, raw_limit = item.split("=", 1)
            prefix = prefix.strip()
            try:
                limit = int(raw_limit.strip())
            except ValueError:
                continue
            if prefix and limit > 0:
                mapping[prefix] = limit
        return mapping


# Singleton settings instance
settings = Settings()
