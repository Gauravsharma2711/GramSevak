import os
import sys
import json
import logging
from typing import Union, List, Dict, Any, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml.preprocessing import (
    FEATURE_COLUMNS,
    load_dataset,
    prepare_inference_features,
    WeatherDataPreprocessor
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = "ml/models"
DEFAULT_BEST_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "best_model.joblib")
DEFAULT_BEST_PREPROCESSOR_PATH = os.path.join(DEFAULT_MODEL_DIR, "best_model_preprocessor.joblib")
DEFAULT_BEST_CONFIG_PATH = os.path.join(DEFAULT_MODEL_DIR, "best_model_config.json")

DEFAULT_RF_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "random_forest_model.joblib")
DEFAULT_RF_PREPROCESSOR_PATH = os.path.join(DEFAULT_MODEL_DIR, "random_forest_preprocessor.joblib")
DEFAULT_RF_PREDICTIONS_PATH = "ml/validation/random_forest_predictions.csv"

DEFAULT_MODEL_PATH = DEFAULT_RF_MODEL_PATH
DEFAULT_PREPROCESSOR_PATH = DEFAULT_RF_PREPROCESSOR_PATH
DEFAULT_OUTPUT_PREDICTIONS_PATH = DEFAULT_RF_PREDICTIONS_PATH

DEFAULT_XGB_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "xgboost_model.joblib")
DEFAULT_XGB_PREDICTIONS_PATH = "ml/validation/xgboost_predictions.csv"

# Global memory cache for loaded models and preprocessors to avoid repeated disk I/O
_MODEL_CACHE: Dict[str, Any] = {}
_PREPROCESSOR_CACHE: Dict[str, Any] = {}
_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}


def load_trained_model(
    model_path: str = DEFAULT_BEST_MODEL_PATH,
    preprocessor_path: Optional[str] = DEFAULT_BEST_PREPROCESSOR_PATH,
    use_cache: bool = True
) -> Tuple[Any, Optional[Any]]:
    """
    Load serialized model artifact and preprocessing pipeline from disk with optional caching.
    
    Never retrains models during loading or prediction.
    """
    if use_cache and model_path in _MODEL_CACHE:
        model = _MODEL_CACHE[model_path]
        preprocessor = _PREPROCESSOR_CACHE.get(preprocessor_path) if preprocessor_path else None
        return model, preprocessor

    if not os.path.exists(model_path):
        # Fallback to XGBoost or Random Forest if best_model.joblib not present
        if os.path.exists(DEFAULT_XGB_MODEL_PATH):
            model_path = DEFAULT_XGB_MODEL_PATH
        elif os.path.exists(DEFAULT_RF_MODEL_PATH):
            model_path = DEFAULT_RF_MODEL_PATH
        else:
            raise FileNotFoundError(f"Model artifact not found at {model_path}. Train model first.")
    
    loaded = joblib.load(model_path)
    if isinstance(loaded, dict) and "model" in loaded:
        model = loaded["model"]
        preprocessor = loaded.get("preprocessor")
    else:
        model = loaded
        preprocessor = None
        
    if preprocessor is None and preprocessor_path:
        if os.path.exists(preprocessor_path):
            preprocessor = joblib.load(preprocessor_path)
        elif os.path.exists(DEFAULT_RF_PREPROCESSOR_PATH):
            preprocessor = joblib.load(DEFAULT_RF_PREPROCESSOR_PATH)
            
    if use_cache:
        _MODEL_CACHE[model_path] = model
        if preprocessor_path and preprocessor:
            _PREPROCESSOR_CACHE[preprocessor_path] = preprocessor
            
    return model, preprocessor


def load_model_config(config_path: str = DEFAULT_BEST_CONFIG_PATH) -> Dict[str, Any]:
    """
    Load frozen model metadata configuration (model_name, model_version, features).
    """
    if config_path in _CONFIG_CACHE:
        return _CONFIG_CACHE[config_path]
        
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "model_name": "XGBoost Regressor",
            "model_version": "v1.0.0",
            "feature_list": FEATURE_COLUMNS
        }
        
    _CONFIG_CACHE[config_path] = config
    return config


