"""
API v1 Advisory Endpoints.

Provides endpoints for generating deterministic agricultural advisories from
downscaled weather forecasts and retrieving approved farmer advisories.
"""

import logging
from datetime import date
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.database import get_db
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from backend.app.schemas.advisory import (
    AdvisoryGenerateRequest,
    AdvisoryResponse,
    PanchayatAdvisoryRetrievalResponse,
)
from src.services.advisory_service import (
    generate_advisory,
    InvalidForecastInputError,
    AdvisoryServiceError,
    _resolve_panchayat_spatial_names,
)
from src.advisory.rainfall_classifier import InvalidRainfallError, classify_rainfall
from src.advisory.advisory_engine import ADVISORY_RULES_REGISTRY
from src.advisory.localization import (
    get_localized_rule_content,
    ALL_SUPPORTED_LANGUAGES,
    LANGUAGE_METADATA,
    DEFAULT_LANGUAGE,
)
from backend.app.schemas.advisory_contracts import AdvisoryContext
from src.advisory.context_builder import (
    default_advisory_context_service,
    AdvisoryContextError,
    PanchayatNotFoundError as CtxPanchayatNotFoundError,
    ForecastNotFoundError as CtxForecastNotFoundError,
    ForecastPanchayatMismatchError as CtxForecastMismatchError,
    HierarchyMismatchError as CtxHierarchyMismatchError,
    InvalidForecastDataError as CtxInvalidForecastDataError,
    RuleEvaluationError as CtxRuleEvaluationError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/advisory/generate",
    response_model=AdvisoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Agricultural Advisory from Stored Forecast",
    description="""
    Generate a deterministic, rule-based agricultural advisory for a specific stored weather forecast.

    Workflow:
    1. Validates the provided `forecast_id`.
    2. Retrieves the stored downscaled weather forecast record from the database.
    3. Checks if an already APPROVED advisory exists for this forecast. If an approved advisory exists,
       it is returned directly without regenerating to preserve officer approvals.
    4. Evaluates rainfall intensity through deterministic prototype thresholds (no LLM).
    5. Formulates actionable, conservative generic agricultural advice and assigns severity.
    6. Persists the generated advisory draft with status `DRAFT` in Supabase PostgreSQL.
    7. Returns the complete advisory entity referencing the forecast ID with language metadata.
    """,
    responses={
        200: {
            "description": "Advisory successfully generated or existing approved advisory returned.",
            "model": AdvisoryResponse,
        },
        404: {
            "description": "Forecast record not found.",
            "content": {"application/json": {"example": {"detail": "Forecast record with ID '99999' not found."}}},
        },
        422: {
            "description": "Validation error or invalid forecast data.",
            "content": {"application/json": {"example": {"detail": "Forecast contains invalid rainfall value."}}},
        },
        500: {
            "description": "Internal server error during advisory generation.",
            "content": {"application/json": {"example": {"detail": "Internal error generating advisory: ..."}}},
        },
    },
)
def generate_advisory_endpoint(
    payload: AdvisoryGenerateRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP POST handler to generate and store a deterministic agricultural advisory.
    """
    forecast_id = payload.forecast_id

    # 1. Retrieve the stored forecast
    forecast = db.query(DownscaledForecast).filter(DownscaledForecast.id == forecast_id).first()
    if not forecast:
        logger.warning(f"[ADVISORY_FORECAST_NOT_FOUND] forecast_id={forecast_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast record with ID '{forecast_id}' not found.",
        )

    # 2. Check for existing approved advisory (Do not regenerate an existing approved advisory automatically)
    existing_approved = (
        db.query(Advisory)
        .filter(Advisory.forecast_id == forecast_id, Advisory.status == "APPROVED")
        .order_by(Advisory.approved_at.desc(), Advisory.id.desc())
        .first()
    )
    if existing_approved:
        logger.info(
            f"[ADVISORY_EXISTING_APPROVED_RETURNED] forecast_id={forecast_id} "
            f"advisory_id={existing_approved.id} panchayat_id={existing_approved.panchayat_id}"
        )
        return existing_approved

    # 3. Generate and store advisory through advisory_service
    try:
        advisory_record = generate_advisory(forecast=forecast, db=db)
        logger.info(
            f"[ADVISORY_GENERATED_SUCCESSFULLY] forecast_id={forecast_id} "
            f"advisory_id={advisory_record.id} panchayat_id={advisory_record.panchayat_id} "
            f"category=\"{advisory_record.rainfall_category}\" severity={advisory_record.severity}"
        )
        return advisory_record

    except (InvalidForecastInputError, InvalidRainfallError) as e:
        logger.warning(f"[ADVISORY_GENERATION_VALIDATION_ERROR] forecast_id={forecast_id} error={e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid forecast input for advisory generation: {e}",
        ) from e

    except Exception as e:
        logger.error(f"[ADVISORY_GENERATION_FAILED] forecast_id={forecast_id} error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during advisory generation: {e}",
        ) from e


@router.get(
    "/advisory/panchayat/{panchayat_id}",
    response_model=PanchayatAdvisoryRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Approved Agricultural Advisory for a Panchayat",
    description="""
    Retrieve the latest APPROVED agricultural advisory for a specific Gram Panchayat.

    Farmer-Facing Rules:
    - Exclusively returns advisories in `APPROVED` status reviewed and validated by extension officers.
    - Never returns `DRAFT` or `REJECTED` advisories to farmers.
    - If `forecast_date` is omitted, returns the latest approved advisory by date.
    - If no approved advisory exists for the Panchayat or date, returns HTTP 404.
    - Multilingual: Supports `en` (English), `mr` (Marathi), and `hi` (Hindi) with deterministic agronomic templates.
    """,
    responses={
        200: {
            "description": "Approved agricultural advisory successfully retrieved.",
            "model": PanchayatAdvisoryRetrievalResponse,
        },
        404: {
            "description": "No approved advisory found for the specified Panchayat.",
            "content": {"application/json": {"example": {"detail": "No approved advisory found for Panchayat ID '1001'."}}},
        },
        422: {
            "description": "Validation error for path or query parameters.",
            "content": {"application/json": {"example": {"detail": "Input should be greater than or equal to 1"}}},
        },
    },
)
def get_approved_panchayat_advisory(
    panchayat_id: int = Path(
        ...,
        ge=1,
        description="Unique Gram Panchayat identifier (positive integer)",
        examples=[1001],
    ),
    forecast_date: Optional[date] = Query(
        None,
        description="Optional target forecast date (YYYY-MM-DD). If omitted, returns the latest approved advisory.",
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
    HTTP GET handler to retrieve the latest approved agricultural advisory for a Panchayat.
    """
    # 1. Base query for APPROVED status only
    query = (
        db.query(Advisory)
        .filter(
            Advisory.panchayat_id == panchayat_id,
            Advisory.status == "APPROVED",
        )
    )

    # 2. Apply optional date filter
    if forecast_date is not None:
        query = query.filter(Advisory.forecast_date == forecast_date)

    # 3. Order by latest forecast_date, approved_at, and id
    advisory = (
        query
        .order_by(
            Advisory.forecast_date.desc(),
            Advisory.approved_at.desc(),
            Advisory.id.desc(),
        )
        .first()
    )

    # 4. Handle Not Found (Do not return DRAFT or REJECTED advisories)
    if not advisory:
        date_str = f" on date '{forecast_date}'" if forecast_date else ""
        logger.info(f"[ADVISORY_NOT_FOUND] panchayat_id={panchayat_id}{date_str}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approved advisory found for Panchayat ID '{panchayat_id}'{date_str}.",
        )

    # 5. Resolve Panchayat Name and Block Name for complete response
    spatial_names = _resolve_panchayat_spatial_names(panchayat_id, db)

    # 6. Resolve Target Language & Review Readiness Status
    clean_lang = str(lang).lower().strip() if lang else DEFAULT_LANGUAGE
    active_lang = clean_lang if clean_lang in ALL_SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    lang_meta = LANGUAGE_METADATA.get(active_lang, {})
    language_status = lang_meta.get("status", "VERIFIED_PRIMARY")

    # 7. Render localized title and text if non-English requested
    rainfall_category = advisory.rainfall_category or classify_rainfall(advisory.rainfall_mm, convert_negative_to_zero=True)
    rainfall_val = float(advisory.rainfall_mm) if advisory.rainfall_mm is not None else 0.0

    if active_lang != DEFAULT_LANGUAGE and rainfall_category in ADVISORY_RULES_REGISTRY:
        rule = ADVISORY_RULES_REGISTRY[rainfall_category]
        try:
            localized = get_localized_rule_content(rule.rule_id, language=active_lang)
            fmt_context = {
                "panchayat_name": spatial_names["panchayat_name"],
                "block_name": spatial_names["block_name"],
                "forecast_date": str(advisory.forecast_date),
                "lead_days": 0,
                "rainfall_mm": round(rainfall_val, 1),
            }
            advisory_title = localized.title_template.format(**fmt_context)
            advisory_text = "\n".join(f"• {p.format(**fmt_context)}" for p in localized.advisory_points_templates)
        except Exception as loc_err:
            logger.warning(f"Failed to format localized advisory ({active_lang}): {loc_err}")
            advisory_title = advisory.advisory_title
            advisory_text = advisory.advisory_text
    else:
        advisory_title = advisory.advisory_title
        advisory_text = advisory.advisory_text

    logger.info(
        f"[ADVISORY_RETRIEVED_SUCCESSFULLY] advisory_id={advisory.id} panchayat_id={panchayat_id} "
        f"forecast_date={advisory.forecast_date} severity={advisory.severity} lang={active_lang}"
    )

    # 8. Format and return response
    return PanchayatAdvisoryRetrievalResponse(
        advisory_id=advisory.id,
        panchayat_id=advisory.panchayat_id,
        panchayat_name=spatial_names["panchayat_name"],
        block_name=spatial_names["block_name"],
        forecast_date=advisory.forecast_date,
        rainfall_mm=float(advisory.rainfall_mm) if advisory.rainfall_mm is not None else None,
        rainfall_category=advisory.rainfall_category,
        severity=advisory.severity,
        advisory_title=advisory_title,
        advisory_text=advisory_text,
        rule_version=advisory.rule_version,
        status=advisory.status,
        approved_at=advisory.approved_at,
        language=active_lang,
        available_languages=ALL_SUPPORTED_LANGUAGES.copy(),
        language_status=language_status,
    )


@router.get(
    "/advisory/context/{panchayat_id}",
    response_model=AdvisoryContext,
    status_code=status.HTTP_200_OK,
    summary="Get Structured Advisory Context for Panchayat",
    description="""
    Retrieves the canonical, validated AdvisoryContext combining authoritative Panchayat metadata,
    validated numerical downscaled forecast, deterministic agricultural rule risks/recommendations,
    and end-to-end traceability metadata.

    Serves as the internal data ingestion layer for the future AI advisory generator and officer review.
    Does NOT invoke AI, publish advisories, or alter numerical weather predictions.
    """,
    responses={
        200: {
            "description": "Structured advisory context successfully retrieved.",
            "model": AdvisoryContext,
        },
        404: {
            "description": "Panchayat or forecast record not found.",
            "content": {"application/json": {"example": {"detail": "No downscaled forecast found for Panchayat ID '1001'."}}},
        },
        422: {
            "description": "Validation error, hierarchy mismatch, or invalid forecast data.",
            "content": {"application/json": {"example": {"detail": "Forecast contains negative rainfall value."}}},
        },
        500: {
            "description": "Internal server error during context assembly.",
            "content": {"application/json": {"example": {"detail": "Internal error assembling advisory context."}}},
        },
    },
)
def get_advisory_context_endpoint(
    panchayat_id: int = Path(..., ge=1, description="Unique Gram Panchayat database identifier"),
    forecast_id: Optional[int] = Query(None, description="Optional specific forecast record identifier"),
    forecast_date: Optional[date] = Query(None, description="Optional target forecast date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP GET handler to assemble and return the canonical AdvisoryContext.
    """
    try:
        context = default_advisory_context_service.build_advisory_context(
            panchayat_id=panchayat_id,
            forecast_id=forecast_id,
            forecast_date=forecast_date,
            db=db,
        )
        return context
    except CtxPanchayatNotFoundError as err:
        logger.warning(f"[ADVISORY_CONTEXT_PANCHAYAT_NOT_FOUND] {err}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err.message,
        )
    except CtxForecastNotFoundError as err:
        logger.warning(f"[ADVISORY_CONTEXT_FORECAST_NOT_FOUND] {err}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err.message,
        )
    except (CtxForecastMismatchError, CtxHierarchyMismatchError, CtxInvalidForecastDataError, CtxRuleEvaluationError) as err:
        logger.warning(f"[ADVISORY_CONTEXT_VALIDATION_ERROR] {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err.message,
        )
    except AdvisoryContextError as err:
        logger.warning(f"[ADVISORY_CONTEXT_GENERIC_ERROR] {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err.message,
        )
    except Exception as exc:
        logger.error(f"[ADVISORY_CONTEXT_UNHANDLED_EXCEPTION] panchayat_id={panchayat_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error assembling advisory context.",
        )
