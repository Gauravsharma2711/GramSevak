"""
Canonical Normalizer and Validator for Weather Datasets.

Transforms raw heterogeneous district datasets into the standard canonical schema.
Performs data validation, coordinates validation, rainfall validation,
date normalization, lead days calculation, Haversine distance verification,
and detailed quality metric computation.
"""

import logging
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd

from data_pipeline.district_config import DistrictConfig

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS: List[str] = [
    "panchayat_id",
    "lgd_code",
    "panchayat_name",
    "block_name",
    "district_name",
    "panchayat_latitude",
    "panchayat_longitude",
    "elevation_m",
    "date",
    "forecast_issue_date",
    "lead_days",
    "block_forecast_rainfall_mm",
    "station_id",
    "station_latitude",
    "station_longitude",
    "station_distance_km",
    "actual_rainfall_mm",
]


def haversine_vectorized(lat1: pd.Series, lon1: pd.Series, lat2: pd.Series, lon2: pd.Series) -> pd.Series:
    """Calculate the great circle distance between two points on the earth in km."""
    R = 6371.0  # Earth radius in kilometers
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return pd.Series(R * c, index=lat1.index)


def normalize_and_validate_dataset(
    df_raw: pd.DataFrame,
    config: DistrictConfig
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Normalizes raw DataFrame into the canonical schema using DistrictConfig.
    Returns:
        canonical_df: Processed, validated, typed DataFrame
        quality_report: Dictionary with comprehensive validation metrics
    """
    total_raw_rows = len(df_raw)
    raw_columns = list(df_raw.columns)
    
    # 1. Drop configured & unnamed columns
    drop_candidates = [c for c in df_raw.columns if c.startswith("Unnamed") or c in config.drop_columns]
    df = df_raw.drop(columns=drop_candidates, errors="ignore").copy()
    
    # 2. Rename columns based on district config
    df = df.rename(columns=config.column_mapping)
    
    # 3. Text field cleaning and title casing
    if "district_name" in df.columns:
        df["district_name"] = df["district_name"].astype(str).str.strip().str.title()
    else:
        df["district_name"] = config.name

    if "block_name" in df.columns:
        df["block_name"] = (
            df["block_name"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
            .str.title()
        )

    if "panchayat_name" in df.columns:
        df["panchayat_name"] = (
            df["panchayat_name"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
            .str.title()
        )

    if "station_id" in df.columns:
        df["station_id"] = (
            df["station_id"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
        )

    # 4. Extract stable integer panchayat_id and lgd_code
    df["lgd_code"] = pd.to_numeric(df["lgd_code"], errors="coerce").fillna(0).astype(np.int64)
    df["panchayat_id"] = [
        config.panchayat_id_extractor(pid, lgd)
        for pid, lgd in zip(df["panchayat_id"], df["lgd_code"])
    ]
    df["panchayat_id"] = df["panchayat_id"].astype(np.int64)

    # 5. Date parsing and lead_days calculation
    date_parsed = pd.to_datetime(df["date"], format=config.date_format, errors="coerce", dayfirst=True)
    if date_parsed.isnull().all():
        date_parsed = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    issue_parsed = pd.to_datetime(df["forecast_issue_date"], format=config.date_format, errors="coerce", dayfirst=True)
    if issue_parsed.isnull().all():
        issue_parsed = pd.to_datetime(df["forecast_issue_date"], errors="coerce", dayfirst=True)

    lead_days = (date_parsed - issue_parsed).dt.days
    df["lead_days"] = lead_days
    df["date"] = date_parsed.dt.strftime("%Y-%m-%d")
    df["forecast_issue_date"] = issue_parsed.dt.strftime("%Y-%m-%d")

    # 6. Numeric conversions
    numeric_cols = [
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
        "station_latitude",
        "station_longitude",
        "station_distance_km",
        "block_forecast_rainfall_mm",
        "actual_rainfall_mm",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 7. Physical Validations & Quality Metrics
    rejection_mask = pd.Series(False, index=df.index)
    rejection_reasons = []

    # Coordinates validation
    invalid_panch_coords = (
        (df["panchayat_latitude"] < -90) | (df["panchayat_latitude"] > 90) |
        (df["panchayat_longitude"] < -180) | (df["panchayat_longitude"] > 180) |
        df["panchayat_latitude"].isnull() | df["panchayat_longitude"].isnull()
    )
    if invalid_panch_coords.any():
        rejection_mask |= invalid_panch_coords
        rejection_reasons.append(f"Invalid panchayat coordinates: {invalid_panch_coords.sum()} rows")

    # Date validation
    invalid_dates = df["date"].isnull() | df["forecast_issue_date"].isnull()
    if invalid_dates.any():
        rejection_mask |= invalid_dates
        rejection_reasons.append(f"Unparseable dates: {invalid_dates.sum()} rows")

    invalid_lead = df["lead_days"] < 0
    if invalid_lead.any():
        rejection_mask |= invalid_lead
        rejection_reasons.append(f"Negative lead days (issue date > forecast date): {invalid_lead.sum()} rows")

    # Rainfall validation
    # Sentinel check (-999.9) and negative values
    sentinel_actual = df["actual_rainfall_mm"] == -999.9
    df.loc[sentinel_actual, "actual_rainfall_mm"] = np.nan

    negative_actual = df["actual_rainfall_mm"] < 0
    df.loc[negative_actual, "actual_rainfall_mm"] = np.nan

    negative_forecast = df["block_forecast_rainfall_mm"] < 0
    if negative_forecast.any():
        rejection_mask |= negative_forecast
        rejection_reasons.append(f"Negative forecast rainfall: {negative_forecast.sum()} rows")

    # 8. Haversine distance verification
    recalculated_dist = haversine_vectorized(
        df["panchayat_latitude"], df["panchayat_longitude"],
        df["station_latitude"], df["station_longitude"]
    )
    distance_discrepancy = (df["station_distance_km"] - recalculated_dist).abs()
    large_discrepancies = (distance_discrepancy > 1.0).sum()
    moderate_discrepancies = ((distance_discrepancy > 0.1) & (distance_discrepancy <= 1.0)).sum()

    # 9. Duplicates check
    exact_duplicates = df.duplicated().sum()
    panchayat_date_duplicates = df.duplicated(subset=["panchayat_id", "date"]).sum()

    # Filter rejected rows
    valid_df = df[~rejection_mask].copy()
    rejected_count = int(rejection_mask.sum())

    # Ensure canonical columns and types
    valid_df = valid_df[CANONICAL_COLUMNS].copy()
    valid_df["lead_days"] = valid_df["lead_days"].astype(np.int64)
    valid_df["panchayat_latitude"] = valid_df["panchayat_latitude"].round(6)
    valid_df["panchayat_longitude"] = valid_df["panchayat_longitude"].round(6)
    valid_df["station_latitude"] = valid_df["station_latitude"].round(6)
    valid_df["station_longitude"] = valid_df["station_longitude"].round(6)
    valid_df["elevation_m"] = valid_df["elevation_m"].round(1)
    valid_df["station_distance_km"] = valid_df["station_distance_km"].round(2)
    valid_df["block_forecast_rainfall_mm"] = valid_df["block_forecast_rainfall_mm"].round(2)
    valid_df["actual_rainfall_mm"] = valid_df["actual_rainfall_mm"].round(2)

    # 10. Generate Comprehensive Quality Report
    quality_report = {
        "district": config.name,
        "raw_rows": total_raw_rows,
        "valid_rows": len(valid_df),
        "rejected_rows": rejected_count,
        "rejection_reasons": rejection_reasons,
        "raw_columns": raw_columns,
        "canonical_columns": CANONICAL_COLUMNS,
        "unique_panchayats": int(valid_df["panchayat_id"].nunique()),
        "unique_lgd_codes": int(valid_df["lgd_code"].nunique()),
        "unique_blocks": int(valid_df["block_name"].nunique()),
        "block_names": sorted(valid_df["block_name"].unique().tolist()),
        "unique_stations": int(valid_df["station_id"].nunique()),
        "date_range": {
            "min_date": str(valid_df["date"].min()),
            "max_date": str(valid_df["date"].max()),
            "unique_dates_count": int(valid_df["date"].nunique()),
        },
        "forecast_issue_date_range": {
            "min_issue_date": str(valid_df["forecast_issue_date"].min()),
            "max_issue_date": str(valid_df["forecast_issue_date"].max()),
        },
        "lead_days_distribution": {
            str(k): int(v) for k, v in valid_df["lead_days"].value_counts().items()
        },
        "duplicates": {
            "exact_duplicates": int(exact_duplicates),
            "panchayat_date_duplicates": int(panchayat_date_duplicates),
        },
        "coordinates": {
            "lat_min": float(valid_df["panchayat_latitude"].min()),
            "lat_max": float(valid_df["panchayat_latitude"].max()),
            "lon_min": float(valid_df["panchayat_longitude"].min()),
            "lon_max": float(valid_df["panchayat_longitude"].max()),
            "invalid_coordinates_count": int(invalid_panch_coords.sum()),
        },
        "elevation_stats": {
            "min": float(valid_df["elevation_m"].min()),
            "max": float(valid_df["elevation_m"].max()),
            "mean": round(float(valid_df["elevation_m"].mean()), 2),
            "median": round(float(valid_df["elevation_m"].median()), 2),
            "nulls": int(valid_df["elevation_m"].isnull().sum()),
        },
        "station_distance_stats": {
            "min": float(valid_df["station_distance_km"].min()),
            "max": float(valid_df["station_distance_km"].max()),
            "mean": round(float(valid_df["station_distance_km"].mean()), 2),
            "median": round(float(valid_df["station_distance_km"].median()), 2),
            "discrepancies_gt_1km": int(large_discrepancies),
            "discrepancies_0_1_to_1km": int(moderate_discrepancies),
            "max_discrepancy_km": round(float(distance_discrepancy.max()), 4),
        },
        "actual_rainfall_stats": {
            "min": float(valid_df["actual_rainfall_mm"].dropna().min()) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "max": float(valid_df["actual_rainfall_mm"].dropna().max()) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "mean": round(float(valid_df["actual_rainfall_mm"].dropna().mean()), 2) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "median": round(float(valid_df["actual_rainfall_mm"].dropna().median()), 2) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "nulls": int(valid_df["actual_rainfall_mm"].isnull().sum()),
            "sentinel_count": int(sentinel_actual.sum()),
        },
        "block_forecast_stats": {
            "min": float(valid_df["block_forecast_rainfall_mm"].min()),
            "max": float(valid_df["block_forecast_rainfall_mm"].max()),
            "mean": round(float(valid_df["block_forecast_rainfall_mm"].mean()), 2),
            "median": round(float(valid_df["block_forecast_rainfall_mm"].median()), 2),
            "nulls": int(valid_df["block_forecast_rainfall_mm"].isnull().sum()),
        },
    }

    return valid_df, quality_report
