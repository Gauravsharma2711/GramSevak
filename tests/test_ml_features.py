"""
Unit tests for GramSevak ML Feature Engineering & Leakage Prevention (Phase 2.2).

Validates all 8 mandatory leakage and feature-engineering criteria:
1. Target column cannot appear in feature matrix X
2. Future target-date rainfall cannot enter features
3. Future observations cannot enter rolling history
4. Historical features strictly respect forecast issue date (t <= issue_date - 1d)
5. Feature generation preserves row identity and alignment
6. Feature generation does not mutate raw input data
7. Repeated feature generation produces deterministic identical output
8. Unseen/future Panchayats do not require target encoding
9. Missing historical data / warm-up period handling (returns NaN + context indicator = 0.0)
10. District-independent execution on arbitrary district schemas
"""

import pytest
import numpy as np
import pandas as pd

from ml.features.engineer import (
    FEATURE_COLUMNS,
    METADATA_COLUMNS,
    TARGET_COLUMN,
    build_feature_dataframe,
    extract_features,
    compute_historical_rainfall_features,
    compute_calendar_features,
    compute_forecast_transformations,
    compute_lead_days
)


@pytest.fixture
def synthetic_timeseries_weather_df():
    """
    Returns a controlled 6-day synthetic time series for Panchayat 999.
    Target dates: 2026-07-10 to 2026-07-15
    Lead days: 1
    Forecast issue dates: 2026-07-09 to 2026-07-14
    """
    rows = []
    dates = [
        ("2026-07-10", "2026-07-09", 5.0, 10.0),
        ("2026-07-11", "2026-07-10", 8.0, 20.0),
        ("2026-07-12", "2026-07-11", 12.0, 15.0),
        ("2026-07-13", "2026-07-12", 0.0, 0.0),
        ("2026-07-14", "2026-07-13", 4.0, 5.0),
        ("2026-07-15", "2026-07-14", 25.0, 30.0),
    ]
    for i, (tgt_d, iss_d, fcst_rain, act_rain) in enumerate(dates):
        rows.append({
            "panchayat_id": 999,
            "lgd_code": 199999,
            "panchayat_name": "Test Panchayat",
            "block_name": "Test Block",
            "district_name": "Test District",
            "state_name": "Maharashtra",
            "panchayat_latitude": 19.50,
            "panchayat_longitude": 73.80,
            "elevation_m": 600.0,
            "date": tgt_d,
            "forecast_issue_date": iss_d,
            "lead_days": 1,
            "block_forecast_rainfall_mm": fcst_rain,
            "station_id": "Station 99",
            "station_latitude": 19.52,
            "station_longitude": 73.85,
            "station_distance_km": 4.5,
            "actual_rainfall_mm": act_rain,
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": i,
            "source_panchayat_id": "P_999"
        })
    return pd.DataFrame(rows)


# 1. Target column cannot appear in feature matrix
def test_target_column_not_in_features(synthetic_timeseries_weather_df):
    """Verifies actual_rainfall_mm is strictly absent from feature matrix X."""
    _, X, y = build_feature_dataframe(synthetic_timeseries_weather_df, include_target=True)
    assert TARGET_COLUMN not in X.columns
    assert TARGET_COLUMN == "actual_rainfall_mm"
    assert len(X.columns) == len(FEATURE_COLUMNS)
    assert y is not None
    assert len(y) == len(X)
    assert y.name == TARGET_COLUMN


# 2. Future target-date rainfall cannot enter features
def test_future_target_date_rainfall_cannot_enter_features(synthetic_timeseries_weather_df):
    """
    Verifies altering target-day actual_rainfall_mm has ZERO effect on features X.
    """
    _, X_baseline, _ = build_feature_dataframe(synthetic_timeseries_weather_df)

    # Mutate actual_rainfall_mm on target day 2026-07-15 from 30.0 mm to 999.0 mm
    mutated_df = synthetic_timeseries_weather_df.copy()
    mutated_df.loc[mutated_df["date"] == "2026-07-15", "actual_rainfall_mm"] = 999.0

    _, X_mutated, _ = build_feature_dataframe(mutated_df)

    # Row for 2026-07-15 in X must be identical between baseline and mutated
    row_idx = mutated_df.index[mutated_df["date"] == "2026-07-15"][0]
    pd.testing.assert_series_equal(
        X_baseline.loc[row_idx],
        X_mutated.loc[row_idx],
        check_names=True
    )


