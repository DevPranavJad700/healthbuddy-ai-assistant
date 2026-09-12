"""Comprehensive HealthBuddy AI system test suite — v2 (all fixes applied)."""
import requests
import json
import time

BASE = "http://127.0.0.1:8000"
results = []

def test(name, fn):
    try:
        ok, detail = fn()
        results.append((name, "PASS" if ok else "FAIL", detail))
    except Exception as e:
        results.append((name, "FAIL", str(e)[:200]))


# 1. Health Check
def t_health():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    d = r.json()
    status = d.get("status")
    docs = d.get("documents_loaded")
    return r.status_code == 200 and status == "healthy", f"status={status}, docs={docs}"
test("1. Health Check", t_health)

# 2. Liveness
def t_live():
    r = requests.get(f"{BASE}/api/live", timeout=5)
    return r.status_code == 200, r.text[:100]
test("2. Liveness", t_live)

# 3. Readiness
def t_ready():
    r = requests.get(f"{BASE}/api/ready", timeout=5)
    return r.status_code == 200, r.text[:100]
test("3. Readiness", t_ready)

# 4. Frontend loads
def t_frontend():
    r = requests.get(f"{BASE}/", timeout=10)
    return r.status_code == 200 and "HealthBuddy" in r.text, f"status={r.status_code}, len={len(r.text)}"
test("4. Frontend HTML", t_frontend)

# 5. Static CSS
def t_css():
    r = requests.get(f"{BASE}/static/styles.css", timeout=5)
    return r.status_code == 200, f"len={len(r.text)}"
test("5. Static CSS", t_css)

# 6. Static JS
def t_js():
    r = requests.get(f"{BASE}/static/app.js", timeout=5)
    return r.status_code == 200, f"len={len(r.text)}"
test("6. Static JS", t_js)

# 7. API Docs
def t_docs():
    r = requests.get(f"{BASE}/api/docs", timeout=5)
    return r.status_code == 200, f"status={r.status_code}"
test("7. API Docs", t_docs)

# 8. Chat (non-streaming)
def t_chat():
    r = requests.post(f"{BASE}/api/v1/chat", json={
        "message": "What are symptoms of dehydration?",
        "session_id": "test-001",
        "consent_to_ai_guidance": True,
        "use_rag": True,
    }, timeout=30)
    if r.status_code == 200:
        d = r.json()
        resp = d.get("response", "")
        model = d.get("model_used")
        sources = d.get("sources", [])
        return bool(resp), f"response_len={len(resp)}, model={model}, sources={len(sources)}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("8. Chat (non-streaming)", t_chat)

# 9. Chat stream
def t_stream():
    r = requests.post(f"{BASE}/api/v1/chat/stream", json={
        "message": "What is a healthy blood pressure?",
        "session_id": "test-stream-001",
        "consent_to_ai_guidance": True,
        "use_rag": True,
    }, timeout=30, stream=True)
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("event:"):
            events.append(line.split(":", 1)[1].strip())
        if len(events) > 5:
            break
    return "token" in events or "metadata" in events, f"events={events[:6]}"
test("9. Chat stream", t_stream)

# 10. Emergency detection
def t_emergency():
    r = requests.post(f"{BASE}/api/v1/chat", json={
        "message": "I am having severe chest pain and cannot breathe",
        "session_id": "test-emerg",
        "consent_to_ai_guidance": True,
    }, timeout=30)
    if r.status_code == 200:
        d = r.json()
        alert = d.get("emergency_alert")
        triage = d.get("triage_level")
        return alert is not None, f"emergency_alert present={alert is not None}, triage={triage}"
    return False, f"status={r.status_code}"
test("10. Emergency Detection", t_emergency)

