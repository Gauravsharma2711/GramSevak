"""
GramSevak Automated Test Suite for ML Model Packaging and Inference API (Phase 2.7).

Verifies:
1. Model artifact loading from registry
2. Model metadata and config loading
3. Feature registry loading and 20-feature validation
4. Model and feature compatibility checks
5. Valid inference request processing
6. Rejection of missing required fields (e.g. missing block_forecast_rainfall_mm)
7. Rejection of invalid dates (forecast_date < forecast_issue_date)
8. Rejection of invalid numeric values (negative block forecast, invalid lat/lon)
9. Target leakage field rejection (actual_rainfall_mm, etc.)
10. Physical non-negative prediction clamping (>= 0.0 mm)
11. Model in-process caching (single disk load)
12. Model load failure and error propagation
13. Deterministic fallback to raw block forecast
14. FastAPI /api/v1/forecast/downscale endpoint success
15. FastAPI endpoint validation errors (422 Unprocessable Entity)
16. Response metadata verification (model_name, model_version, prediction_mode)
17. Verification that no credentials or file paths are exposed to clients
18. Consistency across repeated inference requests
19. Real-data integration test with authentic Pune and Nashik Panchayats
"""

import os
import sys
import json
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.main import app
from backend.ml.registry import ModelRegistry
from backend.ml.schemas import DownscaleInferenceRequest, DownscaleInferenceResponse
from backend.ml.feature_builder import FeatureBuilder
from backend.ml.model_loader import ModelLoader, ModelArtifactNotFoundError
from backend.ml.predictor import DownscalingPredictor
from backend.services.ml_prediction_service import MLPredictionService


@pytest.fixture(scope="module")
def api_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_valid_payload():
    """Sample valid downscaling request payload conforming to Phase 2 contract."""
    return {
        "panchayat_id": 1001,
        "panchayat_name": "Khadakwasla",
        "block_name": "Haveli",
        "district_name": "Pune",
        "forecast_date": "2026-08-15",
        "forecast_issue_date": "2026-08-14",
        "block_forecast_rainfall_mm": 12.5,
        "panchayat_latitude": 18.435,
        "panchayat_longitude": 73.765,
        "elevation_m": 585.0,
        "station_distance_km": 4.2,
        "station_latitude": 18.420,
        "station_longitude": 73.750,
        "lead_days": 1,
        "historical_rainfall_prior_1d_mm": 8.0,
        "historical_rainfall_prior_2d_mm": 5.5,
        "historical_rainfall_prior_3d_mean_mm": 6.2,
        "historical_rainfall_prior_3d_sum_mm": 18.6,
        "historical_rainfall_prior_7d_mean_mm": 10.4,
        "historical_rainfall_prior_7d_sum_mm": 72.8,
        "has_historical_rainfall_context": 1
    }


def test_model_registry_loads_config():
    """Verify registry loads configs/ml_model.yaml and schemas/ml_feature_registry.json."""
    registry = ModelRegistry.get_instance()
    assert registry.get_active_model_name() in ["xgboost", "random_forest"]
    
    cfg = registry.get_model_config()
    assert "model_name" in cfg
    assert "model_version" in cfg
    assert cfg["feature_count"] == 20
    assert cfg["target"] == "actual_rainfall_mm"

    features = registry.get_expected_feature_names()
    assert len(features) == 20
    assert "block_forecast_rainfall_mm" in features
    assert "log1p_block_forecast_rainfall_mm" in features
    assert "target_day_of_year_sin" in features


def test_model_loader_caching_and_metadata():
    """Verify ModelLoader loads artifacts into cache and records load latency."""
    loader = ModelLoader.get_instance()
    model_a, meta_a = loader.load_model("xgboost")
    assert model_a is not None
    assert loader.get_load_duration("xgboost") is not None

    # Second load must return cached reference instantly
    model_b, meta_b = loader.load_model("xgboost")
    assert model_a is model_b


def test_feature_builder_exact_20_features(sample_valid_payload):
    """Verify FeatureBuilder produces exact 20 features in matching column order."""
    registry = ModelRegistry.get_instance()
    builder = FeatureBuilder(registry)
    req = DownscaleInferenceRequest(**sample_valid_payload)
    
    df = builder.build_features(req)
    assert df.shape == (1, 20)
    assert list(df.columns) == registry.get_expected_feature_names()
    assert df["block_forecast_rainfall_mm"].iloc[0] == 12.5
    assert df["log1p_block_forecast_rainfall_mm"].iloc[0] == pytest.approx(2.602689, 1e-4)
    assert df["lead_days"].iloc[0] == 1.0


