"""
HL7 FHIR R4 Interoperability Service.
Generates compliant HL7 FHIR Release 4 JSON bundles for electronic health record (EHR)
interoperability with Epic Systems, Oracle Cerner, AthenaHealth, and hospital patient portals.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from typing import Any, Optional


class FHIRService:
    """Encapsulates transformations from HealthBuddy clinical state into HL7 FHIR R4 resources."""

    @staticmethod
    def _iso_date(dt: Optional[datetime]) -> str:
        if dt is None:
            return datetime.now(UTC).isoformat()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC).isoformat()
        return dt.isoformat()

    @classmethod
    def generate_patient_bundle(
        cls,
        user_data: dict[str, Any],
        goals: list[dict[str, Any]] | None = None,
        symptom_checks: list[dict[str, Any]] | None = None,
        chat_logs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Produce a complete HL7 FHIR R4 Bundle (type: 'document' or 'collection')
        containing Patient, Condition, AllergyIntolerance, Goal, Observation, and DocumentReference.
        """
        user_id = str(user_data.get("user_id") or user_data.get("id") or "0")
        patient_ref = f"Patient/hb-patient-{user_id}"
        full_name = user_data.get("full_name") or user_data.get("username") or "HealthBuddy Patient"
        now_iso = datetime.now(UTC).isoformat()
        bundle_id = str(uuid.uuid4())

        entries: list[dict[str, Any]] = []

        # -----------------------------------------------------------
        # 1. Patient Resource
        # -----------------------------------------------------------
        name_parts = full_name.split()
        given_names = name_parts[:-1] if len(name_parts) > 1 else [full_name]
        family_name = name_parts[-1] if len(name_parts) > 1 else ""

        gender_raw = str(user_data.get("gender") or "").strip().lower()
        gender_fhir = "unknown"
        if gender_raw in {"male", "m"}:
            gender_fhir = "male"
        elif gender_raw in {"female", "f"}:
            gender_fhir = "female"
        elif gender_raw in {"other", "non-binary"}:
            gender_fhir = "other"

        age = user_data.get("age")
        birth_date = None
        if age and isinstance(age, (int, float)) and 0 < age < 125:
            birth_year = datetime.now(UTC).year - int(age)
            birth_date = f"{birth_year}-01-01"

        patient_resource: dict[str, Any] = {
            "resourceType": "Patient",
            "id": f"hb-patient-{user_id}",
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"],
                "lastUpdated": now_iso,
            },
            "identifier": [
                {
                    "system": "urn:healthbuddy:patient:id",
                    "value": user_id,
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "text": full_name,
                    "family": family_name,
                    "given": given_names,
                }
            ],
            "gender": gender_fhir,
        }
        if birth_date:
            patient_resource["birthDate"] = birth_date

        preferred_lang = user_data.get("preferred_language") or "en"
        patient_resource["communication"] = [
            {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": preferred_lang,
                            "display": preferred_lang.upper(),
                        }
                    ],
                    "text": preferred_lang,
                },
                "preferred": True,
            }
        ]

        entries.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": patient_resource,
        })

        # -----------------------------------------------------------
        # 2. Condition Resources (Active Problem List)
        # -----------------------------------------------------------
        conditions = user_data.get("medical_conditions") or []
        for idx, cond_text in enumerate(conditions):
            cond_str = str(cond_text).strip()
            if not cond_str:
                continue
            cond_resource = {
                "resourceType": "Condition",
                "id": f"hb-cond-{user_id}-{idx + 1}",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                            "display": "Active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "confirmed",
                            "display": "Confirmed",
                        }
                    ]
                },
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                "code": "problem-list-item",
                                "display": "Problem List Item",
                            }
                        ]
                    }
                ],
                "code": {
                    "text": cond_str,
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "display": cond_str,
                        }
                    ],
                },
                "subject": {"reference": patient_ref, "display": full_name},
                "recordedDate": now_iso,
            }
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": cond_resource,
            })

        # -----------------------------------------------------------
        # 3. AllergyIntolerance Resources
        # -----------------------------------------------------------
        allergies = user_data.get("allergies") or []
        for idx, allergy_text in enumerate(allergies):
            alg_str = str(allergy_text).strip()
            if not alg_str:
                continue
            alg_lower = alg_str.lower()
            category = "medication" if any(k in alg_lower for k in ["penicillin", "aspirin", "sulfa", "antibiotic", "drug"]) else (
                "food" if any(k in alg_lower for k in ["peanut", "nut", "dairy", "shellfish", "egg", "gluten", "milk"]) else "environment"
            )
            allergy_resource = {
                "resourceType": "AllergyIntolerance",
                "id": f"hb-allergy-{user_id}-{idx + 1}",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                            "display": "Active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            "code": "confirmed",
                            "display": "Confirmed",
                        }
                    ]
                },
                "type": "allergy",
                "category": [category],
                "criticality": "high",
                "code": {"text": alg_str},
                "patient": {"reference": patient_ref, "display": full_name},
                "recordedDate": now_iso,
            }
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": allergy_resource,
            })

        # -----------------------------------------------------------
        # 4. Goal Resources (Health & Wellness Objectives)
        # -----------------------------------------------------------
        goals = goals or []
        for g in goals:
            goal_text = g.get("goal") or ""
            if not goal_text:
                continue
            prio = str(g.get("priority") or "medium").lower()
            is_active = g.get("is_active", True)
            goal_resource = {
                "resourceType": "Goal",
                "id": f"hb-goal-{g.get('id', uuid.uuid4())}",
                "lifecycleStatus": "active" if is_active else "completed",
                "description": {"text": goal_text},
                "priority": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/goal-priority",
                            "code": prio,
                            "display": prio.capitalize(),
                        }
                    ]
                },
                "subject": {"reference": patient_ref, "display": full_name},
                "startDate": g.get("created_at") or now_iso,
            }
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": goal_resource,
            })

        # -----------------------------------------------------------
        # 5. Observation Resources (Symptom Assessments)
        # -----------------------------------------------------------
        symptom_checks = symptom_checks or []
        for sc in symptom_checks:
            pred = sc.get("prediction") or "Symptom Review"
            symp_list = sc.get("symptoms_checked") or []
            if isinstance(symp_list, list):
                symp_str = ", ".join(str(s) for s in symp_list)
            else:
                symp_str = str(symp_list)

            obs_resource = {
                "resourceType": "Observation",
                "id": f"hb-obs-{sc.get('id', uuid.uuid4())}",
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "exam",
                                "display": "Exam",
                            }
                        ]
                    }
                ],
                "code": {
                    "text": f"Symptom Checker Evaluation: {pred}",
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8684-3",
                            "display": "History of Present Illness",
                        }
                    ],
                },
                "subject": {"reference": patient_ref, "display": full_name},
                "effectiveDateTime": sc.get("created_at") or now_iso,
                "valueString": f"Selected Symptoms: {symp_str}. Indicated condition pattern: {pred}.",
            }
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": obs_resource,
            })

        # -----------------------------------------------------------
        # 6. DocumentReference Resources (Clinical Consultation Summaries)
        # -----------------------------------------------------------
        chat_logs = chat_logs or []
        # Group or capture latest consultations up to 20
        for chat in chat_logs[:20]:
            question = chat.get("question") or ""
            response = chat.get("response") or ""
            if not question and not response:
                continue

            session_id = chat.get("session_id") or "session"
            note_content = (
                f"# HealthBuddy AI Clinical Consultation Note\n"
                f"**Date:** {chat.get('created_at') or now_iso}\n"
                f"**Session:** {session_id}\n\n"
                f"### Patient Query:\n{question}\n\n"
                f"### Clinical AI Guidance:\n{response}\n\n"
                f"---\n*Recorded by HealthBuddy AI Clinical Assistant. For clinical triage record only.*"
            )
            b64_note = base64.b64encode(note_content.encode("utf-8")).decode("ascii")

            doc_resource = {
                "resourceType": "DocumentReference",
                "id": f"hb-doc-{chat.get('id', uuid.uuid4())}",
                "status": "current",
                "docStatus": "final",
                "type": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "11488-4",
                            "display": "Consultation note",
                        }
                    ]
                },
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/document-classcodes",
                                "code": "clinical-note",
                                "display": "Clinical Note",
                            }
                        ]
                    }
                ],
                "subject": {"reference": patient_ref, "display": full_name},
                "date": chat.get("created_at") or now_iso,
                "description": f"HealthBuddy AI Consultation Note - Session {session_id}",
                "content": [
                    {
                        "attachment": {
                            "contentType": "text/markdown",
                            "language": preferred_lang,
                            "title": f"Consultation Note ({session_id})",
                            "data": b64_note,
                        }
                    }
                ],
            }
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": doc_resource,
            })

        # -----------------------------------------------------------
        # Complete FHIR R4 Bundle
        # -----------------------------------------------------------
        bundle: dict[str, Any] = {
            "resourceType": "Bundle",
            "id": f"healthbuddy-fhir-r4-{bundle_id}",
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
                "lastUpdated": now_iso,
            },
            "identifier": {
                "system": "urn:healthbuddy:bundle",
                "value": bundle_id,
            },
            "type": "collection",
            "timestamp": now_iso,
            "total": len(entries),
            "entry": entries,
        }

        return bundle


fhir_service = FHIRService()
