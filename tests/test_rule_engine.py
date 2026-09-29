"""
Phase 5.2 Deterministic Agricultural Rule Engine Test Suite.

Comprehensive validation covering:
1. No rule triggered scenario.
2. Single rainfall rule triggered.
3. Multiple rules triggered simultaneously.
4. Exact boundary threshold behavior (0.0, 2.5, 15.5, 64.4, 115.5 mm).
5. Missing rainfall handling (never assumes 0 mm).
6. Missing temperature handling (temperature rules skipped safely).
7. Invalid numeric values handling (NaN, Inf, negative rainfall rejected).
8. Missing Panchayat context validation error handling.
9. Missing forecast date handling (suppresses timing-dependent claims).
10. Duplicate recommendation prevention.
11. Multiple-risk ordering (CRITICAL > HIGH > MODERATE > LOW).
12. Rule version and rule ID preservation.
13. Deterministic repeatability (Input A -> Output A == Output A).
14. Real-data verification using persisted Nashik & Pune records.
"""

from datetime import date
import math
import pytest

from backend.app.schemas.advisory_contracts import (
    ForecastContext,
    PanchayatContext,
    AdvisorySeverityEnum,
)
from src.advisory.rule_engine import (
    DeterministicRuleEngine,
    AgriculturalRuleDefinition,
    RuleCategory,
    ComparisonOperator,
    DEFAULT_AGRICULTURAL_RULES,
    default_rule_engine,
    RuleEngineValidationError,
    RULE_ENGINE_VERSION,
)
from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.panchayat import Panchayat
from src.advisory.context_builder import build_forecast_context, build_panchayat_context


def make_forecast(
    rainfall_mm: float = None,
    temperature_c: float = None,
    forecast_date: date = date(2026, 9, 10),
    forecast_id: int = 101,
) -> ForecastContext:
    """Helper creating a ForecastContext."""
    return ForecastContext(
        forecast_id=forecast_id,
        forecast_date=forecast_date,
        forecast_issue_date=forecast_date,
        lead_days=0,
        block_forecast_rainfall_mm=max(0.0, rainfall_mm) if rainfall_mm is not None else 0.0,
        downscaled_rainfall_mm=float(rainfall_mm) if rainfall_mm is not None else 0.0,
        rainfall_category="Test",
        model_name="XGBoost Regressor",
        model_version="v1.0.0",
        confidence=None,
        temperature_c=temperature_c,
    )


# =============================================================================
# 1. NO RULE TRIGGERED
# =============================================================================

def test_no_rule_triggered_when_all_rules_disabled():
    """Verify that when no rules are enabled, engine produces empty risks and fallback action."""
    disabled_rules = [
        AgriculturalRuleDefinition(
            rule_id="RULE_TEST_OFF",
            rule_version="v1.0.0",
            rule_name="Off Rule",
            category=RuleCategory.SPRAYING,
            enabled=False,
            input_variables=["downscaled_rainfall_mm"],
            condition_operator=ComparisonOperator.GREATER_THAN,
            threshold_value=1.0,
            threshold_unit="mm",
            threshold_source="Test",
            is_prototype=True,
            severity=AdvisorySeverityEnum.HIGH,
            risk_type="TEST",
            recommendation="Test action",
            timing="Immediate",
            explanation="Test explanation",
            priority=1,
        )
    ]
    engine = DeterministicRuleEngine(rules=disabled_rules)
    fc = make_forecast(rainfall_mm=50.0)
    result = engine.evaluate(fc)

    assert len(result.triggered_rules) == 0
    assert len(result.risks) == 0
    assert "Maintain routine crop monitoring" in result.recommendation_context.recommended_actions[0]
    assert result.evaluation_trace[0].skipped is True


# =============================================================================
# 2. SINGLE RAINFALL RULE TRIGGERED
# =============================================================================

