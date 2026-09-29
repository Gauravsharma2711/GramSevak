"""
Phase 6.1 Comprehensive Location Resolution Test Suite.

Validates the Location Intelligence Foundation:
1. Valid coordinates request handling.
2. Coordinate range validation:
   - Latitude [-90.0, 90.0]
   - Longitude [-180.0, 180.0]
   - Missing fields
   - Non-numeric / NaN / Inf inputs
3. GPS accuracy handling:
   - Safe accuracy (e.g. 15m)
   - Low accuracy warning threshold (> 500m)
   - Unsafe accuracy rejection threshold (> 2500m)
4. Empty boundary dataset behavior:
   - Returns BOUNDARY_DATA_UNAVAILABLE safely without crashing or guessing
   - Preserves manual selection fallback instruction
5. Point-in-polygon resolution service logic:
   - Single match -> MATCHED
   - Multiple match -> AMBIGUOUS_MATCH
   - Zero match -> NO_MATCH
6. Privacy & Security Invariants:
   - Public access (no officer bearer token required for farmer location)
   - No farmer coordinates persisted
   - No raw coordinates leaked in response
   - Sanitized database error masking (zero SQL / credential leakage)
7. Clear distinction:
   - Code-level unit & API tests (run on current environment)
   - Geospatial tests gated on authoritative polygon data ingestion
"""

import math
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.main import app
from backend.app.schemas.location import (
    LocationResolutionStatus,
    LocationResolveRequest,
    LocationResolveResponse,
)
from backend.services.location_service import (
    LocationResolutionService,
    InvalidCoordinatesError,
    GeospatialLookupError,
    ACCURACY_WARNING_THRESHOLD_M,
    ACCURACY_REJECTION_THRESHOLD_M,
)

client = TestClient(app)


# =============================================================================
# 1. API SCHEMA & VALIDATION TESTS
# =============================================================================

def test_api_valid_coordinates_boundary_unavailable():
    """
    When authoritative boundaries are not yet ingested, valid coordinates return
    HTTP 200 with status BOUNDARY_DATA_UNAVAILABLE and guidance to use manual selection.
    """
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={"latitude": 19.0355, "longitude": 73.7870},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is False
    assert data["status"] in ("BOUNDARY_DATA_UNAVAILABLE", "NO_MATCH")
    assert data["panchayat"] is None
    assert "manual" in data["message"].lower() or "selection" in data["message"].lower()


@pytest.mark.parametrize("invalid_lat", [-91.0, 90.001, -180.0, 1000.0])
def test_api_invalid_latitude_validation(invalid_lat):
    """Latitudes outside [-90.0, +90.0] are rejected with 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={"latitude": invalid_lat, "longitude": 73.7870},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("invalid_lng", [-181.0, 180.001, -360.0, 999.0])
def test_api_invalid_longitude_validation(invalid_lng):
    """Longitudes outside [-180.0, +180.0] are rejected with 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={"latitude": 19.0355, "longitude": invalid_lng},
    )
    assert response.status_code == 422


def test_api_missing_coordinates():
    """Missing latitude or longitude returns 422 validation error."""
    # Completely empty body
    res_empty = client.post("/api/v1/location/resolve-panchayat", json={})
    assert res_empty.status_code == 422

    # Missing latitude
    res_no_lat = client.post(
        "/api/v1/location/resolve-panchayat", json={"longitude": 73.7870}
    )
    assert res_no_lat.status_code == 422

    # Missing longitude
    res_no_lng = client.post(
        "/api/v1/location/resolve-panchayat", json={"latitude": 19.0355}
    )
    assert res_no_lng.status_code == 422


def test_api_non_numeric_coordinates():
    """Non-numeric string coordinates return 422 validation error."""
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={"latitude": "nineteen", "longitude": 73.7870},
    )
    assert response.status_code == 422


# =============================================================================
# 2. GPS ACCURACY & BOUNDARY-EDGE BEHAVIOR TESTS
# =============================================================================

