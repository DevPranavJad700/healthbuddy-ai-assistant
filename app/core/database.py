"""
Database configuration — SQLAlchemy setup for users, logs, and analytics.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, Boolean, JSON, ForeignKey, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

from app.core.config import settings

# Database URL from environment/config
DATABASE_URL = settings.effective_database_url

# Ensure sqlite file parent directory exists when using sqlite:///path.db
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = DATABASE_URL.replace("sqlite:///", "", 1)
    # Handle both absolute and relative paths
    if ":" not in sqlite_path and not sqlite_path.startswith("/"):
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

engine_kwargs = {"pool_pre_ping": True}
if "sqlite" in DATABASE_URL:
    # Needed for SQLite + FastAPI threaded access patterns.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production settings for PostgreSQL
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_recycle": 3600,
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(UTC)


# ==========================================
# Database Models
# ==========================================

class User(Base):
    """User profile for personalization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    age = Column(Integer)
    gender = Column(String(20))
    medical_conditions = Column(JSON, default=list)  # e.g., ["diabetes", "hypertension"]
    allergies = Column(JSON, default=list)
    preferred_language = Column(String(12), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    chat_logs = relationship("ChatLog", back_populates="user")
    symptom_checks = relationship("SymptomCheck", back_populates="user")


class ChatLog(Base):
    """Log every chat interaction for analytics."""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(50), index=True)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model_used = Column(String(50))
    provider = Column(String(20))
    rag_enabled = Column(Boolean, default=True)
    response_time_ms = Column(Float)
    sources_count = Column(Integer, default=0)
    temperature = Column(Float, default=0.7)
    safety_flagged = Column(Boolean, default=False)
    emergency_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="chat_logs")


class SymptomCheck(Base):
    """Log symptom checker interactions."""
    __tablename__ = "symptom_checks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    symptoms = Column(JSON, nullable=False)
    predicted_conditions = Column(JSON)
    confidence_scores = Column(JSON)
    severity = Column(String(20))  # low, medium, high, emergency
    emergency_flagged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="symptom_checks")


class QueryMetric(Base):
    """Aggregated metrics for monitoring."""
    __tablename__ = "query_metrics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), index=True)  # YYYY-MM-DD
    total_queries = Column(Integer, default=0)
    rag_queries = Column(Integer, default=0)
    standalone_queries = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, default=0)
    emergency_detections = Column(Integer, default=0)
    safety_flags = Column(Integer, default=0)
    symptom_checks = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)


class UserGoal(Base):
    """User goals for personalized recommendations."""
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    goal = Column(String(160), nullable=False)
    priority = Column(String(20), default="medium")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ExperimentAssignment(Base):
    """Sticky assignment for A/B experiments."""
    __tablename__ = "experiment_assignments"

    id = Column(Integer, primary_key=True, index=True)
    experiment = Column(String(80), index=True, nullable=False)
    subject_key = Column(String(120), index=True, nullable=False)
    variant = Column(String(40), nullable=False)
    created_at = Column(DateTime, default=utc_now)


class OutcomeEvent(Base):
    """Outcome and feedback telemetry tied to sessions."""
    __tablename__ = "outcome_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(50), index=True, nullable=False)
    experiment_variant = Column(String(40), default="control")
    helpful = Column(Boolean, nullable=True)
    rating = Column(Integer, nullable=True)
    resolved = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ClinicianReview(Base):
    """Human clinician review queue for high-risk or flagged responses."""
    __tablename__ = "clinician_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(50), index=True, nullable=False)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    triage_level = Column(String(20), nullable=True)
    priority = Column(String(20), default="normal")
    sla_deadline_at = Column(DateTime, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    closed_by_user_id = Column(Integer, nullable=True)
    closure_reason = Column(String(120), nullable=True)
    closure_audit = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    closed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


class UsageCostDaily(Base):
    """Daily usage and estimated cost telemetry by feature/provider/model."""
    __tablename__ = "usage_cost_daily"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), index=True, nullable=False)  # YYYY-MM-DD
    feature = Column(String(40), index=True, nullable=False)  # chat, symptom_checker, etc.
    provider = Column(String(30), index=True, nullable=False)
    model = Column(String(80), nullable=False)
    request_count = Column(Integer, default=0)
    input_tokens_est = Column(Integer, default=0)
    output_tokens_est = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class RevokedToken(Base):
    """Persist revoked JWT token identifiers to enforce logout/rotation invalidation."""
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    token_type = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class ConsentRecord(Base):
    """Track explicit user consent decisions for governance and audits."""
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(64), index=True, nullable=True)
    consent_type = Column(String(80), index=True, nullable=False)
    policy_version = Column(String(40), nullable=False)
    granted = Column(Boolean, nullable=False)
    scope = Column(String(120), nullable=True)
    source = Column(String(40), default="api")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)


class AuditEvent(Base):
    """Persistent audit event store for governance export endpoints."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(120), index=True, nullable=False)
    status = Column(String(20), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)


# ==========================================
# Database Initialization
# ==========================================

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compat_columns()


def _ensure_sqlite_compat_columns():
    """Best-effort SQLite compatibility migration for newly added columns."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    clinician_required_columns = {
        "triage_level": "TEXT",
        "priority": "TEXT DEFAULT 'normal'",
        "sla_deadline_at": "DATETIME",
        "closed_by_user_id": "INTEGER",
        "closure_reason": "TEXT",
        "closure_audit": "JSON",
        "closed_at": "DATETIME",
    }

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(clinician_reviews)"))
        existing = {row[1] for row in rows}
        for col, ddl in clinician_required_columns.items():
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE clinician_reviews ADD COLUMN {col} {ddl}"))

        user_rows = conn.execute(text("PRAGMA table_info(users)"))
        user_existing = {row[1] for row in user_rows}
        if "preferred_language" not in user_existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language TEXT DEFAULT 'en'"))


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
