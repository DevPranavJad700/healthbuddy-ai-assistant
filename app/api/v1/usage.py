"""
Usage API — Daily quota status endpoint.

Allows the frontend to show users their current usage and when it resets.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_required
from app.services.usage_service import get_quota_status

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/quota", summary="Get daily query quota status")
async def get_quota(user: dict = Depends(get_current_user_required)):
    """
    Returns the current user's daily query quota.

    Response:
    - `used`: queries made today
    - `limit`: daily limit (-1 = unlimited for admins)
    - `unlimited`: True for admin users
    - `resets_at`: ISO-8601 timestamp of next quota reset (midnight UTC)
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    is_admin = user.get("role") == "admin"
    return get_quota_status(user_id=user_id, is_admin=is_admin)
