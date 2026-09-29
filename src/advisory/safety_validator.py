"""
Phase 5.5 Safety Validation & Fallback Layer for Agricultural Advisories.

Defines the dedicated post-generation safety inspection, grounding verification,
and deterministic fallback pipeline for AI-generated agricultural advisories:

Target Pipeline:
  AdvisoryContext
  -> Deterministic Rule Results
  -> AI Advisory Service
  -> AI Advisory
  -> Safety Validation
  -> Validated Advisory OR Deterministic Fallback
  -> Future Officer Review

Safety Invariants Enforced:
1. Grounding: AI output must not alter, round, invent, or contradict numerical forecast values.
2. Rule Integrity: AI must not invent risks or contradict deterministic recommendations.
3. Content Safety: Detects and rejects chemical dosages, disease diagnoses, certainty claims,
   medical claims, dangerous physical instructions, and panic-inducing emergency claims.
4. Deterministic Fallback: When AI fails (timeout, unavailable, malformed, or safety violation),
   the system seamlessly falls back to Phase 5.2 deterministic rules with full traceability.
5. Officer Quarantine: Validated or fallback advisories transition to NEEDS_REVIEW;
   never automatically published to farmers.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set

from backend.app.schemas.advisory_contracts import (
    AdvisoryContext,
    AdvisorySeverityEnum,
    AdvisorySourceEnum,
    AIAdvisoryOutputContract,
    SafetyValidationReport,
    AdvisoryTraceabilityContract,
    ValidationStatusEnum,
    ValidationSeverityEnum,
    AdvisoryValidationResult,
)
from src.advisory.ai_service import (
    AIAdvisoryService,
    AIAdvisoryResult,
    AIExecutionMetadata,
    AIAdvisoryServiceError,
    default_ai_advisory_service,
)

logger = logging.getLogger(__name__)

VALIDATOR_VERSION: str = "v1.0.0"


# =============================================================================
# 1. BANNED PATTERNS & SAFETY BOUNDARIES
# =============================================================================

# Specific chemical prescriptions, numeric mixing recipes, and dangerous dosages
BANNED_DOSAGE_PATTERNS: List[str] = [
    r"\b\d+(?:\.\d+)?\s*(?:ml|mg|gm|grams?|liters?|litres?|kg)\s*(?:per|\/)\s*(?:acre|hectare|bigha|plant|tree|guntha|liter|litre)\b",
    r"\bmix\s+\d+(?:\.\d+)?\s*(?:ml|grams?|gm|liters?|kg)\b",
    r"\b(?:apply|spray)\s+\d+(?:\.\d+)?\s*(?:ml|grams?|gm|kg)\b",
    r"\bdilute\s+\d+\s*(?:ml|gm)\s+in\b",
]

# Prohibited medical, human casualty, or panic-inducing emergency terms
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
    "flee the village",
    "state of emergency",
    "catastrophic death toll",
}

# Extreme disaster hallucinations unsupported by local weather downscaling
BANNED_UNSUPPORTED_DISASTERS: Set[str] = {
    "tsunami",
    "volcanic eruption",
    "blizzard",
    "avalanche",
    "tornado warning",
    "super cyclone",
}

# Unsupported certainty guarantees or absolute statements
UNSUPPORTED_CERTAINTY_PATTERNS: List[str] = [
    r"\bguaranteed\s+(?:100\s*%|zero\s+risk|complete|total|crop\s+loss)",
    r"\bwill\s+definitely\s+(?:destroy|ruin|wipe\s+out)\b",
    r"\b100\s*%\s*(?:certain|loss|damage|guaranteed|safe)\b",
    r"\bzero\s+chance\s+of\s+survival\b",
    r"\babsolute\s+guarantee\b",
]

# Specific crop disease / pest diagnosis without agricultural pathology context
UNSUPPORTED_DISEASE_DIAGNOSIS_PATTERNS: List[str] = [
    r"\bdiagnosed\s+with\b",
    r"\bconfirmed\s+infection\s+of\b",
    r"\bcrop\s+(?:has|suffers\s+from)\s+(?:late\s+blight|powdery\s+mildew|stem\s+rot|blast\s+disease|rust\s+fungus)\b",
    r"\binfested\s+by\s+(?:fall\s+armyworm|bollworm|stem\s+borer)\b",
]

# Dangerous physical instructions
DANGEROUS_PHYSICAL_PATTERNS: List[str] = [
    r"\b(?:enter|wade\s+into|cross)\s+(?:deep\s+floodwaters?|swollen\s+streams?|flooded\s+canals?)\b",
    r"\btouch\s+(?:downed|fallen|live)\s+(?:power\s+lines?|wires?)\b",
    r"\boperate\s+machinery\s+in\s+deep\s+water\b",
]


# =============================================================================
# 2. SCHEMA & STRUCTURAL VALIDATOR
# =============================================================================

class AdvisorySchemaValidator:
    """
    Validates that the AI advisory strictly conforms to the Phase 5.1 output contract.
    Ensures no malformed types, missing fields, or empty required strings.
    """

    @classmethod
    def validate_schema(cls, output: Any) -> Tuple[bool, List[str]]:
        violations: List[str] = []

        if not isinstance(output, AIAdvisoryOutputContract):
            violations.append(
                f"Schema violation: Output is of type '{type(output).__name__}', "
                f"expected 'AIAdvisoryOutputContract'."
            )
            return False, violations

        # String fields must not be whitespace-only
        if not output.summary or not output.summary.strip():
            violations.append("Schema violation: 'summary' is missing or blank.")
        elif len(output.summary.strip()) < 10:
            violations.append("Schema violation: 'summary' is too short (min 10 characters).")

        if not output.what_is_happening or not output.what_is_happening.strip():
            violations.append("Schema violation: 'what_is_happening' is missing or blank.")
        elif len(output.what_is_happening.strip()) < 10:
            violations.append("Schema violation: 'what_is_happening' is too short (min 10 characters).")

        if not output.why_it_matters or not output.why_it_matters.strip():
            violations.append("Schema violation: 'why_it_matters' is missing or blank.")
        elif len(output.why_it_matters.strip()) < 10:
            violations.append("Schema violation: 'why_it_matters' is too short (min 10 characters).")

        if not output.timing or not output.timing.strip():
            violations.append("Schema violation: 'timing' is missing or blank.")
        elif len(output.timing.strip()) < 3:
            violations.append("Schema violation: 'timing' is too short (min 3 characters).")

        # Recommended actions must be non-empty list of non-empty strings
        if not output.recommended_actions or len(output.recommended_actions) == 0:
            violations.append("Schema violation: 'recommended_actions' list cannot be empty.")
        else:
            for idx, action in enumerate(output.recommended_actions):
                if not isinstance(action, str) or not action.strip():
                    violations.append(f"Schema violation: Action at index {idx} is empty or not a string.")

        # Severity validation
        if not isinstance(output.severity, AdvisorySeverityEnum):
            violations.append(f"Schema violation: Invalid severity enum value '{output.severity}'.")

        # Forecast reference dictionary
        if not isinstance(output.supporting_forecast_reference, dict):
            violations.append("Schema violation: 'supporting_forecast_reference' must be a valid dictionary.")

        return len(violations) == 0, violations


# =============================================================================
# 3. FORECAST GROUNDING VALIDATOR
# =============================================================================

class ForecastGroundingValidator:
    """
    Verifies that the AI output is strictly grounded in the authoritative numerical forecast.
    Enforces that rainfall, temperature, dates, and locations match without hallucination.
    """

    @classmethod
    def validate_grounding(
        cls,
        output: AIAdvisoryOutputContract,
        context: AdvisoryContext,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        forecast = context.forecast
        panchayat = context.panchayat

        # 1. Supporting Forecast Reference verification
        ref = output.supporting_forecast_reference
        if isinstance(ref, dict):
            # Check forecast_id
            if ref.get("forecast_id") != forecast.forecast_id:
                violations.append(
                    f"Forecast grounding violation: Reference forecast_id '{ref.get('forecast_id')}' "
                    f"does not match authoritative forecast_id '{forecast.forecast_id}'."
                )

            # Check downscaled rainfall reference
            ref_rf = ref.get("downscaled_rainfall_mm")
            if ref_rf is None or not isinstance(ref_rf, (int, float)):
                violations.append("Forecast grounding violation: Reference missing downscaled_rainfall_mm number.")
            elif abs(float(ref_rf) - forecast.downscaled_rainfall_mm) > 0.05:
                violations.append(
                    f"Forecast grounding violation: Reference rainfall '{ref_rf} mm' contradicts "
                    f"authoritative downscaled rainfall '{forecast.downscaled_rainfall_mm:.2f} mm'."
                )

            # Check forecast date reference if present
            ref_date = ref.get("forecast_date")
            if ref_date and str(ref_date) != str(forecast.forecast_date):
                violations.append(
                    f"Forecast grounding violation: Reference forecast_date '{ref_date}' "
                    f"contradicts authoritative forecast_date '{forecast.forecast_date}'."
                )

        combined_text = (
            f"{output.summary} {output.what_is_happening} {output.why_it_matters} "
            f"{' '.join(output.recommended_actions)} {' '.join(output.warnings)}"
        )

        # 2. Text Rainfall mentions
        rainfall_mentions = re.findall(r"(\d+(?:\.\d+)?)\s*mm\b", combined_text, re.IGNORECASE)
        for mention in rainfall_mentions:
            try:
                val = float(mention)
                diff_downscaled = abs(val - forecast.downscaled_rainfall_mm)
                diff_block = abs(val - forecast.block_forecast_rainfall_mm)
                # Must be within 0.5 mm of either downscaled or block forecast
                if diff_downscaled > 0.5 and diff_block > 0.5:
                    violations.append(
                        f"Numerical weather inconsistency: Text mentions '{val} mm', but input downscaled "
                        f"rainfall is '{forecast.downscaled_rainfall_mm:.1f} mm' (block: '{forecast.block_forecast_rainfall_mm:.1f} mm'). "
                        f"AI must never invent or alter weather numbers."
                    )
            except ValueError:
                pass

        # 3. Text Temperature mentions
        temp_mentions = re.findall(r"(\d+(?:\.\d+)?)\s*(?:°\s*[cC]|deg(?:rees)?\s*[cC]?)\b", combined_text)
        for mention in temp_mentions:
            try:
                val = float(mention)
                if forecast.temperature_c is None:
                    violations.append(
                        f"Temperature hallucination: Text mentions '{val}°C', but surface temperature "
                        f"is not provided in the authoritative forecast context."
                    )
                elif abs(val - forecast.temperature_c) > 2.0:
                    violations.append(
                        f"Temperature inconsistency: Text mentions '{val}°C', but input forecast "
                        f"temperature is '{forecast.temperature_c:.1f}°C'."
                    )
            except ValueError:
                pass

        # 4. Text Date mentions
        date_mentions = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", combined_text)
        for date_str in date_mentions:
            if date_str != str(forecast.forecast_date) and date_str != str(forecast.forecast_issue_date):
                violations.append(
                    f"Date hallucination: Text references date '{date_str}', which is neither "
                    f"target forecast_date '{forecast.forecast_date}' nor issue_date '{forecast.forecast_issue_date}'."
                )

        # 5. Location Grounding
        # Ensure text does not mention alien districts
        lower_text = combined_text.lower()
        if "district" in lower_text:
            # If a district is named, it should not contradict authoritative district
            known_alien_districts = {"gadchiroli", "kolhapur", "ratnagiri", "nagpur", "solapur"} - {panchayat.district_name.lower()}
            for alien in known_alien_districts:
                if alien in lower_text:
                    violations.append(
                        f"Location grounding violation: Advisory references alien district '{alien.title()}', "
                        f"contradicting Panchayat district '{panchayat.district_name}'."
                    )

        return len(violations) == 0, violations


# =============================================================================
# 4. RULE GROUNDING VALIDATOR
# =============================================================================

class RuleGroundingValidator:
    """
    Verifies that AI advisory risks and recommendations align with deterministic rule outputs.
    Guarantees AI does not invent unsupported risks or contradict deterministic operational guidance.
    """

    @classmethod
    def validate_rules(
        cls,
        output: AIAdvisoryOutputContract,
        context: AdvisoryContext,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        guidance = context.recommendations.operational_guidance
        combined_text = (
            f"{output.summary} {output.what_is_happening} {output.why_it_matters} "
            f"{' '.join(output.recommended_actions)} {' '.join(output.warnings)}"
        ).lower()

        # 1. Contradicting Spraying Guidance
        spraying_status = guidance.get("spraying")
        if spraying_status in ("DELAY", "POSTPONE", "PAUSE"):
            if re.search(r"\b(?:spray|apply)\s+(?:immediately|today|now|without\s+delay)\b", combined_text):
                violations.append(
                    f"Rule contradiction: Deterministic guidance requires spraying '{spraying_status}', "
                    f"but AI advisory recommends spraying immediately."
                )

        # 2. Contradicting Irrigation Guidance
        irrigation_status = guidance.get("irrigation")
        if irrigation_status in ("PAUSE", "SUSPEND", "STOP"):
            if re.search(r"\b(?:irrigate|water\s+crops?|apply\s+heavy\s+water)\s+(?:heavily|immediately|now)\b", combined_text):
                violations.append(
                    f"Rule contradiction: Deterministic guidance requires irrigation '{irrigation_status}', "
                    f"but AI advisory recommends heavy irrigation."
                )

        # 3. Severity Consistency
        max_deterministic_severity = AdvisorySeverityEnum.LOW
        if context.risks:
            # Rank severities: LOW < MODERATE < HIGH < CRITICAL
            severity_order = {
                AdvisorySeverityEnum.LOW: 1,
                AdvisorySeverityEnum.MODERATE: 2,
                AdvisorySeverityEnum.HIGH: 3,
                AdvisorySeverityEnum.CRITICAL: 4,
            }
            max_deterministic_severity = max(
                context.risks,
                key=lambda r: severity_order.get(r.severity, 1)
            ).severity

            # If deterministic rule is CRITICAL, AI output cannot downgrade to LOW
            if max_deterministic_severity == AdvisorySeverityEnum.CRITICAL:
                if output.severity in (AdvisorySeverityEnum.LOW, AdvisorySeverityEnum.MODERATE):
                    violations.append(
                        f"Severity contradiction: Deterministic rules assigned '{max_deterministic_severity.value}', "
                        f"but AI advisory downgraded severity to '{output.severity.value}'."
                    )

        # 4. Dry weather hallucination: If rainfall <= 2.5 mm and no waterlogging/flood risks exist
        water_risk_present = any(
            getattr(r, "risk_type", "") in ("WATERLOGGING", "HEAVY_RAINFALL", "SOIL_EROSION", "RUNOFF_LEACHING")
            for r in context.risks
        )
        if not water_risk_present and context.forecast.downscaled_rainfall_mm <= 2.5:
            if re.search(r"\b(?:flash\s+flood|waterlogging|torrential\s+rain|heavy\s+downpour|submerged\s+fields)\b", combined_text):
                violations.append(
                    "Unsupported risk invention: AI claims severe waterlogging or flood conditions "
                    "for a dry/light weather forecast without waterlogging risks."
                )

        return len(violations) == 0, violations


# =============================================================================
# 5. SAFETY CONTENT VALIDATOR
# =============================================================================

class AdvisorySafetyValidator:
    """
    Executes boundary checks for harmful, hazardous, or unsupported content:
    - Chemical dosage / mixing recipes
    - Medical and emergency panic claims
    - Unsupported certainty claims
    - Unsupported crop disease diagnoses
    - Dangerous physical instructions
    """

    @classmethod
    def validate_safety(cls, output: AIAdvisoryOutputContract) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        combined_text = (
            f"{output.summary} {output.what_is_happening} {output.why_it_matters} "
            f"{' '.join(output.recommended_actions)} {' '.join(output.warnings)}"
        )
        lower_text = combined_text.lower()

        # 1. Chemical Dosage & Recipe Pattern Check
        for pattern in BANNED_DOSAGE_PATTERNS:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    f"Chemical dosage safety violation: Detected specific chemical recipe pattern '{match.group(0)}'. "
                    f"AI is strictly prohibited from prescribing chemical dosages or mixing ratios."
                )

        # 2. Medical & Emergency Panic Words Check
        for banned in BANNED_MEDICAL_AND_EMERGENCY_WORDS:
            if banned in lower_text:
                violations.append(
                    f"Medical/Emergency violation: Text contains prohibited phrasing '{banned}'."
                )

        # 3. Unsupported Disaster Claims
        for disaster in BANNED_UNSUPPORTED_DISASTERS:
            if disaster in lower_text:
                violations.append(
                    f"Unsupported disaster hallucination: Text mentions '{disaster}'."
                )

        # 4. Unsupported Certainty Claims
        for pattern in UNSUPPORTED_CERTAINTY_PATTERNS:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    f"Unsupported certainty violation: Text makes absolute claim '{match.group(0)}'. "
                    f"Weather advisories must communicate probabilistic risk, not unfounded guarantees."
                )

        # 5. Unsupported Disease Diagnosis
        for pattern in UNSUPPORTED_DISEASE_DIAGNOSIS_PATTERNS:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    f"Unsupported disease diagnosis: Text claims '{match.group(0)}' without plant pathology diagnostic input."
                )

        # 6. Dangerous Physical Instructions
        for pattern in DANGEROUS_PHYSICAL_PATTERNS:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    f"Dangerous instruction violation: Text advises hazardous physical action '{match.group(0)}'."
                )

        return len(violations) == 0, violations


# =============================================================================
# 6. DETERMINISTIC FALLBACK BUILDER
# =============================================================================

class DeterministicFallbackBuilder:
    """
    Constructs a 100% deterministic, grounded agricultural advisory directly from
    AdvisoryContext and Phase 5.2 rule-engine results when AI fails or is unsafe.
    """

    @classmethod
    def build_fallback(
        cls,
        context: AdvisoryContext,
        fallback_reason: str,
    ) -> AIAdvisoryOutputContract:
        """
        Builds a safe, authoritative fallback advisory contract from deterministic rules.
        """
        p = context.panchayat
        f = context.forecast
        rf = f.downscaled_rainfall_mm
        category = f.rainfall_category

        # Determine severity from triggered deterministic risks
        if context.risks:
            severity_order = {
                AdvisorySeverityEnum.LOW: 1,
                AdvisorySeverityEnum.MODERATE: 2,
                AdvisorySeverityEnum.HIGH: 3,
                AdvisorySeverityEnum.CRITICAL: 4,
            }
            highest_risk = max(context.risks, key=lambda r: severity_order.get(r.severity, 1))
            sev = highest_risk.severity
            primary_title = getattr(highest_risk, "risk_type", "Weather Risk")
        else:
            sev = AdvisorySeverityEnum.LOW
            primary_title = "Normal Weather Conditions"

        # Summary
        summary = (
            f"[Deterministic Advisory] {category} Advisory for {p.panchayat_name}: "
            f"{primary_title}"
        )

        # What is happening
        what_is_happening = (
            f"Downscaled weather forecast indicates {rf:.1f} mm of rainfall ({category}) "
            f"for {p.panchayat_name} Gram Panchayat ({p.block_name} Block, {p.district_name} District) "
            f"on {f.forecast_date}."
        )

        # Why it matters
        if context.risks:
            risk_descriptions = [f"{r.risk_type}: {r.triggering_condition}" for r in context.risks if getattr(r, "triggering_condition", None)]
            why_it_matters = "; ".join(risk_descriptions) if risk_descriptions else (
                f"Rainfall of {rf:.1f} mm expected to influence root-zone soil saturation."
            )
        else:
            why_it_matters = (
                f"Rainfall of {rf:.1f} mm is within standard seasonal parameters. "
                "Normal soil moisture retention expected without weather-induced crop distress."
            )

        # Recommended actions
        actions = context.recommendations.recommended_actions
        if not actions:
            actions = ["Maintain routine field monitoring according to standard crop schedules."]

        # Timing
        timing = context.recommendations.timing_window or "Immediate next 24 to 48 hours"

        # Warnings
        warnings = [f"Alert: {r.risk_type} - {r.triggering_condition}" for r in context.risks if r.severity in (AdvisorySeverityEnum.HIGH, AdvisorySeverityEnum.CRITICAL)]
        if not warnings:
            warnings = ["Follow standard agricultural safety guidelines for current operations."]

        # Supporting forecast reference
        reference = {
            "forecast_id": f.forecast_id,
            "forecast_date": str(f.forecast_date),
            "downscaled_rainfall_mm": rf,
        }

        logger.info(
            f"[DETERMINISTIC_FALLBACK_GENERATED] panchayat_id={p.panchayat_id} "
            f"rainfall={rf}mm severity={sev.value} reason={fallback_reason}"
        )

        return AIAdvisoryOutputContract(
            summary=summary[:500],
            what_is_happening=what_is_happening[:1000],
            why_it_matters=why_it_matters[:1000],
            recommended_actions=actions,
            timing=timing[:200],
            severity=sev,
            warnings=warnings,
            supporting_forecast_reference=reference,
        )


# =============================================================================
# 7. ADVISORY VALIDATION SERVICE (ORCHESTRATOR)
# =============================================================================

class AdvisoryValidationService:
    """
    Coordinates post-generation safety validation, grounding verification,
    and deterministic fallback for the agricultural advisory pipeline.
    """

    def __init__(self, validator_version: str = VALIDATOR_VERSION):
        self.validator_version = validator_version

    def validate_advisory(
        self,
        context: AdvisoryContext,
        ai_output: Optional[AIAdvisoryOutputContract] = None,
        ai_error: Optional[Exception] = None,
        ai_metadata: Optional[AIExecutionMetadata] = None,
    ) -> AdvisoryValidationResult:
        """
        Validates an AI advisory against schema, forecast grounding, rule grounding,
        and content safety rules. If any check fails, seamlessly produces a deterministic
        fallback advisory.

        Args:
            context: Validated AdvisoryContext containing authoritative forecast & rules.
            ai_output: Generated AIAdvisoryOutputContract (None if generation failed).
            ai_error: Exception raised during AI generation (None if generation succeeded).
            ai_metadata: Execution metadata from AI service call.

        Returns:
            AdvisoryValidationResult: Complete structured validation and advisory outcome.
        """
        now = datetime.now(timezone.utc)
        checked_rules = [
            "schema_structural_integrity",
            "weather_numerical_consistency",
            "forecast_grounding_verification",
            "rule_grounding_coherence",
            "chemical_dosage_safety",
            "medical_and_emergency_guard",
            "unsupported_certainty_guard",
            "crop_disease_diagnostic_guard",
            "dangerous_instruction_guard",
        ]

        # Branch 1: AI Service encountered an error (timeout, network, auth, parse error)
        if ai_error is not None or ai_output is None:
            err_reason = str(ai_error) if ai_error else "AI output was not provided"
            fallback_reason = f"AI generation failure: {err_reason}"
            logger.warning(
                f"[SAFETY_VALIDATION_FALLBACK_TRIGGERED] panchayat_id={context.panchayat.panchayat_id} "
                f"reason='{fallback_reason}'"
            )

            fallback_advisory = DeterministicFallbackBuilder.build_fallback(
                context=context,
                fallback_reason=fallback_reason,
            )

            report = SafetyValidationReport(
                is_valid=False,
                validation_timestamp=now,
                checked_rules=checked_rules,
                violations=[fallback_reason],
                weather_consistency_passed=False,
                dosage_safety_passed=True,
                hallucination_check_passed=False,
                fallback_required=True,
                status=ValidationStatusEnum.FALLBACK,
                validation_severity=ValidationSeverityEnum.CRITICAL,
                warnings=[],
                fallback_reason=fallback_reason,
                validator_version=self.validator_version,
            )

            traceability = self._build_traceability(
                context=context,
                source=AdvisorySourceEnum.DETERMINISTIC_FALLBACK,
                report=report,
                ai_metadata=ai_metadata,
            )

            return AdvisoryValidationResult(
                status=ValidationStatusEnum.FALLBACK,
                validation_severity=ValidationSeverityEnum.CRITICAL,
                is_valid=False,
                advisory=fallback_advisory,
                report=report,
                advisory_source=AdvisorySourceEnum.DETERMINISTIC_FALLBACK,
                fallback_reason=fallback_reason,
                fallback_rule_ids=[r.rule_id for r in context.risks],
                traceability=traceability,
                validator_version=self.validator_version,
                validation_timestamp=now,
            )

        # Branch 2: AI output exists; execute comprehensive multi-layer validation
        all_violations: List[str] = []

        # Layer 1: Schema & Structure
        schema_ok, schema_violations = AdvisorySchemaValidator.validate_schema(ai_output)
        all_violations.extend(schema_violations)

        forecast_violations: List[str] = []
        rule_violations: List[str] = []
        safety_violations: List[str] = []

        if not schema_ok:
            forecast_ok = False
            rule_ok = False
            safety_ok = False
        else:
            # Layer 2: Forecast Grounding
            forecast_ok, forecast_violations = ForecastGroundingValidator.validate_grounding(ai_output, context)
            all_violations.extend(forecast_violations)

            # Layer 3: Rule Grounding
            rule_ok, rule_violations = RuleGroundingValidator.validate_rules(ai_output, context)
            all_violations.extend(rule_violations)

            # Layer 4: Content Safety
            safety_ok, safety_violations = AdvisorySafetyValidator.validate_safety(ai_output)
            all_violations.extend(safety_violations)

        # Determine individual safety flags
        weather_consistency_passed = forecast_ok and schema_ok
        dosage_safety_passed = not any("dosage" in v.lower() for v in safety_violations)
        hallucination_check_passed = not any("hallucination" in v.lower() or "unsupported" in v.lower() for v in (forecast_violations + safety_violations + rule_violations))

        if all_violations:
            fallback_reason = f"Safety violations detected: {'; '.join(all_violations[:3])}"
            logger.warning(
                f"[SAFETY_VALIDATION_FAILED] panchayat_id={context.panchayat.panchayat_id} "
                f"violations={all_violations}"
            )

            fallback_advisory = DeterministicFallbackBuilder.build_fallback(
                context=context,
                fallback_reason=fallback_reason,
            )

            report = SafetyValidationReport(
                is_valid=False,
                validation_timestamp=now,
                checked_rules=checked_rules,
                violations=all_violations,
                weather_consistency_passed=weather_consistency_passed,
                dosage_safety_passed=dosage_safety_passed,
                hallucination_check_passed=hallucination_check_passed,
                fallback_required=True,
                status=ValidationStatusEnum.FALLBACK,
                validation_severity=ValidationSeverityEnum.CRITICAL,
                warnings=[],
                fallback_reason=fallback_reason,
                validator_version=self.validator_version,
            )

            traceability = self._build_traceability(
                context=context,
                source=AdvisorySourceEnum.DETERMINISTIC_FALLBACK,
                report=report,
                ai_metadata=ai_metadata,
            )

            return AdvisoryValidationResult(
                status=ValidationStatusEnum.FALLBACK,
                validation_severity=ValidationSeverityEnum.CRITICAL,
                is_valid=False,
                advisory=fallback_advisory,
                report=report,
                advisory_source=AdvisorySourceEnum.DETERMINISTIC_FALLBACK,
                fallback_reason=fallback_reason,
                fallback_rule_ids=[r.rule_id for r in context.risks],
                traceability=traceability,
                validator_version=self.validator_version,
                validation_timestamp=now,
            )

        # Branch 3: All validation checks passed cleanly
        logger.info(
            f"[SAFETY_VALIDATION_PASSED] panchayat_id={context.panchayat.panchayat_id} "
            f"forecast_id={context.forecast.forecast_id}"
        )

        report = SafetyValidationReport(
            is_valid=True,
            validation_timestamp=now,
            checked_rules=checked_rules,
            violations=[],
            weather_consistency_passed=True,
            dosage_safety_passed=True,
            hallucination_check_passed=True,
            fallback_required=False,
            status=ValidationStatusEnum.VALID,
            validation_severity=ValidationSeverityEnum.PASS,
            warnings=[],
            fallback_reason=None,
            validator_version=self.validator_version,
        )

        traceability = self._build_traceability(
            context=context,
            source=AdvisorySourceEnum.AI_AUGMENTED,
            report=report,
            ai_metadata=ai_metadata,
        )

        return AdvisoryValidationResult(
            status=ValidationStatusEnum.VALID,
            validation_severity=ValidationSeverityEnum.PASS,
            is_valid=True,
            advisory=ai_output,
            report=report,
            advisory_source=AdvisorySourceEnum.AI_AUGMENTED,
            fallback_reason=None,
            fallback_rule_ids=[],
            traceability=traceability,
            validator_version=self.validator_version,
            validation_timestamp=now,
        )

    def generate_and_validate(
        self,
        context: AdvisoryContext,
        ai_service: Optional[AIAdvisoryService] = None,
        target_language: str = "en",
    ) -> AdvisoryValidationResult:
        """
        Coordinates full end-to-end generation and safety validation:
        AdvisoryContext -> AIAdvisoryService -> Safety Validation -> AdvisoryValidationResult.
        """
        svc = ai_service or default_ai_advisory_service
        try:
            ai_res: AIAdvisoryResult = svc.generate_advisory(
                context=context,
                target_language=target_language,
            )
            return self.validate_advisory(
                context=context,
                ai_output=ai_res.output,
                ai_metadata=ai_res.metadata,
            )
        except Exception as exc:
            logger.warning(
                f"[GENERATE_AND_VALIDATE_EXCEPTION] Falling back to deterministic rules: {exc}"
            )
            return self.validate_advisory(
                context=context,
                ai_output=None,
                ai_error=exc,
            )

    def _build_traceability(
        self,
        context: AdvisoryContext,
        source: AdvisorySourceEnum,
        report: SafetyValidationReport,
        ai_metadata: Optional[AIExecutionMetadata] = None,
    ) -> AdvisoryTraceabilityContract:
        """Constructs an AdvisoryTraceabilityContract linking all lineage metadata."""
        base_t = context.traceability
        return AdvisoryTraceabilityContract(
            panchayat_id=base_t.panchayat_id,
            forecast_id=base_t.forecast_id,
            forecast_date=base_t.forecast_date,
            forecast_issue_date=base_t.forecast_issue_date,
            source_forecast_reference=base_t.source_forecast_reference,
            downscaled_rainfall_mm=base_t.downscaled_rainfall_mm,
            ml_model_name=base_t.ml_model_name,
            ml_model_version=base_t.ml_model_version,
            rule_version=base_t.rule_version,
            advisory_source=source,
            ai_provider=ai_metadata.provider_name if ai_metadata else None,
            ai_model=ai_metadata.model_name if ai_metadata else None,
            ai_prompt_version=ai_metadata.prompt_version if ai_metadata else None,
            validation_report=report,
        )


# Application-wide default singleton instance
default_advisory_validation_service = AdvisoryValidationService()
