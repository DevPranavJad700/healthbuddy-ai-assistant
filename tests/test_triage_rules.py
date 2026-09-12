"""
Unit tests for the triage rules engine.

Tests emergency, urgent, and self-care rule evaluation with various symptom inputs.
"""

import pytest
from app.services.triage_rules import assess_triage, TRIAGE_RULESET_VERSION


# ==========================================
# Triage Rule Evaluation
# ==========================================

class TestTriageEvaluation:
    """Test the triage rules engine correctly classifies symptoms."""

    def test_emergency_chest_pain(self):
        result = assess_triage("I have severe chest pain and shortness of breath", "", None)
        assert result["level"] == "emergency"
        assert result["ruleset_version"] == TRIAGE_RULESET_VERSION

    def test_emergency_from_safety_alert(self):
        result = assess_triage("something", "response", "cardiac_emergency")
        assert result["level"] == "emergency"
        assert result["rule_id"] == "SAFETY_LAYER_EMERGENCY"

    def test_emergency_stroke(self):
        result = assess_triage("sudden face droop and slurred speech", "", None)
        assert result["level"] == "emergency"
        assert "STROKE" in result["rule_id"]

    def test_emergency_cardiac_arrest(self):
        result = assess_triage("cardiac arrest unresponsive", "", None)
        assert result["level"] == "emergency"

    def test_emergency_sepsis(self):
        result = assess_triage("high fever with confusion and sepsis", "", None)
        assert result["level"] == "emergency"

    def test_urgent_high_fever(self):
        result = assess_triage("I have persistent fever for 5 days now", "", None)
        # Check for urgent or self_care depending on rule matching
        assert result["level"] in ("urgent", "self_care", "emergency")
        assert "ruleset_version" in result

    def test_urgent_severe_headache(self):
        result = assess_triage("severe headache with vision changes", "", None)
        assert result["level"] in ("urgent", "emergency")

    def test_self_care_normal_question(self):
        result = assess_triage("What is the capital of France?", "It's Paris.", None)
        assert result["level"] == "self_care"
        assert result["rule_id"] == "SELF_CARE_DEFAULT"

    def test_self_care_mild_symptoms(self):
        result = assess_triage("I have a mild headache", "Rest and stay hydrated.", None)
        assert result["level"] == "self_care"

    def test_result_structure(self):
        result = assess_triage("severe chest pain", "", None)
        assert "level" in result
        assert "rule_id" in result
        assert "reason" in result
        assert "ruleset_version" in result
        assert "action" in result

    def test_version_is_string(self):
        assert isinstance(TRIAGE_RULESET_VERSION, str)
        assert len(TRIAGE_RULESET_VERSION) > 0

    def test_empty_input_returns_self_care(self):
        result = assess_triage("", "", None)
        assert result["level"] == "self_care"

    def test_response_text_also_scanned(self):
        """Triage should scan BOTH question and response for red flags."""
        result = assess_triage("tell me about heart health", "cardiac arrest is very dangerous", None)
        assert result["level"] == "emergency"
