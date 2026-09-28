"""
Phase 5.2 Deterministic Agricultural Rule Engine Unit & Integration Tests.

Validates:
1. Dry weather / no rain (0.0 mm) evaluation and operational guidance.
2. Very light rain (<= 2.5 mm) routine farm management window.
3. Foliar spraying wash-off threshold trigger (> 2.5 mm).
4. Fertilizer leaching and tillage restrictions on moderate rain (> 15.5 mm).
5. Heavy rainfall waterlogging and drainage alerts (> 64.4 mm).
6. Very heavy rainfall extreme inundation hazard (> 115.5 mm).
7. Missing optional variables handling (safe skip of heat stress rule when temperature is None).
8. Conditional triggering of heat stress rule when temperature is supplied.
9. Configurable rule disabling and custom rule injection.
10. Priority ordering and de-duplicated recommendations.
11. Evaluation audit trace completeness and threshold provenance documentation.
"""

from datetime import date
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
)


def create_mock_forecast(
    rainfall_mm: float,
    temperature_c: float = None,
) -> ForecastContext:
    """Helper to create a ForecastContext for testing."""
    return ForecastContext(
        forecast_id=101,
        forecast_date=date(2026, 9, 10),
        forecast_issue_date=date(2026, 9, 10),
        lead_days=0,
        block_forecast_rainfall_mm=max(0.0, rainfall_mm),
        downscaled_rainfall_mm=float(rainfall_mm),
        rainfall_category="Test Category",
        model_name="XGBoost Regressor",
        model_version="v1.0.0",
        confidence=None,
        temperature_c=temperature_c,
    )


# =============================================================================
# 1. DRY WEATHER & VERY LIGHT RAINFALL
# =============================================================================

def test_dry_weather_evaluation():
    """Verify 0.0 mm rainfall triggers routine irrigation and safe operational windows."""
    fc = create_mock_forecast(0.0)
    result = default_rule_engine.evaluate(fc)

    # Risk checks
    risk_types = [r.risk_type for r in result.risks]
    assert "MOISTURE_DEFICIT_MONITORING" in risk_types

    # Operational guidance
    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "SAFE_WINDOW"
    assert guidance["tillage"] == "PERMITTED"
    assert guidance["drainage"] == "NORMAL"
    assert guidance["irrigation"] == "CONTINUE_NORMAL"

    # Highest severity should be LOW
    severities = [r.severity for r in result.risks]
    assert AdvisorySeverityEnum.HIGH not in severities
    assert AdvisorySeverityEnum.CRITICAL not in severities


def test_very_light_rainfall_evaluation():
    """Verify 1.5 mm rainfall triggers standard farm operations."""
    fc = create_mock_forecast(1.5)
    result = default_rule_engine.evaluate(fc)

    risk_types = [r.risk_type for r in result.risks]
    assert "MINIMAL_WEATHER_IMPACT" in risk_types
    assert "SPRAY_WASHOFF" not in risk_types  # Below 2.5 mm threshold

    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "SAFE_WINDOW"
    assert guidance["tillage"] == "PERMITTED"


# =============================================================================
# 2. SPRAYING & IRRIGATION THRESHOLDS (> 2.5 MM)
# =============================================================================

def test_spraying_washoff_trigger():
    """Verify rainfall > 2.5 mm triggers spray postponement and irrigation suspension."""
    fc = create_mock_forecast(8.0)
    result = default_rule_engine.evaluate(fc)

    risk_types = [r.risk_type for r in result.risks]
    assert "SPRAY_WASHOFF" in risk_types
    assert "SURFACE_MOISTURE_EXCESS" in risk_types

    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "POSTPONE"
    assert guidance["irrigation"] == "SUSPEND"

    # Does not trigger heavy tillage/drainage rules
    assert "WATERLOGGING" not in risk_types
    assert "SOIL_COMPACTION" not in risk_types


# =============================================================================
# 3. MODERATE RAINFALL THRESHOLDS (> 15.5 MM)
# =============================================================================

def test_moderate_rainfall_restrictions():
    """Verify rainfall > 15.5 mm restricts tillage, fertilizer broadcasting, and prompts harvest shelter."""
    fc = create_mock_forecast(25.0)
    result = default_rule_engine.evaluate(fc)

    risk_types = [r.risk_type for r in result.risks]
    assert "SPRAY_WASHOFF" in risk_types
    assert "SOIL_COMPACTION" in risk_types
    assert "RUNOFF_LEACHING" in risk_types
    assert "GRAIN_DAMAGE" in risk_types

    guidance = result.recommendation_context.operational_guidance
    assert guidance["spraying"] == "POSTPONE"
    assert guidance["tillage"] == "DELAY"
    assert guidance["fertilizer"] == "DELAY"
    assert guidance["harvest"] == "SHELTER_PRODUCE"

    # Still below heavy waterlogging threshold (64.4 mm)
    assert "WATERLOGGING" not in risk_types


