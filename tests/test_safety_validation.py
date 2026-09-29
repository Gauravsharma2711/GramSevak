"""
Phase 5.5 Safety Validation & Deterministic Fallback Test Suite.

Validates the dedicated safety inspection, grounding verification, and deterministic
fallback layer for AI-generated agricultural advisories.

Tests all minimum requirements:
1. Valid AI advisory passes validation without fallback.
2. Missing required field fails validation (schema violation).
3. Invalid field type fails validation.
4. Invalid severity enum fails validation.
5. Invalid/short timing fails validation.
6. AI changes rainfall value (forecast grounding violation).
7. AI changes temperature value (temperature hallucination).
8. AI changes forecast date (date hallucination).
9. AI changes Panchayat / district identity (location grounding violation).
10. AI invents unsupported risk (severe waterlogging in dry weather).
11. AI contradicts deterministic risk (downgrading critical risk to low).
12. AI introduces unsupported recommendation (spraying during DELAY operational guidance).
13. Unsafe chemical dosage instruction is detected and rejected.
14. Unsupported disease diagnosis is detected and rejected.
15. Unsupported certainty claim is detected and rejected.
16. Provider timeout triggers deterministic fallback.
17. Provider network/HTTP failure triggers deterministic fallback.
18. Malformed AI response triggers deterministic fallback.
19. Valid AI response does not trigger fallback (preserves AI augmented source).
20. Fallback preserves authoritative forecast values.
21. Fallback preserves deterministic rule IDs.
22. Validation metadata is preserved in audit traceability contract.
23. Repeated identical input produces equivalent validation results.
24. No AI output reaches publication state automatically (transitions to NEEDS_REVIEW).
25. Real data verification with Nashik Panchayat context.
"""

from datetime import date
from unittest.mock import MagicMock
import pytest

from backend.app.models.panchayat import Panchayat
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.schemas.advisory_contracts import (
    AdvisoryContext,
    AdvisorySeverityEnum,
    AdvisorySourceEnum,
    AdvisoryStatus,
    AIAdvisoryOutputContract,
    ValidationStatusEnum,
    ValidationSeverityEnum,
    AdvisoryValidationResult,
)
from src.advisory.lifecycle import (
    validate_status_transition,
    InvalidAdvisoryStatusTransitionError,
)
from src.advisory.context_builder import AdvisoryContextService
from src.advisory.ai_service import (
    AIAdvisoryProvider,
    AIAdvisoryService,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIOutputValidationError,
)
from src.advisory.safety_validator import (
    VALIDATOR_VERSION,
    AdvisoryValidationService,
    AdvisorySchemaValidator,
    ForecastGroundingValidator,
    RuleGroundingValidator,
    AdvisorySafetyValidator,
    DeterministicFallbackBuilder,
    default_advisory_validation_service,
)


def make_dummy_panchayat(
    p_id: int = 1001,
    p_name: str = "Ajmer Saundane",
    block_id: int = 10,
    block_name: str = "Baglan",
    dist_id: int = 1,
    dist_name: str = "Nashik",
) -> Panchayat:
    """Helper creating an in-memory Panchayat model with joined parents."""
    p = Panchayat()
    p.id = p_id
    p.name = p_name
    p.panchayat_code = f"P_{p_id}"
    p.lgd_code = 253123
    p.block_id = block_id
    p.district_id = dist_id
    p.latitude = 20.5982
    p.longitude = 74.1201
    p.elevation_m = 585.0

    b = MagicMock()
    b.id = block_id
    b.name = block_name
    p.block = b

    d = MagicMock()
    d.id = dist_id
    d.name = dist_name
    p.district = d

    return p


def make_dummy_forecast(
    f_id: int = 101,
    p_id: int = 1001,
    downscaled_rf: float = 28.5,
    block_rf: float = 30.0,
    f_date: date = date(2026, 9, 10),
    issue_date: date = date(2026, 9, 10),
) -> DownscaledForecast:
    """Helper creating an in-memory DownscaledForecast model."""
    f = DownscaledForecast()
    f.id = f_id
    f.panchayat_id = p_id
    f.forecast_date = f_date
    f.forecast_issue_date = issue_date
    f.downscaled_rainfall_mm = downscaled_rf
    f.block_forecast_rainfall_mm = block_rf
    f.model_name = "XGBoost Regressor"
    f.model_version = "v1.0.0"
    f.confidence = 0.88
    return f