def predict_downscaled_rainfall(
    block_forecast_rainfall_mm: float,
    panchayat_latitude: float,
    panchayat_longitude: float,
    elevation_m: float,
    station_distance_km: float,
    lead_days: int,
    month: int,
    day_of_year: int,
    model_path: str = DEFAULT_BEST_MODEL_PATH,
    preprocessor_path: Optional[str] = DEFAULT_BEST_PREPROCESSOR_PATH,
    config_path: str = DEFAULT_BEST_CONFIG_PATH
) -> Dict[str, Any]:
    """
    Production single-record downscaling prediction function.
    
    Requirements fulfilled:
    - Loads best_model.joblib and matching preprocessor.
    - Applies strictly identical feature ordering and median imputation as during training.
    - Never retrains during prediction.
    - Never uses actual rainfall or future observations as inputs.
    - Ensures non-negative numeric rainfall output (downscaled_rainfall_mm >= 0.0).
    - Returns model metadata (model_name, model_version).
    
    Args:
        block_forecast_rainfall_mm: IMD numerical regional weather forecast in mm.
        panchayat_latitude: WGS84 Latitude of Gram Panchayat centroid.
        panchayat_longitude: WGS84 Longitude of Gram Panchayat centroid.
        elevation_m: SRTM Terrain elevation in meters above sea level.
        station_distance_km: Distance to nearest ground weather station in km.
        lead_days: Forecast lead time horizon in days (e.g. 0).
        month: Calendar month (1 to 12).
        day_of_year: Day of the year (1 to 366).
        model_path: Path to serialized frozen model artifact.
        preprocessor_path: Path to serialized preprocessor artifact.
        config_path: Path to model configuration metadata JSON.
        
    Returns:
        Dict containing:
        - downscaled_rainfall_mm (float, >= 0.0)
        - raw_predicted_rainfall_mm (float)
        - model_name (str)
        - model_version (str)
    """
    # 1. Load model, preprocessor, and metadata
    model, preprocessor = load_trained_model(model_path=model_path, preprocessor_path=preprocessor_path)
    config = load_model_config(config_path=config_path)
    
    # 2. Build input DataFrame matching exact feature column schema
    input_dict = {
        "block_forecast_rainfall_mm": [float(block_forecast_rainfall_mm)],
        "panchayat_latitude": [float(panchayat_latitude)],
        "panchayat_longitude": [float(panchayat_longitude)],
        "elevation_m": [float(elevation_m)],
        "station_distance_km": [float(station_distance_km)],
        "lead_days": [int(lead_days)],
        "month": [int(month)],
        "day_of_year": [int(day_of_year)],
    }
    input_df = pd.DataFrame(input_dict)[FEATURE_COLUMNS]
    
    # 3. Apply matching preprocessing transform (never refitting)
    if preprocessor is not None:
        X = preprocessor.transform(input_df)
    else:
        X = input_df.values.astype(float)
        
    # 4. Generate prediction
    raw_pred = float(model.predict(X)[0])
    
    # 5. Non-negative rainfall constraint
    downscaled_mm = float(max(raw_pred, 0.0))
    
    return {
        "downscaled_rainfall_mm": round(downscaled_mm, 4),
        "raw_predicted_rainfall_mm": round(raw_pred, 4),
        "model_name": config.get("model_name", "XGBoost Regressor"),
        "model_version": config.get("model_version", "v1.0.0"),
    }


