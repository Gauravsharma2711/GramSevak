"""
GramSevak Validated Parquet Weather Pipeline (Phase 1.5).

Consumes Phase 1.4 canonical normalized weather datasets, enforces strict canonical
schema typing, executes pre-conversion validation, produces standardized columnar
Parquet files, and performs comprehensive post-write read-back verification.

Canonical Schema: 22 fields strictly defined in schemas/canonical_weather_schema.json.
Supported Engines: PyArrow (primary) and Pandas.
Compression: Snappy (deterministic, highly performant, standard).
"""

import os
import sys
import time
import hashlib
import logging
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("parquet_pipeline")

# Exact 22-field canonical weather schema defined in Phase 1.3 & 1.4
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

# Authoritative PyArrow Schema for Canonical Storage
CANONICAL_PARQUET_SCHEMA = pa.schema([
    ("panchayat_id", pa.int64()),
    ("lgd_code", pa.int64()),
    ("panchayat_name", pa.string()),
    ("block_name", pa.string()),
    ("district_name", pa.string()),
    ("state_name", pa.string()),
    ("panchayat_latitude", pa.float64()),
    ("panchayat_longitude", pa.float64()),
    ("elevation_m", pa.float64()),
    ("date", pa.string()),
    ("forecast_issue_date", pa.string()),
    ("lead_days", pa.int64()),
    ("block_forecast_rainfall_mm", pa.float64()),
    ("station_id", pa.string()),
    ("station_latitude", pa.float64()),
    ("station_longitude", pa.float64()),
    ("station_distance_km", pa.float64()),
    ("actual_rainfall_mm", pa.float64()),
    ("source_dataset", pa.string()),
    ("source_file", pa.string()),
    ("source_row_id", pa.int64()),
    ("source_panchayat_id", pa.string()),
])