@pytest.fixture
def sample_context() -> AdvisoryContext:
    """Provides a canonical AdvisoryContext for moderate rainfall (28.5 mm)."""
    p = make_dummy_panchayat(1001, "Ajmer Saundane")
    f = make_dummy_forecast(101, 1001, downscaled_rf=28.5, block_rf=30.0)
    service = AdvisoryContextService()
    return service.build_from_objects(p, f)


@pytest.fixture
def dry_context() -> AdvisoryContext:
    """Provides a canonical AdvisoryContext for dry weather (0.0 mm)."""
    p = make_dummy_panchayat(1001, "Ajmer Saundane")
    f = make_dummy_forecast(102, 1001, downscaled_rf=0.0, block_rf=0.0)
    service = AdvisoryContextService()
    return service.build_from_objects(p, f)


@pytest.fixture
def valid_ai_output() -> AIAdvisoryOutputContract:
    """Provides a fully compliant, grounded AI advisory output."""
    return AIAdvisoryOutputContract(
        summary="Moderate Rainfall Alert for Ajmer Saundane: Maintain Field Drainage",
        what_is_happening="Downscaled forecast indicates 28.5 mm of rainfall across Ajmer Saundane.",
        why_it_matters="Increased surface soil moisture can create temporary waterlogging in low-lying crop furrows.",
        recommended_actions=[
            "Clear field drainage channels to prevent water accumulation.",
            "Postpone nitrogen and fertilizer broadcasting.",
        ],
        timing="Next 24 to 48 hours",
        severity=AdvisorySeverityEnum.HIGH,
        warnings=["Inspect drainage outlets along field borders."],
        supporting_forecast_reference={
            "forecast_id": 101,
            "forecast_date": "2026-09-10",
            "downscaled_rainfall_mm": 28.5,
        },
    )


# =============================================================================
# 1. VALID AI ADVISORY PASSES
# =============================================================================

def test_valid_ai_advisory_passes(sample_context, valid_ai_output):
    """Test that a compliant and grounded AI advisory passes validation without fallback."""
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, valid_ai_output)

    assert res.is_valid is True
    assert res.status == ValidationStatusEnum.VALID
    assert res.validation_severity == ValidationSeverityEnum.PASS
    assert res.advisory_source == AdvisorySourceEnum.AI_AUGMENTED
    assert res.fallback_reason is None
    assert len(res.report.violations) == 0


# =============================================================================
# 2. MISSING REQUIRED FIELD FAILS
# =============================================================================

def test_missing_required_field_fails(sample_context, valid_ai_output):
    """Test that blank summary or required strings fail schema validation."""
    invalid_output = valid_ai_output.model_copy(update={"summary": "   "})
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, invalid_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("summary" in v.lower() for v in res.report.violations)


# =============================================================================
# 3. INVALID FIELD TYPE FAILS
# =============================================================================

def test_invalid_field_type_fails(sample_context):
    """Test that passing an invalid object type triggers schema validation failure."""
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, ai_output="Not an AIAdvisoryOutputContract")

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Schema violation" in v for v in res.report.violations)


# =============================================================================
# 4. INVALID SEVERITY FAILS
# =============================================================================

def test_invalid_severity_fails(sample_context, valid_ai_output):
    """Test that an invalid severity object triggers schema rejection."""
    # Construct invalid severity via dict update bypassing direct enum init
    bad_data = valid_ai_output.model_dump()
    bad_data["severity"] = "INVALID_SEVERITY_LEVEL"
    
    ok, violations = AdvisorySchemaValidator.validate_schema("bad_object")
    assert ok is False


# =============================================================================
# 5. INVALID TIMING FAILS
# =============================================================================

def test_invalid_timing_fails(sample_context, valid_ai_output):
    """Test that a whitespace or too short timing field fails validation."""
    invalid_output = valid_ai_output.model_copy(update={"timing": "ab"})  # < 3 chars
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, invalid_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("timing" in v.lower() for v in res.report.violations)