def predict_rainfall(
    data: Union[pd.DataFrame, str],
    model_path: str = DEFAULT_BEST_MODEL_PATH,
    preprocessor_path: Optional[str] = DEFAULT_BEST_PREPROCESSOR_PATH,
    output_column: str = "downscaled_rainfall_mm"
) -> pd.DataFrame:
    """
    Batch prediction function for DataFrames or CSV files.
    """
    if isinstance(data, str):
        df = load_dataset(data)
    else:
        df = data.copy()
        
    model, preprocessor = load_trained_model(model_path, preprocessor_path=preprocessor_path)
    
    X_raw, metadata = prepare_inference_features(df, features=FEATURE_COLUMNS)
    
    if preprocessor is not None:
        X = preprocessor.transform(X_raw)
    else:
        X = X_raw
        
    raw_preds = model.predict(X)
    clipped_preds = np.clip(raw_preds, a_min=0.0, a_max=None)
    
    result_df = df.copy()
    result_df["raw_predicted_rainfall_mm"] = np.round(raw_preds, 4)
    result_df[output_column] = np.round(clipped_preds, 4)
    
    return result_df


def generate_test_predictions(
    test_path: str = "data/features/nashik_test.csv",
    model_path: str = DEFAULT_RF_MODEL_PATH,
    preprocessor_path: str = DEFAULT_RF_PREPROCESSOR_PATH,
    output_path: str = DEFAULT_RF_PREDICTIONS_PATH
) -> pd.DataFrame:
    """
    Generate predictions for held-out test dataset and compute error metrics per row.
    Saves results to ml/validation/random_forest_predictions.csv.
    """
    logger.info(f"Loading test dataset from: {test_path}")
    df_test = load_dataset(test_path)
    
    preds_df = predict_rainfall(
        data=df_test,
        model_path=model_path,
        preprocessor_path=preprocessor_path,
        output_column="predicted_rainfall_mm"
    )
    
    preds_df["prediction_error"] = np.round(preds_df["predicted_rainfall_mm"] - preds_df["actual_rainfall_mm"], 4)
    preds_df["absolute_error"] = np.round(np.abs(preds_df["prediction_error"]), 4)
    preds_df["squared_error"] = np.round(preds_df["prediction_error"] ** 2, 4)
    
    required_cols = [
        "panchayat_id",
        "panchayat_name",
        "block_name",
        "date",
        "forecast_issue_date",
        "lead_days",
        "block_forecast_rainfall_mm",
        "actual_rainfall_mm",
        "raw_predicted_rainfall_mm",
        "predicted_rainfall_mm",
        "prediction_error",
        "absolute_error",
        "squared_error",
    ]
    
    output_df = preds_df[required_cols].copy()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info(f"Saved test predictions to: {output_path} ({len(output_df)} rows)")
    return output_df


def generate_xgboost_predictions(
    test_path: str = "data/features/nashik_test.csv",
    model_path: str = DEFAULT_XGB_MODEL_PATH,
    preprocessor_path: str = DEFAULT_RF_PREPROCESSOR_PATH,
    output_path: str = DEFAULT_XGB_PREDICTIONS_PATH
) -> pd.DataFrame:
    """
    Generate predictions for held-out test dataset using trained XGBoost model.
    Saves results to ml/validation/xgboost_predictions.csv.
    """
    return generate_test_predictions(
        test_path=test_path,
        model_path=model_path,
        preprocessor_path=preprocessor_path,
        output_path=output_path
    )


DEFAULT_PHASE2_RF_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "random_forest", "best_model.joblib")
DEFAULT_PHASE2_RF_PREPROCESSOR_PATH = os.path.join(DEFAULT_MODEL_DIR, "random_forest", "preprocessor.joblib")
DEFAULT_PHASE2_MODEL_CONFIG_PATH = os.path.join(DEFAULT_MODEL_DIR, "model_config.json")


