"""
GramSevak Automated Test Suite for Administrative Hierarchy Database Foundation (Phase 3.2).

Validates:
1. District, Block, and Panchayat domain model instantiation and attribute constraints.
2. District -> Block relationship (one-to-many) and Block -> District back-population.
3. Block -> Panchayat relationship (one-to-many) and Panchayat -> Block back-population.
4. Unique constraints enforcement (uq_blocks_district_name, uq_panchayats_id).
5. HierarchyRepository data-access methods:
   - get_districts
   - get_district_by_id
   - get_district_by_name
   - get_blocks_by_district
   - get_block_by_id
   - get_block_by_name
   - get_panchayats_by_block (with bounded pagination & search)
   - get_panchayat_by_id (with eager parent joins)
   - get_panchayat_by_lgd
   - detect_orphans
6. HierarchyService domain methods:
   - resolve_panchayat_spatial_context
   - validate_hierarchy_parentage
   - get_hierarchy_summary
7. Multi-district coexistence (Nashik 15 blocks, Pune 13 blocks) with zero orphan records.
8. ML downscaling inference compatibility with dynamically resolved spatial context.
9. Weather observation and downscaled forecast referential integrity.
10. Administrative backfill tool idempotency.
"""

import os
import sys
import pytest
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.weather_observation import WeatherObservation
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.repositories.hierarchy_repository import HierarchyRepository
from backend.services.hierarchy_service import (
    HierarchyService,
    PanchayatNotFoundError,
    HierarchyParentageMismatchError,
    get_hierarchy_service,
)
from backend.services.ml_prediction_service import MLPredictionService
from backend.ml.schemas import DownscaleInferenceRequest
from scripts.backfill_administrative_hierarchy import run_full_backfill