def test_single_rainfall_rule_triggered():
    """Verify light rain of 1.2 mm triggers only the routine very light rain rule."""
    fc = make_forecast(rainfall_mm=1.2)
    result = default_rule_engine.evaluate(fc)

    triggered_ids = [r.rule_id for r in result.triggered_rules]
    assert triggered_ids == ["AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1"]
    assert len(result.risks) == 1
    assert result.risks[0].risk_type == "MINIMAL_WEATHER_IMPACT"
    assert result.risks[0].severity == AdvisorySeverityEnum.LOW
    assert result.recommendation_context.operational_guidance["spraying"] == "SAFE_WINDOW"


# =============================================================================
# 3. MULTIPLE RULES TRIGGERED
# =============================================================================

def test_multiple_rules_triggered_simultaneously():
    """Verify 25.0 mm moderate rain triggers multiple concurrent agricultural rules."""
    fc = make_forecast(rainfall_mm=25.0)
    result = default_rule_engine.evaluate(fc)

    triggered_ids = set(r.rule_id for r in result.triggered_rules)
    assert "AGRO_RULE_SPRAY_WASHOFF_V1" in triggered_ids
    assert "AGRO_RULE_IRRIGATION_SUSPENSION_V1" in triggered_ids
    assert "AGRO_RULE_TILLAGE_RESTRICTION_V1" in triggered_ids
    assert "AGRO_RULE_FERTILIZER_LEACHING_V1" in triggered_ids
    assert "AGRO_RULE_HARVEST_SHELTER_V1" in triggered_ids

    # Waterlogging (> 64.4 mm) must NOT be triggered
    assert "AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1" not in triggered_ids

    # Multiple risks generated
    assert len(result.risks) == 5
    # Operational guidance tags
    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "POSTPONE"
    assert guidance["tillage"] == "DELAY"
    assert guidance["fertilizer"] == "DELAY"
    assert guidance["harvest"] == "SHELTER_PRODUCE"
    assert guidance["irrigation"] == "SUSPEND"


# =============================================================================
# 4. BOUNDARY THRESHOLD BEHAVIOR
# =============================================================================

@pytest.mark.parametrize(
    "rainfall_mm, expected_triggered_id, unexpected_triggered_id",
    [
        (0.0, "AGRO_RULE_DRY_WEATHER_IRRIGATION_V1", "AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1"),
        (0.05, "AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1", "AGRO_RULE_DRY_WEATHER_IRRIGATION_V1"),
        (2.5, "AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1", "AGRO_RULE_SPRAY_WASHOFF_V1"),
        (2.51, "AGRO_RULE_SPRAY_WASHOFF_V1", "AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1"),
        (15.5, "AGRO_RULE_SPRAY_WASHOFF_V1", "AGRO_RULE_TILLAGE_RESTRICTION_V1"),
        (15.51, "AGRO_RULE_TILLAGE_RESTRICTION_V1", "AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1"),
        (64.4, "AGRO_RULE_TILLAGE_RESTRICTION_V1", "AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1"),
        (64.41, "AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1", "AGRO_RULE_EXTREME_INUNDATION_V1"),
        (115.5, "AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1", "AGRO_RULE_EXTREME_INUNDATION_V1"),
        (115.51, "AGRO_RULE_EXTREME_INUNDATION_V1", None),
    ],
)
def test_boundary_threshold_behavior(rainfall_mm, expected_triggered_id, unexpected_triggered_id):
    """Verify inclusive/exclusive boundaries for all agronomic threshold transitions."""
    fc = make_forecast(rainfall_mm=rainfall_mm)
    result = default_rule_engine.evaluate(fc)
    triggered_ids = set(r.rule_id for r in result.triggered_rules)

    assert expected_triggered_id in triggered_ids
    if unexpected_triggered_id:
        assert unexpected_triggered_id not in triggered_ids


# =============================================================================
# 5. MISSING RAINFALL HANDLING (NEVER ASSUME 0 MM)
# =============================================================================

