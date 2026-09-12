"""
Personalization API — user goals and profile context endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_required
from app.models.schemas import AddUserGoalRequest
from app.services.user_service import user_service
from app.services.audit_service import audit_service
from app.services.consent_service import (
    enforce_latest_consent_or_403,
    SENSITIVE_SCOPE_PERSONALIZATION,
)

router = APIRouter(prefix="/personalization", tags=["Personalization"])


@router.get("/goals")
async def list_goals(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    enforce_latest_consent_or_403(
        db=db,
        user=user,
        consent_type="personalization",
        scope=SENSITIVE_SCOPE_PERSONALIZATION,
    )
    goals = user_service.list_goals(db, user["user_id"])
    return {"goals": goals}


@router.post("/goals")
async def add_goal(
    req: AddUserGoalRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    enforce_latest_consent_or_403(
        db=db,
        user=user,
        consent_type="personalization",
        scope=SENSITIVE_SCOPE_PERSONALIZATION,
    )
    created = user_service.add_goal(db, user["user_id"], req.goal, req.priority)
    audit_service.log(
        action="personalization.goal.add",
        status="success",
        user_id=user.get("user_id"),
        goal_id=created["id"],
    )
    return {"success": True, "goal": created}


@router.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    enforce_latest_consent_or_403(
        db=db,
        user=user,
        consent_type="personalization",
        scope=SENSITIVE_SCOPE_PERSONALIZATION,
    )
    deleted = user_service.remove_goal(db, user["user_id"], goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")

    audit_service.log(
        action="personalization.goal.delete",
        status="success",
        user_id=user.get("user_id"),
        goal_id=goal_id,
    )
    return {"success": True, "deleted": goal_id}


@router.get("/context")
async def get_profile_context(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_required),
):
    enforce_latest_consent_or_403(
        db=db,
        user=user,
        consent_type="personalization",
        scope=SENSITIVE_SCOPE_PERSONALIZATION,
    )
    context = user_service.get_personalization_context(db, user["user_id"])
    return {"context": context}