# 11. Safety filter (FIXED — expanded patterns)
def t_safety():
    r = requests.post(f"{BASE}/api/v1/chat", json={
        "message": "I want to hurt myself and end everything",
        "session_id": "test-safe",
        "consent_to_ai_guidance": True,
    }, timeout=30)
    if r.status_code == 200:
        d = r.json()
        sf = d.get("safety_flagged")
        ea = d.get("emergency_alert")
        return sf is True or ea is not None, f"safety={sf}, emerg_alert present={ea is not None}"
    return False, f"status={r.status_code}"
test("11. Safety Filter (self-harm)", t_safety)

# 12. Symptom checker (FIXED — now returns 'response' field)
def t_symptom():
    r = requests.post(f"{BASE}/api/v1/symptoms/check", json={
        "symptoms": ["headache", "fever", "nausea"],
    }, timeout=30)
    if r.status_code == 200:
        d = r.json()
        resp = d.get("response", "")
        preds = d.get("predictions", [])
        return bool(resp) and len(preds) > 0, f"response_len={len(resp)}, predictions={len(preds)}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("12. Symptom Checker", t_symptom)

# 13. Documents list
def t_docs_list():
    r = requests.get(f"{BASE}/api/v1/documents", timeout=5)
    if r.status_code == 200:
        d = r.json()
        return True, f"count={len(d.get('documents', []))}"
    return False, f"status={r.status_code}"
test("13. Documents List", t_docs_list)

# 14. Register user (FIXED — tos_accepted field)
def t_register():
    ts = int(time.time())
    r = requests.post(f"{BASE}/api/v1/auth/register", json={
        "username": f"testuser_{ts}",
        "email": f"test_{ts}@example.com",
        "password": "TestPass12345!",
        "full_name": "Test User",
        "age": 25,
        "tos_accepted": True,
    }, timeout=10)
    if r.status_code == 200:
        d = r.json()
        return d.get("success") is True and "token" in d, f"success={d.get('success')}, has_token={'token' in d}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("14. Register User", t_register)

# 15. Login (depends on registration working)
def t_login():
    ts = int(time.time())
    reg = requests.post(f"{BASE}/api/v1/auth/register", json={
        "username": f"logintest_{ts}",
        "email": f"login_{ts}@example.com",
        "password": "TestPass12345!",
        "full_name": "Login Test",
        "age": 25,
        "tos_accepted": True,
    }, timeout=10)
    if reg.status_code != 200:
        return False, f"registration failed: status={reg.status_code}, body={reg.text[:150]}"
    r = requests.post(f"{BASE}/api/v1/auth/login", json={
        "username": f"logintest_{ts}",
        "password": "TestPass12345!",
    }, timeout=10)
    if r.status_code == 200:
        d = r.json()
        return "token" in d, f"has_token={'token' in d}, refresh={'refresh_token' in d}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("15. Login", t_login)

# 16. Theme controls present
def t_theme():
    r = requests.get(f"{BASE}/", timeout=5)
    has_theme = "themeMenuToggle" in r.text and "color-btn" in r.text
    return has_theme, f"theme_controls_present={has_theme}"
test("16. Theme Controls", t_theme)

# 17. Consent Types (FIXED — new endpoint)
def t_consent():
    r = requests.get(f"{BASE}/api/v1/compliance/consents/types", timeout=5)
    if r.status_code == 200:
        d = r.json()
        types = d.get("types", [])
        return len(types) > 0, f"types_count={len(types)}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("17. Consent Types", t_consent)

# 18. Privacy page
def t_privacy():
    r = requests.get(f"{BASE}/privacy", timeout=5)
    return r.status_code == 200, f"status={r.status_code}"
test("18. Privacy Page", t_privacy)

# 19. Terms page
def t_terms():
    r = requests.get(f"{BASE}/terms", timeout=5)
    return r.status_code == 200, f"status={r.status_code}"
test("19. Terms Page", t_terms)

# 20. Startup diagnostics
def t_diag():
    r = requests.get(f"{BASE}/api/startup-diagnostics", timeout=5)
    if r.status_code == 200:
        d = r.json()
        runtime = d.get("runtime", {})
        ready = runtime.get("rag_service_ready")
        return ready is True, json.dumps(runtime)
    return False, f"status={r.status_code}"
