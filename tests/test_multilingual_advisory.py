"""
Unit and Integration Tests for Multilingual Advisory Structure (Day 5 - Step 11).

Verifies:
1. Canonical advisory representation with English (en) as the primary stored version.
2. Multilingual deterministic rule rendering for English (en), Marathi (mr), and Hindi (hi).
3. Zero LLM usage (100% deterministic template interpolation).
4. Response metadata: language, available_languages, and language_status.
5. Robust fallback behavior for unsupported or malformed language codes.
6. API endpoint localization across Farmer and Advisory endpoints.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.advisory import Advisory
from src.advisory.localization import (
    SupportedLanguage,
    DEFAULT_LANGUAGE,
    ALL_SUPPORTED_LANGUAGES,
    LANGUAGE_METADATA,
    MULTILINGUAL_RULE_CATALOG,
    get_localized_rule_content,
)
from src.advisory.advisory_engine import (
    AdvisoryEngine,
    generate_agricultural_advisory,
    ADVISORY_RULES_REGISTRY,
    AdvisoryOutput,
    RULE_VERSION,
)


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """SQLAlchemy Session fixture with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# 1. LOCALIZATION MODULE TESTS
# =============================================================================
def test_multilingual_rule_catalog_completeness():
    """All 7 canonical rule IDs must have English, Marathi, and Hindi translations."""
    canonical_rules = [
        "RAIN_NO_SIGNIFICANT_V1",
        "RAIN_VERY_LIGHT_V1",
        "RAIN_LIGHT_V1",
        "RAIN_MODERATE_V1",
        "RAIN_HEAVY_V1",
        "RAIN_VERY_HEAVY_V1",
        "RAIN_EXTREMELY_HEAVY_V1",
    ]

    for rule_id in canonical_rules:
        assert rule_id in MULTILINGUAL_RULE_CATALOG, f"Rule '{rule_id}' missing in catalog."
        rule_dict = MULTILINGUAL_RULE_CATALOG[rule_id]
        for lang in ["en", "mr", "hi"]:
            assert lang in rule_dict, f"Language '{lang}' missing for rule '{rule_id}'."
            content = rule_dict[lang]
            assert content.title_template and len(content.title_template) > 5
            assert len(content.advisory_points_templates) >= 3


def test_language_metadata_readiness():
    """Validate review status and readiness metadata."""
    assert "en" in LANGUAGE_METADATA
    assert "mr" in LANGUAGE_METADATA
    assert "hi" in LANGUAGE_METADATA

    assert LANGUAGE_METADATA["en"]["status"] == "VERIFIED_PRIMARY"
    assert LANGUAGE_METADATA["mr"]["status"] == "STRUCTURED_REVIEWED"
    assert LANGUAGE_METADATA["hi"]["status"] == "STRUCTURED_REVIEWED"


def test_get_localized_rule_content_valid_languages():
    """Test retrieval for English, Marathi, and Hindi."""
    en_content = get_localized_rule_content("RAIN_MODERATE_V1", language="en")
    assert "Moderate Rainfall Advisory" in en_content.title_template

    mr_content = get_localized_rule_content("RAIN_MODERATE_V1", language="mr")
    assert "मध्यम पाऊस सल्ला" in mr_content.title_template

    hi_content = get_localized_rule_content("RAIN_MODERATE_V1", language="hi")
    assert "मध्यम वर्षा सलाह" in hi_content.title_template


def test_get_localized_rule_content_fallback():
    """Unsupported language codes must fall back to English gracefully."""
    fallback_content = get_localized_rule_content("RAIN_HEAVY_V1", language="fr")
    assert "Heavy Rainfall Warning" in fallback_content.title_template

    fallback_german = get_localized_rule_content("RAIN_HEAVY_V1", language="de")
    assert "Heavy Rainfall Warning" in fallback_german.title_template


def test_get_localized_rule_content_invalid_rule_id():
    """Invalid rule ID must raise KeyError."""
    with pytest.raises(KeyError):
        get_localized_rule_content("INVALID_RULE_XYZ", language="en")


