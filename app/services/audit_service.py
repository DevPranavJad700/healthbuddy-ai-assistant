"""
Lightweight audit logging service for sensitive actions.
"""

import re

from app.core.database import SessionLocal, AuditEvent

from app.core.logging_config import logger


class AuditService:
    """Emit consistent audit log records."""

    _EMAIL_PATTERN = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
    _PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")

    @classmethod
    def _mask_text(cls, value: str) -> str:
        masked = cls._EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
        masked = cls._PHONE_PATTERN.sub("[REDACTED_PHONE]", masked)
        return masked

    @classmethod
    def _sanitize_value(cls, value):
        if isinstance(value, str):
            text = cls._mask_text(value)
            if len(text) > 500:
                return text[:500] + "..."
            return text
        if isinstance(value, dict):
            return {k: cls._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._sanitize_value(v) for v in value]
        return value

    @staticmethod
    def log(action: str, status: str, user_id: int | None = None, **details):
        sanitized_details = {
            k: AuditService._sanitize_value(v)
            for k, v in details.items()
            if v is not None and k not in {"password", "token", "authorization"}
        }
        logger.info(
            "audit action=%s status=%s user_id=%s details=%s",
            action,
            status,
            user_id,
            sanitized_details,
        )

        # Best-effort persistence for governance export queries.
        db = SessionLocal()
        try:
            db.add(
                AuditEvent(
                    action=action,
                    status=status,
                    user_id=user_id,
                    details=sanitized_details,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist audit event")
        finally:
            db.close()


audit_service = AuditService()
