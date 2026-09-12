"""
Security module — JWT authentication, password hashing, and authorization.
"""

from datetime import UTC, datetime, timedelta
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings


# ==========================================
# Configuration
# ==========================================

SECRET_KEY = settings.secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_MINUTES = settings.refresh_token_expire_minutes

security_scheme = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ==========================================
# Password Hashing (using hashlib — no extra deps)
# ==========================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, hashed)


# ==========================================
# JWT Token
# ==========================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "typ": "access", "jti": uuid.uuid4().hex})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a long-lived refresh token.

    We keep refresh tokens stateless in this project and rotate access tokens on demand.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "typ": "refresh", "jti": uuid.uuid4().hex})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[dict]:
    """Get user from JWT token if provided (optional auth)."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    return payload


def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """Require valid JWT token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    token_type = str(payload.get("typ", "access")).lower()
    if token_type != "access":
        raise HTTPException(status_code=401, detail="Access token required")
    return payload


def get_refresh_token_required(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """Require a valid refresh token in Authorization Bearer header."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Refresh token required")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    token_type = str(payload.get("typ", "")).lower()
    if token_type != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")
    return payload


def get_current_admin_required(
    user: dict = Depends(get_current_user_required),
) -> dict:
    """Require authenticated admin access.

    Admin is recognized if any of the following are present:
    - JWT claim `is_admin: true`
    - JWT claim `role: "admin"`
    - JWT subject username in configured `admin_usernames` allowlist
    """
    username = str(user.get("sub", "")).strip().lower()
    role = str(user.get("role", "")).strip().lower()
    is_admin_claim = bool(user.get("is_admin", False)) or role == "admin"
    is_admin_username = username in settings.admin_usernames_list

    if not (is_admin_claim or is_admin_username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def get_current_clinician_required(
    user: dict = Depends(get_current_user_required),
) -> dict:
    """Require clinician or admin role for medical review operations."""
    username = str(user.get("sub", "")).strip().lower()
    role = str(user.get("role", "")).strip().lower()
    is_admin = bool(user.get("is_admin", False)) or role == "admin" or username in settings.admin_usernames_list
    is_clinician = role in {"clinician", "medical_reviewer", "reviewer"}

    if not (is_admin or is_clinician):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinician privileges required",
        )
    return user
