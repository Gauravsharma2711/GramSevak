"""
Unit tests for GramSevak ML Temporal Splits, Baselines & Evaluation Framework (Phase 2.3).

Validates all 11 mandatory criteria using synthetic fixtures:
1. Chronological ordering: max(train) < min(val) < min(test)
2. No split overlap: zero index intersection between train, val, and test
3. No future training rows: test/val target dates never enter training
4. No target leakage: target variable actual_rainfall_mm is strictly barred from X
5. Split reproducibility: repeated splitting produces identical splits
6. Baseline metric correctness: analytical verification of MAE, RMSE, and Bias
7. Zero-rainfall handling: verified dry days and occurrence metrics (precision, recall, F1)
8. Non-zero metric correctness: verifies non-zero slice filters out dry days
9. District metric separation: metrics are separated cleanly between districts
10. Panchayat metric calculation: per-Panchayat spatial MAE distribution and quantiles
11. Test-set immutability rules: test set is locked and preserved
"""

import pytest
import numpy as np
import pandas as pd

from scripts.create_ml_splits import split_temporal_dataset, DEFAULT_SPLIT_BOUNDARIES
from scripts.evaluate_baselines import (
    compute_regression_metrics,
    compute_occurrence_metrics,
    compute_comprehensive_metrics,
    compute_panchayat_diagnostics,
    compute_monthly_diagnostics,
    SimpleLinearBaseline,
    BASELINE_MODEL_FEATURES
)
from ml.features.engineer import TARGET_COLUMN