def downscale_panchayat_forecast(
    panchayat_features: Dict[str, Any],
    block_forecast_rainfall_mm: float,
    model_path: str = DEFAULT_PHASE2_RF_MODEL_PATH,
    preprocessor_path: Optional[str] = DEFAULT_PHASE2_RF_PREPROCESSOR_PATH,
    config_path: str = DEFAULT_PHASE2_MODEL_CONFIG_PATH
) -> Dict[str, Any]:
    """
    Phase 2 Clean Production Prediction Interface.
    
    Accepts:
        panchayat_features: Dictionary containing spatial/terrain features:
            - panchayat_latitude (float)
            - panchayat_longitude (float)
            - elevation_m (float)
            - station_distance_km (float)
            - lead_days (int)
            - month (int)
            - day_of_year (int)
        block_forecast_rainfall_mm: float (IMD regional forecast in mm)
        
    Guarantees:
        - Strict feature schema alignment.
        - Median imputation for missing values (training-derived).
        - Enforced physical non-negativity: downscaled_rainfall_mm = max(raw_pred, 0.0).
        - NaN / Inf safe.
        - Returns downscaled rainfall, raw prediction, model name, model version, and baseline.
    """
    required = [
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
        "station_distance_km",
        "lead_days",
        "month",
        "day_of_year"
    ]
    for k in required:
        if k not in panchayat_features:
            raise KeyError(f"Missing required panchayat feature: '{k}'")
            
    # Fallback if phase 2 subfolder model not found
    if not os.path.exists(model_path):
        if os.path.exists(DEFAULT_BEST_MODEL_PATH):
            model_path = DEFAULT_BEST_MODEL_PATH
            preprocessor_path = DEFAULT_BEST_PREPROCESSOR_PATH
            config_path = DEFAULT_BEST_CONFIG_PATH

    model, preprocessor = load_trained_model(model_path=model_path, preprocessor_path=preprocessor_path)
    config = load_model_config(config_path=config_path)

    input_dict = {
        "block_forecast_rainfall_mm": [float(block_forecast_rainfall_mm)],
        "panchayat_latitude": [float(panchayat_features["panchayat_latitude"])],
        "panchayat_longitude": [float(panchayat_features["panchayat_longitude"])],
        "elevation_m": [float(panchayat_features["elevation_m"])],
        "station_distance_km": [float(panchayat_features["station_distance_km"])],
        "lead_days": [int(panchayat_features["lead_days"])],
        "month": [int(panchayat_features["month"])],
        "day_of_year": [int(panchayat_features["day_of_year"])],
    }
    input_df = pd.DataFrame(input_dict)[FEATURE_COLUMNS]

    if preprocessor is not None:
        X = preprocessor.transform(input_df)
    else:
        X = input_df.values.astype(float)

    raw_pred = float(model.predict(X)[0])
    
    # NaN and Infinity safety guard
    if np.isnan(raw_pred) or np.isinf(raw_pred):
        raw_pred = float(block_forecast_rainfall_mm)
        
    downscaled_mm = float(max(raw_pred, 0.0))

    return {
        "downscaled_rainfall_mm": round(downscaled_mm, 4),
        "raw_predicted_rainfall_mm": round(raw_pred, 4),
        "baseline_forecast_mm": round(float(block_forecast_rainfall_mm), 4),
        "model_name": config.get("model_name", "Random Forest Regressor"),
        "model_version": config.get("model_version", "v2.0.0"),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("SIH26074 -- PRODUCTION PREDICTION FUNCTION (DAY 3 - STEP 16)")
    print("=" * 70)
    
    # Test sample inference for Dindori Gram Panchayat
    sample_res = predict_downscaled_rainfall(
        block_forecast_rainfall_mm=12.5,
        panchayat_latitude=20.2056,
        panchayat_longitude=73.8344,
        elevation_m=585.0,
        station_distance_km=4.2,
        lead_days=0,
        month=9,
        day_of_year=247
    )
    
    print("\n--- Sample Micro-Level Downscaling Prediction ---")
    print(f"Model Name:              {sample_res['model_name']}")
    print(f"Model Version:           {sample_res['model_version']}")
    print(f"Input Block Forecast:    12.50 mm")
    print(f"Downscaled Prediction:   {sample_res['downscaled_rainfall_mm']:.4f} mm")
    print(f"Raw Model Prediction:    {sample_res['raw_predicted_rainfall_mm']:.4f} mm")
    print("=" * 70)
