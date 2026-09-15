#!/usr/bin/env python3
"""
Screenshot capture script for HealthBuddy AI portfolio documentation.

Starts the app on a temporary port, navigates through key flows using
Playwright, saves PNGs to docs/screenshots/, then shuts the server down.

Usage:
    python scripts/capture_screenshots.py

Captures 4 sharp screenshots (viewport 1280x800, device_scale_factor=2):
    1. chat_rag_flow.png - Clinical question, RAG response, source transparency citations
    2. triage_emergency_overlay.png - Emergency chest pain trigger with emergency alert & trust card
    3. symptom_checker_results.png - Symptom checker with selected chips, condition matches & recommendations
    4. clinician_review_queue.png - Admin clinician review tab with escalated triage queue table
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = ROOT / "docs" / "screenshots"
PORT = 8099
BASE_URL = f"http://127.0.0.1:{PORT}"


# ---------------------------------------------------------------------------
# Server lifecycle helpers
# ---------------------------------------------------------------------------

def _start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///./data/healthbuddy_screenshots.db"
    env["DB_AUTO_CREATE_ON_STARTUP"] = "true"
    env["DB_RUN_MIGRATIONS_ON_STARTUP"] = "false"
    env["PRELOAD_MODELS_ON_STARTUP"] = "false"
    env["PRELOAD_VECTOR_STORE_ON_STARTUP"] = "false"
    env["ENVIRONMENT"] = "development"
    env["ADMIN_USERNAMES"] = "admin,screenshotadmin"
    env["CORS_ORIGINS"] = f"http://127.0.0.1:{PORT},http://localhost:{PORT}"
    env["STARTUP_PROVIDER_CONNECTIVITY_CHECK"] = "false"
    env["REQUIRE_TOS_ACCEPTANCE"] = "false"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(PORT),
            "--app-dir", str(ROOT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def _wait_for_server(timeout: int = 45) -> None:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/live", timeout=2):
                return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready on {BASE_URL} within {timeout}s")


def _stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

    db = ROOT / "data" / "healthbuddy_screenshots.db"
    try:
        db.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _login_or_register(page, username: str, password: str) -> None:
    """Register or log in via the auth modal, dismissing the onboarding wizard."""
    page.click("#openAuthModalBtn")
    page.wait_for_selector("#authModal[aria-hidden='false']", timeout=8000)
    page.click("#authModeCreateBtn")
    page.fill("#authUsernameInput", username)
    page.fill("#authEmailInput", f"{username}@example.com")
    page.fill("#authPasswordInput", password)
    if page.locator("#authTermsCheckbox").count() > 0:
        page.check("#authTermsCheckbox")
    page.click("#authRegisterBtn")
    page.wait_for_selector("#signedInBadge", timeout=12000)
    page.wait_for_timeout(800)

    # Dismiss profile onboarding wizard if it appears
    skip_btn = page.locator("#wizardSkipBtn")
    if skip_btn.count() > 0 and skip_btn.is_visible():
        skip_btn.click()
        page.wait_for_timeout(300)


def _screenshot(page, name: str) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(dest), full_page=False)
    size_kb = dest.stat().st_size // 1024
    print(f"  [OK] Saved {dest.name} ({size_kb} KB)")
    return dest


# ---------------------------------------------------------------------------
# Main capture routine
# ---------------------------------------------------------------------------

def capture_all() -> dict[str, Path]:
    from playwright.sync_api import sync_playwright

    saved: dict[str, Path] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        # ------------------------------------------------------------------
        # 1. Chat + RAG flow with Source Transparency citations
        # ------------------------------------------------------------------
        print("\n[1/4] Capturing Chat + RAG flow...")
        context1 = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page1 = context1.new_page()
        page1.goto(BASE_URL, wait_until="domcontentloaded")
        page1.wait_for_selector("#messageInput", timeout=15000)
        page1.wait_for_timeout(1000)

        page1.fill("#messageInput", "What are the common symptoms and early warning signs of Type 2 diabetes?")
        page1.click("#sendButton")

        # Wait for streaming to finish and feedback box to appear
        page1.wait_for_selector(".message.bot:last-child .feedback-box", timeout=60000)
        page1.wait_for_timeout(1000)

        # Expand the source transparency panel if present to show citation cards
        source_summary = page1.locator(".source-transparency-panel summary")
        if source_summary.count() > 0 and source_summary.first.is_visible():
            source_summary.first.click()
            page1.wait_for_timeout(600)

        saved["chat_rag_flow"] = _screenshot(page1, "chat_rag_flow")
        context1.close()

        # ------------------------------------------------------------------
        # 2. Emergency / Triage overlay (cardiac query trigger)
        # ------------------------------------------------------------------
        print("\n[2/4] Capturing Emergency Triage overlay...")
        context2 = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page2 = context2.new_page()
        page2.goto(BASE_URL, wait_until="domcontentloaded")
        page2.wait_for_selector("#messageInput", timeout=15000)
        page2.wait_for_timeout(800)

        page2.fill("#messageInput", "I have crushing chest pain and shortness of breath")
        page2.click("#sendButton")

        # Wait for emergency alert or trust card with emergency triage level
        page2.wait_for_selector(".emergency-alert, .trust-badge.trust-badge--emergency, .message.bot", timeout=30000)
        page2.wait_for_timeout(1200)

        saved["triage_emergency_overlay"] = _screenshot(page2, "triage_emergency_overlay")
        context2.close()

        # ------------------------------------------------------------------
        # 3. Symptom Checker flow
        # ------------------------------------------------------------------
        print("\n[3/4] Capturing Symptom Checker results...")
        context3 = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page3 = context3.new_page()
        page3.goto(BASE_URL, wait_until="domcontentloaded")
        page3.wait_for_selector("#messageInput", timeout=15000)
        page3.wait_for_timeout(800)

        # Click Symptoms tab
        page3.click("#symptomTabBtn")
        page3.wait_for_selector("#symptomInput", timeout=10000)
        page3.wait_for_timeout(500)

        # Select symptoms from the dropdown
        for sym in ["fever", "cough", "fatigue"]:
            try:
                page3.select_option("#symptomInput", sym)
                page3.click("#addSymptomBtn")
                page3.wait_for_timeout(200)
            except Exception:
                pass

        # Click Analyze Symptoms
        page3.click("#checkSymptomsBtn")
        page3.wait_for_selector("#messagesList .message.bot", timeout=25000)
        page3.wait_for_timeout(1200)

        saved["symptom_checker_results"] = _screenshot(page3, "symptom_checker_results")
        context3.close()

        # ------------------------------------------------------------------
        # 4. Clinician Review Queue (Admin view)
        # ------------------------------------------------------------------
        print("\n[4/4] Capturing Clinician Review Queue...")
        context4 = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page4 = context4.new_page()
        page4.goto(BASE_URL, wait_until="domcontentloaded")
        page4.wait_for_selector("#messageInput", timeout=15000)
        page4.wait_for_timeout(800)

        # Register admin user
        admin_username = "admin"
        admin_password = "AdminStrongPass123"
        _login_or_register(page4, admin_username, admin_password)

        # Trigger an escalation to ensure there is at least one item in the queue
        page4.fill("#messageInput", "Severe acute chest pain radiating to left arm and jaw")
        page4.click("#sendButton")
        page4.wait_for_selector(".feedback-box button[data-review='true']", timeout=60000)
        page4.locator(".feedback-box button[data-review='true']").first.click()
        page4.wait_for_timeout(1000)

        # Open clinician tab
        if page4.locator("#sidebarMoreToggle").is_visible():
            page4.click("#sidebarMoreToggle")
            page4.wait_for_timeout(300)
        page4.click("#clinicianTabBtn")
        page4.click("#refreshQueueBtn")
        page4.wait_for_timeout(1500)

        saved["clinician_review_queue"] = _screenshot(page4, "clinician_review_queue")
        context4.close()

        browser.close()

    return saved


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print("Starting local server for automated screenshot capture...")
    proc = _start_server()

    try:
        _wait_for_server()
        print(f"Server ready at {BASE_URL}")
        saved = capture_all()

        print("\n" + "=" * 50)
        print("Captured screenshots:")
        all_valid = True
        for name, path in saved.items():
            if not path.exists():
                print(f"  [MISSING] {name}")
                all_valid = False
                continue
            size_kb = path.stat().st_size // 1024
            if size_kb < 10:
                print(f"  [TOO SMALL] {path.name} ({size_kb} KB)")
                all_valid = False
            else:
                print(f"  [VALID] {path.name} ({size_kb} KB)")
        print("=" * 50)

        if not all_valid or len(saved) < 4:
            sys.exit(1)

    finally:
        print("\nStopping server...")
        _stop_server(proc)
        print("Done.")


if __name__ == "__main__":
    main()
