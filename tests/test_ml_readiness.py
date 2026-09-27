"""
Unit tests for GramSevak ML Dataset Audit & Training Readiness (Phase 2.1).

Validates all 9 mandatory ML readiness criteria using small synthetic fixtures:
1. Target identification: verifies target column is identified, float64, and non-negative
2. Temporal ordering: verifies chronological sequence and gap detection
3. Leakage detection: verifies target and future/contemporaneous data are identified as forbidden features
4. Training eligibility: verifies row filter rules for target, forecast, coordinates, and lead_days
5. Baseline MAE: verifies exact calculation of Mean Absolute Error against synthetic ground truth
6. Baseline RMSE: verifies exact calculation of Root Mean Squared Error against synthetic ground truth
7. Missing-target handling: verifies null targets are flagged and excluded from training eligibility
8. Zero rainfall handling: verifies zero values are treated as valid ground truth dry days
9. District independence: verifies profiler operates seamlessly on arbitrary district datasets
"""

import math
import pytest
import numpy as np
import pandas as pd

from scripts.audit_ml_dataset import (
    compute_target_statistics,
    compute_baseline_slice_metrics,
    compute_baseline_metrics,
    audit_spatial_data,
    audit_historical_feasibility,
    audit_panchayat_coverage,
    evaluate_training_eligibility,
    build_candidate_feature_inventory,
    audit_leakage_risks,
    profile_district,
    determine_readiness_status
)


@pytest.fixture
def synthetic_weather_df():
    """Returns a clean 5-row synthetic canonical DataFrame for testing."""
    return pd.DataFrame([
        {
            "panchayat_id": 1,
            "lgd_code": 100001,
            "panchayat_name": "Panchayat Alpha",
            "block_name": "Block One",
            "district_name": "TestDistrict",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.50,
            "panchayat_longitude": 73.80,
            "elevation_m": 600.0,
            "date": "2026-06-01",
            "forecast_issue_date": "2026-05-31",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 5.0,
            "station_id": "Station A",
            "station_latitude": 19.52,
            "station_longitude": 73.85,
            "station_distance_km": 5.5,
            "actual_rainfall_mm": 8.0,
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 0,
            "source_panchayat_id": "P_01"
        },
        {
            "panchayat_id": 1,
            "lgd_code": 100001,
            "panchayat_name": "Panchayat Alpha",
            "block_name": "Block One",
            "district_name": "TestDistrict",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.50,
            "panchayat_longitude": 73.80,
            "elevation_m": 600.0,
            "date": "2026-06-02",
            "forecast_issue_date": "2026-06-01",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 10.0,
            "station_id": "Station A",
            "station_latitude": 19.52,
            "station_longitude": 73.85,
            "station_distance_km": 5.5,
            "actual_rainfall_mm": 10.0,
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 1,
            "source_panchayat_id": "P_01"
        },
        {
            "panchayat_id": 1,
            "lgd_code": 100001,
            "panchayat_name": "Panchayat Alpha",
            "block_name": "Block One",
            "district_name": "TestDistrict",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.50,
            "panchayat_longitude": 73.80,
            "elevation_m": 600.0,
            "date": "2026-06-03",
            "forecast_issue_date": "2026-06-02",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 2.0,
            "station_id": "Station A",
            "station_latitude": 19.52,
            "station_longitude": 73.85,
            "station_distance_km": 5.5,
            "actual_rainfall_mm": 0.0,  # Dry day
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 2,
            "source_panchayat_id": "P_01"
        },
        {
            "panchayat_id": 2,
            "lgd_code": 100002,
            "panchayat_name": "Panchayat Beta",
            "block_name": "Block Two",
            "district_name": "TestDistrict",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.70,
            "panchayat_longitude": 74.10,
            "elevation_m": 550.0,
            "date": "2026-06-01",
            "forecast_issue_date": "2026-05-31",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 12.0,
            "station_id": "Station B",
            "station_latitude": 19.68,
            "station_longitude": 74.08,
            "station_distance_km": 3.2,
            "actual_rainfall_mm": 40.0,  # Heavy rainfall
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 3,
            "source_panchayat_id": "P_02"
        },
        {
            "panchayat_id": 2,
            "lgd_code": 100002,
            "panchayat_name": "Panchayat Beta",
            "block_name": "Block Two",
            "district_name": "TestDistrict",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.70,
            "panchayat_longitude": 74.10,
            "elevation_m": 550.0,
            "date": "2026-06-02",
            "forecast_issue_date": "2026-06-01",
            "lead_days": 1,
            "block_forecast_rainfall_mm": 0.0,
            "station_id": "Station B",
            "station_latitude": 19.68,
            "station_longitude": 74.08,
            "station_distance_km": 3.2,
            "actual_rainfall_mm": 0.0,  # Dry day
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 4,
            "source_panchayat_id": "P_02"
        }
    ])