# =============================================================================
# 4. HEAVY & VERY HEAVY RAINFALL THRESHOLDS (> 64.4 MM, > 115.5 MM)
# =============================================================================

def test_heavy_rainfall_drainage_alert():
    """Verify rainfall > 64.4 mm triggers drainage trenching and HIGH severity."""
    fc = create_mock_forecast(75.0)
    result = default_rule_engine.evaluate(fc)

    risk_types = [r.risk_type for r in result.risks]
    assert "WATERLOGGING" in risk_types

    guidance = result.recommendation_context.operational_guidance
    assert guidance["drainage"] == "OPEN_TRENCHES"

    severities = [r.severity for r in result.risks]
    assert AdvisorySeverityEnum.HIGH in severities


def test_extreme_inundation_hazard():
    """Verify rainfall > 115.5 mm triggers CRITICAL hazard and HALT_ALL operational directive."""
    fc = create_mock_forecast(135.0)
    result = default_rule_engine.evaluate(fc)

    risk_types = [r.risk_type for r in result.risks]
    assert "SEVERE_INUNDATION" in risk_types

    guidance = result.recommendation_context.operational_guidance
    assert guidance["operations"] == "HALT_ALL"

    # Most severe risk is CRITICAL and ranked first
    assert result.risks[0].severity == AdvisorySeverityEnum.CRITICAL
    assert result.risks[0].risk_type == "SEVERE_INUNDATION"


# =============================================================================
# 5. MISSING OPTIONAL WEATHER VARIABLES SAFE SKIP
# =============================================================================

def test_missing_temperature_variable_skipped_safely():
    """Verify that when temperature_c is None, temperature rules are skipped without error."""
    fc = create_mock_forecast(0.0, temperature_c=None)
    result = default_rule_engine.evaluate(fc)

    # Heat stress rule must NOT be in triggered rules
    triggered_ids = [r.rule_id for r in result.triggered_rules]
    assert "AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1" not in triggered_ids

    # Trace must document the skip reason explicitly
    traces = {t.rule_id: t for t in result.evaluation_trace}
    heat_trace = traces["AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1"]
    assert heat_trace.skipped is True
    assert "temperature_c" in heat_trace.skip_reason


def test_conditional_temperature_trigger_when_present():
    """Verify that when temperature_c is provided and exceeds threshold, rule triggers."""
    fc = create_mock_forecast(0.0, temperature_c=41.5)
    result = default_rule_engine.evaluate(fc)

    triggered_ids = [r.rule_id for r in result.triggered_rules]
    assert "AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1" in triggered_ids

    risk_types = [r.risk_type for r in result.risks]
    assert "HEAT_STRESS" in risk_types


# =============================================================================
# 6. CONFIGURABILITY, PRIORITY & AUDIT TRACE
# =============================================================================

def test_disabled_rule_not_evaluated():
    """Verify that disabled rules are skipped in evaluation."""
    disabled_rules = [
        AgriculturalRuleDefinition(
            rule_id="RULE_TEST_DISABLED",
            rule_version="v1.0.0",
            rule_name="Disabled Test Rule",
            category=RuleCategory.SPRAYING,
            enabled=False,  # Disabled
            input_variables=["downscaled_rainfall_mm"],
            condition_operator=ComparisonOperator.GREATER_THAN,
            threshold_value=0.0,
            threshold_unit="mm",
            threshold_source="Test",
            is_prototype=True,
            severity=AdvisorySeverityEnum.HIGH,
            risk_type="TEST_RISK",
            recommendation="Test recommendation",
            timing="Immediate",
            explanation="Test explanation",
            priority=1,
        )
    ]
    custom_engine = DeterministicRuleEngine(rules=disabled_rules)
    fc = create_mock_forecast(50.0)
    result = custom_engine.evaluate(fc)

    assert len(result.triggered_rules) == 0
    assert len(result.risks) == 0
    assert result.evaluation_trace[0].skipped is True


def test_priority_ordering_of_recommendations():
    """Verify that higher priority (lower number) recommendations appear earlier."""
    fc = create_mock_forecast(120.0)  # Extreme rain
    result = default_rule_engine.evaluate(fc)

    # First recommendation must be the highest priority (priority=1 extreme inundation)
    assert len(result.recommendation_context.recommended_actions) >= 3
    assert "suspend all open-field operations" in result.recommendation_context.recommended_actions[0].lower()


def test_evaluation_trace_documentation():
    """Verify every rule has threshold source provenance documented."""
    for rule in DEFAULT_AGRICULTURAL_RULES:
        assert rule.threshold_source is not None
        assert len(rule.threshold_source.strip()) > 0
        assert rule.rule_id.startswith("AGRO_RULE_")
        assert rule.priority >= 1
