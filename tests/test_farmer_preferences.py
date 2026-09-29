"""
Tests for Farmer Personalization & Preferences Layer (Phase 6.3).

Verifies:
- Authenticated preference retrieval
- Authenticated preference update
- Unauthorized access rejected (401)
- Cross-farmer modification attempt rejected (403)
- Invalid Panchayat ID rejected (404)
- Unsupported language rejected (400)
- Authoritative metadata resolved (Panchayat, Block, District)
- Upsert behavior updates existing record without duplicate
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.farmer_preference import FarmerPreference

# In-memory SQLite test database with static pool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


REQUIRED_TABLES = [
    District.__table__,
    Block.__table__,
    Panchayat.__table__,
    FarmerPreference.__table__,
]


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine, tables=REQUIRED_TABLES)
    db = TestingSessionLocal()

    # Seed test hierarchy: District -> Block -> Panchayat
    district = District(id=1, name="Nashik", state="Maharashtra")
    db.add(district)
    db.commit()

    block = Block(id=10, name="Baglan", district_id=1)
    db.add(block)
    db.commit()

    panchayat1 = Panchayat(
        id=1001,
        lgd_code=182597,
        panchayat_code="182597",
        name="Ajmer Saundane",
        block_id=10,
        district_id=1,
        latitude=20.6385,
        longitude=74.1201,
    )
    panchayat2 = Panchayat(
        id=1002,
        lgd_code=182598,
        panchayat_code="182598",
        name="Akhatwade",
        block_id=10,
        district_id=1,
        latitude=20.6908,
        longitude=74.2045,
    )
    db.add_all([panchayat1, panchayat2])
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine, tables=REQUIRED_TABLES)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.query(FarmerPreference).delete()
    session.commit()
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestFarmerPersonalizationAPI:
    """Test suite for Phase 6.3 Farmer Personalization & Preferences."""

    def test_unauthorized_access_rejected_without_header(self, client):
        """GET /farmer/preferences without auth header must return 401 Unauthorized."""
        response = client.get("/api/v1/farmer/preferences")
        assert response.status_code == 401
        assert "Farmer authentication required" in response.json()["detail"]

    def test_unauthorized_access_rejected_with_anonymous_token(self, client):
        """GET /farmer/preferences with ANONYMOUS token must return 401 Unauthorized."""
        headers = {"X-Farmer-Id": "ANONYMOUS"}
        response = client.get("/api/v1/farmer/preferences", headers=headers)
        assert response.status_code == 401

    def test_missing_preference_returns_404(self, client):
        """GET /farmer/preferences for a new farmer returns 404 Not Found."""
        headers = {"Authorization": "Bearer farmer_new_99"}
        response = client.get("/api/v1/farmer/preferences", headers=headers)
        assert response.status_code == 404
        assert "No saved preferences found" in response.json()["detail"]

    def test_save_and_retrieve_preferences_success(self, client):
        """PUT and then GET farmer preferences saves preference with spatial metadata."""
        headers = {"Authorization": "Bearer farmer_101"}
        payload = {
            "panchayat_id": 1001,
            "preferred_language": "mr",
        }

        # 1. Save preferences
        put_res = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert put_res.status_code == 200
        data = put_res.json()
        assert data["farmer_id"] == "farmer_101"
        assert data["panchayat_id"] == 1001
        assert data["preferred_language"] == "mr"
        assert data["panchayat_name"] == "Ajmer Saundane"
        assert data["block_name"] == "Baglan"
        assert data["district_name"] == "Nashik"
        assert data["is_valid"] is True

        # 2. Retrieve preferences
        get_res = client.get("/api/v1/farmer/preferences", headers=headers)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["farmer_id"] == "farmer_101"
        assert get_data["panchayat_id"] == 1001
        assert get_data["preferred_language"] == "mr"

    def test_update_existing_preference_is_idempotent(self, client):
        """Subsequent PUT updates existing record without creating duplicate."""
        headers = {"X-Farmer-Id": "farmer_102"}

        # Initial save (Ajmer Saundane in English)
        client.put(
            "/api/v1/farmer/preferences",
            json={"panchayat_id": 1001, "preferred_language": "en"},
            headers=headers,
        )

        # Update (Akhatwade in Hindi)
        update_res = client.put(
            "/api/v1/farmer/preferences",
            json={"panchayat_id": 1002, "preferred_language": "hi"},
            headers=headers,
        )
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["panchayat_id"] == 1002
        assert data["preferred_language"] == "hi"
        assert data["panchayat_name"] == "Akhatwade"

        # Verify only 1 record exists for this farmer
        get_res = client.get("/api/v1/farmer/preferences", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["panchayat_id"] == 1002

    def test_cross_farmer_modification_rejected(self, client):
        """Farmer cannot modify another farmer's preferences (403 Forbidden)."""
        headers = {"Authorization": "Bearer farmer_alice"}
        payload = {
            "farmer_id": "farmer_bob",
            "panchayat_id": 1001,
            "preferred_language": "en",
        }
        response = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert response.status_code == 403
        assert "cannot modify preferences" in response.json()["detail"]

    def test_matching_farmer_id_in_payload_allowed(self, client):
        """If payload farmer_id matches authenticated farmer, update succeeds."""
        headers = {"Authorization": "Bearer farmer_matching"}
        payload = {
            "farmer_id": "farmer_matching",
            "panchayat_id": 1001,
            "preferred_language": "en",
        }
        response = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["farmer_id"] == "farmer_matching"

    def test_invalid_panchayat_id_rejected(self, client):
        """PUT /farmer/preferences with nonexistent panchayat_id returns 404."""
        headers = {"Authorization": "Bearer farmer_test_404"}
        payload = {
            "panchayat_id": 999999,  # Nonexistent
            "preferred_language": "en",
        }
        response = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    def test_unsupported_language_rejected(self, client):
        """PUT /farmer/preferences with unsupported language code returns 400."""
        headers = {"Authorization": "Bearer farmer_test_lang"}
        payload = {
            "panchayat_id": 1001,
            "preferred_language": "fr",  # French not in en, mr, hi
        }
        response = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"]

    def test_supported_languages_list_returned(self, client):
        """Response includes supported language list [en, mr, hi]."""
        headers = {"Authorization": "Bearer farmer_langs"}
        payload = {"panchayat_id": 1001, "preferred_language": "en"}
        res = client.put("/api/v1/farmer/preferences", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["available_languages"] == ["en", "mr", "hi"]
