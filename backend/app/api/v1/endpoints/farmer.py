"""
API v1 Farmer Weather Forecast & Advisory Endpoints.

Provides a simplified, high-clarity farmer-facing API delivering hyper-local
downscaled weather forecasts paired with validated agronomic guidance.
"""

import logging
from datetime import date
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from backend.app.schemas.farmer import FarmerForecastResponse
from src.services.advisory_service import _resolve_panchayat_spatial_names
from src.advisory.rainfall_classifier import classify_rainfall
from src.advisory.advisory_engine import ADVISORY_RULES_REGISTRY, AdvisorySeverity
from src.advisory.localization import (
    get_localized_rule_content,
    ALL_SUPPORTED_LANGUAGES,
    LANGUAGE_METADATA,
    DEFAULT_LANGUAGE,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/farmer/panchayat/{panchayat_id}",
    response_model=FarmerForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Farmer-Friendly Weather Forecast & Advisory",
    description="""
    Retrieve a clean, actionable weather forecast and agricultural advisory for a Gram Panchayat.

    Farmer Privacy & Safety Guarantees:
    - Exclusively provides hyper-local downscaled rainfall metrics and validated advisory points.
    - Only includes advisories that have been reviewed and `APPROVED` by extension officers.
    - If no approved advisory is available for the date, the forecast is returned with `advisory_status="NO_APPROVED_ADVISORY"`.
    - Sanitized: Does not expose internal database IDs, officer identifiers, model hyperparameters, or validation metrics.
    - Multilingual: Supports `en` (English), `mr` (Marathi), and `hi` (Hindi) with deterministic agronomic templates.
    """,
    responses={
        200: {
            "description": "Farmer forecast and advisory successfully retrieved.",
            "model": FarmerForecastResponse,
        },
        404: {
            "description": "No forecast found for the specified Panchayat and date.",
            "content": {"application/json": {"example": {"detail": "No forecast found for Panchayat ID '1001'."}}},
        },
        422: {
            "description": "Validation error on panchayat_id or query parameters.",
        },
    },
)
def get_farmer_panchayat_forecast(
    panchayat_id: int = Path(
        ...,
        ge=1,
        description="Unique Gram Panchayat identifier (positive integer)",
        examples=[1001],
    ),
    forecast_date: Optional[date] = Query(
        None,
        description="Target forecast date (YYYY-MM-DD). If omitted, returns the latest available forecast.",
        examples=["2026-09-08"],
    ),
    lang: str = Query(
        DEFAULT_LANGUAGE,
        description="Target language code for the advisory response ('en', 'mr', 'hi')",
        examples=["en"],
    ),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP GET handler to retrieve high-resolution weather forecast and approved agricultural advisory for farmers.
    """
    # 1. Base query for DownscaledForecast
    forecast_query = db.query(DownscaledForecast).filter(DownscaledForecast.panchayat_id == panchayat_id)

    if forecast_date is not None:
        forecast_query = forecast_query.filter(DownscaledForecast.forecast_date == forecast_date)

    forecast = (
        forecast_query
        .order_by(
            DownscaledForecast.forecast_date.desc(),
            DownscaledForecast.created_at.desc(),
            DownscaledForecast.id.desc(),
        )
        .first()
    )

    if not forecast:
        date_str = f" on date '{forecast_date}'" if forecast_date else ""
        logger.info(f"[FARMER_FORECAST_NOT_FOUND] panchayat_id={panchayat_id}{date_str}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast found for Panchayat ID '{panchayat_id}'{date_str}.",
        )

    # 2. Query for APPROVED Advisory for this Panchayat and forecast date
    advisory = (
        db.query(Advisory)
        .filter(
            Advisory.panchayat_id == panchayat_id,
            Advisory.forecast_date == forecast.forecast_date,
            Advisory.status == "APPROVED",
        )
        .order_by(
            Advisory.approved_at.desc(),
            Advisory.id.desc(),
        )
        .first()
    )

    # 3. Resolve Spatial Metadata
    spatial_names = _resolve_panchayat_spatial_names(panchayat_id, db)
    rainfall_val = float(forecast.downscaled_rainfall_mm) if forecast.downscaled_rainfall_mm is not None else 0.0

    # 4. Resolve Target Language & Review Readiness Status
    clean_lang = str(lang).lower().strip() if lang else DEFAULT_LANGUAGE
    active_lang = clean_lang if clean_lang in ALL_SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    lang_meta = LANGUAGE_METADATA.get(active_lang, {})
    language_status = lang_meta.get("status", "VERIFIED_PRIMARY")

    # 5. Construct Advisory Fields with Deterministic Multilingual Rendering
    if advisory:
        advisory_status = "APPROVED"
        rainfall_category = advisory.rainfall_category or classify_rainfall(rainfall_val, convert_negative_to_zero=True)
        severity = advisory.severity or AdvisorySeverity.LOW
        approved_data = advisory.approved_content or advisory.edited_content or advisory.original_content or {}

        fmt_context = {
            "panchayat_name": spatial_names["panchayat_name"],
            "block_name": spatial_names["block_name"],
            "forecast_date": str(forecast.forecast_date),
            "lead_days": 0,
            "rainfall_mm": round(rainfall_val, 1),
        }

        # Render localized 3-tier content if non-English requested
        if active_lang != DEFAULT_LANGUAGE and rainfall_category in ADVISORY_RULES_REGISTRY:
            rule = ADVISORY_RULES_REGISTRY[rainfall_category]
            try:
                localized = get_localized_rule_content(rule.rule_id, language=active_lang)
                advisory_title = localized.title_template.format(**fmt_context)
                advisory_points = [p.format(**fmt_context) for p in localized.advisory_points_templates]
                summary = advisory_title
                what_is_happening = localized.format_what_is_happening(fmt_context)
                why_it_matters = localized.format_why_it_matters(fmt_context)
                recommended_actions = advisory_points
                timing = localized.format_timing(fmt_context)
                warnings = localized.format_warnings(fmt_context)
            except Exception as loc_err:
                logger.warning(f"Failed to format localized advisory ({active_lang}): {loc_err}")
                advisory_title = approved_data.get("summary") or advisory.advisory_title
                advisory_points = approved_data.get("recommended_actions") or [
                    line.lstrip("•").strip()
                    for line in (advisory.advisory_text or "").split("\n")
                    if line.strip()
                ]
                summary = advisory_title
                what_is_happening = approved_data.get("what_is_happening") or f"{rainfall_val:.1f} mm rainfall predicted for {spatial_names['panchayat_name']}."
                why_it_matters = approved_data.get("why_it_matters") or "Agronomic conditions evaluated by agricultural extension rules."
                recommended_actions = advisory_points
                timing = approved_data.get("timing") or "Next 24 to 48 hours"
                warnings = approved_data.get("warnings") or []
        else:
            # English (canonical or officer-approved wording)
            advisory_title = approved_data.get("summary") or advisory.advisory_title
            advisory_points = approved_data.get("recommended_actions") or [
                line.lstrip("•").strip()
                for line in (advisory.advisory_text or "").split("\n")
                if line.strip()
            ]
            summary = advisory_title
            what_is_happening = approved_data.get("what_is_happening") or f"{rainfall_val:.1f} mm rainfall predicted for {spatial_names['panchayat_name']}."
            why_it_matters = approved_data.get("why_it_matters") or "Agronomic conditions evaluated by agricultural extension rules."
            recommended_actions = advisory_points
            timing = approved_data.get("timing") or "Next 24 to 48 hours"
            warnings = approved_data.get("warnings") or []

        advisory_version = advisory.version or 1
        approved_at = advisory.approved_at
    else:
        advisory_status = "NO_APPROVED_ADVISORY"
        advisory_title = None
        advisory_points = []
        summary = None
        what_is_happening = None
        why_it_matters = None
        recommended_actions = []
        timing = None
        warnings = []
        advisory_version = None
        approved_at = None
        rainfall_category = classify_rainfall(rainfall_val, convert_negative_to_zero=True)
        rule = ADVISORY_RULES_REGISTRY.get(rainfall_category)
        severity = rule.severity if rule else AdvisorySeverity.LOW

    logger.info(
        f"[FARMER_FORECAST_RETRIEVED] panchayat_id={panchayat_id} forecast_date={forecast.forecast_date} "
        f"rainfall_mm={rainfall_val} advisory_status={advisory_status} lang={active_lang}"
    )

    # 6. Return Farmer-Friendly Response (Without sensitive internals)
    return FarmerForecastResponse(
        panchayat_name=spatial_names["panchayat_name"],
        block_name=spatial_names["block_name"],
        district_name=spatial_names["district_name"],
        forecast_date=forecast.forecast_date,
        rainfall_mm=round(rainfall_val, 2),
        rainfall_category=rainfall_category,
        severity=severity,
        summary=summary,
        what_is_happening=what_is_happening,
        why_it_matters=why_it_matters,
        recommended_actions=recommended_actions,
        timing=timing,
        warnings=warnings,
        advisory_version=advisory_version,
        approved_at=approved_at,
        advisory_title=advisory_title,
        advisory_points=advisory_points,
        advisory_status=advisory_status,
        model_name=forecast.model_name or "XGBoost Regressor",
        model_version=forecast.model_version or "v1.0.0",
        language=active_lang,
        available_languages=ALL_SUPPORTED_LANGUAGES.copy(),
        language_status=language_status,
    )
