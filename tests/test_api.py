"""
Unit tests for HealthBuddy-AI API endpoints.
"""

import random
from typing import Any, TypeVar, cast

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.core.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware
from app.main import _validate_production_security, app


T = TypeVar("T")


def _get_middleware_instance(cls: type[T]) -> T | None:
    node: Any = app.middleware_stack
    while node is not None:
        if isinstance(node, cls):
            return cast(T, node)
        node = getattr(node, "app", None)
    return None


class TestHealthCheck:
    """Health check endpoint tests."""

    def test_health_check_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_check_fields(self, client):
        r = client.get("/api/health")
        data = r.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "llm_provider" in data
        assert "llm_model" in data
        assert "documents_loaded" in data
        assert "vector_store_ready" in data

    def test_health_has_request_id_header(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert "X-Request-ID" in r.headers

    def test_readiness_check(self, client):
        r = client.get("/api/ready")
        assert r.status_code in (200, 503)

    def test_terms_route_available(self, client):
        r = client.get("/terms")
        assert r.status_code == 200


class TestChatAPI:
    """Chat endpoint tests."""

    def test_chat_returns_200(self, client):
        r = client.post("/api/v1/chat", json={"message": "What is a balanced diet?"})
        assert r.status_code == 200

    def test_chat_response_has_required_fields(self, client):
        r = client.post("/api/v1/chat", json={"message": "Hello"})
        data = r.json()
        assert "response" in data
        assert "sources" in data
        assert "model_used" in data
        assert "provider" in data
        assert "safety_disclaimer" in data

    def test_chat_empty_message_rejected(self, client):
        r = client.post("/api/v1/chat", json={"message": ""})
        assert r.status_code == 422

    def test_chat_history(self, client):
        r = client.get("/api/v1/chat/sessions")
        assert r.status_code == 401

    def test_chat_clear_history(self, client):
        r = client.delete("/api/v1/chat/sessions/test_session_123")
        assert r.status_code == 401

    def test_chat_followup_more_does_not_force_fallback(self, client):
        session_id = "followup_test_session"

        first = client.post(
            "/api/v1/chat",
            json={"message": "How do I manage stress effectively?", "session_id": session_id},
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/chat",
            json={"message": "more", "session_id": session_id},
        )
        assert second.status_code == 200
        text = second.json().get("response", "")
        assert "I couldn't generate a reliable answer from the model right now" not in text


class TestDocumentsAPI:
    """Document management endpoint tests."""

    def test_list_documents(self, client):
        r = client.get("/api/v1/documents")
        assert r.status_code == 200
        data = r.json()
        assert "documents" in data
        assert "total_chunks" in data


class TestSymptomsAPI:
    """Symptom checker endpoint tests."""

    def test_check_symptoms_returns_predictions(self, client):
        r = client.post("/api/v1/symptoms/check", json={"symptoms": ["headache", "fever", "cough"]})
        assert r.status_code == 200
        data = r.json()
        assert "predictions" in data
        assert "severity" in data
        assert "disclaimer" in data
        assert len(data["predictions"]) > 0

    def test_check_symptoms_emergency_detection(self, client):
        r = client.post("/api/v1/symptoms/check", json={"symptoms": ["chest pain", "shortness of breath"]})
        data = r.json()
        assert data["emergency"] is True
        assert data["emergency_message"] is not None
        assert data["severity"] == "emergency"

    def test_check_empty_symptoms(self, client):
        r = client.post("/api/v1/symptoms/check", json={"symptoms": []})
        assert r.status_code == 200
        data = r.json()
        assert len(data["predictions"]) == 0

    def test_list_symptoms(self, client):
        r = client.get("/api/v1/symptoms/list")
        assert r.status_code == 200
        data = r.json()
        assert "symptoms" in data
        assert len(data["symptoms"]) > 0


class TestAuthAPI:
    """Authentication endpoint tests."""

    def test_register_user(self, client):
        r = client.post("/api/v1/auth/register", json={
            "username": "testuser", "email": "test@example.com", "password": "StrongPass123"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "token" in data

    def test_register_duplicate_username(self, client):
        # Register first
        client.post("/api/v1/auth/register", json={
            "username": "duplicate", "email": "dup@example.com", "password": "StrongPass123"
        })
        # Try again
        r = client.post("/api/v1/auth/register", json={
            "username": "duplicate", "email": "dup2@example.com", "password": "StrongPass123"
        })
        assert r.status_code == 400

    def test_register_weak_password_rejected(self, client):
        r = client.post("/api/v1/auth/register", json={
            "username": "weakpass", "email": "weak@example.com", "password": "weak"
        })
        assert r.status_code == 400

    def test_login_success(self, client):
        # Register then login
        client.post("/api/v1/auth/register", json={
            "username": "logintest", "email": "login@example.com", "password": "StrongPass123"
        })
        r = client.post("/api/v1/auth/login", json={
            "username": "logintest", "password": "StrongPass123"
        })
        assert r.status_code == 200
        assert "token" in r.json()
        assert "refresh_token" in r.json()

    def test_refresh_works_with_refresh_token(self, client):
        reg = client.post("/api/v1/auth/register", json={
            "username": "refresh_user", "email": "refresh@example.com", "password": "StrongPass123"
        })
        assert reg.status_code == 200
        refresh = reg.json().get("refresh_token")
        assert refresh

        r = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "token" in data
        assert "refresh_token" in data

    def test_refresh_revokes_previous_refresh_token(self, client):
        reg = client.post("/api/v1/auth/register", json={
            "username": "refresh_rotate", "email": "refresh_rotate@example.com", "password": "StrongPass123"
        })
        assert reg.status_code == 200
        refresh = reg.json().get("refresh_token")
        assert refresh

        r1 = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r1.status_code == 200
        rotated = r1.json().get("refresh_token")
        assert rotated

        r2 = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r2.status_code == 401

    def test_logout_revokes_refresh_token(self, client):
        reg = client.post("/api/v1/auth/register", json={
            "username": "logout_revoke", "email": "logout_revoke@example.com", "password": "StrongPass123"
        })
        assert reg.status_code == 200
        token = reg.json().get("token")
        refresh = reg.json().get("refresh_token")
        assert token and refresh

        out = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": refresh},
        )
        assert out.status_code == 200

        r = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r.status_code == 401

    def test_refresh_rejects_access_token(self, client):
        reg = client.post("/api/v1/auth/register", json={
            "username": "refresh_reject", "email": "refresh_reject@example.com", "password": "StrongPass123"
        })
        assert reg.status_code == 200
        access = reg.json().get("token")
        assert access

        r = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert r.status_code == 401

    def test_session_rejects_refresh_token(self, client):
        reg = client.post("/api/v1/auth/register", json={
            "username": "session_reject", "email": "session_reject@example.com", "password": "StrongPass123"
        })
        assert reg.status_code == 200
        refresh = reg.json().get("refresh_token")
        assert refresh

        r = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r.status_code == 401

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "logintest_wrong", "email": "loginwrong@example.com", "password": "StrongPass123"
        })
        r = client.post("/api/v1/auth/login", json={
            "username": "logintest_wrong", "password": "wrongpassword"
        })
        assert r.status_code == 401

    def test_login_lockout_after_repeated_failures(self, client):
        username = f"lockuser{random.randint(1000, 9999)}"
        email = f"{username}@example.com"
        client.post("/api/v1/auth/register", json={
            "username": username, "email": email, "password": "StrongPass123"
        })

        for _ in range(settings.auth_max_attempts):
            r = client.post("/api/v1/auth/login", json={
                "username": username, "password": "wrongpassword"
            })
            assert r.status_code in (401, 429)
            if r.status_code == 429:
                break

        blocked = client.post("/api/v1/auth/login", json={
            "username": username, "password": "wrongpassword"
        })
        assert blocked.status_code == 429

    def test_profile_requires_auth(self, client):
        r = client.get("/api/v1/auth/profile")
        assert r.status_code == 401 or r.status_code == 403

    def test_delete_my_data_deletes_account(self, client):
        suffix = random.randint(1000, 9999)
        username = f"deleteme_{suffix}"

        reg = client.post("/api/v1/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "StrongPass123",
        })
        assert reg.status_code == 200
        token = reg.json()["token"]

        delete_r = client.post(
            "/api/v1/auth/delete-my-data",
            headers={"Authorization": f"Bearer {token}"},
            json={"confirm": "DELETE_MY_DATA"},
        )
        assert delete_r.status_code == 200
        data = delete_r.json()
        assert data["success"] is True
        assert data["deleted"]["users"] == 1

        profile_r = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile_r.status_code == 404

    def test_delete_my_data_requires_confirmation_phrase(self, client):
        suffix = random.randint(1000, 9999)
        username = f"deleteconfirm_{suffix}"

        reg = client.post("/api/v1/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "StrongPass123",
        })
        assert reg.status_code == 200
        token = reg.json()["token"]

        r = client.post(
            "/api/v1/auth/delete-my-data",
            headers={"Authorization": f"Bearer {token}"},
            json={"confirm": "delete"},
        )
        assert r.status_code == 400

    def test_export_my_data_requires_auth(self, client):
        r = client.get("/api/v1/auth/export-my-data")
        assert r.status_code == 401

    def test_export_my_data_returns_user_scoped_payload(self, client):
        suffix = random.randint(1000, 9999)
        user1 = f"export_u1_{suffix}"
        user2 = f"export_u2_{suffix}"

        def grant_personalization_consent(token: str):
            r = client.post(
                "/api/v1/compliance/consent",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "consent_type": "personalization",
                    "policy_version": "2026.04",
                    "granted": True,
                    "scope": "personalization",
                },
            )
            assert r.status_code == 200

        reg1 = client.post("/api/v1/auth/register", json={
            "username": user1,
            "email": f"{user1}@example.com",
            "password": "StrongPass123",
        })
        assert reg1.status_code == 200
        token1 = reg1.json()["token"]

        reg2 = client.post("/api/v1/auth/register", json={
            "username": user2,
            "email": f"{user2}@example.com",
            "password": "StrongPass123",
        })
        assert reg2.status_code == 200
        token2 = reg2.json()["token"]

        grant_personalization_consent(token1)
        grant_personalization_consent(token2)

        add1 = client.post(
            "/api/v1/personalization/goals",
            headers={"Authorization": f"Bearer {token1}"},
            json={"goal": "User1 goal", "priority": "high"},
        )
        assert add1.status_code == 200

        add2 = client.post(
            "/api/v1/personalization/goals",
            headers={"Authorization": f"Bearer {token2}"},
            json={"goal": "User2 goal", "priority": "low"},
        )
        assert add2.status_code == 200

        export_r = client.get(
            "/api/v1/auth/export-my-data",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert export_r.status_code == 200
        data = export_r.json()
        assert data["success"] is True

        payload = data["export"]
        assert payload["user"]["username"] == user1
        goals = payload.get("goals", [])
        assert any(g.get("goal") == "User1 goal" for g in goals)
        assert not any(g.get("goal") == "User2 goal" for g in goals)
        assert "retention_policy" in payload

    def test_admin_delete_user_data_forbids_non_admin(self, client):
        suffix = random.randint(1000, 9999)
        actor = f"actor_{suffix}"
        target = f"target_{suffix}"

        actor_reg = client.post("/api/v1/auth/register", json={
            "username": actor,
            "email": f"{actor}@example.com",
            "password": "StrongPass123",
        })
        assert actor_reg.status_code == 200
        actor_token = actor_reg.json()["token"]

        target_reg = client.post("/api/v1/auth/register", json={
            "username": target,
            "email": f"{target}@example.com",
            "password": "StrongPass123",
        })
        assert target_reg.status_code == 200
        target_user_id = target_reg.json()["user_id"]

        r = client.delete(
            f"/api/v1/auth/admin/users/{target_user_id}/data",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 403

    def test_admin_delete_user_data_allows_admin(self, client):
        suffix = random.randint(1000, 9999)
        target = f"admin_delete_target_{suffix}"

        target_reg = client.post("/api/v1/auth/register", json={
            "username": target,
            "email": f"{target}@example.com",
            "password": "StrongPass123",
        })
        assert target_reg.status_code == 200
        target_user_id = target_reg.json()["user_id"]
        target_token = target_reg.json()["token"]

        admin_token = create_access_token({"sub": "admin", "user_id": 1})
        r = client.delete(
            f"/api/v1/auth/admin/users/{target_user_id}/data",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["deleted"]["users"] == 1

        profile_after_delete = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert profile_after_delete.status_code == 404


class TestAnalyticsAPI:
    """Analytics endpoint tests."""

    def test_dashboard_stats(self, client):
        token = create_access_token({"sub": "admin", "user_id": 1})
        r = client.get(
            "/api/v1/analytics/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_chats" in data
        assert "daily_stats" in data
        assert "runtime_counters" in data
        assert "usage_cost_today_usd" in data
        assert "feature_usage_today" in data

    def test_clinician_queue_requires_auth(self, client):
        r = client.get("/api/v1/analytics/clinician-reviews")
        assert r.status_code == 401

    def test_clinician_queue_forbids_non_admin(self, client):
        username = f"user_non_admin_{random.randint(1000, 9999)}"
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "StrongPass123",
            },
        )
        assert reg.status_code == 200
        token = reg.json()["token"]

        r = client.get(
            "/api/v1/analytics/clinician-reviews",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    def test_clinician_queue_allows_admin(self, client):
        token = create_access_token({"sub": "admin", "user_id": 1})

        r = client.get(
            "/api/v1/analytics/clinician-reviews",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "items" in r.json()


class TestSecurityAndLimits:
    def test_cross_user_session_access_is_blocked(self, client):
        mw = _get_middleware_instance(RateLimitMiddleware)
        if mw is not None:
            mw.hits.clear()

        suffix = random.randint(1000, 9999)
        user1 = f"u1_{suffix}"
        user2 = f"u2_{suffix}"

        reg1_resp = client.post("/api/v1/auth/register", json={
            "username": user1,
            "email": f"{user1}@example.com",
            "password": "StrongPass123",
        })
        assert reg1_resp.status_code == 200
        reg1 = reg1_resp.json()

        reg2_resp = client.post("/api/v1/auth/register", json={
            "username": user2,
            "email": f"{user2}@example.com",
            "password": "StrongPass123",
        })
        assert reg2_resp.status_code == 200
        reg2 = reg2_resp.json()

        token1 = reg1["token"]
        token2 = reg2["token"]

        client.post(
            "/api/v1/chat",
            json={"message": "hello", "session_id": "shared_session_1"},
            headers={"Authorization": f"Bearer {token1}"},
        )

        forbidden = client.get(
            "/api/v1/chat/sessions/shared_session_1",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert forbidden.status_code == 404

    def test_rate_limit_429(self, client):
        mw = _get_middleware_instance(RateLimitMiddleware)
        assert mw is not None

        original = mw.requests_per_minute
        try:
            mw.requests_per_minute = 2
            mw.hits.clear()

            assert client.get("/api/v1/symptoms/list").status_code == 200
            assert client.get("/api/v1/symptoms/list").status_code == 200
            limited = client.get("/api/v1/symptoms/list")
            assert limited.status_code == 429
        finally:
            mw.requests_per_minute = original
            mw.hits.clear()

    def test_request_size_limit_413(self, client):
        mw = _get_middleware_instance(RequestSizeLimitMiddleware)
        assert mw is not None

        original = mw.max_bytes
        try:
            mw.max_bytes = 120
            too_big = client.post(
                "/api/v1/chat",
                json={"message": "A" * 500},
            )
            assert too_big.status_code == 413
        finally:
            mw.max_bytes = original

    def test_upload_size_limit_413(self, client):
        original = settings.upload_max_size_mb
        try:
            settings.upload_max_size_mb = 0
            too_big = client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.txt", b"abc", "text/plain")},
            )
            assert too_big.status_code == 413
        finally:
            settings.upload_max_size_mb = original

    def test_production_validation_rejects_weak_secret(self):
        old_env = settings.environment
        old_secret = settings.secret_key
        old_origins = settings.cors_origins
        try:
            settings.environment = "production"
            settings.secret_key = "short"
            settings.cors_origins = "http://localhost:3000"
            with pytest.raises(RuntimeError):
                _validate_production_security()
        finally:
            settings.environment = old_env
            settings.secret_key = old_secret
            settings.cors_origins = old_origins

    def test_production_validation_rejects_wildcard_cors(self):
        old_env = settings.environment
        old_secret = settings.secret_key
        old_origins = settings.cors_origins
        try:
            settings.environment = "production"
            settings.secret_key = "X" * 40
            settings.cors_origins = "*"
            with pytest.raises(RuntimeError):
                _validate_production_security()
        finally:
            settings.environment = old_env
            settings.secret_key = old_secret
            settings.cors_origins = old_origins
