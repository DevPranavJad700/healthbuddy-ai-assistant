"""Post-deploy smoke checks for health, chat, and auth."""

import uuid
import requests

BASE = "http://127.0.0.1:8000"


def must(name: str, condition: bool, detail: str = ""):
    if not condition:
        raise SystemExit(f"[FAIL] {name} {detail}")
    print(f"[PASS] {name}")


if __name__ == "__main__":
    r = requests.get(f"{BASE}/api/health", timeout=20)
    must("health 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BASE}/api/live", timeout=20)
    must("live 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BASE}/api/ready", timeout=20)
    must("ready endpoint", r.status_code in (200, 503), str(r.status_code))

    # Auth round-trip
    username = f"smoke_{uuid.uuid4().hex[:8]}"
    password = "SmokePass123!"

    r = requests.post(
        f"{BASE}/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "age": 30,
            "gender": "male",
        },
        timeout=20,
    )
    must("register", r.status_code in (200, 400), str(r.status_code))

    r = requests.post(
        f"{BASE}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=20,
    )
    must("login 200", r.status_code == 200, str(r.status_code))

    # Chat
    r = requests.post(
        f"{BASE}/api/v1/chat",
        json={"message": "Give 3 hydration tips", "use_rag": False},
        timeout=90,
    )
    must("chat 200", r.status_code == 200, str(r.status_code))
    payload = r.json()
    must("chat has response", bool(payload.get("response")))

    print("Smoke checks passed")
