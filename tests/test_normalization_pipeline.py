"""
Unit tests for GramSevak Canonical Weather Data Normalization Pipeline (Phase 1.4).

Tests the 14 canonical normalization requirements using synthetic fixtures:
1. valid row normalization
2. numeric conversion
3. date conversion
4. missing-value handling
5. zero rainfall preservation
6. invalid coordinate detection
7. invalid rainfall detection
8. identifier preservation
9. duplicate detection
10. conflicting duplicate detection
11. source-to-canonical mapping
12. lead_days calculation
13. district independence
14. raw data immutability
"""

import os
import hashlib
import tempfile
import pytest
import numpy as np
import pandas as pd

from data_pipeline.canonical_normalizer import (
    CANONICAL_COLUMNS,
    normalize_weather_data,
    normalize_and_validate_dataset,
)
from data_pipeline.district_config import (
    get_district_config,
    DistrictConfig,
)


@pytest.fixture
def synthetic_nashik_row():
    return {
        "panchayat_id": 1001,
        "lgd_code": 182597,
        "panchayat_name": "Test Gram Panchayat\xa0",
        "block_name": "Baglan",
        "district_name": "Nashik",
        "latitude": 20.65,
        "longitude": 74.05,
        "elevation_m": 580.0,
        "date": "01-09-2026",
        "forecast_issue_date": "01-09-2026",
        "block_forecast_rainfall_mm": 12.5,
        "station_id": "Satana\xa0AWS",
        "station_latitude": 20.59,
        "station_longitude": 74.20,
        "station_distance_km": 16.92,
        "actual_rainfall_mm": 14.0,
        "Unnamed: 16": None,
    }


@pytest.fixture
def synthetic_pune_row():
    return {
        "panchayat_id": "MH_27_PUNE_185262",
        "lgd_code": 185262,
        "panchayat_name": "AHUPE",
        "block_name": "AMBEGAON",
        "district_name": "PUNE",
        "panchayat_latitude": 19.167268,
        "panchayat_longitude": 73.563567,
        "elevation_m": 683.0,
        "date": "13-04-2026",
        "forecast_issue_date": "12-04-2026",
        "block_forecast_rainfall_mm": 5.2,
        "actual_rainfall_mm": 4.8,
        "station_id": "GHCND:IN012190101",
        "station_latitude": 19.05,
        "station_longitude": 73.83,
        "station_distance_km": 30.86,
    }


