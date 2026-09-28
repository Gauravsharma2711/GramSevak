"""
Agricultural Advisory Service Module.

Connects stored downscaled weather forecasts to the deterministic advisory engine,
generating, formatting, and persisting DRAFT advisories to Supabase PostgreSQL.

Safety & Design Invariants:
1. Purely deterministic and rule-based (NO LLM is used).
2. Never modifies the original forecast record.
3. Explicitly links advisory records to forecast_id and panchayat_id.
4. Uses downscaled_rainfall_mm exclusively (never uses actual ground rainfall).
5. All newly generated advisories are stored in 'DRAFT' status for extension officer review.
"""

import os
import sys
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import text

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from src.advisory.rainfall_classifier import (
    classify_rainfall,
    RainfallCategory,
    InvalidRainfallError,
)
from src.advisory.advisory_engine import (
    generate_agricultural_advisory,
    AdvisoryEngine,
    AdvisoryOutput,
    RULE_VERSION,
)

from backend.app.models.panchayat import Panchayat

logger = logging.getLogger(__name__)


# =====================================================================
# CUSTOM SERVICE EXCEPTIONS
# =====================================================================
class AdvisoryServiceError(Exception):
    """Base exception for Advisory Service errors."""
    pass


class InvalidForecastInputError(AdvisoryServiceError):
    """Raised when provided forecast input is missing required attributes or malformed."""
    pass


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def _resolve_panchayat_spatial_names(
    panchayat_id: int,
    db: Optional[Session] = None,
) -> Dict[str, str]:
    """
    Look up panchayat_name, block_name, and district_name for a given panchayat_id
    using the normalized administrative hierarchy, with safe fallback to legacy tables.
    """
    if db is not None:
        try:
            # 1. Primary: Query normalized Panchayat model (with Block and District relationships)
            p = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
            if p:
                b_name = p.block.name if p.block else "Unknown Block"
                d_name = p.district.name if p.district else "Maharashtra"
                return {
                    "panchayat_name": str(p.name),
                    "block_name": str(b_name),
                    "district_name": str(d_name),
                }

            # 2. Secondary: Fallback to legacy panchayat_weather_data
            query = text("""
                SELECT panchayat_name, block_name, district_name
                FROM panchayat_weather_data
                WHERE panchayat_id = :pid
                LIMIT 1;
            """)
            result = db.execute(query, {"pid": panchayat_id}).mappings().first()
            if result:
                return {
                    "panchayat_name": str(result.get("panchayat_name") or f"Panchayat-{panchayat_id}"),
                    "block_name": str(result.get("block_name") or "Unknown Block"),
                    "district_name": str(result.get("district_name") or "Maharashtra"),
                }
        except Exception as e:
            logger.warning(f"Failed to lookup spatial names for panchayat_id {panchayat_id}: {e}")

    return {
        "panchayat_name": f"Panchayat-{panchayat_id}",
        "block_name": "Unknown Block",
        "district_name": "Maharashtra",
    }


def _extract_forecast_attributes(forecast: Any) -> Dict[str, Any]:
    """
    Safely extract required attributes from SQLAlchemy model, dict, or object
    without mutating the original object.
    """
    if forecast is None:
        raise InvalidForecastInputError("Forecast input is null (None).")

    if isinstance(forecast, dict):
        f_id = forecast.get("id") or forecast.get("forecast_id")
        p_id = forecast.get("panchayat_id")
        f_date = forecast.get("forecast_date")
        issue_date = forecast.get("forecast_issue_date")
        rainfall_val = forecast.get("downscaled_rainfall_mm")
        p_name = forecast.get("panchayat_name")
        b_name = forecast.get("block_name")
    else:
        f_id = getattr(forecast, "id", getattr(forecast, "forecast_id", None))
        p_id = getattr(forecast, "panchayat_id", None)
        f_date = getattr(forecast, "forecast_date", None)
        issue_date = getattr(forecast, "forecast_issue_date", None)
        rainfall_val = getattr(forecast, "downscaled_rainfall_mm", None)
        p_name = getattr(forecast, "panchayat_name", None)
        b_name = getattr(forecast, "block_name", None)

    if p_id is None:
        raise InvalidForecastInputError("Forecast must contain a valid 'panchayat_id'.")

    if f_date is None:
        raise InvalidForecastInputError("Forecast must contain a valid 'forecast_date'.")

    if rainfall_val is None:
        raise InvalidForecastInputError("Forecast must contain a valid 'downscaled_rainfall_mm'.")

    # Compute lead days if both dates are present
    lead_days = 0
    if issue_date and f_date:
        try:
            d_target = f_date if isinstance(f_date, date) else datetime.strptime(str(f_date).strip(), "%Y-%m-%d").date()
            d_issue = issue_date if isinstance(issue_date, date) else datetime.strptime(str(issue_date).strip(), "%Y-%m-%d").date()
            lead_days = max(0, (d_target - d_issue).days)
        except Exception:
            lead_days = 0

    return {
        "forecast_id": int(f_id) if f_id is not None else None,
        "panchayat_id": int(p_id),
        "forecast_date": f_date if isinstance(f_date, date) else datetime.strptime(str(f_date).strip()[:10], "%Y-%m-%d").date(),
        "downscaled_rainfall_mm": float(rainfall_val),
        "lead_days": lead_days,
        "panchayat_name": p_name,
        "block_name": b_name,
    }