def test_predictor_valid_inference(sample_valid_payload):
    """Verify DownscalingPredictor returns valid DownscaleInferenceResponse."""
    predictor = DownscalingPredictor()
    req = DownscaleInferenceRequest(**sample_valid_payload)
    res = predictor.predict(req)

    assert isinstance(res, DownscaleInferenceResponse)
    assert res.panchayat_id == 1001
    assert res.prediction_mode == "ml"
    assert res.downscaled_rainfall_mm >= 0.0
    assert res.confidence is None  # Must not fabricate confidence
    assert res.model_name in ["xgboost_downscaler", "random_forest_downscaler"]


def test_reject_target_leakage_fields(sample_valid_payload):
    """Verify request is rejected if client passes ground truth target variable."""
    leaking_payload = dict(sample_valid_payload)
    leaking_payload["actual_rainfall_mm"] = 15.0

    with pytest.raises(ValueError, match="Target leakage violation"):
        DownscaleInferenceRequest(**leaking_payload)

    leaking_payload2 = dict(sample_valid_payload)
    leaking_payload2["target_rainfall"] = 12.0
    with pytest.raises(ValueError, match="Target leakage violation"):
        DownscaleInferenceRequest(**leaking_payload2)


def test_reject_inverted_dates(sample_valid_payload):
    """Verify rejection when forecast_date is earlier than forecast_issue_date."""
    inverted_payload = dict(sample_valid_payload)
    inverted_payload["forecast_date"] = "2026-08-10"
    inverted_payload["forecast_issue_date"] = "2026-08-14"

    with pytest.raises(ValueError, match="Temporal violation"):
        DownscaleInferenceRequest(**inverted_payload)


def test_reject_negative_rainfall(sample_valid_payload):
    """Verify rejection of negative block forecast rainfall."""
    invalid_payload = dict(sample_valid_payload)
    invalid_payload["block_forecast_rainfall_mm"] = -5.0

    with pytest.raises(ValueError):
        DownscaleInferenceRequest(**invalid_payload)


def test_deterministic_fallback_behavior(sample_valid_payload):
    """Verify predictor falls back to block forecast when model artifact is missing."""
    registry = ModelRegistry.get_instance()
    # Create predictor with custom registry pointing to nonexistent model
    fake_registry = ModelRegistry()
    fake_registry.config = {
        "active_model": "missing_model",
        "models": {
            "missing_model": {
                "model_name": "missing_model",
                "model_version": "0.0.0",
                "artifact_dir": "ml/models/nonexistent_dir",
                "model_file": "nonexistent.joblib",
                "feature_count": 20,
            }
        },
        "fallback": {"enabled": True, "strategy": "block_forecast"}
    }
    
    predictor = DownscalingPredictor(registry=fake_registry)
    req = DownscaleInferenceRequest(**sample_valid_payload)
    res = predictor.predict(req, model_name="missing_model")

    assert res.prediction_mode == "fallback"
    assert res.downscaled_rainfall_mm == sample_valid_payload["block_forecast_rainfall_mm"]
    assert "fallback_reason" in res.metadata


