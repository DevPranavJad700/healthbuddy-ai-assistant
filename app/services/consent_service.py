"""Consent policy enforcement utilities."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import ConsentRecord


SENSITIVE_SCOPE_CHAT = "chat"
SENSITIVE_SCOPE_PERSONALIZATION = "personalization"
CONSENT_TERMS_OF_USE = "terms_of_use"


def has_latest_granted_consent(
    db: Session,
    user_id: int,
    consent_type: str,
    scope: str | None = None,
) -> bool:
    q = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == user_id)
        .filter(ConsentRecord.consent_type == consent_type.strip().lower())
        .filter(ConsentRecord.policy_version == settings.consent_policy_version)
        .order_by(ConsentRecord.created_at.desc())
    )

    if scope:
        q = q.filter((ConsentRecord.scope == scope) | (ConsentRecord.scope.is_(None)))

    row = q.first()
    return bool(row and row.granted)


def enforce_latest_consent_or_403(
    db: Session,
    user: dict | None,
    consent_type: str,
    scope: str | None = None,
):
    if not settings.require_stored_consent_for_sensitive:
        return
    if not user:
        return

    raw_user_id = user.get("user_id")
    if raw_user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is required")
    user_id = int(raw_user_id)
    if has_latest_granted_consent(db, user_id=user_id, consent_type=consent_type, scope=scope):
        return

    raise HTTPException(
        status_code=403,
        detail=(
            f"Latest consent required for '{consent_type}' with policy version "
            f"{settings.consent_policy_version}. Record consent via /api/v1/compliance/consent."
        ),
    )


def enforce_terms_acceptance_or_403(db: Session, user: dict | None):
    """Ensure authenticated users accepted the latest Terms policy before chat guidance."""
    if not settings.require_terms_acceptance_for_chat:
        return
    if not user:
        return

    raw_user_id = user.get("user_id")
    if raw_user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is required")
    user_id = int(raw_user_id)
    q = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == user_id)
        .filter(ConsentRecord.consent_type == CONSENT_TERMS_OF_USE)
        .filter(ConsentRecord.policy_version == settings.terms_policy_version)
        .order_by(ConsentRecord.created_at.desc())
    )
    row = q.first()
    if row is not None and bool(row.granted):
        return

    raise HTTPException(
        status_code=403,
        detail=(
            f"Latest terms acceptance required (policy_version={settings.terms_policy_version}). "
            "Record consent type 'terms_of_use' via /api/v1/compliance/consent."
        ),
    )


def build_signed_snapshot(payload: dict) -> dict:
    """Attach deterministic signature metadata to export payload."""
    import hashlib
    import hmac
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    key = (settings.audit_snapshot_signing_key or settings.secret_key).encode("utf-8")
    digest = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        "snapshot_created_at": datetime.now(UTC).isoformat(),
        "signature_alg": "HMAC-SHA256",
        "signature": digest,
    }
