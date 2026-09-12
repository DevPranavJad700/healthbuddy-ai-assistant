"""
Analytics Service — Query logging, metrics tracking, and monitoring.
"""

from datetime import UTC, datetime, timedelta
from threading import Lock
from sqlalchemy import func
from sqlalchemy.orm import Session
import hashlib

from app.core.database import (
    ChatLog,
    SymptomCheck,
    QueryMetric,
    User,
    ExperimentAssignment,
    OutcomeEvent,
    ClinicianReview,
    UsageCostDaily,
)
from app.core.logging_config import logger
from app.core.config import settings


class AnalyticsService:
    """Tracks chat metrics, logs queries, and provides analytics data."""

    def __init__(self):
        self._lock = Lock()
        self._sla_hours_by_triage = {
            "emergency": 1,
            "urgent": 4,
            "self_care": 24,
            "manual_request": 12,
        }
        self._runtime_counters = {
            "chat_errors": 0,
            "safety_flags": 0,
            "emergency_detections": 0,
            "provider_failures": 0,
            "fallback_responses": 0,
        }

    def increment_counter(self, key: str, amount: int = 1):
        with self._lock:
            if key not in self._runtime_counters:
                self._runtime_counters[key] = 0
            self._runtime_counters[key] += amount

    def snapshot_counters(self) -> dict:
        with self._lock:
            return dict(self._runtime_counters)

    def log_chat(self, db: Session, session_id: str, question: str, response: str,
                 model_used: str = "gpt2", provider: str = "huggingface",
                 rag_enabled: bool = True, response_time_ms: float = 0,
                 sources_count: int = 0, temperature: float = 0.7,
                 safety_flagged: bool = False, emergency_detected: bool = False,
                 user_id: int = None):
        """Log a chat interaction to the database."""
        try:
            log = ChatLog(
                user_id=user_id, session_id=session_id, question=question,
                response=response, model_used=model_used, provider=provider,
                rag_enabled=rag_enabled, response_time_ms=response_time_ms,
                sources_count=sources_count, temperature=temperature,
                safety_flagged=safety_flagged, emergency_detected=emergency_detected,
            )
            db.add(log)
            db.commit()

            if safety_flagged:
                self.increment_counter("safety_flags")
            if emergency_detected:
                self.increment_counter("emergency_detections")

            self.log_feature_usage_cost(
                db=db,
                feature="chat",
                provider=provider,
                model=model_used,
                prompt_text=question,
                response_text=response,
            )
        except Exception as e:
            logger.error(f"Failed to log chat: {e}")
            db.rollback()

    @staticmethod
    def _estimate_tokens(text: str, per_char_factor: float) -> int:
        text = text or ""
        return max(1, int(len(text) * per_char_factor)) if text else 0

    def log_feature_usage_cost(
        self,
        db: Session,
        feature: str,
        provider: str,
        model: str,
        prompt_text: str,
        response_text: str,
    ):
        """Persist daily estimated token/cost usage grouped by feature/provider/model."""
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        input_tokens = self._estimate_tokens(prompt_text, settings.default_input_tokens_per_char)
        output_tokens = self._estimate_tokens(response_text, settings.default_output_tokens_per_char)
        est_cost = (
            (input_tokens / 1000.0) * settings.cost_rate_input_per_1k_tokens_usd
            + (output_tokens / 1000.0) * settings.cost_rate_output_per_1k_tokens_usd
        )

        row = (
            db.query(UsageCostDaily)
            .filter(
                UsageCostDaily.date == day,
                UsageCostDaily.feature == feature,
                UsageCostDaily.provider == provider,
                UsageCostDaily.model == model,
            )
            .first()
        )
        if row is None:
            row = UsageCostDaily(
                date=day,
                feature=feature,
                provider=provider,
                model=model,
                request_count=0,
                input_tokens_est=0,
                output_tokens_est=0,
                estimated_cost_usd=0.0,
            )
            db.add(row)

        row.request_count += 1
        row.input_tokens_est += input_tokens
        row.output_tokens_est += output_tokens
        row.estimated_cost_usd += est_cost

    def log_symptom_check(self, db: Session, symptoms: list[str],
                          predicted_conditions: list[dict], confidence_scores: list[float],
                          severity: str, emergency_flagged: bool = False, user_id: int = None):
        """Log a symptom check interaction."""
        try:
            check = SymptomCheck(
                user_id=user_id, symptoms=symptoms,
                predicted_conditions=predicted_conditions,
                confidence_scores=confidence_scores,
                severity=severity, emergency_flagged=emergency_flagged,
            )
            db.add(check)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log symptom check: {e}")
            db.rollback()

    def get_dashboard_stats(self, db: Session, days: int = 30) -> dict:
        """Get aggregated stats for the analytics dashboard."""
        now_utc = datetime.now(UTC)
        cutoff = now_utc - timedelta(days=days)
        try:
            total_chats = db.query(func.count(ChatLog.id)).filter(
                ChatLog.created_at >= cutoff).scalar() or 0
            rag_chats = db.query(func.count(ChatLog.id)).filter(
                ChatLog.created_at >= cutoff, ChatLog.rag_enabled == True).scalar() or 0
            avg_response_time = db.query(func.avg(ChatLog.response_time_ms)).filter(
                ChatLog.created_at >= cutoff, ChatLog.response_time_ms > 0).scalar() or 0
            emergency_count = db.query(func.count(ChatLog.id)).filter(
                ChatLog.created_at >= cutoff, ChatLog.emergency_detected == True).scalar() or 0
            safety_flags = db.query(func.count(ChatLog.id)).filter(
                ChatLog.created_at >= cutoff, ChatLog.safety_flagged == True).scalar() or 0
            symptom_checks_count = db.query(func.count(SymptomCheck.id)).filter(
                SymptomCheck.created_at >= cutoff).scalar() or 0
            total_users = db.query(func.count(User.id)).scalar() or 0

            daily_stats = []
            for i in range(min(days, 7)):
                day = now_utc - timedelta(days=i)
                day_str = day.strftime("%Y-%m-%d")
                day_start = day.replace(hour=0, minute=0, second=0)
                day_end = day.replace(hour=23, minute=59, second=59)
                day_count = db.query(func.count(ChatLog.id)).filter(
                    ChatLog.created_at >= day_start, ChatLog.created_at <= day_end).scalar() or 0
                daily_stats.append({"date": day_str, "queries": day_count})

            recent_questions = db.query(ChatLog.question).filter(
                ChatLog.created_at >= cutoff
            ).order_by(ChatLog.created_at.desc()).limit(10).all()

            feedback_count = db.query(func.count(OutcomeEvent.id)).filter(
                OutcomeEvent.created_at >= cutoff
            ).scalar() or 0
            helpful_count = db.query(func.count(OutcomeEvent.id)).filter(
                OutcomeEvent.created_at >= cutoff,
                OutcomeEvent.helpful == True,
            ).scalar() or 0
            avg_rating = db.query(func.avg(OutcomeEvent.rating)).filter(
                OutcomeEvent.created_at >= cutoff,
                OutcomeEvent.rating.isnot(None),
            ).scalar() or 0
            pending_reviews = db.query(func.count(ClinicianReview.id)).filter(
                ClinicianReview.status == "pending"
            ).scalar() or 0
            overdue_reviews = db.query(func.count(ClinicianReview.id)).filter(
                ClinicianReview.status == "pending",
                ClinicianReview.sla_deadline_at.isnot(None),
                ClinicianReview.sla_deadline_at < now_utc,
            ).scalar() or 0

            usage_today = db.query(UsageCostDaily).filter(
                UsageCostDaily.date == now_utc.strftime("%Y-%m-%d")
            ).all()
            usage_cost_today_usd = round(sum((r.estimated_cost_usd or 0.0) for r in usage_today), 6)
            feature_usage_today: dict[str, dict] = {}
            for row in usage_today:
                feature_row = feature_usage_today.setdefault(
                    row.feature,
                    {
                        "requests": 0,
                        "input_tokens_est": 0,
                        "output_tokens_est": 0,
                        "estimated_cost_usd": 0.0,
                    },
                )
                feature_row["requests"] += row.request_count or 0
                feature_row["input_tokens_est"] += row.input_tokens_est or 0
                feature_row["output_tokens_est"] += row.output_tokens_est or 0
                feature_row["estimated_cost_usd"] += row.estimated_cost_usd or 0.0

            for value in feature_usage_today.values():
                value["estimated_cost_usd"] = round(value["estimated_cost_usd"], 6)

            return {
                "period_days": days, "total_chats": total_chats,
                "rag_chats": rag_chats, "standalone_chats": total_chats - rag_chats,
                "avg_response_time_ms": round(avg_response_time, 2),
                "emergency_detections": emergency_count, "safety_flags": safety_flags,
                "symptom_checks": symptom_checks_count, "total_users": total_users,
                "daily_stats": list(reversed(daily_stats)),
                "recent_questions": [q[0][:100] for q in recent_questions],
                "runtime_counters": self.snapshot_counters(),
                "chat_error_rate_pct": round((self.snapshot_counters().get("chat_errors", 0) / total_chats) * 100, 2) if total_chats else 0,
                "feedback_count": feedback_count,
                "helpful_rate_pct": round((helpful_count / feedback_count) * 100, 2) if feedback_count else 0,
                "avg_rating": round(avg_rating, 2),
                "pending_clinician_reviews": pending_reviews,
                "overdue_clinician_reviews": overdue_reviews,
                "usage_cost_today_usd": usage_cost_today_usd,
                "feature_usage_today": feature_usage_today,
            }
        except Exception as e:
            logger.error(f"Analytics query failed: {e}")
            return {"error": str(e)}

    def get_or_assign_variant(
        self,
        db: Session,
        experiment: str,
        subject_key: str,
        variants: tuple[str, ...] = ("control", "tailored"),
    ) -> str:
        row = (
            db.query(ExperimentAssignment)
            .filter(
                ExperimentAssignment.experiment == experiment,
                ExperimentAssignment.subject_key == subject_key,
            )
            .first()
        )
        if row:
            return row.variant

        digest = hashlib.sha256(f"{experiment}:{subject_key}".encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(variants)
        variant = variants[index]

        row = ExperimentAssignment(
            experiment=experiment,
            subject_key=subject_key,
            variant=variant,
        )
        db.add(row)
        db.commit()
        return variant

    def log_outcome_feedback(
        self,
        db: Session,
        session_id: str,
        user_id: int | None = None,
        experiment_variant: str = "control",
        helpful: bool | None = None,
        rating: int | None = None,
        resolved: bool | None = None,
        comment: str | None = None,
    ) -> dict:
        row = OutcomeEvent(
            user_id=user_id,
            session_id=session_id,
            experiment_variant=experiment_variant,
            helpful=helpful,
            rating=rating,
            resolved=resolved,
            comment=comment,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "session_id": row.session_id,
        }

    def create_clinician_review(
        self,
        db: Session,
        session_id: str,
        question: str,
        response: str,
        user_id: int | None = None,
        triage_level: str | None = None,
        triage_rule_id: str | None = None,
    ) -> dict:
        level = (triage_level or "manual_request").lower()
        priority = "critical" if level == "emergency" else "high" if level == "urgent" else "normal"
        sla_hours = self._sla_hours_by_triage.get(level, 12)
        sla_deadline_at = datetime.now(UTC) + timedelta(hours=sla_hours)

        row = ClinicianReview(
            user_id=user_id,
            session_id=session_id,
            question=question,
            response=response,
            status="pending",
            triage_level=level,
            priority=priority,
            sla_deadline_at=sla_deadline_at,
            closure_audit={"triage_rule_id": triage_rule_id} if triage_rule_id else {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "status": row.status,
            "priority": row.priority,
            "triage_level": row.triage_level,
            "sla_deadline_at": row.sla_deadline_at.isoformat() if row.sla_deadline_at else None,
        }

    def get_experiment_summary(self, db: Session, experiment: str = "response_style") -> dict:
        assignments = (
            db.query(ExperimentAssignment.variant, func.count(ExperimentAssignment.id))
            .filter(ExperimentAssignment.experiment == experiment)
            .group_by(ExperimentAssignment.variant)
            .all()
        )

        feedback = (
            db.query(OutcomeEvent.experiment_variant, func.count(OutcomeEvent.id), func.avg(OutcomeEvent.rating))
            .group_by(OutcomeEvent.experiment_variant)
            .all()
        )

        return {
            "experiment": experiment,
            "assignments": {variant: count for variant, count in assignments},
            "feedback": {
                variant: {
                    "count": count,
                    "avg_rating": round(avg_rating, 2) if avg_rating else 0,
                }
                for variant, count, avg_rating in feedback
            },
        }


analytics_service = AnalyticsService()
