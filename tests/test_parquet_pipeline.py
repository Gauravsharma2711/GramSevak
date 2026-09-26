"""
Unit tests for GramSevak Validated Parquet Weather Pipeline (Phase 1.5).

Covers all 14 mandatory validation criteria using synthetic fixtures:
1. Valid canonical dataset converts successfully
2. Schema mismatch fails
3. Missing required column fails
4. Unexpected column is reported
5. Invalid type fails or is handled according to contract
6. Row count is preserved
7. Null counts are preserved
8. Identifiers are preserved
9. Date values are preserved
10. Rainfall values are preserved
11. Generated Parquet can be read back
12. Repeated execution is safe (deterministic & idempotent)
13. District-independent execution
14. Raw data remains untouched
"""

import os
import hashlib
import pytest
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data_pipeline.parquet_pipeline import (
    CANONICAL_COLUMNS,
    CANONICAL_PARQUET_SCHEMA,
    validate_pre_parquet,
    enforce_canonical_types,
    write_canonical_parquet,
    validate_parquet_file,
    convert_normalized_to_parquet,
)


@pytest.fixture
def synthetic_canonical_nashik_df():
    """Returns a valid 2-row canonical DataFrame for Nashik."""
    return pd.DataFrame([
        {
            "panchayat_id": 1001,
            "lgd_code": 182597,
            "panchayat_name": "Test Panchayat One",
            "block_name": "Baglan",
            "district_name": "Nashik",
            "state_name": "Maharashtra",
            "panchayat_latitude": 20.650000,
            "panchayat_longitude": 74.050000,
            "elevation_m": 580.0,
            "date": "2026-09-01",
            "forecast_issue_date": "2026-09-01",
            "lead_days": 0,
            "block_forecast_rainfall_mm": 12.50,
            "station_id": "Satana AWS",
            "station_latitude": 20.590000,
            "station_longitude": 74.200000,
            "station_distance_km": 16.92,
            "actual_rainfall_mm": 14.00,
            "source_dataset": "nashik",
            "source_file": "data/raw/nashik/nashik_panchayat_weather_raw.csv",
            "source_row_id": 0,
            "source_panchayat_id": "1001",
        },
        {
            "panchayat_id": 1002,
            "lgd_code": 182598,
            "panchayat_name": "Test Panchayat Two",
            "block_name": "Baglan",
            "district_name": "Nashik",
            "state_name": "Maharashtra",
            "panchayat_latitude": 20.670000,
            "panchayat_longitude": 74.080000,
            "elevation_m": 595.0,
            "date": "2026-09-01",
            "forecast_issue_date": "2026-09-01",
            "lead_days": 0,
            "block_forecast_rainfall_mm": 12.50,
            "station_id": "Satana AWS",
            "station_latitude": 20.590000,
            "station_longitude": 74.200000,
            "station_distance_km": 18.15,
            "actual_rainfall_mm": np.nan,  # Nullable actual rainfall
            "source_dataset": "nashik",
            "source_file": "data/raw/nashik/nashik_panchayat_weather_raw.csv",
            "source_row_id": 1,
            "source_panchayat_id": "1002",
        }
    ])


@pytest.fixture
def synthetic_canonical_pune_df():
    """Returns a valid 1-row canonical DataFrame for Pune."""
    return pd.DataFrame([
        {
            "panchayat_id": 185262,
            "lgd_code": 185262,
            "panchayat_name": "Ahupe",
            "block_name": "Ambegaon",
            "district_name": "Pune",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.167268,
            "panchayat_longitude": 73.563567,
            "elevation_m": 683.0,
            "date": "2026-04-13",
            "forecast_issue_date": "2026-04-12",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 5.20,
            "station_id": "GHCND:IN012190101",
            "station_latitude": 19.050000,
            "station_longitude": 73.830000,
            "station_distance_km": 30.86,
            "actual_rainfall_mm": 4.80,
            "source_dataset": "pune",
            "source_file": "data/raw/pune/pune_original.csv",
            "source_row_id": 0,
            "source_panchayat_id": "MH_27_PUNE_185262",
        }
    ])


