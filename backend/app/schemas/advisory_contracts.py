"""
Phase 5 Advisory System Data Contracts.

Defines stable, strongly-typed Pydantic schemas and enums for the Phase 5 Weather
Intelligence and Agricultural Advisory pipeline:
  IMD Block Forecast
  -> Panchayat-Level Downscaling
  -> Panchayat Forecast
  -> Deterministic Risk/Rule Layer
  -> AI Advisory
  -> Safety Validation
  -> Officer Review
  -> Approved Farmer Advisory

Safety Invariants Enforced:
1. ML owns numerical weather prediction. AI must never modify or invent numerical predictions.
2. Rules own deterministic agricultural risk logic and baseline recommendations.
3. AI converts validated structured context into human-readable advisory content.
4. AI must not return unstructured blobs or invent weather/Panchayat metadata.
5. Safety validation happens before officer inspection; officer approval happens before farmer publication.
6. Every advisory must remain traceable to its forecast and Panchayat context.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


# =============================================================================
# 1. STATUS & LIFECYCLE ENUMS
# =============================================================================

class AdvisoryStatus(str, Enum):
    """
    Lifecycle status of an advisory through the Phase 5 pipeline.
    
    Safe Lifecycle:
      DRAFT -> GENERATED -> VALIDATED -> NEEDS_REVIEW -> APPROVED -> PUBLISHED
      Failure branches:
        GENERATED -> FAILED_VALIDATION -> (Fallback to Deterministic) -> NEEDS_REVIEW
        NEEDS_REVIEW -> REJECTED
    """
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class AdvisorySeverityEnum(str, Enum):
    """
    Standardized agricultural advisory severity levels.
    Aligned with IMD risk taxonomy and Phase 4 UI tokens.
    """
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AdvisorySourceEnum(str, Enum):
    """
    Source generator of the advisory content.
    """
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    AI_AUGMENTED = "AI_AUGMENTED"
    OFFICER_AMENDED = "OFFICER_AMENDED"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"


# =============================================================================
# 2. PANCHAYAT CONTEXT CONTRACT
# =============================================================================

class PanchayatContext(BaseModel):
    """
    Normalized administrative spatial metadata for a Gram Panchayat.
    Source of truth: panchayats, blocks, districts tables in Supabase.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    panchayat_id: int = Field(
        ...,
        ge=1,
        description="Unique database identifier for the Gram Panchayat",
        examples=[1001],
    )
    panchayat_name: str = Field(
        ...,
        min_length=1,
        description="Official name of the Gram Panchayat",
        examples=["Ajmer Saundane"],
    )
    panchayat_code: Optional[str] = Field(
        None,
        description="Internal administrative code or reference",
        examples=["P_NASHIK_1001"],
    )
    lgd_code: int = Field(
        ...,
        ge=1,
        description="Local Government Directory (LGD) unique code",
        examples=[253123],
    )
    block_id: Optional[int] = Field(
        None,
        ge=1,
        description="Referenced Tehsil / Block database identifier",
        examples=[10],
    )
    block_name: str = Field(
        ...,
        min_length=1,
        description="Administrative Block / Tehsil name",
        examples=["Baglan"],
    )
    district_id: Optional[int] = Field(
        None,
        ge=1,
        description="Referenced District database identifier",
        examples=[1],
    )
    district_name: str = Field(
        ...,
        min_length=1,
        description="Administrative District name",
        examples=["Nashik"],
    )
    latitude: Optional[float] = Field(
        None,
        ge=-90.0,
        le=90.0,
        description="Latitude of the Panchayat center / pilot station",
        examples=[20.5982],
    )
    longitude: Optional[float] = Field(
        None,
        ge=-180.0,
        le=180.0,
        description="Longitude of the Panchayat center / pilot station",
        examples=[74.1201],
    )
    elevation_m: Optional[float] = Field(
        None,
        ge=-500.0,
        le=9000.0,
        description="Elevation above mean sea level in meters",
        examples=[585.0],
    )


# =============================================================================
# 3. FORECAST CONTEXT CONTRACT
# =============================================================================

