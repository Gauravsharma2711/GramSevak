"""
Test Suite: Scalable Administrative Hierarchy Architecture (Phase 3).
Validates:
1. District -> Block -> Panchayat canonical hierarchy
2. Districts endpoint (Nashik, Pune, future districts)
3. Block retrieval by district ID with 404 validation
4. Hierarchical Block Panchayats with bounded pagination and case-insensitive search
5. Panchayat detail lookup for Nashik and Pune panchayats
6. Backward compatibility for legacy endpoints used by React and Flutter
7. Hierarchy integrity and duplicate safety
8. Dynamic forecast lookup without hardcoded district assumptions
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# 1. DISTRICT LISTING (GET /api/v1/districts)
# =============================================================================

def test_list_districts(client):
    """Verify districts endpoint returns minimal selection payload with Nashik and Pune."""
    response = client.get("/api/v1/districts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    district_names = [d["name"] for d in data]
    assert "Nashik" in district_names
    assert "Pune" in district_names

    # Check payload cleanliness (no weather datasets leaked)
    for dist in data:
        assert "id" in dist
        assert "name" in dist
        assert "weather" not in dist
        assert "forecast" not in dist


# =============================================================================
# 2. DISTRICT BLOCKS (GET /api/v1/districts/{district_id}/blocks)
# =============================================================================

def test_district_blocks_nashik_and_pune(client, db_session):
    """Verify block retrieval for both Nashik (15 blocks) and Pune (13 blocks)."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    pune = db_session.query(District).filter(District.name == "Pune").first()
    assert nashik is not None
    assert pune is not None

    # 1. Nashik blocks
    resp_nashik = client.get(f"/api/v1/districts/{nashik.id}/blocks")
    assert resp_nashik.status_code == 200
    nashik_blocks = resp_nashik.json()
    assert len(nashik_blocks) == 15
    nashik_block_names = [b["name"] for b in nashik_blocks]
    assert "Baglan" in nashik_block_names
    assert "Dindori" in nashik_block_names
    assert "Niphad" in nashik_block_names
    assert "Malegaon" in nashik_block_names

    # 2. Pune blocks
    resp_pune = client.get(f"/api/v1/districts/{pune.id}/blocks")
    assert resp_pune.status_code == 200
    pune_blocks = resp_pune.json()
    assert len(pune_blocks) == 13
    pune_block_names = [b["name"] for b in pune_blocks]
    assert "Haveli" in pune_block_names
    assert "Baramati" in pune_block_names

    # 3. Invalid district returns 404
    resp_invalid = client.get("/api/v1/districts/999999/blocks")
    assert resp_invalid.status_code == 404
    assert "not found" in resp_invalid.json()["detail"].lower()


# =============================================================================
# 3. BLOCK PANCHAYATS (GET /api/v1/blocks/{block_id}/panchayats)
# =============================================================================

def test_block_panchayats_pagination(client, db_session):
    """Verify paginated panchayat retrieval under a block."""
    baglan = db_session.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    resp = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()

    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total"] > 0
    assert len(data["items"]) == min(20, data["total"])

    # Verify canonical item structure
    item = data["items"][0]
    assert "id" in item
    assert "lgd_code" in item
    assert "name" in item
    assert item["block_id"] == baglan.id
    assert item["district_id"] == baglan.district_id

    # Verify 404 on non-existent block
    resp_404 = client.get("/api/v1/blocks/999999/panchayats")
    assert resp_404.status_code == 404


def test_block_panchayats_search(client, db_session):
    """Verify case-insensitive database-backed search within a block."""
    baglan = db_session.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    # Search for "ajmer" in Baglan
    resp = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?search=ajmer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    matched_names = [p["name"].lower() for p in data["items"]]
    assert any("ajmer" in name for name in matched_names)

    # Search for non-existent text
    resp_empty = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?search=xyznonexistentvillage123")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0
    assert len(resp_empty.json()["items"]) == 0


# =============================================================================
# 4. PANCHAYAT DETAIL LOOKUP (GET /api/v1/panchayats/{panchayat_id})
# =============================================================================

