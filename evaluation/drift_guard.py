"""Quality drift guard.

Compares a baseline quality report with a candidate report and fails when
key metrics drop beyond configurable thresholds.
"""

import argparse
import json
from pathlib import Path


DEFAULT_MAX_DROPS = {
    "correctness_proxy_avg": 0.05,
    "brevity_pass_rate": 0.08,
    "safety_pass_rate": 0.02,
    "grounding_pass_rate": 0.05,
    "hallucination_pass_rate": 0.06,
}


def load_report(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Detect quality drift against baseline")
    parser.add_argument("--baseline", default="./evaluation/baseline_quality_report.json")
    parser.add_argument("--candidate", default="./evaluation/quality_report.json")
    args = parser.parse_args()

    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)

    bq = baseline.get("summary", {}).get("quality", {})
    cq = candidate.get("summary", {}).get("quality", {})

    failures = []
    for metric, max_drop in DEFAULT_MAX_DROPS.items():
        b = bq.get(metric)
        c = cq.get(metric)
        if b is None or c is None:
            continue
        drop = b - c
        if drop > max_drop:
            failures.append(
                {
                    "metric": metric,
                    "baseline": b,
                    "candidate": c,
                    "drop": round(drop, 3),
                    "max_allowed_drop": max_drop,
                }
            )

    print("Drift check summary")
    print(json.dumps({"failures": failures, "checked_metrics": list(DEFAULT_MAX_DROPS.keys())}, indent=2))

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