def validate_pre_parquet(df: pd.DataFrame) -> Tuple[bool, List[str], List[str]]:
    """
    Validates input DataFrame against the 22-column canonical weather contract
    prior to Parquet conversion.

    Returns:
        is_valid: True if zero fatal errors detected
        errors: List of fatal validation error descriptions
        warnings: List of non-fatal audit warning descriptions
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Column Presence & Order Check
    missing_cols = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required canonical columns: {missing_cols}")

    unexpected_cols = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    if unexpected_cols:
        warnings.append(f"Unexpected non-canonical columns present (will be excluded): {unexpected_cols}")

    if errors:
        return False, errors, warnings

    # 2. Row Count Check
    if len(df) == 0:
        errors.append("Input dataset is empty (0 rows)")
        return False, errors, warnings

    # 3. Critical Identifiers Non-Null and Domain Constraints
    null_pids = int(df["panchayat_id"].isnull().sum())
    if null_pids > 0:
        errors.append(f"Found {null_pids} null values in required 'panchayat_id'")

    invalid_pids = int((pd.to_numeric(df["panchayat_id"], errors="coerce") <= 0).sum())
    if invalid_pids > 0:
        errors.append(f"Found {invalid_pids} non-positive values in 'panchayat_id'")

    null_lgd = int(df["lgd_code"].isnull().sum())
    if null_lgd > 0:
        errors.append(f"Found {null_lgd} null values in required 'lgd_code'")

    # 4. Critical Administrative Fields Non-Null & Non-Empty
    for str_col in ["panchayat_name", "block_name", "district_name", "state_name", "station_id"]:
        null_count = int(df[str_col].isnull().sum())
        empty_count = int((df[str_col].astype(str).str.strip() == "").sum())
        if null_count > 0 or empty_count > 0:
            errors.append(f"Field '{str_col}' contains {null_count} nulls and {empty_count} blank strings")

    # 5. Coordinate Domain Validation
    lat_invalid = int((
        (pd.to_numeric(df["panchayat_latitude"], errors="coerce") < -90.0) |
        (pd.to_numeric(df["panchayat_latitude"], errors="coerce") > 90.0) |
        df["panchayat_latitude"].isnull()
    ).sum())
    if lat_invalid > 0:
        errors.append(f"Found {lat_invalid} invalid or out-of-bounds values in 'panchayat_latitude'")

    lon_invalid = int((
        (pd.to_numeric(df["panchayat_longitude"], errors="coerce") < -180.0) |
        (pd.to_numeric(df["panchayat_longitude"], errors="coerce") > 180.0) |
        df["panchayat_longitude"].isnull()
    ).sum())
    if lon_invalid > 0:
        errors.append(f"Found {lon_invalid} invalid or out-of-bounds values in 'panchayat_longitude'")

    # 6. Dates and Lead Days
    date_invalid = int((
        pd.to_datetime(df["date"], errors="coerce", format="%Y-%m-%d").isnull()
    ).sum())
    if date_invalid > 0:
        errors.append(f"Found {date_invalid} invalid ISO 8601 date strings in 'date'")

    issue_invalid = int((
        pd.to_datetime(df["forecast_issue_date"], errors="coerce", format="%Y-%m-%d").isnull()
    ).sum())
    if issue_invalid > 0:
        errors.append(f"Found {issue_invalid} invalid ISO 8601 date strings in 'forecast_issue_date'")

    negative_leads = int((pd.to_numeric(df["lead_days"], errors="coerce") < 0).sum())
    if negative_leads > 0:
        errors.append(f"Found {negative_leads} negative lead_days values")

    # 7. Rainfall Constraints
    negative_forecast = int((pd.to_numeric(df["block_forecast_rainfall_mm"], errors="coerce") < 0.0).sum())
    if negative_forecast > 0:
        errors.append(f"Found {negative_forecast} negative block_forecast_rainfall_mm values")

    actual_rf = pd.to_numeric(df["actual_rainfall_mm"], errors="coerce")
    negative_actual = int((actual_rf < 0.0).sum())
    if negative_actual > 0:
        errors.append(f"Found {negative_actual} negative actual_rainfall_mm values (should have been sanitized)")

    # 8. Duplicate / Conflict Check
    key_cols = ["panchayat_id", "date", "lead_days"]
    key_dups = int(df.duplicated(subset=key_cols).sum())
    if key_dups > 0:
        warnings.append(f"Duplicate business keys ({key_cols}) detected: {key_dups} rows")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def enforce_canonical_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explicitly coerces columns into canonical types and deterministic order.
    Guarantees that null representation and integer/float casting conform to
    schemas/canonical_weather_schema.json without loss of precision or NaN corruption.
    """
    df_clean = df.copy()

    # Ensure all canonical columns exist (raises KeyError if missing)
    df_ordered = df_clean[CANONICAL_COLUMNS].copy()

    # Integer identifiers
    df_ordered["panchayat_id"] = pd.to_numeric(df_ordered["panchayat_id"], errors="coerce").astype(np.int64)
    df_ordered["lgd_code"] = pd.to_numeric(df_ordered["lgd_code"], errors="coerce").astype(np.int64)
    df_ordered["lead_days"] = pd.to_numeric(df_ordered["lead_days"], errors="coerce").astype(np.int64)
    df_ordered["source_row_id"] = pd.to_numeric(df_ordered["source_row_id"], errors="coerce").astype(np.int64)

    # Floating point numbers
    float_cols = [
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
        "block_forecast_rainfall_mm",
        "station_latitude",
        "station_longitude",
        "station_distance_km",
        "actual_rainfall_mm",
    ]
    for c in float_cols:
        df_ordered[c] = pd.to_numeric(df_ordered[c], errors="coerce").astype(np.float64)

    # Text / String columns
    str_cols = [
        "panchayat_name",
        "block_name",
        "district_name",
        "state_name",
        "date",
        "forecast_issue_date",
        "station_id",
        "source_dataset",
        "source_file",
        "source_panchayat_id",
    ]
    for c in str_cols:
        df_ordered[c] = df_ordered[c].astype(str).str.strip()

    return df_ordered