test("20. Startup Diagnostics", t_diag)

# 21. Security headers
def t_security_headers():
    r = requests.get(f"{BASE}/", timeout=5)
    h = r.headers
    csp = "Content-Security-Policy" in h
    hsts = "Strict-Transport-Security" in h
    xcto = "X-Content-Type-Options" in h
    xfo = "X-Frame-Options" in h
    return all([csp, hsts, xcto, xfo]), f"CSP={csp}, HSTS={hsts}, XCTO={xcto}, XFO={xfo}"
test("21. Security Headers", t_security_headers)

# 22. Metrics endpoint
def t_metrics():
    r = requests.get(f"{BASE}/api/metrics", timeout=5)
    return r.status_code == 200, f"len={len(r.text)}"
test("22. Metrics Endpoint", t_metrics)

# 23. Authenticated chat with token (depends on registration + login + consent)
def t_auth_chat():
    ts = int(time.time())
    reg = requests.post(f"{BASE}/api/v1/auth/register", json={
        "username": f"authchat_{ts}",
        "email": f"authchat_{ts}@example.com",
        "password": "TestPass12345!",
        "full_name": "Auth Chat Test",
        "age": 30,
        "tos_accepted": True,
    }, timeout=10)
    if reg.status_code != 200:
        return False, f"register_status={reg.status_code}, body={reg.text[:150]}"
    token = reg.json().get("token")
    if not token:
        return False, "no token in registration response"
    headers = {"Authorization": f"Bearer {token}"}
    # Record ai_guidance consent (required for authenticated chat)
    cr = requests.post(f"{BASE}/api/v1/compliance/consent", json={
        "consent_type": "ai_guidance",
        "policy_version": "2026.04",
        "granted": True,
        "scope": "chat",
    }, headers=headers, timeout=10)
    if cr.status_code != 200:
        return False, f"consent_status={cr.status_code}, body={cr.text[:150]}"
    # Record terms acceptance
    tr = requests.post(f"{BASE}/api/v1/compliance/consent", json={
        "consent_type": "terms_of_use",
        "policy_version": "2026.04",
        "granted": True,
        "scope": "platform",
    }, headers=headers, timeout=10)
    if tr.status_code != 200:
        return False, f"terms_status={tr.status_code}, body={tr.text[:150]}"
    # Now chat
    r = requests.post(f"{BASE}/api/v1/chat", json={
        "message": "How much water should I drink daily?",
        "session_id": "auth-test-001",
        "consent_to_ai_guidance": True,
        "use_rag": True,
    }, headers=headers, timeout=30)
    if r.status_code == 200:
        d = r.json()
        return bool(d.get("response")), f"response_len={len(d.get('response', ''))}"
    return False, f"status={r.status_code}, body={r.text[:200]}"
test("23. Authenticated Chat", t_auth_chat)

# 24. Consent denied check
def t_consent_denied():
    r = requests.post(f"{BASE}/api/v1/chat", json={
        "message": "test",
        "consent_to_ai_guidance": False,
    }, timeout=10)
    return r.status_code == 400, f"status={r.status_code}"
test("24. Consent Denied Check", t_consent_denied)

# 25. Usage quota endpoint
def t_usage():
    r = requests.get(f"{BASE}/api/v1/usage/quota", timeout=5)
    return r.status_code in (200, 401, 403), f"status={r.status_code}"
test("25. Usage Quota Endpoint", t_usage)

# Print results
print()
print("=" * 80)
print("HEALTHBUDDY AI - COMPREHENSIVE SYSTEM TEST RESULTS (v2 — all fixes)")
print("=" * 80)
passed = 0
failed = 0
for name, status, detail in results:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"[{icon}] {name}: {detail}")
    if status == "PASS":
        passed += 1
    else:
        failed += 1
print()
print(f"TOTAL: {passed}/{passed + failed} passed ({failed} failed)")
print("=" * 80)
