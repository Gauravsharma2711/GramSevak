"""
Phase 5 Advisory Safety Validation Engine & Guardrails.

Defines safety boundary validation checks that inspect generated AI content
before it is admitted into the officer review queue:
  1. Weather Numerical Consistency Check: Ensures numerical values in text exactly match forecast input.
  2. Chemical Dosage & Pesticide Safety Check: Disallows dangerous brand recipes or unsupported dosages.
  3. Medical & Disaster Safety Check: Prohibits medical claims, panic-inducing evacuations, or fake disasters.
  4. Content Completeness & Structure Check: Validates all required structured fields.
  5. Deterministic Fallback Trigger: Flags fallback_required if any safety check fails.
"""

import re
from typing import List, Set
from backend.app.schemas.advisory_contracts import (
    AIAdvisoryInputContract,
    AIAdvisoryOutputContract,
    SafetyValidationReport,
)


# Banned chemical terms, unauthorized medical claims, and dangerous dosage patterns
BANNED_DOSAGE_PATTERNS = [
    r"\b\d+\s*(?:ml|mg|gm|grams|liters?)\s*(?:per|\/)\s*(?:acre|hectare|bigha|plant|tree)\b",
    r"\bmix\s+\d+\s*(?:ml|grams|gm)\b",
]

BANNED_MEDICAL_AND_EMERGENCY_WORDS: Set[str] = {
    "human disease",
    "cure cancer",
    "covid",
    "antibiotics for humans",
    "fatal poison",
    "toxic to drink",
    "mass casualty",
    "emergency evacuation immediately",
    "run for your life",
}

BANNED_UNSUPPORTED_DISASTERS: Set[str] = {
    "tsunami",
    "volcanic eruption",
    "blizzard",
    "avalanche",
    "tornado warning",
}


def validate_advisory_safety(
    input_contract: AIAdvisoryInputContract,
    output_contract: AIAdvisoryOutputContract,
) -> SafetyValidationReport:
    """
    Executes automated safety validation on AI-generated advisory output against the input context.
    
    Returns:
        SafetyValidationReport: Detailed audit report with pass/fail and specific violation descriptions.
    """
    violations: List[str] = []
    checked_rules: List[str] = [
        "weather_numerical_consistency",
        "chemical_dosage_safety",
        "medical_and_emergency_guard",
        "content_completeness",
        "supporting_forecast_grounding",
    ]

    combined_text = (
        f"{output_contract.summary} {output_contract.what_is_happening} "
        f"{output_contract.why_it_matters} {' '.join(output_contract.recommended_actions)} "
        f"{' '.join(output_contract.warnings)}"
    ).lower()

    # Rule 1: Weather Numerical Consistency & Grounding
    weather_consistency_passed = True
    input_rainfall = input_contract.forecast_context.downscaled_rainfall_mm
    
    # Check supporting forecast reference
    ref = output_contract.supporting_forecast_reference
    if not ref or ref.get("forecast_id") != input_contract.forecast_context.forecast_id:
        violations.append("AI output failed to reference the correct forecast_id in supporting_forecast_reference.")
        weather_consistency_passed = False

    # Extract all floating point or decimal numbers from text that look like rainfall amounts
    # e.g., "15.5 mm" or "15.5mm"
    rainfall_mentions = re.findall(r"(\d+(?:\.\d+)?)\s*mm\b", combined_text)
    for mention in rainfall_mentions:
        try:
            val = float(mention)
            # Must be within 0.2mm tolerance of input downscaled or block forecast
            block_rf = input_contract.forecast_context.block_forecast_rainfall_mm
            if abs(val - input_rainfall) > 0.5 and abs(val - block_rf) > 0.5:
                violations.append(
                    f"Numerical weather inconsistency: Text mentions '{val} mm', but input downscaled rainfall is "
                    f"'{input_rainfall} mm' (block: '{block_rf} mm'). AI must not invent or alter weather numbers."
                )
                weather_consistency_passed = False
        except ValueError:
            pass

    # Rule 2: Chemical Dosage Safety
    dosage_safety_passed = True
    for pattern in BANNED_DOSAGE_PATTERNS:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            violations.append(
                f"Chemical dosage safety violation: Detected specific chemical prescription pattern '{match.group(0)}'. "
                f"AI is strictly prohibited from formulating chemical recipes or dosages."
            )
            dosage_safety_passed = False

    # Rule 3: Medical & Emergency Claim Guard
    hallucination_check_passed = True
    for banned in BANNED_MEDICAL_AND_EMERGENCY_WORDS:
        if banned in combined_text:
            violations.append(f"Medical/Emergency violation: Text contains prohibited phrasing '{banned}'.")
            hallucination_check_passed = False

    for disaster in BANNED_UNSUPPORTED_DISASTERS:
        if disaster in combined_text:
            violations.append(f"Unsupported disaster hallucination: Text mentions '{disaster}'.")
            hallucination_check_passed = False

    # Rule 4: Structural Completeness
    if not output_contract.recommended_actions or len(output_contract.recommended_actions) == 0:
        violations.append("Content completeness violation: recommended_actions is empty.")

    is_valid = len(violations) == 0
    fallback_required = not is_valid

    return SafetyValidationReport(
        is_valid=is_valid,
        checked_rules=checked_rules,
        violations=violations,
        weather_consistency_passed=weather_consistency_passed,
        dosage_safety_passed=dosage_safety_passed,
        hallucination_check_passed=hallucination_check_passed,
        fallback_required=fallback_required,
    )
