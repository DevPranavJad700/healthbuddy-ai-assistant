"""
Report Summarizer — Upload medical reports and get AI-generated summaries.

Features:
- PDF/text medical report parsing
- Key findings extraction
- Structured summary generation
- Abnormal value detection
"""

import re
from app.core.logging_config import logger


class ReportSummarizer:
    """
    Summarizes medical reports using LLM + rule-based extraction.
    """

    # Common medical report sections
    REPORT_SECTIONS = [
        "patient information", "clinical history", "findings", "impression",
        "diagnosis", "recommendations", "medications", "lab results",
        "vital signs", "blood work", "imaging", "conclusion",
    ]

    # Common lab value patterns with normal ranges
    LAB_RANGES = {
        "hemoglobin": {"unit": "g/dL", "male": (13.5, 17.5), "female": (12.0, 16.0)},
        "wbc": {"unit": "cells/mcL", "range": (4500, 11000)},
        "rbc": {"unit": "million/mcL", "male": (4.7, 6.1), "female": (4.2, 5.4)},
        "platelets": {"unit": "/mcL", "range": (150000, 400000)},
        "glucose": {"unit": "mg/dL", "fasting": (70, 100), "random": (70, 140)},
        "cholesterol": {"unit": "mg/dL", "range": (0, 200)},
        "hdl": {"unit": "mg/dL", "range": (40, 60)},
        "ldl": {"unit": "mg/dL", "range": (0, 100)},
        "triglycerides": {"unit": "mg/dL", "range": (0, 150)},
        "creatinine": {"unit": "mg/dL", "male": (0.7, 1.3), "female": (0.6, 1.1)},
        "bun": {"unit": "mg/dL", "range": (7, 20)},
        "sodium": {"unit": "mEq/L", "range": (136, 145)},
        "potassium": {"unit": "mEq/L", "range": (3.5, 5.0)},
        "hba1c": {"unit": "%", "range": (4.0, 5.7)},
        "tsh": {"unit": "mIU/L", "range": (0.4, 4.0)},
        "blood pressure systolic": {"unit": "mmHg", "range": (90, 120)},
        "blood pressure diastolic": {"unit": "mmHg", "range": (60, 80)},
        "bmi": {"unit": "kg/m2", "range": (18.5, 24.9)},
    }

    def summarize_report(self, text: str, llm=None) -> dict:
        """
        Generate a structured summary of a medical report.

        Args:
            text: Full text content of the medical report.
            llm: Optional LLM for AI-powered summarization.

        Returns:
            Dictionary with structured summary sections.
        """
        logger.info(f"Summarizing medical report ({len(text)} chars)")

        # Rule-based extraction
        sections = self._extract_sections(text)
        lab_values = self._extract_lab_values(text)
        abnormals = self._detect_abnormals(lab_values)

        # Build structured summary
        summary = {
            "report_length": len(text),
            "sections_found": list(sections.keys()),
            "key_findings": self._extract_key_findings(text),
            "lab_values": lab_values,
            "abnormal_values": abnormals,
            "medications_mentioned": self._extract_medications(text),
            "ai_summary": None,
        }

        # AI-powered summary if LLM available
        if llm:
            try:
                prompt = self._build_summary_prompt(text)
                summary["ai_summary"] = llm.invoke(prompt)
            except Exception as e:
                logger.error(f"LLM summarization failed: {e}")
                summary["ai_summary"] = self._generate_rule_based_summary(summary)
        else:
            summary["ai_summary"] = self._generate_rule_based_summary(summary)

        return summary

    def _extract_sections(self, text: str) -> dict:
        """Extract recognized report sections."""
        sections = {}
        lines = text.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            line_lower = line.lower().strip()
            matched = False
            for section in self.REPORT_SECTIONS:
                if section in line_lower and len(line_lower) < 80:
                    if current_section:
                        sections[current_section] = "\n".join(current_content).strip()
                    current_section = section
                    current_content = []
                    matched = True
                    break
            if not matched and current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _extract_lab_values(self, text: str) -> list[dict]:
        """Extract numerical lab values from text."""
        values = []
        text_lower = text.lower()

        for lab_name, info in self.LAB_RANGES.items():
            # Match patterns like "Hemoglobin: 14.5 g/dL" or "Glucose 110 mg/dL"
            pattern = rf"{re.escape(lab_name)}[\s:=]*(\d+\.?\d*)\s*{re.escape(info['unit'])}?"
            match = re.search(pattern, text_lower)
            if match:
                value = float(match.group(1))
                # Determine if normal
                ref_range = info.get("range", info.get("male", (0, 999)))
                status = "normal"
                if value < ref_range[0]:
                    status = "low"
                elif value > ref_range[1]:
                    status = "high"

                values.append({
                    "name": lab_name.title(),
                    "value": value,
                    "unit": info["unit"],
                    "reference_range": f"{ref_range[0]}-{ref_range[1]}",
                    "status": status,
                })

        return values

    def _detect_abnormals(self, lab_values: list[dict]) -> list[dict]:
        """Filter abnormal lab values."""
        return [v for v in lab_values if v["status"] != "normal"]

    def _extract_key_findings(self, text: str) -> list[str]:
        """Extract key medical findings from text."""
        findings = []
        keywords = [
            "diagnosis", "finding", "noted", "observed", "revealed",
            "indicates", "suggests", "consistent with", "impression",
            "abnormal", "elevated", "decreased", "positive for",
        ]
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if any(kw in sentence.lower() for kw in keywords) and 20 < len(sentence) < 300:
                findings.append(sentence.strip())

        return findings[:10]  # Top 10 findings

    def _extract_medications(self, text: str) -> list[str]:
        """Extract medication names from text."""
        common_markers = [
            "prescribed", "medication", "taking", "dosage", "mg",
            "tablet", "capsule", "daily", "twice daily",
        ]
        medications = []
        sentences = re.split(r'[.!?\n]', text)

        for sentence in sentences:
            if any(marker in sentence.lower() for marker in common_markers):
                # Clean up
                med = sentence.strip()
                if 10 < len(med) < 200:
                    medications.append(med)

        return medications[:10]

    def _build_summary_prompt(self, text: str) -> str:
        """Build prompt for LLM-based summarization."""
        return (
            "You are a medical report summarizer. Please provide a clear, structured "
            "summary of the following medical report. Include:\n"
            "1. Patient overview\n"
            "2. Key findings\n"
            "3. Abnormal values (if any)\n"
            "4. Recommendations\n\n"
            "IMPORTANT: Always note that this is an AI-generated summary and should be "
            "reviewed by a healthcare professional.\n\n"
            f"MEDICAL REPORT:\n{text[:3000]}\n\n"
            "SUMMARY:"
        )

    def _generate_rule_based_summary(self, analysis: dict) -> str:
        """Generate a structured summary without LLM."""
        parts = ["**Medical Report Summary** (AI-Assisted)\n"]

        if analysis["key_findings"]:
            parts.append("**Key Findings:**")
            for i, f in enumerate(analysis["key_findings"][:5], 1):
                parts.append(f"  {i}. {f}")
            parts.append("")

        if analysis["abnormal_values"]:
            parts.append("**Abnormal Values:**")
            for v in analysis["abnormal_values"]:
                emoji = "HIGH" if v["status"] == "high" else "LOW"
                parts.append(
                    f"  - {v['name']}: {v['value']} {v['unit']} "
                    f"({emoji} | Normal: {v['reference_range']})"
                )
            parts.append("")

        if analysis["medications_mentioned"]:
            parts.append("**Medications Referenced:**")
            for m in analysis["medications_mentioned"][:5]:
                parts.append(f"  - {m}")
            parts.append("")

        parts.append(
            "*This is an AI-generated summary. Please consult your healthcare "
            "provider for interpretation and medical decisions.*"
        )

        return "\n".join(parts)


# Singleton
report_summarizer = ReportSummarizer()
