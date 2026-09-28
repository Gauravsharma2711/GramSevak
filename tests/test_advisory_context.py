"""
Phase 5.3 Advisory Context Layer Test Suite.

Validates the assembly of canonical AdvisoryContext uniting authoritative Panchayat
hierarchy, validated numerical downscaled forecasts, deterministic rule results,
and end-to-end traceability metadata.

Tests:
1. Valid Panchayat + valid forecast (end-to-end context assembly).
2. Valid context with no triggered risks.
3. Valid context with one triggered risk (e.g. 1.2 mm light rain).
4. Valid context with multiple triggered risks (e.g. 25.0 mm moderate rain).
5. Panchayat not found error handling (404 / PanchayatNotFoundError).
6. Forecast not found error handling (404 / ForecastNotFoundError).
7. Panchayat/forecast mismatch error handling (422 / ForecastPanchayatMismatchError).
8. Invalid forecast values (NaN, Inf, negative rainfall).
9. Missing required forecast fields.
10. Rule-engine failure handling (RuleEvaluationError).
11. Invalid rule-engine output / contract consistency.
12. Traceability preservation (spatial link, model version, forecast ID, rule version).
13. Nashik real database records verification (Panchayat 1001).
14. Pune real database records verification (Panchayat 185262).
15. District/Panchayat dynamic generalization (no hardcoded locations).
16. Deterministic repeatability (Input A -> Output A == Output A).
17. REST API endpoint verification (GET /api/v1/advisory/context/{panchayat_id}).
"""

from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.panchayat import Panchayat
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.schemas.advisory_contracts import (
    AdvisoryContext,
    AdvisorySeverityEnum,
)
from src.advisory.context_builder import (
    AdvisoryContextService,
    default_advisory_context_service,
    PanchayatNotFoundError,
    ForecastNotFoundError,
    ForecastPanchayatMismatchError,
    HierarchyMismatchError,
    InvalidForecastDataError,
    RuleEvaluationError,
    build_panchayat_context,
    build_forecast_context,
)


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


def make_dummy_panchayat(
    p_id: int = 1001,
    p_name: str = "Ajmer Saundane",
    block_id: int = 10,
    block_name: str = "Baglan",
    dist_id: int = 1,
    dist_name: str = "Nashik",
) -> Panchayat:
    """Helper creating an in-memory Panchayat model with joined parents."""
    p = Panchayat()
    p.id = p_id
    p.name = p_name
    p.panchayat_code = f"P_{p_id}"
    p.lgd_code = 253123
    p.block_id = block_id
    p.district_id = dist_id
    p.latitude = 20.5982
    p.longitude = 74.1201
    p.elevation_m = 585.0

    b = MagicMock()
    b.id = block_id
    b.name = block_name
    p.block = b

    d = MagicMock()
    d.id = dist_id
    d.name = dist_name
    p.district = d

    return p


def make_dummy_forecast(
    f_id: int = 1,
    p_id: int = 1001,
    downscaled_rf: float = 12.5,
    block_rf: float = 15.0,
    f_date: date = date(2026, 9, 10),
    issue_date: date = date(2026, 9, 10),
) -> DownscaledForecast:
    """Helper creating an in-memory DownscaledForecast model."""
    f = DownscaledForecast()
    f.id = f_id
    f.panchayat_id = p_id
    f.forecast_date = f_date
    f.forecast_issue_date = issue_date
    f.downscaled_rainfall_mm = downscaled_rf
    f.block_forecast_rainfall_mm = block_rf
    f.model_name = "XGBoost Regressor"
    f.model_version = "v1.0.0"
    f.confidence = 0.88
    return f


# =============================================================================
# 1. VALID PANCHAYAT + VALID FORECAST
# =============================================================================

