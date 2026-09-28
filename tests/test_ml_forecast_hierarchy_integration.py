"""
GramSevak Automated Test Suite for Phase 3.7: ML / Forecast Integration.

Verifies end-to-end integration of the scalable District -> Block -> Panchayat hierarchy
with the weather forecasting engine and Phase 2 machine learning downscaling pipelines.

Coverage:
1. Authoritative Panchayat spatial & administrative context resolution (Nashik & Pune)
2. Block-level forecast resolution from 'block_forecasts' table
3. Multi-district ML inference (Nashik & Pune) using production models
4. Idempotent persistence in 'downscaled_forecasts' (duplicate protection)
5. ID-driven ML downscale API (/api/v1/forecast/downscale)
6. Forecast generation API (/api/v1/forecast/generate)
7. Stored forecast retrieval (/api/v1/forecast/panchayat/{id})
8. Farmer API compatibility (/api/v1/farmer/panchayat/{id})
9. Controlled error handling (nonexistent panchayat, missing forecast)
10. Security checks: zero secret/database URL leakage in responses
"""

import os
import sys
from datetime import date
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.services.hierarchy_service import (
    HierarchyService,
    PanchayatNotFoundError as HierarchyPanchayatNotFoundError,
)
from src.services.forecast_service import (
    generate_panchayat_forecast,
    PanchayatNotFoundError,
    BlockForecastNotFoundError,
)
from backend.ml.schemas import DownscaleInferenceRequest
from backend.services.ml_prediction_service import MLPredictionService


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


# =====================================================================
# 1. AUTHORITATIVE PANCHAYAT RESOLUTION (NASHIK & PUNE)
# =====================================================================

def test_panchayat_resolution_nashik():
    """Verify Panchayat 1001 resolves to Baglan Block, Nashik District with real coordinates."""
    db = SessionLocal()
    try:
        service = HierarchyService()
        ctx = service.resolve_panchayat_spatial_context(1001, db=db)
        assert ctx["panchayat_id"] == 1001
        assert ctx["panchayat_name"] == "Ajmer Saundane"
        assert ctx["block_name"] == "Baglan"
        assert ctx["district_name"] == "Nashik"
        assert isinstance(ctx["latitude"], float)
        assert 20.0 <= ctx["latitude"] <= 21.0
        assert isinstance(ctx["longitude"], float)
        assert 73.0 <= ctx["longitude"] <= 75.0
        assert isinstance(ctx["elevation_m"], (int, float))
    finally:
        db.close()


def test_panchayat_resolution_pune():
    """Verify Pune Panchayat 185262 resolves to Ambegaon Block, Pune District with real coordinates."""
    db = SessionLocal()
    try:
        service = HierarchyService()
        ctx = service.resolve_panchayat_spatial_context(185262, db=db)
        assert ctx["panchayat_id"] == 185262
        assert ctx["panchayat_name"] == "Ahupe"
        assert ctx["block_name"] == "Ambegaon"
        assert ctx["district_name"] == "Pune"
        assert isinstance(ctx["latitude"], float)
        assert 18.0 <= ctx["latitude"] <= 20.0
        assert isinstance(ctx["longitude"], float)
        assert 73.0 <= ctx["longitude"] <= 75.0
        assert isinstance(ctx["elevation_m"], (int, float))
        assert ctx["elevation_m"] > 0
    finally:
        db.close()


def test_panchayat_resolution_nonexistent():
    """Verify nonexistent Panchayat ID raises PanchayatNotFoundError."""
    db = SessionLocal()
    try:
        service = HierarchyService()
        with pytest.raises(HierarchyPanchayatNotFoundError):
            service.resolve_panchayat_spatial_context(999999, db=db)
    finally:
        db.close()


# =====================================================================
# 2. MULTI-DISTRICT FORECAST GENERATION & ML INFERENCE
# =====================================================================

