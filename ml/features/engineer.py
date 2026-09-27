"""
GramSevak ML Feature Engineering Engine (Phase 2.2).

Constructs model-ready, leakage-safe features for Panchayat-level rainfall downscaling
strictly governed by the Phase 2.1 ML Data Contract and schemas/ml_feature_registry.json.

Feature Categories:
- Block Forecast: Raw numerical forecast & log1p transformed precipitation
- Spatial & Terrain: Panchayat latitude, longitude, and elevation
- Station Context: Station distance, station latitude, station longitude
- Lead Horizon: Forecast lead time in integer days (lead_days)
- Calendar & Seasonality: Target month, day of year, cyclical sin/cos encoding
- Historical Rainfall Context: Antecedent observations strictly prior to forecast issuance date (t-1d, t-2d, 3d rolling, 7d rolling)

Guarantees:
- Strict mathematical isolation of target variable (actual_rainfall_mm)
- Zero lookahead leakage: all historical features use observations strictly <= forecast_issue_date - 1 day
- Deterministic and reproducible across all districts (Nashik, Pune, future)
"""

import logging
from typing import Tuple, List, Optional, Dict, Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Target variable strictly segregated from feature matrix X
TARGET_COLUMN: str = "actual_rainfall_mm"

# Administrative & temporal tracking metadata (preserved for mapping & evaluation, isolated from X)
METADATA_COLUMNS: List[str] = [
    "panchayat_id",
    "lgd_code",
    "panchayat_name",
    "block_name",
    "district_name",
    "date",
    "forecast_issue_date"
]

# 20 Authoritative approved ML feature columns per schemas/ml_feature_registry.json
FEATURE_COLUMNS: List[str] = [
    # Macro NWP forecast features
    "block_forecast_rainfall_mm",
    "log1p_block_forecast_rainfall_mm",
    
    # Geographic & topographic features
    "panchayat_latitude",
    "panchayat_longitude",
    "elevation_m",
    
    # Station geometric context
    "station_distance_km",
    "station_latitude",
    "station_longitude",
    
    # Forecast lead horizon
    "lead_days",
    
    # Calendar & seasonality features
    "target_month",
    "target_day_of_year",
    "target_day_of_year_sin",
    "target_day_of_year_cos",
    
    # Historical antecedent rainfall features (strictly prior to forecast issuance)
    "historical_rainfall_prior_1d_mm",
    "historical_rainfall_prior_2d_mm",
    "historical_rainfall_prior_3d_mean_mm",
    "historical_rainfall_prior_3d_sum_mm",
    "historical_rainfall_prior_7d_mean_mm",
    "historical_rainfall_prior_7d_sum_mm",
    "has_historical_rainfall_context"
]


def compute_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute deterministic calendar and cyclical seasonality features from target date.
    All dates are known at forecast time.
    """
    result = df.copy()
    
    if "date" in result.columns:
        date_s = pd.to_datetime(result["date"])
        result["target_month"] = date_s.dt.month.astype("int64")
        result["target_day_of_year"] = date_s.dt.dayofyear.astype("int64")
    else:
        result["target_month"] = 1
        result["target_day_of_year"] = 1

    # Cyclical sin/cos transformations (period = 365.25 days)
    day_rad = 2.0 * np.pi * result["target_day_of_year"] / 365.25
    result["target_day_of_year_sin"] = np.sin(day_rad).round(6)
    result["target_day_of_year_cos"] = np.cos(day_rad).round(6)
    
    return result


def compute_forecast_transformations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute non-linear transformations on block forecast precipitation.
    Handles zero values cleanly: log(1 + 0) = 0.
    """
    result = df.copy()
    if "block_forecast_rainfall_mm" in result.columns:
        # Clip at 0 to guarantee non-negative input to log1p
        safe_forecast = result["block_forecast_rainfall_mm"].clip(lower=0.0).fillna(0.0)
        result["log1p_block_forecast_rainfall_mm"] = np.log1p(safe_forecast).round(6)
    else:
        result["block_forecast_rainfall_mm"] = 0.0
        result["log1p_block_forecast_rainfall_mm"] = 0.0
    return result