# 3. Future observations cannot enter rolling history
def test_future_observations_cannot_enter_rolling_history(synthetic_timeseries_weather_df):
    """
    Verifies that observations after the forecast issuance date cannot enter rolling 3d/7d features.
    """
    # For target date 2026-07-13, forecast_issue_date is 2026-07-12.
    # The latest allowable historical observation is 2026-07-11 (forecast_issue_date - 1 day).
    # Mutating actual rainfall on 2026-07-12, 2026-07-13, 2026-07-14, 2026-07-15 MUST NOT
    # change the rolling historical features for target date 2026-07-13.
    _, X_base, _ = build_feature_dataframe(synthetic_timeseries_weather_df)

    mutated_df = synthetic_timeseries_weather_df.copy()
    mutated_df.loc[mutated_df["date"] >= "2026-07-12", "actual_rainfall_mm"] = 888.0

    _, X_mut, _ = build_feature_dataframe(mutated_df)

    idx_13 = synthetic_timeseries_weather_df.index[synthetic_timeseries_weather_df["date"] == "2026-07-13"][0]
    # For target 2026-07-13 (issue 2026-07-12), prior 1d rainfall is observation from 2026-07-11 (20.0 mm).
    # Since 2026-07-12 was mutated to 888.0, prior 1d must remain 20.0 and NOT 888.0.
    assert X_base.loc[idx_13, "historical_rainfall_prior_1d_mm"] == 20.0
    assert X_mut.loc[idx_13, "historical_rainfall_prior_1d_mm"] == 20.0
    assert X_base.loc[idx_13, "historical_rainfall_prior_3d_mean_mm"] == X_mut.loc[idx_13, "historical_rainfall_prior_3d_mean_mm"]


# 4. Historical features strictly respect forecast issue date
def test_historical_features_respect_forecast_issue_date():
    """
    Replicates the exact scenario specified in Phase 2.2 Section 12:
    Forecast:
      issue = 2026-07-10
      target = 2026-07-11
    Valid prior history:
      2026-07-09 rainfall
      2026-07-08 rainfall
      2026-07-07 rainfall
    Invalid / forbidden:
      2026-07-10 rainfall
      2026-07-11 rainfall
      2026-07-12 rainfall
    """
    days = [
        ("2026-07-07", "2026-07-06", 10.0),
        ("2026-07-08", "2026-07-07", 20.0),
        ("2026-07-09", "2026-07-08", 30.0),
        ("2026-07-10", "2026-07-09", 40.0),  # Observation on issue day
        ("2026-07-11", "2026-07-10", 50.0),  # Target day
        ("2026-07-12", "2026-07-11", 60.0),  # Future day
    ]
    df_list = []
    for d, iss, rain in days:
        df_list.append({
            "panchayat_id": 501,
            "lgd_code": 150001,
            "panchayat_name": "Section 12 Test",
            "block_name": "Block Test",
            "district_name": "District Test",
            "panchayat_latitude": 19.5,
            "panchayat_longitude": 73.8,
            "elevation_m": 500.0,
            "date": d,
            "forecast_issue_date": iss,
            "lead_days": 1,
            "block_forecast_rainfall_mm": 5.0,
            "station_id": "AWS 1",
            "station_latitude": 19.5,
            "station_longitude": 73.8,
            "station_distance_km": 2.0,
            "actual_rainfall_mm": rain,
            "source_dataset": "test",
            "source_file": "test.csv",
            "source_row_id": 0,
            "source_panchayat_id": "P_501"
        })
    test_df = pd.DataFrame(df_list)

    _, X, y = build_feature_dataframe(test_df)

    row_11 = test_df.index[test_df["date"] == "2026-07-11"][0]
    # For target 2026-07-11, issue date is 2026-07-10.
    # Latest valid observation is 2026-07-09 (30.0 mm).
    # It must NOT be 2026-07-10 (40.0 mm) or 2026-07-11 (50.0 mm).
    assert X.loc[row_11, "historical_rainfall_prior_1d_mm"] == 30.0
    assert X.loc[row_11, "historical_rainfall_prior_2d_mm"] == 20.0
    # 3-day mean over [2026-07-07, 2026-07-08, 2026-07-09]: (10 + 20 + 30) / 3 = 20.0
    assert X.loc[row_11, "historical_rainfall_prior_3d_mean_mm"] == 20.0
    assert X.loc[row_11, "historical_rainfall_prior_3d_sum_mm"] == 60.0


