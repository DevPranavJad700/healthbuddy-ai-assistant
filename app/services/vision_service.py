"""
Multimodal Medical Vision Service.
Analyzes patient-submitted medical images (dermatology/rashes, medication pill bottles, and lab test reports)
using Groq Llama 3.2 Vision, OpenAI GPT-4o, and clinical rule-based fallbacks with safety triage.
"""

from __future__ import annotations

import base64
import re
from typing import Any, AsyncGenerator

import httpx

from app.core.config import settings
from app.core.logging_config import logger

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}

CLINICAL_VISION_SYSTEM_PROMPT = """You are HealthBuddy AI's Senior Clinical Vision Specialist.
Your role is to carefully analyze medical imagery provided by patients (e.g., skin lesions/rashes, prescription medication labels, or laboratory test reports).

You must format your clinical assessment clearly with markdown headings, metric badges, and bullet points:

1. **Visual Findings & Key Observations**:
   - For Rashes/Skin: Describe lesion distribution, color (erythema), borders (regular/irregular), elevation, and texture.
   - For Medication Labels: Extract exact medication name, active strength/dosage, administration instructions, expiration, and black-box warnings.
   - For Lab Reports: Tabulate test name, measured value, reference range, and clinical flag status (NORMAL, HIGH, LOW).

2. **Clinical Interpretation & Differential Insights**:
   - Offer potential medical possibilities to discuss with a healthcare provider.
   - Emphasize that this is NOT a formal medical diagnosis.

3. **Red Flag Warnings & When to Seek Immediate Care**:
   - Highlight signs of severe complications (e.g., rapid spreading, high fever, blistering, breathing difficulty, extreme lab anomalies).

4. **Recommended Next Steps & Discussion Guide**:
   - Provide concrete questions for the patient to ask their doctor or pharmacist.

Maintain an empathetic, highly professional medical tone. Always emphasize safety first."""

DISCLAIMER_TEXT = (
    "\n\n> ⚠️ **Clinical Vision Advisory**: AI visual assessment is an assistive screening tool, "
    "not a definitive clinical diagnosis. Please present any new rashes, medication questions, "
    "or abnormal lab results to a qualified healthcare professional."
)