# 1. Target identification test
def test_target_identification(synthetic_weather_df):
    """Verifies actual_rainfall_mm is identified as the continuous target >= 0."""
    target_series = synthetic_weather_df["actual_rainfall_mm"]
    assert target_series.name == "actual_rainfall_mm"
    stats = compute_target_statistics(target_series)
    assert stats["valid_count"] == 5
    assert stats["min"] >= 0.0
    assert stats["max"] == 40.0
    assert stats["mean"] == (8.0 + 10.0 + 0.0 + 40.0 + 0.0) / 5.0


# 2. Temporal ordering test
def test_temporal_ordering_and_feasibility(synthetic_weather_df):
    """Verifies chronological ordering and daily continuity detection."""
    feasibility = audit_historical_feasibility(synthetic_weather_df)
    assert feasibility["unique_dates_count"] == 3
    assert feasibility["is_daily_continuous"] is True
    assert feasibility["min_date_gap_days"] == 1
    assert feasibility["max_date_gap_days"] == 1

    # Single snapshot dataset should be marked non-continuous and lag infeasible
    snapshot_df = synthetic_weather_df.iloc[[0]].copy()
    snapshot_feasibility = audit_historical_feasibility(snapshot_df)
    assert snapshot_feasibility["is_daily_continuous"] is False
    assert snapshot_feasibility["lag_t1_feasible"] is False


# 3. Leakage detection test
def test_leakage_detection():
    """Verifies target and post-forecast fields are classified as forbidden features."""
    inventory = build_candidate_feature_inventory()
    inv_dict = {item["field"]: item for item in inventory}

    # actual_rainfall_mm must be forbidden as feature
    assert "actual_rainfall_mm" in inv_dict
    assert "FORBIDDEN" in inv_dict["actual_rainfall_mm"]["decision"]
    assert inv_dict["actual_rainfall_mm"]["availability_at_forecast_time"].startswith("Category C")

    # block_forecast_rainfall_mm must be allowed
    assert "block_forecast_rainfall_mm" in inv_dict
    assert "ALLOWED" in inv_dict["block_forecast_rainfall_mm"]["decision"]
    assert inv_dict["block_forecast_rainfall_mm"]["availability_at_forecast_time"].startswith("Category A")

    # raw panchayat_id must be forbidden from tree features to avoid memorization
    assert "panchayat_id" in inv_dict["panchayat_id (as raw integer or categorical)"]["field"]
    assert "FORBIDDEN" in inv_dict["panchayat_id (as raw integer or categorical)"]["decision"]


# 4. Training eligibility test
def test_training_eligibility(synthetic_weather_df):
    """Verifies row filter rules for target, forecast, coordinates, and lead_days."""
    res = evaluate_training_eligibility(synthetic_weather_df)
    assert res["eligible_rows"] == 5
    assert res["ineligible_rows"] == 0
    assert res["eligibility_rate_pct"] == 100.0

    # Introduce invalid conditions
    corrupted_df = synthetic_weather_df.copy()
    corrupted_df.loc[0, "actual_rainfall_mm"] = np.nan       # Null target
    corrupted_df.loc[1, "block_forecast_rainfall_mm"] = -1.0  # Negative forecast
    corrupted_df.loc[2, "panchayat_latitude"] = np.nan       # Missing coordinate
    corrupted_df.loc[3, "lead_days"] = -1                    # Negative lead horizon

    c_res = evaluate_training_eligibility(corrupted_df)
    assert c_res["eligible_rows"] == 1  # Only row 4 is valid
    assert c_res["ineligible_rows"] == 4
    assert c_res["rejection_breakdown"]["missing_or_negative_target"] == 1
    assert c_res["rejection_breakdown"]["missing_or_negative_block_forecast"] == 1
    assert c_res["rejection_breakdown"]["invalid_coordinates"] == 1
    assert c_res["rejection_breakdown"]["negative_lead_days"] == 1


