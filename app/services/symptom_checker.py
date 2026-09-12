"""
Symptom Checker Module — Hybrid rule-based + ML approach.

Features:
- Maps user symptoms to possible medical conditions
- Provides confidence scores for each prediction
- Severity assessment (low/medium/high/emergency)
- Emergency detection for critical symptoms
- Clear medical disclaimers
"""

from dataclasses import dataclass
from app.core.logging_config import logger


# ==========================================
# Symptom-Condition Knowledge Base
# ==========================================

SYMPTOM_CONDITIONS_DB = {
    # Condition: {symptoms, severity_base, description, recommendations}
    "Common Cold": {
        "symptoms": ["runny nose", "sneezing", "sore throat", "cough", "congestion",
                      "mild headache", "watery eyes", "low fever"],
        "severity_base": "low",
        "description": "A viral infection of the upper respiratory tract. Usually resolves in 7-10 days.",
        "recommendations": [
            "Rest and stay hydrated",
            "Over-the-counter cold medications for symptom relief",
            "Warm fluids like tea with honey",
            "Consult a doctor if symptoms persist beyond 10 days"
        ]
    },
    "Influenza (Flu)": {
        "symptoms": ["high fever", "severe body aches", "fatigue", "chills", "headache",
                      "cough", "sore throat", "congestion"],
        "severity_base": "medium",
        "description": "A more severe viral respiratory illness than the common cold.",
        "recommendations": [
            "Rest and stay hydrated",
            "Antiviral medications (if within 48 hours of symptom onset)",
            "Over-the-counter fever reducers",
            "Seek medical attention if symptoms worsen"
        ]
    },
    "COVID-19": {
        "symptoms": ["fever", "cough", "shortness of breath", "fatigue", "body aches",
                      "loss of taste", "loss of smell", "sore throat", "headache", "diarrhea"],
        "severity_base": "medium",
        "description": "Respiratory illness caused by the SARS-CoV-2 virus.",
        "recommendations": [
            "Get tested for COVID-19",
            "Isolate from others",
            "Monitor oxygen levels if possible",
            "Seek emergency care if difficulty breathing"
        ]
    },
    "Migraine": {
        "symptoms": ["severe headache", "headache", "nausea", "sensitivity to light",
                      "sensitivity to sound", "vision changes", "throbbing pain", "vomiting"],
        "severity_base": "medium",
        "description": "A neurological condition causing intense, debilitating headaches.",
        "recommendations": [
            "Rest in a dark, quiet room",
            "Over-the-counter pain relievers (ibuprofen, acetaminophen)",
            "Stay hydrated",
            "Consult a doctor for recurring migraines"
        ]
    },
    "Gastroenteritis": {
        "symptoms": ["nausea", "vomiting", "diarrhea", "stomach cramps", "abdominal pain",
                      "low fever", "loss of appetite", "dehydration"],
        "severity_base": "medium",
        "description": "Inflammation of the stomach and intestines, usually from viral or bacterial infection.",
        "recommendations": [
            "Stay hydrated with clear fluids and electrolytes",
            "Follow the BRAT diet (Bananas, Rice, Applesauce, Toast)",
            "Rest and avoid solid foods until vomiting stops",
            "Seek medical attention if symptoms last more than 3 days"
        ]
    },
    "Allergic Reaction": {
        "symptoms": ["hives", "itching", "swelling", "sneezing", "watery eyes",
                      "runny nose", "rash", "skin redness"],
        "severity_base": "medium",
        "description": "Immune system response to an allergen (food, pollen, medication, etc.).",
        "recommendations": [
            "Identify and avoid the allergen",
            "Take antihistamines (e.g., cetirizine, loratadine)",
            "Apply cold compresses to affected areas",
            "Seek emergency care if throat swelling or difficulty breathing"
        ]
    },
    "Urinary Tract Infection": {
        "symptoms": ["painful urination", "frequent urination", "urgency to urinate",
                      "cloudy urine", "blood in urine", "lower abdominal pain", "pelvic pain"],
        "severity_base": "medium",
        "description": "Bacterial infection in the urinary system (bladder, urethra, or kidneys).",
        "recommendations": [
            "Drink plenty of water",
            "See a doctor for antibiotics",
            "Avoid caffeine and alcohol",
            "Seek immediate care if fever, back pain, or blood in urine"
        ]
    },
    "Anxiety Disorder": {
        "symptoms": ["excessive worry", "restlessness", "rapid heartbeat", "sweating",
                      "trembling", "difficulty concentrating", "insomnia", "muscle tension",
                      "panic attacks", "shortness of breath"],
        "severity_base": "medium",
        "description": "A mental health condition characterized by persistent, excessive worry.",
        "recommendations": [
            "Practice deep breathing and relaxation techniques",
            "Regular physical exercise",
            "Limit caffeine and alcohol",
            "Consider therapy (CBT) or consult a mental health professional"
        ]
    },
    "Hypertension (High Blood Pressure)": {
        "symptoms": ["headache", "dizziness", "blurred vision", "chest pain",
                      "shortness of breath", "nosebleed"],
        "severity_base": "high",
        "description": "Persistently elevated blood pressure that can damage organs over time.",
        "recommendations": [
            "Monitor blood pressure regularly",
            "Reduce sodium intake",
            "Exercise regularly and maintain healthy weight",
            "Take prescribed medications; see a doctor immediately if BP is very high"
        ]
    },
    "Diabetes (Type 2)": {
        "symptoms": ["frequent urination", "excessive thirst", "unexplained weight loss",
                      "fatigue", "blurred vision", "slow healing wounds", "tingling in hands",
                      "tingling in feet", "increased hunger"],
        "severity_base": "high",
        "description": "A metabolic condition where the body cannot properly regulate blood sugar.",
        "recommendations": [
            "Get blood sugar tested (fasting glucose, HbA1c)",
            "Maintain a healthy diet and exercise routine",
            "Monitor blood sugar levels regularly",
            "Consult an endocrinologist for proper management"
        ]
    },
    "Heart Attack": {
        "symptoms": ["chest pain", "chest pressure", "arm pain", "jaw pain", "back pain",
                      "shortness of breath", "nausea", "cold sweats", "lightheadedness"],
        "severity_base": "emergency",
        "description": "A life-threatening condition where blood flow to the heart is blocked.",
        "recommendations": [
            "CALL EMERGENCY SERVICES (911/112) IMMEDIATELY",
            "Chew an aspirin if available and not allergic",
            "Sit or lie down in a comfortable position",
            "Do NOT drive yourself to the hospital"
        ]
    },
    "Stroke": {
        "symptoms": ["face drooping", "arm weakness", "speech difficulty", "sudden confusion",
                      "severe headache", "vision problems", "difficulty walking", "numbness"],
        "severity_base": "emergency",
        "description": "A life-threatening condition where blood supply to the brain is interrupted.",
        "recommendations": [
            "CALL EMERGENCY SERVICES (911/112) IMMEDIATELY",
            "Note the time symptoms started (critical for treatment)",
            "Do NOT give food or water",
            "Keep the person lying down with head slightly elevated"
        ]
    },
    "Severe Allergic Reaction (Anaphylaxis)": {
        "symptoms": ["throat swelling", "difficulty breathing", "severe swelling", "rapid pulse",
                      "dizziness", "loss of consciousness", "severe hives", "nausea", "vomiting"],
        "severity_base": "emergency",
        "description": "A severe, potentially life-threatening allergic reaction.",
        "recommendations": [
            "CALL EMERGENCY SERVICES (911/112) IMMEDIATELY",
            "Use an epinephrine auto-injector (EpiPen) if available",
            "Lie flat with legs elevated (unless difficulty breathing)",
            "Do NOT wait to see if symptoms improve"
        ]
    },
    "Asthma Attack": {
        "symptoms": ["wheezing", "shortness of breath", "chest tightness", "cough",
                      "difficulty breathing", "rapid breathing"],
        "severity_base": "high",
        "description": "A condition where airways narrow and swell, making breathing difficult.",
        "recommendations": [
            "Use rescue inhaler (albuterol) immediately",
            "Sit upright and try to stay calm",
            "Remove yourself from triggers (smoke, allergens)",
            "Call emergency services if inhaler doesn't help within 15 minutes"
        ]
    },
    "Food Poisoning": {
        "symptoms": ["nausea", "vomiting", "diarrhea", "stomach cramps", "fever",
                      "weakness", "loss of appetite"],
        "severity_base": "medium",
        "description": "Illness caused by consuming contaminated food or beverages.",
        "recommendations": [
            "Stay hydrated with small sips of water or electrolyte drinks",
            "Rest and avoid solid foods initially",
            "Gradually reintroduce bland foods",
            "Seek medical attention if severe dehydration, bloody stool, or high fever"
        ]
    },
}