def write_canonical_parquet(
    df: pd.DataFrame,
    output_path: str,
    compression: str = "snappy"
) -> Dict[str, Any]:
    """
    Converts DataFrame into a PyArrow Table adhering strictly to CANONICAL_PARQUET_SCHEMA,
    and performs an atomic file write using the specified compression codec.

    Parameters:
        df: Pre-validated DataFrame with canonical columns and types
        output_path: Destination file path for Parquet dataset
        compression: Parquet compression codec (default: 'snappy')

    Returns:
        write_metadata: Dictionary with file size, write time, row count, schema info
    """
    start_time = time.perf_counter()

    # Convert DataFrame to PyArrow Table with explicit canonical schema
    arrow_table = pa.Table.from_pandas(
        df,
        schema=CANONICAL_PARQUET_SCHEMA,
        preserve_index=False
    )

    # Ensure target directory exists
    target_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(target_dir, exist_ok=True)

    # Atomic write pattern: write to .tmp file then rename
    temp_path = f"{output_path}.tmp_{os.getpid()}_{int(time.time())}"
    try:
        pq.write_table(
            arrow_table,
            temp_path,
            compression=compression,
            use_dictionary=True,
        )
        if os.path.exists(output_path):
            os.remove(output_path)
        os.replace(temp_path, output_path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"Failed to write Parquet file at {output_path}: {e}") from e

    elapsed_sec = time.perf_counter() - start_time
    file_size_bytes = os.path.getsize(output_path)

    logger.info(
        f"Wrote canonical Parquet dataset to '{output_path}' "
        f"({len(df):,} rows, {file_size_bytes:,} bytes, compression='{compression}', elapsed={elapsed_sec:.3f}s)."
    )

    return {
        "output_path": output_path,
        "row_count": len(df),
        "column_count": len(CANONICAL_COLUMNS),
        "file_size_bytes": file_size_bytes,
        "compression": compression,
        "write_elapsed_seconds": round(elapsed_sec, 4),
    }