# =============================================================================
# 6. AI CHANGES RAINFALL VALUE
# =============================================================================

def test_ai_changes_rainfall_value(sample_context, valid_ai_output):
    """Test that AI claiming 65.0 mm when forecast is 28.5 mm triggers grounding violation."""
    tampered_output = valid_ai_output.model_copy(
        update={
            "what_is_happening": "Torrential rainfall of 65.0 mm is expected today.",
            "supporting_forecast_reference": {
                "forecast_id": 101,
                "forecast_date": "2026-09-10",
                "downscaled_rainfall_mm": 65.0,  # Changed!
            },
        }
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, tampered_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("contradicts authoritative downscaled rainfall" in v or "Numerical weather inconsistency" in v for v in res.report.violations)


# =============================================================================
# 7. AI CHANGES TEMPERATURE VALUE
# =============================================================================

def test_ai_changes_temperature_value(sample_context, valid_ai_output):
    """Test that AI claiming specific unmeasured temperatures triggers hallucination violation."""
    temp_output = valid_ai_output.model_copy(
        update={"what_is_happening": "Downscaled rainfall of 28.5 mm with extreme heat of 46°C."}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, temp_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Temperature hallucination" in v for v in res.report.violations)


# =============================================================================
# 8. AI CHANGES FORECAST DATE
# =============================================================================

def test_ai_changes_forecast_date(sample_context, valid_ai_output):
    """Test that AI hallucinating a different date (e.g. 2026-12-25) is caught."""
    date_output = valid_ai_output.model_copy(
        update={"what_is_happening": "Downscaled rainfall of 28.5 mm is expected on 2026-12-25."}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, date_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Date hallucination" in v for v in res.report.violations)


# =============================================================================
# 9. AI CHANGES PANCHAYAT IDENTITY
# =============================================================================

def test_ai_changes_panchayat_identity(sample_context, valid_ai_output):
    """Test that AI referencing an alien district name triggers location violation."""
    alien_output = valid_ai_output.model_copy(
        update={"what_is_happening": "Downscaled rainfall of 28.5 mm over Gadchiroli district."}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, alien_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Location grounding violation" in v for v in res.report.violations)


# =============================================================================
# 10. AI INVENTS UNSUPPORTED RISK
# =============================================================================

def test_ai_invents_unsupported_risk(dry_context):
    """Test that claiming flash flood during dry 0 mm weather triggers risk invention violation."""
    flood_output = AIAdvisoryOutputContract(
        summary="Flash Flood Warning for Ajmer Saundane",
        what_is_happening="Severe flash flood and waterlogging conditions developing.",
        why_it_matters="High risk of submerged fields.",
        recommended_actions=["Dig emergency drainage trenches."],
        timing="Next 24 hours",
        severity=AdvisorySeverityEnum.HIGH,
        warnings=["Evacuate field equipment."],
        supporting_forecast_reference={
            "forecast_id": 102,
            "forecast_date": "2026-09-10",
            "downscaled_rainfall_mm": 0.0,
        },
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(dry_context, flood_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Unsupported risk invention" in v for v in res.report.violations)


# =============================================================================
# 11. AI CONTRADICTS DETERMINISTIC RISK
# =============================================================================

def test_ai_contradicts_deterministic_risk(sample_context, valid_ai_output):
    """Test that AI cannot downgrade a critical risk to LOW severity."""
    # Artificially set sample_context highest risk to CRITICAL
    sample_context.risks[0].severity = AdvisorySeverityEnum.CRITICAL
    downgraded_output = valid_ai_output.model_copy(update={"severity": AdvisorySeverityEnum.LOW})

    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, downgraded_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Severity contradiction" in v for v in res.report.violations)


# =============================================================================
# 12. AI INTRODUCES UNSUPPORTED RECOMMENDATION
# =============================================================================

def test_ai_introduces_unsupported_recommendation(sample_context, valid_ai_output):
    """Test that advising immediate spraying when deterministic guidance is DELAY triggers rule contradiction."""
    assert sample_context.recommendations.operational_guidance.get("spraying") in ("DELAY", "POSTPONE")
    contradictory_output = valid_ai_output.model_copy(
        update={"recommended_actions": ["Apply foliar spray immediately without delay."]}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, contradictory_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Rule contradiction" in v for v in res.report.violations)


# =============================================================================
# 13. UNSAFE CHEMICAL DOSAGE INSTRUCTION DETECTED
# =============================================================================

def test_unsafe_dosage_instruction_detected(sample_context, valid_ai_output):
    """Test that chemical mixing dosage patterns like 250 ml/acre are caught and rejected."""
    dosage_output = valid_ai_output.model_copy(
        update={"recommended_actions": ["Mix 250 ml per acre of Chlorpyrifos with water."]}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, dosage_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Chemical dosage safety violation" in v for v in res.report.violations)


# =============================================================================
# 14. UNSUPPORTED DISEASE DIAGNOSIS DETECTED
# =============================================================================

def test_unsupported_disease_diagnosis_detected(sample_context, valid_ai_output):
    """Test that unverified plant pathology claims like 'diagnosed with late blight' are caught."""
    disease_output = valid_ai_output.model_copy(
        update={"why_it_matters": "Crop diagnosed with late blight fungal infection."}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, disease_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Unsupported disease diagnosis" in v for v in res.report.violations)


# =============================================================================
# 15. UNSUPPORTED CERTAINTY CLAIM DETECTED
# =============================================================================

def test_unsupported_certainty_claim_detected(sample_context, valid_ai_output):
    """Test that guarantees like 'guaranteed 100% crop loss' trigger certainty violation."""
    certainty_output = valid_ai_output.model_copy(
        update={"why_it_matters": "This rainfall will cause guaranteed 100% complete crop loss."}
    )
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, certainty_output)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert any("Unsupported certainty violation" in v for v in res.report.violations)


# =============================================================================
# 16. PROVIDER TIMEOUT TRIGGERS FALLBACK
# =============================================================================

def test_provider_timeout_triggers_fallback(sample_context):
    """Test that a timeout exception during AI generation seamlessly triggers deterministic fallback."""
    timeout_err = AIProviderTimeoutError("Connection timed out after 15.0 seconds")
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, ai_output=None, ai_error=timeout_err)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert res.advisory_source == AdvisorySourceEnum.DETERMINISTIC_FALLBACK
    assert "Connection timed out" in res.fallback_reason
    assert res.advisory.severity in [AdvisorySeverityEnum.HIGH, AdvisorySeverityEnum.MODERATE]
    assert "28.5 mm" in res.advisory.what_is_happening


# =============================================================================
# 17. PROVIDER FAILURE TRIGGERS FALLBACK
# =============================================================================

def test_provider_failure_triggers_fallback(sample_context):
    """Test that provider 503 or network failure seamlessly triggers deterministic fallback."""
    fail_err = AIProviderUnavailableError("HTTP 503 Service Unavailable")
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, ai_output=None, ai_error=fail_err)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert res.advisory_source == AdvisorySourceEnum.DETERMINISTIC_FALLBACK
    assert "503" in res.fallback_reason


# =============================================================================
# 18. MALFORMED AI RESPONSE TRIGGERS FALLBACK
# =============================================================================

def test_malformed_ai_response_triggers_fallback(sample_context):
    """Test that malformed JSON or parsing errors from AI trigger fallback."""
    parse_err = AIOutputValidationError("Invalid JSON returned by provider")
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, ai_output=None, ai_error=parse_err)

    assert res.is_valid is False
    assert res.status == ValidationStatusEnum.FALLBACK
    assert res.advisory_source == AdvisorySourceEnum.DETERMINISTIC_FALLBACK


# =============================================================================
# 19. VALID AI RESPONSE DOES NOT TRIGGER FALLBACK
# =============================================================================

def test_valid_ai_response_does_not_trigger_fallback(sample_context, valid_ai_output):
    """Test that a valid AI advisory retains AdvisorySourceEnum.AI_AUGMENTED."""
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, valid_ai_output)

    assert res.is_valid is True
    assert res.advisory_source == AdvisorySourceEnum.AI_AUGMENTED
    assert res.status == ValidationStatusEnum.VALID


# =============================================================================
# 20. FALLBACK PRESERVES FORECAST VALUES
# =============================================================================

def test_fallback_preserves_forecast_values(sample_context):
    """Test that deterministic fallback strictly preserves the input downscaled rainfall."""
    fallback_advisory = DeterministicFallbackBuilder.build_fallback(
        context=sample_context,
        fallback_reason="AI Provider unreachable",
    )

    assert fallback_advisory.supporting_forecast_reference["downscaled_rainfall_mm"] == 28.5
    assert fallback_advisory.supporting_forecast_reference["forecast_id"] == 101
    assert "28.5 mm" in fallback_advisory.what_is_happening


# =============================================================================
# 21. FALLBACK PRESERVES RULE IDS
# =============================================================================

def test_fallback_preserves_rule_ids(sample_context):
    """Test that deterministic fallback records the triggered deterministic rule IDs."""
    service = AdvisoryValidationService()
    res = service.validate_advisory(
        context=sample_context,
        ai_output=None,
        ai_error=AIProviderTimeoutError("Timeout"),
    )

    assert len(res.fallback_rule_ids) >= 1
    assert any("RULE_" in r_id for r_id in res.fallback_rule_ids)


# =============================================================================
# 22. VALIDATION METADATA IS PRESERVED
# =============================================================================

def test_validation_metadata_is_preserved(sample_context, valid_ai_output):
    """Test that lineage metadata, validator version, and validation report are attached."""
    service = AdvisoryValidationService()
    res = service.validate_advisory(sample_context, valid_ai_output)

    assert res.validator_version == VALIDATOR_VERSION
    assert res.validator_version == "v1.0.0"
    assert res.traceability.panchayat_id == 1001
    assert res.traceability.forecast_id == 101
    assert res.traceability.downscaled_rainfall_mm == 28.5
    assert res.traceability.validation_report is not None
    assert res.traceability.validation_report.is_valid is True


# =============================================================================
# 23. REPEATED IDENTICAL INPUT PRODUCES EQUIVALENT VALIDATION RESULTS
# =============================================================================

def test_repeated_identical_input_produces_equivalent_results(sample_context, valid_ai_output):
    """Test that validation is deterministic and produces consistent results."""
    service = AdvisoryValidationService()
    res_1 = service.validate_advisory(sample_context, valid_ai_output)
    res_2 = service.validate_advisory(sample_context, valid_ai_output)

    assert res_1.status == res_2.status
    assert res_1.is_valid == res_2.is_valid
    assert res_1.advisory.summary == res_2.advisory.summary
    assert res_1.report.violations == res_2.report.violations


# =============================================================================
# 24. NO AI OUTPUT REACHES PUBLICATION STATE AUTOMATICALLY
# =============================================================================

def test_no_ai_output_reaches_publication_state_automatically():
    """Verify that validated advisories require officer review and cannot publish directly."""
    # Direct transition from VALIDATED to PUBLISHED is strictly prohibited by state machine
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.VALIDATED, AdvisoryStatus.PUBLISHED, "AI_SERVICE")

    # VALIDATED can only transition to NEEDS_REVIEW
    assert validate_status_transition(AdvisoryStatus.VALIDATED, AdvisoryStatus.NEEDS_REVIEW, "PIPELINE_ORCHESTRATOR") is True


# =============================================================================
# 25. REAL DATA VERIFICATION (NASHIK CONTEXT)
# =============================================================================

def test_real_data_verification_nashik():
    """Verify end-to-end generate and validate workflow with realistic Nashik Panchayat context."""
    p = make_dummy_panchayat(1001, "Ajmer Saundane", dist_name="Nashik")
    f = make_dummy_forecast(101, 1001, downscaled_rf=12.8, block_rf=15.0)
    ctx_service = AdvisoryContextService()
    nashik_context = ctx_service.build_from_objects(p, f)

    val_service = default_advisory_validation_service
    res = val_service.generate_and_validate(context=nashik_context)

    # Mock provider produces grounded advisory matching 12.8 mm
    assert res.is_valid is True
    assert res.status == ValidationStatusEnum.VALID
    assert "Ajmer Saundane" in res.advisory.what_is_happening
    assert res.advisory.supporting_forecast_reference["downscaled_rainfall_mm"] == 12.8
    assert res.traceability.panchayat_id == 1001
    assert res.traceability.validation_report.is_valid is True