def test_panchayat_detail_nashik(client):
    """Verify detail lookup for a Nashik Panchayat (1001 - Ajmer Saundane)."""
    resp = client.get("/api/v1/panchayats/1001")
    assert resp.status_code == 200
    data = resp.json()

    assert data["panchayat_id"] == 1001
    assert data["id"] == 1001
    assert "Ajmer" in data["panchayat_name"]
    assert data["block_name"] == "Baglan"
    assert data["district_name"] == "Nashik"
    assert data["block_id"] is not None
    assert data["district_id"] is not None


def test_panchayat_detail_pune(client, db_session):
    """Verify detail lookup for a Pune Panchayat without hardcoded Nashik assumption."""
    pune_dist = db_session.query(District).filter(District.name == "Pune").first()
    assert pune_dist is not None

    pune_panchayat = (
        db_session.query(Panchayat)
        .filter(Panchayat.district_id == pune_dist.id)
        .first()
    )
    assert pune_panchayat is not None

    resp = client.get(f"/api/v1/panchayats/{pune_panchayat.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["panchayat_id"] == pune_panchayat.id
    assert data["id"] == pune_panchayat.id
    assert data["district_name"] == "Pune"
    assert data["block_id"] == pune_panchayat.block_id
    assert data["district_id"] == pune_dist.id


# =============================================================================
# 5. DATA INTEGRITY & HIERARCHY COMPLETENESS
# =============================================================================

def test_administrative_hierarchy_completeness(db_session):
    """Verify completeness of Nashik (15 blocks, 1388 panchayats) and Pune (13 blocks, 1338 panchayats)."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    pune = db_session.query(District).filter(District.name == "Pune").first()

    assert nashik is not None
    assert pune is not None

    nashik_blocks = db_session.query(Block).filter(Block.district_id == nashik.id).count()
    pune_blocks = db_session.query(Block).filter(Block.district_id == pune.id).count()
    assert nashik_blocks == 15
    assert pune_blocks == 13

    nashik_panchayats = db_session.query(Panchayat).filter(Panchayat.district_id == nashik.id).count()
    pune_panchayats = db_session.query(Panchayat).filter(Panchayat.district_id == pune.id).count()
    assert nashik_panchayats == 1388
    assert pune_panchayats == 1338

    # Total system panchayats
    total_panchayats = db_session.query(Panchayat).count()
    assert total_panchayats == 2726


def test_panchayat_membership_integrity(db_session):
    """Verify that every panchayat belongs to a valid block and district."""
    orphan_block_panchayats = (
        db_session.query(Panchayat)
        .outerjoin(Block, Panchayat.block_id == Block.id)
        .filter(Block.id == None)
        .count()
    )
    assert orphan_block_panchayats == 0

    orphan_district_panchayats = (
        db_session.query(Panchayat)
        .outerjoin(District, Panchayat.district_id == District.id)
        .filter(District.id == None)
        .count()
    )
    assert orphan_district_panchayats == 0


# =============================================================================
# 6. BACKWARD COMPATIBILITY
# =============================================================================

def test_legacy_panchayats_endpoint_compatibility(client):
    """Verify legacy /api/v1/panchayats endpoint continues working for React and Flutter."""
    resp = client.get("/api/v1/panchayats?page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) == 20

    # Test filtering by block_name
    resp_block = client.get("/api/v1/panchayats?block_name=Baglan&page_size=10")
    assert resp_block.status_code == 200
    for item in resp_block.json()["items"]:
        assert item["block_name"] == "Baglan"

    # Test filtering by district_name
    resp_pune = client.get("/api/v1/panchayats?district_name=Pune&page_size=10")
    assert resp_pune.status_code == 200
    for item in resp_pune.json()["items"]:
        assert item["district_name"] == "Pune"


# =============================================================================
# 7. FORECAST LOOKUP WITHOUT HARDCODED NASHIK
# =============================================================================

def test_forecast_retrieval_dynamic_district(client):
    """Verify forecast lookup endpoint dynamic district resolution."""
    # Test for 1001 (Nashik)
    resp = client.get("/api/v1/forecast/panchayat/1001")
    if resp.status_code == 200:
        data = resp.json()
        assert data["district_name"] == "Nashik"
        assert data["block_name"] == "Baglan"
    else:
        assert resp.status_code == 404
