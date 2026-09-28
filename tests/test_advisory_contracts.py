"""
Phase 5 Advisory Data Contracts, Lifecycle, and Safety Tests.

Verifies:
1. Valid advisory context construction (PanchayatContext, ForecastContext, RiskContext).
2. Rejection of missing required Panchayat information.
3. Rejection of invalid forecast references / dates (forecast_date < forecast_issue_date).
4. Advisory lifecycle status transitions and safety boundaries (DRAFT -> GENERATED -> VALIDATED -> NEEDS_REVIEW -> APPROVED -> PUBLISHED).
5. Illegal transition rejection (e.g. GENERATED -> PUBLISHED, DRAFT -> PUBLISHED, REJECTED -> APPROVED).
6. Missing prerequisite data for transitions (e.g. APPROVED without officer_id).
7. AI input and output contract structure validation.
8. Rejection of invalid or incomplete AI output (missing required fields, negative rainfall, etc.).
9. Safety validation guardrails (weather numerical consistency check, chemical dosage check, prohibited claims).
10. Traceability contract integrity and audit fields.
11. Backward compatibility with existing forecast and advisory API schemas.
"""

from datetime import date, datetime, timedelta
import pytest
from pydantic import ValidationError

from backend.app.schemas.advisory_contracts import (
    AdvisoryStatus,
    AdvisorySeverityEnum,
    AdvisorySourceEnum,
    PanchayatContext,
    ForecastContext,
    AgriculturalRiskItem,
    DeterministicRecommendationContext,
    AIAdvisoryInputContract,
    AIAdvisoryOutputContract,
    SafetyValidationReport,
    AdvisoryTraceabilityContract,
    FullAdvisoryPipelineEnvelope,
)
from src.advisory.lifecycle import (
    validate_status_transition,
    check_transition_data_requirements,
    InvalidAdvisoryStatusTransitionError,
    MissingRequiredTransitionDataError,
    ALLOWED_TRANSITIONS,
)
from src.advisory.safety_rules import validate_advisory_safety
from src.advisory.context_builder import (
    build_panchayat_context,
    build_forecast_context,
    build_deterministic_risk_and_recommendations,
    build_ai_advisory_input,
    build_traceability_record,
    ContextBuilderError,
)
from backend.app.models.panchayat import Panchayat
from backend.app.models.block import Block
from backend.app.models.district import District
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.schemas.forecast import ForecastGenerateResponse, ForecastRetrievalResponse
from backend.app.schemas.advisory import AdvisoryResponse


# =============================================================================
# 1. PANCHAYAT CONTEXT CONTRACT TESTS
# =============================================================================

def test_valid_panchayat_context():
    """Verify that a complete, valid Panchayat context is accepted."""
    context = PanchayatContext(
        panchayat_id=1001,
        panchayat_name="Ajmer Saundane",
        panchayat_code="P_1001",
        lgd_code=253123,
        block_id=10,
        block_name="Baglan",
        district_id=1,
        district_name="Nashik",
        latitude=20.5982,
        longitude=74.1201,
        elevation_m=585.0,
    )
    assert context.panchayat_id == 1001
    assert context.panchayat_name == "Ajmer Saundane"
    assert context.block_name == "Baglan"
    assert context.district_name == "Nashik"
    assert context.elevation_m == 585.0


def test_missing_required_panchayat_information():
    """Verify that missing mandatory fields (e.g. panchayat_name or lgd_code) raises ValidationError."""
    with pytest.raises(ValidationError):
        PanchayatContext(
            panchayat_id=1001,
            # panchayat_name missing
            lgd_code=253123,
            block_name="Baglan",
            district_name="Nashik",
        )

    with pytest.raises(ValidationError):
        PanchayatContext(
            panchayat_id=1001,
            panchayat_name="Ajmer Saundane",
            # lgd_code missing
            block_name="Baglan",
            district_name="Nashik",
        )


def test_invalid_panchayat_coordinates():
    """Verify that out-of-bounds latitude/longitude are rejected."""
    with pytest.raises(ValidationError):
        PanchayatContext(
            panchayat_id=1001,
            panchayat_name="Ajmer Saundane",
            lgd_code=253123,
            block_name="Baglan",
            district_name="Nashik",
            latitude=120.0,  # Invalid latitude > 90
            longitude=74.12,
        )


