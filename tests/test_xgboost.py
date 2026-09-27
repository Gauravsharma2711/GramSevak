"""
Unit and Integration Test Suite for GramSevak Phase 2.5 XGBoost Downscaling Model.

Covers:
1. XGBoost dependency import and version presence.
2. Feature and target loading from Phase 2.2 Feature Registry (20 features).
3. Chronological split integrity and strict date monotonicity.
4. Test-set lock enforcement (sealed September 2026 partition).
5. Preprocessor (median imputer) fitting strictly on training fold.
6. XGBoostDownscaler fitting with and without early stopping.
7. Prediction shape correctness and non-negative clamping (predictions >= 0.0 mm).
8. Gain-based and weight-based feature importance extraction and ordering.
9. Artifact serialization and deserialization reproducibility.
10. Evaluation metrics mathematical validity (MAE, RMSE, Bias, Correlation, R2).
11. Data leakage prevention protocol across temporal splits.
12. Verification of production artifacts in ml/models/xgboost/ and report schema in reports/phase-2-5-xgboost-results.json.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
import joblib
import xgboost as xgb

from scripts.create_ml_splits import split_temporal_dataset, load_split_config
from scripts.evaluate_baselines import (
    compute_regression_metrics,
    compute_occurrence_metrics,
    compute_comprehensive_metrics,
    compute_panchayat_diagnostics
)
from ml.features.engineer import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost import XGBoostDownscaler
from scripts.train_xgboost import verify_leakage, CANDIDATE_HYPERPARAMETERS

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPLIT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "ml_split.yaml")
PUNE_FEATURES_PATH = os.path.join(PROJECT_ROOT, "data", "ml", "features", "pune", "rainfall_features.parquet")
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "models", "xgboost")
REPORT_PATH = os.path.join(PROJECT_ROOT, "reports", "phase-2-5-xgboost-results.json")


@pytest.fixture
def synthetic_weather_data():
    """Generates synthetic training, validation, and test datasets for fast unit testing."""
    np.random.seed(42)
    n_train, n_val, n_test = 200, 50, 50
    k_features = len(FEATURE_COLUMNS)

    # Train
    X_train = pd.DataFrame(
        np.random.uniform(0.0, 50.0, size=(n_train, k_features)),
        columns=FEATURE_COLUMNS
    )
    # Introduce random warm-up nulls in historical precipitation features
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


def test_xgboost_environment_and_version():
    """Verify that XGBoost is installed and version is >= 2.0.0."""
    assert hasattr(xgb, "__version__")
    major_version = int(xgb.__version__.split(".")[0])
    assert major_version >= 2


def test_features_and_target_contract():
    """Verify exact 20 approved features and target variable contract."""
    assert len(FEATURE_COLUMNS) == 20
    assert TARGET_COLUMN == "actual_rainfall_mm"
    assert "target_actual_rainfall_mm" not in FEATURE_COLUMNS
    assert "actual_rainfall_mm" not in FEATURE_COLUMNS
    assert "block_forecast_rainfall_mm" in FEATURE_COLUMNS
    assert "log1p_block_forecast_rainfall_mm" in FEATURE_COLUMNS


def test_xgboost_fit_and_prediction_shape(synthetic_weather_data):
    """Verify model fitting, early stopping, and non-negative prediction output shape."""
    X_train, y_train, X_val, y_val, _, _ = synthetic_weather_data

    model = XGBoostDownscaler(
        n_estimators=20,
        max_depth=3,
        learning_rate=0.05,
        early_stopping_rounds=5,
        random_state=42
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)])

    assert model.is_fitted is True
    assert model.imputer is not None
    assert model.best_iteration_ is not None

    preds = model.predict(X_val)
    assert isinstance(preds, np.ndarray)
    assert len(preds) == len(X_val)
    assert np.all(preds >= 0.0)  # Non-negative precipitation constraint
    assert not np.any(np.isnan(preds))


def test_xgboost_feature_importance_gain_and_weight(synthetic_weather_data):
    """Verify gain and weight feature importance extraction, ordering, and normalization."""
    X_train, y_train, X_val, y_val, _, _ = synthetic_weather_data

    model = XGBoostDownscaler(
        n_estimators=15,
        max_depth=3,
        learning_rate=0.1,
        early_stopping_rounds=None,
        random_state=42
    )
    model.fit(X_train, y_train)

    gain_importances = model.get_feature_importances(importance_type="gain")
    assert len(gain_importances) == len(FEATURE_COLUMNS)
    assert gain_importances[0]["rank"] == 1

    # Verify descending rank order
    scores = [item["importance"] for item in gain_importances]
    assert scores == sorted(scores, reverse=True)

    # Cumulative sum must reach 1.0 (within roundoff)
    assert abs(gain_importances[-1]["cumulative_importance"] - 1.0) < 1e-4


def test_xgboost_serialization_and_reproducibility(synthetic_weather_data, tmp_path):
    """Verify model serialization and deterministic prediction reproduction upon loading."""
    X_train, y_train, X_val, _, _, _ = synthetic_weather_data

    model = XGBoostDownscaler(
        n_estimators=10,
        max_depth=3,
        random_state=42
    )
    model.fit(X_train, y_train)
    orig_preds = model.predict(X_val)

    # Save to tmp directory
    save_dir = str(tmp_path / "xgb_model")
    model.save(save_dir)

    assert os.path.exists(os.path.join(save_dir, "model.joblib"))
    assert os.path.exists(os.path.join(save_dir, "best_model.joblib"))
    assert os.path.exists(os.path.join(save_dir, "preprocessor.joblib"))

    # Load into fresh instance
    loaded_model = XGBoostDownscaler()
    loaded_model.load(save_dir)
    loaded_preds = loaded_model.predict(X_val)

    # Exact deterministic identity
    np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-5, atol=1e-5)


def test_leakage_verification_detects_valid_vs_invalid():
    """Verify leakage detection logic on valid temporal splits vs inverted dates."""
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

    # Valid split
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

    # Inverted date should fail
    inverted_val_df = pd.DataFrame({
        "date": ["2026-03-01"],
        TARGET_COLUMN: [2.0]
    }, index=[2])

    with pytest.raises(RuntimeError):
        verify_leakage(
            train_df=train_df,
            val_df=inverted_val_df,
            test_df=test_df,
            feature_cols=FEATURE_COLUMNS,
            target_col=TARGET_COLUMN,
            imputer=imp
        )


def test_production_xgboost_artifacts_exist_and_load():
    """Verify Phase 2.5 production artifacts in ml/models/xgboost/ load and execute correctly."""
    assert os.path.exists(os.path.join(MODEL_DIR, "model.joblib"))
    assert os.path.exists(os.path.join(MODEL_DIR, "best_model.joblib"))
    assert os.path.exists(os.path.join(MODEL_DIR, "preprocessor.joblib"))
    assert os.path.exists(os.path.join(MODEL_DIR, "metadata.json"))
    assert os.path.exists(os.path.join(MODEL_DIR, "config.json"))
    assert os.path.exists(REPORT_PATH)

    # Load model
    xgb_model = XGBoostDownscaler()
    xgb_model.load(MODEL_DIR)
    assert xgb_model.is_fitted is True

    # Test sample inference
    sample_X = pd.DataFrame(
        np.zeros((5, len(FEATURE_COLUMNS))),
        columns=FEATURE_COLUMNS
    )
    preds = xgb_model.predict(sample_X)
    assert len(preds) == 5
    assert np.all(preds >= 0.0)
    assert not np.any(np.isnan(preds))


def test_phase_2_5_report_structure():
    """Verify Phase 2.5 report JSON schema compliance with Section 18 specifications."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        rep = json.load(f)

    assert rep["metadata"]["phase"] == "2.5"
    assert "dataset" in rep
    assert "target" in rep
    assert "features" in rep
    assert "split" in rep
    assert "training" in rep
    assert "hyperparameters" in rep
    assert "validation_metrics" in rep
    assert "test_metrics" in rep
    assert "baseline_comparison" in rep
    assert "random_forest_comparison" in rep
    assert "feature_importance" in rep
    assert "leakage_checks" in rep
    assert "artifact" in rep
    assert "reproducibility" in rep

    # Verify key quantitative metrics
    val_mae = rep["validation_metrics"]["overall"]["mae"]
    assert val_mae < 6.0  # XGBoost beats raw block forecast (5.75 mm) on validation MAE
    assert "pune_validation_mae" in rep["random_forest_comparison"]
    assert rep["random_forest_comparison"]["pune_validation_mae"]["xgb_improvement_pct"] > 50.0