def compute_lead_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute or validate lead_days as integer horizon (date - forecast_issue_date).
    """
    result = df.copy()
    if "lead_days" in result.columns and result["lead_days"].notna().all():
        result["lead_days"] = result["lead_days"].astype("int64").clip(lower=0)
    elif "date" in result.columns and "forecast_issue_date" in result.columns:
        d = pd.to_datetime(result["date"])
        iss = pd.to_datetime(result["forecast_issue_date"])
        result["lead_days"] = (d - iss).dt.days.fillna(1).astype("int64").clip(lower=0)
    else:
        result["lead_days"] = 1
    return result


def compute_historical_rainfall_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute antecedent historical rainfall features strictly prior to forecast issuance date.
    
    Mathematical Leakage Boundary:
    For a record with target `date` and `forecast_issue_date`:
    - The latest allowable historical observation is dated (forecast_issue_date - 1 day).
    - Under NO circumstances can observations from forecast_issue_date, date, or future dates enter.
    - If prior historical observations do not exist (e.g. initial warm-up period or snapshot datasets
      like Nashik), historical features are set to NaN and has_historical_rainfall_context is set to 0.0.
    """
    result = df.copy()
    
    # Default initialization (NaN for unobserved history, 0.0 for context indicator)
    result["historical_rainfall_prior_1d_mm"] = np.nan
    result["historical_rainfall_prior_2d_mm"] = np.nan
    result["historical_rainfall_prior_3d_mean_mm"] = np.nan
    result["historical_rainfall_prior_3d_sum_mm"] = np.nan
    result["historical_rainfall_prior_7d_mean_mm"] = np.nan
    result["historical_rainfall_prior_7d_sum_mm"] = np.nan
    result["has_historical_rainfall_context"] = 0.0

    # Required columns for historical antecedent calculation
    if not all(col in result.columns for col in ["panchayat_id", "date", "forecast_issue_date", "actual_rainfall_mm"]):
        logger.warning("Historical features skipped: missing required columns (panchayat_id, date, forecast_issue_date, actual_rainfall_mm).")
        return result

    # Check if there is more than 1 date in the dataset (skip single snapshots like Nashik safely)
    if result["date"].nunique() <= 1:
        logger.info("Single snapshot detected (1 unique date). Historical features set to NaN with has_historical_rainfall_context=0.0.")
        return result

    # Standardize dates
    date_dt = pd.to_datetime(result["date"])
    issue_dt = pd.to_datetime(result["forecast_issue_date"])

    # Build unique historical ground truth observation table
    obs_df = result[["panchayat_id", "actual_rainfall_mm"]].copy()
    obs_df["obs_date"] = date_dt
    obs_df = obs_df.dropna(subset=["actual_rainfall_mm"]).drop_duplicates(subset=["panchayat_id", "obs_date"])
    obs_df = obs_df.sort_values(by=["panchayat_id", "obs_date"]).reset_index(drop=True)

    # 1-day prior observation: exact match on (forecast_issue_date - 1 day)
    prior_1d_date = issue_dt - pd.Timedelta(days=1)
    # 2-days prior observation: exact match on (forecast_issue_date - 2 days)
    prior_2d_date = issue_dt - pd.Timedelta(days=2)

    # Merge prior 1d observation
    obs_lookup_1d = obs_df[["panchayat_id", "obs_date", "actual_rainfall_mm"]].rename(
        columns={"obs_date": "lookup_date_1d", "actual_rainfall_mm": "prior_1d"}
    )
    result["_lookup_1d"] = prior_1d_date
    m1 = pd.merge(
        result[["panchayat_id", "_lookup_1d"]].reset_index(),
        obs_lookup_1d,
        left_on=["panchayat_id", "_lookup_1d"],
        right_on=["panchayat_id", "lookup_date_1d"],
        how="left"
    ).set_index("index")
    result["historical_rainfall_prior_1d_mm"] = m1["prior_1d"].astype(float)
    result.drop(columns=["_lookup_1d"], inplace=True)

    # Merge prior 2d observation
    obs_lookup_2d = obs_df[["panchayat_id", "obs_date", "actual_rainfall_mm"]].rename(
        columns={"obs_date": "lookup_date_2d", "actual_rainfall_mm": "prior_2d"}
    )
    result["_lookup_2d"] = prior_2d_date
    m2 = pd.merge(
        result[["panchayat_id", "_lookup_2d"]].reset_index(),
        obs_lookup_2d,
        left_on=["panchayat_id", "_lookup_2d"],
        right_on=["panchayat_id", "lookup_date_2d"],
        how="left"
    ).set_index("index")
    result["historical_rainfall_prior_2d_mm"] = m2["prior_2d"].astype(float)
    result.drop(columns=["_lookup_2d"], inplace=True)

    # Calculate rolling backward statistics on observation table
    # Since obs_df is sorted by obs_date, rolling stats at obs_date T use [T-window, T]
    # When joined on lookup_date_1d (forecast_issue_date - 1 day), all records are strictly <= forecast_issue_date - 1 day.
    grp = obs_df.groupby("panchayat_id")["actual_rainfall_mm"]
    obs_df["roll_3d_sum"] = grp.transform(lambda s: s.rolling(3, min_periods=2).sum())
    obs_df["roll_3d_mean"] = grp.transform(lambda s: s.rolling(3, min_periods=2).mean())
    obs_df["roll_7d_sum"] = grp.transform(lambda s: s.rolling(7, min_periods=4).sum())
    obs_df["roll_7d_mean"] = grp.transform(lambda s: s.rolling(7, min_periods=4).mean())

    obs_roll_lookup = obs_df[[
        "panchayat_id", "obs_date",
        "roll_3d_sum", "roll_3d_mean",
        "roll_7d_sum", "roll_7d_mean"
    ]].rename(columns={"obs_date": "lookup_roll_date"})

    result["_lookup_roll"] = prior_1d_date
    m_roll = pd.merge(
        result[["panchayat_id", "_lookup_roll"]].reset_index(),
        obs_roll_lookup,
        left_on=["panchayat_id", "_lookup_roll"],
        right_on=["panchayat_id", "lookup_roll_date"],
        how="left"
    ).set_index("index")

    result["historical_rainfall_prior_3d_sum_mm"] = m_roll["roll_3d_sum"].astype(float).round(4)
    result["historical_rainfall_prior_3d_mean_mm"] = m_roll["roll_3d_mean"].astype(float).round(4)
    result["historical_rainfall_prior_7d_sum_mm"] = m_roll["roll_7d_sum"].astype(float).round(4)
    result["historical_rainfall_prior_7d_mean_mm"] = m_roll["roll_7d_mean"].astype(float).round(4)
    result.drop(columns=["_lookup_roll"], inplace=True)

    # Context indicator flag (1.0 if any historical antecedent is non-null)
    has_context = (
        result["historical_rainfall_prior_1d_mm"].notna() |
        result["historical_rainfall_prior_3d_mean_mm"].notna()
    ).astype(float)
    result["has_historical_rainfall_context"] = has_context

    return result


