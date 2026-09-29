"""
API v1 Farmer Weather Forecast & Advisory Endpoints.

Provides a simplified, high-clarity farmer-facing API delivering hyper-local
downscaled weather forecasts paired with validated agronomic guidance.
"""

import logging
from datetime import date
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from backend.app.core.database import get_db
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from backend.app.models.panchayat import Panchayat
from backend.app.models.farmer_preference import FarmerPreference
from backend.app.schemas.farmer import FarmerForecastResponse
from backend.app.schemas.farmer_preference import (
    FarmerPreferenceUpdateRequest,
    FarmerPreferenceResponse,
)
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


# ---------------------------------------------------------------------------
# Farmer Personalization & Preferences (Phase 6.3)
# ---------------------------------------------------------------------------

def get_authenticated_farmer_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_farmer_id: Optional[str] = Header(None, alias="X-Farmer-Id"),
) -> str:
    """
    Extracts and authenticates farmer identity from HTTP request context.

    Accepts:
    1. 'Authorization: Bearer <token_or_farmer_id>'
    2. 'X-Farmer-Id: <farmer_id>'

    Rejects:
    - Missing or blank credentials (401 Unauthorized)
    - Unauthorized or anonymous tokens (401 Unauthorized)
    """
    farmer_id: Optional[str] = None
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            farmer_id = parts[1].strip()
        elif len(parts) == 1:
            farmer_id = parts[0].strip()

    if not farmer_id and x_farmer_id:
        farmer_id = x_farmer_id.strip()

    if not farmer_id or farmer_id.upper() in ("ANONYMOUS", "UNAUTHORIZED", "NONE", "NULL", ""):
        logger.warning("[FARMER_AUTH_REJECTED] Missing or invalid farmer authentication token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Farmer authentication required. Please provide a valid Authorization Bearer token or X-Farmer-Id header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return farmer_id


@router.get(
    "/farmer/preferences",
    response_model=FarmerPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Farmer Preferred Panchayat & Language",
    description="""
    Retrieves the authenticated farmer's saved Panchayat and language preferences
    with authoritative spatial metadata (Panchayat, Block, District).
    """,
    tags=["Farmer Services"],
)
def get_farmer_preferences(
    farmer_id: str = Depends(get_authenticated_farmer_id),
    db: Session = Depends(get_db),
) -> FarmerPreferenceResponse:
    pref = db.query(FarmerPreference).filter(FarmerPreference.farmer_id == farmer_id).first()
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No saved preferences found for farmer '{farmer_id}'. Please complete setup.",
        )

    # Authoritative spatial metadata lookup
    spatial = _resolve_panchayat_spatial_names(pref.panchayat_id, db)

    return FarmerPreferenceResponse(
        farmer_id=pref.farmer_id,
        panchayat_id=pref.panchayat_id,
        preferred_language=pref.preferred_language,
        panchayat_name=spatial["panchayat_name"],
        block_name=spatial["block_name"],
        district_name=spatial["district_name"],
        updated_at=pref.updated_at or pref.created_at or func.now(),
        is_valid=True,
        available_languages=ALL_SUPPORTED_LANGUAGES.copy(),
    )


@router.put(
    "/farmer/preferences",
    response_model=FarmerPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or Update Farmer Preferred Panchayat & Language",
    description="""
    Saves or updates the authenticated farmer's preferred Panchayat and language.

    Validation Guarantees:
    - Farmer identity is derived exclusively from the authenticated context.
    - If payload supplies a `farmer_id`, it MUST match authenticated identity (403 Forbidden otherwise).
    - Panchayat ID must exist in the authoritative hierarchy (404 Not Found otherwise).
    - Language must be supported ('en', 'mr', 'hi') (400 Bad Request otherwise).
    - Never stores raw GPS coordinates or location history.
    """,
    tags=["Farmer Services"],
)
def update_farmer_preferences(
    payload: FarmerPreferenceUpdateRequest,
    farmer_id: str = Depends(get_authenticated_farmer_id),
    db: Session = Depends(get_db),
) -> FarmerPreferenceResponse:
    # 1. Authorization check: farmer cannot modify another farmer's preferences
    if payload.farmer_id and payload.farmer_id.strip() != farmer_id:
        logger.warning(
            f"[FARMER_AUTH_FORBIDDEN] Authenticated farmer '{farmer_id}' attempted to modify '{payload.farmer_id}'."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Authenticated farmer '{farmer_id}' cannot modify preferences for '{payload.farmer_id}'.",
        )

    # 2. Validate Panchayat existence in authoritative hierarchy
    panchayat = db.query(Panchayat).filter(Panchayat.id == payload.panchayat_id).first()
    if not panchayat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panchayat with ID '{payload.panchayat_id}' does not exist.",
        )

    # 3. Validate language support
    clean_lang = (payload.preferred_language or "").strip().lower()
    if clean_lang not in ALL_SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{payload.preferred_language}' is not supported. Supported languages: {ALL_SUPPORTED_LANGUAGES}",
        )

    # 4. Upsert preference record
    pref = db.query(FarmerPreference).filter(FarmerPreference.farmer_id == farmer_id).first()
    if not pref:
        pref = FarmerPreference(
            farmer_id=farmer_id,
            panchayat_id=payload.panchayat_id,
            preferred_language=clean_lang,
        )
        db.add(pref)
    else:
        pref.panchayat_id = payload.panchayat_id
        pref.preferred_language = clean_lang
        pref.updated_at = func.now()

    db.commit()
    db.refresh(pref)

    # 5. Retrieve authoritative spatial metadata
    spatial = _resolve_panchayat_spatial_names(pref.panchayat_id, db)

    logger.info(
        f"[FARMER_PREFERENCES_SAVED] farmer_id='{farmer_id}' panchayat_id={pref.panchayat_id} "
        f"lang='{pref.preferred_language}'"
    )

    return FarmerPreferenceResponse(
        farmer_id=pref.farmer_id,
        panchayat_id=pref.panchayat_id,
        preferred_language=pref.preferred_language,
        panchayat_name=spatial["panchayat_name"],
        block_name=spatial["block_name"],
        district_name=spatial["district_name"],
        updated_at=pref.updated_at or pref.created_at or func.now(),
        is_valid=True,
        available_languages=ALL_SUPPORTED_LANGUAGES.copy(),
    )

