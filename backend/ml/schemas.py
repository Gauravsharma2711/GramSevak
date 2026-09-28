"""
GramSevak ML Input and Output Schemas (Phase 2.7).

Provides strict Pydantic data validation for Panchayat-level rainfall downscaling inference:
- Rejects future target information and target-derived labels
- Enforces prediction-time temporal constraints (forecast_date >= forecast_issue_date)
- Validates geographic coordinate ranges and non-negative precipitation inputs
- Enforces explicit prediction_mode ('ml' vs 'fallback') without fabricating confidence
"""

from datetime import date, datetime, timezone
from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel, Field, model_validator


# Strictly forbidden keys that represent ground truth target leakage
FORBIDDEN_LEAKAGE_FIELDS = {
    "actual_rainfall_mm",
    "target_actual_rainfall_mm",
    "actual_rainfall",
    "target_rainfall",
    "ground_truth_rainfall",
    "observed_rainfall_mm",
    "y_true"
}


class DownscaleInferenceRequest(BaseModel):
    """
    Request payload for Panchayat-level weather forecast downscaling.
    Contains only information legally available at forecast issuance time.
    """
    panchayat_id: Union[int, str] = Field(..., description="Unique identifier for Gram Panchayat")
    forecast_date: date = Field(..., description="Target calendar date for rainfall prediction")
    forecast_issue_date: date = Field(..., description="Date on which regional NWP forecast was issued")
    block_forecast_rainfall_mm: Optional[float] = Field(default=None, ge=0.0, description="Numerical block-level forecast rainfall in mm")

    panchayat_latitude: Optional[float] = Field(default=None, ge=8.0, le=38.0, description="Latitude centroid in decimal degrees")
    panchayat_longitude: Optional[float] = Field(default=None, ge=68.0, le=98.0, description="Longitude centroid in decimal degrees")
    elevation_m: Optional[float] = Field(default=None, ge=-100.0, le=9000.0, description="Elevation above sea level in meters")

    station_distance_km: Optional[float] = Field(default=None, ge=0.0, description="Distance to nearest AWS sensor in km")
    station_latitude: Optional[float] = Field(default=None, ge=8.0, le=38.0, description="Nearest AWS station latitude")
    station_longitude: Optional[float] = Field(default=None, ge=68.0, le=98.0, description="Nearest AWS station longitude")

    lead_days: Optional[int] = Field(default=None, ge=0, description="Forecast lead time in days")

    # Antecedent Historical Rainfall (strictly prior to forecast issue)
    historical_rainfall_prior_1d_mm: Optional[float] = Field(default=None, ge=0.0, description="Observed rainfall at t-1 day (mm)")
    historical_rainfall_prior_2d_mm: Optional[float] = Field(default=None, ge=0.0, description="Observed rainfall at t-2 days (mm)")
    historical_rainfall_prior_3d_mean_mm: Optional[float] = Field(default=None, ge=0.0, description="3-day trailing mean rainfall (mm)")
    historical_rainfall_prior_3d_sum_mm: Optional[float] = Field(default=None, ge=0.0, description="3-day trailing cumulative rainfall (mm)")
    historical_rainfall_prior_7d_mean_mm: Optional[float] = Field(default=None, ge=0.0, description="7-day trailing mean rainfall (mm)")
    historical_rainfall_prior_7d_sum_mm: Optional[float] = Field(default=None, ge=0.0, description="7-day trailing cumulative rainfall (mm)")
    has_historical_rainfall_context: Optional[int] = Field(default=None, ge=0, le=1, description="Binary context availability flag")

    # Optional metadata (ignored during feature building)
    panchayat_name: Optional[str] = Field(default=None, description="Descriptive Panchayat name")
    block_name: Optional[str] = Field(default=None, description="Administrative block name")
    district_name: Optional[str] = Field(default=None, description="District name (e.g. Pune, Nashik)")

    @model_validator(mode="before")
    @classmethod
    def check_leakage_and_temporal_boundaries(cls, data: Any) -> Any:
        """Reject target leakage fields and enforce forecast_date >= forecast_issue_date."""
        if isinstance(data, dict):
            # 1. Leakage field check
            detected_leaks = [k for k in data.keys() if k.lower() in FORBIDDEN_LEAKAGE_FIELDS]
            if detected_leaks:
                raise ValueError(f"Target leakage violation: Request contains forbidden target fields {detected_leaks}.")

            # 2. Date ordering check
            f_date = data.get("forecast_date")
            i_date = data.get("forecast_issue_date")
            if f_date and i_date:
                # Convert strings to date objects if needed for comparison
                d_f = date.fromisoformat(f_date) if isinstance(f_date, str) else f_date
                d_i = date.fromisoformat(i_date) if isinstance(i_date, str) else i_date
                if d_f < d_i:
                    raise ValueError(f"Temporal violation: forecast_date ({d_f}) cannot precede forecast_issue_date ({d_i}).")

        return data


class DownscaleInferenceResponse(BaseModel):
    """
    Structured response containing downscaled Panchayat rainfall prediction and model provenance.
    """
    panchayat_id: Union[int, str] = Field(..., description="Gram Panchayat identifier")
    forecast_date: date = Field(..., description="Target forecast date")
    forecast_issue_date: date = Field(..., description="Forecast issue date")
    lead_days: int = Field(..., ge=0, description="Calculated lead time in days")
    block_forecast_rainfall_mm: float = Field(..., ge=0.0, description="Original macro block NWP forecast in mm")
    downscaled_rainfall_mm: float = Field(..., ge=0.0, description="Hyper-local downscaled prediction in mm")
    model_name: str = Field(..., description="Identifier of the executing model")
    model_version: str = Field(..., description="Semantic version of the model")
    feature_registry_version: str = Field(..., description="Feature registry contract version")
    prediction_mode: str = Field(..., description="'ml' for successful model execution, 'fallback' for deterministic fallback")
    confidence: Optional[float] = Field(default=None, description="Calibrated confidence score (None if uncalibrated)")
    inference_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of inference execution")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic telemetry (e.g. latency, fallback rationale)")