# =====================================================================
# ADVISORY GENERATION SERVICE
# =====================================================================
def generate_advisory(
    forecast: Union[DownscaledForecast, Dict[str, Any], Any],
    db: Optional[Session] = None,
    engine: Optional[AdvisoryEngine] = None,
) -> Advisory:
    """
    Generate and persist a deterministic agricultural advisory for a downscaled forecast.

    Workflow:
    1. Receive a stored Panchayat forecast (SQLAlchemy model or dict).
    2. Read downscaled_rainfall_mm.
    3. Classify rainfall category.
    4. Select applicable deterministic advisory rules.
    5. Generate structured advisory text.
    6. Assign severity (LOW, MODERATE, HIGH, CRITICAL).
    7. Assign rule_version (e.g. v1.0.0).
    8. Create a DRAFT advisory record referencing the forecast ID.
    9. Save the advisory to Supabase PostgreSQL.
    10. Return the persisted advisory ORM entity.

    Guarantees:
    - Never modifies the original forecast.
    - References the forecast ID.
    - Does NOT use actual rainfall.
    - Does NOT use an LLM.

    Args:
        forecast: Stored DownscaledForecast entity or dictionary.
        db: Optional SQLAlchemy Session. If None, a new session is created.
        engine: Optional custom AdvisoryEngine instance.

    Returns:
        Advisory: Persisted SQLAlchemy advisory instance in 'DRAFT' status.

    Raises:
        InvalidForecastInputError: If forecast attributes are missing or invalid.
        AdvisoryServiceError: If database persistence fails.
    """
    # 1 & 2. Extract forecast attributes safely (immutable copy)
    attr = _extract_forecast_attributes(forecast)
    rainfall_mm = attr["downscaled_rainfall_mm"]
    panchayat_id = attr["panchayat_id"]
    forecast_id = attr["forecast_id"]
    forecast_date = attr["forecast_date"]
    lead_days = attr["lead_days"]

    # Manage DB session lifecycle
    should_close_db = False
    active_db = db
    if active_db is None:
        active_db = SessionLocal()
        should_close_db = True

    try:
        # Spatial metadata lookup if not in forecast
        panchayat_name = attr["panchayat_name"]
        block_name = attr["block_name"]
        if not panchayat_name or not block_name:
            names = _resolve_panchayat_spatial_names(panchayat_id, active_db)
            panchayat_name = panchayat_name or names["panchayat_name"]
            block_name = block_name or names["block_name"]

        # 3, 4, 5, 6, 7. Classify rainfall, apply rules, format advisory text & severity
        adv_engine = engine or AdvisoryEngine()
        advisory_output: AdvisoryOutput = adv_engine.generate_advisory(
            rainfall_mm=rainfall_mm,
            panchayat_name=panchayat_name,
            block_name=block_name,
            forecast_date=forecast_date,
            lead_days=lead_days,
        )

        # Format full advisory text with clean bullet points
        formatted_text = "\n".join(f"• {point}" for point in advisory_output.advisory_points)

        # 8. Create a DRAFT advisory entity
        advisory_record = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast_id,
            forecast_date=forecast_date,
            rainfall_mm=round(rainfall_mm, 2),
            rainfall_category=advisory_output.rainfall_category,
            severity=advisory_output.severity,
            advisory_title=advisory_output.advisory_title,
            advisory_text=formatted_text,
            rule_version=advisory_output.rule_version,
            status="DRAFT",
            officer_id=None,
            officer_comment=None,
            approved_at=None,
        )

        # 9. Save it to Supabase
        active_db.add(advisory_record)
        active_db.commit()
        active_db.refresh(advisory_record)

        logger.info(
            f"Generated DRAFT advisory ID={advisory_record.id} for Panchayat {panchayat_id} "
            f"on {forecast_date} (Forecast ID={forecast_id}, Rule={advisory_output.rule_id})."
        )

        # 10. Return the advisory
        return advisory_record

    except Exception as e:
        active_db.rollback()
        if isinstance(e, (InvalidForecastInputError, InvalidRainfallError)):
            raise
        logger.error(f"Failed to generate and persist advisory: {e}", exc_info=True)
        raise AdvisoryServiceError(f"Advisory generation failed: {e}") from e

    finally:
        if should_close_db:
            active_db.close()
