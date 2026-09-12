"""
Medical Safety Layer — Emergency detection, harmful content filtering, and guardrails.

Features:
- Emergency keyword detection (chest pain, suicide, etc.)
- Harmful advice prevention
- Response moderation
- Mandatory disclaimers
"""

import re
from dataclasses import dataclass
from app.core.logging_config import logger


@dataclass
class SafetyCheckResult:
    """Result of a safety check on user input or model output."""
    is_safe: bool
    is_emergency: bool
    emergency_type: str | None
    warning_message: str | None
    modified_response: str | None
    flags: list[str]


# Emergency patterns — trigger immediate alert
EMERGENCY_PATTERNS = [
    {
        "pattern": r"\b(chest\s*pain|heart\s*attack|cardiac\s*arrest)\b",
        "type": "cardiac_emergency",
        "message": (
            "EMERGENCY ALERT: You may be experiencing a cardiac emergency.\n\n"
            "Please CALL EMERGENCY SERVICES (911/112) IMMEDIATELY.\n\n"
            "While waiting for help:\n"
            "- Sit or lie down in a comfortable position\n"
            "- Chew an aspirin if available and not allergic\n"
            "- Loosen any tight clothing\n"
            "- Do NOT drive yourself to the hospital"
        ),
    },
    {
        "pattern": r"\b(suicid|kill\s*myself|end\s*(my\s*life|it\s*all|everything)|want\s*to\s*die|self[\s-]*harm|hurt\s*myself|don'?t\s*want\s*to\s*live|no\s*reason\s*to\s*live|give\s*up\s*on\s*life)\b",
        "type": "mental_health_crisis",
        "message": (
            "CRISIS ALERT: If you or someone you know is in crisis, "
            "please reach out for help immediately.\n\n"
            "- National Suicide Prevention Lifeline: 988 (US)\n"
            "- Crisis Text Line: Text HOME to 741741\n"
            "- Vandrevala Foundation (India): 1860-2662-345\n"
            "- iCall (India): 9152987821\n\n"
            "You are not alone. Help is available 24/7."
        ),
    },
    {
        "pattern": r"\b(can'?t\s*breathe|choking|anaphyla|severe\s*allergic)\b",
        "type": "respiratory_emergency",
        "message": (
            "EMERGENCY ALERT: This may be a respiratory emergency.\n\n"
            "Please CALL EMERGENCY SERVICES (911/112) IMMEDIATELY.\n\n"
            "If someone is choking, perform the Heimlich maneuver.\n"
            "If allergic reaction, use an EpiPen if available."
        ),
    },
    {
        "pattern": r"\b(stroke|face\s*droop|slurred\s*speech|sudden\s*numbness)\b",
        "type": "stroke_emergency",
        "message": (
            "EMERGENCY ALERT: These symptoms may indicate a stroke.\n\n"
            "Remember FAST:\n"
            "- F: Face drooping\n"
            "- A: Arm weakness\n"
            "- S: Speech difficulty\n"
            "- T: Time to call emergency services (911/112)\n\n"
            "CALL EMERGENCY SERVICES IMMEDIATELY. Time is critical."
        ),
    },
    {
        "pattern": r"\b(overdose|poison|swallow\w*\s*(bleach|chemical|pill))\b",
        "type": "poisoning_emergency",
        "message": (
            "EMERGENCY ALERT: This may be a poisoning/overdose situation.\n\n"
            "CALL POISON CONTROL: 1-800-222-1222 (US)\n"
            "Or CALL EMERGENCY SERVICES (911/112) IMMEDIATELY.\n\n"
            "Do NOT induce vomiting unless instructed by medical professionals."
        ),
    },
    {
        "pattern": r"\b(severe\s*bleeding|won'?t\s*stop\s*bleeding|hemorrhag)\b",
        "type": "bleeding_emergency",
        "message": (
            "EMERGENCY ALERT: Severe bleeding requires immediate attention.\n\n"
            "CALL EMERGENCY SERVICES (911/112).\n\n"
            "While waiting:\n"
            "- Apply firm, direct pressure with a clean cloth\n"
            "- Elevate the injured area if possible\n"
            "- Do NOT remove the cloth; add more layers if needed"
        ),
    },
]