# =============================================================================
# 2. ADVISORY ENGINE MULTILINGUAL RENDERING TESTS
# =============================================================================
def test_advisory_engine_english_rendering():
    """Test canonical English generation."""
    output = generate_agricultural_advisory(
        rainfall_mm=25.0,
        panchayat_name="Saundane",
        block_name="Baglan",
        forecast_date="2026-09-08",
        language="en",
    )
    assert isinstance(output, AdvisoryOutput)
    assert output.language == "en"
    assert "en" in output.available_languages
    assert "mr" in output.available_languages
    assert "hi" in output.available_languages
    assert "Moderate Rainfall Advisory for Saundane" in output.advisory_title
    assert any("drainage" in p.lower() for p in output.advisory_points)


def test_advisory_engine_marathi_rendering():
    """Test deterministic Marathi rendering."""
    output = generate_agricultural_advisory(
        rainfall_mm=25.0,
        panchayat_name="Saundane",
        block_name="Baglan",
        forecast_date="2026-09-08",
        language="mr",
    )
    assert output.language == "mr"
    assert "Saundane साठी मध्यम पाऊस सल्ला" in output.advisory_title
    assert any("सिंचन" in p for p in output.advisory_points)


def test_advisory_engine_hindi_rendering():
    """Test deterministic Hindi rendering."""
    output = generate_agricultural_advisory(
        rainfall_mm=25.0,
        panchayat_name="Saundane",
        block_name="Baglan",
        forecast_date="2026-09-08",
        language="hi",
    )
    assert output.language == "hi"
    assert "Saundane के लिए मध्यम वर्षा सलाह" in output.advisory_title
    assert any("सिंचाई" in p for p in output.advisory_points)


def test_advisory_engine_unsupported_language_fallback():
    """AdvisoryEngine should gracefully fall back to English for unknown language."""
    output = generate_agricultural_advisory(
        rainfall_mm=5.0,
        panchayat_name="Saundane",
        block_name="Baglan",
        forecast_date="2026-09-08",
        language="es",
    )
    assert output.language == "en"
    assert "Light Rainfall Advisory for Saundane" in output.advisory_title