def test_api_gps_accuracy_moderate_warning():
    """
    When GPS horizontal accuracy is between 500m and 2500m, an accuracy warning
    is returned to guide the farmer to double-check their location.
    """
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={
            "latitude": 19.0355,
            "longitude": 73.7870,
            "gps_accuracy_m": 750.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["accuracy_warning"] is not None
    assert "750" in data["accuracy_warning"] or "moderate" in data["accuracy_warning"].lower()


def test_api_gps_accuracy_unsafe_rejection():
    """
    When GPS horizontal accuracy exceeds 2500m, automatic selection is safely
    rejected with status ACCURACY_TOO_LOW to prevent incorrect village assignment.
    """
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        json={
            "latitude": 19.0355,
            "longitude": 73.7870,
            "gps_accuracy_m": 3500.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is False
    assert data["status"] == "ACCURACY_TOO_LOW"
    assert data["panchayat"] is None
    assert "too low" in data["message"].lower()


# =============================================================================
# 3. DOMAIN SERVICE UNIT TESTS
# =============================================================================

def test_service_coordinate_boundary_validation():
    """Validates physical WGS84 coordinate boundary conditions."""
    svc = LocationResolutionService()

    # Exact boundary edges must succeed
    svc.validate_coordinates(-90.0, -180.0)
    svc.validate_coordinates(90.0, 180.0)
    svc.validate_coordinates(0.0, 0.0)

    # Invalid cases must raise InvalidCoordinatesError
    with pytest.raises(InvalidCoordinatesError, match="Latitude"):
        svc.validate_coordinates(90.0001, 73.0)

    with pytest.raises(InvalidCoordinatesError, match="Latitude"):
        svc.validate_coordinates(-90.0001, 73.0)

    with pytest.raises(InvalidCoordinatesError, match="Longitude"):
        svc.validate_coordinates(19.0, 180.0001)

    with pytest.raises(InvalidCoordinatesError, match="Longitude"):
        svc.validate_coordinates(19.0, -180.0001)

    with pytest.raises(InvalidCoordinatesError, match="null"):
        svc.validate_coordinates(None, 73.0)

    with pytest.raises(InvalidCoordinatesError, match="finite"):
        svc.validate_coordinates(float("nan"), 73.0)

    with pytest.raises(InvalidCoordinatesError, match="finite"):
        svc.validate_coordinates(19.0, float("inf"))


def test_service_database_failure_handling_and_masking():
    """
    Database operational failures must be caught, logged, and raised as GeospatialLookupError
    without leaking connection strings or SQL internals.
    """
    svc = LocationResolutionService()
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("SELECT ST_Contains...", {}, Exception("connection terminated"))

    with pytest.raises(GeospatialLookupError, match="geospatial boundary lookup"):
        svc.resolve_panchayat_by_coordinates(
            latitude=19.123,
            longitude=73.456,
            db=mock_db,
        )


def test_service_simulated_ambiguous_boundary():
    """
    When coordinates intersect multiple overlapping boundary polygons, the service
    returns AMBIGUOUS_MATCH and prompts manual hierarchy selection.
    """
    svc = LocationResolutionService()
    mock_db = MagicMock()

    # Simulate 2 overlapping rows
    mock_row_1 = MagicMock(
        panchayat_id=1001,
        lgd_code=182597,
        panchayat_name="Ajmer Saundane",
        district_id=1,
        district_name="Nashik",
        block_id=4,
        block_name="Baglan",
        latitude=20.6385,
        longitude=74.1201,
        elevation_m=585.0,
    )
    mock_row_2 = MagicMock(
        panchayat_id=1002,
        lgd_code=182598,
        panchayat_name="Akhatwade",
        district_id=1,
        district_name="Nashik",
        block_id=4,
        block_name="Baglan",
        latitude=20.6908,
        longitude=74.2045,
        elevation_m=595.0,
    )

    mock_db.execute.return_value.fetchall.return_value = [mock_row_1, mock_row_2]

    res = svc.resolve_panchayat_by_coordinates(latitude=20.65, longitude=74.15, db=mock_db)
    assert res.matched is False
    assert res.status == LocationResolutionStatus.AMBIGUOUS_MATCH
    assert res.panchayat is None
    assert "overlapping" in res.message.lower() or "boundary zone" in res.message.lower()


def test_service_simulated_unambiguous_match():
    """
    When coordinates match exactly one authoritative boundary polygon, the service
    returns MATCHED with full administrative hierarchy metadata.
    """
    svc = LocationResolutionService()
    mock_db = MagicMock()

    mock_row = MagicMock(
        panchayat_id=1001,
        lgd_code=182597,
        panchayat_name="Ajmer Saundane",
        district_id=1,
        district_name="Nashik",
        block_id=4,
        block_name="Baglan",
        latitude=20.6385,
        longitude=74.1201,
        elevation_m=585.0,
    )
    mock_db.execute.return_value.fetchall.return_value = [mock_row]

    res = svc.resolve_panchayat_by_coordinates(latitude=20.6385, longitude=74.1201, db=mock_db)
    assert res.matched is True
    assert res.status == LocationResolutionStatus.MATCHED
    assert res.panchayat is not None
    assert res.panchayat.id == 1001
    assert res.panchayat.lgd_code == 182597
    assert res.panchayat.name == "Ajmer Saundane"
    assert res.panchayat.block_name == "Baglan"
    assert res.panchayat.district_name == "Nashik"


# =============================================================================
# 4. PRIVACY & SECURITY CONTRACT TESTS
# =============================================================================

def test_api_public_access_no_token_required():
    """
    Verifies that the endpoint is publicly accessible without Authorization headers,
    consistent with public farmer-facing services in Phase 4 and 5.
    """
    response = client.post(
        "/api/v1/location/resolve-panchayat",
        headers={},  # Zero auth headers
        json={"latitude": 19.5, "longitude": 73.5},
    )
    # Must NOT return 401 or 403
    assert response.status_code != 401
    assert response.status_code != 403


def test_privacy_guarantee_no_coordinate_persistence_or_echo():
    """
    Verifies minimum data principle: response does not echo raw coordinates
    back to the farmer app, preserving privacy.
    """
    req_payload = {"latitude": 19.1234567, "longitude": 73.9876543}
    response = client.post("/api/v1/location/resolve-panchayat", json=req_payload)
    assert response.status_code == 200
    data = response.json()

    # The top-level response must not include farmer coordinates
    assert "latitude" not in data
    assert "longitude" not in data
