"""
Integration Test Suite: Phase 3.4 Pagination and Server-Side Search.

Validates:
1. District API (GET /api/v1/districts):
   - Default pagination (page=1, page_size=20)
   - Custom page and page_size
   - Maximum page_size bounds (max 100)
   - Server-side search & case-insensitivity
   - No-match search returning 200 with empty items
   - Page beyond available results
   - Strict validation: page=0, page=-1, page_size=1000, long search -> HTTP 422
   - Payload cleanliness & deterministic ordering
2. Block-by-District API (GET /api/v1/districts/{district_id}/blocks):
   - Bounded pagination scoped strictly to parent district
   - Server-side search strictly within district
   - Cross-district search isolation (no leakage)
   - Empty district returns 200 with total=0
   - Invalid district ID -> HTTP 404
   - Malformed parameters -> HTTP 422
3. Panchayat-by-Block API (GET /api/v1/blocks/{block_id}/panchayats):
   - Bounded pagination (page_size up to 200)
   - Server-side search by name and LGD code
   - Cross-block search isolation
   - Empty block returns 200 with total=0
   - Invalid block ID -> HTTP 404
   - Malformed parameters -> HTTP 422
4. Panchayat Detail API (GET /api/v1/panchayats/{panchayat_id}):
   - Single-resource retrieval remains unchanged & backward-compatible
   - 404 for non-existent, 422 for malformed
5. Deterministic ordering across all endpoints
6. Full regression safety (health, forecast)
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
# 1. DISTRICT PAGINATION & SEARCH (GET /api/v1/districts)
# =============================================================================

def test_api_districts_default_pagination(client):
    """Verify default pagination returns envelope with metadata and deterministic ordering."""
    response = client.get("/api/v1/districts")
    assert response.status_code == 200
    data = response.json()

    assert "total" in data
    assert "page" in data and data["page"] == 1
    assert "page_size" in data and data["page_size"] == 20
    assert "total_pages" in data and data["total_pages"] >= 1
    assert "items" in data and isinstance(data["items"], list)
    assert len(data["items"]) >= 2

    # Deterministic alphabetical ordering by name
    names = [d["name"] for d in data["items"]]
    assert names == sorted(names)
    assert "Nashik" in names
    assert "Pune" in names

    # Schema cleanliness
    for d in data["items"]:
        assert "id" in d and isinstance(d["id"], int)
        assert "name" in d and isinstance(d["name"], str)
        assert "state" in d and d["state"] == "Maharashtra"
        assert "code" in d
        assert "password" not in d
        assert "db_url" not in d
        assert "blocks" not in d  # no nested collections


def test_api_districts_custom_pagination(client):
    """Verify custom page and page_size boundaries."""
    # Page size 1: should return exactly 1 item, total >= 2, total_pages >= 2
    r1 = client.get("/api/v1/districts?page=1&page_size=1")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["page"] == 1
    assert d1["page_size"] == 1
    assert len(d1["items"]) == 1
    first_item = d1["items"][0]

    # Page 2: should return the second item without overlapping page 1
    r2 = client.get("/api/v1/districts?page=2&page_size=1")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["page"] == 2
    assert d2["page_size"] == 1
    assert len(d2["items"]) == 1
    second_item = d2["items"][0]

    assert first_item["id"] != second_item["id"]
    assert first_item["name"] < second_item["name"]


def test_api_districts_maximum_page_size(client):
    """Verify max bounded page_size (100) is accepted."""
    response = client.get("/api/v1/districts?page_size=100")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 100
    assert len(data["items"]) == data["total"]


def test_api_districts_search_case_insensitive(client):
    """Verify server-side case-insensitive search on district name."""
    for query in ["nashik", "NASHIK", "Nashik", "Nash"]:
        res = client.get(f"/api/v1/districts?search={query}")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Nashik"

    # Search Pune
    res_pune = client.get("/api/v1/districts?search=pune")
    assert res_pune.status_code == 200
    assert res_pune.json()["total"] == 1
    assert res_pune.json()["items"][0]["name"] == "Pune"


def test_api_districts_search_no_match(client):
    """Search query with no matching districts returns 200 with empty items."""
    response = client.get("/api/v1/districts?search=NonExistentDistrictXYZ")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["total_pages"] == 0
    assert data["items"] == []


def test_api_districts_page_beyond_available(client):
    """Valid page number beyond total pages returns 200 with empty items list."""
    response = client.get("/api/v1/districts?page=999&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert data["page"] == 999
    assert data["items"] == []


def test_api_districts_invalid_parameters_422(client):
    """Invalid pagination and search parameters return HTTP 422 Unprocessable Entity."""
    assert client.get("/api/v1/districts?page=0").status_code == 422
    assert client.get("/api/v1/districts?page=-1").status_code == 422
    assert client.get("/api/v1/districts?page_size=0").status_code == 422
    assert client.get("/api/v1/districts?page_size=1000").status_code == 422
    assert client.get(f"/api/v1/districts?search={'x'*101}").status_code == 422


# =============================================================================
# 2. BLOCK-BY-DISTRICT PAGINATION & SEARCH (GET /api/v1/districts/{id}/blocks)
# =============================================================================

def test_api_blocks_default_pagination(client, db_session):
    """Verify blocks retrieval for Nashik (15 blocks) and Pune (13 blocks) with default pagination."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    pune = db_session.query(District).filter(District.name == "Pune").first()
    assert nashik is not None
    assert pune is not None

    # Nashik: exactly 15 blocks
    r_nsk = client.get(f"/api/v1/districts/{nashik.id}/blocks")
    assert r_nsk.status_code == 200
    d_nsk = r_nsk.json()
    assert d_nsk["total"] == 15
    assert d_nsk["page"] == 1
    assert d_nsk["page_size"] == 20
    assert d_nsk["total_pages"] == 1
    assert len(d_nsk["items"]) == 15

    for b in d_nsk["items"]:
        assert b["district_id"] == nashik.id
        assert "id" in b and "name" in b
    nsk_names = [b["name"] for b in d_nsk["items"]]
    assert nsk_names == sorted(nsk_names)
    assert "Baglan" in nsk_names
    assert "Dindori" in nsk_names

    # Pune: exactly 13 blocks
    r_pun = client.get(f"/api/v1/districts/{pune.id}/blocks")
    assert r_pun.status_code == 200
    d_pun = r_pun.json()
    assert d_pun["total"] == 13
    assert len(d_pun["items"]) == 13
    for b in d_pun["items"]:
        assert b["district_id"] == pune.id
    pun_names = [b["name"] for b in d_pun["items"]]
    assert pun_names == sorted(pun_names)
    assert "Haveli" in pun_names
    assert "Baramati" in pun_names


