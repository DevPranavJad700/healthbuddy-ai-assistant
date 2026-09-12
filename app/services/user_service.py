"""
User Service — User registration, authentication, and profile management.
"""

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import (
    User,
    UserGoal,
    ChatLog,
    SymptomCheck,
    OutcomeEvent,
    ClinicianReview,
    ExperimentAssignment,
    RevokedToken,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.core.logging_config import logger


class UserService:
    """Manages user accounts and profiles."""

    @staticmethod
    def _iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return None

    @staticmethod
    def _validate_password_policy(password: str):
        min_len = settings.auth_min_password_length
        if len(password) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters long")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must include at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must include at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must include at least one number")

    def register(self, db: Session, username: str, email: str, password: str,
                 full_name: str = None, age: int = None, gender: str = None) -> dict:
        """Register a new user."""
        self._validate_password_policy(password)
        if db.query(User).filter(User.username == username).first():
            raise ValueError("Username already exists")
        if db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            age=age,
            gender=gender,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"New user registered: {username}")
        token = create_access_token({"sub": username, "user_id": user.id})
        return {"user_id": user.id, "username": user.username, "token": token}

    def login(self, db: Session, username: str, password: str) -> dict:
        """Authenticate user and return JWT token."""
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid username or password")

        token = create_access_token({"sub": username, "user_id": user.id})
        logger.info(f"User logged in: {username}")
        return {"user_id": user.id, "username": user.username, "token": token}

    def get_profile(self, db: Session, user_id: int) -> dict | None:
        """Get user profile by ID."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {
            "user_id": user.id, "username": user.username, "email": user.email,
            "full_name": user.full_name, "age": user.age, "gender": user.gender,
            "medical_conditions": user.medical_conditions or [],
            "allergies": user.allergies or [],
            "preferred_language": user.preferred_language or "en",
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def update_profile(self, db: Session, user_id: int, **kwargs) -> dict:
        """Update user profile fields."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        for key, value in kwargs.items():
            if hasattr(user, key) and key not in ("id", "hashed_password"):
                setattr(user, key, value)
        user.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(user)
        return self.get_profile(db, user_id)

    def get_personalization_context(self, db: Session, user_id: int) -> str:
        """Build personalization context string for LLM prompt."""
        profile = self.get_profile(db, user_id)
        if not profile:
            return ""
        parts = []
        if profile.get("age"):
            parts.append(f"Patient age: {profile['age']}")
        if profile.get("gender"):
            parts.append(f"Gender: {profile['gender']}")
        if profile.get("medical_conditions"):
            parts.append(f"Known conditions: {', '.join(profile['medical_conditions'])}")
        if profile.get("allergies"):
            parts.append(f"Allergies: {', '.join(profile['allergies'])}")

        goals = self.list_goals(db, user_id)
        active_goals = [g["goal"] for g in goals if g.get("is_active")]
        if active_goals:
            parts.append(f"User goals: {', '.join(active_goals[:5])}")

        return ("USER HEALTH PROFILE:\n" + "\n".join(parts) + "\n\n") if parts else ""

    def list_goals(self, db: Session, user_id: int) -> list[dict]:
        rows = (
            db.query(UserGoal)
            .filter(UserGoal.user_id == user_id)
            .order_by(UserGoal.created_at.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "goal": row.goal,
                "priority": row.priority,
                "is_active": row.is_active,
            }
            for row in rows
        ]

    def add_goal(self, db: Session, user_id: int, goal: str, priority: str = "medium") -> dict:
        row = UserGoal(user_id=user_id, goal=goal.strip(), priority=priority)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "goal": row.goal,
            "priority": row.priority,
            "is_active": row.is_active,
        }

    def remove_goal(self, db: Session, user_id: int, goal_id: int) -> bool:
        row = (
            db.query(UserGoal)
            .filter(UserGoal.id == goal_id, UserGoal.user_id == user_id)
            .first()
        )
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True

    def export_user_data(self, db: Session, user_id: int) -> dict:
        """Export a user's account data for portability before deletion."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        goals = db.query(UserGoal).filter(UserGoal.user_id == user_id).all()
        chat_logs = db.query(ChatLog).filter(ChatLog.user_id == user_id).all()
        symptom_checks = db.query(SymptomCheck).filter(SymptomCheck.user_id == user_id).all()
        outcome_events = db.query(OutcomeEvent).filter(OutcomeEvent.user_id == user_id).all()
        clinician_reviews = db.query(ClinicianReview).filter(ClinicianReview.user_id == user_id).all()
        experiment_assignments = (
            db.query(ExperimentAssignment)
            .filter(ExperimentAssignment.subject_key == str(user_id))
            .all()
        )

        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "user": {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "age": user.age,
                "gender": user.gender,
                "medical_conditions": user.medical_conditions or [],
                "allergies": user.allergies or [],
                "preferred_language": user.preferred_language or "en",
                "created_at": self._iso(user.created_at),
                "updated_at": self._iso(user.updated_at),
            },
            "goals": [
                {
                    "id": g.id,
                    "goal": g.goal,
                    "priority": g.priority,
                    "is_active": g.is_active,
                    "created_at": self._iso(g.created_at),
                    "updated_at": self._iso(g.updated_at),
                }
                for g in goals
            ],
            "chat_logs": [
                {
                    "id": c.id,
                    "session_id": c.session_id,
                    "question": c.question,
                    "response": c.response,
                    "model_used": c.model_used,
                    "provider": c.provider,
                    "created_at": self._iso(c.created_at),
                }
                for c in chat_logs
            ],
            "symptom_checks": [
                {
                    "id": s.id,
                    "symptoms": s.symptoms,
                    "predicted_conditions": s.predicted_conditions,
                    "confidence_scores": s.confidence_scores,
                    "severity": s.severity,
                    "emergency_flagged": s.emergency_flagged,
                    "created_at": self._iso(s.created_at),
                }
                for s in symptom_checks
            ],
            "outcome_events": [
                {
                    "id": o.id,
                    "session_id": o.session_id,
                    "experiment_variant": o.experiment_variant,
                    "helpful": o.helpful,
                    "rating": o.rating,
                    "resolved": o.resolved,
                    "comment": o.comment,
                    "created_at": self._iso(o.created_at),
                }
                for o in outcome_events
            ],
            "clinician_reviews": [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "question": r.question,
                    "response": r.response,
                    "status": r.status,
                    "reviewer_notes": r.reviewer_notes,
                    "created_at": self._iso(r.created_at),
                    "reviewed_at": self._iso(r.reviewed_at),
                }
                for r in clinician_reviews
            ],
            "experiment_assignments": [
                {
                    "id": a.id,
                    "experiment": a.experiment,
                    "subject_key": a.subject_key,
                    "variant": a.variant,
                    "created_at": self._iso(a.created_at),
                }
                for a in experiment_assignments
            ],
            "retention_policy": {
                "data_retention_days": settings.data_retention_days,
                "note": "Aggregated analytics and operational metrics may be retained without direct personal identifiers.",
            },
        }

    def delete_user_data(self, db: Session, user_id: int) -> dict:
        """Delete a user and directly associated records for data-erasure workflows."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        deleted: dict[str, int] = {}

        deleted["chat_logs"] = (
            db.query(ChatLog)
            .filter(ChatLog.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["symptom_checks"] = (
            db.query(SymptomCheck)
            .filter(SymptomCheck.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["outcome_events"] = (
            db.query(OutcomeEvent)
            .filter(OutcomeEvent.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["clinician_reviews"] = (
            db.query(ClinicianReview)
            .filter(ClinicianReview.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["user_goals"] = (
            db.query(UserGoal)
            .filter(UserGoal.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["revoked_tokens"] = (
            db.query(RevokedToken)
            .filter(RevokedToken.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted["experiment_assignments"] = (
            db.query(ExperimentAssignment)
            .filter(ExperimentAssignment.subject_key == str(user_id))
            .delete(synchronize_session=False)
        )

        db.delete(user)
        deleted["users"] = 1
        db.commit()

        logger.info("User data deleted for user_id=%s counts=%s", user_id, deleted)
        return deleted


user_service = UserService()