# Harmful content patterns — things the bot should NEVER recommend
HARMFUL_PATTERNS = [
    r"\b(inject|snort|smoke)\s*(bleach|detergent|cleaning)",
    r"\bdrink\s*bleach\b",
    r"\bself[\s-]*medicate\b.*\b(opioid|narcotic)\b",
    r"\bstop\s+taking\s+(your\s+)?(prescribed|medication)\b",
    r"\breplace\s*(doctor|medicine|treatment)\b.*\b(with|by)\b",
    r"\btake\s+\d+\s*(mg|ml|mcg|g)\b",
    r"\b(skip|ignore)\s*(your\s*)?(doctor|prescription|medication)\b",
    r"\bdouble\s*(your\s*)?dose\b",
    r"\b(share|use someone else's)\s*(prescription|medicine)\b",
]

NON_DIAGNOSTIC_BOUNDARY_PATTERNS = [
    r"\byou\s+have\s+(cancer|stroke|heart attack|diabetes|pneumonia)\b",
    r"\bi\s+diagnose\b",
    r"\bdefinitive\s+diagnosis\b",
    r"\bprescribe\b",
]

# Mandatory disclaimer for all medical responses
MEDICAL_DISCLAIMER = (
    "\n\n---\n"
    "*Disclaimer: This information is for educational purposes only and is not "
    "a substitute for professional medical advice, diagnosis, or treatment. "
    "Always consult a qualified healthcare provider.*"
)


class SafetyLayer:
    """
    Medical safety layer that checks user inputs and model outputs.
    Ensures the chatbot doesn't provide harmful advice and detects emergencies.
    """

    def check_user_input(self, message: str) -> SafetyCheckResult:
        """
        Check user input for emergency situations.

        Args:
            message: User's chat message.

        Returns:
            SafetyCheckResult with emergency detection info.
        """
        message_lower = message.lower()
        flags = []

        # Check emergency patterns
        for pattern_info in EMERGENCY_PATTERNS:
            if re.search(pattern_info["pattern"], message_lower, re.IGNORECASE):
                logger.warning(
                    f"EMERGENCY DETECTED: {pattern_info['type']} "
                    f"in message: '{message[:80]}...'"
                )
                return SafetyCheckResult(
                    is_safe=True,  # We still process it, but flag as emergency
                    is_emergency=True,
                    emergency_type=pattern_info["type"],
                    warning_message=pattern_info["message"],
                    modified_response=None,
                    flags=[f"emergency:{pattern_info['type']}"],
                )

        return SafetyCheckResult(
            is_safe=True,
            is_emergency=False,
            emergency_type=None,
            warning_message=None,
            modified_response=None,
            flags=flags,
        )

    def check_model_output(self, response: str) -> SafetyCheckResult:
        """
        Check model output for harmful content.

        Args:
            response: Model-generated response text.

        Returns:
            SafetyCheckResult with moderation info.
        """
        response_lower = response.lower()
        flags = []

        # Check for harmful patterns in output
        for pattern in HARMFUL_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                flags.append("harmful_content")
                logger.warning(f"HARMFUL CONTENT detected in model output")
                return SafetyCheckResult(
                    is_safe=False,
                    is_emergency=False,
                    emergency_type=None,
                    warning_message="Response contained potentially harmful content and was filtered.",
                    modified_response=(
                        "I apologize, but I cannot provide that specific advice as it could be "
                        "harmful. Please consult a qualified healthcare professional for safe "
                        "and personalized medical guidance."
                    ),
                    flags=flags,
                )

        for pattern in NON_DIAGNOSTIC_BOUNDARY_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                flags.append("non_diagnostic_boundary")
                logger.warning("NON-DIAGNOSTIC boundary violation detected in model output")
                return SafetyCheckResult(
                    is_safe=False,
                    is_emergency=False,
                    emergency_type=None,
                    warning_message="Response crossed non-diagnostic boundary and was rewritten.",
                    modified_response=(
                        "I can provide general health information, but I cannot diagnose conditions "
                        "or prescribe treatment. For diagnosis and personalized treatment, please "
                        "consult a qualified healthcare professional promptly."
                    ),
                    flags=flags,
                )

        return SafetyCheckResult(
            is_safe=True,
            is_emergency=False,
            emergency_type=None,
            warning_message=None,
            modified_response=None,
            flags=flags,
        )

    def add_disclaimer(self, response: str) -> str:
        """Add medical disclaimer to response if not already present."""
        if "not a substitute" not in response.lower():
            return response + MEDICAL_DISCLAIMER
        return response


# Singleton
safety_layer = SafetyLayer()