def test_api_blocks_custom_pagination(client, db_session):
    """Verify pagination slicing within district blocks."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    assert nashik is not None

    r1 = client.get(f"/api/v1/districts/{nashik.id}/blocks?page=1&page_size=5")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 15
    assert d1["total_pages"] == 3
    assert len(d1["items"]) == 5

    r2 = client.get(f"/api/v1/districts/{nashik.id}/blocks?page=2&page_size=5")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 5

    # Ensure no overlap between page 1 and page 2
    p1_ids = {b["id"] for b in d1["items"]}
    p2_ids = {b["id"] for b in d2["items"]}
    assert p1_ids.isdisjoint(p2_ids)

    # Page beyond available
    r_out = client.get(f"/api/v1/districts/{nashik.id}/blocks?page=10&page_size=5")
    assert r_out.status_code == 200
    assert r_out.json()["items"] == []


def test_api_blocks_search_within_district(client, db_session):
    """Verify server-side case-insensitive search strictly scoped to district."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    assert nashik is not None

    for term in ["baglan", "BAGLAN", "Baglan", "Bag"]:
        res = client.get(f"/api/v1/districts/{nashik.id}/blocks?search={term}")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Baglan"


def test_api_blocks_cross_district_search_isolation(client, db_session):
    """
    Verify search inside District A cannot return blocks belonging to District B.
    'Haveli' belongs to Pune; searching 'Haveli' in Nashik must return 0 results.
    """
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    pune = db_session.query(District).filter(District.name == "Pune").first()
    assert nashik is not None and pune is not None

    # Search Pune block inside Nashik -> 0 matches
    r_nsk_leak = client.get(f"/api/v1/districts/{nashik.id}/blocks?search=Haveli")
    assert r_nsk_leak.status_code == 200
    assert r_nsk_leak.json()["total"] == 0
    assert r_nsk_leak.json()["items"] == []

    # Search Nashik block inside Pune -> 0 matches
    r_pun_leak = client.get(f"/api/v1/districts/{pune.id}/blocks?search=Baglan")
    assert r_pun_leak.status_code == 200
    assert r_pun_leak.json()["total"] == 0
    assert r_pun_leak.json()["items"] == []