def test_valid_panchayat_and_forecast_context_assembly():
    """Verify clean assembly of canonical AdvisoryContext with all sub-contracts."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=10.0)

    service = AdvisoryContextService()
    ctx = service.build_from_objects(p, f)

    assert isinstance(ctx, AdvisoryContext)
    assert ctx.panchayat.panchayat_id == 1001
    assert ctx.panchayat.panchayat_name == "Ajmer Saundane"
    assert ctx.panchayat.block_name == "Baglan"
    assert ctx.panchayat.district_name == "Nashik"

    assert ctx.forecast.forecast_id == 1
    assert ctx.forecast.downscaled_rainfall_mm == 10.0
    assert ctx.forecast.model_name == "XGBoost Regressor"

    assert len(ctx.recommendations.recommended_actions) >= 1
    assert ctx.traceability.panchayat_id == 1001
    assert ctx.traceability.forecast_id == 1
    assert ctx.traceability.downscaled_rainfall_mm == 10.0


# =============================================================================
# 2. VALID CONTEXT WITH NO TRIGGERED RISKS / DRY WEATHER
# =============================================================================

def test_valid_context_dry_weather():
    """Verify 0.0 mm dry weather generates low severity and routine irrigation action."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=0.0)

    ctx = default_advisory_context_service.build_from_objects(p, f)
    assert ctx.forecast.downscaled_rainfall_mm == 0.0

    severities = [r.severity for r in ctx.risks]
    assert AdvisorySeverityEnum.CRITICAL not in severities
    assert AdvisorySeverityEnum.HIGH not in severities
    assert ctx.recommendations.operational_guidance["irrigation"] == "CONTINUE_NORMAL"


# =============================================================================
# 3. VALID CONTEXT WITH ONE TRIGGERED RISK
# =============================================================================

def test_valid_context_single_triggered_risk():
    """Verify light rain of 1.2 mm triggers single minimal impact risk."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=1.2)

    ctx = default_advisory_context_service.build_from_objects(p, f)
    assert len(ctx.risks) == 1
    assert ctx.risks[0].risk_type == "MINIMAL_WEATHER_IMPACT"
    assert ctx.risks[0].severity == AdvisorySeverityEnum.LOW


# =============================================================================
# 4. VALID CONTEXT WITH MULTIPLE TRIGGERED RISKS
# =============================================================================

def test_valid_context_multiple_triggered_risks():
    """Verify moderate rain of 25.0 mm triggers multiple concurrent risks and guidance."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=25.0)

    ctx = default_advisory_context_service.build_from_objects(p, f)
    risk_types = {r.risk_type for r in ctx.risks}
    assert "SPRAY_WASHOFF" in risk_types
    assert "SOIL_COMPACTION" in risk_types
    assert "RUNOFF_LEACHING" in risk_types
    assert "GRAIN_DAMAGE" in risk_types

    assert ctx.recommendations.operational_guidance["spraying"] == "POSTPONE"
    assert ctx.recommendations.operational_guidance["tillage"] == "DELAY"


# =============================================================================
# 5. PANCHAYAT NOT FOUND
# =============================================================================

def test_panchayat_not_found_raises_structured_error():
    """Verify non-existent Panchayat ID raises PanchayatNotFoundError."""
    service = AdvisoryContextService()
    with pytest.raises(PanchayatNotFoundError) as exc_info:
        service.build_advisory_context(panchayat_id=9999999)
    assert exc_info.value.code == "PANCHAYAT_NOT_FOUND"


# =============================================================================
# 6. FORECAST NOT FOUND
# =============================================================================

def test_forecast_not_found_raises_structured_error():
    """Verify valid Panchayat with no forecast for date raises ForecastNotFoundError."""
    service = AdvisoryContextService()
    with pytest.raises(ForecastNotFoundError) as exc_info:
        # Panchayat 1001 exists, but date 1990-01-01 will not have downscaled forecast
        service.build_advisory_context(panchayat_id=1001, forecast_date=date(1990, 1, 1))
    assert exc_info.value.code == "FORECAST_NOT_FOUND"


# =============================================================================
# 7. PANCHAYAT / FORECAST MISMATCH
# =============================================================================