# Emergency symptoms that always trigger emergency severity
EMERGENCY_SYMPTOMS = {
    "chest pain", "chest pressure", "difficulty breathing", "shortness of breath",
    "loss of consciousness", "severe bleeding", "throat swelling", "face drooping",
    "arm weakness", "speech difficulty", "sudden confusion", "seizure",
    "suicidal thoughts", "self harm", "overdose", "severe allergic reaction",
    "severe chest pain", "sudden severe headache", "coughing blood",
    "inability to breathe", "choking",
}


@dataclass
class ConditionPrediction:
    """A predicted condition with confidence and metadata."""
    condition: str
    confidence: float
    severity: str
    description: str
    matching_symptoms: list[str]
    recommendations: list[str]


@dataclass
class SymptomCheckResult:
    """Result of a symptom check."""
    predictions: list[ConditionPrediction]
    severity: str  # overall severity
    emergency: bool
    emergency_message: str | None
    disclaimer: str
    input_symptoms: list[str]


class SymptomChecker:
    """
    Hybrid rule-based + similarity symptom checker.
    Maps user symptoms to possible conditions with confidence scores.
    """

    DISCLAIMER = (
        "IMPORTANT DISCLAIMER: This symptom checker provides general health information only. "
        "It is NOT a medical diagnosis. The results are based on pattern matching and should NOT "
        "be used as a substitute for professional medical advice, diagnosis, or treatment. "
        "Always consult a qualified healthcare provider for medical concerns."
    )

    def check_symptoms(self, user_symptoms: list[str]) -> SymptomCheckResult:
        """
        Analyze user symptoms and predict possible conditions.

        Args:
            user_symptoms: List of symptom strings from the user.

        Returns:
            SymptomCheckResult with predictions, severity, and recommendations.
        """
        # Normalize symptoms
        normalized = [s.lower().strip() for s in user_symptoms if s.strip()]

        if not normalized:
            return SymptomCheckResult(
                predictions=[],
                severity="low",
                emergency=False,
                emergency_message=None,
                disclaimer=self.DISCLAIMER,
                input_symptoms=[],
            )

        # Check for emergency symptoms first
        emergency = False
        emergency_msg = None
        for symptom in normalized:
            for emerg in EMERGENCY_SYMPTOMS:
                if emerg in symptom or symptom in emerg:
                    emergency = True
                    emergency_msg = (
                        "WARNING: You reported symptoms that may indicate a medical emergency. "
                        "Please call emergency services (911/112) IMMEDIATELY or go to the nearest "
                        "emergency room. Do NOT wait."
                    )
                    break
            if emergency:
                break

        # Match against conditions
        predictions = []
        for condition_name, condition_data in SYMPTOM_CONDITIONS_DB.items():
            matching = self._match_symptoms(normalized, condition_data["symptoms"])
            if matching:
                # Calculate confidence based on symptom overlap
                confidence = len(matching) / len(condition_data["symptoms"])
                # Bonus for matching more user symptoms
                user_coverage = len(matching) / len(normalized)
                confidence = min(0.95, (confidence * 0.6 + user_coverage * 0.4))

                predictions.append(ConditionPrediction(
                    condition=condition_name,
                    confidence=round(confidence, 2),
                    severity=condition_data["severity_base"],
                    description=condition_data["description"],
                    matching_symptoms=matching,
                    recommendations=condition_data["recommendations"],
                ))

        # Sort by confidence (descending)
        predictions.sort(key=lambda x: x.confidence, reverse=True)

        # Take top 5
        predictions = predictions[:5]

        # Determine overall severity
        overall_severity = "low"
        if emergency:
            overall_severity = "emergency"
        elif predictions:
            severity_order = {"low": 0, "medium": 1, "high": 2, "emergency": 3}
            max_severity = max(predictions[:3], key=lambda x: severity_order.get(x.severity, 0))
            overall_severity = max_severity.severity

        logger.info(
            f"Symptom check: {len(normalized)} symptoms -> "
            f"{len(predictions)} conditions, severity={overall_severity}"
        )

        return SymptomCheckResult(
            predictions=predictions,
            severity=overall_severity,
            emergency=emergency,
            emergency_message=emergency_msg,
            disclaimer=self.DISCLAIMER,
            input_symptoms=normalized,
        )

    def _match_symptoms(self, user_symptoms: list[str], condition_symptoms: list[str]) -> list[str]:
        """Find matching symptoms using fuzzy string matching."""
        matches = []
        for user_sym in user_symptoms:
            for cond_sym in condition_symptoms:
                # Exact match or substring match
                if (user_sym == cond_sym or
                    user_sym in cond_sym or
                    cond_sym in user_sym or
                    self._word_overlap(user_sym, cond_sym) >= 0.5):
                    matches.append(cond_sym)
                    break
        return list(set(matches))

    @staticmethod
    def _word_overlap(a: str, b: str) -> float:
        """Calculate word-level overlap between two strings."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        overlap = words_a & words_b
        return len(overlap) / min(len(words_a), len(words_b))


# Singleton
symptom_checker = SymptomChecker()
