"""
GramSevak Canonical Weather Data Normalization Pipeline (Phase 1.4).

Converts raw, heterogeneous district meteorological datasets (e.g. Nashik, Pune,
and future jurisdictions) into the canonical 22-field weather data schema defined
in Phase 1.3.

Architecture:
    Raw Source Dataset
           │
           ▼
    Encoding Normalization & Provenance Capture
           │
           ▼
    Source-to-Canonical Field Mapping & Trailing Artifact Dropping
           │
           ▼
    Administrative & Text Standardization (Title Case)
           │
           ▼
    Identifier Extraction (Stable Integer IDs & LGD Codes)
           │
           ▼
    Temporal Normalization (ISO 8601 YYYY-MM-DD & Lead Days)
           │
           ▼
    Physical Bounds, Sentinel Sanitization & Geographic Validation
           │
           ▼
    Haversine Station Distance Verification & Duplicate/Conflict Audit
           │
           ▼
    Severity Contract Enforcement (ERROR -> Reject; WARNING -> Retain & Alert)
           │
           ▼
    Canonical Intermediate Output & Structured Quality Report
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data_pipeline.district_config import DistrictConfig, get_district_config, DISTRICT_REGISTRY

try:
    from src.utils.geospatial import haversine_distance
except ImportError:
    def haversine_distance(lat1, lon1, lat2, lon2, radius_km=6371.0):
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        delta_phi = np.radians(lat2 - lat1)
        delta_lambda = np.radians(lon2 - lon1)
        a = (
            np.sin(delta_phi / 2.0) ** 2
            + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * np.arcsin(np.clip(np.sqrt(a), 0.0, 1.0))
        return radius_km * c

logger = logging.getLogger("canonical_normalizer")

# Exact 22-field canonical weather schema defined in Phase 1.3
CANONICAL_COLUMNS: List[str] = [
    "panchayat_id",
    "lgd_code",
    "panchayat_name",
    "block_name",
    "district_name",
    "state_name",
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
    "source_dataset",
    "source_file",
    "source_row_id",
    "source_panchayat_id",
]

# Maharashtra Regional Bounding Box for Geographic Warning Emittance
MH_LAT_MIN, MH_LAT_MAX = 15.0, 22.5
MH_LON_MIN, MH_LON_MAX = 72.0, 81.5


def haversine_vectorized(lat1: pd.Series, lon1: pd.Series, lat2: pd.Series, lon2: pd.Series) -> pd.Series:
    """Calculate the great circle distance between two points on the earth in km."""
    R = 6371.0  # Earth radius in kilometers
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return pd.Series(R * c, index=lat1.index)


def normalize_and_validate_dataset(
    df_raw: pd.DataFrame,
    config: DistrictConfig,
    raw_file_path: str = ""
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Normalizes a raw DataFrame into the canonical 22-field schema using DistrictConfig.
    Enforces the Phase 1.3 validation contract and returns the valid DataFrame and
    structured quality metrics.

    Parameters:
        df_raw: Unmodified raw input DataFrame
        config: DistrictConfig instance defining source mappings and rules
        raw_file_path: Originating relative/absolute path of raw dataset

    Returns:
        valid_df: Standardized DataFrame conforming strictly to CANONICAL_COLUMNS
        quality_report: Comprehensive quality audit dictionary
    """
    total_raw_rows = len(df_raw)
    raw_columns = list(df_raw.columns)
    source_path_val = raw_file_path or config.raw_path

    # Tracking lists for quality report
    errors_list: List[str] = []
    warnings_list: List[str] = []
    info_list: List[str] = []

    # ---------------------------------------------------------
    # 1. Provenance / Audit Lineage Capture
    # ---------------------------------------------------------
    # Capture original raw values before any dropping, renaming, or casting
    if "panchayat_id" in df_raw.columns:
        source_panchayat_id_series = df_raw["panchayat_id"].astype(str)
    else:
        source_panchayat_id_series = pd.Series(["UNKNOWN"] * total_raw_rows, index=df_raw.index)

    source_row_id_series = pd.Series(np.arange(total_raw_rows, dtype=np.int64), index=df_raw.index)
    source_dataset_val = config.district_key or config.name.strip().lower()
    state_name_val = config.state or "Maharashtra"

    # ---------------------------------------------------------
    # 2. Source-to-Canonical Column Mapping & Artifact Dropping
    # ---------------------------------------------------------
    drop_candidates = [c for c in df_raw.columns if c.startswith("Unnamed") or c in config.drop_columns]
    if drop_candidates:
        info_list.append(f"Dropped trailing/unnamed source artifacts: {drop_candidates}")

    # Track mapped vs unmapped source columns
    mapped_source_cols = [c for c in raw_columns if c in config.column_mapping or c in CANONICAL_COLUMNS]
    unmapped_source_cols = [c for c in raw_columns if c not in config.column_mapping and c not in CANONICAL_COLUMNS]
    if unmapped_source_cols:
        warnings_list.append(f"Unmapped source columns detected: {unmapped_source_cols}")

    df = df_raw.drop(columns=drop_candidates, errors="ignore").copy()
    df = df.rename(columns=config.column_mapping)

    # ---------------------------------------------------------
    # 3. Administrative Text Normalization (Title Case)
    # ---------------------------------------------------------
    if "district_name" in df.columns and df["district_name"].notnull().any():
        df["district_name"] = df["district_name"].astype(str).str.strip().str.title()
    else:
        df["district_name"] = config.name.strip().title()

    if "block_name" in df.columns:
        df["block_name"] = (
            df["block_name"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
            .str.title()
        )
    else:
        df["block_name"] = "Unknown"

    if "panchayat_name" in df.columns:
        df["panchayat_name"] = (
            df["panchayat_name"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
            .str.title()
        )
    else:
        df["panchayat_name"] = "Unknown"

    if "station_id" in df.columns:
        df["station_id"] = (
            df["station_id"].astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip()
        )
    else:
        df["station_id"] = "Unknown Station"

    # ---------------------------------------------------------
    # 4. Identifier Extraction & Validation
    # ---------------------------------------------------------
    # lgd_code normalization
    if "lgd_code" in df.columns:
        df["lgd_code"] = pd.to_numeric(df["lgd_code"], errors="coerce").fillna(0).astype(np.int64)
    else:
        df["lgd_code"] = pd.Series(0, index=df.index, dtype=np.int64)

    # Extract integer panchayat_id
    raw_pid_series = df["panchayat_id"] if "panchayat_id" in df.columns else df["lgd_code"]
    extracted_pids = [
        config.panchayat_id_extractor(pid, lgd)
        for pid, lgd in zip(raw_pid_series, df["lgd_code"])
    ]
    df["panchayat_id"] = pd.Series(extracted_pids, index=df.index).astype(np.int64)

    # In datasets where lgd_code was not present separately (e.g. Pune), the extracted panchayat_id is the LGD code
    df["lgd_code"] = np.where(df["lgd_code"] > 0, df["lgd_code"], df["panchayat_id"]).astype(np.int64)

    # ---------------------------------------------------------
    # 5. Temporal Normalization & Lead Days Calculation
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 6. Numeric Normalization
    # ---------------------------------------------------------
    numeric_fields = [
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
        "station_latitude",
        "station_longitude",
        "station_distance_km",
        "block_forecast_rainfall_mm",
        "actual_rainfall_mm",
    ]
    for col in numeric_fields:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ---------------------------------------------------------
    # 7. Physical Validation & Severity Enforcement
    # ---------------------------------------------------------
    error_mask = pd.Series(False, index=df.index)

    # A. Identifier Checks (ERROR if <= 0 or missing)
    invalid_pid = (df["panchayat_id"] <= 0) | df["panchayat_id"].isnull()
    if invalid_pid.any():
        error_mask |= invalid_pid
        errors_list.append(f"Invalid or non-positive panchayat_id: {int(invalid_pid.sum())} rows")

    invalid_lgd = (df["lgd_code"] < 100000) | (df["lgd_code"] > 999999) | df["lgd_code"].isnull()
    if invalid_lgd.any():
        error_mask |= invalid_lgd
        errors_list.append(f"Invalid LGD code outside [100000, 999999]: {int(invalid_lgd.sum())} rows")

    # B. Geographic Coordinate Checks (ERROR if out of global range or missing or (0,0))
    invalid_coords = (
        (df["panchayat_latitude"] < -90.0) | (df["panchayat_latitude"] > 90.0) |
        (df["panchayat_longitude"] < -180.0) | (df["panchayat_longitude"] > 180.0) |
        ((df["panchayat_latitude"] == 0.0) & (df["panchayat_longitude"] == 0.0)) |
        df["panchayat_latitude"].isnull() | df["panchayat_longitude"].isnull()
    )
    if invalid_coords.any():
        error_mask |= invalid_coords
        errors_list.append(f"Invalid or missing Panchayat coordinates: {int(invalid_coords.sum())} rows")

    # WARNING for coordinates outside Maharashtra regional bounding envelope
    outside_mh = (
        (df["panchayat_latitude"] < MH_LAT_MIN) | (df["panchayat_latitude"] > MH_LAT_MAX) |
        (df["panchayat_longitude"] < MH_LON_MIN) | (df["panchayat_longitude"] > MH_LON_MAX)
    ) & ~invalid_coords
    if outside_mh.any():
        warnings_list.append(f"Panchayat coordinates outside Maharashtra regional envelope: {int(outside_mh.sum())} rows")

    # C. Elevation Checks (ERROR if null; WARNING if outside realistic bounds)
    null_elevation = df["elevation_m"].isnull()
    if null_elevation.any():
        error_mask |= null_elevation
        errors_list.append(f"Missing elevation: {int(null_elevation.sum())} rows")

    unrealistic_elevation = ((df["elevation_m"] < 0.0) | (df["elevation_m"] > 2500.0)) & ~null_elevation
    if unrealistic_elevation.any():
        warnings_list.append(f"Elevation outside expected Deccan/Ghat range [0, 2500m]: {int(unrealistic_elevation.sum())} rows")

    # D. Date Checks (ERROR if unparseable or negative lead days)
    invalid_dates = df["date"].isnull() | df["forecast_issue_date"].isnull()
    if invalid_dates.any():
        error_mask |= invalid_dates
        errors_list.append(f"Unparseable date or forecast_issue_date: {int(invalid_dates.sum())} rows")

    negative_lead = (df["lead_days"] < 0) & ~invalid_dates
    if negative_lead.any():
        error_mask |= negative_lead
        errors_list.append(f"Negative lead days (issue_date > target_date): {int(negative_lead.sum())} rows")

    large_lead = (df["lead_days"] > 15) & ~invalid_dates & ~negative_lead
    if large_lead.any():
        warnings_list.append(f"Lead days > 15 days: {int(large_lead.sum())} rows")

    # E. Rainfall Normalization & Checks
    # Sentinel check (-999, -999.9, 9999) & negative actual rainfall -> Coerced to null with WARNING
    sentinel_actual = (
        (df["actual_rainfall_mm"] == -999.0) |
        (df["actual_rainfall_mm"] == -999.9) |
        (df["actual_rainfall_mm"] == 9999.0) |
        (df["actual_rainfall_mm"] < 0.0)
    )
    if sentinel_actual.any():
        df.loc[sentinel_actual, "actual_rainfall_mm"] = np.nan
        warnings_list.append(f"Sanitized negative/sentinel actual rainfall to null: {int(sentinel_actual.sum())} rows")

    # Forecast rainfall must be non-negative (ERROR if negative or null)
    invalid_forecast = (df["block_forecast_rainfall_mm"] < 0.0) | df["block_forecast_rainfall_mm"].isnull()
    if invalid_forecast.any():
        error_mask |= invalid_forecast
        errors_list.append(f"Invalid or negative block forecast rainfall: {int(invalid_forecast.sum())} rows")

    extreme_forecast = (df["block_forecast_rainfall_mm"] > 300.0) & ~invalid_forecast
    if extreme_forecast.any():
        warnings_list.append(f"Extreme block forecast rainfall (> 300mm): {int(extreme_forecast.sum())} rows")

    extreme_actual = (df["actual_rainfall_mm"] > 500.0)
    if extreme_actual.any():
        warnings_list.append(f"Extreme actual rainfall (> 500mm): {int(extreme_actual.sum())} rows")

    # F. Station Distance Verification
    recalculated_dist = haversine_vectorized(
        df["panchayat_latitude"], df["panchayat_longitude"],
        df["station_latitude"], df["station_longitude"]
    )
    distance_discrepancy = (df["station_distance_km"] - recalculated_dist).abs()
    large_distance_diff = (distance_discrepancy > 5.0).sum()
    if large_distance_diff > 0:
        warnings_list.append(f"Station distance discrepancy > 5.0 km vs Haversine calculation: {int(large_distance_diff)} rows")

    sparse_station_dist = (df["station_distance_km"] > 50.0).sum()
    if sparse_station_dist > 0:
        warnings_list.append(f"Panchayats with station distance > 50.0 km: {int(sparse_station_dist)} rows")

    # G. Duplicate & Conflict Detection
    exact_duplicates_count = int(df.duplicated().sum())
    if exact_duplicates_count > 0:
        warnings_list.append(f"Exact duplicate rows detected: {exact_duplicates_count} rows")

    # Business key is (panchayat_id, date, lead_days)
    key_cols = ["panchayat_id", "date", "lead_days"]
    key_duplicates_count = int(df.duplicated(subset=key_cols).sum())
    if key_duplicates_count > 0:
        warnings_list.append(f"Duplicate business keys detected: {key_duplicates_count} rows")

    # Conflict check: same (panchayat_id, date, lead_days) with conflicting rainfall or forecast
    conflicts_count = 0
    if key_duplicates_count > 0:
        grouped_key = df.groupby(key_cols)
        actual_variance = grouped_key["actual_rainfall_mm"].nunique(dropna=False)
        forecast_variance = grouped_key["block_forecast_rainfall_mm"].nunique(dropna=False)
        conflicts_count = int(((actual_variance > 1) | (forecast_variance > 1)).sum())
        if conflicts_count > 0:
            errors_list.append(f"Conflicting duplicate business keys with mismatched values: {conflicts_count} groups")

    # ---------------------------------------------------------
    # 8. Assembly of 22 Canonical Columns & Quality Classification
    # ---------------------------------------------------------
    # Inject Provenance / Audit Lineage
    df["source_dataset"] = source_dataset_val
    df["source_file"] = source_path_val
    df["source_row_id"] = source_row_id_series
    df["source_panchayat_id"] = source_panchayat_id_series
    df["state_name"] = state_name_val

    # Rounding numeric values to canonical precision
    df["panchayat_latitude"] = df["panchayat_latitude"].round(6)
    df["panchayat_longitude"] = df["panchayat_longitude"].round(6)
    df["station_latitude"] = df["station_latitude"].round(6)
    df["station_longitude"] = df["station_longitude"].round(6)
    df["elevation_m"] = df["elevation_m"].round(1)
    df["station_distance_km"] = df["station_distance_km"].round(2)
    df["block_forecast_rainfall_mm"] = df["block_forecast_rainfall_mm"].round(2)
    df["actual_rainfall_mm"] = df["actual_rainfall_mm"].round(2)

    # Filter out rows with ERROR violations
    valid_df = df[~error_mask][CANONICAL_COLUMNS].copy()
    rejected_rows_count = int(error_mask.sum())

    # Overall Normalization Status Classification
    if rejected_rows_count > 0 or len(errors_list) > 0:
        norm_status = "FAIL" if len(valid_df) == 0 else "PASS WITH WARNINGS"
    elif len(warnings_list) > 0:
        norm_status = "PASS WITH WARNINGS"
    else:
        norm_status = "PASS"

    # ---------------------------------------------------------
    # 9. Structured Quality Report Generation
    # ---------------------------------------------------------
    quality_report = {
        "district": config.name,
        "district_key": config.district_key,
        "source_file": source_path_val,
        "normalization_status": norm_status,
        "input_row_count": total_raw_rows,
        "output_row_count": len(valid_df),
        "valid_rows": len(valid_df),
        "rejected_row_count": rejected_rows_count,
        "rejected_rows": rejected_rows_count,
        "errors_count": len(errors_list),
        "warnings_count": len(warnings_list),
        "info_count": len(info_list),
        "errors": errors_list,
        "warnings": warnings_list,
        "info": info_list,
        "canonical_columns_count": len(CANONICAL_COLUMNS),
        "canonical_columns": CANONICAL_COLUMNS,
        "mapped_source_columns": mapped_source_cols,
        "unmapped_source_columns": unmapped_source_cols,
        "unique_panchayats": int(valid_df["panchayat_id"].nunique()) if len(valid_df) > 0 else 0,
        "unique_lgd_codes": int(valid_df["lgd_code"].nunique()) if len(valid_df) > 0 else 0,
        "unique_blocks": int(valid_df["block_name"].nunique()) if len(valid_df) > 0 else 0,
        "block_names": sorted(valid_df["block_name"].unique().tolist()) if len(valid_df) > 0 else [],
        "unique_stations": int(valid_df["station_id"].nunique()) if len(valid_df) > 0 else 0,
        "temporal_coverage": {
            "min_date": str(valid_df["date"].min()) if len(valid_df) > 0 else None,
            "max_date": str(valid_df["date"].max()) if len(valid_df) > 0 else None,
            "unique_dates_count": int(valid_df["date"].nunique()) if len(valid_df) > 0 else 0,
            "lead_days_distribution": {
                str(k): int(v) for k, v in valid_df["lead_days"].value_counts().items()
            } if len(valid_df) > 0 else {},
        },
        "rainfall_summary": {
            "block_forecast_min": float(valid_df["block_forecast_rainfall_mm"].min()) if len(valid_df) > 0 else None,
            "block_forecast_max": float(valid_df["block_forecast_rainfall_mm"].max()) if len(valid_df) > 0 else None,
            "block_forecast_mean": round(float(valid_df["block_forecast_rainfall_mm"].mean()), 2) if len(valid_df) > 0 else None,
            "actual_rainfall_min": float(valid_df["actual_rainfall_mm"].dropna().min()) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "actual_rainfall_max": float(valid_df["actual_rainfall_mm"].dropna().max()) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "actual_rainfall_mean": round(float(valid_df["actual_rainfall_mm"].dropna().mean()), 2) if not valid_df["actual_rainfall_mm"].dropna().empty else None,
            "actual_rainfall_nulls": int(valid_df["actual_rainfall_mm"].isnull().sum()),
        },
        "geographic_summary": {
            "lat_min": float(valid_df["panchayat_latitude"].min()) if len(valid_df) > 0 else None,
            "lat_max": float(valid_df["panchayat_latitude"].max()) if len(valid_df) > 0 else None,
            "lon_min": float(valid_df["panchayat_longitude"].min()) if len(valid_df) > 0 else None,
            "lon_max": float(valid_df["panchayat_longitude"].max()) if len(valid_df) > 0 else None,
            "elevation_min": float(valid_df["elevation_m"].min()) if len(valid_df) > 0 else None,
            "elevation_max": float(valid_df["elevation_m"].max()) if len(valid_df) > 0 else None,
            "elevation_mean": round(float(valid_df["elevation_m"].mean()), 2) if len(valid_df) > 0 else None,
        },
        "station_distance_summary": {
            "min_km": float(valid_df["station_distance_km"].min()) if len(valid_df) > 0 else None,
            "max_km": float(valid_df["station_distance_km"].max()) if len(valid_df) > 0 else None,
            "mean_km": round(float(valid_df["station_distance_km"].mean()), 2) if len(valid_df) > 0 else None,
            "max_haversine_discrepancy_km": round(float(distance_discrepancy.max()), 4) if len(valid_df) > 0 else 0.0,
        },
        "duplicates_summary": {
            "exact_duplicate_rows": exact_duplicates_count,
            "business_key_duplicates": key_duplicates_count,
            "conflicting_duplicates": conflicts_count,
        }
    }

    return valid_df, quality_report


def normalize_weather_data(
    source_path: str,
    district: str,
    output_path: Optional[str] = None,
    config: Optional[DistrictConfig] = None,
    dry_run: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    District-independent normalization pipeline entrypoint.
    Loads raw CSV safely, executes canonical normalization and validation,
    and optionally writes intermediate output without mutating raw inputs.

    Parameters:
        source_path: Path to raw source dataset CSV
        district: District name or key (e.g. 'nashik', 'pune')
        output_path: Destination path for normalized CSV (optional)
        config: Optional pre-configured DistrictConfig instance
        dry_run: If True, executes full pipeline and validation without disk writes

    Returns:
        valid_df: Normalized canonical DataFrame (22 columns)
        quality_report: Structured validation and quality dictionary
    """
    if config is None:
        config = get_district_config(district)

    raw_path = source_path or config.raw_path
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Source raw weather dataset not found: {raw_path}")

    # Read raw dataset safely with encoding sequence fallback
    encodings_to_try = [config.encoding, "utf-8", "latin1", "cp1252"]
    df_raw = None
    loaded_encoding = ""
    for enc in encodings_to_try:
        try:
            df_raw = pd.read_csv(raw_path, encoding=enc, low_memory=False)
            loaded_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if df_raw is None:
        raise ValueError(f"Failed to read {raw_path} with any supported encodings: {encodings_to_try}")

    logger.info(
        f"Loaded raw dataset '{raw_path}' for district '{config.name}' "
        f"({len(df_raw):,} rows, {len(df_raw.columns)} cols, encoding='{loaded_encoding}')."
    )

    # Execute normalization
    valid_df, quality_report = normalize_and_validate_dataset(
        df_raw=df_raw,
        config=config,
        raw_file_path=raw_path
    )

    # Handle output persistence
    if not dry_run and output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        valid_df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"Saved normalized canonical dataset ({len(valid_df):,} rows) to: {output_path}")

    return valid_df, quality_report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GramSevak Canonical Weather Data Normalization Pipeline")
    parser.add_argument("--district", type=str, required=True, help="District key ('nashik', 'pune', etc.)")
    parser.add_argument("--source-path", type=str, default=None, help="Custom path to raw CSV file")
    parser.add_argument("--output", type=str, default=None, help="Output destination path for normalized CSV")
    parser.add_argument("--dry-run", action="store_true", help="Execute normalization and validation without writing files")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    df_norm, report = normalize_weather_data(
        source_path=args.source_path,
        district=args.district,
        output_path=args.output,
        dry_run=args.dry_run
    )

    print("\n" + "=" * 60)
    print(f"CANONICAL NORMALIZATION REPORT: {report['district'].upper()}")
    print("=" * 60)
    print(f"Status               : {report['normalization_status']}")
    print(f"Input Rows           : {report['input_row_count']:,}")
    print(f"Valid Canonical Rows : {report['output_row_count']:,}")
    print(f"Rejected Rows        : {report['rejected_row_count']:,}")
    print(f"Canonical Columns    : {report['canonical_columns_count']}")
    print(f"Unique Panchayats    : {report['unique_panchayats']:,}")
    print(f"Unique Blocks        : {report['unique_blocks']:,}")
    print(f"Date Range           : {report['temporal_coverage']['min_date']} to {report['temporal_coverage']['max_date']}")
    print(f"Errors Logged        : {report['errors_count']}")
    print(f"Warnings Logged      : {report['warnings_count']}")
    print("=" * 60 + "\n")
