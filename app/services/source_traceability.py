"""Map source files to guideline references for explainable traceability."""

from __future__ import annotations

TRACEABILITY_MAP: dict[str, dict[str, str]] = {
    "clinical_protocols_source_versioned_v2.txt": {
        "guideline_ref": "HB-Clinical-Protocols-v2.0",
        "guideline_url": "https://www.who.int/health-topics/emergencies",
        "source_version": "v2.0",
    },
    "clinical_protocol_quickref_v1.txt": {
        "guideline_ref": "HB-QuickRef-v1",
        "guideline_url": "https://www.cdc.gov/",
        "source_version": "v1.0",
    },
    "validation_health_facts_v1.txt": {
        "guideline_ref": "HB-Validation-Facts-v1",
        "guideline_url": "https://www.nice.org.uk/guidance",
        "source_version": "v1.0",
    },
}


def resolve_traceability(source_name: str) -> dict[str, str | None]:
    key = (source_name or "").strip()
    data = TRACEABILITY_MAP.get(key, {})
    return {
        "guideline_ref": data.get("guideline_ref"),
        "guideline_url": data.get("guideline_url"),
        "source_version": data.get("source_version"),
    }
