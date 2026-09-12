"""Compliance API — consent recording and governance audit export."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db, ConsentRecord, AuditEvent
from app.core.config import settings
from app.core.security import get_current_user_required, get_current_admin_required
from app.services.audit_service import audit_service
from app.services.consent_service import build_signed_snapshot

router = APIRouter(prefix="/compliance", tags=["Compliance"])

EMERGENCY_CONTACTS = {
    "us": {"label": "US/Canada", "emergency_number": "911", "poison_control": "1-800-222-1222"},
    "eu": {"label": "EU", "emergency_number": "112", "poison_control": "Local country service"},
    "uk": {"label": "United Kingdom", "emergency_number": "999", "poison_control": "NHS 111"},
    "au": {"label": "Australia", "emergency_number": "000", "poison_control": "13 11 26"},
    "in": {"label": "India", "emergency_number": "112", "poison_control": "National helpline (state-specific)"},
}


class ConsentUpsertRequest(BaseModel):
    consent_type: str = Field(..., min_length=2, max_length=80)
    policy_version: str = Field(..., min_length=1, max_length=40)
    granted: bool
    scope: Optional[str] = Field(default="chat", max_length=120)
    session_id: Optional[str] = Field(default=None, max_length=64)
    metadata_json: Optional[dict] = None


class ConsentRevokeRequest(BaseModel):
    consent_type: str = Field(..., min_length=2, max_length=80)
    scope: Optional[str] = Field(default=None, max_length=120)
    reason: Optional[str] = Field(default=None, max_length=240)


@router.get("/consents/types", summary="List all recognized consent types")
async def list_consent_types():
    """Return the catalogue of consent types the system recognises, with
    their current policy versions and human-readable descriptions."""
    return {
        "consent_policy_version": settings.consent_policy_version,
        "terms_policy_version": settings.terms_policy_version,
        "types": [
            {
                "consent_type": "ai_guidance",
                "description": "Consent to receive AI-generated health guidance and information.",
                "scope": "chat",
                "required_for": ["chat", "symptom_checker"],
            },
            {
                "consent_type": "data_processing",
                "description": "Consent for processing and storing your health-related queries.",
                "scope": "data",
                "required_for": ["chat_history", "analytics"],
            },
            {
                "consent_type": "terms_of_use",
                "description": "Acceptance of HealthBuddy AI Terms of Service.",
                "scope": "platform",
                "required_for": ["registration"],
            },
            {
                "consent_type": "analytics",
                "description": "Consent for anonymous usage analytics to improve the service.",
                "scope": "analytics",
                "required_for": [],
            },
            {
                "consent_type": "personalization",
                "description": "Consent to use your health profile for personalised responses.",
                "scope": "personalization",
                "required_for": ["personalized_chat"],
            },
        ],
    }


@router.post("/consent", summary="Record explicit consent decision")
async def record_consent(
    req: ConsentUpsertRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    user_id = int(user["user_id"])

    if req.policy_version.strip() != settings.consent_policy_version:
        raise HTTPException(
            status_code=400,
            detail=(
                f"policy_version mismatch. Expected {settings.consent_policy_version}. "
                "Use latest policy version when recording consent."
            ),
        )

    row = ConsentRecord(
        user_id=user_id,
        session_id=req.session_id,
        consent_type=req.consent_type.strip().lower(),
        policy_version=req.policy_version.strip(),
        granted=req.granted,
        scope=req.scope,
        source="api",
        metadata_json=req.metadata_json or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    audit_service.log(
        action="compliance.consent.record",
        status="success",
        user_id=user_id,
        consent_type=row.consent_type,
        policy_version=row.policy_version,
        granted=row.granted,
        scope=row.scope,
        session_id=row.session_id,
    )

    return {
        "success": True,
        "active_consent_policy_version": settings.consent_policy_version,
        "active_terms_policy_version": settings.terms_policy_version,
        "consent": {
            "id": row.id,
            "consent_type": row.consent_type,
            "policy_version": row.policy_version,
            "granted": row.granted,
            "scope": row.scope,
            "session_id": row.session_id,
            "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        },
    }


@router.get("/consent/me", summary="List my consent history")
async def my_consent_history(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    user_id = int(user["user_id"])
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == user_id)
        .order_by(ConsentRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "consents": [
            {
                "id": r.id,
                "consent_type": r.consent_type,
                "policy_version": r.policy_version,
                "granted": r.granted,
                "scope": r.scope,
                "session_id": r.session_id,
                "created_at": r.created_at.isoformat() if r.created_at is not None else None,
            }
            for r in rows
        ]
    }


@router.post("/consent/revoke", summary="Revoke an existing consent by recording a deny decision")
async def revoke_consent(
    req: ConsentRevokeRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    user_id = int(user["user_id"])
    row = ConsentRecord(
        user_id=user_id,
        session_id=None,
        consent_type=req.consent_type.strip().lower(),
        policy_version=settings.consent_policy_version,
        granted=False,
        scope=req.scope,
        source="api",
        metadata_json={"reason": req.reason} if req.reason else {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    audit_service.log(
        action="compliance.consent.revoke",
        status="success",
        user_id=user_id,
        consent_type=row.consent_type,
        scope=row.scope,
        policy_version=row.policy_version,
    )

    return {
        "success": True,
        "revoked": {
            "id": row.id,
            "consent_type": row.consent_type,
            "scope": row.scope,
            "policy_version": row.policy_version,
            "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        },
    }


@router.get("/audit-export", summary="Export governance audit data (admin)")
async def governance_audit_export(
    start: Optional[str] = Query(default=None, description="ISO datetime inclusive"),
    end: Optional[str] = Query(default=None, description="ISO datetime inclusive"),
    limit: int = Query(default=1000, ge=1, le=10000),
    consent_type: Optional[str] = Query(default=None),
    action_prefix: Optional[str] = Query(default=None),
    signed: bool = Query(default=False, description="Attach HMAC signature metadata to export payload"),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin_required),
):
    try:
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ISO datetime filter: {exc}")

    consent_q = db.query(ConsentRecord)
    audit_q = db.query(AuditEvent)

    if start_dt:
        consent_q = consent_q.filter(ConsentRecord.created_at >= start_dt)
        audit_q = audit_q.filter(AuditEvent.created_at >= start_dt)
    if end_dt:
        consent_q = consent_q.filter(ConsentRecord.created_at <= end_dt)
        audit_q = audit_q.filter(AuditEvent.created_at <= end_dt)
    if consent_type:
        consent_q = consent_q.filter(ConsentRecord.consent_type == consent_type.strip().lower())
    if action_prefix:
        audit_q = audit_q.filter(AuditEvent.action.like(f"{action_prefix.strip()}%"))

    consent_rows = consent_q.order_by(ConsentRecord.created_at.desc()).limit(limit).all()
    audit_rows = audit_q.order_by(AuditEvent.created_at.desc()).limit(limit).all()

    audit_service.log(
        action="compliance.audit_export",
        status="success",
        user_id=admin.get("user_id"),
        start=start,
        end=end,
        action_prefix=action_prefix,
        consent_type=consent_type,
        result_counts={"consents": len(consent_rows), "audit_events": len(audit_rows)},
    )

    payload = {
        "filters": {
            "start": start,
            "end": end,
            "limit": limit,
            "consent_type": consent_type,
            "action_prefix": action_prefix,
            "signed": signed,
        },
        "consents": [
            {
                "id": c.id,
                "user_id": c.user_id,
                "session_id": c.session_id,
                "consent_type": c.consent_type,
                "policy_version": c.policy_version,
                "granted": c.granted,
                "scope": c.scope,
                "source": c.source,
                "metadata_json": c.metadata_json,
                "created_at": c.created_at.isoformat() if c.created_at is not None else None,
            }
            for c in consent_rows
        ],
        "audit_events": [
            {
                "id": a.id,
                "action": a.action,
                "status": a.status,
                "user_id": a.user_id,
                "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at is not None else None,
            }
            for a in audit_rows
        ],
    }

    if signed:
        payload["snapshot_signature"] = build_signed_snapshot(payload)

    return payload


@router.get("/emergency-contacts", summary="Get locale-specific emergency contacts")
async def emergency_contacts(country: str = Query(default="us", description="Country code: us, eu, uk, au, in")):
    key = country.strip().lower()
    data = EMERGENCY_CONTACTS.get(key, EMERGENCY_CONTACTS["us"])
    return {
        "country": key,
        "contacts": data,
        "all_supported": sorted(EMERGENCY_CONTACTS.keys()),
    }
