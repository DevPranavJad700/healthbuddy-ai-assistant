"""Adversarial safety evaluation for prompt-injection and harmful requests."""

import argparse
import json

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", default="./evaluation/adversarial_redteam_cases.json")
    parser.add_argument("--output", default="./evaluation/adversarial_report.json")
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        rows = json.load(f)

    results = []
    blocked = 0
    for row in rows:
        r = requests.post(
            f"{args.base_url.rstrip('/')}/api/v1/chat",
            json={
                "message": row["question"],
                "use_rag": True,
                "disable_cache": True,
                "consent_to_ai_guidance": True,
            },
            timeout=90,
        )
        text = ""
        if r.status_code == 200:
            text = (r.json().get("response") or "").lower()
        forbidden = [t.lower() for t in row.get("forbidden_terms", [])]
        safe = not any(term in text for term in forbidden)
        if safe:
            blocked += 1
        results.append({"name": row["name"], "status": r.status_code, "safe": safe})

    report = {
        "summary": {
            "num_cases": len(rows),
            "safe_rate": round(blocked / max(1, len(rows)), 3),
        },
        "cases": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
