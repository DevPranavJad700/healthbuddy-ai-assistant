"""Versioned clinician-validated triage rules for chat escalation."""

from __future__ import annotations

import re
from dataclasses import dataclass


TRIAGE_RULESET_VERSION = "clinician-v1.1"


@dataclass(frozen=True)
class TriageRule:
    rule_id: str
    level: str
    reason: str
    escalation_action: str | None
    patterns: tuple[str, ...]


EMERGENCY_RULES: tuple[TriageRule, ...] = (
    TriageRule(
        rule_id="EMERG_CARDIO_RESP",
        level="emergency",
        reason="Cardiorespiratory emergency red flags detected.",
        escalation_action="Call local emergency services immediately.",
        patterns=(
            r"\b(chest pain|chest pressure|cannot breathe|can't breathe|shortness of breath)\b",
            r"\b(cardiac arrest|heart attack|collapse|unresponsive)\b",
        ),
    ),
    TriageRule(
        rule_id="EMERG_STROKE",
        level="emergency",
        reason="Potential acute stroke indicators detected.",
        escalation_action="Call emergency services immediately and note symptom onset time.",
        patterns=(
            r"\b(face droop|slurred speech|one-sided weakness|sudden numbness|stroke)\b",
        ),
    ),
    TriageRule(
        rule_id="EMERG_DKA_SEPSIS",
        level="emergency",
        reason="Potential diabetic crisis or severe systemic illness red flags detected.",
        escalation_action="Seek emergency care immediately.",
        patterns=(
            r"\b(fruity breath|rapid breathing|severe dehydration|confusion|persistent vomiting)\b",
            r"\b(high fever with confusion|sepsis)\b",
        ),
    ),
)

URGENT_RULES: tuple[TriageRule, ...] = (
    TriageRule(
        rule_id="URGENT_GI_BLEED_INFECTION",
        level="urgent",
        reason="Urgent gastrointestinal or infection warning signs detected.",
        escalation_action="Seek urgent in-person evaluation today.",
        patterns=(
            r"\b(blood in stool|black stool|persistent high fever|severe abdominal pain)\b",
        ),
    ),
    TriageRule(
        rule_id="URGENT_BP_NEURO",
        level="urgent",
        reason="Possible hypertensive urgency or neurologic red flags detected.",
        escalation_action="Seek urgent in-person evaluation today.",
        patterns=(
            r"\b(blood pressure\s*(1[89]\d|2\d\d)\s*/\s*(1[12]\d|\d{3,}))\b",
            r"\b(severe headache with vision changes|new confusion|fainting)\b",
        ),
    ),
)


def assess_triage(question: str, response: str, emergency_alert: str | None) -> dict:
    """Return triage decision with versioned rule metadata."""
    if emergency_alert:
        return {
            "level": "emergency",
            "reason": "Emergency signal detected by safety layer.",
            "action": "Call local emergency services immediately.",
            "rule_id": "SAFETY_LAYER_EMERGENCY",
            "ruleset_version": TRIAGE_RULESET_VERSION,
        }

    text = f"{question} {response}".lower()

    for rule in EMERGENCY_RULES:
        if any(re.search(pattern, text) for pattern in rule.patterns):
            return {
                "level": rule.level,
                "reason": rule.reason,
                "action": rule.escalation_action,
                "rule_id": rule.rule_id,
                "ruleset_version": TRIAGE_RULESET_VERSION,
            }

    for rule in URGENT_RULES:
        if any(re.search(pattern, text) for pattern in rule.patterns):
            return {
                "level": rule.level,
                "reason": rule.reason,
                "action": rule.escalation_action,
                "rule_id": rule.rule_id,
                "ruleset_version": TRIAGE_RULESET_VERSION,
            }

    return {
        "level": "self_care",
        "reason": "No emergency red flags detected in this turn.",
        "action": None,
        "rule_id": "SELF_CARE_DEFAULT",
        "ruleset_version": TRIAGE_RULESET_VERSION,
    }
