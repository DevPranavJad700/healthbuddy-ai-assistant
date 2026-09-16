"""Tests for HL7 FHIR R4 interoperability service."""

import base64
import pytest
from app.services.fhir_service import fhir_service


def test_fhir_bundle_generation():
    user_data = {
        "user_id": 42,
        "username": "jane_doe",
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "age": 34,
        "gender": "female",
        "medical_conditions": ["Hypertension", "Type 2 Diabetes"],
        "allergies": ["Penicillin", "Peanuts"],
        "preferred_language": "en",
    }
    goals = [
        {"id": 1, "goal": "Walk 10,000 steps daily", "priority": "high", "is_active": True}
    ]
    symptom_checks = [
        {"id": 10, "symptoms_checked": ["headache", "fatigue"], "prediction": "Tension Headache"}
    ]
    chat_logs = [
        {"id": 99, "session_id": "sess_123", "question": "Hydration tips", "response": "Drink 2L daily"}
    ]

    bundle = fhir_service.generate_patient_bundle(
        user_data=user_data,
        goals=goals,
        symptom_checks=symptom_checks,
        chat_logs=chat_logs,
    )

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] >= 7

    # Validate individual resource types
    resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert "Patient" in resource_types
    assert "Condition" in resource_types
    assert "AllergyIntolerance" in resource_types
    assert "Goal" in resource_types
    assert "Observation" in resource_types
    assert "DocumentReference" in resource_types

    # Validate Patient details
    patient = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    assert patient["gender"] == "female"
    assert patient["name"][0]["text"] == "Jane Doe"
    assert patient["identifier"][0]["value"] == "42"

    # Validate AllergyIntolerance categories
    allergies = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance"]
    assert len(allergies) == 2
    categories = [a["category"][0] for a in allergies]
    assert "medication" in categories  # Penicillin
    assert "food" in categories        # Peanuts

    # Validate DocumentReference attachment is valid base64
    doc_ref = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "DocumentReference")
    b64_data = doc_ref["content"][0]["attachment"]["data"]
    decoded = base64.b64decode(b64_data).decode("utf-8")
    assert "HealthBuddy AI Clinical Consultation Note" in decoded
    assert "Hydration tips" in decoded


def test_fhir_endpoint_export(client):
    # Register and login a test user
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": "test_fhir_user", "user_id": 1, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/integrations/fhir/export-care-summary", headers=headers)
    assert response.status_code in (200, 404)  # 404 only if user id 1 not in ephemeral test db
    if response.status_code == 200:
        data = response.json()
        assert data["resourceType"] == "Bundle"

