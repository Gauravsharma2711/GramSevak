"""
Forecast Generation API Endpoints.
Handles execution of micro-level weather downscaling for Gram Panchayats
and stores predictions in Supabase PostgreSQL downscaled_forecasts table.
"""

import logging
from datetime import date
from typing import Optional
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Path as FastAPIPath, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.logging import (
    log_forecast_request,
    log_prediction_success,
    log_prediction_failure,
    log_db_operation,
)
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.panchayat_weather import PanchayatWeatherData
from backend.app.models.panchayat import Panchayat
from backend.app.schemas.forecast import (
    ForecastGenerateRequest,
    ForecastGenerateResponse,
    ForecastRetrievalResponse,
)
from src.services.forecast_service import (
    generate_panchayat_forecast,
    PanchayatNotFoundError,
    BlockForecastNotFoundError,
    MissingFeatureError,
    ModelUnavailableError,
    ForecastServiceError,
)
from src.validation.forecast_validation import (
    validate_forecast_output,
    InvalidForecastOutputError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/forecast/generate",
    response_model=ForecastGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Micro-Level Weather Forecast",
    description=(
        "Downscales block-level weather forecast to high-resolution Gram Panchayat level "
        "using local terrain, spatial, and meteorological features with zero future data leakage. "
        "The resulting forecast is automatically stored in the downscaled_forecasts database."
    ),
    response_description="Generated downscaled rainfall forecast with metadata",
    responses={
        200: {"description": "Downscaled forecast generated and recorded successfully."},
        404: {"description": "Panchayat or numerical block forecast not found."},
        422: {"description": "Missing required Panchayat features or invalid date range."},
        503: {"description": "ML downscaling model is unavailable or unloaded."},
        500: {"description": "Unexpected model error during forecast generation."},
    },
    tags=["Forecasts"],
)
def generate_forecast(
    payload: ForecastGenerateRequest,
    db: Session = Depends(get_db),
) -> ForecastGenerateResponse:
    """
    Generate downscaled weather forecast for the specified Panchayat and dates.
    1. Validates dates (forecast_date >= forecast_issue_date).
    2. Resolves Panchayat and administrative block.
    3. Retrieves applicable block forecast.
    4. Extracts spatial, elevation, and proximity features.
    5. Computes lead days and seasonal temporal features.
    6. Executes downscaling inference via ModelService (never using actual rainfall).
    7. Stores downscaled forecast into Supabase 'downscaled_forecasts' table.
    8. Returns the generated forecast.
    """
    log_forecast_request(
        logger=logger,
        request_type="POST /api/v1/forecast/generate",
        panchayat_id=payload.panchayat_id,
        forecast_date=payload.forecast_date,
        forecast_issue_date=payload.forecast_issue_date,
    )

    try:
        # Generate forecast via ForecastService
        result = generate_panchayat_forecast(
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            forecast_issue_date=payload.forecast_issue_date,
            db=db,
        )

        # Validate output before persistence
        validated_output = validate_forecast_output(
            result.get("raw_predicted_rainfall_mm", result.get("downscaled_rainfall_mm"))
        )

        log_prediction_success(
            logger=logger,
            panchayat_id=result["panchayat_id"],
            block_name=result["block_name"],
            forecast_date=payload.forecast_date,
            model_name=result["model_name"],
            model_version=result["model_version"],
            block_forecast_mm=float(result["block_forecast_rainfall_mm"]),
            downscaled_rainfall_mm=float(validated_output.downscaled_rainfall_mm),
        )

        # Persist downscaled prediction to database
        try:
            # TODO (Day 5+): Implement statistical confidence/uncertainty calibration based on historical model residuals.
            # Confidence is kept None on Day 4 to avoid arbitrary ungrounded percentages.
            forecast_record = DownscaledForecast(
                panchayat_id=result["panchayat_id"],
                forecast_date=payload.forecast_date,
                forecast_issue_date=payload.forecast_issue_date,
                block_forecast_rainfall_mm=result["block_forecast_rainfall_mm"],
                downscaled_rainfall_mm=validated_output.downscaled_rainfall_mm,
                model_name=result["model_name"],
                model_version=result["model_version"],
                confidence=None,
            )
            db.add(forecast_record)
            db.commit()
            db.refresh(forecast_record)
            log_db_operation(
                logger=logger,
                operation="INSERT",
                table="downscaled_forecasts",
                status="SUCCESS",
                panchayat_id=result["panchayat_id"],
                forecast_date=payload.forecast_date,
            )
        except Exception as db_err:
            db.rollback()
            log_db_operation(
                logger=logger,
                operation="INSERT",
                table="downscaled_forecasts",
                status="FAILURE",
                panchayat_id=result["panchayat_id"],
                forecast_date=payload.forecast_date,
                details=str(db_err),
                level=logging.WARNING,
            )

        return ForecastGenerateResponse(
            panchayat_id=result["panchayat_id"],
            panchayat_name=result["panchayat_name"],
            block_name=result["block_name"],
            district_name=result["district_name"],
            forecast_date=payload.forecast_date,
            forecast_issue_date=payload.forecast_issue_date,
            lead_days=int(result["lead_days"]),
            block_forecast_rainfall_mm=float(result["block_forecast_rainfall_mm"]),
            downscaled_rainfall_mm=float(validated_output.downscaled_rainfall_mm),
            model_name=result["model_name"],
            model_version=result["model_version"],
            confidence=None,
        )

    except InvalidForecastOutputError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Invalid ML output: {e}",
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model generated invalid rainfall output: {e}",
        )

    except PanchayatNotFoundError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Panchayat not found: {e}",
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except BlockForecastNotFoundError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Block forecast not found: {e}",
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except MissingFeatureError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Missing feature: {e}",
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    except ModelUnavailableError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Model unavailable: {e}",
            level=logging.CRITICAL,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    except ForecastServiceError as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Forecast service error: {e}",
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast generation failed: {e}",
        )

    except Exception as e:
        log_prediction_failure(
            logger=logger,
            panchayat_id=payload.panchayat_id,
            forecast_date=payload.forecast_date,
            reason=f"Unexpected error: {e}",
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected internal model error: {e}",
        )