def build_feature_dataframe(
    df: pd.DataFrame,
    include_target: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.Series]]:
    """
    Main feature engineering pipeline.
    
    Extracts:
    1. metadata_df: administrative and temporal identifiers (strictly isolated from model training)
    2. features_df: the 20 approved model-ready features (matrix X)
    3. target_series: ground-truth target vector y (actual_rainfall_mm), or None if unavailable/inference
    
    Args:
        df: Input DataFrame conforming to canonical weather schema.
        include_target: Whether to extract target variable y.
        
    Returns:
        Tuple of (metadata_df, features_df, target_series)
    """
    data = df.copy()

    # 1. Lead days calculation/validation
    data = compute_lead_days(data)

    # 2. Calendar and seasonality features
    data = compute_calendar_features(data)

    # 3. Forecast transformations (log1p)
    data = compute_forecast_transformations(data)

    # 4. Station spatial context validation
    for col in ["station_distance_km", "station_latitude", "station_longitude"]:
        if col not in data.columns:
            data[col] = 0.0

    # 5. Topography and coordinates validation
    for col in ["panchayat_latitude", "panchayat_longitude", "elevation_m"]:
        if col not in data.columns:
            data[col] = 0.0

    # 6. Historical antecedent features (leakage-safe)
    data = compute_historical_rainfall_features(data)

    # Ensure all required feature columns exist
    for col in FEATURE_COLUMNS:
        if col not in data.columns:
            data[col] = np.nan

    # 7. Extract Feature Matrix X
    features_df = data[FEATURE_COLUMNS].copy()

    # 8. Extract Metadata Identifiers
    available_meta = [col for col in METADATA_COLUMNS if col in data.columns]
    metadata_df = data[available_meta].copy()

    # 9. Extract Target Vector y
    target_series = None
    if include_target and TARGET_COLUMN in data.columns:
        target_series = data[TARGET_COLUMN].copy()

    logger.info(f"Feature engineering complete: {len(features_df)} rows, {len(FEATURE_COLUMNS)} approved features.")
    return metadata_df, features_df, target_series


def extract_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Backward-compatible feature extraction interface.
    Returns (X: pd.DataFrame, y: pd.Series).
    """
    _, X, y = build_feature_dataframe(df, include_target=True)
    if y is None:
        y = pd.Series(index=X.index, dtype=float)
    return X, y