def test_panchayat_forecast_mismatch_raises_error():
    """Verify mismatched Panchayat and forecast IDs raises ForecastPanchayatMismatchError."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, p_id=2002, downscaled_rf=10.0)  # belongs to 2002, not 1001

    service = AdvisoryContextService()
    with pytest.raises(ForecastPanchayatMismatchError) as exc_info:
        service.build_from_objects(p, f)
    assert exc_info.value.code == "FORECAST_PANCHAYAT_MISMATCH"


# =============================================================================
# 8. INVALID FORECAST VALUES (NEGATIVE, NAN, INF)
# =============================================================================

@pytest.mark.parametrize("bad_val", [-5.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_numeric_values_rejected(bad_val):
    """Verify non-physical numerical forecast values are rejected with InvalidForecastDataError."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=bad_val)

    service = AdvisoryContextService()
    with pytest.raises(InvalidForecastDataError) as exc_info:
        service.build_from_objects(p, f)
    assert exc_info.value.code == "INVALID_FORECAST_DATA"


# =============================================================================
# 9. MISSING REQUIRED FORECAST FIELD & TEMPORAL INCONSISTENCY
# =============================================================================

def test_missing_forecast_date_rejected():
    """Verify missing forecast date raises InvalidForecastDataError."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=10.0)
    f.forecast_date = None

    service = AdvisoryContextService()
    with pytest.raises(InvalidForecastDataError):
        service.build_from_objects(p, f)


def test_issue_date_after_forecast_date_rejected():
    """Verify issue date later than target forecast date is rejected."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(
        1,
        1001,
        downscaled_rf=10.0,
        f_date=date(2026, 9, 10),
        issue_date=date(2026, 9, 12),  # Invalid: issue > target
    )
    service = AdvisoryContextService()
    with pytest.raises(InvalidForecastDataError):
        service.build_from_objects(p, f)


# =============================================================================
# 10. RULE ENGINE FAILURE HANDLING
# =============================================================================

def test_rule_engine_failure_wrapped_in_rule_evaluation_error():
    """Verify unexpected failure in rule evaluation raises RuleEvaluationError."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=10.0)

    with patch("src.advisory.context_builder.default_rule_engine.evaluate", side_effect=RuntimeError("Rule Engine Fault")):
        service = AdvisoryContextService()
        with pytest.raises(RuleEvaluationError) as exc_info:
            service.build_from_objects(p, f)
        assert exc_info.value.code == "RULE_EVALUATION_ERROR"


# =============================================================================
# 11. HIERARCHY MISMATCH ERROR HANDLING
# =============================================================================

def test_hierarchy_mismatch_raises_error():
    """Verify expected block mismatch raises HierarchyMismatchError."""
    service = AdvisoryContextService()
    # Panchayat 1001 belongs to block 10 (Baglan), expecting block 9999 must raise
    with pytest.raises(HierarchyMismatchError) as exc_info:
        service.build_advisory_context(panchayat_id=1001, expected_block_id=9999)
    assert exc_info.value.code == "HIERARCHY_MISMATCH"


# =============================================================================
# 12. TRACEABILITY PRESERVATION
# =============================================================================

def test_traceability_preservation():
    """Verify traceability contract maintains audit linkage."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(42, 1001, downscaled_rf=18.5)

    ctx = default_advisory_context_service.build_from_objects(p, f)
    trace = ctx.traceability

    assert trace.panchayat_id == 1001
    assert trace.forecast_id == 42
    assert trace.downscaled_rainfall_mm == 18.5
    assert trace.ml_model_name == "XGBoost Regressor"
    assert trace.ml_model_version == "v1.0.0"
    assert trace.rule_version == "v1.0.0"
    assert "FORECAST_P1001" in trace.source_forecast_reference


# =============================================================================
# 13. REAL-DATA VERIFICATION (NASHIK PANCHAYAT 1001)
# =============================================================================