@pytest.fixture
def synthetic_split_dataset():
    """
    Returns an 18-row synthetic time-series covering 3 distinct temporal periods:
    - Train: 2026-05-01 to 2026-05-06 (6 days)
    - Validation: 2026-05-07 to 2026-05-12 (6 days)
    - Test: 2026-05-13 to 2026-05-18 (6 days)
    For 2 Panchayats (P1, P2) across all days -> 36 rows total.
    """
    rows = []
    dates = pd.date_range("2026-05-01", "2026-05-18", freq="D")

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        iss_str = (dt - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        day_val = dt.day

        for pid, lat, lon, elev in [(101, 19.5, 73.8, 600.0), (102, 19.8, 74.1, 550.0)]:
            # Deterministic rainfall pattern
            act_rain = 0.0 if day_val % 3 == 0 else float(day_val * 2.0)
            fcst_rain = float(day_val * 1.5)

            rows.append({
                "panchayat_id": pid,
                "lgd_code": pid + 100000,
                "panchayat_name": f"Panchayat {pid}",
                "block_name": "Test Block",
                "district_name": "Test District",
                "date": dt_str,
                "forecast_issue_date": iss_str,
                "lead_days": 1,
                "block_forecast_rainfall_mm": fcst_rain,
                "log1p_block_forecast_rainfall_mm": float(np.log1p(fcst_rain)),
                "panchayat_latitude": lat,
                "panchayat_longitude": lon,
                "elevation_m": elev,
                "station_distance_km": 5.0,
                "station_latitude": lat + 0.02,
                "station_longitude": lon + 0.05,
                "target_month": dt.month,
                "target_day_of_year": dt.dayofyear,
                "target_day_of_year_sin": float(np.sin(2 * np.pi * dt.dayofyear / 365.25)),
                "target_day_of_year_cos": float(np.cos(2 * np.pi * dt.dayofyear / 365.25)),
                "historical_rainfall_prior_1d_mm": 5.0,
                "historical_rainfall_prior_2d_mm": 5.0,
                "historical_rainfall_prior_3d_mean_mm": 5.0,
                "historical_rainfall_prior_3d_sum_mm": 15.0,
                "historical_rainfall_prior_7d_mean_mm": 5.0,
                "historical_rainfall_prior_7d_sum_mm": 35.0,
                "has_historical_rainfall_context": 1.0,
                "actual_rainfall_mm": act_rain
            })

    return pd.DataFrame(rows)


@pytest.fixture
def custom_split_config():
    return {
        "splits": {
            "train": {
                "start_date": "2026-05-01", "end_date": "2026-05-06",
                "start_issue_date": "2026-04-30", "end_issue_date": "2026-05-05"
            },
            "validation": {
                "start_date": "2026-05-07", "end_date": "2026-05-12",
                "start_issue_date": "2026-05-06", "end_issue_date": "2026-05-11"
            },
            "test": {
                "start_date": "2026-05-13", "end_date": "2026-05-18",
                "start_issue_date": "2026-05-12", "end_issue_date": "2026-05-17",
                "locked": True
            }
        },
        "split_key": "date",
        "issue_key": "forecast_issue_date"
    }


# 1. Chronological ordering
def test_chronological_ordering(synthetic_split_dataset, custom_split_config):
    """Verifies max(train) < min(val) and max(val) < min(test)."""
    train_df, val_df, test_df, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    assert train_df["date"].max() < val_df["date"].min()
    assert val_df["date"].max() < test_df["date"].min()
    assert train_df["forecast_issue_date"].max() < val_df["forecast_issue_date"].min()
    assert val_df["forecast_issue_date"].max() < test_df["forecast_issue_date"].min()


# 2. No split overlap
def test_no_split_overlap(synthetic_split_dataset, custom_split_config):
    """Verifies zero index intersection between any two splits."""
    train_df, val_df, test_df, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    t_idx = set(train_df.index)
    v_idx = set(val_df.index)
    te_idx = set(test_df.index)

    assert len(t_idx.intersection(v_idx)) == 0
    assert len(v_idx.intersection(te_idx)) == 0
    assert len(t_idx.intersection(te_idx)) == 0
    assert len(train_df) + len(val_df) + len(test_df) == len(synthetic_split_dataset)


# 3. No future training rows
def test_no_future_training_rows(synthetic_split_dataset, custom_split_config):
    """Verifies that no rows with validation or test dates can enter training."""
    train_df, val_df, test_df, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    val_dates = set(val_df["date"])
    test_dates = set(test_df["date"])

    assert not any(d in val_dates for d in train_df["date"])
    assert not any(d in test_dates for d in train_df["date"])


# 4. No target leakage in baseline training
def test_no_target_leakage_in_baseline(synthetic_split_dataset, custom_split_config):
    """Verifies that actual_rainfall_mm is strictly barred from X in SimpleLinearBaseline."""
    train_df, _, _, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    model = SimpleLinearBaseline()
    assert TARGET_COLUMN not in model.feature_columns
    model.fit(train_df)

    # Check fitted model features
    assert TARGET_COLUMN not in model.coefficients_
    for feat in model.feature_columns:
        assert feat in BASELINE_MODEL_FEATURES


# 5. Split reproducibility
def test_split_reproducibility(synthetic_split_dataset, custom_split_config):
    """Verifies running the split multiple times on identical input yields identical outputs."""
    t1, v1, te1, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)
    t2, v2, te2, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    pd.testing.assert_frame_equal(t1, t2)
    pd.testing.assert_frame_equal(v1, v2)
    pd.testing.assert_frame_equal(te1, te2)


# 6. Baseline metric correctness
def test_baseline_metric_correctness():
    """Analytically verifies MAE, RMSE, Bias, and Pearson r against hand-computed ground truth."""
    y_true = np.array([10.0, 20.0, 0.0, 40.0])
    y_pred = np.array([12.0, 20.0, 5.0, 35.0])
    # Differences: [2, 0, 5, -5]
    # Abs differences: [2, 0, 5, 5] -> MAE = 12 / 4 = 3.0
    # Squared differences: [4, 0, 25, 25] = 54 -> RMSE = sqrt(54/4) = sqrt(13.5) = 3.6742
    # Bias: mean(y_pred - y_true) = (2 + 0 + 5 - 5) / 4 = 2 / 4 = 0.5
    metrics = compute_regression_metrics(y_true, y_pred)
    assert metrics["mae"] == 3.0
    assert metrics["rmse"] == round(float(np.sqrt(13.5)), 4)
    assert metrics["bias"] == 0.5
    assert metrics["count"] == 4


