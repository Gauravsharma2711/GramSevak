"""
Unit and Integration Test Suite: Scalable Administrative Hierarchy REST APIs (Phase 3.3).

Validates:
1. District API (GET /api/v1/districts)
2. Block-by-District API (GET /api/v1/districts/{district_id}/blocks)
3. Panchayat-by-Block API (GET /api/v1/blocks/{block_id}/panchayats)
4. Panchayat detail API (GET /api/v1/panchayats/{panchayat_id})
5. Request validation & error handling (404 for missing parents, 422 for malformed IDs)
6. Empty child collections (200 with empty items, distinct from missing parents)
7. Cross-hierarchy isolation (panchayats strictly scoped to their parent block)
8. Multi-district real-data verification (Nashik & Pune served by identical generic routes)
9. Security & payload cleanliness (zero leakage of DB credentials or internal traces)
10. Backward compatibility with existing backend weather/forecast/ML endpoints
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

def test_api_list_districts(client):
    """Verify districts endpoint returns deterministic list with stable IDs and codes."""
    response = client.get("/api/v1/districts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Verify deterministic alphabetical ordering
    names = [d["name"] for d in data]
    assert names == sorted(names)
    assert "Nashik" in names
    assert "Pune" in names

    # Verify canonical schema fields
    for d in data:
        assert "id" in d and isinstance(d["id"], int)
        assert "name" in d and isinstance(d["name"], str)
        assert "state" in d and d["state"] == "Maharashtra"
        assert "code" in d  # can be None or str, but key must exist


def test_api_list_districts_payload_cleanliness(client):
    """Ensure district endpoint does not leak internal DB credentials, weather data, or nested entities."""
    response = client.get("/api/v1/districts")
    assert response.status_code == 200
    for d in response.json():
        assert "password" not in d
        assert "db_url" not in d
        assert "weather" not in d
        assert "forecast" not in d
        assert "blocks" not in d  # lightweight endpoint: no nested blocks


# =============================================================================
# 2. BLOCK-BY-DISTRICT (GET /api/v1/districts/{district_id}/blocks)
# =============================================================================

def test_api_blocks_by_district_valid(client, db_session):
    """Verify blocks retrieval for both Nashik (15 blocks) and Pune (13 blocks)."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    pune = db_session.query(District).filter(District.name == "Pune").first()
    assert nashik is not None
    assert pune is not None

    # Nashik: exactly 15 blocks
    r_nsk = client.get(f"/api/v1/districts/{nashik.id}/blocks")
    assert r_nsk.status_code == 200
    nsk_blocks = r_nsk.json()
    assert len(nsk_blocks) == 15
    for b in nsk_blocks:
        assert b["district_id"] == nashik.id
        assert "id" in b and "name" in b
    nsk_names = [b["name"] for b in nsk_blocks]
    assert nsk_names == sorted(nsk_names)  # deterministic ordering
    assert "Baglan" in nsk_names
    assert "Dindori" in nsk_names

    # Pune: exactly 13 blocks
    r_pun = client.get(f"/api/v1/districts/{pune.id}/blocks")
    assert r_pun.status_code == 200
    pun_blocks = r_pun.json()
    assert len(pun_blocks) == 13
    for b in pun_blocks:
        assert b["district_id"] == pune.id
        assert "id" in b and "name" in b
    pun_names = [b["name"] for b in pun_blocks]
    assert pun_names == sorted(pun_names)
    assert "Haveli" in pun_names
    assert "Baramati" in pun_names


def test_api_blocks_by_district_invalid_returns_404(client):
    """Non-existent district returns HTTP 404."""
    response = client.get("/api/v1/districts/999999/blocks")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_api_blocks_by_district_malformed_returns_422(client):
    """Malformed district ID (0, negative, non-integer) returns HTTP 422."""
    assert client.get("/api/v1/districts/0/blocks").status_code == 422
    assert client.get("/api/v1/districts/-5/blocks").status_code == 422
    assert client.get("/api/v1/districts/invalid_id/blocks").status_code == 422