def test_missing_rainfall_never_assumes_zero():
    """Verify that missing rainfall never assumes 0.0 mm and evaluates safely without triggers."""
    class ForecastWithNoneRainfall:
        downscaled_rainfall_mm = None
        block_forecast_rainfall_mm = None
        lead_days = 0
        forecast_date = date(2026, 9, 10)
        temperature_c = None
        humidity_pct = None
        wind_speed_kmh = None
        soil_moisture_index = None

    result = default_rule_engine.evaluate(ForecastWithNoneRainfall())

    # Dry weather (0.0 mm) rule MUST NOT trigger!
    triggered_ids = [r.rule_id for r in result.triggered_rules]
    assert "AGRO_RULE_DRY_WEATHER_IRRIGATION_V1" not in triggered_ids
    assert len(result.risks) == 0

    # Operational guidance flags unknown
    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "UNKNOWN"
    assert guidance["drainage"] == "UNKNOWN"

    # Validation errors must note unavailable rainfall
    assert any("Rainfall forecast data is unavailable" in err for err in result.validation_errors)

    # Traces must show skipped
    rf_traces = [t for t in result.evaluation_trace if "downscaled_rainfall_mm" in t.condition]
    assert all(t.skipped is True for t in rf_traces)


# =============================================================================
# 6. MISSING TEMPERATURE HANDLING
# =============================================================================

def test_missing_temperature_skips_heat_rules():
    """Verify missing temperature safely skips temperature-dependent rules."""
    fc = make_forecast(rainfall_mm=0.0, temperature_c=None)
    result = default_rule_engine.evaluate(fc)

    triggered_ids = [r.rule_id for r in result.triggered_rules]
    assert "AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1" not in triggered_ids

    trace = next(t for t in result.evaluation_trace if t.rule_id == "AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1")
    assert trace.skipped is True
    assert "temperature_c" in trace.skip_reason


# =============================================================================
# 7. INVALID NUMERIC VALUES
# =============================================================================

@pytest.mark.parametrize(
    "invalid_val",
    [float("nan"), float("inf"), float("-inf"), -5.0, "invalid_str"],
)
def test_invalid_numeric_values_rejected(invalid_val):
    """Verify invalid numeric values (NaN, Inf, negative rainfall) are rejected safely."""
    class CorruptForecast:
        downscaled_rainfall_mm = invalid_val
        block_forecast_rainfall_mm = 0.0
        lead_days = 0
        forecast_date = date(2026, 9, 10)
        temperature_c = None
        humidity_pct = None
        wind_speed_kmh = None
        soil_moisture_index = None

    result = default_rule_engine.evaluate(CorruptForecast())
    assert len(result.triggered_rules) == 0
    assert len(result.risks) == 0
    assert any("Invalid rainfall value" in err or "unavailable" in err for err in result.validation_errors)


# =============================================================================
# 8. MISSING PANCHAYAT CONTEXT
# =============================================================================

def test_missing_panchayat_context_validation_error():
    """Verify missing Panchayat context records structured validation warning or raises in strict mode."""
    fc = make_forecast(rainfall_mm=10.0)

    # Non-strict mode records validation warning
    result = default_rule_engine.evaluate(fc, panchayat_context=None, require_panchayat=False)
    assert any("Panchayat context is missing" in err for err in result.validation_errors)

    # Strict mode raises RuleEngineValidationError
    with pytest.raises(RuleEngineValidationError) as exc_info:
        default_rule_engine.evaluate(fc, panchayat_context=None, require_panchayat=True)
    assert exc_info.value.field == "panchayat_context"


# =============================================================================
# 9. MISSING FORECAST DATE
# =============================================================================

def test_missing_forecast_date_suppresses_timing():
    """Verify missing forecast date flags timing as unavailable."""
    class NoDateForecast:
        downscaled_rainfall_mm = 80.0
        block_forecast_rainfall_mm = 80.0
        lead_days = 0
        forecast_date = None
        temperature_c = None
        humidity_pct = None
        wind_speed_kmh = None
        soil_moisture_index = None

    result = default_rule_engine.evaluate(NoDateForecast())
    assert result.recommendation_context.timing_window == "Timing unavailable (missing forecast date)"
    assert any("Forecast date is missing" in err for err in result.validation_errors)