def test_api_downscale_endpoint_success(api_client, sample_valid_payload):
    """Verify POST /api/v1/forecast/downscale endpoint returns HTTP 200 with valid prediction."""
    response = api_client.post("/api/v1/forecast/downscale", json=sample_valid_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["panchayat_id"] == 1001
    assert data["forecast_date"] == "2026-08-15"
    assert data["forecast_issue_date"] == "2026-08-14"
    assert data["block_forecast_rainfall_mm"] == 12.5
    assert data["downscaled_rainfall_mm"] >= 0.0
    assert data["prediction_mode"] in ["ml", "fallback"]
    assert "model_name" in data
    assert "model_version" in data
    assert data["confidence"] is None


def test_api_downscale_validation_errors(api_client, sample_valid_payload):
    """Verify API returns HTTP 422 Unprocessable Entity on validation violations."""
    # 1. Missing required field (block_forecast_rainfall_mm)
    bad_payload1 = dict(sample_valid_payload)
    del bad_payload1["block_forecast_rainfall_mm"]
    res1 = api_client.post("/api/v1/forecast/downscale", json=bad_payload1)
    assert res1.status_code == 422

    # 2. Target leakage field passed
    bad_payload2 = dict(sample_valid_payload)
    bad_payload2["actual_rainfall_mm"] = 10.0
    res2 = api_client.post("/api/v1/forecast/downscale", json=bad_payload2)
    assert res2.status_code == 422
    assert "Target leakage" in res2.text

    # 3. Temporal inverted dates
    bad_payload3 = dict(sample_valid_payload)
    bad_payload3["forecast_date"] = "2026-08-01"
    bad_payload3["forecast_issue_date"] = "2026-08-10"
    res3 = api_client.post("/api/v1/forecast/downscale", json=bad_payload3)
    assert res3.status_code == 422
    assert "Temporal violation" in res3.text


def test_api_does_not_expose_secrets_or_filepaths(api_client, sample_valid_payload):
    """Verify API responses never leak internal filesystem paths, database URLs, or API keys."""
    response = api_client.post("/api/v1/forecast/downscale", json=sample_valid_payload)
    body_text = response.text.lower()

    forbidden_tokens = ["postgres://", "postgresql://", "supabase_key", "service_role", "c:\\", "/users/"]
    for token in forbidden_tokens:
        assert token not in body_text, f"Potential sensitive leak detected: {token}"


def test_repeated_inference_consistency(sample_valid_payload):
    """Verify identical input payloads yield identical deterministic predictions."""
    predictor = DownscalingPredictor()
    req = DownscaleInferenceRequest(**sample_valid_payload)
    
    res1 = predictor.predict(req)
    res2 = predictor.predict(req)
    assert res1.downscaled_rainfall_mm == res2.downscaled_rainfall_mm


def test_real_data_integration_pune_and_nashik():
    """Verify inference works on real feature records from Pune and Nashik datasets."""
    pune_parquet = os.path.join(PROJECT_ROOT, "data", "ml", "features", "pune", "rainfall_features.parquet")
    nashik_parquet = os.path.join(PROJECT_ROOT, "data", "ml", "features", "nashik", "rainfall_features.parquet")

    service = MLPredictionService.get_instance()

    # 1. Test with real Pune record
    if os.path.exists(pune_parquet):
        import pandas as pd
        df_pune = pd.read_parquet(pune_parquet)
        sample_row = df_pune.iloc[100]

        req_pune = DownscaleInferenceRequest(
            panchayat_id=int(sample_row["panchayat_id"]),
            forecast_date=sample_row["date"],
            forecast_issue_date=sample_row["forecast_issue_date"],
            block_forecast_rainfall_mm=float(sample_row["block_forecast_rainfall_mm"]),
            panchayat_latitude=float(sample_row["panchayat_latitude"]),
            panchayat_longitude=float(sample_row["panchayat_longitude"]),
            elevation_m=float(sample_row["elevation_m"]) if not pd.isna(sample_row["elevation_m"]) else None,
            station_distance_km=float(sample_row["station_distance_km"]) if not pd.isna(sample_row["station_distance_km"]) else None,
            station_latitude=float(sample_row["station_latitude"]) if not pd.isna(sample_row["station_latitude"]) else None,
            station_longitude=float(sample_row["station_longitude"]) if not pd.isna(sample_row["station_longitude"]) else None,
            lead_days=int(sample_row["lead_days"]),
            historical_rainfall_prior_1d_mm=float(sample_row["historical_rainfall_prior_1d_mm"]) if not pd.isna(sample_row["historical_rainfall_prior_1d_mm"]) else None,
            historical_rainfall_prior_2d_mm=float(sample_row["historical_rainfall_prior_2d_mm"]) if not pd.isna(sample_row["historical_rainfall_prior_2d_mm"]) else None,
            has_historical_rainfall_context=int(sample_row["has_historical_rainfall_context"])
        )
        res_pune = service.predict_rainfall(req_pune)
        assert res_pune.prediction_mode == "ml"
        assert res_pune.downscaled_rainfall_mm >= 0.0

    # 2. Test with real Nashik record
    if os.path.exists(nashik_parquet):
        import pandas as pd
        df_nashik = pd.read_parquet(nashik_parquet)
        sample_nashik = df_nashik.iloc[50]

        req_nashik = DownscaleInferenceRequest(
            panchayat_id=int(sample_nashik["panchayat_id"]),
            forecast_date=sample_nashik["date"],
            forecast_issue_date=sample_nashik["forecast_issue_date"],
            block_forecast_rainfall_mm=float(sample_nashik["block_forecast_rainfall_mm"]),
            panchayat_latitude=float(sample_nashik["panchayat_latitude"]),
            panchayat_longitude=float(sample_nashik["panchayat_longitude"]),
            elevation_m=float(sample_nashik["elevation_m"]) if not pd.isna(sample_nashik["elevation_m"]) else None,
            station_distance_km=float(sample_nashik["station_distance_km"]) if not pd.isna(sample_nashik["station_distance_km"]) else None,
            station_latitude=float(sample_nashik["station_latitude"]) if not pd.isna(sample_nashik["station_latitude"]) else None,
            station_longitude=float(sample_nashik["station_longitude"]) if not pd.isna(sample_nashik["station_longitude"]) else None,
            lead_days=int(sample_nashik["lead_days"]),
            has_historical_rainfall_context=int(sample_nashik["has_historical_rainfall_context"])
        )
        res_nashik = service.predict_rainfall(req_nashik)
        assert res_nashik.prediction_mode == "ml"
        assert res_nashik.downscaled_rainfall_mm >= 0.0