def compute_logical_fingerprint(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes a deterministic logical fingerprint across canonical columns,
    keys, null distributions, and numeric aggregates for verification.
    """
    # Sorted business key hash
    key_df = df[["panchayat_id", "date", "lead_days"]].sort_values(by=["panchayat_id", "date", "lead_days"])
    key_repr = "\n".join(f"{p}:{d}:{l}" for p, d, l in zip(key_df["panchayat_id"], key_df["date"], key_df["lead_days"]))
    key_hash = hashlib.sha256(key_repr.encode("utf-8")).hexdigest()

    # Null counts map
    null_counts = {col: int(df[col].isnull().sum()) for col in CANONICAL_COLUMNS}

    # Numeric aggregates
    aggregates = {
        "block_forecast_sum": round(float(df["block_forecast_rainfall_mm"].sum()), 4),
        "block_forecast_mean": round(float(df["block_forecast_rainfall_mm"].mean()), 4),
        "actual_rainfall_sum": round(float(df["actual_rainfall_mm"].dropna().sum()), 4) if not df["actual_rainfall_mm"].dropna().empty else 0.0,
        "actual_rainfall_mean": round(float(df["actual_rainfall_mm"].dropna().mean()), 4) if not df["actual_rainfall_mm"].dropna().empty else 0.0,
        "elevation_mean": round(float(df["elevation_m"].mean()), 4),
        "unique_panchayats": int(df["panchayat_id"].nunique()),
        "unique_blocks": int(df["block_name"].nunique()),
        "min_date": str(df["date"].min()),
        "max_date": str(df["date"].max()),
    }

    return {
        "key_hash": key_hash,
        "null_counts": null_counts,
        "aggregates": aggregates,
    }


def validate_parquet_file(
    parquet_path: str,
    expected_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Reads back generated Parquet file from disk using both PyArrow and Pandas.
    Validates schema, column order, data types, row counts, null distributions,
    and aggregate consistency against expected DataFrame.

    Returns:
        validation_report: Dictionary with comprehensive validation metrics and status
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Existence and File Size Check
    if not os.path.exists(parquet_path):
        errors.append(f"Parquet file does not exist: {parquet_path}")
        return {
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "parquet_path": parquet_path,
        }

    file_size_bytes = os.path.getsize(parquet_path)
    if file_size_bytes == 0:
        errors.append(f"Parquet file is empty (0 bytes): {parquet_path}")

    # 2. PyArrow Low-Level Read & Schema Verification
    try:
        parquet_file = pq.ParquetFile(parquet_path)
        arrow_metadata = parquet_file.metadata
        arrow_schema = parquet_file.schema_arrow
        arrow_num_rows = arrow_metadata.num_rows
        arrow_num_cols = arrow_metadata.num_columns
    except Exception as e:
        errors.append(f"PyArrow failed to open Parquet file: {e}")
        return {
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "parquet_path": parquet_path,
        }

    # Verify column count and names
    if arrow_num_cols != len(CANONICAL_COLUMNS):
        errors.append(f"Column count mismatch: expected {len(CANONICAL_COLUMNS)}, found {arrow_num_cols}")

    arrow_col_names = arrow_schema.names
    if arrow_col_names != CANONICAL_COLUMNS:
        errors.append(f"Column order/names mismatch vs CANONICAL_COLUMNS: {arrow_col_names}")

    # Verify types against CANONICAL_PARQUET_SCHEMA
    for expected_field in CANONICAL_PARQUET_SCHEMA:
        idx = arrow_schema.get_field_index(expected_field.name)
        if idx == -1:
            errors.append(f"Missing canonical field '{expected_field.name}' in Parquet schema")
        else:
            actual_field = arrow_schema.field(idx)
            if actual_field.type != expected_field.type:
                errors.append(
                    f"Type mismatch for field '{expected_field.name}': "
                    f"expected {expected_field.type}, got {actual_field.type}"
                )

    # 3. Pandas High-Level Read Verification
    try:
        df_read = pd.read_parquet(parquet_path, engine="pyarrow")
    except Exception as e:
        errors.append(f"Pandas read_parquet failed: {e}")
        df_read = None

    if df_read is not None:
        read_rows = len(df_read)
        if read_rows != arrow_num_rows:
            errors.append(f"Pandas row count ({read_rows}) differs from Arrow metadata ({arrow_num_rows})")

        # 4. Deep Data Integrity Comparison against Source if provided (only if schema has zero errors)
        read_fp = None
        if len(errors) == 0:
            if expected_df is not None:
                expected_rows = len(expected_df)
                if read_rows != expected_rows:
                    errors.append(f"Row count mismatch: expected {expected_rows:,}, read {read_rows:,}")

                # Verify unique Panchayats & Blocks
                exp_panch = int(expected_df["panchayat_id"].nunique())
                read_panch = int(df_read["panchayat_id"].nunique())
                if exp_panch != read_panch:
                    errors.append(f"Unique Panchayats mismatch: expected {exp_panch}, read {read_panch}")

                exp_blocks = int(expected_df["block_name"].nunique())
                read_blocks = int(df_read["block_name"].nunique())
                if exp_blocks != read_blocks:
                    errors.append(f"Unique Blocks mismatch: expected {exp_blocks}, read {read_blocks}")

                # Verify date ranges
                if str(expected_df["date"].min()) != str(df_read["date"].min()):
                    errors.append("Min date mismatch")
                if str(expected_df["date"].max()) != str(df_read["date"].max()):
                    errors.append("Max date mismatch")

                # Null count preservation
                for col in CANONICAL_COLUMNS:
                    exp_nulls = int(expected_df[col].isnull().sum())
                    read_nulls = int(df_read[col].isnull().sum())
                    if exp_nulls != read_nulls:
                        errors.append(f"Null count mismatch in '{col}': expected {exp_nulls}, read {read_nulls}")

                # Numeric Aggregate Comparison with 1e-4 tolerance
                numeric_check_cols = [
                    "panchayat_latitude",
                    "panchayat_longitude",
                    "elevation_m",
                    "block_forecast_rainfall_mm",
                    "station_latitude",
                    "station_longitude",
                    "station_distance_km",
                ]
                for col in numeric_check_cols:
                    exp_sum = float(expected_df[col].sum())
                    read_sum = float(df_read[col].sum())
                    if abs(exp_sum - read_sum) > 1e-4:
                        errors.append(f"Aggregate sum mismatch for '{col}': diff={abs(exp_sum - read_sum):.6f}")

                # Actual rainfall sum (excluding nulls)
                exp_rf_sum = float(expected_df["actual_rainfall_mm"].dropna().sum())
                read_rf_sum = float(df_read["actual_rainfall_mm"].dropna().sum())
                if abs(exp_rf_sum - read_rf_sum) > 1e-4:
                    errors.append(f"Aggregate actual rainfall sum mismatch: diff={abs(exp_rf_sum - read_rf_sum):.6f}")

                # Logical Key Fingerprint Comparison
                exp_fp = compute_logical_fingerprint(expected_df)
                read_fp = compute_logical_fingerprint(df_read)
                if exp_fp["key_hash"] != read_fp["key_hash"]:
                    errors.append("Logical business key fingerprint mismatch between source and Parquet")
            else:
                read_fp = compute_logical_fingerprint(df_read)

    status = "PASS" if len(errors) == 0 else "FAIL"

    return {
        "status": status,
        "parquet_path": parquet_path,
        "file_size_bytes": file_size_bytes,
        "arrow_rows": arrow_num_rows,
        "arrow_columns": arrow_num_cols,
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "logical_fingerprint": read_fp if df_read is not None else None,
    }


def convert_normalized_to_parquet(
    input_path: str,
    output_path: str,
    district: str,
    compression: str = "snappy",
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    District-independent pipeline executing pre-parquet validation, type enforcement,
    Parquet conversion, and post-write read-back verification.

    Parameters:
        input_path: Source path to Phase 1.4 normalized CSV
        output_path: Destination path for canonical Parquet file
        district: Target district name (e.g. 'nashik', 'pune')
        compression: Parquet compression codec (default: 'snappy')
        dry_run: If True, performs validation and type enforcement without disk write

    Returns:
        pipeline_report: Comprehensive execution and verification report
    """
    start_total = time.perf_counter()

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Normalized input dataset not found: {input_path}")

    # Read normalized dataset
    logger.info(f"Loading normalized dataset from '{input_path}' for district '{district}'...")
    df_norm = pd.read_csv(input_path, low_memory=False)
    input_row_count = len(df_norm)

    # 1. Pre-Parquet Validation
    is_valid, pre_errors, pre_warnings = validate_pre_parquet(df_norm)
    if not is_valid:
        raise ValueError(f"Pre-Parquet validation failed for {district}: {pre_errors}")

    # 2. Type Enforcement & Canonical Ordering
    df_canonical = enforce_canonical_types(df_norm)

    write_meta = {}
    validation_res = {}

    if dry_run:
        logger.info(f"[DRY-RUN] Pre-Parquet validation succeeded ({input_row_count:,} rows). Skipping disk write.")
        status = "PASS" if len(pre_errors) == 0 else "FAIL"
    else:
        # 3. Parquet Writing
        write_meta = write_canonical_parquet(
            df=df_canonical,
            output_path=output_path,
            compression=compression,
        )

        # 4. Post-Write Parquet Validation & Read-Back Integrity Audit
        validation_res = validate_parquet_file(
            parquet_path=output_path,
            expected_df=df_canonical
        )
        status = validation_res["status"]

    total_elapsed = time.perf_counter() - start_total

    pipeline_report = {
        "district": district,
        "input_path": input_path,
        "output_path": output_path,
        "dry_run": dry_run,
        "input_rows": input_row_count,
        "canonical_columns_count": len(CANONICAL_COLUMNS),
        "pre_validation": {
            "status": "PASS" if len(pre_errors) == 0 else "FAIL",
            "errors": pre_errors,
            "warnings": pre_warnings,
        },
        "write_metadata": write_meta,
        "post_validation": validation_res,
        "overall_status": status,
        "total_elapsed_seconds": round(total_elapsed, 4),
    }

    return pipeline_report