class ForecastContext(BaseModel):
    """
    Validated weather prediction data originating from Phase 2 ML downscaling.
    Source of truth: downscaled_forecasts and block_forecasts tables.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    forecast_id: int = Field(
        ...,
        ge=1,
        description="Unique database identifier of the stored downscaled forecast",
        examples=[1],
    )
    forecast_date: date = Field(
        ...,
        description="Target date for which the weather forecast applies (YYYY-MM-DD)",
        examples=["2026-09-04"],
    )
    forecast_issue_date: date = Field(
        ...,
        description="Date on which the baseline NWP forecast was issued (YYYY-MM-DD)",
        examples=["2026-09-04"],
    )
    lead_days: int = Field(
        ...,
        ge=0,
        description="Lead days between issue date and forecast target date",
        examples=[0],
    )
    block_forecast_rainfall_mm: float = Field(
        ...,
        ge=0.0,
        description="Original baseline numerical block forecast rainfall in mm",
        examples=[15.0],
    )
    downscaled_rainfall_mm: float = Field(
        ...,
        ge=0.0,
        description="Downscaled micro-level rainfall forecast in mm for the Panchayat",
        examples=[12.78],
    )
    rainfall_category: str = Field(
        ...,
        description="Standardized IMD rainfall category (e.g. 'Moderate rainfall')",
        examples=["Moderate rainfall"],
    )
    model_name: str = Field(
        ...,
        description="Name of the deployed ML model used for inference",
        examples=["XGBoost Regressor"],
    )
    model_version: str = Field(
        ...,
        description="Version tag of the deployed ML model",
        examples=["v1.0.0"],
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Model prediction statistical confidence / certainty (null if uncalibrated)",
        examples=[None],
    )

    # Future Variables (Documented as optional/future; NOT fabricated)
    temperature_c: Optional[float] = Field(
        None,
        description="[Future/Optional] Predicted mean surface temperature in Celsius",
    )
    humidity_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="[Future/Optional] Predicted relative humidity percentage",
    )
    wind_speed_kmh: Optional[float] = Field(
        None,
        ge=0.0,
        description="[Future/Optional] Predicted mean wind speed in km/h",
    )
    soil_moisture_index: Optional[float] = Field(
        None,
        description="[Future/Optional] Estimated root-zone soil moisture index",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> "ForecastContext":
        if self.forecast_date < self.forecast_issue_date:
            raise ValueError(
                f"forecast_date ({self.forecast_date}) cannot be earlier than "
                f"forecast_issue_date ({self.forecast_issue_date})"
            )
        return self


# =============================================================================
# 4. AGRICULTURAL RISK & DETERMINISTIC RULE CONTRACT
# =============================================================================

class AgriculturalRiskItem(BaseModel):
    """
    Individual risk condition evaluated by the deterministic agricultural rule layer.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    risk_type: str = Field(
        ...,
        description="Category of agricultural risk (e.g. 'HEAVY_RAINFALL', 'SPRAY_WASHOFF', 'WATERLOGGING')",
        examples=["SPRAY_WASHOFF"],
    )
    severity: AdvisorySeverityEnum = Field(
        ...,
        description="Severity level assigned to this specific risk",
        examples=[AdvisorySeverityEnum.HIGH],
    )
    triggering_condition: str = Field(
        ...,
        description="Specific threshold or condition that triggered the risk",
        examples=["Downscaled rainfall 18.5 mm > 2.5 mm spraying threshold"],
    )
    supporting_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting numerical values from forecast context",
        examples=[{"rainfall_mm": 18.5, "threshold_mm": 2.5}],
    )
    rule_id: str = Field(
        ...,
        description="Identifier of the rule in the agricultural rules registry",
        examples=["RULE_AGRO_SPRAY_01"],
    )
    rule_version: str = Field(
        ...,
        description="Version tag of the deterministic rule specification",
        examples=["v1.0.0"],
    )


