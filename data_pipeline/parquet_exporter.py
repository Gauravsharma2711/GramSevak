"""
Parquet Exporter for Normalized Weather and ML Datasets.

Writes scalable columnar Parquet datasets:
- data/processed/canonical_{district}.parquet
- data/processed/panchayats.parquet
- data/processed/forecasts.parquet
- data/processed/observations.parquet
- data/processed/training_dataset.parquet

Maintains multi-district incremental consolidation and ML feature preparation.
"""

import os
import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

PROCESSED_DIR = "data/processed"


def export_district_to_parquet(
    df: pd.DataFrame,
    district_name: str,
    output_dir: str = PROCESSED_DIR
) -> Dict[str, str]:
    """
    Exports normalized dataset into canonical Parquet files.
    Merges with existing cross-district Parquets to support multi-district scaling.
    """
    os.makedirs(output_dir, exist_ok=True)
    created_files = {}
    clean_dist = district_name.strip().lower()

    # 1. District-Specific Canonical Parquet
    canonical_district_path = os.path.join(output_dir, f"canonical_{clean_dist}.parquet")
    df.to_parquet(canonical_district_path, index=False, engine="pyarrow", compression="snappy")
    created_files[f"canonical_{clean_dist}"] = canonical_district_path
    logger.info(f"Saved canonical {district_name} Parquet to {canonical_district_path} ({len(df):,} rows)")

    # 2. Panchayats Parquet (Cumulative across districts)
    panchayats_path = os.path.join(output_dir, "panchayats.parquet")
    panch_cols = [
        "panchayat_id",
        "lgd_code",
        "panchayat_name",
        "block_name",
        "district_name",
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
    ]
    current_panch = (
        df.sort_values(by=["panchayat_id", "date"], ascending=[True, False])[panch_cols]
        .drop_duplicates(subset=["panchayat_id"])
        .copy()
    )

    if os.path.exists(panchayats_path):
        try:
            existing_panch = pd.read_parquet(panchayats_path)
            # Filter out current district to avoid stale records, then concat
            other_panch = existing_panch[existing_panch["district_name"].str.lower() != clean_dist]
            combined_panch = pd.concat([other_panch, current_panch], ignore_index=True)
        except Exception as e:
            logger.warning(f"Could not merge with existing panchayats.parquet ({e}), overwriting with current.")
            combined_panch = current_panch
    else:
        combined_panch = current_panch

    combined_panch = combined_panch.sort_values(by=["district_name", "panchayat_id"])
    combined_panch.to_parquet(panchayats_path, index=False, engine="pyarrow", compression="snappy")
    created_files["panchayats"] = panchayats_path
    logger.info(f"Saved Panchayats Parquet to {panchayats_path} ({len(combined_panch):,} unique panchayats)")

    # 3. Forecasts Parquet (Cumulative across districts)
    forecasts_path = os.path.join(output_dir, "forecasts.parquet")
    forecast_group_cols = [
        "district_name",
        "block_name",
        "forecast_issue_date",
        "date",
        "lead_days",
    ]
    current_forecasts = (
        df.groupby(forecast_group_cols, as_index=False)["block_forecast_rainfall_mm"]
        .mean()
        .round(2)
        .rename(columns={"date": "forecast_date"})
    )

    if os.path.exists(forecasts_path):
        try:
            existing_forecasts = pd.read_parquet(forecasts_path)
            other_forecasts = existing_forecasts[existing_forecasts["district_name"].str.lower() != clean_dist]
            combined_forecasts = pd.concat([other_forecasts, current_forecasts], ignore_index=True)
        except Exception:
            combined_forecasts = current_forecasts
    else:
        combined_forecasts = current_forecasts

    combined_forecasts = combined_forecasts.sort_values(by=["district_name", "block_name", "forecast_date"])
    combined_forecasts.to_parquet(forecasts_path, index=False, engine="pyarrow", compression="snappy")
    created_files["forecasts"] = forecasts_path
    logger.info(f"Saved Forecasts Parquet to {forecasts_path} ({len(combined_forecasts):,} records)")

    # 4. Observations Parquet (Cumulative across districts)
    observations_path = os.path.join(output_dir, "observations.parquet")
    obs_cols = [
        "panchayat_id",
        "lgd_code",
        "district_name",
        "date",
        "station_id",
        "station_latitude",
        "station_longitude",
        "station_distance_km",
        "actual_rainfall_mm",
    ]
    current_obs = df[obs_cols].copy()

    if os.path.exists(observations_path):
        try:
            existing_obs = pd.read_parquet(observations_path)
            other_obs = existing_obs[existing_obs["district_name"].str.lower() != clean_dist]
            combined_obs = pd.concat([other_obs, current_obs], ignore_index=True)
        except Exception:
            combined_obs = current_obs
    else:
        combined_obs = current_obs

    combined_obs.to_parquet(observations_path, index=False, engine="pyarrow", compression="snappy")
    created_files["observations"] = observations_path
    logger.info(f"Saved Observations Parquet to {observations_path} ({len(combined_obs):,} records)")

    # 5. Training Dataset Parquet (Cumulative ML features)
    training_path = os.path.join(output_dir, "training_dataset.parquet")
    train_df = df.copy()
    
    # Engineer temporal features for ML readiness (Section 17)
    dt_series = pd.to_datetime(train_df["date"], errors="coerce")
    train_df["month"] = dt_series.dt.month.fillna(0).astype(np.int32)
    train_df["day_of_year"] = dt_series.dt.dayofyear.fillna(0).astype(np.int32)

    train_cols = [
        "panchayat_id",
        "lgd_code",
        "district_name",
        "block_name",
        "panchayat_name",
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
        "station_distance_km",
        "date",
        "forecast_issue_date",
        "lead_days",
        "month",
        "day_of_year",
        "block_forecast_rainfall_mm",
        "actual_rainfall_mm",
    ]
    current_train = train_df[train_cols].copy()

    if os.path.exists(training_path):
        try:
            existing_train = pd.read_parquet(training_path)
            other_train = existing_train[existing_train["district_name"].str.lower() != clean_dist]
            combined_train = pd.concat([other_train, current_train], ignore_index=True)
        except Exception:
            combined_train = current_train
    else:
        combined_train = current_train

    combined_train.to_parquet(training_path, index=False, engine="pyarrow", compression="snappy")
    created_files["training_dataset"] = training_path
    logger.info(f"Saved ML Training Parquet to {training_path} ({len(combined_train):,} rows)")

    return created_files
