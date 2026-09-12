"""Block release if clinical KPI report falls below required thresholds."""

import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="./evaluation/clinical_quality_report.json")
    parser.add_argument("--thresholds", default="./evaluation/clinical_kpi_thresholds.json")
    args = parser.parse_args()

    with open(args.report, "r", encoding="utf-8") as f:
        report = json.load(f)
    with open(args.thresholds, "r", encoding="utf-8") as f:
        thresholds = json.load(f)

    quality = report.get("summary", {}).get("quality", {})
    failures = []
    for k, min_val in thresholds.items():
        v = quality.get(k)
        if v is None:
            continue
        if v < min_val:
            failures.append({"metric": k, "value": v, "minimum": min_val})

    print(json.dumps({"quality": quality, "failures": failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