class VisionService:
    """Handles multimodal image validation, inference routing, and clinical safety wrappers."""

    @staticmethod
    def parse_image_data(image_data_uri: str) -> tuple[str, str, bytes]:
        """
        Parse base64 data URI (e.g. 'data:image/png;base64,...') or raw base64.
        Returns: (mime_type, clean_base64_str, raw_bytes)
        """
        mime_type = "image/jpeg"
        b64_str = image_data_uri.strip()

        if b64_str.startswith("data:"):
            match = re.match(r"^data:(image\/[a-zA-Z0-9.+_-]+);base64,(.+)$", b64_str, re.DOTALL)
            if match:
                mime_type = match.group(1).lower()
                b64_str = match.group(2)
            else:
                raise ValueError("Invalid image data URI format")

        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported image format '{mime_type}'. Supported: JPEG, PNG, WebP.")

        try:
            raw_bytes = base64.b64decode(b64_str)
        except Exception as exc:
            raise ValueError(f"Failed to decode base64 image data: {exc}")

        if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image exceeds maximum permitted size of 5 MB ({len(raw_bytes) / 1024 / 1024:.1f} MB).")

        return mime_type, b64_str, raw_bytes

    @classmethod
    async def analyze_medical_image(
        cls,
        image_data: str,
        user_query: str = "",
        image_type: str = "general",
    ) -> str:
        """
        Orchestrates vision model execution across Groq, OpenAI, and heuristic fallbacks.
        """
        mime_type, b64_clean, raw_bytes = cls.parse_image_data(image_data)
        query = (user_query or "").strip() or "Please analyze this medical image, identify key clinical details, and provide guidance."

        # 1. Try Groq Multimodal Vision (Llama 3.2 Vision)
        if settings.groq_api_key:
            try:
                result = await cls._query_groq_vision(mime_type, b64_clean, query, image_type)
                if result:
                    return result + DISCLAIMER_TEXT
            except Exception as e:
                logger.warning(f"Groq vision inference failed ({e}); checking secondary providers...")

        # 2. Try OpenAI Vision (GPT-4o / GPT-4o-mini)
        if settings.openai_api_key:
            try:
                result = await cls._query_openai_vision(mime_type, b64_clean, query, image_type)
                if result:
                    return result + DISCLAIMER_TEXT
            except Exception as e:
                logger.warning(f"OpenAI vision inference failed ({e}); falling back to clinical rule engine...")

        # 3. Deterministic Heuristic Clinical Fallback
        return cls._heuristic_clinical_analysis(raw_bytes, query, image_type) + DISCLAIMER_TEXT

    @classmethod
    async def stream_medical_image_analysis(
        cls,
        image_data: str,
        user_query: str = "",
        image_type: str = "general",
    ) -> AsyncGenerator[str, None]:
        """Stream chunks of the vision analysis."""
        full_text = await cls.analyze_medical_image(image_data, user_query, image_type)
        # Yield in realistic clinical streaming increments
        words = full_text.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size]) + " "
            yield chunk

    @classmethod
    async def _query_groq_vision(cls, mime_type: str, b64_str: str, query: str, image_type: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        type_hint = f" Image focus context: {image_type.upper()}." if image_type != "general" else ""
        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {"role": "system", "content": CLINICAL_VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{query}{type_hint}"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_str}"},
                        },
                    ],
                },
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            raise RuntimeError(f"Groq returned HTTP {resp.status_code}: {resp.text}")

    @classmethod
    async def _query_openai_vision(cls, mime_type: str, b64_str: str, query: str, image_type: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": CLINICAL_VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_str}"},
                        },
                    ],
                },
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            raise RuntimeError(f"OpenAI returned HTTP {resp.status_code}: {resp.text}")

    @classmethod
    def _heuristic_clinical_analysis(cls, raw_bytes: bytes, query: str, image_type: str) -> str:
        """
        Clinical safety fallback when remote vision API is unreachable.
        Provides a structured review template tailored to image category and question.
        """
        category = image_type.lower()
        size_kb = len(raw_bytes) / 1024

        if category == "medication_label" or any(w in query.lower() for w in ["pill", "bottle", "dose", "drug", "prescription"]):
            return (
                f"### 💊 Medication Label & Prescription Analysis\n\n"
                f"**Image Captured:** {size_kb:.1f} KB prescription document.\n\n"
                f"#### Key Extraction Checklist:\n"
                f"- **Medication & Strength**: Please verify the brand/generic name and milligram strength on the front label.\n"
                f"- **Administration Schedule**: Ensure dosing frequency matches physician instructions (e.g. *once daily with meals*).\n"
                f"- **Safety Precautions**: Check the label for cautionary stickers (e.g. *avoid alcohol*, *causes drowsiness*).\n\n"
                f"#### Pharmacist Discussion Guide:\n"
                f"- *Are there known interactions between this medication and your existing supplements?*\n"
                f"- *What should you do if a dose is missed?*"
            )

        if category == "lab_report" or any(w in query.lower() for w in ["lab", "blood", "test", "cbc", "panel", "cholesterol"]):
            return (
                f"### 🧪 Laboratory & Diagnostic Report Review\n\n"
                f"**Image Captured:** {size_kb:.1f} KB diagnostic panel.\n\n"
                f"#### Interpretation Structure:\n"
                f"- **Standard Reference Ranges**: Lab values must always be interpreted against the specific laboratory's normal range printed adjacent to each analyte.\n"
                f"- **Flags (High/Low)**: Values marked with **H** or **L** represent variances that should be evaluated in clinical context with symptoms.\n\n"
                f"#### Next Steps for Physician Review:\n"
                f"- Request an explanation of any out-of-range biomarkers.\n"
                f"- Inquire whether follow-up testing is needed to establish a trend."
            )

        # Default: Dermatology / Rash / General Clinical Photo
        return (
            f"### 🩺 Clinical Visual Assessment\n\n"
            f"**Image Captured:** {size_kb:.1f} KB clinical photograph.\n\n"
            f"#### Morphological Characteristics:\n"
            f"- **Observation**: Photo received for dermatological/visual evaluation.\n"
            f"- **Key Signs to Monitor**: Observe for changes in size, irregular borders, uneven pigmentation, or local heat/swelling.\n\n"
            f"#### Urgent Warning Signs:\n"
            f"- Seek emergency evaluation if accompanied by **high fever**, **facial or lip swelling**, **rapidly spreading redness**, or **intense blistering**.\n\n"
            f"#### Recommended Actions:\n"
            f"- Keep the area clean and avoid scratching or applying unprescribed topical steroids.\n"
            f"- Show this photograph to a primary care clinician or dermatologist."
        )


vision_service = VisionService()
