"""
Symptom Checker API — Analyze symptoms and predict possible conditions.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.services.symptom_checker import symptom_checker
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/symptoms", tags=["Symptom Checker"])


class SymptomCheckRequest(BaseModel):
    symptoms: list[str]


@router.post("/check")
async def check_symptoms(
    req: SymptomCheckRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """
    Analyze symptoms and predict possible conditions.
    Returns predictions with confidence scores and severity.
    """
    result = symptom_checker.check_symptoms(req.symptoms)

    # Log to analytics
    analytics_service.log_symptom_check(
        db=db,
        symptoms=result.input_symptoms,
        predicted_conditions=[
            {"condition": p.condition, "confidence": p.confidence}
            for p in result.predictions
        ],
        confidence_scores=[p.confidence for p in result.predictions],
        severity=result.severity,
        emergency_flagged=result.emergency,
        user_id=user.get("user_id") if user else None,
    )

    # Build a human-readable response summary
    response_lines = []
    if result.emergency:
        response_lines.append(f"⚠️ {result.emergency_message}")
    response_lines.append(f"Based on your symptoms ({', '.join(result.input_symptoms)}), here are possible conditions:")
    for p in result.predictions:
        response_lines.append(
            f"• {p.condition} ({p.confidence:.0%} confidence, {p.severity} severity) — {p.description}"
        )
    if result.disclaimer:
        response_lines.append(f"\n{result.disclaimer}")

    return {
        "response": "\n".join(response_lines),
        "emergency": result.emergency,
        "emergency_message": result.emergency_message,
        "severity": result.severity,
        "predictions": [
            {
                "condition": p.condition,
                "confidence": p.confidence,
                "severity": p.severity,
                "description": p.description,
                "matching_symptoms": p.matching_symptoms,
                "recommendations": p.recommendations,
            }
            for p in result.predictions
        ],
        "input_symptoms": result.input_symptoms,
        "disclaimer": result.disclaimer,
    }


@router.get("/list")
async def list_symptoms():
    """Get list of all recognized symptoms for autocomplete."""
    all_symptoms = set()
    from app.services.symptom_checker import SYMPTOM_CONDITIONS_DB
    for condition in SYMPTOM_CONDITIONS_DB.values():
        all_symptoms.update(condition["symptoms"])
    return {"symptoms": sorted(all_symptoms)}
