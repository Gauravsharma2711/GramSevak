"""
Phase 5 Advisory Context Builder.

Assembles strongly-typed input contracts (PanchayatContext, ForecastContext,
AgriculturalRiskItem, DeterministicRecommendationContext, and Traceability) from
persisted database records and existing deterministic rule engine components.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.panchayat import Panchayat
from backend.app.schemas.advisory_contracts import (
    PanchayatContext,
    ForecastContext,
    AgriculturalRiskItem,
    DeterministicRecommendationContext,
    AIAdvisoryInputContract,
    AdvisoryTraceabilityContract,
    AdvisorySeverityEnum,
    AdvisorySourceEnum,
)
from src.advisory.rainfall_classifier import classify_rainfall
from src.advisory.advisory_engine import RULE_VERSION
from src.advisory.rule_engine import default_rule_engine


class ContextBuilderError(ValueError):
    """Raised when context building fails due to missing or invalid inputs."""
    pass


def build_panchayat_context(panchayat: Panchayat) -> PanchayatContext:
    """
    Constructs a validated PanchayatContext from an ORM Panchayat model.
    """
    if not panchayat or not panchayat.id:
        raise ContextBuilderError("Cannot build PanchayatContext from null or unpersisted Panchayat.")

    block_name = panchayat.block.name if panchayat.block else "Unknown Block"
    district_name = panchayat.district.name if panchayat.district else "Unknown District"

    return PanchayatContext(
        panchayat_id=int(panchayat.id),
        panchayat_name=str(panchayat.name),
        panchayat_code=str(panchayat.panchayat_code) if panchayat.panchayat_code else None,
        lgd_code=int(panchayat.lgd_code) if panchayat.lgd_code is not None else int(panchayat.id),
        block_id=int(panchayat.block_id) if panchayat.block_id else None,
        block_name=block_name,
        district_id=int(panchayat.district_id) if panchayat.district_id else None,
        district_name=district_name,
        latitude=float(panchayat.latitude) if panchayat.latitude is not None else None,
        longitude=float(panchayat.longitude) if panchayat.longitude is not None else None,
        elevation_m=float(panchayat.elevation_m) if panchayat.elevation_m is not None else None,
    )


def build_forecast_context(forecast: DownscaledForecast) -> ForecastContext:
    """
    Constructs a validated ForecastContext from an ORM DownscaledForecast model.
    """
    if not forecast or not forecast.id:
        raise ContextBuilderError("Cannot build ForecastContext from null or unpersisted DownscaledForecast.")

    downscaled_rf = float(forecast.downscaled_rainfall_mm) if forecast.downscaled_rainfall_mm is not None else 0.0
    block_rf = float(forecast.block_forecast_rainfall_mm) if forecast.block_forecast_rainfall_mm is not None else 0.0

    category_str = classify_rainfall(downscaled_rf)
    issue_date = forecast.forecast_issue_date or forecast.forecast_date
    lead_days = (forecast.forecast_date - issue_date).days if (forecast.forecast_date and issue_date) else 0

    return ForecastContext(
        forecast_id=int(forecast.id),
        forecast_date=forecast.forecast_date,
        forecast_issue_date=issue_date,
        lead_days=max(0, lead_days),
        block_forecast_rainfall_mm=block_rf,
        downscaled_rainfall_mm=downscaled_rf,
        rainfall_category=category_str,
        model_name=str(forecast.model_name or "XGBoost Regressor"),
        model_version=str(forecast.model_version or "v1.0.0"),
        confidence=float(forecast.confidence) if forecast.confidence is not None else None,
    )


def build_deterministic_risk_and_recommendations(
    forecast_context: ForecastContext,
) -> tuple[List[AgriculturalRiskItem], DeterministicRecommendationContext]:
    """
    Evaluates validated forecast context through the Phase 5 Deterministic Agricultural Rule Engine
    to produce structured, prioritized risk items and consolidated operational guidance.
    """
    eval_result = default_rule_engine.evaluate(forecast_context)
    return eval_result.risks, eval_result.recommendation_context


def build_ai_advisory_input(
    panchayat: Panchayat,
    forecast: DownscaledForecast,
    target_language: str = "en",
) -> AIAdvisoryInputContract:
    """
    Builds the complete structured input contract for the future AI advisory generator.
    """
    p_context = build_panchayat_context(panchayat)
    f_context = build_forecast_context(forecast)
    risks, recs = build_deterministic_risk_and_recommendations(f_context)

    return AIAdvisoryInputContract(
        panchayat_context=p_context,
        forecast_context=f_context,
        risks=risks,
        deterministic_recommendations=recs,
        target_language=target_language,
    )


def build_traceability_record(
    panchayat: Panchayat,
    forecast: DownscaledForecast,
    advisory_source: AdvisorySourceEnum = AdvisorySourceEnum.DETERMINISTIC_RULE,
    ai_provider: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_prompt_version: Optional[str] = None,
) -> AdvisoryTraceabilityContract:
    """
    Builds an end-to-end traceability contract anchoring the advisory to its inputs.
    """
    f_context = build_forecast_context(forecast)
    source_ref = f"FORECAST_P{panchayat.id}_{forecast.forecast_date}"

    return AdvisoryTraceabilityContract(
        panchayat_id=int(panchayat.id),
        forecast_id=int(forecast.id),
        forecast_date=forecast.forecast_date,
        forecast_issue_date=forecast.forecast_issue_date or forecast.forecast_date,
        source_forecast_reference=source_ref,
        downscaled_rainfall_mm=f_context.downscaled_rainfall_mm,
        ml_model_name=f_context.model_name,
        ml_model_version=f_context.model_version,
        rule_version=RULE_VERSION,
        advisory_source=advisory_source,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_prompt_version=ai_prompt_version,
    )