def test_api_blocks_by_district_empty_district(client, db_session):
    """A valid district with 0 blocks returns 200 with an empty list, not 404."""
    # Create a temporary district with no blocks
    temp_dist = District(name="EmptyDistrictTest", state="Maharashtra")
    db_session.add(temp_dist)
    db_session.commit()
    db_session.refresh(temp_dist)

    try:
        response = client.get(f"/api/v1/districts/{temp_dist.id}/blocks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0  # 200 OK with empty items
    finally:
        db_session.delete(temp_dist)
        db_session.commit()


# =============================================================================
# 3. PANCHAYAT-BY-BLOCK (GET /api/v1/blocks/{block_id}/panchayats)
# =============================================================================

def test_api_panchayats_by_block_valid(client, db_session):
    """Verify paginated Panchayats strictly scoped to a block."""
    baglan = db_session.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    resp = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?page=1&page_size=25")
    assert resp.status_code == 200
    data = resp.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data and data["page"] == 1
    assert "page_size" in data and data["page_size"] == 25
    assert "total_pages" in data
    assert data["total"] > 0
    assert len(data["items"]) == min(25, data["total"])

    # Verify item schema
    for item in data["items"]:
        assert item["block_id"] == baglan.id
        assert item["district_id"] == baglan.district_id
        assert "id" in item
        assert "name" in item
        assert "latitude" in item
        assert "longitude" in item


def test_api_panchayats_by_block_invalid_returns_404(client):
    """Non-existent block returns HTTP 404."""
    response = client.get("/api/v1/blocks/999999/panchayats")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_panchayats_by_block_malformed_returns_422(client):
    """Malformed block ID returns HTTP 422."""
    assert client.get("/api/v1/blocks/0/panchayats").status_code == 422
    assert client.get("/api/v1/blocks/-10/panchayats").status_code == 422
    assert client.get("/api/v1/blocks/abc/panchayats").status_code == 422


def test_api_panchayats_by_block_empty_block(client, db_session):
    """A valid block with 0 Panchayats returns 200 with empty items, not 404."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    temp_block = Block(district_id=nashik.id, name="EmptyBlockTest")
    db_session.add(temp_block)
    db_session.commit()
    db_session.refresh(temp_block)

    try:
        response = client.get(f"/api/v1/blocks/{temp_block.id}/panchayats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
    finally:
        db_session.delete(temp_block)
        db_session.commit()


# =============================================================================
# 4. PANCHAYAT DETAIL (GET /api/v1/panchayats/{panchayat_id})
# =============================================================================

def test_api_panchayat_detail_nashik_and_pune(client, db_session):
    """Verify detail retrieval for both a Nashik and a Pune Panchayat."""
    # Nashik: ID 1001 (Ajmer Saundane)
    r_nsk = client.get("/api/v1/panchayats/1001")
    assert r_nsk.status_code == 200
    d_nsk = r_nsk.json()
    assert d_nsk["id"] == 1001
    assert "Ajmer" in d_nsk["name"]
    assert d_nsk["district_name"] == "Nashik"
    assert d_nsk["block_name"] == "Baglan"
    assert d_nsk["latitude"] is not None
    assert d_nsk["longitude"] is not None

    # Pune: query a real Pune panchayat
    pune_p = db_session.query(Panchayat).filter(Panchayat.id > 100000).first()
    assert pune_p is not None

    r_pun = client.get(f"/api/v1/panchayats/{pune_p.id}")
    assert r_pun.status_code == 200
    d_pun = r_pun.json()
    assert d_pun["id"] == pune_p.id
    assert d_pun["name"] == pune_p.name
    assert d_pun["district_name"] == "Pune"
    assert d_pun["latitude"] is not None
    assert d_pun["longitude"] is not None


def test_api_panchayat_detail_missing_returns_404(client):
    """Non-existent Panchayat ID returns HTTP 404."""
    response = client.get("/api/v1/panchayats/99999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_panchayat_detail_malformed_returns_422(client):
    """Malformed Panchayat ID returns HTTP 422."""
    assert client.get("/api/v1/panchayats/0").status_code == 422
    assert client.get("/api/v1/panchayats/-1").status_code == 422
    assert client.get("/api/v1/panchayats/bad_id").status_code == 422


# =============================================================================
# 5. CROSS-HIERARCHY ISOLATION
# =============================================================================

def test_api_cross_hierarchy_isolation(client, db_session):
    """
    Verify that Panchayat P belonging to Block B cannot be returned
    under a different Block B2 (even within the same district or in another district).
    """
    p_1001 = db_session.query(Panchayat).filter(Panchayat.id == 1001).first()
    assert p_1001 is not None
    baglan = p_1001.block
    assert baglan.name == "Baglan"

    # Find another block in Nashik (e.g. Dindori)
    dindori = db_session.query(Block).filter(Block.name == "Dindori").first()
    assert dindori is not None

    # Find a block in Pune (e.g. Haveli)
    haveli = db_session.query(Block).filter(Block.name == "Haveli").first()
    assert haveli is not None

    # Query Dindori panchayats with large page size
    r_dindori = client.get(f"/api/v1/blocks/{dindori.id}/panchayats?page_size=200")
    assert r_dindori.status_code == 200
    dindori_ids = [p["id"] for p in r_dindori.json()["items"]]
    assert 1001 not in dindori_ids, "Panchayat 1001 (Baglan) must NOT appear in Dindori"

    # Query Haveli panchayats with large page size
    r_haveli = client.get(f"/api/v1/blocks/{haveli.id}/panchayats?page_size=200")
    assert r_haveli.status_code == 200
    haveli_ids = [p["id"] for p in r_haveli.json()["items"]]
    assert 1001 not in haveli_ids, "Panchayat 1001 (Baglan) must NOT appear in Haveli (Pune)"


# =============================================================================
# 6. MULTI-DISTRICT GENERIC SERVING & NO SPECIAL ROUTES
# =============================================================================

def test_api_multi_district_no_special_routes(client):
    """Ensure no hardcoded /nashik/... or /pune/... routes exist."""
    assert client.get("/api/v1/nashik/blocks").status_code == 404
    assert client.get("/api/v1/pune/blocks").status_code == 404
    assert client.get("/api/v1/nashik/panchayats").status_code == 404
    assert client.get("/api/v1/pune/panchayats").status_code == 404


# =============================================================================
# 7. REGRESSION & COMPATIBILITY
# =============================================================================

def test_api_regression_health_endpoint(client):
    """Health check endpoint remains operational."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["ok", "healthy"]


def test_api_regression_forecast_lookup(client):
    """Weather downscaled forecast lookup for Panchayat 1001 still functions cleanly."""
    response = client.get("/api/v1/forecast/panchayat/1001")
    # Endpoint returns 200 with forecast or 404 with standard envelope if no forecast recorded for date
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert data["panchayat_id"] == 1001
