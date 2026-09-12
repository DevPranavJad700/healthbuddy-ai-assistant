"""
Analytics API — Dashboard stats and monitoring endpoints.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field

from app.core.database import get_db, ClinicianReview
from app.core.security import get_current_admin_required, get_current_clinician_required
from app.core.metrics import CLINICIAN_REVIEW_EVENTS_TOTAL
from app.services.audit_service import audit_service
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class ClinicianReviewUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|reviewed|resolved)$")
    reviewer_notes: str | None = Field(default=None, max_length=2000)
    closure_reason: str | None = Field(default=None, max_length=120)


@router.get("/dashboard")
async def get_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_admin_required),
):
    """Get analytics dashboard data."""
    return analytics_service.get_dashboard_stats(db, days=days)


@router.get("/experiments")
async def get_experiment_summary(
    experiment: str = "response_style",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_admin_required),
):
    """Get A/B experiment assignment and feedback summary."""
    return analytics_service.get_experiment_summary(db, experiment=experiment)


@router.get("/clinician-reviews")
async def get_clinician_review_queue(
    status: str = "pending",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_clinician_required),
):
    """Fetch clinician review queue for operational follow-up."""
    rows = (
        db.query(ClinicianReview)
        .filter(ClinicianReview.status == status)
        .order_by(ClinicianReview.created_at.desc())
        .limit(100)
        .all()
    )
    
    now = datetime.now(UTC)
    
    def is_overdue(r) -> bool:
        if not r.sla_deadline_at or r.status != "pending":
            return False
        deadline = r.sla_deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        return deadline < now

    return {
        "status": status,
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "session_id": r.session_id,
                "status": r.status,
                "question": r.question[:300],
                "response": r.response[:300],
                "reviewer_notes": r.reviewer_notes,
                "priority": r.priority,
                "triage_level": r.triage_level,
                "sla_deadline_at": r.sla_deadline_at.isoformat() if r.sla_deadline_at else None,
                "is_sla_overdue": is_overdue(r),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "closed_at": r.closed_at.isoformat() if r.closed_at else None,
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
            for r in rows
        ],
    }


@router.patch("/clinician-reviews/{review_id}")
async def update_clinician_review(
    review_id: int,
    req: ClinicianReviewUpdateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_clinician_required),
):
    """Update clinician review status/notes (admin operation)."""
    row = db.query(ClinicianReview).filter(ClinicianReview.id == review_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    row.status = req.status
    row.reviewer_notes = req.reviewer_notes
    if req.status in {"reviewed", "resolved"}:
        row.reviewed_at = datetime.now(UTC)
    if req.status == "resolved":
        row.closed_at = datetime.now(UTC)
        row.closed_by_user_id = user.get("user_id")
        row.closure_reason = req.closure_reason
        row.closure_audit = {
            "closed_by_user_id": user.get("user_id"),
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "closure_reason": req.closure_reason,
        }

    db.commit()
    db.refresh(row)
    CLINICIAN_REVIEW_EVENTS_TOTAL.labels(event=f"admin_status_{req.status}").inc()
    audit_service.log(
        action="clinician.review.update",
        status="success",
        user_id=user.get("user_id"),
        review_id=row.id,
        new_status=row.status,
    )

    return {
        "success": True,
        "review": {
            "id": row.id,
            "status": row.status,
            "reviewer_notes": row.reviewer_notes,
            "priority": row.priority,
            "sla_deadline_at": row.sla_deadline_at.isoformat() if row.sla_deadline_at else None,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "closure_reason": row.closure_reason,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        },
    }
