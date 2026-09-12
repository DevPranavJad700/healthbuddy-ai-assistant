"""Integration stubs for EHR/identity/telehealth workflows."""

from fastapi import APIRouter, Depends

from app.core.security import get_current_clinician_required

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("/fhir/export-care-summary")
async def export_fhir_care_summary(user: dict = Depends(get_current_clinician_required)):
    return {
        "enabled": False,
        "message": "FHIR export adapter is scaffolded. Configure integration provider and mapping profile.",
        "resource_types": ["Observation", "Condition", "CarePlan", "Encounter"],
    }


@router.get("/identity/oidc-status")
async def oidc_status(user: dict = Depends(get_current_clinician_required)):
    return {
        "enabled": False,
        "message": "OIDC/SAML enterprise SSO adapter not configured yet.",
    }


@router.post("/telehealth/handoff")
async def telehealth_handoff(user: dict = Depends(get_current_clinician_required)):
    return {
        "enabled": False,
        "message": "Telehealth handoff workflow scaffolded. Connect scheduling/telehealth provider.",
    }
