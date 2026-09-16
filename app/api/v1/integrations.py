"""Integration endpoints for EHR (HL7 FHIR R4), identity, and telehealth workflows."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, User, UserGoal, ChatLog, SymptomCheck
from app.core.security import get_current_user_required
from app.services.fhir_service import fhir_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])


def _build_user_fhir_bundle(db: Session, target_user_id: int) -> dict:
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Patient user not found")

    user_dict = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "age": user.age,
        "gender": user.gender,
        "medical_conditions": user.medical_conditions or [],
        "allergies": user.allergies or [],
        "preferred_language": user.preferred_language or "en",
    }

    goals_db = db.query(UserGoal).filter(UserGoal.user_id == target_user_id).all()
    goals_list = [
        {
            "id": g.id,
            "goal": g.goal,
            "priority": g.priority,
            "is_active": g.is_active,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in goals_db
    ]

    checks_db = (
        db.query(SymptomCheck)
        .filter(SymptomCheck.user_id == target_user_id)
        .order_by(SymptomCheck.created_at.desc())
        .limit(25)
        .all()
    )
    symptom_list = [
        {
            "id": sc.id,
            "symptoms_checked": sc.symptoms_checked,
            "prediction": sc.prediction,
            "created_at": sc.created_at.isoformat() if sc.created_at else None,
        }
        for sc in checks_db
    ]

    chats_db = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == target_user_id)
        .order_by(ChatLog.created_at.desc())
        .limit(20)
        .all()
    )
    chat_list = [
        {
            "id": c.id,
            "session_id": c.session_id,
            "question": c.question,
            "response": c.response,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chats_db
    ]

    return fhir_service.generate_patient_bundle(
        user_data=user_dict,
        goals=goals_list,
        symptom_checks=symptom_list,
        chat_logs=chat_list,
    )


@router.get("/fhir/export-care-summary", summary="Export HL7 FHIR R4 Bundle for EHR")
async def export_fhir_care_summary(
    download: bool = Query(default=False, description="Whether to prompt download as JSON file"),
    user_id: Optional[int] = Query(default=None, description="Admin/Clinician override to export specific user"),
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """
    Export patient clinical history as a standard HL7 FHIR Release 4 Bundle.
    Compatible with Epic Systems, Oracle Cerner, and AthenaHealth patient portals.
    """
    is_clinician = user.get("role") in {"admin", "clinician"}
    current_uid = int(user["user_id"])
    target_uid = user_id if (user_id is not None and is_clinician) else current_uid

    bundle = _build_user_fhir_bundle(db, target_uid)

    audit_service.log(
        action="integrations.fhir_export",
        status="success",
        user_id=current_uid,
        details={"target_user_id": target_uid, "resource_count": bundle.get("total", 0)},
    )

    if download:
        return JSONResponse(
            content=bundle,
            media_type="application/fhir+json",
            headers={
                "Content-Disposition": f'attachment; filename="healthbuddy-fhir-r4-patient-{target_uid}.json"',
            },
        )

    return bundle


@router.get("/fhir/patient-bundle", summary="Direct FHIR R4 Patient Bundle Resource")
async def get_patient_fhir_bundle(
    user: dict = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Direct API endpoint for EHRs to retrieve the patient's FHIR R4 Bundle."""
    current_uid = int(user["user_id"])
    return _build_user_fhir_bundle(db, current_uid)


@router.get("/identity/oidc-status")
async def oidc_status(user: dict = Depends(get_current_user_required)):
    return {
        "enabled": False,
        "message": "OIDC/SAML enterprise SSO adapter scaffolded. Ready for hospital IdP linkage.",
    }


@router.post("/telehealth/handoff")
async def telehealth_handoff(user: dict = Depends(get_current_user_required)):
    return {
        "enabled": False,
        "message": "Telehealth handoff workflow scaffolded. Ready for scheduling provider linkage.",
    }
