"""
Day 4 — Step 13: Backend and ML Test Suite

Tests all 14 core backend, API, service, and ML validation functionalities:
1. Health endpoint.
2. Database health endpoint.
3. Panchayat list endpoint.
4. Panchayat detail endpoint.
5. Unknown Panchayat returns 404.
6. Forecast generation with valid input.
7. Missing block forecast handling (HTTP 404).
8. Missing Panchayat handling (HTTP 404).
9. Invalid dates validation (HTTP 422).
10. Negative model output handling (clamped to 0.0).
11. NaN prediction handling (rejected/handled safely).
12. Forecast retrieval (GET endpoint).
13. Database persistence (stored record verification).
14. Model metadata response (model_name, model_version, confidence).
"""

import math
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from src.services.forecast_service import (
    PanchayatNotFoundError,
    BlockForecastNotFoundError,
    MissingFeatureError,
    ModelUnavailableError,
)
from src.validation.forecast_validation import (
    validate_forecast_output,
    ForecastValidationError,
)
from src.services.model_service import ModelService


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# =====================================================================
# 1. Health endpoint
# =====================================================================
def test_1_health_endpoint(client):
    """
    Test 1: Health endpoint returns 200 OK and healthy status.
    """
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "ok"

    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == "ok"


# =====================================================================
# 2. Database health endpoint
# =====================================================================
def test_2_database_health_endpoint(client):
    """
    Test 2: Database health endpoint returns 200 OK and database connectivity status.
    """
    res = client.get("/api/v1/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert body["database"]["connected"] is True


# =====================================================================
# 3. Panchayat list endpoint
# =====================================================================
def test_3_panchayat_list_endpoint(client):
    """
    Test 3: Panchayat list endpoint returns paginated panchayats with expected fields.
    """
    res = client.get("/api/v1/panchayats?page=1&page_size=10")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert len(body["items"]) <= 10
    if len(body["items"]) > 0:
        first = body["items"][0]
        for field in ["panchayat_id", "lgd_code", "panchayat_name", "block_name", "district_name", "latitude", "longitude", "elevation_m"]:
            assert field in first


# =====================================================================
# 4. Panchayat detail endpoint
# =====================================================================
def test_4_panchayat_detail_endpoint(client):
    """
    Test 4: Panchayat detail endpoint returns single panchayat data.
    """
    res = client.get("/api/v1/panchayats/1001")
    assert res.status_code == 200
    body = res.json()
    assert body["panchayat_id"] == 1001
    assert body["panchayat_name"] == "Ajmer Saundane"
    assert body["block_name"] == "Baglan"
    assert body["district_name"] == "Nashik"


# =====================================================================
# 5. Unknown Panchayat returns 404
# =====================================================================
def test_5_unknown_panchayat_returns_404(client):
    """
    Test 5: Non-existent panchayat_id returns HTTP 404.
    """
    res = client.get("/api/v1/panchayats/999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# =====================================================================
# 6. Forecast generation with valid input
# =====================================================================
def test_6_forecast_generation_valid_input(client):
    """
    Test 6: Forecast generation returns HTTP 200 with downscaled rainfall.
    """
    payload = {
        "panchayat_id": 1001,
        "forecast_date": "2026-05-09",
        "forecast_issue_date": "2026-05-09",
    }
    res = client.post("/api/v1/forecast/generate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["panchayat_id"] == 1001
    assert body["lead_days"] == 0
    assert isinstance(body["downscaled_rainfall_mm"], (int, float))
    assert body["downscaled_rainfall_mm"] >= 0.0


# =====================================================================
# 7. Missing block forecast handling
# =====================================================================
def test_7_missing_block_forecast_handling(client):
    """
    Test 7: Missing block forecast returns HTTP 404.
    """
    with patch(
        "backend.app.api.v1.endpoints.forecast.generate_panchayat_forecast",
        side_effect=BlockForecastNotFoundError("No block forecast found for Baglan on 2030-01-01."),
    ):
        payload = {
            "panchayat_id": 1001,
            "forecast_date": "2030-01-01",
            "forecast_issue_date": "2030-01-01",
        }
        res = client.post("/api/v1/forecast/generate", json=payload)
        assert res.status_code == 404
        assert "no block forecast found" in res.json()["detail"].lower()


# =====================================================================
# 8. Missing Panchayat handling
# =====================================================================
def test_8_missing_panchayat_handling(client):
    """
    Test 8: Missing panchayat returns HTTP 404.
    """
    payload = {
        "panchayat_id": 999999,
        "forecast_date": "2026-05-09",
        "forecast_issue_date": "2026-05-09",
    }
    res = client.post("/api/v1/forecast/generate", json=payload)
    assert res.status_code == 404
    detail = res.json()["detail"].lower()
    assert "found" in detail and "not" in detail


# =====================================================================
# 9. Invalid dates validation
# =====================================================================
def test_9_invalid_dates_validation(client):
    """
    Test 9: Invalid dates (forecast_date prior to issue date) return HTTP 422.
    """
    payload = {
        "panchayat_id": 1001,
        "forecast_date": "2026-05-01",
        "forecast_issue_date": "2026-05-09",
    }
    res = client.post("/api/v1/forecast/generate", json=payload)
    assert res.status_code == 422


# =====================================================================
# 10. Negative model output handling
# =====================================================================
def test_10_negative_model_output_handling():
    """
    Test 10: Negative model predictions are clamped to 0.0 with raw diagnostics preserved.
    """
    res = validate_forecast_output(-4.52)
    assert res.downscaled_rainfall_mm == 0.0
    assert res.raw_predicted_rainfall_mm == -4.52
    assert res.is_clamped is True

    # ModelService level check
    ms = ModelService()
    # Mock model predict to return negative value
    mock_model = MagicMock()
    mock_model.predict.return_value = [-3.14]
    with patch.object(ms, "model", mock_model):
        res_dict = ms.predict(
            block_forecast_rainfall_mm=5.0,
            panchayat_latitude=20.0,
            panchayat_longitude=74.0,
            elevation_m=500.0,
            station_distance_km=10.0,
            lead_days=1,
            month=9,
            day_of_year=250,
        )
        assert res_dict["downscaled_rainfall_mm"] == 0.0
        assert res_dict["raw_predicted_rainfall_mm"] == -3.14


# =====================================================================
# 11. NaN prediction handling
# =====================================================================
def test_11_nan_prediction_handling():
    """
    Test 11: NaN and Infinite predictions are rejected and raise ForecastValidationError.
    """
    with pytest.raises(ForecastValidationError) as exc:
        validate_forecast_output(float("nan"))
    assert "nan" in str(exc.value).lower()

    with pytest.raises(ForecastValidationError) as exc_inf:
        validate_forecast_output(float("inf"))
    assert "finite" in str(exc_inf.value).lower()


# =====================================================================
# 12. Forecast retrieval
# =====================================================================
def test_12_forecast_retrieval(client):
    """
    Test 12: Forecast retrieval endpoint retrieves stored forecast by panchayat_id.
    """
    # Seed a forecast
    client.post(
        "/api/v1/forecast/generate",
        json={
            "panchayat_id": 1001,
            "forecast_date": "2026-05-09",
            "forecast_issue_date": "2026-05-09",
        },
    )

    # Retrieve by panchayat_id
    res = client.get("/api/v1/forecast/panchayat/1001?forecast_date=2026-05-09")
    assert res.status_code == 200
    body = res.json()
    assert body["panchayat_id"] == 1001
    assert body["forecast_date"] == "2026-05-09"
    assert isinstance(body["downscaled_rainfall_mm"], (int, float))


# =====================================================================
# 13. Database persistence
# =====================================================================
def test_13_database_persistence(client):
    """
    Test 13: Generated forecast is correctly persisted in downscaled_forecasts table.
    """
    target_date = "2026-09-04"
    gen_res = client.post(
        "/api/v1/forecast/generate",
        json={
            "panchayat_id": 1001,
            "forecast_date": target_date,
            "forecast_issue_date": "2026-09-04",
        },
    )
    assert gen_res.status_code == 200
    api_downscaled = gen_res.json()["downscaled_rainfall_mm"]

    db = SessionLocal()
    try:
        record = (
            db.query(DownscaledForecast)
            .filter(
                DownscaledForecast.panchayat_id == 1001,
                DownscaledForecast.forecast_date == target_date,
            )
            .order_by(DownscaledForecast.id.desc())
            .first()
        )
        assert record is not None
        assert float(record.downscaled_rainfall_mm) == pytest.approx(api_downscaled, rel=1e-4)
        assert record.model_name == "XGBoost Regressor"
        assert record.model_version == "v1.0.0"
    finally:
        db.close()


# =====================================================================
# 14. Model metadata response
# =====================================================================
def test_14_model_metadata_response(client):
    """
    Test 14: Model metadata fields (model_name, model_version, confidence) are present and valid.
    """
    res = client.get("/api/v1/forecast/panchayat/1001?forecast_date=2026-05-09")
    assert res.status_code == 200
    body = res.json()
    assert "model_name" in body
    assert body["model_name"] == "XGBoost Regressor"
    assert "model_version" in body
    assert body["model_version"] == "v1.0.0"
    assert "confidence" in body
    assert body["confidence"] is None  # Calibrated null per Day 4 Step 9 requirement


# =====================================================================
# 15. OpenAPI documentation review
# =====================================================================
def test_15_openapi_documentation_review(client):
    """
    Test 15: Verify /docs and /openapi.json are accessible, all Day 4 endpoints
    have proper summaries, descriptions, response schemas, and zero secrets are leaked.
    """
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200
    assert "swagger-ui" in res_docs.text.lower()

    res_openapi = client.get("/openapi.json")
    assert res_openapi.status_code == 200
    schema = res_openapi.json()
    paths = schema.get("paths", {})

    expected_endpoints = [
        ("/health", "get"),
        ("/health/db", "get"),
        ("/api/v1/health", "get"),
        ("/api/v1/health/db", "get"),
        ("/api/v1/panchayats", "get"),
        ("/api/v1/panchayats/{panchayat_id}", "get"),
        ("/api/v1/forecast/generate", "post"),
        ("/api/v1/forecast/panchayat/{panchayat_id}", "get"),
    ]

    for path, method in expected_endpoints:
        assert path in paths, f"Missing endpoint in OpenAPI: {path}"
        assert method in paths[path], f"Missing {method} for endpoint {path}"
        op = paths[path][method]
        assert "summary" in op and op["summary"], f"Summary missing for {method.upper()} {path}"
        assert "description" in op and op["description"], f"Description missing for {method.upper()} {path}"
        assert "responses" in op and op["responses"], f"Responses missing for {method.upper()} {path}"

    # Verify zero credential leakage
    schema_str = json.dumps(schema).lower()
    for forbidden in ["postgres:", "localhost:5432", "supabase_key", "service_role"]:
        assert forbidden not in schema_str, f"Secret leaked in OpenAPI schema: {forbidden}"


# =====================================================================
# 16. Database integration test (full persistence & integrity flow)
# =====================================================================
def test_16_database_integration_persistence_flow(client):
    """
    Test 16: Verify full forecast persistence flow for a real Nashik Panchayat:
    1. Read Panchayat info.
    2. Read block forecast.
    3. Generate ML prediction.
    4. Verify insertion into downscaled_forecasts.
    5. Retrieve inserted record.
    6. Compare API and DB results field-by-field.
    7. Verify historical actual rainfall and block forecast values were NOT overwritten.
    """
    from datetime import date
    from backend.app.models.panchayat_weather import PanchayatWeatherData
    from backend.app.models.downscaled_forecast import DownscaledForecast

    target_panchayat_id = 1001
    target_forecast_date = "2026-09-04"
    target_issue_date = "2026-09-04"

    # 1. Read Panchayat info
    p_res = client.get(f"/api/v1/panchayats/{target_panchayat_id}")
    assert p_res.status_code == 200
    p_info = p_res.json()
    assert p_info["panchayat_name"] == "Ajmer Saundane"

    # Capture historical before-state
    db = SessionLocal()
    try:
        hist_before = db.query(PanchayatWeatherData).filter(PanchayatWeatherData.panchayat_id == target_panchayat_id).first()
        hist_actual_before = float(hist_before.actual_rainfall_mm) if hist_before and hist_before.actual_rainfall_mm is not None else None
        hist_forecast_before = float(hist_before.block_forecast_rainfall_mm) if hist_before and hist_before.block_forecast_rainfall_mm is not None else None
    finally:
        db.close()

    # 2 & 3. Generate ML prediction via API
    gen_res = client.post(
        "/api/v1/forecast/generate",
        json={
            "panchayat_id": target_panchayat_id,
            "forecast_date": target_forecast_date,
            "forecast_issue_date": target_issue_date,
        },
    )
    assert gen_res.status_code == 200
    api_gen = gen_res.json()

    # 4 & 5. Retrieve persisted record from DB and GET endpoint
    db = SessionLocal()
    try:
        db_record = (
            db.query(DownscaledForecast)
            .filter(
                DownscaledForecast.panchayat_id == target_panchayat_id,
                DownscaledForecast.forecast_date == target_forecast_date,
            )
            .order_by(DownscaledForecast.id.desc())
            .first()
        )
        assert db_record is not None

        ret_res = client.get(f"/api/v1/forecast/panchayat/{target_panchayat_id}?forecast_date={target_forecast_date}")
        assert ret_res.status_code == 200
        api_ret = ret_res.json()

        # 6. Compare API result and database result field-by-field
        assert api_gen["panchayat_id"] == db_record.panchayat_id == api_ret["panchayat_id"]
        assert str(api_gen["forecast_date"]) == str(db_record.forecast_date) == str(api_ret["forecast_date"])
        assert str(api_gen["forecast_issue_date"]) == str(db_record.forecast_issue_date) == str(api_ret["forecast_issue_date"])
        assert round(float(api_gen["block_forecast_rainfall_mm"]), 2) == round(float(db_record.block_forecast_rainfall_mm), 2) == round(float(api_ret["block_forecast_rainfall_mm"]), 2)
        assert round(float(api_gen["downscaled_rainfall_mm"]), 4) == round(float(db_record.downscaled_rainfall_mm), 4) == round(float(api_ret["downscaled_rainfall_mm"]), 4)
        assert api_gen["model_name"] == db_record.model_name == api_ret["model_name"]
        assert api_gen["model_version"] == db_record.model_version == api_ret["model_version"]
        assert db_record.confidence is None

        # 7. Check integrity (no overwrite of historical records)
        hist_after = db.query(PanchayatWeatherData).filter(PanchayatWeatherData.panchayat_id == target_panchayat_id).first()
        hist_actual_after = float(hist_after.actual_rainfall_mm) if hist_after and hist_after.actual_rainfall_mm is not None else None
        hist_forecast_after = float(hist_after.block_forecast_rainfall_mm) if hist_after and hist_after.block_forecast_rainfall_mm is not None else None

        assert hist_actual_before == hist_actual_after
        assert hist_forecast_before == hist_forecast_after
    finally:
        db.close()


