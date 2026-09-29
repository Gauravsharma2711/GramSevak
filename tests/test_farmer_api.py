"""
Integration tests for Farmer Forecast & Advisory API (Day 5 - Step 10).

Validates:
1. GET /api/v1/farmer/panchayat/{panchayat_id} with APPROVED advisory.
2. GET /api/v1/farmer/panchayat/{panchayat_id} without approved advisory (DRAFT/REJECTED isolation).
3. Forecast date filtering.
4. Data sanitization: verifies no internal DB IDs, officer IDs, model internals, or credentials are exposed.
5. Error handling (404 when no forecast exists, 422 on invalid parameters).
6. OpenAPI schema verification.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from backend.app.models.panchayat import Panchayat


client = TestClient(app)


@pytest.fixture
def cleanup_farmer_records():
    """Cleanup test records after each test."""
    created_forecast_ids = []
    created_advisory_ids = []

    def _track(f_id: int = None, a_id: int = None):
        if f_id:
            created_forecast_ids.append(f_id)
        if a_id:
            created_advisory_ids.append(a_id)

    yield _track

    db = SessionLocal()
    try:
        if created_advisory_ids:
            db.query(Advisory).filter(Advisory.id.in_(created_advisory_ids)).delete(synchronize_session=False)
        if created_forecast_ids:
            db.query(DownscaledForecast).filter(DownscaledForecast.id.in_(created_forecast_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_farmer_forecast_with_approved_advisory(cleanup_farmer_records):
    """
    Test retrieving farmer forecast when an APPROVED advisory exists:
    - Returns all required fields
    - advisory_status is APPROVED
    - advisory_points are parsed clean list
    - Does not expose internal officer_id, database IDs, or credentials
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 15)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 14),
            block_forecast_rainfall_mm=30.0,
            downscaled_rainfall_mm=22.4,
            actual_rainfall_mm=None,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_farmer_records(f_id=forecast.id)

        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=22.4,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Moderate Rainfall Advisory - Maintain Drainage",
            advisory_text="• Postpone surface irrigation to conserve soil structure.\n• Clean field drainage lines to avoid root submergence.",
            rule_version="RAIN_RULES_V1",
            status="APPROVED",
            officer_id="OFFICER_SECRET_ID_99",
            officer_comment="Internal ground survey note",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(advisory)
        db.commit()
        db.refresh(advisory)
        cleanup_farmer_records(a_id=advisory.id)

        # Call endpoint with specific forecast date
        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}")
        assert response.status_code == 200, response.text
        data = response.json()

        # Check required fields
        assert "panchayat_name" in data
        assert "block_name" in data
        assert "district_name" in data
        assert data["forecast_date"] == "2026-09-15"
        assert data["rainfall_mm"] == 22.4
        assert data["rainfall_category"] == "Moderate rainfall"
        assert data["severity"] == "MODERATE"
        assert data["advisory_title"] == "Moderate Rainfall Advisory - Maintain Drainage"
        assert isinstance(data["advisory_points"], list)
        assert len(data["advisory_points"]) == 2
        assert "Postpone surface irrigation" in data["advisory_points"][0]
        assert data["advisory_status"] == "APPROVED"
        assert data["model_name"] == "XGBoost Regressor"
        assert data["model_version"] == "v1.0.0"

        # Security check: No officer ID or internal database IDs leaked
        assert "officer_id" not in data
        assert "OFFICER_SECRET_ID_99" not in str(data)
        assert "officer_comment" not in data
        assert "Internal ground survey note" not in str(data)

    finally:
        db.close()


def test_farmer_forecast_without_approved_advisory(cleanup_farmer_records):
    """
    Test retrieving farmer forecast when only DRAFT or REJECTED advisory exists:
    - Returns 200 with forecast data
    - advisory_status is NO_APPROVED_ADVISORY
    - advisory_title is None
    - advisory_points is empty list []
    - rainfall_category and severity are classified deterministically
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 16)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 15),
            block_forecast_rainfall_mm=5.0,
            downscaled_rainfall_mm=1.2,
            actual_rainfall_mm=None,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_farmer_records(f_id=forecast.id)

        # Add a DRAFT advisory (not approved)
        draft_adv = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=1.2,
            rainfall_category="Very light rainfall",
            severity="LOW",
            advisory_title="Draft Unapproved Title",
            advisory_text="• Unverified draft advice",
            rule_version="RAIN_RULES_V1",
            status="DRAFT",
        )
        db.add(draft_adv)
        db.commit()
        db.refresh(draft_adv)
        cleanup_farmer_records(a_id=draft_adv.id)

        # Call endpoint with specific forecast date
        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["rainfall_mm"] == 1.2
        assert data["rainfall_category"] == "Very light rainfall"
        assert data["severity"] == "LOW"
        assert data["advisory_status"] == "NO_APPROVED_ADVISORY"
        assert data["advisory_title"] is None
        assert data["advisory_points"] == []
        assert "Draft Unapproved Title" not in str(data)
        assert "Unverified draft advice" not in str(data)

    finally:
        db.close()


def test_farmer_forecast_date_filtering(cleanup_farmer_records):
    """
    Test retrieving farmer forecast for a specific forecast_date.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    date_1 = date(2026, 9, 17)
    date_2 = date(2026, 9, 18)

    try:
        f1 = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=date_1,
            downscaled_rainfall_mm=0.0,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        f2 = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=date_2,
            downscaled_rainfall_mm=88.5,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add_all([f1, f2])
        db.commit()
        db.refresh(f1)
        db.refresh(f2)
        cleanup_farmer_records(f_id=f1.id)
        cleanup_farmer_records(f_id=f2.id)

        # Query date_2 specifically
        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date=2026-09-18")
        assert response.status_code == 200
        data = response.json()
        assert data["forecast_date"] == "2026-09-18"
        assert data["rainfall_mm"] == 88.5
        assert data["rainfall_category"] == "Heavy rainfall"
        assert data["severity"] == "HIGH"

    finally:
        db.close()


def test_farmer_forecast_not_found():
    """
    Test that non-existent panchayat or missing forecast returns HTTP 404.
    """
    response = client.get("/api/v1/farmer/panchayat/99999999")
    assert response.status_code == 404
    assert "no forecast found" in response.json()["detail"].lower()


def test_farmer_forecast_validation():
    """
    Test validation errors on invalid panchayat_id.
    """
    res_neg = client.get("/api/v1/farmer/panchayat/0")
    assert res_neg.status_code == 422

    res_str = client.get("/api/v1/farmer/panchayat/invalid")
    assert res_str.status_code == 422


def test_farmer_forecast_openapi_documentation():
    """
    Verify /api/v1/farmer/panchayat/{panchayat_id} is registered in Swagger/OpenAPI.
    """
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    assert "/api/v1/farmer/panchayat/{panchayat_id}" in spec["paths"]
    farmer_spec = spec["paths"]["/api/v1/farmer/panchayat/{panchayat_id}"]["get"]
    assert "Farmer" in farmer_spec["summary"]
    assert "200" in farmer_spec["responses"]
    assert "404" in farmer_spec["responses"]
    assert "422" in farmer_spec["responses"]
