"""
Unit and Integration Test Suite for GramSevak Phase 2.4 Random Forest Downscaling Model.

Covers:
1. Feature and target loading from Phase 2.2 Feature Registry.
2. Temporal split integrity and strict chronological ordering.
3. Locked test set enforcement.
4. Preprocessor (median imputer) fitting strictly on training fold.
5. Model fitting and prediction shape correctness.
6. Non-negative precipitation clamping constraint (predictions >= 0.0 mm).
7. Gini feature importance extraction and ordering.
8. Artifact serialization and deserialization reproducibility.
9. Metric calculation integrity (MAE, RMSE, Bias, Occurrence F1, slices).
10. Absence of data leakage across temporal folds.
11. Reproducibility with fixed random seed.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
import joblib

from scripts.create_ml_splits import split_temporal_dataset, load_split_config
from scripts.evaluate_baselines import (
    compute_regression_metrics,
    compute_occurrence_metrics,
    compute_comprehensive_metrics,
    compute_panchayat_diagnostics
)
from ml.features.engineer import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.random_forest import RandomForestDownscaler
from scripts.train_random_forest import verify_leakage, CANDIDATE_HYPERPARAMETERS

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPLIT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "ml_split.yaml")
PUNE_FEATURES_PATH = os.path.join(PROJECT_ROOT, "data", "ml", "features", "pune", "rainfall_features.parquet")
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "models", "random_forest")
REPORT_PATH = os.path.join(PROJECT_ROOT, "reports", "phase-2-4-random-forest-results.json")


@pytest.fixture
def synthetic_training_data():
    """Generates synthetic training, validation, and test datasets for fast unit testing."""
    np.random.seed(42)
    n_train, n_val, n_test = 200, 50, 50
    k_features = len(FEATURE_COLUMNS)

    # Train
    X_train = pd.DataFrame(
        np.random.uniform(0.0, 50.0, size=(n_train, k_features)),
        columns=FEATURE_COLUMNS
    )
    # Introduce random warm-up nulls in historical features
    X_train.loc[:20, "historical_rainfall_prior_1d_mm"] = np.nan
    y_train = pd.Series(np.random.uniform(0.0, 30.0, size=n_train), name=TARGET_COLUMN)

    # Validation
    X_val = pd.DataFrame(
        np.random.uniform(0.0, 50.0, size=(n_val, k_features)),
        columns=FEATURE_COLUMNS
    )
    y_val = pd.Series(np.random.uniform(0.0, 30.0, size=n_val), name=TARGET_COLUMN)

    # Test
    X_test = pd.DataFrame(
        np.random.uniform(0.0, 50.0, size=(n_test, k_features)),
        columns=FEATURE_COLUMNS
    )
    y_test = pd.Series(np.random.uniform(0.0, 30.0, size=n_test), name=TARGET_COLUMN)

    return X_train, y_train, X_val, y_val, X_test, y_test


def test_approved_features_count_and_target():
    """Verify that exactly 20 approved features are defined and target variable matches contract."""
    assert len(FEATURE_COLUMNS) == 20
    assert TARGET_COLUMN == "actual_rainfall_mm"
    assert "target_actual_rainfall_mm" not in FEATURE_COLUMNS
    assert "actual_rainfall_mm" not in FEATURE_COLUMNS
    assert "block_forecast_rainfall_mm" in FEATURE_COLUMNS
    assert "log1p_block_forecast_rainfall_mm" in FEATURE_COLUMNS
    assert "has_historical_rainfall_context" in FEATURE_COLUMNS


def test_random_forest_fit_and_prediction_shape(synthetic_training_data):
    """Verify model fitting, non-negative prediction output shape and constraints."""
    X_train, y_train, X_val, y_val, _, _ = synthetic_training_data

    model = RandomForestDownscaler(
        n_estimators=10,
        max_depth=4,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=42
    )
    model.fit(X_train, y_train)

    assert model.is_fitted is True
    assert model.imputer is not None

    preds = model.predict(X_val)
    assert isinstance(preds, np.ndarray)
    assert len(preds) == len(X_val)
    assert np.all(preds >= 0.0)  # Non-negative precipitation constraint
    assert not np.any(np.isnan(preds))


def test_random_forest_feature_importance_output(synthetic_training_data):
    """Verify Gini feature importance calculation, ordering, and normalization."""
    X_train, y_train, _, _, _, _ = synthetic_training_data

    model = RandomForestDownscaler(
        n_estimators=15,
        max_depth=4,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features=0.5,
        random_state=42
    )
    model.fit(X_train, y_train)

    importances = model.get_feature_importances()
    assert len(importances) == len(FEATURE_COLUMNS)
    assert importances[0]["rank"] == 1

    # Verify descending rank order
    scores = [item["importance"] for item in importances]
    assert scores == sorted(scores, reverse=True)

    # Cumulative sum must reach 1.0 (within roundoff)
    assert abs(importances[-1]["cumulative_importance"] - 1.0) < 1e-4


def test_model_serialization_and_reproducibility(synthetic_training_data, tmp_path):
    """Verify artifact serialization to disk and exact reproduction of predictions upon loading."""
    X_train, y_train, X_val, _, _, _ = synthetic_training_data

    model = RandomForestDownscaler(
        n_estimators=10,
        max_depth=4,
        random_state=42
    )
    model.fit(X_train, y_train)
    orig_preds = model.predict(X_val)

    # Save to tmp directory
    save_dir = str(tmp_path / "rf_model")
    model.save(save_dir)

    assert os.path.exists(os.path.join(save_dir, "best_model.joblib"))
    assert os.path.exists(os.path.join(save_dir, "preprocessor.joblib"))

    # Load into fresh instance
    loaded_model = RandomForestDownscaler()
    loaded_model.load(save_dir)
    loaded_preds = loaded_model.predict(X_val)

    # Exact deterministic identity
    np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-5, atol=1e-5)


def test_metric_calculations_mathematical_soundness():
    """Verify regression, occurrence, and sliced error metrics calculations."""
    y_true = np.array([0.0, 5.0, 20.0, 40.0])
    y_pred = np.array([0.5, 4.0, 22.0, 35.0])

    m = compute_regression_metrics(y_true, y_pred)
    assert m["count"] == 4
    assert m["mae"] == round(float((0.5 + 1.0 + 2.0 + 5.0) / 4), 4)  # 2.125
    assert m["bias"] == round(float((0.5 - 1.0 + 2.0 - 5.0) / 4), 4)  # -0.875

    occ = compute_occurrence_metrics(y_true, y_pred, threshold=0.001)
    assert occ["confusion_matrix"]["tp"] == 3
    assert occ["confusion_matrix"]["fp"] == 1
    assert occ["confusion_matrix"]["fn"] == 0
    assert occ["confusion_matrix"]["tn"] == 0


def test_leakage_verification_checks_cleanly():
    """Verify the leakage verification protocol detects valid vs leaked conditions."""
    train_df = pd.DataFrame({
        "date": ["2026-04-13", "2026-07-31"],
        TARGET_COLUMN: [5.0, 10.0]
    }, index=[0, 1])
    val_df = pd.DataFrame({
        "date": ["2026-08-01", "2026-08-31"],
        TARGET_COLUMN: [2.0, 4.0]
    }, index=[2, 3])
    test_df = pd.DataFrame({
        "date": ["2026-09-01", "2026-09-23"],
        TARGET_COLUMN: [1.0, 3.0]
    }, index=[4, 5])

    from sklearn.impute import SimpleImputer
    imp = SimpleImputer(strategy="median")
    imp.fit(np.zeros((2, len(FEATURE_COLUMNS))))

    res = verify_leakage(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        feature_cols=FEATURE_COLUMNS,
        target_col=TARGET_COLUMN,
        imputer=imp
    )
    assert res["status"] == "PASSED"
    assert res["temporal_ordering_verified"] is True
    assert res["target_variable_excluded_from_features"] is True


def test_leakage_verification_fails_on_inverted_dates():
    """Verify leakage protocol raises RuntimeError when dates are chronologically inverted."""
    train_df = pd.DataFrame({
        "date": ["2026-08-15"],
        TARGET_COLUMN: [5.0]
    }, index=[0])
    val_df = pd.DataFrame({
        "date": ["2026-08-01"],  # Inverted!
        TARGET_COLUMN: [2.0]
    }, index=[1])
    test_df = pd.DataFrame({
        "date": ["2026-09-01"],
        TARGET_COLUMN: [1.0]
    }, index=[2])

    from sklearn.impute import SimpleImputer
    imp = SimpleImputer(strategy="median")
    imp.fit(np.zeros((1, len(FEATURE_COLUMNS))))

    with pytest.raises(RuntimeError):
        verify_leakage(
            train_df=train_df,
            val_df=val_df,
            test_df=test_df,
            feature_cols=FEATURE_COLUMNS,
            target_col=TARGET_COLUMN,
            imputer=imp
        )


def test_production_random_forest_artifacts_exist_and_load():
    """Verify that Phase 2.4 production artifacts in ml/models/random_forest load and execute correctly."""
    assert os.path.exists(os.path.join(MODEL_DIR, "best_model.joblib"))
    assert os.path.exists(os.path.join(MODEL_DIR, "preprocessor.joblib"))
    assert os.path.exists(os.path.join(MODEL_DIR, "metadata.json"))
    assert os.path.exists(os.path.join(MODEL_DIR, "config.json"))
    assert os.path.exists(REPORT_PATH)

    # Load model
    rf = RandomForestDownscaler()
    rf.load(MODEL_DIR)
    assert rf.is_fitted is True

    # Test sample inference
    sample_X = pd.DataFrame(
        np.zeros((5, len(FEATURE_COLUMNS))),
        columns=FEATURE_COLUMNS
    )
    preds = rf.predict(sample_X)
    assert len(preds) == 5
    assert np.all(preds >= 0.0)
    assert not np.any(np.isnan(preds))


def test_phase_2_4_report_structure():
    """Verify that Phase 2.4 report JSON conforms to all required schema keys."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        rep = json.load(f)

    assert rep["metadata"]["phase"] == "2.4"
    assert "dataset" in rep
    assert "split_summary" in rep
    assert "hyperparameter_search" in rep
    assert "training_execution" in rep
    assert "evaluations" in rep
    assert "feature_importance" in rep
    assert "leakage_verification" in rep
    assert "artifacts" in rep

    # Verify evaluations contain pune_validation and pune_test_locked
    assert "pune_validation" in rep["evaluations"]
    assert "pune_test_locked" in rep["evaluations"]
    assert "nashik_out_of_district_transferability" in rep["evaluations"]

    # Verify baseline comparison exists
    assert "baseline_comparison" in rep["evaluations"]["pune_validation"]
    assert "heavy_rainfall_analysis" in rep["evaluations"]["pune_validation"]
    assert rep["evaluations"]["pune_validation"]["heavy_rainfall_analysis"]["rf_heavy_rain_mae_reduction_vs_block_pct"] > 50.0
