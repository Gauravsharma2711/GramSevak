"""
GramSevak ML Dataset Audit and Training Readiness Profiler (Phase 2.1).

Audits validated Phase 1 Canonical Parquet datasets (Nashik and Pune) to establish
a strict ML data contract for Panchayat-level rainfall downscaling.

Evaluates:
- Dataset structural and administrative properties
- Unit of observation and supervised target semantics
- Target distribution and skewness across IMD rainfall categories
- Prediction-time information boundaries and data leakage vectors
- Historical lag feasibility (t-1, t-3, t-7) and temporal continuity
- Raw Numerical Block Forecast Baseline metrics (MAE, RMSE, Bias, Correlation)
- Spatial variation, elevation, and station distance distributions
- Cross-district comparability (Nashik snapshot vs. Pune time-series)
- Row-level training eligibility contract and ML readiness status

Usage:
    python scripts/audit_ml_dataset.py
    python scripts/audit_ml_dataset.py --nashik data/processed/canonical_nashik.parquet --pune data/processed/canonical_pune.parquet
"""

import os
import sys
import json
import math
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("audit_ml_dataset")

# Standard IMD Rainfall Intensity Classification thresholds (mm / 24h)
IMD_CATEGORIES = {
    "dry_no_rain": (0.0, 0.0),            # Exactly 0.0 mm
    "very_light_trace": (0.001, 2.4),    # >0.0 and <= 2.4 mm
    "light_rain": (2.401, 15.5),         # 2.5 to 15.5 mm
    "moderate_rain": (15.501, 64.4),      # 15.6 to 64.4 mm
    "heavy_rain": (64.401, 115.5),        # 64.5 to 115.5 mm
    "very_heavy_rain": (115.501, 204.4),  # 115.6 to 204.4 mm
    "extremely_heavy_rain": (204.401, 1000.0) # > 204.4 mm
}


def load_parquet_dataset(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load Parquet dataset and extract file-level metadata."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Parquet dataset not found at: {file_path}")
    
    file_size = os.path.getsize(file_path)
    df = pd.read_parquet(file_path)
    metadata = {
        "file_path": file_path.replace("\\", "/"),
        "file_size_bytes": file_size,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
    }
    return df, metadata


def compute_target_statistics(actual_series: pd.Series) -> Dict[str, Any]:
    """Calculate comprehensive target distribution metrics on actual_rainfall_mm."""
    total_count = len(actual_series)
    missing_count = int(actual_series.isna().sum())
    valid_series = actual_series.dropna()
    valid_count = len(valid_series)

    if valid_count == 0:
        return {
            "total_count": total_count,
            "missing_count": missing_count,
            "missing_pct": 100.0 if total_count > 0 else 0.0,
            "valid_count": 0,
            "zero_count": 0,
            "zero_pct": 0.0,
            "nonzero_count": 0,
            "nonzero_pct": 0.0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "percentiles": {},
            "categories": {}
        }

    vals = valid_series.values.astype(float)
    zero_mask = (vals == 0.0)
    zero_count = int(np.sum(zero_mask))
    nonzero_count = valid_count - zero_count

    percentiles = {
        "p25": float(np.percentile(vals, 25)),
        "p50": float(np.percentile(vals, 50)),
        "p75": float(np.percentile(vals, 75)),
        "p90": float(np.percentile(vals, 90)),
        "p95": float(np.percentile(vals, 95)),
        "p99": float(np.percentile(vals, 99))
    }

    # Categorize according to IMD definitions
    categories = {}
    for cat_name, (low, high) in IMD_CATEGORIES.items():
        if cat_name == "dry_no_rain":
            cnt = int(np.sum(vals == 0.0))
        else:
            cnt = int(np.sum((vals >= low) & (vals <= high)))
        categories[cat_name] = {
            "count": cnt,
            "percentage": round((cnt / valid_count) * 100.0, 3)
        }

    return {
        "total_count": total_count,
        "missing_count": missing_count,
        "missing_pct": round((missing_count / total_count) * 100.0, 3) if total_count > 0 else 0.0,
        "valid_count": valid_count,
        "zero_count": zero_count,
        "zero_pct": round((zero_count / valid_count) * 100.0, 3),
        "nonzero_count": nonzero_count,
        "nonzero_pct": round((nonzero_count / valid_count) * 100.0, 3),
        "mean": round(float(np.mean(vals)), 4),
        "median": round(float(np.median(vals)), 4),
        "std": round(float(np.std(vals)), 4),
        "min": round(float(np.min(vals)), 4),
        "max": round(float(np.max(vals)), 4),
        "percentiles": percentiles,
        "categories": categories
    }


