"""Quick API verification script with fail-fast CI gating."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, ".")

import requests


def parse_args():
    parser = argparse.ArgumentParser(description="Verify HealthBuddy API endpoints")
    parser.add_argument(
        "--base-url",
        default=os.getenv("HEALTHBUDDY_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the running API",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failed check",
    )
    return parser.parse_args()


args = parse_args()
BASE = args.base_url.rstrip("/")
results = []


def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {}

def test(name, check):
    status = "PASS" if check else "FAIL"
    results.append((name, status))
    print(f"  [{status}] {name}")
    if status == "FAIL" and args.fail_fast:
        raise SystemExit(1)


def safe_request(method: str, path: str, **kwargs) -> requests.Response | None:
    url = f"{BASE}{path}"
    try:
        kwargs.setdefault("timeout", 30)
        return requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        test(f"HTTP {method} {path}", False)
        print(f"  [ERROR] {exc}")
        return None

print("=" * 50)
print("  HealthBuddy-AI — Full API Verification")
print("=" * 50)

# 1. Health
r = safe_request("GET", "/api/health")
if r is None:
    raise SystemExit(1)
test("Health Check (200)", r.status_code == 200)
d = safe_json(r)
test("Health: has status field", d.get("status") == "healthy")

# 2. Symptom Check
r = safe_request("POST", "/api/v1/symptoms/check",
                  json={"symptoms": ["headache", "fever", "cough"]})
if r is None:
    raise SystemExit(1)
test("Symptom Check (200)", r.status_code == 200)
d = safe_json(r)
predictions = d.get("predictions", [])
severity = d.get("severity")
test(f"Symptom: {len(predictions)} predictions", len(predictions) > 0)
test(f"Symptom: severity={severity}", severity in ["low", "medium", "high", "emergency"])

# 3. Emergency Detection
r = safe_request("POST", "/api/v1/symptoms/check",
                  json={"symptoms": ["chest pain", "shortness of breath"]})
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test("Emergency: detected", d.get("emergency") is True)
test("Emergency: severity=emergency", d.get("severity") == "emergency")

# 4. Symptom List
r = safe_request("GET", "/api/v1/symptoms/list")
if r is None:
    raise SystemExit(1)
d = safe_json(r)
symptoms = d.get("symptoms", [])
test(f"Symptom List: {len(symptoms)} symptoms", len(symptoms) > 20)

username = f"testdemo_{datetime.now().strftime('%Y%m%d%H%M%S')}"
password = "Pass123456"

# 5. Register
r = safe_request("POST", "/api/v1/auth/register",
            json={"username": username, "email": f"{username}@test.com",
                "password": password, "age": 25, "gender": "male", "tos_accepted": True})
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test("Register: success", d.get("success") is True)
token = d.get("token", "")
test("Register: token", bool(token))

# 6. Login
r = safe_request("POST", "/api/v1/auth/login",
                  json={"username": username, "password": password})
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test("Login: success", bool(d.get("token")))
token = d.get("token", token)

# 7. Profile
r = safe_request("GET", "/api/v1/auth/profile",
                 headers={"Authorization": f"Bearer {token}"})
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test(f"Profile: username={d.get('username')}", d.get("username") == username)
test(f"Profile: age={d.get('age')}", d.get("age") == 25)

# 8. Analytics
from app.core.security import create_access_token
admin_token = create_access_token({"sub": "admin", "role": "admin"})
r = safe_request("GET", "/api/v1/analytics/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test("Analytics Dashboard (200)", r.status_code == 200)
test(f"Analytics: total_users={d.get('total_users')}", d.get("total_users", 0) >= 1)

# 9. Documents
r = safe_request("GET", "/api/v1/documents")
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test(f"Documents endpoint returns count={d.get('total_chunks')}", "total_chunks" in d)

# 10. Chat (with safety)
r = safe_request("POST", "/api/v1/chat",
                  json={"message": "What is healthy eating?", "use_rag": True},
                  timeout=120)
if r is None:
    raise SystemExit(1)
d = safe_json(r)
test("Chat: response", bool(d.get("response")))
test("Chat: safety_disclaimer", "safety_disclaimer" in d)
test("Chat: confidence_note", "confidence_note" in d)

# Summary
print("\n" + "=" * 50)
passed = sum(1 for _, s in results if s == "PASS")
total = len(results)
print(f"  Results: {passed}/{total} PASSED")
print("=" * 50)

if passed != total:
    raise SystemExit(1)
