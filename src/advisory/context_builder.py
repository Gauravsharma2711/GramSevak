"""
Phase 5.3 Advisory Context Builder & Service.

Assembles authoritative Panchayat spatial context, validated numerical downscaled
forecast data, deterministic agricultural risk evaluations, and end-to-end
traceability metadata into the canonical AdvisoryContext contract.

Safety and Architectural Invariants:
1. Panchayat identity is anchored to database identifiers and Local Government Directory (LGD) codes.
2. Forecast values are strictly preserved and never mutated, overwritten, or fabricated.
3. Multiple forecast records are resolved using an explicit, deterministic ordering policy:
   (forecast_issue_date DESC, created_at DESC, id DESC).
4. Missing numerical values are never treated as zero; missing dependencies raise structured errors.
5. Every risk item and baseline recommendation preserves its rule_id, rule_version, and forecast linkage.
6. Pure consumer layer: does NOT invoke LLMs, prompt builders, or publish to farmers.
"""

from datetime import date, datetime
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.panchayat import Panchayat
from backend.app.repositories.hierarchy_repository import HierarchyRepository
from backend.app.schemas.advisory_contracts import (
    PanchayatContext,
    ForecastContext,
    AgriculturalRiskItem,
    DeterministicRecommendationContext,
    AIAdvisoryInputContract,
    AdvisoryTraceabilityContract,
    AdvisoryContext,
    AdvisorySeverityEnum,
    AdvisorySourceEnum,
)
from src.advisory.rainfall_classifier import classify_rainfall
from src.advisory.rule_engine import default_rule_engine, RULE_ENGINE_VERSION

logger = logging.getLogger(__name__)


# =============================================================================
# 1. STRUCTURED ADVISORY CONTEXT EXCEPTIONS
# =============================================================================