# =============================================================================
# 10. DUPLICATE RECOMMENDATION PREVENTION
# =============================================================================

def test_duplicate_recommendation_prevention():
    """Verify identical recommendation strings from multiple rules are deduplicated."""
    dup_rules = [
        AgriculturalRuleDefinition(
            rule_id="RULE_A",
            rule_version="v1.0.0",
            rule_name="Rule A",
            category=RuleCategory.SPRAYING,
            enabled=True,
            input_variables=["downscaled_rainfall_mm"],
            condition_operator=ComparisonOperator.GREATER_THAN,
            threshold_value=1.0,
            threshold_unit="mm",
            threshold_source="Test",
            is_prototype=True,
            severity=AdvisorySeverityEnum.MODERATE,
            risk_type="RISK_A",
            recommendation="Shared Action String",
            timing="Immediate",
            explanation="Exp A",
            priority=1,
        ),
        AgriculturalRuleDefinition(
            rule_id="RULE_B",
            rule_version="v1.0.0",
            rule_name="Rule B",
            category=RuleCategory.DRAINAGE,
            enabled=True,
            input_variables=["downscaled_rainfall_mm"],
            condition_operator=ComparisonOperator.GREATER_THAN,
            threshold_value=2.0,
            threshold_unit="mm",
            threshold_source="Test",
            is_prototype=True,
            severity=AdvisorySeverityEnum.HIGH,
            risk_type="RISK_B",
            recommendation="Shared Action String",  # Exact duplicate
            timing="Immediate",
            explanation="Exp B",
            priority=2,
        ),
    ]
    engine = DeterministicRuleEngine(rules=dup_rules)
    fc = make_forecast(rainfall_mm=10.0)
    result = engine.evaluate(fc)

    assert len(result.triggered_rules) == 2
    actions = result.recommendation_context.recommended_actions
    assert actions.count("Shared Action String") == 1


# =============================================================================
# 11. MULTIPLE-RISK ORDERING
# =============================================================================

def test_multiple_risk_severity_ordering():
    """Verify risks are sorted deterministically: CRITICAL > HIGH > MODERATE > LOW."""
    fc = make_forecast(rainfall_mm=140.0)  # Extreme rain triggers CRITICAL, HIGH, MODERATE, LOW
    result = default_rule_engine.evaluate(fc)

    severities = [r.severity for r in result.risks]
    assert len(severities) >= 4

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    ranks = [severity_order[s.value] for s in severities]
    assert ranks == sorted(ranks), f"Risks not ordered by severity: {severities}"


# =============================================================================
# 12. RULE VERSION PRESERVATION
# =============================================================================

def test_rule_version_preservation():
    """Verify all triggered risks preserve the rule_id and rule_version of their source rule."""
    fc = make_forecast(rainfall_mm=80.0)
    result = default_rule_engine.evaluate(fc)

    rule_map = {r.rule_id: r for r in DEFAULT_AGRICULTURAL_RULES}
    for risk in result.risks:
        source_rule = rule_map[risk.rule_id]
        assert risk.rule_version == source_rule.rule_version
        assert risk.rule_id == source_rule.rule_id
        assert risk.rule_version == RULE_ENGINE_VERSION


# =============================================================================
# 13. DETERMINISM
# =============================================================================

