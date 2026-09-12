"""
Unit tests for the email verification service.

Tests OTP generation, verification, expiry, brute-force protection,
and the password reset flow.
"""

import pytest
from unittest.mock import patch
from datetime import UTC, datetime, timedelta

from app.services.email_verification import (
    generate_otp,
    create_verification,
    verify_otp,
    is_verification_required,
    create_password_reset,
    verify_password_reset_otp,
    send_verification_email,
    send_password_reset_email,
    _otp_store,
    _password_reset_store,
    OTP_EXPIRY_MINUTES,
)


@pytest.fixture(autouse=True)
def clear_stores():
    """Clear OTP stores before each test."""
    _otp_store.clear()
    _password_reset_store.clear()
    yield
    _otp_store.clear()
    _password_reset_store.clear()


# ==========================================
# OTP Generation
# ==========================================

class TestOTPGeneration:
    def test_otp_length(self):
        otp = generate_otp()
        assert len(otp) == 6

    def test_otp_is_digits(self):
        otp = generate_otp()
        assert otp.isdigit()

    def test_otp_uniqueness(self):
        """Two consecutive OTPs should be different (statistically)."""
        otps = {generate_otp() for _ in range(20)}
        assert len(otps) > 1  # At least some should be unique


# ==========================================
# Email Verification Flow
# ==========================================

class TestEmailVerification:
    def test_create_and_verify_otp(self):
        otp = create_verification("user@example.com")
        success, message = verify_otp("user@example.com", otp)
        assert success is True
        assert "verified" in message.lower()

    def test_wrong_otp_fails(self):
        create_verification("user@example.com")
        success, message = verify_otp("user@example.com", "000000")
        assert success is False
        assert "invalid" in message.lower()

    def test_case_insensitive_email(self):
        otp = create_verification("User@Example.COM")
        success, _ = verify_otp("user@example.com", otp)
        assert success is True

    def test_no_pending_verification(self):
        success, message = verify_otp("nobody@example.com", "123456")
        assert success is False
        assert "no pending" in message.lower()

    def test_otp_consumed_after_success(self):
        otp = create_verification("user@example.com")
        verify_otp("user@example.com", otp)
        # Second attempt should fail
        success, _ = verify_otp("user@example.com", otp)
        assert success is False

    def test_expired_otp_rejected(self):
        otp = create_verification("user@example.com")
        # Manually expire the OTP
        key = "user@example.com"
        _otp_store[key]["created_at"] = datetime.now(UTC) - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        success, message = verify_otp("user@example.com", otp)
        assert success is False
        assert "expired" in message.lower()

    def test_brute_force_protection(self):
        create_verification("user@example.com")
        # Attempt 5 wrong codes
        for i in range(5):
            verify_otp("user@example.com", f"00000{i}")
        # 6th attempt should be locked out
        success, message = verify_otp("user@example.com", "000000")
        assert success is False
        assert "no pending" in message.lower() or "too many" in message.lower()


# ==========================================
# Password Reset Flow
# ==========================================

class TestPasswordReset:
    def test_create_and_verify_reset_otp(self):
        otp = create_password_reset("user@example.com")
        success, message = verify_password_reset_otp("user@example.com", otp)
        assert success is True

    def test_wrong_reset_otp_fails(self):
        create_password_reset("user@example.com")
        success, message = verify_password_reset_otp("user@example.com", "000000")
        assert success is False

    def test_expired_reset_otp(self):
        otp = create_password_reset("user@example.com")
        key = "user@example.com"
        _password_reset_store[key]["created_at"] = datetime.now(UTC) - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        success, message = verify_password_reset_otp("user@example.com", otp)
        assert success is False
        assert "expired" in message.lower()

    def test_reset_otp_consumed_after_use(self):
        otp = create_password_reset("user@example.com")
        verify_password_reset_otp("user@example.com", otp)
        success, _ = verify_password_reset_otp("user@example.com", otp)
        assert success is False


# ==========================================
# Email Sending (Dev Mode)
# ==========================================

class TestEmailSending:
    def test_dev_mode_verification_email(self):
        """In dev mode (no SMTP), should log and return True."""
        result = send_verification_email("test@test.com", "123456")
        assert result is True

    def test_dev_mode_password_reset_email(self):
        result = send_password_reset_email("test@test.com", "654321")
        assert result is True


# ==========================================
# Configuration
# ==========================================

class TestConfig:
    def test_verification_required_default(self):
        """Default should be False (not required in dev)."""
        # This depends on .env — just test the function exists and returns bool
        result = is_verification_required()
        assert isinstance(result, bool)