# =============================================================================
# 3. FARMER API MULTILINGUAL ENDPOINT TESTS
# =============================================================================
def test_farmer_api_multilingual_responses(client, db_session: Session):
    """Farmer endpoint should return localized response based on lang query param."""
    panchayat_id = 1001
    f_date = date(2026, 9, 8)

    # Clean prior test rows if any
    db_session.rollback()
    db_session.query(Advisory).filter(Advisory.panchayat_id == panchayat_id, Advisory.forecast_date == f_date).delete(synchronize_session=False)
    db_session.query(DownscaledForecast).filter(DownscaledForecast.panchayat_id == panchayat_id, DownscaledForecast.forecast_date == f_date).delete(synchronize_session=False)
    db_session.commit()

    try:
        # 1. Insert forecast
        forecast = DownscaledForecast(
            panchayat_id=panchayat_id,
            forecast_date=f_date,
            forecast_issue_date=date(2026, 9, 7),
            downscaled_rainfall_mm=85.0,
            model_name="XGBoost Regressor",
            model_version="v1.0.0",
        )
        db_session.add(forecast)
        db_session.commit()
        db_session.refresh(forecast)

        # 2. Insert APPROVED canonical English advisory
        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=forecast.id,
            forecast_date=f_date,
            rainfall_mm=85.0,
            rainfall_category="Heavy rainfall",
            severity="HIGH",
            advisory_title="Heavy Rainfall Warning for Panchayat-1001 - Excess Water Drainage & Crop Protection",
            advisory_text="• Suspend all irrigation.\n• Clear drainage furrows.",
            rule_version=RULE_VERSION,
            status="APPROVED",
            officer_id="OFFICER_SATANA_01",
            officer_comment="Approved for release",
        )
        db_session.add(advisory)
        db_session.commit()

        # --- Test English (Default) ---
        res_en = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=en")
        assert res_en.status_code == 200
        data_en = res_en.json()
        assert data_en["language"] == "en"
        assert data_en["available_languages"] == ["en", "mr", "hi"]
        assert data_en["language_status"] == "VERIFIED_PRIMARY"
        assert "Heavy Rainfall Warning" in data_en["advisory_title"]

        # --- Test Marathi ---
        res_mr = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=mr")
        assert res_mr.status_code == 200
        data_mr = res_mr.json()
        assert data_mr["language"] == "mr"
        assert data_mr["language_status"] == "STRUCTURED_REVIEWED"
        assert "मुसळधार पाऊस इशारा" in data_mr["advisory_title"]
        assert any("सिंचन" in p for p in data_mr["advisory_points"])

        # --- Test Hindi ---
        res_hi = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=hi")
        assert res_hi.status_code == 200
        data_hi = res_hi.json()
        assert data_hi["language"] == "hi"
        assert data_hi["language_status"] == "STRUCTURED_REVIEWED"
        assert "बारीक" in data_hi["advisory_title"] or "वर्षा" in data_hi["advisory_title"] or "बारिश" in data_hi["advisory_title"]
        assert any("सिंचाई" in p for p in data_hi["advisory_points"])

        # --- Test Unsupported Lang Fallback ---
        res_fallback = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}&lang=japanese")
        assert res_fallback.status_code == 200
        data_fallback = res_fallback.json()
        assert data_fallback["language"] == "en"
        assert "Heavy Rainfall Warning" in data_fallback["advisory_title"]

    finally:
        db_session.rollback()
        db_session.query(Advisory).filter(Advisory.panchayat_id == panchayat_id, Advisory.forecast_date == f_date).delete(synchronize_session=False)
        db_session.query(DownscaledForecast).filter(DownscaledForecast.panchayat_id == panchayat_id, DownscaledForecast.forecast_date == f_date).delete(synchronize_session=False)
        db_session.commit()


# =============================================================================
# 4. ADVISORY RETRIEVAL API MULTILINGUAL TESTS
# =============================================================================
def test_advisory_retrieval_api_multilingual(client, db_session: Session):
    """GET /api/v1/advisory/panchayat/{panchayat_id} should support lang parameter."""
    panchayat_id = 9502
    f_date = date(2026, 9, 8)

    # Clean prior test rows if any
    db_session.query(Advisory).filter(Advisory.panchayat_id == panchayat_id).delete(synchronize_session=False)
    db_session.commit()

    try:
        # Insert APPROVED advisory
        advisory = Advisory(
            panchayat_id=panchayat_id,
            forecast_id=101,
            forecast_date=f_date,
            rainfall_mm=0.0,
            rainfall_category="No significant rainfall",
            severity="LOW",
            advisory_title="Dry Weather Advisory for Panchayat-9502 - Routine Farm Management",
            advisory_text="• Continue routine irrigation.",
            rule_version=RULE_VERSION,
            status="APPROVED",
            officer_id="OFFICER_01",
        )
        db_session.add(advisory)
        db_session.commit()

        # Marathi
        res_mr = client.get(f"/api/v1/advisory/panchayat/{panchayat_id}?lang=mr")
        assert res_mr.status_code == 200
        data_mr = res_mr.json()
        assert data_mr["language"] == "mr"
        assert "कोरडे हवामान कृषी सल्ला" in data_mr["advisory_title"]

        # Hindi
        res_hi = client.get(f"/api/v1/advisory/panchayat/{panchayat_id}?lang=hi")
        assert res_hi.status_code == 200
        data_hi = res_hi.json()
        assert data_hi["language"] == "hi"
        assert "शुष्क मौसम कृषि सलाह" in data_hi["advisory_title"]

    finally:
        db_session.query(Advisory).filter(Advisory.panchayat_id == panchayat_id).delete(synchronize_session=False)
        db_session.commit()
