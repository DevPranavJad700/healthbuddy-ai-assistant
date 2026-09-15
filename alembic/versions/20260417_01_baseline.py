"""baseline schema — initial table definitions

Revision ID: 20260417_01
Revises:
Create Date: 2026-04-17

Creates the eight core tables that the application needs at launch:
  users, chat_logs, symptom_checks, query_metrics, user_goals,
  experiment_assignments, outcome_events, clinician_reviews
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260417_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("medical_conditions", sa.JSON(), nullable=True),
        sa.Column("allergies", sa.JSON(), nullable=True),
        sa.Column("preferred_language", sa.String(12), nullable=True, server_default="en"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # chat_logs
    # ------------------------------------------------------------------
    op.create_table(
        "chat_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(50), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("rag_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("response_time_ms", sa.Float(), nullable=True),
        sa.Column("sources_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("temperature", sa.Float(), nullable=True, server_default="0.7"),
        sa.Column("safety_flagged", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("emergency_detected", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_logs_session_id", "chat_logs", ["session_id"])

    # ------------------------------------------------------------------
    # symptom_checks
    # ------------------------------------------------------------------
    op.create_table(
        "symptom_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("symptoms", sa.JSON(), nullable=False),
        sa.Column("predicted_conditions", sa.JSON(), nullable=True),
        sa.Column("confidence_scores", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("emergency_flagged", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ------------------------------------------------------------------
    # query_metrics
    # ------------------------------------------------------------------
    op.create_table(
        "query_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.String(10), nullable=True),
        sa.Column("total_queries", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("rag_queries", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("standalone_queries", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=True, server_default="0"),
        sa.Column("emergency_detections", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("safety_flags", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("symptom_checks", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("unique_users", sa.Integer(), nullable=True, server_default="0"),
    )
    op.create_index("ix_query_metrics_date", "query_metrics", ["date"])

    # ------------------------------------------------------------------
    # user_goals
    # ------------------------------------------------------------------
    op.create_table(
        "user_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("goal", sa.String(160), nullable=False),
        sa.Column("priority", sa.String(20), nullable=True, server_default="medium"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_goals_user_id", "user_goals", ["user_id"])

    # ------------------------------------------------------------------
    # experiment_assignments
    # ------------------------------------------------------------------
    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment", sa.String(80), nullable=False),
        sa.Column("subject_key", sa.String(120), nullable=False),
        sa.Column("variant", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_experiment_assignments_experiment", "experiment_assignments", ["experiment"])
    op.create_index("ix_experiment_assignments_subject_key", "experiment_assignments", ["subject_key"])

    # ------------------------------------------------------------------
    # outcome_events
    # ------------------------------------------------------------------
    op.create_table(
        "outcome_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(50), nullable=False),
        sa.Column("experiment_variant", sa.String(40), nullable=True, server_default="control"),
        sa.Column("helpful", sa.Boolean(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_outcome_events_session_id", "outcome_events", ["session_id"])

    # ------------------------------------------------------------------
    # clinician_reviews
    # ------------------------------------------------------------------
    op.create_table(
        "clinician_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=True, server_default="pending"),
        sa.Column("triage_level", sa.String(20), nullable=True),
        sa.Column("priority", sa.String(20), nullable=True, server_default="normal"),
        sa.Column("sla_deadline_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("closure_reason", sa.String(120), nullable=True),
        sa.Column("closure_audit", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_clinician_reviews_session_id", "clinician_reviews", ["session_id"])

    # ------------------------------------------------------------------
    # consent_records
    # ------------------------------------------------------------------
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("consent_type", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("scope", sa.String(120), nullable=True),
        sa.Column("source", sa.String(40), nullable=True, server_default="api"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_consent_records_session_id", "consent_records", ["session_id"])
    op.create_index("ix_consent_records_consent_type", "consent_records", ["consent_type"])
    op.create_index("ix_consent_records_created_at", "consent_records", ["created_at"])

    # ------------------------------------------------------------------
    # audit_events
    # ------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_status", "audit_events", ["status"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("consent_records")
    op.drop_table("clinician_reviews")
    op.drop_table("outcome_events")
    op.drop_table("experiment_assignments")
    op.drop_table("user_goals")
    op.drop_table("query_metrics")
    op.drop_table("symptom_checks")
    op.drop_table("chat_logs")
    op.drop_table("users")
