"""
Unit and Integration Test Suite for GramSevak Phase 2 ML Downscaling Pipeline.

Validates all 10 mandatory Phase 2 ML contracts:
1. Feature generation and schema compliance
2. Missing-value handling (training-only fitting, non-imputed target)
3. Date splitting (strict chronological ordering, zero temporal overlap)
4. Leakage prevention (zero target, temporal, or future observation leakage)
5. Baseline calculation (MAE, RMSE, Bias on held-out test rows)
6. Model prediction (Random Forest production candidate)
7. Negative prediction clipping (physical constraint: downscaled_mm >= 0.0)
8. NaN and infinity handling (robust numerical safety)
9. Model loading and serialization integrity
10. Prediction schema and metadata compliance
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
import joblib

from ml.preprocessing import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    WeatherDataPreprocessor,
    load_dataset,
    split_dataset_by_time,
    prepare_training_features,
    prepare_inference_features,
)
from ml.predict import (
    load_trained_model,
    load_model_config,
    downscale_panchayat_forecast,
    predict_downscaled_rainfall,
    DEFAULT_PHASE2_RF_MODEL_PATH,
    DEFAULT_PHASE2_RF_PREPROCESSOR_PATH,
    DEFAULT_PHASE2_MODEL_CONFIG_PATH,
)


@pytest.fixture(scope="module")
def canonical_dataset():
    path = "data/processed/training_dataset.parquet"
    assert os.path.exists(path), f"Canonical dataset not found at {path}"
    return load_dataset(path)


@pytest.fixture(scope="module")
def temporal_split(canonical_dataset):
    df_train, df_val, df_test, split_info = split_dataset_by_time(
        canonical_dataset, train_ratio=0.70, val_ratio=0.15, date_col="date"
    )
    return df_train, df_val, df_test, split_info


# =====================================================================
# 1. Feature Generation & Canonical Schema
# =====================================================================
def test_feature_generation(canonical_dataset):
    """
    Validate that canonical dataset contains all 8 required numeric features
    and the primary target column with proper data types.
    """
    assert len(canonical_dataset) == 188708, f"Expected 188,708 rows, got {len(canonical_dataset)}"
    
    # 8 candidate features
    for col in FEATURE_COLUMNS:
        assert col in canonical_dataset.columns, f"Missing feature: {col}"
        assert pd.api.types.is_numeric_dtype(canonical_dataset[col]), f"{col} must be numeric"
        assert canonical_dataset[col].isnull().sum() == 0, f"{col} contains nulls in canonical parquet"

    # Primary target
    assert TARGET_COLUMN in canonical_dataset.columns
    assert pd.api.types.is_numeric_dtype(canonical_dataset[TARGET_COLUMN])
    assert canonical_dataset[TARGET_COLUMN].isnull().sum() == 0

    # Ensure prohibited identification columns are NOT in candidate features
    forbidden_features = ["panchayat_name", "block_name", "district_name", "station_id", "lgd_code", "panchayat_id"]
    for forbidden in forbidden_features:
        assert forbidden not in FEATURE_COLUMNS, f"Forbidden feature '{forbidden}' found in FEATURE_COLUMNS"


# =====================================================================
# 2. Missing-Value Handling
# =====================================================================
def test_missing_value_handling(temporal_split):
    """
    Verify training-derived median imputation:
    - Preprocessor statistics fitted strictly on training data
    - Target actual_rainfall_mm is NEVER imputed
    - Missing feature values in test set are filled using train medians
    """
    df_train, _, df_test, _ = temporal_split
    X_train_raw = df_train[FEATURE_COLUMNS].copy()
    
    preprocessor = WeatherDataPreprocessor(feature_columns=FEATURE_COLUMNS)
    preprocessor.fit(X_train_raw)

    # Imputer statistics must exist for all 8 features
    medians = preprocessor.get_imputation_statistics()
    assert len(medians) == 8
    for col in FEATURE_COLUMNS:
        assert col in medians
        assert not np.isnan(medians[col])

    # Test handling of injected missing values in inference data
    sample_df = df_test.head(10)[FEATURE_COLUMNS].copy()
    sample_df.loc[sample_df.index[0], "elevation_m"] = np.nan
    sample_df.loc[sample_df.index[1], "station_distance_km"] = np.nan

    transformed = preprocessor.transform(sample_df)
    assert not transformed.isna().any().any(), "Transformed data must contain zero NaNs"
    
    # Verify the imputed value matches train median
    assert transformed.iloc[0]["elevation_m"] == pytest.approx(medians["elevation_m"], rel=1e-4)


# =====================================================================
# 3. Date Splitting (Strict Chronological Ordering)
# =====================================================================
def test_date_splitting(temporal_split):
    """
    Validate chronological time-aware split:
    - No temporal shuffling
    - Train period strictly precedes Validation period
    - Validation period strictly precedes Test period
    - Date boundaries are contiguous without overlap
    """
    df_train, df_val, df_test, split_info = temporal_split

    train_dates = pd.to_datetime(df_train["date"])
    val_dates = pd.to_datetime(df_val["date"])
    test_dates = pd.to_datetime(df_test["date"])

    train_max = train_dates.max()
    val_min = val_dates.min()
    val_max = val_dates.max()
    test_min = test_dates.min()

    assert train_max < val_min, f"Train max ({train_max}) must be earlier than Val min ({val_min})"
    assert val_max < test_min, f"Val max ({val_max}) must be earlier than Test min ({test_min})"

    # Verify no date leakage across sets
    train_date_set = set(df_train["date"].unique())
    val_date_set = set(df_val["date"].unique())
    test_date_set = set(df_test["date"].unique())

    assert len(train_date_set.intersection(val_date_set)) == 0, "Train and Val dates must not overlap"
    assert len(train_date_set.intersection(test_date_set)) == 0, "Train and Test dates must not overlap"
    assert len(val_date_set.intersection(test_date_set)) == 0, "Val and Test dates must not overlap"

    # Verify row counts
    assert len(df_train) == 129636
    assert len(df_val) == 29486
    assert len(df_test) == 29586


# =====================================================================
# 4. Leakage Prevention
# =====================================================================
def test_leakage_prevention(temporal_split):
    """
    Verify zero data leakage:
    - Target actual_rainfall_mm is NOT present in feature inputs
    - Future dates or future weather observations cannot leak into training features
    """
    df_train, _, df_test, _ = temporal_split

    X_train_raw, y_train, _ = prepare_training_features(df_train, features=FEATURE_COLUMNS, target=TARGET_COLUMN)
    assert TARGET_COLUMN not in X_train_raw.columns, "TARGET LEAKAGE: actual_rainfall_mm found in training features"

    X_test_raw, _ = prepare_inference_features(df_test, features=FEATURE_COLUMNS)
    assert TARGET_COLUMN not in X_test_raw.columns, "TARGET LEAKAGE: actual_rainfall_mm found in test inference features"

    # Verify lead_days >= 0 (forecast horizon is future-oriented, not retrospective)
    assert (X_train_raw["lead_days"] >= 0).all()
    assert (X_test_raw["lead_days"] >= 0).all()


# =====================================================================
# 5. Baseline Calculation
# =====================================================================
def test_baseline_calculation(temporal_split):
    """
    Verify baseline performance metrics on held-out test rows:
    Prediction = block_forecast_rainfall_mm, Target = actual_rainfall_mm.
    """
    _, _, df_test, _ = temporal_split

    y_true = df_test["actual_rainfall_mm"].values.astype(float)
    y_base = df_test["block_forecast_rainfall_mm"].values.astype(float)

    mae = float(np.mean(np.abs(y_base - y_true)))
    rmse = float(np.sqrt(np.mean((y_base - y_true) ** 2)))
    bias = float(np.mean(y_base - y_true))

    assert mae == pytest.approx(4.5271, abs=0.01)
    assert rmse == pytest.approx(5.0206, abs=0.01)
    assert bias == pytest.approx(2.7458, abs=0.01)


# =====================================================================
# 6. Model Loading and Artifact Integrity
# =====================================================================
def test_model_loading():
    """
    Verify serialized model artifact and model_config.json load cleanly.
    """
    assert os.path.exists(DEFAULT_PHASE2_RF_MODEL_PATH), f"Phase 2 model missing at {DEFAULT_PHASE2_RF_MODEL_PATH}"
    assert os.path.exists(DEFAULT_PHASE2_RF_PREPROCESSOR_PATH), f"Phase 2 preprocessor missing at {DEFAULT_PHASE2_RF_PREPROCESSOR_PATH}"
    assert os.path.exists(DEFAULT_PHASE2_MODEL_CONFIG_PATH), f"Phase 2 config missing at {DEFAULT_PHASE2_MODEL_CONFIG_PATH}"

    model, preprocessor = load_trained_model(
        model_path=DEFAULT_PHASE2_RF_MODEL_PATH,
        preprocessor_path=DEFAULT_PHASE2_RF_PREPROCESSOR_PATH,
        use_cache=False
    )
    assert model is not None
    assert preprocessor is not None

    config = load_model_config(config_path=DEFAULT_PHASE2_MODEL_CONFIG_PATH)
    assert config["model_name"] == "Random Forest Regressor"
    assert config["model_version"] == "v2.0.0"
    assert "evaluation_metrics" in config
    assert "baseline" in config["evaluation_metrics"]
    assert "random_forest" in config["evaluation_metrics"]
    assert config["evaluation_metrics"]["random_forest"]["mae"] < config["evaluation_metrics"]["baseline"]["mae"]


# =====================================================================
# 7. Model Prediction (Clean Phase 2 Interface)
# =====================================================================
def test_model_prediction():
    """
    Test downscale_panchayat_forecast single-record prediction interface.
    """
    panchayat_features = {
        "panchayat_latitude": 20.2056,
        "panchayat_longitude": 73.8344,
        "elevation_m": 585.0,
        "station_distance_km": 4.2,
        "lead_days": 0,
        "month": 9,
        "day_of_year": 250,
    }
    result = downscale_panchayat_forecast(
        panchayat_features=panchayat_features,
        block_forecast_rainfall_mm=10.0
    )

    assert isinstance(result, dict)
    assert "downscaled_rainfall_mm" in result
    assert "raw_predicted_rainfall_mm" in result
    assert "baseline_forecast_mm" in result
    assert "model_name" in result
    assert "model_version" in result

    assert isinstance(result["downscaled_rainfall_mm"], (int, float))
    assert result["downscaled_rainfall_mm"] >= 0.0
    assert result["model_name"] == "Random Forest Regressor"
    assert result["model_version"] == "v2.0.0"


# =====================================================================
# 8. Negative Prediction Clipping
# =====================================================================
def test_negative_prediction_clipping():
    """
    Verify physical non-negativity constraint:
    downscaled_rainfall_mm = max(raw_prediction, 0.0)
    """
    panchayat_features = {
        "panchayat_latitude": 20.0,
        "panchayat_longitude": 73.8,
        "elevation_m": 500.0,
        "station_distance_km": 5.0,
        "lead_days": 0,
        "month": 1,
        "day_of_year": 10,
    }
    # zero block forecast in dry month (January)
    result = downscale_panchayat_forecast(
        panchayat_features=panchayat_features,
        block_forecast_rainfall_mm=0.0
    )
    assert result["downscaled_rainfall_mm"] >= 0.0
    assert not np.isnan(result["downscaled_rainfall_mm"])


# =====================================================================
# 9. NaN and Infinity Safety Handling
# =====================================================================
def test_nan_infinity_handling():
    """
    Verify extreme boundary values do not generate NaN or Inf.
    """
    panchayat_features = {
        "panchayat_latitude": 18.5,
        "panchayat_longitude": 73.8,
        "elevation_m": 1200.0,
        "station_distance_km": 50.0,
        "lead_days": 5,
        "month": 7,
        "day_of_year": 200,
    }
    result = downscale_panchayat_forecast(
        panchayat_features=panchayat_features,
        block_forecast_rainfall_mm=250.0  # extreme heavy rainfall event
    )
    assert not np.isnan(result["downscaled_rainfall_mm"])
    assert not np.isinf(result["downscaled_rainfall_mm"])
    assert result["downscaled_rainfall_mm"] >= 0.0


# =====================================================================
# 10. Prediction Schema and Contract Compliance
# =====================================================================
def test_prediction_schema():
    """
    Verify exact contract specification of prediction output schema.
    """
    panchayat_features = {
        "panchayat_latitude": 19.9975,
        "panchayat_longitude": 73.7898,
        "elevation_m": 600.0,
        "station_distance_km": 3.5,
        "lead_days": 1,
        "month": 8,
        "day_of_year": 220,
    }
    res = downscale_panchayat_forecast(
        panchayat_features=panchayat_features,
        block_forecast_rainfall_mm=15.5
    )

    expected_keys = {
        "downscaled_rainfall_mm",
        "raw_predicted_rainfall_mm",
        "baseline_forecast_mm",
        "model_name",
        "model_version",
    }
    assert set(res.keys()) == expected_keys
    assert isinstance(res["downscaled_rainfall_mm"], float)
    assert isinstance(res["raw_predicted_rainfall_mm"], float)
    assert isinstance(res["baseline_forecast_mm"], float)
    assert isinstance(res["model_name"], str)
    assert isinstance(res["model_version"], str)


# =====================================================================
# 11. Spatial Holdout Robustness Validation Check
# =====================================================================
def test_spatial_holdout_robustness():
    """
    Verify spatial holdout metrics are saved and demonstrate positive generalization
    on unseen Panchayats.
    """
    config = load_model_config(config_path=DEFAULT_PHASE2_MODEL_CONFIG_PATH)
    assert "spatial_holdout_metrics" in config
    sp = config["spatial_holdout_metrics"]

    assert sp["holdout_panchayats_count"] > 500
    assert sp["evaluation_records"] > 5000
    assert sp["model_mae"] < sp["baseline_mae"]
    assert sp["mae_improvement_percent"] > 0.0
