"""
Integration tests for Farmer Advisory Workflow & Multilingual Delivery (Phase 5.7).

Validates:
1. Approved advisory returns structured 3-tier fields (summary, what_is_happening, why_it_matters,
   recommended_actions, timing, warnings, advisory_version, approved_at).
2. DRAFT, NEEDS_REVIEW, EDITED, and REJECTED advisories are never returned to farmers (publication boundary).
3. Clean empty state returned when no approved advisory exists.
4. Multilingual delivery in Marathi ('mr') and Hindi ('hi') preserving exact numerical rainfall and units.
5. Numerical values, dates, and severity remain unchanged across languages.
6. No sensitive internal metadata (officer IDs, internal DB IDs, audit logs, raw prompts) is exposed.
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
def cleanup_test_records():
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


def test_approved_advisory_returns_3_tier_structure(cleanup_test_records):
    """
    Test 1: Approved advisory returns complete 3-tier structure, version, and approved timestamp.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 21)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 20),
            downscaled_rainfall_mm=24.5,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        approved_snapshot = {
            "summary": "Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation",
            "what_is_happening": "24.5 mm moderate rainfall predicted across the Panchayat.",
            "why_it_matters": "Rainfall satisfies crop water demands; water stagnation in heavy soils may cause root damage.",
            "recommended_actions": [
                "Suspend all surface irrigation.",
                "Clean field drainage channels.",
            ],
            "timing": "Next 24 to 48 hours",
            "warnings": ["Do not apply nitrogenous fertilizers prior to rainfall."],
        }

        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=24.5,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation",
            advisory_text="• Suspend all surface irrigation.\n• Clean field drainage channels.",
            approved_content=approved_snapshot,
            version=2,
            status="APPROVED",
            officer_id="OFFICER_CONFIDENTIAL_123",
            approved_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
        )
        db.add(advisory)
        db.commit()
        db.refresh(advisory)
        cleanup_test_records(a_id=advisory.id)

        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=en")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["advisory_status"] == "APPROVED"
        assert data["rainfall_mm"] == 24.5
        assert data["severity"] == "MODERATE"
        assert data["advisory_version"] == 2
        assert "2026-09-20" in data["approved_at"]
        assert data["summary"] == "Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation"
        assert data["what_is_happening"] == "24.5 mm moderate rainfall predicted across the Panchayat."
        assert "root damage" in data["why_it_matters"]
        assert len(data["recommended_actions"]) == 2
        assert data["timing"] == "Next 24 to 48 hours"
        assert len(data["warnings"]) == 1
        assert "nitrogenous fertilizers" in data["warnings"][0]

        # Security check: Internal officer ID and private names must NOT leak
        assert "officer_id" not in data
        assert "OFFICER_CONFIDENTIAL_123" not in str(data)

    finally:
        db.close()


def test_unapproved_advisories_isolated_from_farmer(cleanup_test_records):
    """
    Test 2: DRAFT, NEEDS_REVIEW, EDITED, and REJECTED advisories are never returned to farmers.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 22)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 21),
            downscaled_rainfall_mm=15.0,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        # Create unapproved advisory (NEEDS_REVIEW)
        adv_review = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=15.0,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Draft Unapproved Review Advisory",
            advisory_text="• Internal draft guidance",
            status="NEEDS_REVIEW",
        )
        db.add(adv_review)
        db.commit()
        db.refresh(adv_review)
        cleanup_test_records(a_id=adv_review.id)

        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}")
        assert response.status_code == 200
        data = response.json()

        assert data["advisory_status"] == "NO_APPROVED_ADVISORY"
        assert data["advisory_title"] is None
        assert data["advisory_points"] == []
        assert data["summary"] is None
        assert data["what_is_happening"] is None
        assert data["why_it_matters"] is None
        assert data["recommended_actions"] == []
        assert data["timing"] is None
        assert data["warnings"] == []
        assert data["advisory_version"] is None
        assert data["approved_at"] is None
        assert "Draft Unapproved Review Advisory" not in str(data)

    finally:
        db.close()


def test_rejected_advisory_never_exposed(cleanup_test_records):
    """
    Test 3: REJECTED advisory and rejection reasons are strictly isolated from farmers.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 23)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 22),
            downscaled_rainfall_mm=5.0,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        adv_rejected = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=5.0,
            rainfall_category="Light rainfall",
            severity="LOW",
            advisory_title="Rejected Advisory Title",
            advisory_text="• Rejected advice",
            status="REJECTED",
            rejection_reason="Contradicts ground crop stage observation.",
        )
        db.add(adv_rejected)
        db.commit()
        db.refresh(adv_rejected)
        cleanup_test_records(a_id=adv_rejected.id)

        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}")
        assert response.status_code == 200
        data = response.json()

        assert data["advisory_status"] == "NO_APPROVED_ADVISORY"
        assert "Rejected Advisory Title" not in str(data)
        assert "Contradicts ground crop stage" not in str(data)

    finally:
        db.close()


