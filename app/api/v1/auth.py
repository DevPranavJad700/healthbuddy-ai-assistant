"""
Authentication API — User registration, login, and profile management.
"""

from datetime import UTC, datetime
from secrets import token_urlsafe
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db, RevokedToken
from app.core.config import settings
from app.core.security import (
    get_current_user_required,
    create_access_token,
    create_refresh_token,
    get_current_admin_required,
    decode_access_token,
    security_scheme,
)
from app.core.metrics import AUTH_LOGIN_TOTAL, AUTH_TOKEN_REFRESH_TOTAL
from app.services.auth_protection import auth_protection_service
from app.services.audit_service import audit_service
from app.services.user_service import user_service
from app.services.email_verification import (
    create_verification,
    send_verification_email,
    verify_otp,
    is_verification_required,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==========================================
# Request / Response Models
# ==========================================

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str | None = None
    age: int | None = None
    gender: str | None = None
    tos_accepted: bool = False  # Must be True for registration to succeed

class LoginRequest(BaseModel):
    username: str
    password: str

class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    age: int | None = None
    gender: str | None = None
    medical_conditions: list[str] | None = None
    allergies: list[str] | None = None
    preferred_language: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class DeleteMyDataRequest(BaseModel):
    confirm: str


def _token_payload(user_id: int, username: str) -> dict:
    return {"sub": username, "user_id": user_id}


def _is_token_revoked(db: Session, jti: str | None) -> bool:
    if not jti:
        return True
    return (
        db.query(RevokedToken.id)
        .filter(RevokedToken.jti == jti)
        .first()
        is not None
    )


def _revoke_token(db: Session, payload: dict):
    jti = str(payload.get("jti", "")).strip()
    if not jti:
        return
    if _is_token_revoked(db, jti):
        return

    exp = payload.get("exp")
    expires_at = None
    if isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(exp, tz=UTC)

    row = RevokedToken(
        jti=jti,
        token_type=str(payload.get("typ", "unknown")),
        user_id=payload.get("user_id"),
        expires_at=expires_at,
    )
    db.add(row)


# ==========================================
# Endpoints
# ==========================================

@router.post("/register")
async def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user account."""
    # --- Age gate ---
    if req.age is not None and req.age < settings.min_user_age:
        raise HTTPException(
            status_code=400,
            detail=f"You must be at least {settings.min_user_age} years old to use HealthBuddy AI.",
        )

    # --- Terms of Service ---
    if settings.require_tos_acceptance and not req.tos_accepted:
        raise HTTPException(
            status_code=400,
            detail="You must accept the Terms of Service to register.",
        )

    try:
        result = user_service.register(
            db, req.username, req.email, req.password,
            req.full_name, req.age, req.gender,
        )
        audit_service.log(
            action="auth.register",
            status="success",
            user_id=result.get("user_id"),
            username=req.username,
            ip=request.client.host if request.client else "unknown",
        )
        payload = _token_payload(result["user_id"], result["username"])

        # If email verification is required, send OTP instead of tokens
        if is_verification_required():
            otp = create_verification(req.email)
            send_verification_email(req.email, otp)
            return {
                "success": True,
                "requires_verification": True,
                "message": "Account created. Please check your email for a verification code.",
                "user_id": result["user_id"],
                "username": result["username"],
            }

        return {
            "success": True,
            **result,
            "refresh_token": create_refresh_token(payload),
        }
    except ValueError as e:
        audit_service.log(
            action="auth.register",
            status="failure",
            username=req.username,
            ip=request.client.host if request.client else "unknown",
            reason=str(e),
        )
        AUTH_LOGIN_TOTAL.labels(outcome="register_failure").inc()
        raise HTTPException(status_code=400, detail=str(e))


class VerifyEmailRequest(BaseModel):
    email: str
    otp: str


class ResendOTPRequest(BaseModel):
    email: str


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verify a user's email address with an OTP code."""
    success, message = verify_otp(req.email, req.otp)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    audit_service.log(
        action="auth.verify_email",
        status="success",
        email=req.email,
    )
    return {"success": True, "message": message}


@router.post("/resend-otp")
async def resend_otp(req: ResendOTPRequest):
    """Resend a verification OTP to the user's email."""
    otp = create_verification(req.email)
    sent = send_verification_email(req.email, otp)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email.")
    return {"success": True, "message": "Verification code sent."}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send a password-reset OTP to the user's registered email.

    Always returns success to avoid leaking whether the email exists.
    """
    from app.services.email_verification import (
        create_password_reset,
        send_password_reset_email,
    )
    from app.core.database import User

    user = db.query(User).filter(User.email == req.email).first()
    if user:
        otp = create_password_reset(req.email)
        send_password_reset_email(req.email, otp)
        audit_service.log(
            action="auth.forgot_password",
            status="success",
            email=req.email,
        )
    else:
        # Don't reveal whether the email exists
        audit_service.log(
            action="auth.forgot_password",
            status="no_user",
            email=req.email,
        )

    return {
        "success": True,
        "message": "If an account with that email exists, a reset code has been sent.",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset a user's password using an OTP code."""
    from app.services.email_verification import verify_password_reset_otp
    from app.core.database import User
    from app.core.security import hash_password

    # Verify OTP first
    success, message = verify_password_reset_otp(req.email, req.otp)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Validate new password policy
    try:
        user_service._validate_password_policy(req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Update password
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = hash_password(req.new_password)
    db.commit()

    audit_service.log(
        action="auth.reset_password",
        status="success",
        user_id=user.id,
        email=req.email,
    )
    return {"success": True, "message": "Password has been reset successfully. Please log in."}


@router.get("/google/start")
async def google_oauth_start(request: Request):
    """Redirect browser to Google OAuth account chooser screen."""
    client_id = settings.google_oauth_client_id
    redirect_uri = settings.google_oauth_redirect_uri
    
    is_dummy = "dummy" in client_id.lower() or not client_id or not redirect_uri
    
    if is_dummy:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured with real API keys. Set a valid GOOGLE_OAUTH_CLIENT_ID in .env.",
        )

    state = token_urlsafe(24)
    nonce = token_urlsafe(24)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": settings.google_oauth_scope,
        "prompt": "select_account",
        "include_granted_scopes": "true",
        "state": state,
        "nonce": nonce,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/google/status")
async def google_oauth_status():
    """Return whether Google OAuth is configured on the server."""
    client_id = settings.google_oauth_client_id
    redirect_uri = settings.google_oauth_redirect_uri
    
    configured = bool(client_id and redirect_uri and "dummy" not in client_id.lower())
    
    return {
        "success": True,
        "configured": configured,
        "message": (
            "Google OAuth is configured"
            if configured
            else "Google OAuth requires a real Client ID in .env (current is dummy or missing)."
        ),
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Login and get JWT token."""
    ip = request.client.host if request.client else "unknown"
    allowed, reason = auth_protection_service.check_allowed(req.username, ip)
    if not allowed:
        audit_service.log(
            action="auth.login",
            status="blocked",
            username=req.username,
            ip=ip,
            reason=reason,
        )
        AUTH_LOGIN_TOTAL.labels(outcome="blocked").inc()
        raise HTTPException(status_code=429, detail=reason)

    try:
        result = user_service.login(db, req.username, req.password)
        auth_protection_service.record_success(req.username, ip)
        AUTH_LOGIN_TOTAL.labels(outcome="success").inc()
        audit_service.log(
            action="auth.login",
            status="success",
            user_id=result.get("user_id"),
            username=req.username,
            ip=ip,
        )
        payload = _token_payload(result["user_id"], result["username"])
        return {
            "success": True,
            **result,
            "refresh_token": create_refresh_token(payload),
        }
    except ValueError as e:
        auth_protection_service.record_failure(req.username, ip)
        AUTH_LOGIN_TOTAL.labels(outcome="failure").inc()
        audit_service.log(
            action="auth.login",
            status="failure",
            username=req.username,
            ip=ip,
            reason=str(e),
        )
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh")
async def refresh_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
):
    """Issue a new access token from a valid refresh token and rotate refresh token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Refresh token required")

    refresh_user = decode_access_token(credentials.credentials)
    if refresh_user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if str(refresh_user.get("typ", "")).lower() != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")
    if _is_token_revoked(db, str(refresh_user.get("jti", ""))):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    try:
        user_id = int(refresh_user.get("user_id"))
        username = str(refresh_user.get("sub"))
        payload = _token_payload(user_id, username)
        token = create_access_token(payload)
        rotated_refresh = create_refresh_token(payload)
        _revoke_token(db, refresh_user)
        db.commit()
        AUTH_TOKEN_REFRESH_TOTAL.labels(outcome="success").inc()
        audit_service.log(
            action="auth.refresh",
            status="success",
            user_id=user_id,
        )
        return {"success": True, "token": token, "refresh_token": rotated_refresh}
    except Exception as e:
        AUTH_TOKEN_REFRESH_TOTAL.labels(outcome="failure").inc()
        audit_service.log(
            action="auth.refresh",
            status="failure",
            user_id=refresh_user.get("user_id"),
            reason=str(e),
        )
        raise HTTPException(status_code=400, detail="Could not refresh token")


@router.post("/logout")
async def logout(
    req: LogoutRequest | None = None,
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Logout endpoint that revokes provided refresh token and records audit trail."""
    if req and req.refresh_token:
        payload = decode_access_token(req.refresh_token)
        if payload and str(payload.get("typ", "")).lower() == "refresh":
            # Revoke only caller-owned refresh tokens.
            if int(payload.get("user_id", -1)) == int(user.get("user_id", -2)):
                _revoke_token(db, payload)
                db.commit()

    audit_service.log(
        action="auth.logout",
        status="success",
        user_id=user.get("user_id"),
    )
    return {"success": True, "message": "Logged out"}


@router.get("/session")
async def session_state(user: dict = Depends(get_current_user_required)):
    """Return token/session identity for frontend sign-in indicators."""
    username = str(user.get("sub", ""))
    is_admin = (
        bool(user.get("is_admin", False))
        or str(user.get("role", "")).lower() == "admin"
        or username.lower() in settings.admin_usernames_list
    )
    return {
        "authenticated": True,
        "user_id": user.get("user_id"),
        "username": username,
        "is_admin": is_admin,
        "token_expires_at": user.get("exp"),
    }


@router.get("/protection-status")
async def auth_protection_status(user: dict = Depends(get_current_admin_required)):
    """Admin-only auth abuse monitoring snapshot."""
    return {"success": True, "protection": auth_protection_service.snapshot()}


@router.get("/profile")
async def get_profile(
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Get current user's profile."""
    profile = user_service.get_profile(db, user["user_id"])
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    audit_service.log(action="auth.profile.read", status="success", user_id=user.get("user_id"))
    return profile


@router.put("/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Update current user's profile."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        profile = user_service.update_profile(db, user["user_id"], **updates)
        audit_service.log(
            action="auth.profile.update",
            status="success",
            user_id=user.get("user_id"),
            fields=list(updates.keys()),
        )
        return {"success": True, "profile": profile}
    except ValueError as e:
        audit_service.log(
            action="auth.profile.update",
            status="failure",
            user_id=user.get("user_id"),
            reason=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/delete-my-data")
async def delete_my_data(
    req: DeleteMyDataRequest,
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Allow authenticated users to permanently delete their account and associated records."""
    if req.confirm.strip().upper() != "DELETE_MY_DATA":
        raise HTTPException(status_code=400, detail="Confirmation text must be DELETE_MY_DATA")

    user_id = int(user["user_id"])
    try:
        deleted = user_service.delete_user_data(db, user_id=user_id)
        audit_service.log(
            action="auth.delete_my_data",
            status="success",
            user_id=user_id,
            deleted=deleted,
        )
        return {"success": True, "deleted": deleted}
    except ValueError as e:
        audit_service.log(
            action="auth.delete_my_data",
            status="failure",
            user_id=user_id,
            reason=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/export-my-data")
async def export_my_data(
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Export authenticated user's account data for portability before deletion."""
    user_id = int(user["user_id"])
    try:
        payload = user_service.export_user_data(db, user_id=user_id)
        audit_service.log(
            action="auth.export_my_data",
            status="success",
            user_id=user_id,
            records={
                "goals": len(payload.get("goals", [])),
                "chat_logs": len(payload.get("chat_logs", [])),
                "symptom_checks": len(payload.get("symptom_checks", [])),
            },
        )
        return {"success": True, "export": payload}
    except ValueError as e:
        audit_service.log(
            action="auth.export_my_data",
            status="failure",
            user_id=user_id,
            reason=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/admin/users/{user_id}/data")
async def admin_delete_user_data(
    user_id: int,
    admin_user: dict = Depends(get_current_admin_required),
    db: Session = Depends(get_db),
):
    """Admin endpoint to delete a user's account + associated records."""
    try:
        deleted = user_service.delete_user_data(db, user_id=user_id)
        audit_service.log(
            action="auth.admin_delete_user_data",
            status="success",
            user_id=admin_user.get("user_id"),
            target_user_id=user_id,
            deleted=deleted,
        )
        return {"success": True, "deleted": deleted}
    except ValueError as e:
        audit_service.log(
            action="auth.admin_delete_user_data",
            status="failure",
            user_id=admin_user.get("user_id"),
            target_user_id=user_id,
            reason=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))
