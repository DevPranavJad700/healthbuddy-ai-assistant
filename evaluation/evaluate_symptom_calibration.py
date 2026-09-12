"""Evaluate symptom checker calibration against labeled cases.

Outputs emergency precision/recall and severity accuracy.
Exits with non-zero code when thresholds are not met.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def parse_args():
    p = argparse.ArgumentParser(description="Evaluate symptom checker calibration")
    p.add_argument(
        "--cases",
        default="evaluation/symptom_calibration_cases.json",
        help="Path to labeled symptom cases JSON",
    )
    p.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of running API",
    )
    p.add_argument(
        "--min-emergency-recall",
        type=float,
        default=0.95,
        help="Minimum acceptable emergency recall",
    )
    p.add_argument(
        "--max-emergency-fpr",
        type=float,
        default=0.25,
        help="Maximum acceptable emergency false positive rate",
    )
    p.add_argument(
        "--min-severity-accuracy",
        type=float,
        default=0.60,
        help="Minimum acceptable severity accuracy",
    )
    p.add_argument(
        "--output",
        default="evaluation/symptom_calibration_results.json",
        help="JSON output path for detailed results",
    )
    return p.parse_args()


def main():
    args = parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    base = args.base_url.rstrip("/")

    tp = fp = tn = fn = 0
    severity_hits = 0
    rows = []

    for case in cases:
        r = requests.post(
            f"{base}/api/v1/symptoms/check",
            json={"symptoms": case["symptoms"]},
            timeout=30,
        )
        if r.status_code != 200:
            raise SystemExit(f"Case '{case['name']}' failed with HTTP {r.status_code}")

        data = r.json()
        pred_emergency = bool(data.get("emergency"))
        pred_severity = str(data.get("severity", "")).lower()
        exp_emergency = bool(case["expected_emergency"])
        exp_severity = str(case["expected_severity"]).lower()

        if exp_emergency and pred_emergency:
            tp += 1
        elif exp_emergency and not pred_emergency:
            fn += 1
        elif (not exp_emergency) and pred_emergency:
            fp += 1
        else:
            tn += 1

        if pred_severity == exp_severity:
            severity_hits += 1

        rows.append(
            {
                "name": case["name"],
                "expected_emergency": exp_emergency,
                "pred_emergency": pred_emergency,
                "expected_severity": exp_severity,
                "pred_severity": pred_severity,
                "predictions_count": len(data.get("predictions") or []),
            }
        )

    pos = tp + fn
    neg = tn + fp
    emergency_recall = tp / pos if pos else 1.0
    emergency_fpr = fp / neg if neg else 0.0
    severity_accuracy = severity_hits / len(cases) if cases else 0.0

    summary = {
        "cases": len(cases),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "emergency_recall": round(emergency_recall, 3),
        "emergency_false_positive_rate": round(emergency_fpr, 3),
        "severity_accuracy": round(severity_accuracy, 3),
        "thresholds": {
            "min_emergency_recall": args.min_emergency_recall,
            "max_emergency_fpr": args.max_emergency_fpr,
            "min_severity_accuracy": args.min_severity_accuracy,
        },
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps({"summary": summary, "cases": rows}, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    print(f"Detailed results written to {args.output}")

    failed = (
        emergency_recall < args.min_emergency_recall
        or emergency_fpr > args.max_emergency_fpr
        or severity_accuracy < args.min_severity_accuracy
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