# 1. Valid Row Normalization
def test_valid_row_normalization(synthetic_nashik_row):
    df_raw = pd.DataFrame([synthetic_nashik_row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 1
    assert list(valid_df.columns) == CANONICAL_COLUMNS
    assert report["normalization_status"] in ["PASS", "PASS WITH WARNINGS"]
    assert valid_df["district_name"].iloc[0] == "Nashik"
    assert valid_df["state_name"].iloc[0] == "Maharashtra"
    assert valid_df["source_dataset"].iloc[0] == "nashik"


# 2. Numeric Conversion
def test_numeric_conversion(synthetic_nashik_row):
    row = synthetic_nashik_row.copy()
    row["elevation_m"] = " 620.5 "
    row["latitude"] = "20.65"
    row["longitude"] = "74.05"
    row["block_forecast_rainfall_mm"] = "15.0"

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, _ = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 1
    assert valid_df["elevation_m"].iloc[0] == 620.5
    assert valid_df["panchayat_latitude"].iloc[0] == 20.65
    assert valid_df["panchayat_longitude"].iloc[0] == 74.05
    assert valid_df["block_forecast_rainfall_mm"].iloc[0] == 15.0


# 3. Date Conversion
def test_date_conversion(synthetic_nashik_row):
    # DD-MM-YYYY format
    row = synthetic_nashik_row.copy()
    row["date"] = "15-08-2026"
    row["forecast_issue_date"] = "15-08-2026"

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, _ = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 1
    assert valid_df["date"].iloc[0] == "2026-08-15"
    assert valid_df["forecast_issue_date"].iloc[0] == "2026-08-15"


# 4. Missing-Value Handling
def test_missing_value_handling(synthetic_nashik_row):
    row = synthetic_nashik_row.copy()
    row["actual_rainfall_mm"] = -999.0  # Sentinel value in actual rainfall

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 1
    assert pd.isna(valid_df["actual_rainfall_mm"].iloc[0])
    assert any("sentinel" in w.lower() for w in report["warnings"])


# 5. Zero Rainfall Preservation
def test_zero_rainfall_preservation(synthetic_nashik_row):
    row = synthetic_nashik_row.copy()
    row["actual_rainfall_mm"] = 0.0
    row["block_forecast_rainfall_mm"] = 0.0

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, _ = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 1
    assert valid_df["actual_rainfall_mm"].iloc[0] == 0.0
    assert not pd.isna(valid_df["actual_rainfall_mm"].iloc[0])
    assert valid_df["block_forecast_rainfall_mm"].iloc[0] == 0.0
    assert not pd.isna(valid_df["block_forecast_rainfall_mm"].iloc[0])


# 6. Invalid Coordinate Detection
def test_invalid_coordinate_detection(synthetic_nashik_row):
    row = synthetic_nashik_row.copy()
    row["latitude"] = 120.5  # Invalid latitude (> 90)

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 0
    assert report["rejected_row_count"] == 1
    assert any("coordinates" in e.lower() for e in report["errors"])


# 7. Invalid Rainfall Detection
def test_invalid_forecast_rainfall_detection(synthetic_nashik_row):
    row = synthetic_nashik_row.copy()
    row["block_forecast_rainfall_mm"] = -5.0  # Negative forecast rainfall is invalid

    df_raw = pd.DataFrame([row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert len(valid_df) == 0
    assert report["rejected_row_count"] == 1
    assert any("forecast rainfall" in e.lower() for e in report["errors"])


# 8. Identifier Preservation
def test_identifier_preservation(synthetic_nashik_row, synthetic_pune_row):
    # Nashik: integer IDs
    df_n = pd.DataFrame([synthetic_nashik_row])
    cfg_n = get_district_config("nashik")
    valid_n, _ = normalize_and_validate_dataset(df_n, cfg_n)
    assert valid_n["panchayat_id"].iloc[0] == 1001
    assert valid_n["lgd_code"].iloc[0] == 182597
    assert valid_n["source_panchayat_id"].iloc[0] == "1001"

    # Pune: extracted integer ID and preserved original string
    df_p = pd.DataFrame([synthetic_pune_row])
    cfg_p = get_district_config("pune")
    valid_p, _ = normalize_and_validate_dataset(df_p, cfg_p)
    assert valid_p["panchayat_id"].iloc[0] == 185262
    assert valid_p["lgd_code"].iloc[0] == 185262
    assert valid_p["source_panchayat_id"].iloc[0] == "MH_27_PUNE_185262"


# 9. Duplicate Detection
def test_duplicate_detection(synthetic_nashik_row):
    # Two identical rows
    df_raw = pd.DataFrame([synthetic_nashik_row, synthetic_nashik_row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert report["duplicates_summary"]["exact_duplicate_rows"] == 1
    assert any("exact duplicate" in w.lower() for w in report["warnings"])


# 10. Conflicting Duplicate Detection
def test_conflicting_duplicate_detection(synthetic_nashik_row):
    row1 = synthetic_nashik_row.copy()
    row2 = synthetic_nashik_row.copy()
    row2["actual_rainfall_mm"] = 55.0  # Same business key (panchayat_id + date + lead_days), different rainfall

    df_raw = pd.DataFrame([row1, row2])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert report["duplicates_summary"]["conflicting_duplicates"] > 0
    assert any("conflicting duplicate" in e.lower() for e in report["errors"])


# 11. Source-to-Canonical Mapping
def test_source_to_canonical_mapping(synthetic_nashik_row):
    df_raw = pd.DataFrame([synthetic_nashik_row])
    config = get_district_config("nashik")
    valid_df, report = normalize_and_validate_dataset(df_raw, config)

    assert "Unnamed: 16" in report["unmapped_source_columns"]
    assert "Unnamed: 16" not in valid_df.columns
    assert "panchayat_latitude" in valid_df.columns
    assert "panchayat_longitude" in valid_df.columns


# 12. Lead Days Calculation
def test_lead_days_calculation(synthetic_pune_row, synthetic_nashik_row):
    # Pune: 2026-05-15 date, 2026-05-14 issue_date => lead_days = 1
    df_p = pd.DataFrame([synthetic_pune_row])
    cfg_p = get_district_config("pune")
    valid_p, _ = normalize_and_validate_dataset(df_p, cfg_p)
    assert valid_p["lead_days"].iloc[0] == 1

    # Nashik: same date and issue_date => lead_days = 0
    df_n = pd.DataFrame([synthetic_nashik_row])
    cfg_n = get_district_config("nashik")
    valid_n, _ = normalize_and_validate_dataset(df_n, cfg_n)
    assert valid_n["lead_days"].iloc[0] == 0


# 13. District Independence
def test_district_independence(synthetic_nashik_row, synthetic_pune_row, tmp_path):
    nashik_file = tmp_path / "nashik_test.csv"
    pune_file = tmp_path / "pune_test.csv"

    pd.DataFrame([synthetic_nashik_row]).to_csv(nashik_file, index=False, encoding="latin1")
    pd.DataFrame([synthetic_pune_row]).to_csv(pune_file, index=False, encoding="utf-8")

    # Call the exact same normalize_weather_data function for both
    df_n, rep_n = normalize_weather_data(source_path=str(nashik_file), district="nashik", dry_run=True)
    df_p, rep_p = normalize_weather_data(source_path=str(pune_file), district="pune", dry_run=True)

    assert list(df_n.columns) == CANONICAL_COLUMNS
    assert list(df_p.columns) == CANONICAL_COLUMNS
    assert rep_n["district"] == "Nashik"
    assert rep_p["district"] == "Pune"


# 14. Raw Data Immutability
def test_raw_data_immutability(synthetic_pune_row, tmp_path):
    test_csv = tmp_path / "immutability_test.csv"
    pd.DataFrame([synthetic_pune_row]).to_csv(test_csv, index=False)

    def compute_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    before_hash = compute_sha256(test_csv)
    before_mtime = os.path.getmtime(test_csv)

    # Execute normalization
    normalize_weather_data(
        source_path=str(test_csv),
        district="pune",
        dry_run=True,
    )

    after_hash = compute_sha256(test_csv)
    after_mtime = os.path.getmtime(test_csv)

    assert before_hash == after_hash, "Raw file content was modified!"
    assert before_mtime == after_mtime, "Raw file modification time changed!"