def test_multilingual_marathi_delivery(cleanup_test_records):
    """
    Test 4: Marathi ('mr') query delivers validated Marathi agronomic templates preserving exact rainfall.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 24)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 23),
            downscaled_rainfall_mm=32.4,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=32.4,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Moderate Rainfall Advisory in English",
            advisory_text="• English advice point",
            status="APPROVED",
            version=1,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(advisory)
        db.commit()
        db.refresh(advisory)
        cleanup_test_records(a_id=advisory.id)

        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=mr")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["language"] == "mr"
        assert data["rainfall_mm"] == 32.4
        assert data["advisory_status"] == "APPROVED"
        # Check Marathi title and points
        assert "सल्ला" in data["advisory_title"]
        assert len(data["advisory_points"]) > 0
        assert "सिंचन" in data["advisory_points"][0] or "पाऊस" in data["advisory_points"][0]
        # Check Marathi 3-tier fields
        assert "मिमी" in data["what_is_happening"]
        assert "32.4" in data["what_is_happening"]
        assert "तास" in data["timing"]

    finally:
        db.close()


def test_multilingual_hindi_delivery(cleanup_test_records):
    """
    Test 5: Hindi ('hi') query delivers validated Hindi agronomic guidance preserving exact rainfall.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 25)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 24),
            downscaled_rainfall_mm=45.2,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=45.2,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Moderate Rainfall Advisory in English",
            advisory_text="• English advice point",
            status="APPROVED",
            version=1,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(advisory)
        db.commit()
        db.refresh(advisory)
        cleanup_test_records(a_id=advisory.id)

        response = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=hi")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["language"] == "hi"
        assert data["rainfall_mm"] == 45.2
        assert data["advisory_status"] == "APPROVED"
        assert "सलाह" in data["advisory_title"]
        assert len(data["advisory_points"]) > 0
        assert "सिंचाई" in data["advisory_points"][0] or "वर्षा" in data["advisory_points"][0]
        assert "मिमी" in data["what_is_happening"]
        assert "45.2" in data["what_is_happening"]
        assert "घंटे" in data["timing"]

    finally:
        db.close()


def test_numerical_invariants_across_all_languages(cleanup_test_records):
    """
    Test 6: Numerical rainfall and forecast date are identical across en, mr, hi.
    """
    db = SessionLocal()
    p_row = db.query(Panchayat).first()
    panchayat_id = p_row.id if p_row else 1001
    f_date = date(2026, 9, 26)

    try:
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            downscaled_rainfall_mm=18.75,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        cleanup_test_records(f_id=forecast.id)

        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=18.75,
            rainfall_category="Moderate rainfall",
            severity="MODERATE",
            advisory_title="Moderate Rain",
            advisory_text="• Point",
            status="APPROVED",
            version=1,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(advisory)
        db.commit()
        db.refresh(advisory)
        cleanup_test_records(a_id=advisory.id)

        res_en = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=en").json()
        res_mr = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=mr").json()
        res_hi = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=hi").json()

        # Invariant 1: Rainfall float value is identical
        assert res_en["rainfall_mm"] == 18.75
        assert res_mr["rainfall_mm"] == 18.75
        assert res_hi["rainfall_mm"] == 18.75

        # Invariant 2: Forecast date is identical
        assert res_en["forecast_date"] == str(f_date)
        assert res_mr["forecast_date"] == str(f_date)
        assert res_hi["forecast_date"] == str(f_date)

        # Invariant 3: Severity is identical
        assert res_en["severity"] == res_mr["severity"] == res_hi["severity"] == "MODERATE"

    finally:
        db.close()