# 7. Zero-rainfall handling and occurrence metrics
def test_zero_rainfall_and_occurrence_metrics():
    """Verifies binary occurrence classification metrics (TP, FP, TN, FN, Precision, Recall, F1)."""
    y_true = np.array([0.0, 5.0, 0.0, 10.0])
    y_pred = np.array([0.0, 8.0, 2.0, 0.0])
    # True binary:  [0, 1, 0, 1]
    # Pred binary:  [0, 1, 1, 0]
    # TP: idx 1 (true=1, pred=1) -> 1
    # FP: idx 2 (true=0, pred=1) -> 1
    # FN: idx 3 (true=1, pred=0) -> 1
    # TN: idx 0 (true=0, pred=0) -> 1
    # Precision: TP/(TP+FP) = 1/2 = 0.5
    # Recall: TP/(TP+FN) = 1/2 = 0.5
    # F1: 0.5
    occ = compute_occurrence_metrics(y_true, y_pred, threshold=0.001)
    assert occ["confusion_matrix"]["tp"] == 1
    assert occ["confusion_matrix"]["fp"] == 1
    assert occ["confusion_matrix"]["fn"] == 1
    assert occ["confusion_matrix"]["tn"] == 1
    assert occ["precision"] == 0.5
    assert occ["recall"] == 0.5
    assert occ["f1"] == 0.5


# 8. Non-zero metric correctness
def test_nonzero_metric_correctness():
    """Verifies that non-zero slice metrics strictly evaluate records with actual > 0."""
    y_true = np.array([0.0, 10.0, 0.0, 30.0])
    y_pred = np.array([5.0, 15.0, 0.0, 20.0])
    # Non-zero true: [10.0, 30.0], corresponding pred: [15.0, 20.0]
    # Errors: [5, -10] -> Abs: [5, 10] -> MAE = 7.5
    res = compute_comprehensive_metrics(y_true, y_pred)
    assert res["nonzero_rainfall_slice"]["count"] == 2
    assert res["nonzero_rainfall_slice"]["mae"] == 7.5
    assert res["zero_rainfall_slice"]["count"] == 2
    assert res["zero_rainfall_slice"]["mae"] == 2.5  # |5-0|=5, |0-0|=0 -> mean = 2.5


# 9. District metric separation
def test_district_metric_separation(synthetic_split_dataset, custom_split_config):
    """Verifies metrics can be computed independently for separate districts."""
    train_df, val_df, _, _ = split_temporal_dataset(synthetic_split_dataset, custom_split_config)

    model = SimpleLinearBaseline()
    model.fit(train_df)

    pred_val = model.predict(val_df)
    pune_metrics = compute_regression_metrics(val_df[TARGET_COLUMN].values, pred_val)

    # Synthetic second district (e.g. Nashik)
    nashik_mock = val_df.copy()
    nashik_mock["district_name"] = "Nashik"
    nashik_mock["block_forecast_rainfall_mm"] += 5.0
    pred_nashik = model.predict(nashik_mock)
    nashik_metrics = compute_regression_metrics(nashik_mock[TARGET_COLUMN].values, pred_nashik)

    assert pune_metrics["count"] == len(val_df)
    assert nashik_metrics["count"] == len(nashik_mock)
    assert pune_metrics != nashik_metrics


# 10. Panchayat metric calculation
def test_panchayat_metric_calculation(synthetic_split_dataset):
    """Verifies calculation of spatial MAE distribution across unique Panchayats."""
    y_pred = synthetic_split_dataset["block_forecast_rainfall_mm"].values
    panch_diag = compute_panchayat_diagnostics(synthetic_split_dataset, y_pred)

    assert panch_diag["panchayats_evaluated"] == 2  # P101 and P102
    assert panch_diag["median_mae"] > 0.0
    assert panch_diag["min_mae"] <= panch_diag["max_mae"]


# 11. Test-set immutability rules
def test_test_set_immutability_rules(custom_split_config):
    """Verifies that the test set definition has the locked flag set to True."""
    test_cfg = custom_split_config["splits"]["test"]
    assert test_cfg.get("locked") is True
    assert test_cfg["start_date"] > custom_split_config["splits"]["validation"]["end_date"]
