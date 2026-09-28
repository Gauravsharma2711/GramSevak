"""
Pydantic Schemas for Weather Forecast Generation and Downscaling Endpoints.
Ensures strict validation of dates, input IDs, and standardized output representation.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ForecastGenerateRequest(BaseModel):
    """
    Request payload for generating a micro-level downscaled weather forecast.
    """
    model_config = ConfigDict(from_attributes=True)

    panchayat_id: int = Field(
        ...,
        ge=1,
        description="Unique identifier of the target Gram Panchayat",
        examples=[1001],
    )
    forecast_date: date = Field(
        ...,
        description="Target forecast date (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    forecast_issue_date: date = Field(
        ...,
        description="Date on which the numerical weather forecast was issued (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    block_forecast_rainfall_mm: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional block-level rainfall forecast override in mm",
        examples=[18.5],
    )

    @model_validator(mode="after")
    def validate_date_sequence(self) -> "ForecastGenerateRequest":
        if self.forecast_date < self.forecast_issue_date:
            raise ValueError(
                f"forecast_date ({self.forecast_date}) cannot be earlier than "
                f"forecast_issue_date ({self.forecast_issue_date})."
            )
        return self


class ForecastGenerateResponse(BaseModel):
    """
    Downscaled micro-level weather forecast response for a Gram Panchayat.
    """
    model_config = ConfigDict(from_attributes=True)

    panchayat_id: int = Field(
        ...,
        description="Unique system Panchayat identifier",
        examples=[1001],
    )
    panchayat_name: str = Field(
        ...,
        description="Name of the Gram Panchayat",
        examples=["Ajmer Saundane"],
    )
    block_name: str = Field(
        ...,
        description="Administrative Tehsil / Block name",
        examples=["Baglan"],
    )
    district_name: str = Field(
        ...,
        description="District name (Nashik)",
        examples=["Nashik"],
    )
    forecast_date: date = Field(
        ...,
        description="Target forecast date (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    forecast_issue_date: date = Field(
        ...,
        description="Date on which the numerical weather forecast was issued (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    lead_days: int = Field(
        ...,
        ge=0,
        description="Lead days between issue date and forecast target date",
        examples=[0],
    )
    block_forecast_rainfall_mm: float = Field(
        ...,
        description="Original baseline numerical block forecast rainfall in mm",
        examples=[15.0],
    )
    downscaled_rainfall_mm: float = Field(
        ...,
        ge=0.0,
        description="ML downscaled micro-level rainfall forecast in mm for the Panchayat",
        examples=[12.7831],
    )
    model_name: str = Field(
        ...,
        description="Name of the ML model used for inference",
        examples=["XGBoost Regressor"],
    )
    model_version: str = Field(
        ...,
        description="Version tag of the deployed ML model",
        examples=["v1.0.0"],
    )
    confidence: Optional[float] = Field(
        None,
        description=(
            "Model prediction uncertainty / confidence metric. Null by default "
            "unless statistical calibration is provided."
        ),
        examples=[None],
    )


class ForecastRetrievalResponse(BaseModel):
    """
    Stored historical or latest downscaled weather forecast response for a Gram Panchayat.
    Includes nullable confidence score and model versioning metadata.
    """
    model_config = ConfigDict(from_attributes=True)

    panchayat_id: int = Field(
        ...,
        description="Unique system Panchayat identifier",
        examples=[1001],
    )
    panchayat_name: str = Field(
        ...,
        description="Name of the Gram Panchayat",
        examples=["Ajmer Saundane"],
    )
    block_name: str = Field(
        ...,
        description="Administrative Tehsil / Block name",
        examples=["Baglan"],
    )
    district_name: str = Field(
        ...,
        description="District name (Nashik)",
        examples=["Nashik"],
    )
    forecast_date: date = Field(
        ...,
        description="Target forecast date (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    forecast_issue_date: date = Field(
        ...,
        description="Date on which the numerical weather forecast was issued (YYYY-MM-DD)",
        examples=["2026-05-09"],
    )
    lead_days: int = Field(
        ...,
        ge=0,
        description="Lead days between issue date and forecast target date",
        examples=[0],
    )
    block_forecast_rainfall_mm: float = Field(
        ...,
        description="Original baseline numerical block forecast rainfall in mm",
        examples=[15.0],
    )
    downscaled_rainfall_mm: float = Field(
        ...,
        ge=0.0,
        description="ML downscaled micro-level rainfall forecast in mm for the Panchayat",
        examples=[12.7831],
    )
    model_name: str = Field(
        ...,
        description="Name of the ML model used for inference",
        examples=["XGBoost Regressor"],
    )
    model_version: str = Field(
        ...,
        description="Version tag of the deployed ML model",
        examples=["v1.0.0"],
    )
    confidence: Optional[float] = Field(
        None,
        description=(
            "Model prediction uncertainty / confidence metric. Null by default "
            "unless statistical calibration is provided."
        ),
        examples=[None],
    )