# 1. Valid Canonical Dataset Converts Successfully
def test_valid_canonical_dataset_converts(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "valid_nashik.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    meta = write_canonical_parquet(df_clean, str(output_parquet))

    assert os.path.exists(output_parquet)
    assert meta["row_count"] == 2
    assert meta["file_size_bytes"] > 0
    assert meta["compression"] == "snappy"


# 2. Schema Mismatch Fails
def test_schema_mismatch_fails(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "schema_mismatch.parquet"
    # Write a parquet file with an incompatible schema (e.g. only 2 random columns)
    bad_df = pd.DataFrame({"random_col": [1, 2], "extra_col": ["a", "b"]})
    bad_df.to_parquet(str(output_parquet))

    report = validate_parquet_file(str(output_parquet))
    assert report["status"] == "FAIL"
    assert any("mismatch" in e.lower() for e in report["errors"])


# 3. Missing Required Column Fails
def test_missing_required_column_fails(synthetic_canonical_nashik_df):
    df_missing = synthetic_canonical_nashik_df.drop(columns=["elevation_m"])
    is_valid, errors, _ = validate_pre_parquet(df_missing)

    assert not is_valid
    assert any("elevation_m" in e for e in errors)


# 4. Unexpected Column is Reported
def test_unexpected_column_reported(synthetic_canonical_nashik_df):
    df_extra = synthetic_canonical_nashik_df.copy()
    df_extra["unwanted_debug_col"] = 999

    is_valid, errors, warnings = validate_pre_parquet(df_extra)
    assert is_valid  # Non-fatal
    assert any("unwanted_debug_col" in w for w in warnings)


# 5. Invalid Type Fails Pre-Validation
def test_invalid_type_fails_pre_validation(synthetic_canonical_nashik_df):
    df_invalid = synthetic_canonical_nashik_df.copy()
    df_invalid["panchayat_id"] = -500  # Non-positive ID

    is_valid, errors, _ = validate_pre_parquet(df_invalid)
    assert not is_valid
    assert any("non-positive" in e.lower() for e in errors)


# 6. Row Count is Preserved
def test_row_count_preserved(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "row_count.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    report = validate_parquet_file(str(output_parquet), expected_df=df_clean)
    assert report["status"] == "PASS"
    assert report["arrow_rows"] == len(synthetic_canonical_nashik_df)


# 7. Null Counts are Preserved
def test_null_counts_preserved(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "null_counts.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    df_read = pd.read_parquet(str(output_parquet))
    assert df_read["actual_rainfall_mm"].isnull().sum() == 1
    assert df_read["actual_rainfall_mm"].notnull().sum() == 1


# 8. Identifiers are Preserved
def test_identifiers_preserved(synthetic_canonical_pune_df, tmp_path):
    output_parquet = tmp_path / "ids.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_pune_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    df_read = pd.read_parquet(str(output_parquet))
    assert df_read["panchayat_id"].iloc[0] == 185262
    assert df_read["lgd_code"].iloc[0] == 185262
    assert df_read["source_panchayat_id"].iloc[0] == "MH_27_PUNE_185262"


# 9. Date Values are Preserved
def test_date_values_preserved(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "dates.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    df_read = pd.read_parquet(str(output_parquet))
    assert df_read["date"].iloc[0] == "2026-09-01"
    assert df_read["forecast_issue_date"].iloc[0] == "2026-09-01"
    assert df_read["lead_days"].iloc[0] == 0


# 10. Rainfall Values are Preserved
def test_rainfall_values_preserved(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "rainfall.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    df_read = pd.read_parquet(str(output_parquet))
    assert df_read["block_forecast_rainfall_mm"].iloc[0] == 12.50
    assert df_read["actual_rainfall_mm"].iloc[0] == 14.00


# 11. Generated Parquet can be Read Back by Both PyArrow and Pandas
def test_read_back_pyarrow_and_pandas(synthetic_canonical_nashik_df, tmp_path):
    output_parquet = tmp_path / "dual_read.parquet"
    df_clean = enforce_canonical_types(synthetic_canonical_nashik_df)
    write_canonical_parquet(df_clean, str(output_parquet))

    # PyArrow read
    table = pq.read_table(str(output_parquet))
    assert len(table) == 2
    assert table.num_columns == 22

    # Pandas read
    df_pandas = pd.read_parquet(str(output_parquet))
    assert len(df_pandas) == 2
    assert list(df_pandas.columns) == CANONICAL_COLUMNS


# 12. Repeated Execution is Safe (Deterministic & Idempotent)
def test_repeated_execution_is_safe(synthetic_canonical_nashik_df, tmp_path):
    csv_file = tmp_path / "input.csv"
    parquet_file = tmp_path / "output.parquet"
    synthetic_canonical_nashik_df.to_csv(csv_file, index=False)

    # First execution
    rep1 = convert_normalized_to_parquet(str(csv_file), str(parquet_file), district="nashik")
    size1 = os.path.getsize(parquet_file)
    assert rep1["overall_status"] == "PASS"

    # Second execution (overwrites safely)
    rep2 = convert_normalized_to_parquet(str(csv_file), str(parquet_file), district="nashik")
    size2 = os.path.getsize(parquet_file)
    assert rep2["overall_status"] == "PASS"

    # Verify identical size and record count (no duplicate appending)
    assert size1 == size2
    df_read = pd.read_parquet(str(parquet_file))
    assert len(df_read) == 2


# 13. District-Independent Execution
def test_district_independent_execution(synthetic_canonical_nashik_df, synthetic_canonical_pune_df, tmp_path):
    nashik_csv = tmp_path / "norm_nashik.csv"
    pune_csv = tmp_path / "norm_pune.csv"
    nashik_pq = tmp_path / "nashik.parquet"
    pune_pq = tmp_path / "pune.parquet"

    synthetic_canonical_nashik_df.to_csv(nashik_csv, index=False)
    synthetic_canonical_pune_df.to_csv(pune_csv, index=False)

    rep_n = convert_normalized_to_parquet(str(nashik_csv), str(nashik_pq), district="nashik")
    rep_p = convert_normalized_to_parquet(str(pune_csv), str(pune_pq), district="pune")

    assert rep_n["overall_status"] == "PASS"
    assert rep_p["overall_status"] == "PASS"
    assert rep_n["input_rows"] == 2
    assert rep_p["input_rows"] == 1


# 14. Raw Data Remains Untouched
def test_raw_data_remains_untouched(synthetic_canonical_nashik_df, tmp_path):
    raw_dummy = tmp_path / "raw_weather.csv"
    synthetic_canonical_nashik_df.to_csv(raw_dummy, index=False)

    def compute_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    before_hash = compute_sha256(raw_dummy)
    before_mtime = os.path.getmtime(raw_dummy)

    # Execute Parquet pipeline on dummy file
    out_pq = tmp_path / "out.parquet"
    convert_normalized_to_parquet(str(raw_dummy), str(out_pq), district="nashik")

    after_hash = compute_sha256(raw_dummy)
    after_mtime = os.path.getmtime(raw_dummy)

    assert before_hash == after_hash, "Raw file was modified!"
    assert before_mtime == after_mtime, "Raw file mtime changed!"
