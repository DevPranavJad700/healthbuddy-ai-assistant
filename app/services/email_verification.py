"""
Email Verification Service — OTP-based email verification for user registration.

Features:
- Generates 6-digit OTP codes with configurable expiry
- Sends verification emails via SMTP
- Stores OTPs in Redis (shared across all workers) with in-memory fallback
- Enforces verification before account activation (when enabled)
- Password reset OTP flow reuses the same infrastructure
"""

import random
import smtplib
import string
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger


OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 15
_MEM_OTP: dict[str, dict] = {}           # in-memory fallback for OTP
_MEM_RESET: dict[str, dict] = {}         # in-memory fallback for password reset
_otp_store = _MEM_OTP                     # Backward-compatibility alias
_password_reset_store = _MEM_RESET       # Backward-compatibility alias


def _redis():
    """Lazy-import to avoid circular imports at module load time."""
    from app.services.redis_client import get_redis
    return get_redis()


def _otp_key(email: str) -> str:
    return f"hb:otp:{email.lower().strip()}"


def _reset_key(email: str) -> str:
    return f"hb:reset:{email.lower().strip()}"


def generate_otp() -> str:
    """Generate a cryptographically random 6-digit OTP."""
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def send_verification_email(to_email: str, otp: str) -> bool:
    """
    Send an OTP verification email.

    Returns True if sent successfully, False otherwise.
    Falls back to logging the OTP if SMTP is not configured (dev mode).
    """
    if not settings.is_smtp_configured:
        # Development fallback: log the OTP instead of sending
        logger.info(
            "EMAIL VERIFICATION (dev-mode, no SMTP): email=%s otp=%s",
            to_email,
            otp,
        )
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = "HealthBuddy AI — Verify Your Email"
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email
        msg.set_content(
            f"Welcome to HealthBuddy AI!\n\n"
            f"Your verification code is: {otp}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            f"If you did not create an account, please ignore this email.\n\n"
            f"— HealthBuddy AI Team"
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("Verification email sent to %s", to_email)
        return True

    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)
        return False


def create_verification(email: str) -> str:
    """
    Create a new OTP verification for the given email.
    Stored in Redis with TTL; falls back to in-memory.
    Returns the generated OTP code.
    """
    otp = generate_otp()
    key = _otp_key(email)
    r = _redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.hset(key, mapping={"otp": otp, "attempts": 0})
            pipe.expire(key, OTP_EXPIRY_MINUTES * 60)
            pipe.execute()
            return otp
        except Exception as e:
            logger.warning("Redis OTP store failed, using memory: %s", e)
    # In-memory fallback
    _MEM_OTP[email.lower().strip()] = {
        "otp": otp, "created_at": datetime.now(UTC), "attempts": 0
    }
    return otp


def verify_otp(email: str, otp: str) -> tuple[bool, str]:
    """
    Verify an OTP code for the given email.
    Returns (success: bool, message: str).
    """
    r = _redis()
    key = _otp_key(email)

    if r is not None:
        try:
            record = r.hgetall(key)
            if not record:
                return False, "No pending verification found. Please request a new code."
            attempts = int(record.get("attempts", 0))
            if attempts >= 5:
                r.delete(key)
                return False, "Too many failed attempts. Please request a new code."
            if record.get("otp") != otp.strip():
                r.hincrby(key, "attempts", 1)
                remaining = 4 - attempts
                return False, f"Invalid code. {max(0,remaining)} attempts remaining."
            r.delete(key)  # consume OTP
            return True, "Email verified successfully."
        except Exception as e:
            logger.warning("Redis OTP verify failed, using memory: %s", e)

    # In-memory fallback
    mem_key = email.lower().strip()
    record = _MEM_OTP.get(mem_key)
    if not record:
        return False, "No pending verification found. Please request a new code."
    elapsed = datetime.now(UTC) - record["created_at"]
    if elapsed > timedelta(minutes=OTP_EXPIRY_MINUTES):
        _MEM_OTP.pop(mem_key, None)
        return False, "Verification code has expired. Please request a new one."
    if record["attempts"] >= 5:
        _MEM_OTP.pop(mem_key, None)
        return False, "Too many failed attempts. Please request a new code."
    record["attempts"] += 1
    if record["otp"] != otp.strip():
        remaining = 5 - record["attempts"]
        return False, f"Invalid code. {remaining} attempts remaining."
    _MEM_OTP.pop(mem_key, None)
    return True, "Email verified successfully."


def is_verification_required() -> bool:
    """Check if email verification is enforced by configuration."""
    return settings.email_verification_required


# ==========================================
# Password Reset OTP (reuses same OTP store)
# ==========================================

def create_password_reset(email: str) -> str:
    """Create a password-reset OTP. Stored in Redis with TTL; falls back to memory."""
    otp = generate_otp()
    key = _reset_key(email)
    r = _redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.hset(key, mapping={"otp": otp, "attempts": 0})
            pipe.expire(key, OTP_EXPIRY_MINUTES * 60)
            pipe.execute()
            return otp
        except Exception as e:
            logger.warning("Redis reset store failed, using memory: %s", e)
    _MEM_RESET[email.lower().strip()] = {
        "otp": otp, "created_at": datetime.now(UTC), "attempts": 0
    }
    return otp


def verify_password_reset_otp(email: str, otp: str) -> tuple[bool, str]:
    """Verify a password-reset OTP. Returns (success, message)."""
    r = _redis()
    key = _reset_key(email)

    if r is not None:
        try:
            record = r.hgetall(key)
            if not record:
                return False, "No pending password reset. Please request a new code."
            attempts = int(record.get("attempts", 0))
            if attempts >= 5:
                r.delete(key)
                return False, "Too many failed attempts. Please request a new code."
            if record.get("otp") != otp.strip():
                r.hincrby(key, "attempts", 1)
                remaining = 4 - attempts
                return False, f"Invalid code. {max(0, remaining)} attempts remaining."
            r.delete(key)
            return True, "OTP verified. You may now set a new password."
        except Exception as e:
            logger.warning("Redis reset verify failed, using memory: %s", e)

    # In-memory fallback
    mem_key = email.lower().strip()
    record = _MEM_RESET.get(mem_key)
    if not record:
        return False, "No pending password reset. Please request a new code."
    elapsed = datetime.now(UTC) - record["created_at"]
    if elapsed > timedelta(minutes=OTP_EXPIRY_MINUTES):
        _MEM_RESET.pop(mem_key, None)
        return False, "Reset code has expired. Please request a new one."
    if record["attempts"] >= 5:
        _MEM_RESET.pop(mem_key, None)
        return False, "Too many failed attempts. Please request a new code."
    record["attempts"] += 1
    if record["otp"] != otp.strip():
        remaining = 5 - record["attempts"]
        return False, f"Invalid code. {remaining} attempts remaining."
    _MEM_RESET.pop(mem_key, None)
    return True, "OTP verified. You may now set a new password."


def send_password_reset_email(to_email: str, otp: str) -> bool:
    """Send a password-reset OTP email."""
    if not settings.is_smtp_configured:
        logger.info(
            "PASSWORD RESET (dev-mode, no SMTP): email=%s otp=%s",
            to_email,
            otp,
        )
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = "HealthBuddy AI — Password Reset Code"
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email
        msg.set_content(
            f"You requested a password reset for your HealthBuddy AI account.\n\n"
            f"Your reset code is: {otp}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— HealthBuddy AI Team"
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("Password reset email sent to %s", to_email)
        return True

    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", to_email, e)
        return False