class AdvisoryContextError(ValueError):
    """Base exception for advisory context building errors."""
    def __init__(
        self,
        message: str,
        code: str = "CONTEXT_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


# Backwards compatibility alias for Phase 5.1
ContextBuilderError = AdvisoryContextError


class PanchayatNotFoundError(AdvisoryContextError):
    """Raised when the requested Panchayat cannot be found."""
    def __init__(self, panchayat_id: int):
        super().__init__(
            f"Panchayat with ID '{panchayat_id}' does not exist in administrative hierarchy.",
            code="PANCHAYAT_NOT_FOUND",
            details={"panchayat_id": panchayat_id},
        )


class HierarchyMismatchError(AdvisoryContextError):
    """Raised when Panchayat does not belong to the claimed Block or District."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="HIERARCHY_MISMATCH", details=details)


class ForecastNotFoundError(AdvisoryContextError):
    """Raised when no downscaled forecast is found for the given Panchayat/date."""
    def __init__(self, panchayat_id: int, forecast_date: Optional[date] = None, forecast_id: Optional[int] = None):
        msg = f"No downscaled forecast found for Panchayat ID '{panchayat_id}'"
        if forecast_id:
            msg += f" with forecast_id '{forecast_id}'"
        elif forecast_date:
            msg += f" on forecast date '{forecast_date}'"
        super().__init__(
            msg,
            code="FORECAST_NOT_FOUND",
            details={
                "panchayat_id": panchayat_id,
                "forecast_date": str(forecast_date) if forecast_date else None,
                "forecast_id": forecast_id,
            },
        )


class ForecastPanchayatMismatchError(AdvisoryContextError):
    """Raised when a forecast record belongs to a different Panchayat than requested."""
    def __init__(self, forecast_id: int, forecast_panchayat_id: int, requested_panchayat_id: int):
        super().__init__(
            f"Forecast record {forecast_id} belongs to Panchayat {forecast_panchayat_id}, "
            f"not requested Panchayat {requested_panchayat_id}.",
            code="FORECAST_PANCHAYAT_MISMATCH",
            details={
                "forecast_id": forecast_id,
                "forecast_panchayat_id": forecast_panchayat_id,
                "requested_panchayat_id": requested_panchayat_id,
            },
        )


class InvalidForecastDataError(AdvisoryContextError):
    """Raised when forecast records contain unphysical, corrupted, or missing data."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="INVALID_FORECAST_DATA", details=details)


class RuleEvaluationError(AdvisoryContextError):
    """Raised when the deterministic rule evaluation fails or returns invalid schema."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="RULE_EVALUATION_ERROR", details=details)


# =============================================================================
# 2. VALIDATION UTILITIES
# =============================================================================

def validate_numeric_value(val: Any, name: str, allow_negative: bool = False) -> float:
    """Validates that a numeric field is present, finite, and within valid range."""
    if val is None:
        raise InvalidForecastDataError(
            f"Required numerical field '{name}' is missing/null.",
            details={"field": name, "value": None},
        )
    try:
        f = float(val)
    except (ValueError, TypeError):
        raise InvalidForecastDataError(
            f"Field '{name}' contains non-numeric value '{val}'.",
            details={"field": name, "value": str(val)},
        )

    if math.isnan(f) or math.isinf(f):
        raise InvalidForecastDataError(
            f"Field '{name}' contains non-finite value '{val}'.",
            details={"field": name, "value": str(val)},
        )

    if not allow_negative and f < 0.0:
        raise InvalidForecastDataError(
            f"Field '{name}' has negative value {f:.2f}, but must be non-negative.",
            details={"field": name, "value": f},
        )

    return f


# =============================================================================
# 3. DOMAIN CONTEXT BUILDERS
# =============================================================================

def build_panchayat_context(panchayat: Panchayat) -> PanchayatContext:
    """
    Constructs an authoritative, validated PanchayatContext from an ORM Panchayat model.
    Eagerly loads and normalizes Block and District hierarchy names and LGD codes.
    """
    if not panchayat or not getattr(panchayat, "id", None):
        raise PanchayatNotFoundError(panchayat_id=getattr(panchayat, "id", 0))

    block = getattr(panchayat, "block", None)
    district = getattr(panchayat, "district", None)

    block_name = str(block.name) if block and getattr(block, "name", None) else "Unknown Block"
    district_name = str(district.name) if district and getattr(district, "name", None) else "Unknown District"

    p_id = int(panchayat.id)
    raw_lgd = getattr(panchayat, "lgd_code", None)
    lgd_code = int(raw_lgd) if raw_lgd is not None and int(raw_lgd) > 0 else p_id

    return PanchayatContext(
        panchayat_id=p_id,
        panchayat_name=str(panchayat.name),
        panchayat_code=str(panchayat.panchayat_code) if getattr(panchayat, "panchayat_code", None) else None,
        lgd_code=lgd_code,
        block_id=int(panchayat.block_id) if getattr(panchayat, "block_id", None) else None,
        block_name=block_name,
        district_id=int(panchayat.district_id) if getattr(panchayat, "district_id", None) else None,
        district_name=district_name,
        latitude=float(panchayat.latitude) if getattr(panchayat, "latitude", None) is not None else None,
        longitude=float(panchayat.longitude) if getattr(panchayat, "longitude", None) is not None else None,
        elevation_m=float(panchayat.elevation_m) if getattr(panchayat, "elevation_m", None) is not None else None,
    )


def build_forecast_context(forecast: DownscaledForecast) -> ForecastContext:
    """
    Constructs and strictly validates a ForecastContext from an ORM DownscaledForecast model.
    Enforces temporal consistency, physical numeric ranges, and metadata provenance.
    """
    if not forecast or not getattr(forecast, "id", None):
        raise InvalidForecastDataError("Cannot build ForecastContext from null or unpersisted forecast.")

    # 1. Date consistency
    f_date = getattr(forecast, "forecast_date", None)
    if not f_date:
        raise InvalidForecastDataError("Forecast date is missing.", details={"forecast_id": getattr(forecast, "id", None)})

    issue_date = getattr(forecast, "forecast_issue_date", None) or f_date
    if issue_date > f_date:
        raise InvalidForecastDataError(
            f"Forecast issue date ({issue_date}) is after target forecast date ({f_date}).",
            details={"forecast_issue_date": str(issue_date), "forecast_date": str(f_date)},
        )

    lead_days = (f_date - issue_date).days

    # 2. Numerical validity (never assume missing is 0.0)
    downscaled_rf = validate_numeric_value(
        getattr(forecast, "downscaled_rainfall_mm", None),
        name="downscaled_rainfall_mm",
        allow_negative=False,
    )
    block_rf = validate_numeric_value(
        getattr(forecast, "block_forecast_rainfall_mm", None),
        name="block_forecast_rainfall_mm",
        allow_negative=False,
    )

    category_str = classify_rainfall(downscaled_rf)

    # 3. Model metadata
    model_name = str(getattr(forecast, "model_name", None) or "XGBoost Regressor")
    model_version = str(getattr(forecast, "model_version", None) or "v1.0.0")
    raw_conf = getattr(forecast, "confidence", None)
    confidence = float(raw_conf) if raw_conf is not None else None

    return ForecastContext(
        forecast_id=int(forecast.id),
        forecast_date=f_date,
        forecast_issue_date=issue_date,
        lead_days=max(0, lead_days),
        block_forecast_rainfall_mm=block_rf,
        downscaled_rainfall_mm=downscaled_rf,
        rainfall_category=category_str,
        model_name=model_name,
        model_version=model_version,
        confidence=confidence,
        temperature_c=None,
        humidity_pct=None,
        wind_speed_kmh=None,
        soil_moisture_index=None,
    )


def build_deterministic_risk_and_recommendations(
    forecast_context: ForecastContext,
    panchayat_context: Optional[PanchayatContext] = None,
) -> Tuple[List[AgriculturalRiskItem], DeterministicRecommendationContext, List[str]]:
    """
    Evaluates validated forecast context through the Phase 5 Deterministic Agricultural Rule Engine.
    Returns (risks, recommendation_context, validation_errors).
    """
    try:
        eval_result = default_rule_engine.evaluate(
            forecast_context,
            panchayat_context=panchayat_context,
            require_panchayat=False,
        )
    except Exception as exc:
        raise RuleEvaluationError(
            f"Deterministic rule engine evaluation failed: {exc}",
            details={"error": str(exc)},
        ) from exc

    return eval_result.risks, eval_result.recommendation_context, eval_result.validation_errors


def build_traceability_record(
    panchayat: Union[Panchayat, PanchayatContext],
    forecast: Union[DownscaledForecast, ForecastContext],
    rule_version: str = RULE_ENGINE_VERSION,
    advisory_source: AdvisorySourceEnum = AdvisorySourceEnum.DETERMINISTIC_RULE,
    ai_provider: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_prompt_version: Optional[str] = None,
) -> AdvisoryTraceabilityContract:
    """
    Builds an end-to-end auditability contract anchoring the advisory to its inputs.
    Accepts either ORM model objects or validated context contracts.
    """
    p_id = int(getattr(panchayat, "panchayat_id", None) or getattr(panchayat, "id"))
    f_id = int(getattr(forecast, "forecast_id", None) or getattr(forecast, "id"))
    f_date = getattr(forecast, "forecast_date")
    f_issue_date = getattr(forecast, "forecast_issue_date", None) or f_date
    downscaled_rf = float(getattr(forecast, "downscaled_rainfall_mm"))
    model_name = str(getattr(forecast, "model_name", None) or "XGBoost Regressor")
    model_version = str(getattr(forecast, "model_version", None) or "v1.0.0")

    source_ref = f"FORECAST_P{p_id}_{f_date}"

    return AdvisoryTraceabilityContract(
        panchayat_id=p_id,
        forecast_id=f_id,
        forecast_date=f_date,
        forecast_issue_date=f_issue_date,
        source_forecast_reference=source_ref,
        downscaled_rainfall_mm=downscaled_rf,
        ml_model_name=model_name,
        ml_model_version=model_version,
        rule_version=rule_version,
        advisory_source=advisory_source,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_prompt_version=ai_prompt_version,
    )


# =============================================================================
# 4. ADVISORY CONTEXT DOMAIN SERVICE
# =============================================================================

class AdvisoryContextService:
    """
    Coordinates authoritative Panchayat metadata, validated forecast extraction,
    and deterministic rule execution into the canonical AdvisoryContext.
    """

    def __init__(self, hierarchy_repo: Optional[HierarchyRepository] = None):
        self.hierarchy_repo = hierarchy_repo or HierarchyRepository()

    def build_advisory_context(
        self,
        panchayat_id: int,
        forecast_id: Optional[int] = None,
        forecast_date: Optional[date] = None,
        expected_block_id: Optional[int] = None,
        expected_district_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> AdvisoryContext:
        """
        Assembles and validates a canonical AdvisoryContext for a Gram Panchayat.

        Args:
            panchayat_id: Primary database ID of the Gram Panchayat.
            forecast_id: Optional specific forecast record ID.
            forecast_date: Optional target date for forecast lookup.
            expected_block_id: Optional block ID for hierarchy validation.
            expected_district_id: Optional district ID for hierarchy validation.
            db: Optional database session; if omitted, creates a scoped SessionLocal.

        Returns:
            AdvisoryContext: Validated context containing panchayat, forecast, risks,
            recommendations, and traceability.
        """
        local_db = False
        if db is None:
            db = SessionLocal()
            local_db = True

        try:
            # 1. Authoritative Panchayat Resolution with eager-loaded parents
            panchayat = self.hierarchy_repo.get_panchayat_by_id(db, panchayat_id, eager_load_parents=True)
            if not panchayat:
                raise PanchayatNotFoundError(panchayat_id)

            # 2. Hierarchy Parentage Validation
            if expected_block_id is not None and panchayat.block_id != expected_block_id:
                raise HierarchyMismatchError(
                    f"Panchayat {panchayat_id} belongs to Block {panchayat.block_id}, not expected {expected_block_id}.",
                    details={"panchayat_id": panchayat_id, "actual_block_id": panchayat.block_id, "expected_block_id": expected_block_id},
                )
            if expected_district_id is not None and panchayat.district_id != expected_district_id:
                raise HierarchyMismatchError(
                    f"Panchayat {panchayat_id} belongs to District {panchayat.district_id}, not expected {expected_district_id}.",
                    details={"panchayat_id": panchayat_id, "actual_district_id": panchayat.district_id, "expected_district_id": expected_district_id},
                )

            # 3. Forecast Retrieval & Multi-Record Conflict Resolution Policy
            if forecast_id is not None:
                forecast = (
                    db.query(DownscaledForecast)
                    .filter(DownscaledForecast.id == forecast_id)
                    .first()
                )
                if not forecast:
                    raise ForecastNotFoundError(panchayat_id=panchayat_id, forecast_id=forecast_id)
                if forecast.panchayat_id != panchayat_id:
                    raise ForecastPanchayatMismatchError(
                        forecast_id=forecast_id,
                        forecast_panchayat_id=forecast.panchayat_id,
                        requested_panchayat_id=panchayat_id,
                    )
            else:
                query = db.query(DownscaledForecast).filter(DownscaledForecast.panchayat_id == panchayat_id)
                if forecast_date is not None:
                    query = query.filter(DownscaledForecast.forecast_date == forecast_date)

                # Deterministic conflict resolution policy:
                # Latest issue date, then newest created timestamp, then highest ID
                forecast = (
                    query.order_by(
                        desc(DownscaledForecast.forecast_issue_date),
                        desc(DownscaledForecast.created_at),
                        desc(DownscaledForecast.id),
                    )
                    .first()
                )
                if not forecast:
                    raise ForecastNotFoundError(panchayat_id=panchayat_id, forecast_date=forecast_date)

            # 4. Build strongly-typed domain contracts
            panchayat_ctx = build_panchayat_context(panchayat)
            forecast_ctx = build_forecast_context(forecast)

            # 5. Execute Deterministic Rule Engine
            risks, recommendations, val_errors = build_deterministic_risk_and_recommendations(
                forecast_ctx, panchayat_context=panchayat_ctx
            )

            # 6. Assemble Traceability Metadata
            traceability = build_traceability_record(
                panchayat=panchayat_ctx,
                forecast=forecast_ctx,
                rule_version=RULE_ENGINE_VERSION,
                advisory_source=AdvisorySourceEnum.DETERMINISTIC_RULE,
            )

            # 7. Return canonical AdvisoryContext
            return AdvisoryContext(
                panchayat=panchayat_ctx,
                forecast=forecast_ctx,
                risks=risks,
                recommendations=recommendations,
                traceability=traceability,
                validation_errors=val_errors,
            )
        finally:
            if local_db:
                db.close()

    def build_from_objects(
        self,
        panchayat: Panchayat,
        forecast: DownscaledForecast,
    ) -> AdvisoryContext:
        """
        Builds AdvisoryContext directly from in-memory ORM model objects.
        Validates ownership, date sequence, and numeric integrity.
        """
        if not panchayat or not getattr(panchayat, "id", None):
            raise PanchayatNotFoundError(panchayat_id=getattr(panchayat, "id", 0))

        if not forecast or not getattr(forecast, "id", None):
            raise InvalidForecastDataError("Forecast object is null or unpersisted.")

        if forecast.panchayat_id != panchayat.id:
            raise ForecastPanchayatMismatchError(
                forecast_id=forecast.id,
                forecast_panchayat_id=forecast.panchayat_id,
                requested_panchayat_id=panchayat.id,
            )

        panchayat_ctx = build_panchayat_context(panchayat)
        forecast_ctx = build_forecast_context(forecast)

        risks, recommendations, val_errors = build_deterministic_risk_and_recommendations(
            forecast_ctx, panchayat_context=panchayat_ctx
        )

        traceability = build_traceability_record(
            panchayat=panchayat_ctx,
            forecast=forecast_ctx,
            rule_version=RULE_ENGINE_VERSION,
            advisory_source=AdvisorySourceEnum.DETERMINISTIC_RULE,
        )

        return AdvisoryContext(
            panchayat=panchayat_ctx,
            forecast=forecast_ctx,
            risks=risks,
            recommendations=recommendations,
            traceability=traceability,
            validation_errors=val_errors,
        )


# Default singleton instance for application-wide imports
default_advisory_context_service = AdvisoryContextService()


# Legacy helper function preserved for Phase 5.1 compatibility
def build_ai_advisory_input(
    panchayat: Panchayat,
    forecast: DownscaledForecast,
    target_language: str = "en",
) -> AIAdvisoryInputContract:
    """Builds AIAdvisoryInputContract via AdvisoryContextService."""
    ctx = default_advisory_context_service.build_from_objects(panchayat, forecast)
    return ctx.to_ai_input(target_language=target_language)
