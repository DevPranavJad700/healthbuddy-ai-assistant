"""Browser end-to-end tests for auth/goals/chat/feedback/clinician queue."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

if os.getenv("RUN_E2E") != "1":
    pytest.skip("RUN_E2E=1 not set; skipping browser end-to-end tests", allow_module_level=True)

playwright = pytest.importorskip("playwright.sync_api")

BASE_URL = "http://127.0.0.1:8010"


def _wait_for_server(url: str, timeout_seconds: int = 45):
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            resp = requests.get(f"{url}/api/live", timeout=2)
            if resp.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError("E2E server did not become ready in time")


@pytest.fixture(scope="session")
def e2e_server():
    project_root = Path(__file__).resolve().parents[1]
    test_db = project_root / "data" / "healthbuddy_e2e.db"
    if test_db.exists():
        test_db.unlink()

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///./data/healthbuddy_e2e.db"
    env["DB_AUTO_CREATE_ON_STARTUP"] = "true"
    env["DB_RUN_MIGRATIONS_ON_STARTUP"] = "false"
    env["PRELOAD_MODELS_ON_STARTUP"] = "false"
    env["PRELOAD_VECTOR_STORE_ON_STARTUP"] = "false"
    env["ENVIRONMENT"] = "development"
    env["ADMIN_USERNAMES"] = "admin"

    python_exe = Path(sys.executable)
    proc = subprocess.Popen(
        [
            str(python_exe),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
            "--app-dir",
            str(project_root),
        ],
        cwd=str(project_root),
        env=env,
    )

    try:
        _wait_for_server(BASE_URL)
        yield BASE_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        if test_db.exists():
            try:
                test_db.unlink()
            except OSError:
                pass


@pytest.fixture()
def page(e2e_server):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(e2e_server, wait_until="domcontentloaded")
        page.wait_for_selector("#messageInput")
        yield page
        context.close()
        browser.close()


def _login_or_register(page, username: str, password: str):
    page.click("#openAuthModalBtn")
    page.wait_for_selector("#authModal[aria-hidden='false']")
    page.click("#authModeCreateBtn")
    page.fill("#authUsernameInput", username)
    page.fill("#authEmailInput", f"{username}@example.com")
    page.fill("#authPasswordInput", password)
    if page.locator("#authTermsCheckbox").count() > 0:
        page.check("#authTermsCheckbox")
    page.click("#authRegisterBtn")
    page.wait_for_selector("#signedInBadge", timeout=10000)
    page.wait_for_timeout(600)


def _grant_personalization_consent(page):
    token = page.evaluate("() => localStorage.getItem('healthbuddy.jwt') || ''")
    assert token

    r = requests.post(
        f"{BASE_URL}/api/v1/compliance/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "consent_type": "personalization",
            "policy_version": "2026.04",
            "granted": True,
            "scope": "personalization",
        },
        timeout=10,
    )
    assert r.status_code == 200



def test_auth_and_goals_flow(page):
    username = f"e2e_user_{int(time.time())}"
    password = "E2eStrongPass123"
    _login_or_register(page, username, password)
    _grant_personalization_consent(page)

    # Signed-in indicator should appear.
    expect_text = page.locator("#signedInBadge")
    expect_text.wait_for(state="visible")
    assert "signed in" in expect_text.inner_text().lower()

    page.click("#goalsTabBtn")
    page.fill("#goalInput", "Walk 30 minutes daily")
    page.select_option("#goalPriority", "high")
    page.click("#addGoalBtn")
    page.wait_for_timeout(1000)
    assert page.locator("#goalList").inner_text().find("Walk 30 minutes daily") >= 0



def test_chat_and_feedback_flow(page):
    page.fill("#messageInput", "Give me two hydration tips")
    page.click("#sendButton")

    page.wait_for_selector(".feedback-box", timeout=90000)
    assert "hydration" in page.locator("#messagesList").inner_text().lower()

    page.locator(".feedback-box button[data-helpful='true']").first.click()
    page.wait_for_timeout(800)


def test_stream_completion_renders_feedback_controls(page):
    page.evaluate(
        """() => {
        window.__hbStreamCompleteSeen = false;
        window.addEventListener('healthbuddy:chat-stream-complete', () => {
            window.__hbStreamCompleteSeen = true;
        }, { once: true });
    }"""
    )

    page.fill("#messageInput", "List two practical hydration habits for a workday")
    page.click("#sendButton")

    page.wait_for_function("() => window.__hbStreamCompleteSeen === true", timeout=90000)
    page.wait_for_selector(".message.bot:last-child .feedback-box", timeout=15000)
    assert page.locator(".message.bot:last-child .feedback-box").count() >= 1



def test_clinician_queue_admin_flow(page):
    admin_username = "admin"
    password = "AdminStrongPass123"
    _login_or_register(page, admin_username, password)
    page.wait_for_timeout(800)
    admin_classes = page.locator("#adminBadge").get_attribute("class") or ""
    if "hidden" in admin_classes:
        pytest.skip("Admin role not enabled for current E2E environment")

    page.fill("#messageInput", "I have severe chest pain and cannot breathe")
    page.click("#sendButton")
    page.wait_for_selector(".feedback-box button[data-review='true']", timeout=90000)
    page.locator(".feedback-box button[data-review='true']").first.click()
    page.wait_for_timeout(1000)

    page.click("#clinicianTabBtn")
    page.click("#refreshQueueBtn")
    page.wait_for_timeout(1200)

    queue_text = page.locator("#clinicianQueue").inner_text()
    assert "No pending items" not in queue_text


def test_delete_my_data_flow(page):
    username = f"e2e_delete_{int(time.time())}"
    password = "E2eDeletePass123"
    _login_or_register(page, username, password)

    # Ensure signed-in state before delete flow.
    signed_in_text = page.locator("#signedInBadge")
    signed_in_text.wait_for(state="visible")
    assert "signed in" in signed_in_text.inner_text().lower()

    page.evaluate("() => { window.__hbDeleteMyDataProbe = { status: 'idle' }; }")
    page.click("#dangerZoneToggleBtn")
    page.evaluate("() => window.handleDeleteMyData({ forceConfirm: true })")
    page.wait_for_function(
        """() => {
        const probe = window.__hbDeleteMyDataProbe || {};
        return ['success', 'error', 'blocked', 'canceled'].includes(String(probe.status || ''));
    }""",
        timeout=15000,
    )

    probe = page.evaluate("() => window.__hbDeleteMyDataProbe")
    assert probe.get("status") in ("success", "error")

    badge_text = page.locator("#signedInBadge").inner_text().lower()
    auth_status = page.locator("#authStatus").inner_text().lower()
    if probe.get("status") == "success":
        assert "signed out" in badge_text
    else:
        assert probe.get("message")
        assert auth_status in (probe.get("message", "").lower(), "not found")