# =============================================================================
# 2. FORECAST CONTEXT CONTRACT TESTS
# =============================================================================

def test_valid_forecast_context():
    """Verify that a complete, valid forecast context is accepted."""
    fc = ForecastContext(
        forecast_id=1,
        forecast_date=date(2026, 9, 4),
        forecast_issue_date=date(2026, 9, 4),
        lead_days=0,
        block_forecast_rainfall_mm=15.0,
        downscaled_rainfall_mm=12.78,
        rainfall_category="Moderate rainfall",
        model_name="XGBoost Regressor",
        model_version="v1.0.0",
        confidence=None,
    )
    assert fc.forecast_id == 1
    assert fc.downscaled_rainfall_mm == 12.78
    assert fc.confidence is None
    # Future fields default to None and are not fabricated
    assert fc.temperature_c is None
    assert fc.humidity_pct is None
    assert fc.wind_speed_kmh is None


def test_invalid_forecast_dates():
    """Verify that forecast_date earlier than forecast_issue_date is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ForecastContext(
            forecast_id=1,
            forecast_date=date(2026, 9, 1),
            forecast_issue_date=date(2026, 9, 4),  # issue date later than target date
            lead_days=0,
            block_forecast_rainfall_mm=15.0,
            downscaled_rainfall_mm=12.78,
            rainfall_category="Moderate rainfall",
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
    assert "cannot be earlier than forecast_issue_date" in str(exc_info.value)


def test_negative_rainfall_rejected():
    """Verify negative rainfall values are rejected by schema."""
    with pytest.raises(ValidationError):
        ForecastContext(
            forecast_id=1,
            forecast_date=date(2026, 9, 4),
            forecast_issue_date=date(2026, 9, 4),
            lead_days=0,
            block_forecast_rainfall_mm=-5.0,
            downscaled_rainfall_mm=12.0,
            rainfall_category="No rain",
            model_name="XGBoost",
            model_version="v1.0",
        )


# =============================================================================
# 3. LIFECYCLE & STATUS TRANSITION TESTS
# =============================================================================

def test_valid_status_transitions():
    """Verify that all legal transitions across the Phase 5 pipeline succeed."""
    assert validate_status_transition(AdvisoryStatus.DRAFT, AdvisoryStatus.GENERATED, "AI_SERVICE")
    assert validate_status_transition(AdvisoryStatus.GENERATED, AdvisoryStatus.VALIDATED, "SAFETY_VALIDATOR")
    assert validate_status_transition(AdvisoryStatus.VALIDATED, AdvisoryStatus.NEEDS_REVIEW, "PIPELINE_ORCHESTRATOR")
    assert validate_status_transition(AdvisoryStatus.NEEDS_REVIEW, AdvisoryStatus.APPROVED, "EXTENSION_OFFICER")
    assert validate_status_transition(AdvisoryStatus.APPROVED, AdvisoryStatus.PUBLISHED, "PUBLICATION_SERVICE")


def test_deterministic_bypass_transition():
    """Verify that deterministic path can transition directly from DRAFT to NEEDS_REVIEW."""
    assert validate_status_transition(AdvisoryStatus.DRAFT, AdvisoryStatus.NEEDS_REVIEW, "RULE_ENGINE")


def test_safety_failure_and_rejection_transitions():
    """Verify transitions to FAILED_VALIDATION and REJECTED."""
    assert validate_status_transition(AdvisoryStatus.GENERATED, AdvisoryStatus.FAILED_VALIDATION, "SAFETY_VALIDATOR")
    assert validate_status_transition(AdvisoryStatus.FAILED_VALIDATION, AdvisoryStatus.NEEDS_REVIEW, "FALLBACK_SERVICE")
    assert validate_status_transition(AdvisoryStatus.NEEDS_REVIEW, AdvisoryStatus.REJECTED, "EXTENSION_OFFICER")


def test_illegal_status_transitions_rejected():
    """Verify that unsafe shortcuts (e.g. GENERATED -> PUBLISHED) are strictly blocked."""
    # Cannot publish directly from GENERATED (must pass validation and officer approval)
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.GENERATED, AdvisoryStatus.PUBLISHED)

    # Cannot publish directly from DRAFT
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.DRAFT, AdvisoryStatus.PUBLISHED)

    # Cannot publish directly from VALIDATED (requires officer approval)
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.VALIDATED, AdvisoryStatus.PUBLISHED)

    # Cannot approve a REJECTED advisory without new draft
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.REJECTED, AdvisoryStatus.APPROVED)

    # Cannot modify an already PUBLISHED advisory
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.PUBLISHED, AdvisoryStatus.DRAFT)


def test_unauthorized_actor_rejected():
    """Verify that unauthorized actors cannot execute restricted transitions."""
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        # AI service cannot approve advisories; only EXTENSION_OFFICER can
        validate_status_transition(AdvisoryStatus.NEEDS_REVIEW, AdvisoryStatus.APPROVED, "AI_SERVICE")


def test_transition_data_requirements():
    """Verify that transition requirements are strictly enforced."""
    # GENERATED requires draft content
    with pytest.raises(MissingRequiredTransitionDataError):
        check_transition_data_requirements(AdvisoryStatus.GENERATED, has_draft_content=False)

    # VALIDATED requires is_safety_valid=True
    with pytest.raises(MissingRequiredTransitionDataError):
        check_transition_data_requirements(AdvisoryStatus.VALIDATED, is_safety_valid=False)

    # APPROVED requires officer_id
    with pytest.raises(MissingRequiredTransitionDataError):
        check_transition_data_requirements(AdvisoryStatus.APPROVED, has_officer_id=False)


# =============================================================================
# 4. AI INPUT / OUTPUT CONTRACT TESTS
# =============================================================================

@pytest.fixture
def sample_input_contract():
    return AIAdvisoryInputContract(
        panchayat_context=PanchayatContext(
            panchayat_id=1001,
            panchayat_name="Ajmer Saundane",
            lgd_code=253123,
            block_name="Baglan",
            district_name="Nashik",
        ),
        forecast_context=ForecastContext(
            forecast_id=1,
            forecast_date=date(2026, 9, 4),
            forecast_issue_date=date(2026, 9, 4),
            lead_days=0,
            block_forecast_rainfall_mm=15.0,
            downscaled_rainfall_mm=12.8,
            rainfall_category="Moderate rainfall",
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        ),
        risks=[
            AgriculturalRiskItem(
                risk_type="SPRAY_WASHOFF",
                severity=AdvisorySeverityEnum.HIGH,
                triggering_condition="Rainfall 12.8 mm > 2.5 mm threshold",
                rule_id="RULE_SPRAY_01",
                rule_version="v1.0.0",
            )
        ],
        deterministic_recommendations=DeterministicRecommendationContext(
            recommended_actions=["Postpone chemical spraying."],
            timing_window="Next 24 to 48 hours",
            operational_guidance={"spraying": "POSTPONE"},
        ),
    )


def test_valid_ai_output_contract(sample_input_contract):
    """Verify that well-formed structured AI output is accepted."""
    output = AIAdvisoryOutputContract(
        summary="Moderate Rainfall Advisory: Delay Spraying & Maintain Drainage",
        what_is_happening="Downscaled micro-level forecast indicates 12.8 mm moderate rainfall over Ajmer Saundane.",
        why_it_matters="Surface moisture will increase rapidly, causing pesticide washes and localized saturation.",
        recommended_actions=[
            "Postpone all chemical pesticide/fungicide spraying.",
            "Inspect standing crop furrows for free-flowing drainage.",
        ],
        timing="Next 24 to 48 hours",
        severity=AdvisorySeverityEnum.MODERATE,
        warnings=["Avoid foliar fertilizer application."],
        supporting_forecast_reference={"forecast_id": 1, "forecast_date": "2026-09-04", "downscaled_rainfall_mm": 12.8},
    )
    assert output.severity == AdvisorySeverityEnum.MODERATE
    assert len(output.recommended_actions) == 2


def test_missing_required_ai_fields():
    """Verify that omitting mandatory structured fields (e.g. what_is_happening) raises ValidationError."""
    with pytest.raises(ValidationError):
        AIAdvisoryOutputContract(
            summary="Moderate Rainfall Advisory",
            # what_is_happening missing
            why_it_matters="Impact on standing crops.",
            recommended_actions=["Delay spraying."],
            timing="24 hours",
            severity=AdvisorySeverityEnum.MODERATE,
            supporting_forecast_reference={"forecast_id": 1},
        )


def test_empty_recommended_actions_rejected():
    """Verify that empty recommended_actions is rejected by schema."""
    with pytest.raises(ValidationError):
        AIAdvisoryOutputContract(
            summary="Moderate Rainfall Advisory",
            what_is_happening="Rain expected.",
            why_it_matters="Impact on crops.",
            recommended_actions=[],  # Empty list forbidden
            timing="24 hours",
            severity=AdvisorySeverityEnum.MODERATE,
            supporting_forecast_reference={"forecast_id": 1},
        )


# =============================================================================
# 5. SAFETY VALIDATION GUARDRAILS TESTS
# =============================================================================

def test_safety_validation_pass(sample_input_contract):
    """Verify that compliant AI output passes safety validation."""
    valid_output = AIAdvisoryOutputContract(
        summary="Moderate Rainfall Advisory for Ajmer Saundane",
        what_is_happening="Expected rainfall of 12.8 mm across the Gram Panchayat.",
        why_it_matters="High surface moisture risk.",
        recommended_actions=["Postpone chemical spraying until dry weather returns."],
        timing="Next 24 hours",
        severity=AdvisorySeverityEnum.MODERATE,
        warnings=[],
        supporting_forecast_reference={"forecast_id": 1, "forecast_date": "2026-09-04", "downscaled_rainfall_mm": 12.8},
    )
    report = validate_advisory_safety(sample_input_contract, valid_output)
    assert report.is_valid is True
    assert len(report.violations) == 0
    assert report.weather_consistency_passed is True
    assert report.dosage_safety_passed is True
    assert report.fallback_required is False


def test_safety_validation_catches_numerical_hallucination(sample_input_contract):
    """Verify that AI fabricating different rainfall numbers is flagged as violation."""
    hallucinated_output = AIAdvisoryOutputContract(
        summary="Heavy Storm Warning for Ajmer Saundane",
        what_is_happening="Downscaled forecast predicts 85.0 mm of rainfall (fabricated).",
        why_it_matters="Risk of flood.",
        recommended_actions=["Move equipment to higher ground."],
        timing="Next 24 hours",
        severity=AdvisorySeverityEnum.HIGH,
        warnings=[],
        supporting_forecast_reference={"forecast_id": 1},
    )
    report = validate_advisory_safety(sample_input_contract, hallucinated_output)
    assert report.is_valid is False
    assert report.weather_consistency_passed is False
    assert report.fallback_required is True
    assert any("Numerical weather inconsistency" in v for v in report.violations)


def test_safety_validation_catches_chemical_dosage_instructions(sample_input_contract):
    """Verify that prescribing chemical dosages triggers safety violation."""
    dosage_output = AIAdvisoryOutputContract(
        summary="Pest Treatment Advisory",
        what_is_happening="Rainfall of 12.8 mm will create pest conditions.",
        why_it_matters="Fungal infestation risk.",
        recommended_actions=["Apply Chlorpyrifos at 250 ml per acre immediately."],
        timing="Immediate",
        severity=AdvisorySeverityEnum.MODERATE,
        warnings=[],
        supporting_forecast_reference={"forecast_id": 1},
    )
    report = validate_advisory_safety(sample_input_contract, dosage_output)
    assert report.is_valid is False
    assert report.dosage_safety_passed is False
    assert report.fallback_required is True
    assert any("Chemical dosage safety violation" in v for v in report.violations)


def test_safety_validation_catches_medical_or_emergency_claims(sample_input_contract):
    """Verify that medical advice or unsupported emergency panics are blocked."""
    prohibited_output = AIAdvisoryOutputContract(
        summary="Emergency Weather Warning",
        what_is_happening="Rainfall of 12.8 mm approaching.",
        why_it_matters="Severe conditions.",
        recommended_actions=["Initiate emergency evacuation immediately and run for your life."],
        timing="Immediate",
        severity=AdvisorySeverityEnum.CRITICAL,
        warnings=[],
        supporting_forecast_reference={"forecast_id": 1},
    )
    report = validate_advisory_safety(sample_input_contract, prohibited_output)
    assert report.is_valid is False
    assert report.hallucination_check_passed is False
    assert report.fallback_required is True


# =============================================================================
# 6. CONTEXT BUILDER TESTS
# =============================================================================

def test_context_builder_from_models():
    """Verify context builder creates compliant input and traceability contracts from ORM objects."""
    district = District(id=1, name="Nashik")
    block = Block(id=10, name="Baglan", district_id=1, district=district)
    panchayat = Panchayat(
        id=1001,
        name="Ajmer Saundane",
        panchayat_code="P_1001",
        lgd_code=253123,
        block_id=10,
        district_id=1,
        block=block,
        district=district,
        latitude=20.5982,
        longitude=74.1201,
        elevation_m=585.0,
    )
    forecast = DownscaledForecast(
        id=1,
        panchayat_id=1001,
        forecast_date=date(2026, 9, 4),
        forecast_issue_date=date(2026, 9, 4),
        block_forecast_rainfall_mm=15.0,
        downscaled_rainfall_mm=12.78,
        model_name="XGBoost Regressor",
        model_version="v1.0.0",
        confidence=None,
    )

    # 1. Build AI Input Contract
    ai_input = build_ai_advisory_input(panchayat, forecast, target_language="en")
    assert ai_input.panchayat_context.panchayat_name == "Ajmer Saundane"
    assert ai_input.panchayat_context.block_name == "Baglan"
    assert ai_input.forecast_context.downscaled_rainfall_mm == 12.78
    assert len(ai_input.risks) >= 1
    assert len(ai_input.deterministic_recommendations.recommended_actions) >= 1

    # 2. Build Traceability Contract
    trace = build_traceability_record(
        panchayat,
        forecast,
        advisory_source=AdvisorySourceEnum.AI_AUGMENTED,
        ai_provider="OLLAMA_LOCAL",
        ai_model="llama3:8b",
        ai_prompt_version="v1.0.0",
    )
    assert trace.panchayat_id == 1001
    assert trace.forecast_id == 1
    assert trace.downscaled_rainfall_mm == 12.78
    assert trace.advisory_source == AdvisorySourceEnum.AI_AUGMENTED
    assert trace.ai_provider == "OLLAMA_LOCAL"


def test_context_builder_rejects_null_entities():
    """Verify builder raises ContextBuilderError if required entities are null."""
    with pytest.raises(ContextBuilderError):
        build_panchayat_context(None)

    with pytest.raises(ContextBuilderError):
        build_forecast_context(None)


# =============================================================================
# 7. BACKWARD COMPATIBILITY WITH EXISTING SCHEMAS
# =============================================================================

def test_backward_compatibility_with_existing_schemas():
    """Verify that existing Forecast and Advisory response schemas remain intact."""
    forecast_resp = ForecastRetrievalResponse(
        panchayat_id=1001,
        panchayat_name="Ajmer Saundane",
        block_name="Baglan",
        district_name="Nashik",
        forecast_date=date(2026, 9, 4),
        forecast_issue_date=date(2026, 9, 4),
        lead_days=0,
        block_forecast_rainfall_mm=15.0,
        downscaled_rainfall_mm=12.78,
        model_name="XGBoost Regressor",
        model_version="v1.0.0",
        confidence=None,
    )
    assert forecast_resp.panchayat_id == 1001

    advisory_resp = AdvisoryResponse(
        id=1,
        panchayat_id=1001,
        forecast_id=1,
        forecast_date=date(2026, 9, 4),
        rainfall_mm=12.78,
        rainfall_category="Moderate rainfall",
        severity="MODERATE",
        advisory_title="Moderate Rain Advisory",
        advisory_text="• Postpone spraying.",
        rule_version="v1.0.0",
        status="DRAFT",
    )
    assert advisory_resp.id == 1
    assert advisory_resp.status == "DRAFT"