def test_rule_engine_deterministic_repeatability():
    """Verify identical forecast input yields identical output across repeated evaluations."""
    fc = make_forecast(rainfall_mm=45.2, temperature_c=36.5)

    result_1 = default_rule_engine.evaluate(fc)
    result_2 = default_rule_engine.evaluate(fc)

    assert len(result_1.risks) == len(result_2.risks)
    assert [r.rule_id for r in result_1.risks] == [r.rule_id for r in result_2.risks]
    assert [r.severity for r in result_1.risks] == [r.severity for r in result_2.risks]
    assert (
        result_1.recommendation_context.recommended_actions
        == result_2.recommendation_context.recommended_actions
    )
    assert (
        result_1.recommendation_context.operational_guidance
        == result_2.recommendation_context.operational_guidance
    )
    assert (
        result_1.recommendation_context.timing_window
        == result_2.recommendation_context.timing_window
    )


# =============================================================================
# 14. REAL-DATA VERIFICATION (NASHIK & PUNE PERSISTED RECORDS)
# =============================================================================

def test_real_data_verification_nashik_and_pune():
    """
    Real-data verification using actual persisted database records from Nashik and Pune.
    Ensures:
      - Accepts actual Phase 2 forecast output.
      - Produces valid structured risk output.
      - Does not alter numerical forecasts.
      - Does not fabricate recommendations from missing variables.
      - Functions dynamically for both Nashik and Pune without hardcoding.
    """
    db = SessionLocal()
    try:
        # 1. Fetch real Nashik forecast (Panchayat 1001, Ajmer Saundane)
        nashik_panchayat = db.query(Panchayat).filter(Panchayat.id == 1001).first()
        nashik_forecast = (
            db.query(DownscaledForecast)
            .filter(DownscaledForecast.panchayat_id == 1001)
            .first()
        )
        assert nashik_panchayat is not None, "Real Nashik Panchayat record 1001 not found"
        assert nashik_forecast is not None, "Real Nashik DownscaledForecast record not found"

        nashik_p_ctx = build_panchayat_context(nashik_panchayat)
        nashik_f_ctx = build_forecast_context(nashik_forecast)

        # Record original downscaled rainfall
        orig_nashik_rf = nashik_f_ctx.downscaled_rainfall_mm

        # Evaluate through rule engine
        nashik_result = default_rule_engine.evaluate(
            nashik_f_ctx, panchayat_context=nashik_p_ctx
        )

        # Verification checks
        assert nashik_f_ctx.downscaled_rainfall_mm == orig_nashik_rf  # Did NOT modify forecast
        assert isinstance(nashik_result.risks, list)
        assert len(nashik_result.evaluation_trace) == len(DEFAULT_AGRICULTURAL_RULES)
        # Ensure optional variables were NOT fabricated
        assert nashik_f_ctx.temperature_c is None
        assert not any(r.rule_id == "AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1" for r in nashik_result.triggered_rules)

        # 2. Fetch real Pune forecast (Panchayat 185262, Ahupe)
        pune_panchayat = db.query(Panchayat).filter(Panchayat.id == 185262).first()
        pune_forecast = (
            db.query(DownscaledForecast)
            .filter(DownscaledForecast.panchayat_id == 185262)
            .first()
        )
        assert pune_panchayat is not None, "Real Pune Panchayat record 185262 not found"
        assert pune_forecast is not None, "Real Pune DownscaledForecast record not found"

        pune_p_ctx = build_panchayat_context(pune_panchayat)
        pune_f_ctx = build_forecast_context(pune_forecast)

        orig_pune_rf = pune_f_ctx.downscaled_rainfall_mm

        pune_result = default_rule_engine.evaluate(
            pune_f_ctx, panchayat_context=pune_p_ctx
        )

        assert pune_f_ctx.downscaled_rainfall_mm == orig_pune_rf  # Did NOT modify forecast
        assert isinstance(pune_result.risks, list)
        assert len(pune_result.recommendation_context.recommended_actions) >= 1

        # District independence: Nashik is Nashik, Pune is Pune
        assert nashik_p_ctx.district_name == "Nashik"
        assert pune_p_ctx.district_name == "Pune"
        assert nashik_p_ctx.panchayat_id != pune_p_ctx.panchayat_id
    finally:
        db.close()