# 5. Baseline MAE test
def test_baseline_mae():
    """Verifies baseline MAE calculation matches exact analytical value."""
    y_true = np.array([10.0, 20.0, 0.0, 50.0])
    y_pred = np.array([8.0, 25.0, 5.0, 40.0])
    # Absolute errors: |8-10|=2, |25-20|=5, |5-0|=5, |40-50|=10 -> mean = (2+5+5+10)/4 = 5.5
    metrics = compute_baseline_slice_metrics(y_true, y_pred)
    assert metrics["mae"] == 5.5
    assert metrics["count"] == 4


# 6. Baseline RMSE test
def test_baseline_rmse():
    """Verifies baseline RMSE calculation matches exact analytical value."""
    y_true = np.array([10.0, 20.0, 0.0, 50.0])
    y_pred = np.array([8.0, 25.0, 5.0, 40.0])
    # Squared errors: 2^2=4, 5^2=25, 5^2=25, (-10)^2=100 -> mean = 154 / 4 = 38.5 -> sqrt = 6.2048
    metrics = compute_baseline_slice_metrics(y_true, y_pred)
    expected_rmse = round(float(np.sqrt(38.5)), 4)
    assert metrics["rmse"] == expected_rmse
    # Bias: mean(y_pred - y_true) = (-2 + 5 + 5 - 10) / 4 = -2 / 4 = -0.5
    assert metrics["bias"] == -0.5


# 7. Missing-target handling test
def test_missing_target_handling():
    """Verifies null actual_rainfall_mm handling."""
    series_with_nulls = pd.Series([10.0, np.nan, 0.0, np.nan, 25.0])
    stats = compute_target_statistics(series_with_nulls)
    assert stats["total_count"] == 5
    assert stats["missing_count"] == 2
    assert stats["missing_pct"] == 40.0
    assert stats["valid_count"] == 3
    assert stats["zero_count"] == 1
    assert stats["nonzero_count"] == 2


# 8. Zero rainfall handling test
def test_zero_rainfall_handling(synthetic_weather_df):
    """Verifies zero rainfall records are recognized as verified dry days, not nulls."""
    stats = compute_target_statistics(synthetic_weather_df["actual_rainfall_mm"])
    assert stats["zero_count"] == 2
    assert stats["zero_pct"] == 40.0
    assert stats["missing_count"] == 0

    # Test baseline evaluation specifically on zero-rainfall slice
    baseline = compute_baseline_metrics(synthetic_weather_df)
    zero_slice = baseline["zero_rainfall_slice"]
    assert zero_slice["count"] == 2
    # In synthetic df: rows 2 and 4 have actual=0.0; forecasts are 2.0 and 0.0
    # Absolute errors: |2-0|=2, |0-0|=0 -> MAE = 1.0; Bias = +1.0
    assert zero_slice["mae"] == 1.0
    assert zero_slice["bias"] == 1.0


# 9. District independence test
def test_district_independence(tmp_path, synthetic_weather_df):
    """Verifies audit profiler executes correctly on arbitrary district data without hardcoding."""
    custom_district_df = synthetic_weather_df.copy()
    custom_district_df["district_name"] = "Kolhapur"
    custom_district_df["source_dataset"] = "kolhapur"

    mock_metadata = {
        "file_path": str(tmp_path / "canonical_kolhapur.parquet"),
        "file_size_bytes": 1024,
        "row_count": len(custom_district_df),
        "column_count": len(custom_district_df.columns),
        "columns": list(custom_district_df.columns),
        "dtypes": {col: str(dtype) for col, dtype in custom_district_df.dtypes.items()}
    }

    profile = profile_district(custom_district_df, mock_metadata, "Kolhapur")
    assert profile["district_name"] == "Kolhapur"
    assert profile["structural_metrics"]["total_rows"] == 5
    assert profile["structural_metrics"]["unique_districts"] == 1
    assert profile["training_eligibility"]["eligible_rows"] == 5

    import copy
    nashik_mock = copy.deepcopy(profile)
    nashik_mock["structural_metrics"]["rows_per_panchayat"]["max"] = 1
    nashik_mock["structural_metrics"]["lead_days_distribution"] = {0: 5}

    pune_mock = copy.deepcopy(profile)
    pune_mock["structural_metrics"]["rows_per_panchayat"]["max"] = 140
    pune_mock["structural_metrics"]["lead_days_distribution"] = {1: 5}

    status, warnings, blockers = determine_readiness_status(nashik_mock, pune_mock)
    assert status == "READY WITH WARNINGS"
    assert len(blockers) == 0
    assert len(warnings) >= 2