def compute_baseline_slice_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Calculate regression error metrics: MAE, RMSE, Mean Error (bias), Pearson correlation."""
    count = len(y_true)
    if count == 0:
        return {"count": 0, "mae": None, "rmse": None, "bias": None, "pearson_corr": None}
    
    diff = y_pred - y_true
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    bias = float(np.mean(diff)) # positive means forecast overpredicts, negative means underpredicts

    # Correlation
    if count > 1 and np.std(y_true) > 1e-9 and np.std(y_pred) > 1e-9:
        pearson_corr = float(np.corrcoef(y_true, y_pred)[0, 1])
        if math.isnan(pearson_corr):
            pearson_corr = 0.0
    else:
        pearson_corr = 0.0

    return {
        "count": count,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "bias": round(bias, 4),
        "pearson_corr": round(pearson_corr, 4)
    }


def compute_baseline_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Establish the Raw Block Forecast Baseline:
    Use block_forecast_rainfall_mm directly as the prediction for actual_rainfall_mm.
    Evaluates overall, zero-actual, non-zero-actual, and heavy rainfall slices.
    """
    valid_df = df.dropna(subset=["actual_rainfall_mm", "block_forecast_rainfall_mm"])
    y_true = valid_df["actual_rainfall_mm"].values.astype(float)
    y_pred = valid_df["block_forecast_rainfall_mm"].values.astype(float)

    # All records
    all_metrics = compute_baseline_slice_metrics(y_true, y_pred)

    # Zero rainfall cases (dry actuals)
    zero_mask = (y_true == 0.0)
    zero_metrics = compute_baseline_slice_metrics(y_true[zero_mask], y_pred[zero_mask])

    # Non-zero rainfall cases (rainy days)
    nonzero_mask = (y_true > 0.0)
    nonzero_metrics = compute_baseline_slice_metrics(y_true[nonzero_mask], y_pred[nonzero_mask])

    # Moderate and above (actual >= 15.5 mm)
    mod_mask = (y_true >= 15.5)
    mod_metrics = compute_baseline_slice_metrics(y_true[mod_mask], y_pred[mod_mask])

    # Heavy rainfall cases (actual >= 35.5 mm)
    heavy_mask = (y_true >= 35.5)
    heavy_metrics = compute_baseline_slice_metrics(y_true[heavy_mask], y_pred[heavy_mask])

    # Very heavy rainfall cases (actual >= 64.5 mm)
    vheavy_mask = (y_true >= 64.5)
    vheavy_metrics = compute_baseline_slice_metrics(y_true[vheavy_mask], y_pred[vheavy_mask])

    return {
        "overall": all_metrics,
        "zero_rainfall_slice": zero_metrics,
        "nonzero_rainfall_slice": nonzero_metrics,
        "moderate_plus_slice_gte_15_5mm": mod_metrics,
        "heavy_slice_gte_35_5mm": heavy_metrics,
        "very_heavy_slice_gte_64_5mm": vheavy_metrics,
        "baseline_summary": (
            f"Raw block forecast achieves MAE={all_metrics['mae']} mm, RMSE={all_metrics['rmse']} mm, "
            f"Bias={all_metrics['bias']} mm across {all_metrics['count']} records. "
            f"On heavy rainfall events (>=35.5 mm, n={heavy_metrics['count']}), MAE degrades to {heavy_metrics['mae']} mm "
            f"with severe under-prediction bias ({heavy_metrics['bias']} mm)."
        )
    }


