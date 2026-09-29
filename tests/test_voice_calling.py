"""
Test Suite for Phase 6.4 Advisory Voice Calling & Provider Abstraction.

Verifies:
- Approved advisory can be dispatched via CallingService.
- Unapproved advisory (DRAFT, REJECTED, etc.) is strictly rejected.
- Invalid phone number formats are rejected.
- Idempotency blocks duplicate calls within cooldown window.
- Telephony provider failure (network error, busy line) handled gracefully.
- API endpoint POST /api/v1/advisories/{advisory_id}/voice-call integration.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.advisory import Advisory
from backend.services.calling_provider import (
    DevelopmentCallingProvider,
    CallingResult,
)
from backend.services.calling_service import (
    CallingService,
    get_calling_service,
    IneligibleAdvisoryCallError,
    InvalidPhoneNumberError,
    DuplicateCallError,
)

# Test in-memory SQLite engine
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def db_session():
    # Only create Advisory table to avoid JSONB SQLite dialect issues
    Advisory.__table__.create(bind=engine, checkfirst=True)
    session = TestingSessionLocal()
    try:
        # Create test approved advisory
        approved = Advisory(
            id=101,
            panchayat_id=1001,
            forecast_date=date(2026, 9, 30),
            rainfall_mm=35.0,
            rainfall_category="Moderate Rain",
            severity="HIGH",
            advisory_title="Clear Field Drainage Immediately",
            advisory_text="Continuous rainfall expected. Open peripheral drainage channels.",
            status="APPROVED",
            approved_content={
                "what_is_happening": "Moderate rain for next 24 hours.",
                "why_it_matters": "Water logging in onion beds.",
                "recommended_actions": ["Open field drainage channels.", "Postpone spray operations."],
                "timing": "Next 36 hours.",
                "warnings": ["Do not apply nitrogen fertilizer."],
            },
        )
        # Create test draft advisory
        draft = Advisory(
            id=102,
            panchayat_id=1001,
            forecast_date=date(2026, 9, 30),
            rainfall_mm=10.0,
            rainfall_category="Light Rain",
            severity="LOW",
            advisory_title="Draft Unverified Advisory",
            status="DRAFT",
        )
        session.add(approved)
        session.add(draft)
        session.commit()
        yield session
    finally:
        session.close()
        Advisory.__table__.drop(bind=engine, checkfirst=True)


@pytest.fixture
def mock_calling_provider():
    return DevelopmentCallingProvider(
        simulate_failure_numbers=["+919000000000"],
        simulate_busy_numbers=["+919999999999"],
    )


@pytest.fixture
def calling_service(mock_calling_provider):
    return CallingService(provider=mock_calling_provider)


@pytest.fixture
def client(db_session, calling_service):
    def override_get_db():
        yield db_session

    def override_calling_service():
        return calling_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_calling_service] = override_calling_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Unit Tests for CallingService & DevelopmentCallingProvider
# ============================================================================

def test_calling_provider_phone_normalization(mock_calling_provider):
    assert mock_calling_provider.normalize_phone_number("9876543210") == "+919876543210"
    assert mock_calling_provider.normalize_phone_number("+91 98765 43210") == "+919876543210"
    assert mock_calling_provider.normalize_phone_number("919876543210") == "+919876543210"
    assert mock_calling_provider.validate_phone_number("+919876543210") is True
    assert mock_calling_provider.validate_phone_number("12345") is False
    assert mock_calling_provider.validate_phone_number("abc") is False


def test_calling_service_dispatch_approved_advisory(db_session, calling_service):
    result = calling_service.dispatch_advisory_call(
        db=db_session,
        advisory_id=101,
        phone_number="9876543210",
        language="en",
        farmer_id="farmer_test_01",
    )
    assert result.success is True
    assert result.status == "INITIATED"
    assert result.phone_number == "+919876543210"
    assert result.call_id is not None
    assert result.call_id.startswith("mock-call-101-")


def test_calling_service_rejects_unapproved_advisory(db_session, calling_service):
    with pytest.raises(IneligibleAdvisoryCallError) as exc_info:
        calling_service.dispatch_advisory_call(
            db=db_session,
            advisory_id=102,  # DRAFT
            phone_number="9876543210",
        )
    assert "Only APPROVED or PUBLISHED advisories" in str(exc_info.value)


def test_calling_service_rejects_nonexistent_advisory(db_session, calling_service):
    with pytest.raises(IneligibleAdvisoryCallError) as exc_info:
        calling_service.dispatch_advisory_call(
            db=db_session,
            advisory_id=99999,
            phone_number="9876543210",
        )
    assert "does not exist" in str(exc_info.value)


def test_calling_service_rejects_invalid_phone(db_session, calling_service):
    with pytest.raises(InvalidPhoneNumberError) as exc_info:
        calling_service.dispatch_advisory_call(
            db=db_session,
            advisory_id=101,
            phone_number="12345",  # Invalid
        )
    assert "Invalid recipient phone number" in str(exc_info.value)


def test_calling_service_idempotency_duplicate_call_prevention(db_session, calling_service):
    phone = "9876543211"
    # First call succeeds
    result1 = calling_service.dispatch_advisory_call(
        db=db_session,
        advisory_id=101,
        phone_number=phone,
    )
    assert result1.success is True

    # Immediate second call to same phone for same advisory is blocked
    with pytest.raises(DuplicateCallError) as exc_info:
        calling_service.dispatch_advisory_call(
            db=db_session,
            advisory_id=101,
            phone_number=phone,
        )
    assert "already initiated" in str(exc_info.value)


def test_calling_service_handles_provider_failure_gracefully(db_session, calling_service):
    # Designated failure phone number
    result = calling_service.dispatch_advisory_call(
        db=db_session,
        advisory_id=101,
        phone_number="+919000000000",
    )
    assert result.success is False
    assert result.status == "FAILED"
    assert "gateway timeout" in result.error_message.lower()


# ============================================================================
# API Endpoint Integration Tests (POST /api/v1/advisories/{id}/voice-call)
# ============================================================================

def test_api_dispatch_voice_call_success(client):
    response = client.post(
        "/api/v1/advisories/101/voice-call",
        json={"phone_number": "+919876543220", "language": "en", "farmer_id": "kisan_01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "INITIATED"
    assert data["advisory_id"] == 101
    assert data["call_id"] is not None


def test_api_dispatch_voice_call_unapproved_rejected(client):
    response = client.post(
        "/api/v1/advisories/102/voice-call",
        json={"phone_number": "+919876543221"},
    )
    assert response.status_code == 400
    assert "Only APPROVED or PUBLISHED advisories" in response.json()["detail"]


def test_api_dispatch_voice_call_invalid_phone(client):
    response = client.post(
        "/api/v1/advisories/101/voice-call",
        json={"phone_number": "invalid_phone"},
    )
    assert response.status_code == 400
    assert "Invalid recipient phone number" in response.json()["detail"]


def test_api_dispatch_voice_call_duplicate_conflict(client):
    phone = "+919876543225"
    resp1 = client.post(
        "/api/v1/advisories/101/voice-call",
        json={"phone_number": phone},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/api/v1/advisories/101/voice-call",
        json={"phone_number": phone},
    )
    assert resp2.status_code == 409
    assert "already initiated" in resp2.json()["detail"]