class DeterministicRecommendationContext(BaseModel):
    """
    Baseline actionable guidance formulated by the deterministic agronomic rule layer.
    Serves as the foundation that AI can articulate, and as the fallback if AI fails.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    recommended_actions: List[str] = Field(
        ...,
        min_length=1,
        description="List of concrete agricultural action statements from deterministic rules",
        examples=[["Postpone foliar pesticide/fungicide sprays to prevent chemical wash-off."]],
    )
    timing_window: str = Field(
        ...,
        description="Recommended operational timeframe",
        examples=["Next 24 to 48 hours"],
    )
    operational_guidance: Dict[str, str] = Field(
        default_factory=dict,
        description="Field operational guidance mappings (e.g., spraying: POSTPONE)",
        examples=[{"spraying": "POSTPONE", "tillage": "PERMITTED", "drainage": "NORMAL"}],
    )


# =============================================================================
# 5. AI ADVISORY INPUT & OUTPUT CONTRACTS
# =============================================================================

class AIAdvisoryInputContract(BaseModel):
    """
    Strict input payload passed to the future AI Advisory Layer.
    Only structured, validated context is supplied; no arbitrary application state.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    panchayat_context: PanchayatContext = Field(
        ...,
        description="Validated geographic and administrative spatial metadata",
    )
    forecast_context: ForecastContext = Field(
        ...,
        description="Validated numerical downscaled weather prediction",
    )
    risks: List[AgriculturalRiskItem] = Field(
        default_factory=list,
        description="Identified deterministic agricultural risks",
    )
    deterministic_recommendations: DeterministicRecommendationContext = Field(
        ...,
        description="Baseline recommendations from deterministic rule layer",
    )
    target_language: str = Field(
        default="en",
        description="Target output language code ('en', 'mr', 'hi')",
        examples=["en"],
    )
    supported_languages: List[str] = Field(
        default_factory=lambda: ["en", "mr", "hi"],
        description="List of supported languages",
    )
    advisory_constraints: List[str] = Field(
        default_factory=lambda: [
            "Do not modify or contradict numerical weather values.",
            "Do not prescribe specific chemical brand names or unverified dosages.",
            "Do not fabricate disease diagnoses or emergency evacuations.",
            "Maintain calm, professional, and practical tone suitable for farmers.",
        ],
        description="Safety and editorial constraints enforced during generation",
    )


class AIAdvisoryOutputContract(BaseModel):
    """
    Strict structured output contract returned by the future AI Advisory Layer.
    Free-form blobs are forbidden; every field must conform to structured schema.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    summary: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="High-level advisory headline summary for the Panchayat",
        examples=["Moderate Rainfall Advisory: Delay Spraying & Maintain Field Drainage"],
    )
    what_is_happening: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Tier 1: Downscaled meteorological situation explained clearly",
        examples=["Downscaled forecast indicates 12.8 mm moderate rainfall over Ajmer Saundane."],
    )
    why_it_matters: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Tier 2: Agronomic impact on soil moisture, standing crops, and farm operations",
        examples=["Surface moisture will increase, making current chemical applications ineffective."],
    )
    recommended_actions: List[str] = Field(
        ...,
        min_length=1,
        description="Tier 3: Bulleted practical agronomic operations for farmers",
        examples=[["Postpone pesticide sprays until soil surfaces dry."]],
    )
    timing: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Operational timeframe and validity period",
        examples=["Immediate to next 24 hours"],
    )
    severity: AdvisorySeverityEnum = Field(
        ...,
        description="Assigned advisory severity level",
        examples=[AdvisorySeverityEnum.MODERATE],
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Specific caution points or threshold alerts",
        examples=[["Avoid water stagnation near root zones."]],
    )
    supporting_forecast_reference: Dict[str, Any] = Field(
        ...,
        description="Reference verification ensuring AI grounded in the input forecast",
        examples=[{"forecast_id": 1, "forecast_date": "2026-09-04", "downscaled_rainfall_mm": 12.78}],
    )


# =============================================================================
# 6. SAFETY VALIDATION CONTRACT
# =============================================================================

class SafetyValidationReport(BaseModel):
    """
    Automated safety validation inspection report.
    Must be PASS (is_valid=True) before an advisory can transition to NEEDS_REVIEW.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    is_valid: bool = Field(
        ...,
        description="Overall validation pass/fail status",
    )
    validation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when safety validation was executed",
    )
    checked_rules: List[str] = Field(
        ...,
        description="List of safety checks evaluated",
        examples=[["weather_numerical_consistency", "chemical_dosage_safety", "hallucination_guard", "content_completeness"]],
    )
    violations: List[str] = Field(
        default_factory=list,
        description="List of detected rule violations or safety hazards",
    )
    weather_consistency_passed: bool = Field(
        ...,
        description="Confirms weather numbers in text match input forecast context",
    )
    dosage_safety_passed: bool = Field(
        ...,
        description="Confirms text contains no unverified chemical dosages or harmful recipes",
    )
    hallucination_check_passed: bool = Field(
        ...,
        description="Confirms text does not reference unverified locations or unsupported disasters",
    )
    fallback_required: bool = Field(
        default=False,
        description="True if validation failed and deterministic fallback must be used",
    )