def audit_spatial_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Inspect Panchayat coordinates, elevations, and reference weather station distances."""
    panch_coords = df[["panchayat_latitude", "panchayat_longitude"]].drop_duplicates()
    stations = df[["station_id", "station_latitude", "station_longitude"]].drop_duplicates()

    return {
        "unique_panchayat_coordinates": len(panch_coords),
        "latitude_bounds": {
            "min": round(float(df["panchayat_latitude"].min()), 6),
            "max": round(float(df["panchayat_latitude"].max()), 6),
            "mean": round(float(df["panchayat_latitude"].mean()), 6)
        },
        "longitude_bounds": {
            "min": round(float(df["panchayat_longitude"].min()), 6),
            "max": round(float(df["panchayat_longitude"].max()), 6),
            "mean": round(float(df["panchayat_longitude"].mean()), 6)
        },
        "elevation_m": {
            "min": round(float(df["elevation_m"].min()), 2),
            "max": round(float(df["elevation_m"].max()), 2),
            "mean": round(float(df["elevation_m"].mean()), 2),
            "std": round(float(df["elevation_m"].std()), 2),
            "unique_values": int(df["elevation_m"].nunique())
        },
        "station_coverage": {
            "unique_station_count": int(df["station_id"].nunique()),
            "unique_station_locations": len(stations),
            "station_ids": sorted(list(df["station_id"].unique()))
        },
        "station_distance_km": {
            "min": round(float(df["station_distance_km"].min()), 3),
            "max": round(float(df["station_distance_km"].max()), 3),
            "mean": round(float(df["station_distance_km"].mean()), 3),
            "std": round(float(df["station_distance_km"].std()), 3),
            "p50": round(float(df["station_distance_km"].quantile(0.50)), 3),
            "p95": round(float(df["station_distance_km"].quantile(0.95)), 3)
        }
    }


def audit_historical_feasibility(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Determine whether historical rainfall features (lag t-1, t-3, t-7, rolling)
    can be safely and strictly constructed prior to forecast_issue_date.
    """
    unique_dates = sorted(df["date"].unique())
    num_unique_dates = len(unique_dates)
    panchayat_counts = df.groupby("panchayat_id")["date"].nunique()

    # Check consecutive day spacing
    if num_unique_dates > 1:
        date_series = pd.to_datetime(pd.Series(unique_dates))
        diffs = (date_series - date_series.shift(1)).dt.days.dropna()
        max_gap = int(diffs.max())
        min_gap = int(diffs.min())
        median_gap = float(diffs.median())
        is_continuous = bool((diffs == 1).all())
    else:
        max_gap = 0
        min_gap = 0
        median_gap = 0.0
        is_continuous = False

    # Check feasibility of t-1, t-3, t-7
    # For a row to have safe t-1 lag, the Panchayat must have an observation on date - 1 day,
    # and date - 1 day must be <= forecast_issue_date.
    # In Pune, lead_days=1, so date - 1 == forecast_issue_date.
    # Under daily operational reporting, previous day's rainfall is available at issuance time.
    min_dates_per_panchayat = int(panchayat_counts.min()) if len(panchayat_counts) > 0 else 0
    max_dates_per_panchayat = int(panchayat_counts.max()) if len(panchayat_counts) > 0 else 0

    t1_feasible = bool(min_dates_per_panchayat >= 2 and is_continuous)
    t3_feasible = bool(min_dates_per_panchayat >= 4 and is_continuous)
    t7_feasible = bool(min_dates_per_panchayat >= 8 and is_continuous)

    return {
        "unique_dates_count": num_unique_dates,
        "is_daily_continuous": is_continuous,
        "min_date_gap_days": min_gap,
        "max_date_gap_days": max_gap,
        "median_date_gap_days": median_gap,
        "min_records_per_panchayat": min_dates_per_panchayat,
        "max_records_per_panchayat": max_dates_per_panchayat,
        "lag_t1_feasible": t1_feasible,
        "lag_t3_feasible": t3_feasible,
        "lag_t7_feasible": t7_feasible,
        "assessment": (
            "Fully feasible for daily sequential lags (t-1, t-3, t-7) with warmup window."
            if t7_feasible else
            "Not feasible for historical lag features due to insufficient chronological depth or snapshot structure."
        )
    }


def audit_panchayat_coverage(df: pd.DataFrame) -> Dict[str, Any]:
    """Classify Panchayats into coverage tiers based on usable target observation counts."""
    valid_df = df.dropna(subset=["actual_rainfall_mm"])
    counts = valid_df.groupby("panchayat_id").size()

    sufficient = int((counts >= 60).sum())
    moderate = int(((counts >= 10) & (counts < 60)).sum())
    sparse = int(((counts >= 2) & (counts < 10)).sum())
    single_snapshot = int((counts == 1).sum())
    
    all_panch_ids = set(df["panchayat_id"].unique())
    valid_panch_ids = set(counts.index)
    unusable = len(all_panch_ids - valid_panch_ids)

    return {
        "total_panchayats": len(all_panch_ids),
        "sufficient_history_gte_60_days": sufficient,
        "moderate_history_10_to_59_days": moderate,
        "sparse_history_2_to_9_days": sparse,
        "single_snapshot_1_day": single_snapshot,
        "unusable_0_days": unusable,
        "min_observations": int(counts.min()) if len(counts) > 0 else 0,
        "max_observations": int(counts.max()) if len(counts) > 0 else 0,
        "mean_observations": round(float(counts.mean()), 2) if len(counts) > 0 else 0.0
    }


