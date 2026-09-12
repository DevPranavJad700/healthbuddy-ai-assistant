"""
Unit tests for the Symptom Checker module.
"""

import pytest
from app.services.symptom_checker import symptom_checker


class TestSymptomChecker:
    """Tests for the symptom checker service."""

    def test_cold_symptoms(self):
        result = symptom_checker.check_symptoms(["runny nose", "sneezing", "sore throat"])
        assert len(result.predictions) > 0
        conditions = [p.condition for p in result.predictions]
        assert "Common Cold" in conditions

    def test_flu_symptoms(self):
        result = symptom_checker.check_symptoms(["high fever", "body aches", "fatigue", "chills"])
        assert len(result.predictions) > 0
        conditions = [p.condition for p in result.predictions]
        assert "Influenza (Flu)" in conditions

    def test_emergency_chest_pain(self):
        result = symptom_checker.check_symptoms(["chest pain", "arm pain", "shortness of breath"])
        assert result.emergency is True
        assert result.emergency_message is not None
        assert result.severity == "emergency"

    def test_emergency_suicide(self):
        result = symptom_checker.check_symptoms(["suicidal thoughts"])
        assert result.emergency is True

    def test_confidence_scores_are_valid(self):
        result = symptom_checker.check_symptoms(["headache", "nausea", "fever"])
        for p in result.predictions:
            assert 0 <= p.confidence <= 1.0

    def test_predictions_sorted_by_confidence(self):
        result = symptom_checker.check_symptoms(["fever", "cough", "fatigue"])
        if len(result.predictions) > 1:
            for i in range(len(result.predictions) - 1):
                assert result.predictions[i].confidence >= result.predictions[i + 1].confidence

    def test_empty_symptoms(self):
        result = symptom_checker.check_symptoms([])
        assert len(result.predictions) == 0
        assert result.severity == "low"
        assert result.emergency is False

    def test_disclaimer_always_present(self):
        result = symptom_checker.check_symptoms(["headache"])
        assert "DISCLAIMER" in result.disclaimer.upper()

    def test_recommendations_provided(self):
        result = symptom_checker.check_symptoms(["runny nose", "sneezing", "cough"])
        for p in result.predictions:
            assert len(p.recommendations) > 0

    def test_max_5_predictions(self):
        result = symptom_checker.check_symptoms([
            "fever", "cough", "headache", "fatigue", "nausea",
            "diarrhea", "sore throat", "dizziness"
        ])
        assert len(result.predictions) <= 5


class TestSafetyLayer:
    """Tests for the safety layer."""

    def test_cardiac_emergency_detection(self):
        from app.services.safety_layer import safety_layer
        result = safety_layer.check_user_input("I have severe chest pain")
        assert result.is_emergency is True
        assert result.emergency_type == "cardiac_emergency"

    def test_mental_health_crisis_detection(self):
        from app.services.safety_layer import safety_layer
        result = safety_layer.check_user_input("I want to kill myself")
        assert result.is_emergency is True
        assert result.emergency_type == "mental_health_crisis"

    def test_safe_input(self):
        from app.services.safety_layer import safety_layer
        result = safety_layer.check_user_input("What foods are good for heart health?")
        assert result.is_emergency is False
        assert result.is_safe is True

    def test_harmful_output_filtered(self):
        from app.services.safety_layer import safety_layer
        result = safety_layer.check_model_output("You should drink bleach to cure your illness")
        assert result.is_safe is False
        assert result.modified_response is not None

    def test_safe_output_passes(self):
        from app.services.safety_layer import safety_layer
        result = safety_layer.check_model_output("Eating vegetables is good for health.")
        assert result.is_safe is True

    def test_disclaimer_added(self):
        from app.services.safety_layer import safety_layer
        text = "Drink water daily."
        result = safety_layer.add_disclaimer(text)
        assert "not a substitute" in result.lower()
