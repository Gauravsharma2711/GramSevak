"""
Phase 5 Deterministic Agricultural Risk and Recommendation Rule Engine.

Converts validated Panchayat-level weather context into deterministic agricultural
risks, operational guidance, and actionable baseline recommendations.

Design & Architectural Invariants:
1. Purely deterministic and explainable: NO LLM, NO non-deterministic heuristics.
2. Grounded in validated meteorological (IMD) and agronomic (ICAR) guidelines.
3. Every evaluated rule produces an explicit audit trace explaining why it triggered or skipped.
4. Input-aware: Only evaluates rules for weather variables that actually exist. If optional
   variables (e.g., temperature, wind) are absent, corresponding rules are safely skipped.
5. Configurable and machine-readable: Centralized catalog for domain review.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

from backend.app.schemas.advisory_contracts import (
    ForecastContext,
    PanchayatContext,
    AgriculturalRiskItem,
    DeterministicRecommendationContext,
    AdvisorySeverityEnum,
)

logger = logging.getLogger(__name__)

RULE_ENGINE_VERSION = "v1.0.0"


# =============================================================================
# 1. ENUMS AND RULE METADATA CONTRACTS
# =============================================================================

class RuleCategory(str, Enum):
    """Agronomic domain category for rule classification."""
    SPRAYING = "SPRAYING"
    IRRIGATION = "IRRIGATION"
    DRAINAGE = "DRAINAGE"
    FIELD_OPERATIONS = "FIELD_OPERATIONS"
    FERTILIZER = "FERTILIZER"
    HARVEST = "HARVEST"
    EXTREME_WEATHER = "EXTREME_WEATHER"
    TEMPERATURE_STRESS = "TEMPERATURE_STRESS"


class ComparisonOperator(str, Enum):
    """Supported mathematical comparison operators for rule conditions."""
    GREATER_THAN = ">"
    GREATER_THAN_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_EQUAL = "<="
    EQUAL = "=="
    BETWEEN = "BETWEEN"  # [min, max] inclusive


@dataclass(frozen=True)
class AgriculturalRuleDefinition:
    """
    Standardized, machine-readable rule definition contract.
    Contains full agronomic metadata, threshold provenance, and operational guidance.
    """
    rule_id: str
    rule_version: str
    rule_name: str
    category: RuleCategory
    enabled: bool
    input_variables: List[str]
    condition_operator: ComparisonOperator
    threshold_value: Any
    threshold_unit: str
    threshold_source: str
    is_prototype: bool
    severity: AdvisorySeverityEnum
    risk_type: str
    recommendation: str
    timing: str
    explanation: str
    priority: int  # 1 = critical hazard, 10 = standard advisory
    operational_action_key: Optional[str] = None  # e.g., 'spraying', 'tillage', 'drainage'
    operational_action_value: Optional[str] = None  # e.g., 'POSTPONE', 'SAFE_WINDOW'

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule definition to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "enabled": self.enabled,
            "input_variables": self.input_variables,
            "condition_operator": self.condition_operator.value,
            "threshold_value": self.threshold_value,
            "threshold_unit": self.threshold_unit,
            "threshold_source": self.threshold_source,
            "is_prototype": self.is_prototype,
            "severity": self.severity.value,
            "risk_type": self.risk_type,
            "recommendation": self.recommendation,
            "timing": self.timing,
            "explanation": self.explanation,
            "priority": self.priority,
            "operational_action_key": self.operational_action_key,
            "operational_action_value": self.operational_action_value,
        }


@dataclass
class RuleEvaluationTrace:
    """
    Audit record documenting the execution of an individual rule.
    """
    rule_id: str
    rule_name: str
    triggered: bool
    skipped: bool
    skip_reason: Optional[str]
    actual_value: Optional[Any]
    threshold_value: Any
    condition: str
    explanation: str


@dataclass
class RuleEngineEvaluationResult:
    """
    Consolidated output returned by the DeterministicRuleEngine.
    """
    risks: List[AgriculturalRiskItem]
    recommendation_context: DeterministicRecommendationContext
    triggered_rules: List[AgriculturalRuleDefinition]
    evaluation_trace: List[RuleEvaluationTrace]
    rule_version: str = RULE_ENGINE_VERSION


# =============================================================================
# 2. CENTRALIZED AGRICULTURAL RULES CATALOG
# =============================================================================
# Threshold Sources & Rationales:
# 1. IMD Rainfall Categories:
#    - 0.0 mm: No significant rainfall
#    - 0.1 to 2.5 mm: Very light rain
#    - 2.5 to 15.5 mm: Light rain
#    - 15.6 to 64.4 mm: Moderate rain
#    - 64.5 to 115.5 mm: Heavy rain
#    - > 115.5 mm: Very heavy / Extremely heavy rain
# 2. ICAR Agromet Advisory Service Guidelines:
#    - Spraying: Rainfall > 2.5 mm washes foliar sprays off leaves within 24h; postpones spraying.
#    - Fertilizer: Rainfall > 15.5 mm causes surface runoff and nitrogen leaching; delays broadcasting.
#    - Tillage: Wet soil (rainfall > 15.5 mm) damages soil aggregate structure and causes severe compaction.
#    - Waterlogging / Drainage: Rainfall > 64.4 mm causes standing water, hypoxia in root zones, requiring trenching.
#    - Irrigation: Rainfall > 2.5 mm satisfies short-term crop water needs; suggests suspension to conserve energy/water.

DEFAULT_AGRICULTURAL_RULES: List[AgriculturalRuleDefinition] = [
    # -------------------------------------------------------------------------
    # 1. Extreme Weather & Severe Inundation
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_EXTREME_INUNDATION_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Very Heavy to Extremely Heavy Rainfall Flood Hazard",
        category=RuleCategory.EXTREME_WEATHER,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=115.5,
        threshold_unit="mm",
        threshold_source="IMD Very Heavy Rainfall Threshold (> 115.5 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.CRITICAL,
        risk_type="SEVERE_INUNDATION",
        recommendation="Completely suspend all open-field operations, machinery movement, and harvesting. Relocate livestock and portable pumps to elevated ground.",
        timing="Immediate to next 24 hours",
        explanation="Rainfall exceeding 115.5 mm causes rapid surface water accumulation, flash inundation of low-lying plots, and topsoil wash-off.",
        priority=1,
        operational_action_key="operations",
        operational_action_value="HALT_ALL",
    ),

    # -------------------------------------------------------------------------
    # 2. Heavy Rainfall Drainage & Waterlogging
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Heavy Rainfall Root-Zone Waterlogging Risk",
        category=RuleCategory.DRAINAGE,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=64.4,
        threshold_unit="mm",
        threshold_source="IMD Heavy Rainfall Threshold (> 64.4 mm) & ICAR Drainage Guidelines",
        is_prototype=False,
        severity=AdvisorySeverityEnum.HIGH,
        risk_type="WATERLOGGING",
        recommendation="Immediately inspect, clear, and deepen field drainage furrows to discharge surplus runoff and prevent root-zone hypoxia.",
        timing="Next 12 to 24 hours",
        explanation="Rainfall exceeding 64.4 mm saturates the soil profile. Standing water for > 24 hours causes oxygen deprivation in crop root zones and fungal root rots.",
        priority=2,
        operational_action_key="drainage",
        operational_action_value="OPEN_TRENCHES",
    ),

    # -------------------------------------------------------------------------
    # 3. Moderate to Heavy Rain Tillage Restriction
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_TILLAGE_RESTRICTION_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Soil Wetness Tillage Delay",
        category=RuleCategory.FIELD_OPERATIONS,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=15.5,
        threshold_unit="mm",
        threshold_source="ICAR Soil Management / Tilth Preservation Threshold (> 15.5 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.MODERATE,
        risk_type="SOIL_COMPACTION",
        recommendation="Delay plowing, harrowing, and heavy intercultural tractor operations until topsoil moisture drops below field capacity.",
        timing="Next 24 to 48 hours",
        explanation="Tillage in wet soils exceeding 15.5 mm creates plow-pan compaction, clod formation, and damages delicate soil aggregate structure.",
        priority=4,
        operational_action_key="tillage",
        operational_action_value="DELAY",
    ),

    # -------------------------------------------------------------------------
    # 4. Moderate Rain Fertilizer Runoff & Leaching
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_FERTILIZER_LEACHING_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Fertilizer Surface Runoff and Leaching Warning",
        category=RuleCategory.FERTILIZER,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=15.5,
        threshold_unit="mm",
        threshold_source="ICAR Nutrient Best Management Practices (> 15.5 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.MODERATE,
        risk_type="RUNOFF_LEACHING",
        recommendation="Do not apply chemical top-dress fertilizers (e.g. Urea, DAP) before expected moderate-to-heavy showers to prevent runoff loss.",
        timing="Next 24 to 48 hours",
        explanation="Rainfall exceeding 15.5 mm generates surface runoff that washes away broadcast granular fertilizers into waterways.",
        priority=4,
        operational_action_key="fertilizer",
        operational_action_value="DELAY",
    ),

    # -------------------------------------------------------------------------
    # 5. Harvested Produce Protection
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_HARVEST_SHELTER_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Harvested Produce Moisture Spoilage Warning",
        category=RuleCategory.HARVEST,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=15.5,
        threshold_unit="mm",
        threshold_source="ICAR Post-Harvest Protection Guidelines (> 15.5 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.MODERATE,
        risk_type="GRAIN_DAMAGE",
        recommendation="Move threshed grains, harvested onion bulbs, and crop produce to elevated, covered sheds or protect with waterproof tarpaulins.",
        timing="Immediate",
        explanation="Wet conditions and rain splashes cause post-harvest mould, sprouting, and discoloration of open produce.",
        priority=3,
        operational_action_key="harvest",
        operational_action_value="SHELTER_PRODUCE",
    ),

    # -------------------------------------------------------------------------
    # 6. Foliar Spraying Wash-off Hazard
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_SPRAY_WASHOFF_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Foliar Spraying Wash-off Precaution",
        category=RuleCategory.SPRAYING,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=2.5,
        threshold_unit="mm",
        threshold_source="ICAR Plant Protection Guidelines: rain > 2.5 mm washes foliar sprays off leaves",
        is_prototype=False,
        severity=AdvisorySeverityEnum.MODERATE,
        risk_type="SPRAY_WASHOFF",
        recommendation="Postpone scheduled foliar chemical sprays (pesticides, fungicides) until rainfall ceases and foliage dries.",
        timing="Next 24 hours",
        explanation="Precipitation greater than 2.5 mm washes off foliar deposits before chemical absorption, resulting in waste and environmental runoff.",
        priority=5,
        operational_action_key="spraying",
        operational_action_value="POSTPONE",
    ),

    # -------------------------------------------------------------------------
    # 7. Irrigation Suspension on Rain
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_IRRIGATION_SUSPENSION_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Irrigation Cycle Suspension",
        category=RuleCategory.IRRIGATION,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=2.5,
        threshold_unit="mm",
        threshold_source="ICAR Water Management Guidelines: rain > 2.5 mm meets daily evapotranspiration",
        is_prototype=False,
        severity=AdvisorySeverityEnum.LOW,
        risk_type="SURFACE_MOISTURE_EXCESS",
        recommendation="Temporarily suspend scheduled canal or drip irrigation cycles as rainfall provides natural soil moisture replenishment.",
        timing="Next 24 to 48 hours",
        explanation="Rainfall above 2.5 mm satisfies daily evapotranspiration requirements for typical field crops; supplemental watering wastes electricity and water.",
        priority=6,
        operational_action_key="irrigation",
        operational_action_value="SUSPEND",
    ),

    # -------------------------------------------------------------------------
    # 8. Very Light Rain / Favorable Standard Operations
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Light Moisture Standard Farm Operations",
        category=RuleCategory.FIELD_OPERATIONS,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.BETWEEN,
        threshold_value=(0.0, 2.5),
        threshold_unit="mm",
        threshold_source="IMD Very Light Rainfall Classification (0.0 to 2.5 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.LOW,
        risk_type="MINIMAL_WEATHER_IMPACT",
        recommendation="Normal field management, hoeing, nursery care, and intercultural weeding may proceed as planned.",
        timing="Next 24 hours",
        explanation="Rainfall under 2.5 mm produces light surface moisture without disrupting fieldwork or soil structure.",
        priority=8,
        operational_action_key="spraying",
        operational_action_value="SAFE_WINDOW",
    ),

    # -------------------------------------------------------------------------
    # 9. Dry Weather / Soil Moisture Conservation
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_DRY_WEATHER_IRRIGATION_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="Dry Weather Irrigation Scheduling",
        category=RuleCategory.IRRIGATION,
        enabled=True,
        input_variables=["downscaled_rainfall_mm"],
        condition_operator=ComparisonOperator.EQUAL,
        threshold_value=0.0,
        threshold_unit="mm",
        threshold_source="IMD No Significant Rainfall Classification (0.0 mm)",
        is_prototype=False,
        severity=AdvisorySeverityEnum.LOW,
        risk_type="MOISTURE_DEFICIT_MONITORING",
        recommendation="Continue routine irrigation scheduling based on crop water requirements and root-zone moisture depth. Ideal window for spraying and weeding.",
        timing="Routine daily scheduling",
        explanation="Absence of precipitation allows unobstructed agricultural operations, harvesting, intercultural tillage, and safe chemical applications.",
        priority=9,
        operational_action_key="irrigation",
        operational_action_value="CONTINUE_NORMAL",
    ),

    # -------------------------------------------------------------------------
    # 10. [Conditional/Future] Heat Stress Precaution (Disabled if temp absent)
    # -------------------------------------------------------------------------
    AgriculturalRuleDefinition(
        rule_id="AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1",
        rule_version=RULE_ENGINE_VERSION,
        rule_name="High Temperature Crop Stress Precaution",
        category=RuleCategory.TEMPERATURE_STRESS,
        enabled=True,
        input_variables=["temperature_c"],
        condition_operator=ComparisonOperator.GREATER_THAN,
        threshold_value=38.0,
        threshold_unit="Celsius",
        threshold_source="ICAR Thermal Stress Guidelines: temperature > 38°C induces flower drop",
        is_prototype=True,
        severity=AdvisorySeverityEnum.HIGH,
        risk_type="HEAT_STRESS",
        recommendation="Provide light, frequent evening irrigations and soil mulching to mitigate root-zone thermal shock.",
        timing="Midday to afternoon",
        explanation="Temperatures above 38°C increase evapotranspiration and risk blossom abortion in horticultural crops.",
        priority=3,
        operational_action_key="irrigation",
        operational_action_value="EVENING_CYCLE",
    ),
]


# =============================================================================
# 3. DETERMINISTIC EVALUATION ENGINE
# =============================================================================

class DeterministicRuleEngine:
    """
    Evaluates validated forecast context against the standardized agricultural rule catalog.
    Produces structured risk items, prioritized recommendations, and operational tags.
    """

    def __init__(self, rules: Optional[List[AgriculturalRuleDefinition]] = None):
        self.rules = rules if rules is not None else DEFAULT_AGRICULTURAL_RULES

    def _evaluate_condition(
        self,
        actual_val: Any,
        operator: ComparisonOperator,
        threshold_val: Any,
    ) -> bool:
        """Evaluates numerical condition deterministically."""
        if actual_val is None:
            return False

        try:
            val = float(actual_val)
            if operator == ComparisonOperator.GREATER_THAN:
                return val > float(threshold_val)
            elif operator == ComparisonOperator.GREATER_THAN_EQUAL:
                return val >= float(threshold_val)
            elif operator == ComparisonOperator.LESS_THAN:
                return val < float(threshold_val)
            elif operator == ComparisonOperator.LESS_THAN_EQUAL:
                return val <= float(threshold_val)
            elif operator == ComparisonOperator.EQUAL:
                return abs(val - float(threshold_val)) < 1e-6
            elif operator == ComparisonOperator.BETWEEN:
                low, high = threshold_val
                # Exclusive of low if low == 0 to distinguish exact 0.0
                if low == 0.0:
                    return 0.0 < val <= float(high)
                return float(low) <= val <= float(high)
        except (ValueError, TypeError):
            return False

        return False

    def evaluate(
        self,
        forecast_context: ForecastContext,
        panchayat_context: Optional[PanchayatContext] = None,
    ) -> RuleEngineEvaluationResult:
        """
        Executes all active rules against the given forecast context.
        
        Args:
            forecast_context: Validated numerical downscaled weather prediction.
            panchayat_context: Optional administrative Panchayat context.
            
        Returns:
            RuleEngineEvaluationResult: Aggregated risks, consolidated recommendations,
            operational guidance, and comprehensive execution trace.
        """
        triggered_rules: List[AgriculturalRuleDefinition] = []
        evaluation_traces: List[RuleEvaluationTrace] = []
        risks: List[AgriculturalRiskItem] = []
        operational_guidance: Dict[str, str] = {
            "spraying": "SAFE_WINDOW",
            "tillage": "PERMITTED",
            "drainage": "NORMAL",
            "irrigation": "CONTINUE_NORMAL",
        }

        # Context dictionary mapping input variable names to forecast values
        context_vars = {
            "downscaled_rainfall_mm": forecast_context.downscaled_rainfall_mm,
            "block_forecast_rainfall_mm": forecast_context.block_forecast_rainfall_mm,
            "lead_days": forecast_context.lead_days,
            "temperature_c": forecast_context.temperature_c,
            "humidity_pct": forecast_context.humidity_pct,
            "wind_speed_kmh": forecast_context.wind_speed_kmh,
            "soil_moisture_index": forecast_context.soil_moisture_index,
        }

        # Evaluate rules in sequence
        for rule in self.rules:
            if not rule.enabled:
                evaluation_traces.append(
                    RuleEvaluationTrace(
                        rule_id=rule.rule_id,
                        rule_name=rule.rule_name,
                        triggered=False,
                        skipped=True,
                        skip_reason="Rule is disabled in configuration.",
                        actual_value=None,
                        threshold_value=rule.threshold_value,
                        condition=f"{rule.input_variables} {rule.condition_operator.value} {rule.threshold_value}",
                        explanation=rule.explanation,
                    )
                )
                continue

            # Verify all required input variables are available in the forecast context
            primary_var = rule.input_variables[0] if rule.input_variables else None
            actual_val = context_vars.get(primary_var) if primary_var else None

            if actual_val is None:
                evaluation_traces.append(
                    RuleEvaluationTrace(
                        rule_id=rule.rule_id,
                        rule_name=rule.rule_name,
                        triggered=False,
                        skipped=True,
                        skip_reason=f"Required variable '{primary_var}' is not available in current forecast data.",
                        actual_value=None,
                        threshold_value=rule.threshold_value,
                        condition=f"{rule.input_variables} {rule.condition_operator.value} {rule.threshold_value}",
                        explanation=rule.explanation,
                    )
                )
                continue

            # Evaluate condition
            is_triggered = self._evaluate_condition(
                actual_val=actual_val,
                operator=rule.condition_operator,
                threshold_val=rule.threshold_value,
            )

            evaluation_traces.append(
                RuleEvaluationTrace(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    triggered=is_triggered,
                    skipped=False,
                    skip_reason=None,
                    actual_value=actual_val,
                    threshold_value=rule.threshold_value,
                    condition=f"{primary_var} ({actual_val}) {rule.condition_operator.value} {rule.threshold_value} {rule.threshold_unit}",
                    explanation=rule.explanation,
                )
            )

            if is_triggered:
                triggered_rules.append(rule)

                # Formulate AgriculturalRiskItem
                risk_item = AgriculturalRiskItem(
                    risk_type=rule.risk_type,
                    severity=rule.severity,
                    triggering_condition=f"{rule.rule_name}: {primary_var}={actual_val:.1f} {rule.threshold_unit} ({rule.condition_operator.value} {rule.threshold_value})",
                    supporting_values={
                        "actual_value": actual_val,
                        "threshold_value": rule.threshold_value,
                        "unit": rule.threshold_unit,
                        "threshold_source": rule.threshold_source,
                    },
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                )
                risks.append(risk_item)

                # Update operational guidance tags (higher severity wins)
                if rule.operational_action_key and rule.operational_action_value:
                    operational_guidance[rule.operational_action_key] = rule.operational_action_value

        # Sort triggered rules by priority (ascending: 1 = most urgent)
        triggered_rules.sort(key=lambda r: r.priority)
        risks.sort(key=lambda r: (
            {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}.get(r.severity.value, 4)
        ))

        # Consolidate non-redundant recommended actions
        recommended_actions: List[str] = []
        for r in triggered_rules:
            if r.recommendation not in recommended_actions:
                recommended_actions.append(r.recommendation)

        if not recommended_actions:
            recommended_actions.append("Maintain routine crop monitoring and soil moisture assessments.")

        # Determine timing window from most severe rule
        timing_window = triggered_rules[0].timing if triggered_rules else "Next 24 to 48 hours"

        recommendation_context = DeterministicRecommendationContext(
            recommended_actions=recommended_actions,
            timing_window=timing_window,
            operational_guidance=operational_guidance,
        )

        return RuleEngineEvaluationResult(
            risks=risks,
            recommendation_context=recommendation_context,
            triggered_rules=triggered_rules,
            evaluation_trace=evaluation_traces,
            rule_version=RULE_ENGINE_VERSION,
        )


# Default singleton instance for direct module imports
default_rule_engine = DeterministicRuleEngine()