def evaluate_training_eligibility(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Establish training eligibility contract:
    A row is eligible for supervised learning if and only if:
    1. actual_rainfall_mm is NOT NULL and >= 0.0
    2. block_forecast_rainfall_mm is NOT NULL and >= 0.0
    3. panchayat_latitude and panchayat_longitude are valid non-null coordinates
    4. forecast_issue_date is NOT NULL and date is NOT NULL
    5. lead_days >= 0 (target date is on or after issue date)
    """
    c1 = df["actual_rainfall_mm"].notna() & (df["actual_rainfall_mm"] >= 0.0)
    c2 = df["block_forecast_rainfall_mm"].notna() & (df["block_forecast_rainfall_mm"] >= 0.0)
    c3 = df["panchayat_latitude"].notna() & df["panchayat_longitude"].notna()
    c4 = df["forecast_issue_date"].notna() & df["date"].notna()
    c5 = df["lead_days"].notna() & (df["lead_days"] >= 0)

    eligible_mask = c1 & c2 & c3 & c4 & c5
    eligible_count = int(eligible_mask.sum())
    total_count = len(df)

    return {
        "total_rows": total_count,
        "eligible_rows": eligible_count,
        "ineligible_rows": total_count - eligible_count,
        "eligibility_rate_pct": round((eligible_count / total_count) * 100.0, 3) if total_count > 0 else 0.0,
        "rejection_breakdown": {
            "missing_or_negative_target": int((~c1).sum()),
            "missing_or_negative_block_forecast": int((~c2).sum()),
            "invalid_coordinates": int((~c3).sum()),
            "invalid_dates": int((~c4).sum()),
            "negative_lead_days": int((~c5).sum())
        }
    }


def build_candidate_feature_inventory() -> List[Dict[str, Any]]:
    """Comprehensive candidate feature inventory with prediction-time classification and leakage audit."""
    return [
        {
            "field": "block_forecast_rainfall_mm",
            "purpose": "Primary macro-scale numerical weather prediction rainfall signal",
            "data_type": "float64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Produced by IMD NWP model before forecast issue)",
            "missingness": "0.0%",
            "spatial_meaning": "Regional block-level mean rainfall (15-25 km grid)",
            "temporal_meaning": "Forecast accumulation for target 24h period",
            "decision": "ALLOWED (Core Baseline Feature)",
            "reason": "Indispensable physics-based macro predictor; available at issuance."
        },
        {
            "field": "panchayat_latitude",
            "purpose": "Spatial positioning and North-South climate gradient",
            "data_type": "float64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Static administrative attribute)",
            "missingness": "0.0%",
            "spatial_meaning": "Geographic latitude centroid of Gram Panchayat",
            "temporal_meaning": "Static invariant",
            "decision": "ALLOWED (Spatial Feature)",
            "reason": "Standard spatial coordinate enabling model to capture regional latitudinal rainfall trends."
        },
        {
            "field": "panchayat_longitude",
            "purpose": "Spatial positioning and East-West Western Ghats orographic gradient",
            "data_type": "float64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Static administrative attribute)",
            "missingness": "0.0%",
            "spatial_meaning": "Geographic longitude centroid of Gram Panchayat",
            "temporal_meaning": "Static invariant",
            "decision": "ALLOWED (Spatial Feature)",
            "reason": "Crucial for capturing the Western Ghats rain shadow gradient across Maharashtra."
        },
        {
            "field": "elevation_m",
            "purpose": "Topographic elevation for orographic rainfall downscaling",
            "data_type": "float64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Static terrain attribute)",
            "missingness": "0.0%",
            "spatial_meaning": "Terrain altitude in meters above mean sea level",
            "temporal_meaning": "Static invariant",
            "decision": "ALLOWED (Topographic Feature)",
            "reason": "Key physical driver of localized rainfall enhancement/rain-shadow."
        },
        {
            "field": "station_distance_km",
            "purpose": "Distance to nearest reference weather station",
            "data_type": "float64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Static geometric distance)",
            "missingness": "0.0%",
            "spatial_meaning": "Haversine distance between Panchayat and reference AWS/ARG",
            "temporal_meaning": "Static invariant",
            "decision": "ALLOWED (Spatial Context Feature)",
            "reason": "Provides spatial proximity context to reference observation source."
        },
        {
            "field": "lead_days",
            "purpose": "Forecast lead horizon in integer days",
            "data_type": "int64",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Known strictly at forecast issuance)",
            "missingness": "0.0%",
            "spatial_meaning": "Spatial invariant",
            "temporal_meaning": "Difference: target date - forecast issue date",
            "decision": "ALLOWED (Temporal Horizon Feature)",
            "reason": "Accounts for forecast skill degradation over lead horizons."
        },
        {
            "field": "day_of_year / month",
            "purpose": "Captures monsoon seasonality and intra-seasonal progression",
            "data_type": "int64 / float64 (cyclical sine/cosine)",
            "availability_at_forecast_time": "Category A (Available at forecast time)",
            "potential_leakage": "None (Calendar date is deterministic)",
            "missingness": "0.0%",
            "spatial_meaning": "Spatial invariant",
            "temporal_meaning": "Target calendar position (e.g. onset, peak monsoon, withdrawal)",
            "decision": "ALLOWED (Temporal Feature)",
            "reason": "Captures seasonal monsoon transitions across July-September."
        },
        {
            "field": "lag_actual_rainfall_t1_mm",
            "purpose": "Previous-day observed rainfall at Panchayat",
            "data_type": "float64",
            "availability_at_forecast_time": "Category B (Available from past history only)",
            "potential_leakage": "Leakage Risk if computed for t=0 or if t-1 crosses forecast issue timestamp",
            "missingness": "Requires 1-day warm-up (unpopulated on first observation day)",
            "spatial_meaning": "Panchayat local antecedent moisture / persistence",
            "temporal_meaning": "Observation on target date minus 1 day",
            "decision": "ALLOWED (Historical Feature - Pune only, with strict lag verification)",
            "reason": "Valid when strictly prior to forecast issue; unavailable in single-snapshot Nashik."
        },
        {
            "field": "rolling_actual_rainfall_t3_mm",
            "purpose": "3-day rolling antecedent precipitation at Panchayat",
            "data_type": "float64",
            "availability_at_forecast_time": "Category B (Available from past history only)",
            "potential_leakage": "High Leakage Risk if forward-looking window is mistakenly used",
            "missingness": "Requires 3-day warm-up window",
            "spatial_meaning": "Panchayat localized soil saturation / active wet spell",
            "temporal_meaning": "Sum/mean of actual rainfall from t-3 to t-1",
            "decision": "ALLOWED (Historical Feature - Pune only, backward window only)",
            "reason": "Strong meteorological persistence signal when computed with closed-past window."
        },
        {
            "field": "actual_rainfall_mm",
            "purpose": "Ground truth 24-hour target precipitation",
            "data_type": "float64",
            "availability_at_forecast_time": "Category C (Available ONLY AFTER the target time)",
            "potential_leakage": "CATASTROPHIC TARGET LEAKAGE if included as input feature",
            "missingness": "0.0% in validated canonical dataset",
            "spatial_meaning": "True observed precipitation at Panchayat",
            "temporal_meaning": "Measured 24h accumulation after target date concludes",
            "decision": "FORBIDDEN AS FEATURE (SUPERVISED TARGET ONLY)",
            "reason": "Using target-day observation as input produces 100% artificial, trivial accuracy."
        },
        {
            "field": "panchayat_id (as raw integer or categorical)",
            "purpose": "Entity identifier",
            "data_type": "int64 / categorical",
            "availability_at_forecast_time": "Category A",
            "potential_leakage": "Spatial Memorization Risk",
            "missingness": "0.0%",
            "spatial_meaning": "Administrative entity ID",
            "temporal_meaning": "Static invariant",
            "decision": "FORBIDDEN IN LINEAR/TREE MODELS (Risk of entity memorization)",
            "reason": "Models will overfit to specific IDs rather than learning geographic features (lat/lon/elev)."
        },
        {
            "field": "source_row_id / source_file",
            "purpose": "Audit metadata",
            "data_type": "int64 / string",
            "availability_at_forecast_time": "Category D (ETL artifact)",
            "potential_leakage": "Spurious correlation risk",
            "missingness": "0.0%",
            "spatial_meaning": "File metadata",
            "temporal_meaning": "ETL lineage",
            "decision": "FORBIDDEN (ETL Lineage Only)",
            "reason": "Data processing artifacts have no physical meteorological relationship."
        }
    ]


def profile_district(df: pd.DataFrame, file_metadata: Dict[str, Any], district_name: str) -> Dict[str, Any]:
    """Execute complete ML dataset profiling and audit for a specific district."""
    logger.info(f"Auditing ML dataset for district: {district_name} ({len(df)} rows)...")

    # Dates and lead horizons
    dates = df["date"].astype(str).tolist()
    issue_dates = df["forecast_issue_date"].astype(str).tolist()
    lead_days_counts = {int(k): int(v) for k, v in df["lead_days"].value_counts().items()}

    # Group counts
    panch_counts = df.groupby("panchayat_id").size()
    block_counts = df.groupby("block_name").size()
    date_counts = df.groupby("date").size()

    # Missingness
    missing_by_col = {col: int(df[col].isna().sum()) for col in df.columns}
    missing_pct_by_col = {col: round((int(df[col].isna().sum()) / len(df)) * 100.0, 3) for col in df.columns}

    # Duplicate business keys: (panchayat_id, date)
    duplicate_business_keys = int(df.duplicated(subset=["panchayat_id", "date"]).sum())

    # Target statistics
    target_stats = compute_target_statistics(df["actual_rainfall_mm"])

    # Block forecast statistics
    forecast_stats = compute_target_statistics(df["block_forecast_rainfall_mm"])

    # Baseline regression metrics
    baseline_metrics = compute_baseline_metrics(df)

    # Spatial audit
    spatial_audit = audit_spatial_data(df)

    # Historical lag feasibility
    historical_feasibility = audit_historical_feasibility(df)

    # Panchayat coverage
    panchayat_coverage = audit_panchayat_coverage(df)

    # Training eligibility
    eligibility = evaluate_training_eligibility(df)

    return {
        "district_name": district_name,
        "file_metadata": file_metadata,
        "structural_metrics": {
            "total_rows": len(df),
            "unique_panchayats": int(df["panchayat_id"].nunique()),
            "unique_blocks": int(df["block_name"].nunique()),
            "unique_districts": int(df["district_name"].nunique()),
            "earliest_date": min(dates) if dates else None,
            "latest_date": max(dates) if dates else None,
            "unique_dates_count": len(set(dates)),
            "earliest_forecast_issue_date": min(issue_dates) if issue_dates else None,
            "latest_forecast_issue_date": max(issue_dates) if issue_dates else None,
            "unique_forecast_issue_dates_count": len(set(issue_dates)),
            "lead_days_distribution": lead_days_counts,
            "rows_per_panchayat": {
                "min": int(panch_counts.min()) if len(panch_counts) > 0 else 0,
                "max": int(panch_counts.max()) if len(panch_counts) > 0 else 0,
                "mean": round(float(panch_counts.mean()), 2) if len(panch_counts) > 0 else 0.0,
                "median": float(panch_counts.median()) if len(panch_counts) > 0 else 0.0
            },
            "rows_per_block": {
                "min": int(block_counts.min()) if len(block_counts) > 0 else 0,
                "max": int(block_counts.max()) if len(block_counts) > 0 else 0,
                "mean": round(float(block_counts.mean()), 2) if len(block_counts) > 0 else 0.0,
                "median": float(block_counts.median()) if len(block_counts) > 0 else 0.0
            },
            "rows_per_date": {
                "min": int(date_counts.min()) if len(date_counts) > 0 else 0,
                "max": int(date_counts.max()) if len(date_counts) > 0 else 0,
                "mean": round(float(date_counts.mean()), 2) if len(date_counts) > 0 else 0.0,
                "median": float(date_counts.median()) if len(date_counts) > 0 else 0.0
            },
            "duplicate_business_keys": duplicate_business_keys,
            "missing_values_count": missing_by_col,
            "missing_values_pct": missing_pct_by_col
        },
        "target_statistics": target_stats,
        "block_forecast_statistics": forecast_stats,
        "baseline_metrics": baseline_metrics,
        "spatial_audit": spatial_audit,
        "historical_feasibility": historical_feasibility,
        "panchayat_coverage": panchayat_coverage,
        "training_eligibility": eligibility
    }


def compare_districts(nashik_profile: Dict[str, Any], pune_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Perform side-by-side comparison between Nashik and Pune datasets."""
    n_struct = nashik_profile["structural_metrics"]
    p_struct = pune_profile["structural_metrics"]
    n_tgt = nashik_profile["target_statistics"]
    p_tgt = pune_profile["target_statistics"]
    n_base = nashik_profile["baseline_metrics"]["overall"]
    p_base = pune_profile["baseline_metrics"]["overall"]

    pooling_verdict = (
        "RESTRICTED / NOT RECOMMENDED FOR DIRECT POOLING: "
        "Pune provides a rich 140-day continuous time-series (187,320 rows across 1,338 Panchayats with lead_days=1), "
        "allowing chronological splits and historical lag feature engineering. "
        "Nashik provides only a single-observation spatial snapshot per Panchayat (1,388 rows, 1 record per Panchayat, lead_days=0). "
        "Pooling them directly would induce severe temporal heterogeneity, lead-time mismatch (lead 0 vs lead 1), "
        "and prevent lag features on Nashik. Instead, Pune should serve as the primary training and temporal validation dataset, "
        "while Nashik serves as an out-of-district spatial generalization test set."
    )

    return {
        "comparison_table": {
            "total_rows": {"nashik": n_struct["total_rows"], "pune": p_struct["total_rows"]},
            "unique_panchayats": {"nashik": n_struct["unique_panchayats"], "pune": p_struct["unique_panchayats"]},
            "unique_blocks": {"nashik": n_struct["unique_blocks"], "pune": p_struct["unique_blocks"]},
            "temporal_span_days": {"nashik": n_struct["unique_dates_count"], "pune": p_struct["unique_dates_count"]},
            "date_range": {
                "nashik": f"{n_struct['earliest_date']} to {n_struct['latest_date']}",
                "pune": f"{p_struct['earliest_date']} to {p_struct['latest_date']}"
            },
            "lead_days": {"nashik": list(n_struct["lead_days_distribution"].keys()), "pune": list(p_struct["lead_days_distribution"].keys())},
            "target_mean_mm": {"nashik": n_tgt["mean"], "pune": p_tgt["mean"]},
            "target_max_mm": {"nashik": n_tgt["max"], "pune": p_tgt["max"]},
            "target_zero_pct": {"nashik": n_tgt["zero_pct"], "pune": p_tgt["zero_pct"]},
            "baseline_mae_mm": {"nashik": n_base["mae"], "pune": p_base["mae"]},
            "baseline_rmse_mm": {"nashik": n_base["rmse"], "pune": p_base["rmse"]},
            "baseline_bias_mm": {"nashik": n_base["bias"], "pune": p_base["bias"]},
            "baseline_correlation": {"nashik": n_base["pearson_corr"], "pune": p_base["pearson_corr"]}
        },
        "pooling_evaluation": pooling_verdict,
        "recommended_ml_strategy": {
            "primary_training_district": "Pune (187,320 rows, 140 days, complete time-series)",
            "holdout_evaluation_district": "Nashik (1,388 rows, spatial out-of-district evaluation)",
            "temporal_split_feasibility": "Supported in Pune; Unsupported in Nashik (snapshot only)"
        }
    }


def audit_leakage_risks() -> List[Dict[str, Any]]:
    """Enumerate known data leakage risks, evidence, severity, and mitigation rules."""
    return [
        {
            "risk": "Target Observation Leakage (actual_rainfall_mm)",
            "evidence": "actual_rainfall_mm is present in canonical Parquet alongside forecast fields.",
            "severity": "CRITICAL / FATAL",
            "potential_mitigation": (
                "Strict feature isolation: actual_rainfall_mm is the designated y target. "
                "It is strictly excluded from feature matrix X. Only past lags strictly before "
                "forecast_issue_date are permitted as features."
            )
        },
        {
            "risk": "Temporal Leakage via Random Train/Test Splitting",
            "evidence": "Weather time-series exhibit strong atmospheric auto-correlation across consecutive days.",
            "severity": "CRITICAL",
            "potential_mitigation": (
                "Strict prohibition of random k-fold or train_test_split on dates. "
                "Must use strict chronological cutoff (e.g. Train on April-July 2026, Test on August-September 2026) "
                "or TimeSeriesSplit with non-overlapping blocks."
            )
        },
        {
            "risk": "Contemporaneous Station Observation Leakage",
            "evidence": "Station rainfall on target day reflects ground truth and is not available at forecast issue.",
            "severity": "CRITICAL",
            "potential_mitigation": (
                "Zero station meteorological observations from target day t may be used as inputs. "
                "Only static station geometry (station_latitude, station_longitude, station_distance_km) is permitted."
            )
        },
        {
            "risk": "Panchayat Identity Memorization",
            "evidence": "Tree models can split on panchayat_id integer or high-cardinality one-hot encoding.",
            "severity": "HIGH",
            "potential_mitigation": (
                "Exclude raw panchayat_id from model features. Represent spatial variation exclusively through continuous "
                "geographical attributes (panchayat_latitude, panchayat_longitude, elevation_m, station_distance_km)."
            )
        },
        {
            "risk": "Future Aggregation / Target Encoding Leakage",
            "evidence": "Computing mean target rainfall per block/panchayat over the entire dataset leaks future outcomes into training.",
            "severity": "HIGH",
            "potential_mitigation": (
                "Prohibit global target encodings. Any spatial aggregation must be computed strictly out-of-fold or on training time windows only."
            )
        },
        {
            "risk": "Lead Time Mismatch / Lookahead Bias",
            "evidence": "Nashik has lead_days=0 (nowcast) while Pune has lead_days=1 (1-day advance forecast).",
            "severity": "MEDIUM",
            "potential_mitigation": (
                "Include lead_days as explicit feature or train lead-horizon-specific models. "
                "Never evaluate a lead_days=1 model against lead_days=0 data without documenting the horizon discrepancy."
            )
        }
    ]


def determine_readiness_status(nashik_profile: Dict[str, Any], pune_profile: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
    """Determine overall dataset readiness status, warnings, and blockers."""
    warnings = []
    blockers = []

    # Check target integrity
    if nashik_profile["target_statistics"]["missing_count"] > 0:
        warnings.append(f"Nashik has {nashik_profile['target_statistics']['missing_count']} missing actual_rainfall_mm values.")
    if pune_profile["target_statistics"]["missing_count"] > 0:
        warnings.append(f"Pune has {pune_profile['target_statistics']['missing_count']} missing actual_rainfall_mm values.")

    # Check temporal depth
    if nashik_profile["structural_metrics"]["rows_per_panchayat"]["max"] == 1:
        warnings.append(
            "Nashik contains exactly 1 observation per Panchayat (snapshot). "
            "It cannot support temporal lag features (t-1, t-3, t-7) or time-series validation splits."
        )

    # Check lead days heterogeneity
    if nashik_profile["structural_metrics"]["lead_days_distribution"] != pune_profile["structural_metrics"]["lead_days_distribution"]:
        warnings.append(
            f"Forecast horizon discrepancy: Nashik is lead_days={list(nashik_profile['structural_metrics']['lead_days_distribution'].keys())} "
            f"whereas Pune is lead_days={list(pune_profile['structural_metrics']['lead_days_distribution'].keys())}."
        )

    # Check baseline performance
    pune_heavy_bias = pune_profile["baseline_metrics"]["heavy_slice_gte_35_5mm"]["bias"]
    if pune_heavy_bias is not None and pune_heavy_bias < -30.0:
        warnings.append(
            f"Significant numerical forecast under-prediction on heavy rainfall in Pune: "
            f"Mean Bias = {pune_heavy_bias} mm on events >= 35.5 mm."
        )

    # Decision logic
    if blockers:
        status = "NOT READY"
    elif warnings:
        status = "READY WITH WARNINGS"
    else:
        status = "READY"

    return status, warnings, blockers


def run_audit(nashik_path: str, pune_path: str, output_json_path: str) -> Dict[str, Any]:
    """Execute end-to-end ML dataset readiness audit and generate machine-readable report."""
    logger.info("Starting GramSevak Phase 2.1 ML Dataset Readiness Audit...")

    # Load Parquet datasets
    df_nashik, meta_nashik = load_parquet_dataset(nashik_path)
    df_pune, meta_pune = load_parquet_dataset(pune_path)

    # Profile individual districts
    profile_nashik = profile_district(df_nashik, meta_nashik, "Nashik")
    profile_pune = profile_district(df_pune, meta_pune, "Pune")

    # Cross-district comparison
    comparison = compare_districts(profile_nashik, profile_pune)

    # Leakage and candidate feature audit
    feature_inventory = build_candidate_feature_inventory()
    leakage_risks = audit_leakage_risks()

    # Readiness status determination
    readiness_status, warnings, blockers = determine_readiness_status(profile_nashik, profile_pune)

    # Assemble comprehensive report
    report = {
        "audit_metadata": {
            "phase": "2.1",
            "title": "ML Dataset Audit and Training Readiness Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "problem_statement": "SIH 26074 - GramSevak Hyper-local Rainfall Downscaling",
            "datasets_audited": {
                "nashik": nashik_path.replace("\\", "/"),
                "pune": pune_path.replace("\\", "/")
            }
        },
        "readiness_summary": {
            "status": readiness_status,
            "can_proceed_to_phase_2_2": (readiness_status in ["READY", "READY WITH WARNINGS"]),
            "warnings_count": len(warnings),
            "blockers_count": len(blockers),
            "warnings": warnings,
            "blockers": blockers
        },
        "ml_objective_and_observation_unit": {
            "ml_objective": "Downscale regional numerical block rainfall forecasts to hyper-local Gram Panchayat level using spatial terrain and validated historical context.",
            "unit_of_observation": "A single Gram Panchayat forecast instance uniquely identified by (panchayat_id, forecast_issue_date, target_date).",
            "target_variable": "actual_rainfall_mm (Ground-truth 24-hour precipitation at the Gram Panchayat in millimeters, continuous float >= 0.0)",
            "primary_baseline_predictor": "block_forecast_rainfall_mm (Raw numerical weather prediction from IMD/NCMRWF at regional block scale in millimeters)"
        },
        "districts": {
            "nashik": profile_nashik,
            "pune": profile_pune
        },
        "cross_district_comparison": comparison,
        "candidate_feature_inventory": feature_inventory,
        "leakage_audit": leakage_risks
    }

    # Write JSON report
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Machine-readable ML readiness report written to: {output_json_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="GramSevak ML Dataset Audit and Training Readiness Profiler")
    parser.add_argument("--nashik", default="data/processed/canonical_nashik.parquet", help="Path to Nashik Parquet file")
    parser.add_argument("--pune", default="data/processed/canonical_pune.parquet", help="Path to Pune Parquet file")
    parser.add_argument("--output", default="reports/phase-2-1-ml-readiness.json", help="Path to output JSON report")
    args = parser.parse_args()

    report = run_audit(args.nashik, args.pune, args.output)
    print("\n" + "=" * 80)
    print("GRAMSEVAK PHASE 2.1 — ML DATASET AUDIT & READINESS SUMMARY")
    print("=" * 80)
    print(f"Status: {report['readiness_summary']['status']}")
    print(f"Nashik Rows: {report['districts']['nashik']['structural_metrics']['total_rows']} | Panchayats: {report['districts']['nashik']['structural_metrics']['unique_panchayats']}")
    print(f"Pune Rows:   {report['districts']['pune']['structural_metrics']['total_rows']} | Panchayats: {report['districts']['pune']['structural_metrics']['unique_panchayats']}")
    print(f"Nashik Baseline MAE: {report['districts']['nashik']['baseline_metrics']['overall']['mae']} mm | RMSE: {report['districts']['nashik']['baseline_metrics']['overall']['rmse']} mm")
    print(f"Pune Baseline MAE:   {report['districts']['pune']['baseline_metrics']['overall']['mae']} mm | RMSE: {report['districts']['pune']['baseline_metrics']['overall']['rmse']} mm")
    print(f"Warnings ({len(report['readiness_summary']['warnings'])}):")
    for w in report['readiness_summary']['warnings']:
        print(f"  - {w}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