def test_forecast_generate_nashik(api_client):
    """Test full forecast generation flow for Nashik Panchayat 1001."""
    payload = {
        "panchayat_id": 1001,
        "forecast_date": "2026-09-04",
        "forecast_issue_date": "2026-09-04",
    }
    response = api_client.post("/api/v1/forecast/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["panchayat_id"] == 1001
    assert data["panchayat_name"] == "Ajmer Saundane"
    assert data["block_name"] == "Baglan"
    assert data["district_name"] == "Nashik"
    assert data["forecast_date"] == "2026-09-04"
    assert data["block_forecast_rainfall_mm"] >= 0.0
    assert data["downscaled_rainfall_mm"] >= 0.0
    assert "actual_rainfall_mm" not in data


def test_forecast_generate_pune(api_client):
    """Test full forecast generation flow for Pune Panchayat 185262."""
    payload = {
        "panchayat_id": 185262,
        "forecast_date": "2026-09-23",
        "forecast_issue_date": "2026-09-22",
    }
    response = api_client.post("/api/v1/forecast/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["panchayat_id"] == 185262
    assert data["panchayat_name"] == "Ahupe"
    assert data["block_name"] == "Ambegaon"
    assert data["district_name"] == "Pune"
    assert data["forecast_date"] == "2026-09-23"
    assert data["lead_days"] == 1
    assert data["block_forecast_rainfall_mm"] == 5.8
    assert data["downscaled_rainfall_mm"] >= 0.0
    assert "actual_rainfall_mm" not in data


# =====================================================================
# 3. IDEMPOTENT PERSISTENCE & DUPLICATE PROTECTION
# =====================================================================

def test_forecast_generate_idempotency(api_client):
    """
    Verify repeated forecast generation for the same Panchayat, forecast date,
    issue date, and model version does not create uncontrolled duplicate records.
    """
    payload = {
        "panchayat_id": 185262,
        "forecast_date": "2026-09-23",
        "forecast_issue_date": "2026-09-22",
    }

    # First call
    res1 = api_client.post("/api/v1/forecast/generate", json=payload)
    assert res1.status_code == 200

    # Second call
    res2 = api_client.post("/api/v1/forecast/generate", json=payload)
    assert res2.status_code == 200

    # Third call
    res3 = api_client.post("/api/v1/forecast/generate", json=payload)
    assert res3.status_code == 200

    # Verify database count
    db = SessionLocal()
    try:
        count = (
            db.query(DownscaledForecast)
            .filter(
                DownscaledForecast.panchayat_id == 185262,
                DownscaledForecast.forecast_date == date(2026, 9, 23),
                DownscaledForecast.forecast_issue_date == date(2026, 9, 22),
            )
            .count()
        )
        assert count == 1, f"Expected exactly 1 idempotent record, found {count}"
    finally:
        db.close()


# =====================================================================
# 4. ID-DRIVEN ML DOWNSCALING INFERENCE (/api/v1/forecast/downscale)
# =====================================================================

def test_ml_downscale_id_driven_pune(api_client):
    """
    Verify /api/v1/forecast/downscale resolves spatial context and block forecast
    automatically when called with only stable Panchayat ID and forecast dates.
    """
    payload = {
        "panchayat_id": 185262,
        "forecast_date": "2026-09-23",
        "forecast_issue_date": "2026-09-22",
    }
    response = api_client.post("/api/v1/forecast/downscale", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["panchayat_id"] == "185262" or data["panchayat_id"] == 185262
    assert data["forecast_date"] == "2026-09-23"
    assert data["lead_days"] == 1
    assert data["block_forecast_rainfall_mm"] == 5.8
    assert data["downscaled_rainfall_mm"] >= 0.0
    assert data["prediction_mode"] == "ml"
    assert data["model_name"] == "xgboost_downscaler"
    assert data["model_version"] == "2.5.0"


def test_ml_downscale_random_forest_override(api_client):
    """Verify model_name override to random_forest works for Pune Panchayat."""
    payload = {
        "panchayat_id": 185262,
        "forecast_date": "2026-09-23",
        "forecast_issue_date": "2026-09-22",
    }
    response = api_client.post("/api/v1/forecast/downscale?model_name=random_forest", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["downscaled_rainfall_mm"] >= 0.0
    assert data["prediction_mode"] == "ml"
    assert data["model_name"] == "random_forest_downscaler"
    assert data["model_version"] == "2.4.0"


# =====================================================================
# 5. RETRIEVAL & FARMER API INTEGRATION
# =====================================================================

def test_retrieval_and_farmer_api(api_client):
    """Verify stored forecast is retrievable via both officer and farmer endpoints."""
    panchayat_id = 185262
    target_date = "2026-09-23"

    # Officer forecast retrieval
    get_res = api_client.get(f"/api/v1/forecast/panchayat/{panchayat_id}?forecast_date={target_date}")
    assert get_res.status_code == 200, get_res.text
    officer_data = get_res.json()
    assert officer_data["panchayat_name"] == "Ahupe"
    assert officer_data["district_name"] == "Pune"
    assert officer_data["block_name"] == "Ambegaon"

    # Farmer weather & advisory retrieval
    farmer_res = api_client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={target_date}")
    assert farmer_res.status_code == 200, farmer_res.text
    farmer_data = farmer_res.json()
    assert farmer_data["panchayat_name"] == "Ahupe"
    assert farmer_data["district_name"] == "Pune"
    assert farmer_data["block_name"] == "Ambegaon"
    assert farmer_data["forecast_date"] == target_date
    assert farmer_data["rainfall_mm"] == round(float(officer_data["downscaled_rainfall_mm"]), 2)


# =====================================================================
# 6. ERROR HANDLING & SECURITY
# =====================================================================

def test_forecast_generate_nonexistent_panchayat_404(api_client):
    """Verify 404 is returned for an invalid Panchayat ID."""
    response = api_client.post(
        "/api/v1/forecast/generate",
        json={
            "panchayat_id": 999999,
            "forecast_date": "2026-09-23",
            "forecast_issue_date": "2026-09-22",
        }
    )
    assert response.status_code == 404


def test_forecast_generate_unavailable_forecast_404(api_client):
    """Verify 404 is returned when numerical block forecast is not available for a date."""
    response = api_client.post(
        "/api/v1/forecast/generate",
        json={
            "panchayat_id": 185262,
            "forecast_date": "2099-01-01",
            "forecast_issue_date": "2099-01-01",
        }
    )
    assert response.status_code == 404


def test_security_sanitization(api_client):
    """Verify responses never expose Supabase credentials, DB connection URLs, or file paths."""
    response = api_client.post(
        "/api/v1/forecast/downscale",
        json={
            "panchayat_id": 185262,
            "forecast_date": "2026-09-23",
            "forecast_issue_date": "2026-09-22",
        }
    )
    body = response.text.lower()
    forbidden = ["postgres://", "postgresql://", "service_role", "supabase_key", "c:\\", "/users/"]
    for token in forbidden:
        assert token not in body, f"Security leak detected: {token}"