def test_api_blocks_by_district_invalid_returns_404(client):
    """Non-existent district returns HTTP 404."""
    response = client.get("/api/v1/districts/999999/blocks")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_api_blocks_by_district_malformed_returns_422(client):
    """Malformed district ID or pagination params return HTTP 422."""
    assert client.get("/api/v1/districts/0/blocks").status_code == 422
    assert client.get("/api/v1/districts/-5/blocks").status_code == 422
    assert client.get("/api/v1/districts/invalid_id/blocks").status_code == 422
    assert client.get("/api/v1/districts/1/blocks?page=0").status_code == 422
    assert client.get("/api/v1/districts/1/blocks?page_size=1000").status_code == 422


def test_api_blocks_by_district_empty_district(client, db_session):
    """A valid district with 0 blocks returns 200 with an empty list envelope, not 404."""
    temp_dist = District(name="EmptyDistrictTestP34", state="Maharashtra")
    db_session.add(temp_dist)
    db_session.commit()
    db_session.refresh(temp_dist)

    try:
        response = client.get(f"/api/v1/districts/{temp_dist.id}/blocks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert data["items"] == []
    finally:
        db_session.delete(temp_dist)
        db_session.commit()


# =============================================================================
# 3. PANCHAYAT-BY-BLOCK PAGINATION & SEARCH (GET /api/v1/blocks/{id}/panchayats)
# =============================================================================

def test_api_panchayats_pagination_and_deterministic_order(client, db_session):
    """Verify paginated Panchayats strictly scoped to a block with deterministic order."""
    baglan = db_session.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    r1 = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?page=1&page_size=20")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] > 20
    assert d1["page"] == 1
    assert d1["page_size"] == 20
    assert len(d1["items"]) == 20

    # Verify deterministic ordering (name ASC, id ASC)
    names = [p["name"] for p in d1["items"]]
    assert names == sorted(names)

    r2 = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?page=2&page_size=20")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 20

    p1_ids = {p["id"] for p in d1["items"]}
    p2_ids = {p["id"] for p in d2["items"]}
    assert p1_ids.isdisjoint(p2_ids)


def test_api_panchayats_search_by_name_and_lgd(client, db_session):
    """Verify server-side search by name (case-insensitive) and LGD code within block scope."""
    baglan = db_session.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    # Search by name case-insensitive
    for term in ["ajmer", "AJMER", "Ajmer"]:
        res = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?search={term}")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any("Ajmer" in p["name"] for p in data["items"])

    # Search by exact LGD code of Ajmer Saundane (182597)
    res_lgd = client.get(f"/api/v1/blocks/{baglan.id}/panchayats?search=182597")
    assert res_lgd.status_code == 200
    d_lgd = res_lgd.json()
    assert d_lgd["total"] == 1
    assert d_lgd["items"][0]["lgd_code"] == 182597


def test_api_panchayats_cross_block_search_isolation(client, db_session):
    """Verify searching for a Baglan panchayat inside Dindori returns 0 matches."""
    dindori = db_session.query(Block).filter(Block.name == "Dindori").first()
    assert dindori is not None

    res = client.get(f"/api/v1/blocks/{dindori.id}/panchayats?search=182597")
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["items"] == []


def test_api_panchayats_by_block_invalid_returns_404(client):
    """Non-existent block returns HTTP 404."""
    response = client.get("/api/v1/blocks/999999/panchayats")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_panchayats_by_block_malformed_returns_422(client):
    """Malformed block ID or pagination params return HTTP 422."""
    assert client.get("/api/v1/blocks/0/panchayats").status_code == 422
    assert client.get("/api/v1/blocks/-10/panchayats").status_code == 422
    assert client.get("/api/v1/blocks/abc/panchayats").status_code == 422
    assert client.get("/api/v1/blocks/1/panchayats?page=0").status_code == 422
    assert client.get("/api/v1/blocks/1/panchayats?page_size=500").status_code == 422  # max 200


def test_api_panchayats_by_block_empty_block(client, db_session):
    """A valid block with 0 Panchayats returns 200 with empty items, not 404."""
    nashik = db_session.query(District).filter(District.name == "Nashik").first()
    temp_block = Block(district_id=nashik.id, name="EmptyBlockTestP34")
    db_session.add(temp_block)
    db_session.commit()
    db_session.refresh(temp_block)

    try:
        response = client.get(f"/api/v1/blocks/{temp_block.id}/panchayats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert data["items"] == []
    finally:
        db_session.delete(temp_block)
        db_session.commit()


# =============================================================================
# 4. PANCHAYAT DETAIL (GET /api/v1/panchayats/{panchayat_id})
# =============================================================================

def test_api_panchayat_detail_nashik_and_pune(client, db_session):
    """Verify detail retrieval for both a Nashik and a Pune Panchayat."""
    r_nsk = client.get("/api/v1/panchayats/1001")
    assert r_nsk.status_code == 200
    d_nsk = r_nsk.json()
    assert d_nsk["id"] == 1001
    assert "Ajmer" in d_nsk["name"]
    assert d_nsk["district_name"] == "Nashik"
    assert d_nsk["block_name"] == "Baglan"
    assert d_nsk["latitude"] is not None
    assert d_nsk["longitude"] is not None

    pune_p = db_session.query(Panchayat).filter(Panchayat.id > 100000).first()
    assert pune_p is not None

    r_pun = client.get(f"/api/v1/panchayats/{pune_p.id}")
    assert r_pun.status_code == 200
    d_pun = r_pun.json()
    assert d_pun["id"] == pune_p.id
    assert d_pun["name"] == pune_p.name
    assert d_pun["district_name"] == "Pune"


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
# 5. CROSS-HIERARCHY ISOLATION & REGRESSION
# =============================================================================

def test_api_cross_hierarchy_isolation(client, db_session):
    """Verify that Panchayat 1001 (Baglan) never appears under Dindori or Haveli."""
    dindori = db_session.query(Block).filter(Block.name == "Dindori").first()
    haveli = db_session.query(Block).filter(Block.name == "Haveli").first()
    assert dindori is not None and haveli is not None

    r_dindori = client.get(f"/api/v1/blocks/{dindori.id}/panchayats?page_size=200")
    assert r_dindori.status_code == 200
    dindori_ids = [p["id"] for p in r_dindori.json()["items"]]
    assert 1001 not in dindori_ids

    r_haveli = client.get(f"/api/v1/blocks/{haveli.id}/panchayats?page_size=200")
    assert r_haveli.status_code == 200
    haveli_ids = [p["id"] for p in r_haveli.json()["items"]]
    assert 1001 not in haveli_ids


def test_api_multi_district_no_special_routes(client):
    """Ensure no hardcoded /nashik/... or /pune/... routes exist."""
    assert client.get("/api/v1/nashik/blocks").status_code == 404
    assert client.get("/api/v1/pune/blocks").status_code == 404


def test_api_regression_health_endpoint(client):
    """Health check endpoint remains operational."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["ok", "healthy"]


def test_api_regression_forecast_lookup(client):
    """Weather downscaled forecast lookup for Panchayat 1001 still functions cleanly."""
    response = client.get("/api/v1/forecast/panchayat/1001")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert response.json()["panchayat_id"] == 1001
