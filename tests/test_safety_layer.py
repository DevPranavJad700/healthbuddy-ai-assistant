"""
Unit tests for the medical safety layer.

Tests emergency detection, harmful content filtering, output moderation,
and disclaimer injection for all 6 emergency types.
"""

import pytest
from app.services.safety_layer import SafetyLayer, MEDICAL_DISCLAIMER


@pytest.fixture
def safety():
    return SafetyLayer()


# ==========================================
# Emergency Detection (Input Scanning)
# ==========================================

class TestEmergencyDetection:
    """Test emergency types are correctly detected in user input."""

    def test_cardiac_chest_pain(self, safety):
        result = safety.check_user_input("I have severe chest pain")
        assert result.is_emergency is True
        assert result.emergency_type == "cardiac_emergency"

    def test_cardiac_heart_attack(self, safety):
        result = safety.check_user_input("Am I having a heart attack?")
        assert result.is_emergency is True
        assert result.emergency_type == "cardiac_emergency"

    def test_mental_health_suicide(self, safety):
        result = safety.check_user_input("I want to kill myself")
        assert result.is_emergency is True
        assert result.emergency_type == "mental_health_crisis"
        assert "988" in result.warning_message or "Crisis" in result.warning_message

    def test_mental_health_self_harm(self, safety):
        result = safety.check_user_input("thinking about self-harm")
        assert result.is_emergency is True
        assert result.emergency_type == "mental_health_crisis"

    def test_respiratory_cant_breathe(self, safety):
        result = safety.check_user_input("I can't breathe help me")
        assert result.is_emergency is True
        assert result.emergency_type == "respiratory_emergency"

    def test_respiratory_anaphylaxis(self, safety):
        result = safety.check_user_input("severe allergic reaction anaphylaxis")
        assert result.is_emergency is True
        assert result.emergency_type == "respiratory_emergency"

    def test_poisoning_swallowed(self, safety):
        result = safety.check_user_input("my child swallowed bleach")
        assert result.is_emergency is True
        assert result.emergency_type == "poisoning_emergency"

    def test_stroke_symptoms(self, safety):
        result = safety.check_user_input("sudden numbness one side, can't speak, face drooping")
        assert result.is_emergency is True
        assert result.emergency_type == "stroke_emergency"

    def test_emergency_is_still_safe(self, safety):
        """Emergencies are flagged but the input is still 'safe' to process."""
        result = safety.check_user_input("I have chest pain")
        assert result.is_safe is True  # We process it, just flag as emergency


# ==========================================
# Normal Input — No Emergency
# ==========================================

class TestNormalInput:
    """Test that normal health questions don't trigger emergencies."""

    def test_headache(self, safety):
        result = safety.check_user_input("I have a mild headache")
        assert result.is_emergency is False
        assert result.is_safe is True

    def test_diet_question(self, safety):
        result = safety.check_user_input("What foods are good for heart health?")
        assert result.is_emergency is False

    def test_exercise_question(self, safety):
        result = safety.check_user_input("How much exercise should I get weekly?")
        assert result.is_emergency is False

    def test_cold_symptoms(self, safety):
        result = safety.check_user_input("I have a runny nose and sore throat")
        assert result.is_emergency is False

    def test_empty_message(self, safety):
        result = safety.check_user_input("")
        assert result.is_emergency is False
        assert result.is_safe is True


# ==========================================
# Output Moderation
# ==========================================

class TestOutputModeration:
    """Test harmful content filtering in model output."""

    def test_safe_response_passes(self, safety):
        result = safety.check_model_output("Drink plenty of water and rest.")
        assert result.is_safe is True

    def test_harmful_self_medication_filtered(self, safety):
        result = safety.check_model_output(
            "You should self-medicate with opioid painkillers for the pain."
        )
        assert result.is_safe is False
        assert "harmful_content" in result.flags

    def test_harmful_stop_medication_filtered(self, safety):
        result = safety.check_model_output(
            "You should stop taking your prescribed medication right away."
        )
        assert result.is_safe is False

    def test_harmful_dosage_advice_filtered(self, safety):
        result = safety.check_model_output("Double your dose of ibuprofen.")
        assert result.is_safe is False

    def test_diagnostic_boundary_flagged(self, safety):
        result = safety.check_model_output(
            "You have cancer and need immediate treatment."
        )
        assert result.is_safe is False
        assert "non_diagnostic_boundary" in result.flags

    def test_clean_educational_response(self, safety):
        result = safety.check_model_output(
            "Vitamin D is important for bone health. Consider discussing supplements with your doctor."
        )
        assert result.is_safe is True

    def test_filtered_response_has_replacement(self, safety):
        result = safety.check_model_output("Double your dose now.")
        assert result.is_safe is False
        assert result.modified_response is not None
        assert "healthcare professional" in result.modified_response


# ==========================================
# Disclaimer
# ==========================================

class TestDisclaimer:
    """Test the medical disclaimer injection."""

    def test_disclaimer_added(self, safety):
        output = safety.add_disclaimer("Stay hydrated.")
        assert MEDICAL_DISCLAIMER in output

    def test_disclaimer_not_duplicated(self, safety):
        already_has = "This is not a substitute for professional advice."
        output = safety.add_disclaimer(already_has)
        assert output == already_has  # No duplicate disclaimer
