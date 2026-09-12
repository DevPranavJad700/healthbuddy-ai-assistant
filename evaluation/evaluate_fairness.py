"""Cohort fairness check for triage consistency across demographic/language groups."""

import argparse
import json
from collections import defaultdict

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", default="./evaluation/fairness_cases.json")
    parser.add_argument("--output", default="./evaluation/fairness_report.json")
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        cases = json.load(f)

    cohort_stats = defaultdict(lambda: {"total": 0, "triage_pass": 0})
    detailed = []

    for row in cases:
        payload = {
            "message": row["question"],
            "use_rag": True,
            "disable_cache": True,
            "consent_to_ai_guidance": True,
            "preferred_language": row.get("preferred_language"),
        }
        r = requests.post(f"{args.base_url.rstrip('/')}/api/v1/chat", json=payload, timeout=90)
        triage = None
        ok = False
        if r.status_code == 200:
            triage = (r.json().get("triage_level") or "").lower()
            ok = triage == row["expected_triage"].lower()

        c = row["cohort"]
        cohort_stats[c]["total"] += 1
        cohort_stats[c]["triage_pass"] += 1 if ok else 0
        detailed.append({"cohort": c, "status": r.status_code, "triage": triage, "pass": ok})

    summary = {}
    rates = []
    for cohort, stats in cohort_stats.items():
        rate = stats["triage_pass"] / max(1, stats["total"])
        summary[cohort] = {"triage_pass_rate": round(rate, 3), **stats}
        rates.append(rate)

    disparity = max(rates) - min(rates) if rates else 0.0
    report = {
        "summary": {"max_pass_rate_disparity": round(disparity, 3), "cohorts": summary},
        "cases": detailed,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
