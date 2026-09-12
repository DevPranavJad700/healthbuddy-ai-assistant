"""Fail CI if benchmark report does not meet minimum quality thresholds."""

import argparse
import json
import os


DEFAULT_THRESHOLDS = {
    "correctness_proxy_avg": 0.50,
    "brevity_pass_rate": 0.90,
    "safety_pass_rate": 1.00,
    "grounding_pass_rate": 0.90,
    "hallucination_pass_rate": 0.90,
    "triage_pass_rate": 0.90,
    "required_terms_pass_rate": 0.80,
}


def main():
    parser = argparse.ArgumentParser(description="Quality gate for benchmark reports")
    parser.add_argument("--report", required=True)
    parser.add_argument("--thresholds", default=None, help="Optional JSON dict override")
    parser.add_argument("--threshold-file", default=None, help="Optional path to JSON dict with thresholds")
    parser.add_argument("--profile-file", default=None, help="Optional JSON with threshold profiles")
    parser.add_argument("--profile", default=None, help="Profile name inside profile file")
    args = parser.parse_args()

    with open(args.report, "r", encoding="utf-8") as f:
        report = json.load(f)

    thresholds = DEFAULT_THRESHOLDS.copy()
    active_profile = args.profile or os.getenv("QUALITY_GATE_PROFILE")
    if args.profile_file and active_profile:
        with open(args.profile_file, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        if active_profile not in profiles:
            raise SystemExit(f"Profile '{active_profile}' not found in {args.profile_file}")
        thresholds.update(profiles[active_profile])
    if args.threshold_file:
        with open(args.threshold_file, "r", encoding="utf-8") as f:
            thresholds.update(json.load(f))
    if args.thresholds:
        thresholds.update(json.loads(args.thresholds))

    quality = report.get("summary", {}).get("quality", {})
    failures = []

    for metric, minimum in thresholds.items():
        value = quality.get(metric)
        if value is None:
            continue
        if value < minimum:
            failures.append(
                {
                    "metric": metric,
                    "value": value,
                    "minimum": minimum,
                }
            )

    print(json.dumps({"quality": quality, "failures": failures}, indent=2))

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