# =============================================================================
# 7. TRACEABILITY & AUDIT CONTRACT
# =============================================================================

class AdvisoryTraceabilityContract(BaseModel):
    """
    Complete audit lineage linking published advisory back through all layers.
    Ensures full transparency, accountability, and reproducibility.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    advisory_id: Optional[int] = Field(
        None,
        description="Unique identifier of the advisory record in the database",
    )
    panchayat_id: int = Field(
        ...,
        ge=1,
        description="Target Gram Panchayat identifier",
    )
    forecast_id: int = Field(
        ...,
        ge=1,
        description="Source downscaled forecast record identifier",
    )
    forecast_date: date = Field(
        ...,
        description="Target validity date for the forecast and advisory",
    )
    forecast_issue_date: date = Field(
        ...,
        description="Issue date of the source forecast",
    )
    source_forecast_reference: str = Field(
        ...,
        description="Reference identifier or composite key of the underlying NWP forecast",
        examples=["IMD_BLOCK_BAGLAN_2026-09-04"],
    )
    downscaled_rainfall_mm: float = Field(
        ...,
        ge=0.0,
        description="Numerical downscaled rainfall used for this advisory",
    )
    ml_model_name: str = Field(
        ...,
        description="Name of ML model that produced downscaled forecast",
    )
    ml_model_version: str = Field(
        ...,
        description="Version tag of ML model",
    )
    rule_version: str = Field(
        ...,
        description="Version tag of deterministic rule engine",
    )
    advisory_source: AdvisorySourceEnum = Field(
        ...,
        description="Generation source (DETERMINISTIC_RULE, AI_AUGMENTED, DETERMINISTIC_FALLBACK)",
    )
    ai_provider: Optional[str] = Field(
        None,
        description="Name of AI provider/service if AI augmented (null for deterministic)",
    )
    ai_model: Optional[str] = Field(
        None,
        description="AI model version/identifier (null for deterministic)",
    )
    ai_prompt_version: Optional[str] = Field(
        None,
        description="Version of prompt template used (null for deterministic)",
    )
    validation_report: Optional[SafetyValidationReport] = Field(
        None,
        description="Safety validation report if validated",
    )
    officer_id: Optional[str] = Field(
        None,
        description="Extension officer identifier who reviewed/approved",
    )
    officer_action: Optional[str] = Field(
        None,
        description="Action performed by officer (APPROVE, REJECT, AMEND)",
    )
    officer_comment: Optional[str] = Field(
        None,
        description="Officer remarks, field adjustments, or rejection reason",
    )
    action_timestamp: Optional[datetime] = Field(
        None,
        description="Timestamp of officer approval or rejection",
    )
    publication_timestamp: Optional[datetime] = Field(
        None,
        description="Timestamp when advisory became visible to farmers",
    )
    approved_content_hash: Optional[str] = Field(
        None,
        description="Cryptographic or structured hash of approved content for tamper verification",
    )


# =============================================================================
# 8. COMPLETE ADVISORY PIPELINE PAYLOAD
# =============================================================================

class FullAdvisoryPipelineEnvelope(BaseModel):
    """
    Internal envelope carrying an advisory through the complete Phase 5 pipeline:
      Panchayat Context + Forecast Context + Risk Context
      -> AI/Deterministic Draft -> Safety Validation -> Officer Action -> Published Output.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    panchayat_context: PanchayatContext
    forecast_context: ForecastContext
    risks: List[AgriculturalRiskItem] = Field(default_factory=list)
    deterministic_recommendations: DeterministicRecommendationContext
    current_status: AdvisoryStatus = Field(default=AdvisoryStatus.DRAFT)
    advisory_source: AdvisorySourceEnum = Field(default=AdvisorySourceEnum.DETERMINISTIC_RULE)
    draft_content: Optional[AIAdvisoryOutputContract] = None
    validation_report: Optional[SafetyValidationReport] = None
    traceability: AdvisoryTraceabilityContract