def test_real_data_verification_nashik():
    """Verify context building against real persisted Nashik database records."""
    db = SessionLocal()
    try:
        service = AdvisoryContextService()
        ctx = service.build_advisory_context(panchayat_id=1001, db=db)

        assert ctx.panchayat.panchayat_id == 1001
        assert ctx.panchayat.district_name == "Nashik"
        assert ctx.panchayat.block_name == "Baglan"
        assert ctx.panchayat.panchayat_name == "Ajmer Saundane"
        assert ctx.forecast.downscaled_rainfall_mm >= 0.0
        assert ctx.forecast.model_name is not None
        assert len(ctx.recommendations.recommended_actions) >= 1
    finally:
        db.close()


# =============================================================================
# 14. REAL-DATA VERIFICATION (PUNE PANCHAYAT 185262)
# =============================================================================

def test_real_data_verification_pune():
    """Verify context building against real persisted Pune database records."""
    db = SessionLocal()
    try:
        service = AdvisoryContextService()
        ctx = service.build_advisory_context(panchayat_id=185262, db=db)

        assert ctx.panchayat.panchayat_id == 185262
        assert ctx.panchayat.district_name == "Pune"
        assert ctx.panchayat.block_name == "Ambegaon"
        assert ctx.panchayat.panchayat_name == "Ahupe"
        assert ctx.forecast.downscaled_rainfall_mm >= 0.0
        assert len(ctx.recommendations.recommended_actions) >= 1
    finally:
        db.close()


# =============================================================================
# 15. DYNAMIC GENERALIZATION (NO HARDCODED DISTRICTS)
# =============================================================================

def test_dynamic_generalization_across_districts():
    """Verify service dynamically accommodates different districts without code branching."""
    nashik_p = make_dummy_panchayat(p_id=1001, dist_name="Nashik")
    pune_p = make_dummy_panchayat(p_id=185262, dist_name="Pune")
    kolhapur_p = make_dummy_panchayat(p_id=5001, dist_name="Kolhapur")

    f1 = make_dummy_forecast(1, 1001, downscaled_rf=10.0)
    f2 = make_dummy_forecast(2, 185262, downscaled_rf=10.0)
    f3 = make_dummy_forecast(3, 5001, downscaled_rf=10.0)

    service = AdvisoryContextService()
    c1 = service.build_from_objects(nashik_p, f1)
    c2 = service.build_from_objects(pune_p, f2)
    c3 = service.build_from_objects(kolhapur_p, f3)

    assert c1.panchayat.district_name == "Nashik"
    assert c2.panchayat.district_name == "Pune"
    assert c3.panchayat.district_name == "Kolhapur"


# =============================================================================
# 16. DETERMINISTIC REPEATABILITY
# =============================================================================

def test_deterministic_repeatability():
    """Verify identical inputs yield identical AdvisoryContext across multiple calls."""
    p = make_dummy_panchayat(1001)
    f = make_dummy_forecast(1, 1001, downscaled_rf=18.5)

    service = AdvisoryContextService()
    ctx_1 = service.build_from_objects(p, f)
    ctx_2 = service.build_from_objects(p, f)

    assert ctx_1.model_dump() == ctx_2.model_dump()


# =============================================================================
# 17. REST API ENDPOINT INTEGRATION
# =============================================================================

def test_api_advisory_context_endpoint_success(api_client):
    """Verify GET /api/v1/advisory/context/{panchayat_id} returns 200 and AdvisoryContext schema."""
    response = api_client.get("/api/v1/advisory/context/1001")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["panchayat"]["panchayat_id"] == 1001
    assert data["panchayat"]["panchayat_name"] == "Ajmer Saundane"
    assert "downscaled_rainfall_mm" in data["forecast"]
    assert "recommended_actions" in data["recommendations"]
    assert "source_forecast_reference" in data["traceability"]


def test_api_advisory_context_endpoint_not_found(api_client):
    """Verify GET /api/v1/advisory/context/{nonexistent_id} returns 404."""
    response = api_client.get("/api/v1/advisory/context/999999")
    assert response.status_code == 404
    data = response.json()
    assert "not exist" in data["detail"] or "not found" in data["detail"].lower()