PROCESSED_DATA_PATH = Path("data/processed/nashik_weather_clean.csv")


@router.get(
    "/forecast/panchayat/{panchayat_id}",
    response_model=ForecastRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Stored Downscaled Forecast",
    description=(
        "Retrieves the latest or date-filtered stored downscaled weather forecast for a Gram Panchayat "
        "from the downscaled_forecasts database. Does not execute new ML model inference."
    ),
    response_description="Stored downscaled forecast record",
    responses={
        200: {"description": "Stored forecast record retrieved successfully."},
        404: {"description": "No stored forecast found for the requested Panchayat/date."},
    },
    tags=["Forecasts"],
)
def get_panchayat_forecast(
    panchayat_id: int = FastAPIPath(
        ...,
        ge=1,
        description="Unique identifier of the Gram Panchayat",
        examples=[1001],
    ),
    forecast_date: Optional[date] = Query(
        None,
        description="Optional target forecast date (YYYY-MM-DD). If omitted, returns the latest recorded forecast.",
        examples=["2026-05-09"],
    ),
    db: Session = Depends(get_db),
) -> ForecastRetrievalResponse:
    """
    Retrieve stored downscaled forecast from Supabase database table downscaled_forecasts.
    Returns HTTP 404 if no forecast exists.
    """
    log_forecast_request(
        logger=logger,
        request_type="GET /api/v1/forecast/panchayat/{panchayat_id}",
        panchayat_id=panchayat_id,
        forecast_date=forecast_date or "LATEST",
    )

    # 1. Resolve Panchayat metadata dynamically from normalized hierarchy
    panchayat_name = f"Panchayat-{panchayat_id}"
    block_name = "Unknown"
    district_name = "Unknown"

    p_norm = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
    if p_norm is not None:
        panchayat_name = str(p_norm.name or panchayat_name)
        if p_norm.block is not None:
            block_name = str(p_norm.block.name or block_name)
        if p_norm.district is not None:
            district_name = str(p_norm.district.name or district_name)
    else:
        p_row = (
            db.query(
                PanchayatWeatherData.panchayat_name,
                PanchayatWeatherData.block_name,
                PanchayatWeatherData.district_name,
            )
            .filter(PanchayatWeatherData.panchayat_id == panchayat_id)
            .first()
        )
        if p_row is not None:
            panchayat_name = str(p_row.panchayat_name or panchayat_name)
            block_name = str(p_row.block_name or block_name)
            district_name = str(p_row.district_name or district_name)
        elif PROCESSED_DATA_PATH.exists():
            try:
                df = pd.read_csv(PROCESSED_DATA_PATH)
                match = df[df["panchayat_id"] == panchayat_id]
                if not match.empty:
                    r = match.iloc[0]
                    panchayat_name = str(r.get("panchayat_name", panchayat_name))
                    block_name = str(r.get("block_name", block_name))
                    district_name = str(r.get("district_name", district_name))
            except Exception:
                pass

    # 2. Query downscaled_forecasts table
    query = db.query(DownscaledForecast).filter(DownscaledForecast.panchayat_id == panchayat_id)
    if forecast_date is not None:
        query = query.filter(DownscaledForecast.forecast_date == forecast_date)

    forecast_row = query.order_by(
        DownscaledForecast.forecast_date.desc(),
        DownscaledForecast.id.desc(),
    ).first()

    if forecast_row is not None:
        f_date = forecast_row.forecast_date
        f_issue = forecast_row.forecast_issue_date or f_date
        lead_days = (f_date - f_issue).days if (f_date and f_issue) else 0
        lead_days = max(lead_days, 0)

        log_db_operation(
            logger=logger,
            operation="SELECT",
            table="downscaled_forecasts",
            status="SUCCESS",
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            details=f"retrieved_record_id={forecast_row.id}",
        )

        return ForecastRetrievalResponse(
            panchayat_id=int(panchayat_id),
            panchayat_name=panchayat_name,
            block_name=block_name,
            district_name=district_name,
            forecast_date=f_date,
            forecast_issue_date=f_issue,
            lead_days=int(lead_days),
            block_forecast_rainfall_mm=float(forecast_row.block_forecast_rainfall_mm or 0.0),
            downscaled_rainfall_mm=float(forecast_row.downscaled_rainfall_mm or 0.0),
            model_name=str(forecast_row.model_name or "XGBoost Regressor"),
            model_version=str(forecast_row.model_version or "v1.0.0"),
            confidence=float(forecast_row.confidence) if forecast_row.confidence is not None else None,
        )

    # 3. If no stored record exists, return HTTP 404
    log_db_operation(
        logger=logger,
        operation="SELECT",
        table="downscaled_forecasts",
        status="NOT_FOUND",
        panchayat_id=panchayat_id,
        forecast_date=forecast_date,
        level=logging.WARNING,
    )
    date_msg = f" on date '{forecast_date}'" if forecast_date else ""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No stored downscaled forecast found for Panchayat {panchayat_id}{date_msg}.",
    )
