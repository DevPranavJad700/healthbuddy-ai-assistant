"""
Admin API — Platform management endpoints.

All endpoints require role=admin JWT claim.
Provides: user management, platform stats, clinician review queue.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.security import get_current_admin_required
from app.core.database import get_db, User, ChatLog
from app.core.logging_config import logger
from app.services.usage_service import reset_quota, get_quota_status

router = APIRouter(prefix="/admin", tags=["Admin"])


# ==========================================
# Users
# ==========================================

@router.get("/users", summary="List all users (paginated)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_required),
):
    """Return paginated list of all registered users."""
    offset = (page - 1) * page_size
    total = db.query(func.count(User.id)).scalar() or 0
    users = (
        db.query(User)
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "is_verified": getattr(u, "is_verified", True),
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.post("/users/{user_id}/suspend", summary="Suspend a user account")
async def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin_required),
):
    """Disable a user account. The user cannot log in until reinstated."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.username in ("admin",):
        raise HTTPException(status_code=400, detail="Cannot suspend the primary admin.")
    user.is_active = False
    db.commit()
    logger.info("Admin %s suspended user %s", admin.get("username"), user.username)
    return {"message": f"User {user.username} suspended."}


@router.post("/users/{user_id}/reinstate", summary="Reinstate a suspended user")
async def reinstate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin_required),
):
    """Re-enable a suspended user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    db.commit()
    logger.info("Admin %s reinstated user %s", admin.get("username"), user.username)
    return {"message": f"User {user.username} reinstated."}


@router.post("/users/{user_id}/reset-quota", summary="Reset a user's daily query quota")
async def reset_user_quota(
    user_id: int,
    admin: dict = Depends(get_current_admin_required),
):
    """Manually reset a specific user's daily query count to 0."""
    reset_quota(user_id)
    logger.info("Admin %s reset quota for user_id=%s", admin.get("username"), user_id)
    return {"message": f"Quota reset for user_id={user_id}."}


@router.get("/users/{user_id}/quota", summary="Check a user's current quota")
async def get_user_quota(
    user_id: int,
    _admin: dict = Depends(get_current_admin_required),
):
    return get_quota_status(user_id=user_id, is_admin=False)


# ==========================================
# Platform Stats
# ==========================================

@router.get("/stats", summary="Platform-wide statistics")
async def platform_stats(
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_required),
):
    """Return high-level platform statistics."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_chats = db.query(func.count(ChatLog.id)).scalar() or 0

    # Chats in last 24h
    from datetime import UTC, datetime, timedelta
    since = datetime.now(UTC) - timedelta(hours=24)
    chats_24h = (
        db.query(func.count(ChatLog.id))
        .filter(ChatLog.created_at >= since)
        .scalar() or 0
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": total_users - active_users,
        "total_chats": total_chats,
        "chats_last_24h": chats_24h,
    }


# ==========================================
# Clinician Review Queue
# ==========================================

@router.get("/clinician-queue", summary="Get pending clinician review items")
async def clinician_review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_required),
):
    """Return chat logs that were flagged for clinician review."""
    offset = (page - 1) * page_size
    flagged = (
        db.query(ChatLog)
        .filter(ChatLog.needs_clinician_review == True)
        .order_by(desc(ChatLog.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    total = (
        db.query(func.count(ChatLog.id))
        .filter(ChatLog.needs_clinician_review == True)
        .scalar() or 0
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "session_id": log.session_id,
                "message": log.message[:200] if log.message else "",
                "response": log.response[:300] if log.response else "",
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in flagged
        ],
    }