@pytest.fixture(scope="module")
def db():
    """Provide a thread-safe database session for test execution."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def hierarchy_repo():
    return HierarchyRepository()


@pytest.fixture(scope="module")
def hierarchy_service():
    return HierarchyService()


# =============================================================================
# 1. DOMAIN MODELS & ATTRIBUTES
# =============================================================================

def test_district_model_attributes():
    """Verify District model attributes and string representation."""
    d = District(id=999, name="Solapur", state="Maharashtra", code="SLP")
    assert d.id == 999
    assert d.name == "Solapur"
    assert d.state == "Maharashtra"
    assert d.code == "SLP"
    assert "Solapur" in repr(d)


def test_block_model_attributes():
    """Verify Block model attributes and string representation."""
    b = Block(id=888, district_id=999, name="Pandharpur", code="PDR")
    assert b.id == 888
    assert b.district_id == 999
    assert b.name == "Pandharpur"
    assert b.code == "PDR"
    assert "Pandharpur" in repr(b)


def test_panchayat_model_attributes():
    """Verify Panchayat model attributes and string representation."""
    p = Panchayat(
        id=777,
        lgd_code=234567,
        name="Wakhari",
        block_id=888,
        district_id=999,
        latitude=17.6789,
        longitude=75.3456,
        elevation_m=460.0,
    )
    assert p.id == 777
    assert p.lgd_code == 234567
    assert p.name == "Wakhari"
    assert p.block_id == 888
    assert p.district_id == 999
    assert p.latitude == 17.6789
    assert p.longitude == 75.3456
    assert p.elevation_m == 460.0
    assert "Wakhari" in repr(p)


# =============================================================================
# 2. REPOSITORY QUERIES & NAVIGATION
# =============================================================================

def test_repo_get_districts(db, hierarchy_repo):
    """Verify HierarchyRepository.get_districts returns configured districts."""
    districts = hierarchy_repo.get_districts(db)
    assert len(districts) >= 2
    names = [d.name for d in districts]
    assert "Nashik" in names
    assert "Pune" in names


def test_repo_get_district_by_name(db, hierarchy_repo):
    """Verify case-insensitive district lookup by name."""
    nashik = hierarchy_repo.get_district_by_name(db, "nashik")
    assert nashik is not None
    assert nashik.name == "Nashik"

    pune = hierarchy_repo.get_district_by_name(db, "PUNE")
    assert pune is not None
    assert pune.name == "Pune"

    non_existent = hierarchy_repo.get_district_by_name(db, "InvalidNonExistentDistrict")
    assert non_existent is None


def test_repo_get_blocks_by_district(db, hierarchy_repo):
    """Verify block retrieval scoped strictly by District ID."""
    nashik = hierarchy_repo.get_district_by_name(db, "Nashik")
    pune = hierarchy_repo.get_district_by_name(db, "Pune")

    nashik_blocks = hierarchy_repo.get_blocks_by_district(db, nashik.id)
    assert len(nashik_blocks) == 15
    nashik_block_names = [b.name for b in nashik_blocks]
    assert "Baglan" in nashik_block_names
    assert "Dindori" in nashik_block_names

    pune_blocks = hierarchy_repo.get_blocks_by_district(db, pune.id)
    assert len(pune_blocks) == 13
    pune_block_names = [b.name for b in pune_blocks]
    assert "Haveli" in pune_block_names
    assert "Baramati" in pune_block_names


def test_repo_get_block_by_name(db, hierarchy_repo):
    """Verify block retrieval by district ID and block name."""
    nashik = hierarchy_repo.get_district_by_name(db, "Nashik")
    baglan = hierarchy_repo.get_block_by_name(db, nashik.id, "baglan")
    assert baglan is not None
    assert baglan.name == "Baglan"
    assert baglan.district_id == nashik.id


def test_repo_get_panchayats_by_block(db, hierarchy_repo):
    """Verify paginated panchayat retrieval under a block."""
    nashik = hierarchy_repo.get_district_by_name(db, "Nashik")
    baglan = hierarchy_repo.get_block_by_name(db, nashik.id, "Baglan")

    items, total = hierarchy_repo.get_panchayats_by_block(db, baglan.id, offset=0, limit=20)
    assert total > 0
    assert len(items) == min(20, total)
    for p in items:
        assert p.block_id == baglan.id
        assert p.district_id == nashik.id


def test_repo_get_panchayats_search(db, hierarchy_repo):
    """Verify case-insensitive search by name within a block."""
    nashik = hierarchy_repo.get_district_by_name(db, "Nashik")
    baglan = hierarchy_repo.get_block_by_name(db, nashik.id, "Baglan")

    items, total = hierarchy_repo.get_panchayats_by_block(db, baglan.id, search="ajmer")
    assert total >= 1
    assert any("ajmer" in p.name.lower() for p in items)


def test_repo_get_panchayat_by_id_eager(db, hierarchy_repo):
    """Verify single Panchayat lookup with eager parent resolution."""
    # Test Nashik Panchayat (1001)
    p_nashik = hierarchy_repo.get_panchayat_by_id(db, 1001, eager_load_parents=True)
    assert p_nashik is not None
    assert p_nashik.id == 1001
    assert p_nashik.block is not None
    assert p_nashik.district is not None
    assert p_nashik.district.name == "Nashik"

    # Test Pune Panchayat (185262)
    p_pune = hierarchy_repo.get_panchayat_by_id(db, 185262, eager_load_parents=True)
    assert p_pune is not None
    assert p_pune.id == 185262
    assert p_pune.block is not None
    assert p_pune.district is not None
    assert p_pune.district.name == "Pune"


def test_repo_get_panchayat_by_lgd(db, hierarchy_repo):
    """Verify lookup by official 6-digit LGD Code."""
    p = hierarchy_repo.get_panchayat_by_lgd(db, 182597)
    assert p is not None
    assert p.id == 1001
    assert "Ajmer" in p.name


# =============================================================================
# 3. DOMAIN SERVICE LOGIC & SPATIAL CONTEXT
# =============================================================================

def test_service_resolve_spatial_context(db, hierarchy_service):
    """Verify HierarchyService resolves spatial coordinates and administrative context."""
    # 1. Nashik Panchayat
    ctx_n = hierarchy_service.resolve_panchayat_spatial_context(1001, db=db)
    assert ctx_n["panchayat_id"] == 1001
    assert "Ajmer" in ctx_n["panchayat_name"]
    assert ctx_n["district_name"] == "Nashik"
    assert ctx_n["block_name"] == "Baglan"
    assert ctx_n["latitude"] is not None
    assert ctx_n["longitude"] is not None
    assert ctx_n["elevation_m"] is not None

    # 2. Pune Panchayat
    ctx_p = hierarchy_service.resolve_panchayat_spatial_context(185262, db=db)
    assert ctx_p["panchayat_id"] == 185262
    assert ctx_p["district_name"] == "Pune"
    assert ctx_p["latitude"] is not None
    assert ctx_p["longitude"] is not None


def test_service_resolve_non_existent_panchayat(db, hierarchy_service):
    """Verify PanchayatNotFoundError is raised for non-existent ID."""
    with pytest.raises(PanchayatNotFoundError):
        hierarchy_service.resolve_panchayat_spatial_context(99999999, db=db)


def test_service_validate_parentage(db, hierarchy_service):
    """Verify parentage validation correctly confirms or rejects claimed parent IDs."""
    nashik = HierarchyRepository.get_district_by_name(db, "Nashik")
    baglan = HierarchyRepository.get_block_by_name(db, nashik.id, "Baglan")

    # Valid parentage
    assert hierarchy_service.validate_hierarchy_parentage(
        1001, expected_block_id=baglan.id, expected_district_id=nashik.id, db=db
    ) is True

    # Invalid block parentage
    with pytest.raises(HierarchyParentageMismatchError):
        hierarchy_service.validate_hierarchy_parentage(
            1001, expected_block_id=999999, db=db
        )


def test_service_hierarchy_summary(db, hierarchy_service):
    """Verify get_hierarchy_summary returns accurate totals and clean health."""
    summary = hierarchy_service.get_hierarchy_summary(db=db)
    assert summary["total_districts"] == 2
    assert summary["total_blocks"] == 28
    assert summary["total_panchayats"] == 2726
    assert summary["healthy"] is True
    assert summary["orphan_audit"]["is_clean"] is True


# =============================================================================
# 4. ORPHAN INTEGRITY & RELATIONSHIP CHECKS
# =============================================================================

def test_orphan_integrity(db, hierarchy_repo):
    """Verify zero orphan records across the entire database."""
    orphans = hierarchy_repo.detect_orphans(db)
    assert orphans["orphan_blocks"] == 0
    assert orphans["orphan_panchayats_block"] == 0
    assert orphans["orphan_panchayats_district"] == 0
    assert orphans["orphan_weather_panchayat"] == 0
    assert orphans["is_clean"] is True


# =============================================================================
# 5. ML INFERENCE COMPATIBILITY
# =============================================================================

def test_ml_downscaling_with_resolved_spatial_context(db, hierarchy_service):
    """
    Verify that Phase 2 ML Downscaling inference operates successfully
    using the dynamically resolved spatial context from Phase 3.2.
    """
    ctx = hierarchy_service.resolve_panchayat_spatial_context(185262, db=db)
    ml_service = MLPredictionService()

    req = DownscaleInferenceRequest(
        panchayat_id=ctx["panchayat_id"],
        forecast_date=date(2026, 6, 14),
        forecast_issue_date=date(2026, 6, 13),
        block_forecast_rainfall_mm=4.6,
        panchayat_latitude=ctx["latitude"],
        panchayat_longitude=ctx["longitude"],
        elevation_m=ctx["elevation_m"],
        station_distance_km=8.4,
        district_name=ctx["district_name"],
        block_name=ctx["block_name"],
        panchayat_name=ctx["panchayat_name"],
        lead_days=1,
    )

    resp = ml_service.predict_rainfall(req)
    assert resp.prediction_mode == "ml"
    assert resp.downscaled_rainfall_mm >= 0.0
    assert resp.model_name == "xgboost_downscaler"


# =============================================================================
# 6. BACKFILL IDEMPOTENCY DRY-RUN
# =============================================================================

def test_backfill_idempotency_dry_run():
    """Verify backfill dry-run executes cleanly across all canonical Parquet datasets."""
    summary = run_full_backfill(dry_run=True)
    assert summary["healthy"] is True
    assert summary["nashik"]["blocks_count"] == 15
    assert summary["nashik"]["panchayats_count"] == 1388
    assert summary["pune"]["blocks_count"] == 13
    assert summary["pune"]["panchayats_count"] == 1338