# 5. Feature generation preserves row identity
def test_feature_generation_preserves_row_identity(synthetic_timeseries_weather_df):
    """Verifies that output features X and metadata match input row count and indices exactly."""
    meta, X, y = build_feature_dataframe(synthetic_timeseries_weather_df)
    assert len(meta) == len(synthetic_timeseries_weather_df)
    assert len(X) == len(synthetic_timeseries_weather_df)
    assert len(y) == len(synthetic_timeseries_weather_df)
    assert (meta.index == synthetic_timeseries_weather_df.index).all()
    assert (X.index == synthetic_timeseries_weather_df.index).all()


# 6. Feature generation does not change raw data
def test_feature_generation_does_not_mutate_raw_data(synthetic_timeseries_weather_df):
    """Verifies input DataFrame is not mutated in-place during feature engineering."""
    original_df = synthetic_timeseries_weather_df.copy(deep=True)
    _ = build_feature_dataframe(synthetic_timeseries_weather_df)
    pd.testing.assert_frame_equal(synthetic_timeseries_weather_df, original_df)


# 7. Repeated feature generation is deterministic
def test_repeated_feature_generation_is_deterministic(synthetic_timeseries_weather_df):
    """Verifies running feature engineering multiple times yields identical bit-for-bit results."""
    meta1, X1, y1 = build_feature_dataframe(synthetic_timeseries_weather_df)
    meta2, X2, y2 = build_feature_dataframe(synthetic_timeseries_weather_df)
    pd.testing.assert_frame_equal(meta1, meta2)
    pd.testing.assert_frame_equal(X1, X2)
    pd.testing.assert_series_equal(y1, y2)


# 8. Unseen/future Panchayats do not require target encoding
def test_unseen_panchayats_do_not_require_target_encoding(synthetic_timeseries_weather_df):
    """
    Verifies that novel/unseen Panchayat IDs process successfully without out-of-vocabulary crashes
    because spatial features rely solely on continuous lat/lon/elevation coordinates.
    """
    unseen_df = synthetic_timeseries_weather_df.copy()
    unseen_df["panchayat_id"] = 8888888  # Completely new unseen ID
    unseen_df["panchayat_name"] = "Brand New Village"

    meta, X, y = build_feature_dataframe(unseen_df)
    assert len(X) == len(unseen_df)
    assert "panchayat_id" not in X.columns
    assert "panchayat_name" not in X.columns
    assert X["panchayat_latitude"].notna().all()
    assert X["panchayat_longitude"].notna().all()


# 9. Missing historical data handling (warm-up window)
def test_missing_history_handling(synthetic_timeseries_weather_df):
    """
    Verifies that early records in the warm-up window have NaN historical features
    and has_historical_rainfall_context set to 0.0.
    """
    _, X, _ = build_feature_dataframe(synthetic_timeseries_weather_df)

    # First row (2026-07-10, issue 2026-07-09):
    # Lookup date is 2026-07-08, which does not exist in synthetic_timeseries_weather_df.
    assert pd.isna(X.loc[0, "historical_rainfall_prior_1d_mm"])
    assert pd.isna(X.loc[0, "historical_rainfall_prior_3d_mean_mm"])
    assert X.loc[0, "has_historical_rainfall_context"] == 0.0

    # Once history is accumulated (e.g. row 4 on 2026-07-14), context is 1.0
    assert X.loc[4, "has_historical_rainfall_context"] == 1.0
    assert pd.notna(X.loc[4, "historical_rainfall_prior_1d_mm"])


# 10. District independence test
def test_district_independence(synthetic_timeseries_weather_df):
    """Verifies feature pipeline executes seamlessly on arbitrary district names."""
    custom_df = synthetic_timeseries_weather_df.copy()
    custom_df["district_name"] = "Kolhapur"
    custom_df["source_dataset"] = "kolhapur"

    meta, X, y = build_feature_dataframe(custom_df)
    assert meta["district_name"].iloc[0] == "Kolhapur"
    assert len(X) == len(custom_df)
    assert len(X.columns) == len(FEATURE_COLUMNS)
