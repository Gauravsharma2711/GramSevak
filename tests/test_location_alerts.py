"""
Phase 6.2 Test Suite: Panchayat-Based Location Alerts and Farmer Notifications.

Validates the 11 core requirements defined in Phase 6.2:
1. Approved advisory creates eligible notification.
2. Unapproved advisory does not create notification (DRAFT, UNDER_REVIEW).
3. Rejected advisory does not create notification (REJECTED).
4. Safety-failed advisory does not create notification (FAILED_VALIDATION).
5. Wrong Panchayat does not create notification (strict Panchayat scoping).
6. Duplicate event is prevented (idempotent business key adv:{id}:v{version}:p{panchayat_id}).
7. Retry does not duplicate notification (re-targets failed deliveries without duplicating events).
8. Stale advisory version is rejected (cannot notify for older version if newer approved).
9. Missing Panchayat is rejected (null/zero panchayat_id is non-eligible).
10. Notification provider failure is handled safely (status FAILED, error logged, no crash).
11. Invalid notification token is handled safely (auto-deactivates dead token).
12. Farmer API endpoints: POST /api/v1/farmer/device-token and GET /api/v1/farmer/notifications.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.advisory import Advisory
from backend.app.models.notification import FarmerDevice, NotificationEvent, NotificationDelivery
from backend.services.notification_service import NotificationService
from backend.services.notification_provider import BaseNotificationProvider, DeliveryResult

client = TestClient(app)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """Yield a database session and clean up created test records."""
    db_gen = get_db()
    db: Session = next(db_gen)
    
    created_device_ids = []
    created_event_ids = []
    created_advisory_ids = []

    yield {
        "db": db,
        "device_ids": created_device_ids,
        "event_ids": created_event_ids,
        "advisory_ids": created_advisory_ids,
    }

    try:
        if created_event_ids:
            db.query(NotificationDelivery).filter(
                NotificationDelivery.event_id.in_(created_event_ids)
            ).delete(synchronize_session=False)
            db.query(NotificationEvent).filter(
                NotificationEvent.id.in_(created_event_ids)
            ).delete(synchronize_session=False)
        if created_device_ids:
            db.query(FarmerDevice).filter(
                FarmerDevice.id.in_(created_device_ids)
            ).delete(synchronize_session=False)
        if created_advisory_ids:
            db.query(Advisory).filter(
                Advisory.id.in_(created_advisory_ids)
            ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _create_advisory(
    db: Session,
    advisory_ids_list: list,
    panchayat_id: int = 1001,
    status: str = "APPROVED",
    validation_status: str = "VALIDATED",
    version: int = 1,
    rainfall_mm: float = 45.0,
    severity: str = "HIGH",
) -> Advisory:
    """Helper to persist a test advisory record matching existing DB schema."""
    advisory = Advisory(
        panchayat_id=panchayat_id,
        forecast_id=9999,
        forecast_date=date(2026, 9, 29),
        rainfall_mm=rainfall_mm,
        rainfall_category="HEAVY",
        severity=severity,
        advisory_title="Heavy Rain Drainage Alert",
        advisory_text="Heavy rainfall expected. Clear field drainage channels.",
        rule_version="v1.0.0",
        status=status,
        version=version,
        advisory_source="DETERMINISTIC_RULES",
        validation_status=validation_status,
        original_content={
            "advisory_title": "Heavy Rain Drainage Alert",
            "advisory_text": "Heavy rainfall expected. Clear field drainage channels.",
            "severity": severity,
        },
        approved_content={
            "advisory_title": "Heavy Rain Drainage Alert",
            "advisory_text": "Heavy rainfall expected. Clear field drainage channels.",
            "severity": severity,
        },
        officer_id="test_officer_1",
        approved_at=datetime.now(timezone.utc) if status in ("APPROVED", "PUBLISHED") else None,
    )
    db.add(advisory)
    db.commit()
    db.refresh(advisory)
    advisory_ids_list.append(advisory.id)
    return advisory


# =============================================================================
# 1. ELIGIBILITY TESTS
# =============================================================================

def test_approved_advisory_creates_eligible_notification(db_session):
    """Requirement 1: Approved, safety-passed advisory creates an eligible notification event."""
    db = db_session["db"]
    service = NotificationService(db)

    # Register farmer devices for Panchayat 1001
    dev1 = service.register_device(
        device_token="dev_tok_test_1001_a",
        panchayat_id=1001,
        platform="android",
        language_preference="en",
    )
    db_session["device_ids"].append(dev1.id)

    advisory = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
    )

    result = service.process_advisory_alerts(advisory.id)
    assert result.success is True
    assert result.event_id is not None
    assert result.eligible_devices_count >= 1
    assert result.successful_deliveries_count >= 1
    db_session["event_ids"].append(result.event_id)

    # Verify event stored in DB
    event = db.query(NotificationEvent).filter_by(id=result.event_id).first()
    assert event is not None
    assert event.panchayat_id == 1001
    assert event.severity == "HIGH"
    assert "Heavy Rain" in event.title


def test_unapproved_advisory_does_not_create_notification(db_session):
    """Requirement 2: Unapproved advisories (DRAFT, UNDER_REVIEW) do not create notifications."""
    db = db_session["db"]
    service = NotificationService(db)

    for unapproved_status in ["DRAFT", "UNDER_REVIEW"]:
        adv = _create_advisory(
            db, db_session["advisory_ids"],
            panchayat_id=1001,
            status=unapproved_status,
            validation_status="VALIDATED",
        )
        is_eligible, reason = service.evaluate_advisory_eligibility(adv)
        assert is_eligible is False
        assert "not approved" in reason

        result = service.process_advisory_alerts(adv.id)
        assert result.success is False
        assert result.event_id is None


def test_rejected_advisory_does_not_create_notification(db_session):
    """Requirement 3: Rejected advisory cannot trigger farmer notifications."""
    db = db_session["db"]
    service = NotificationService(db)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="REJECTED",
        validation_status="VALIDATED",
    )
    is_eligible, reason = service.evaluate_advisory_eligibility(adv)
    assert is_eligible is False
    assert "not approved" in reason

    result = service.process_advisory_alerts(adv.id)
    assert result.success is False
    assert result.event_id is None


def test_safety_failed_advisory_does_not_create_notification(db_session):
    """Requirement 4: Safety-failed or flagged advisory cannot trigger notifications."""
    db = db_session["db"]
    service = NotificationService(db)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="FAILED_VALIDATION",
    )
    is_eligible, reason = service.evaluate_advisory_eligibility(adv)
    assert is_eligible is False
    assert "failed automated safety" in reason

    result = service.process_advisory_alerts(adv.id)
    assert result.success is False
    assert result.event_id is None


def test_wrong_panchayat_does_not_create_notification(db_session):
    """Requirement 5: Notifications are strictly scoped to the target Panchayat."""
    db = db_session["db"]
    service = NotificationService(db)

    # Device in Panchayat 1002 (Akhatwade)
    dev_other = service.register_device(
        device_token="tok_akhatwade_other_village",
        panchayat_id=1002,
        platform="android",
    )
    db_session["device_ids"].append(dev_other.id)

    # Advisory for Panchayat 1008 (Mulher)
    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1008,
        status="APPROVED",
        validation_status="VALIDATED",
    )

    result = service.process_advisory_alerts(adv.id)
    assert result.success is True
    db_session["event_ids"].append(result.event_id)

    # Verify dev_other received ZERO deliveries for Panchayat 1008
    deliveries = db.query(NotificationDelivery).filter_by(
        event_id=result.event_id,
        device_id=dev_other.id,
    ).all()
    assert len(deliveries) == 0


def test_duplicate_event_is_prevented(db_session):
    """Requirement 6: Duplicate events are prevented using stable idempotency key."""
    db = db_session["db"]
    service = NotificationService(db)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
        version=1,
    )

    # First run creates event
    res1 = service.process_advisory_alerts(adv.id)
    assert res1.success is True
    first_event_id = res1.event_id
    db_session["event_ids"].append(first_event_id)

    # Second run detects already processed event and returns the existing event safely
    res2 = service.process_advisory_alerts(adv.id)
    assert res2.success is True
    assert res2.event_id == first_event_id
    assert "already processed" in res2.status_message


def test_retry_does_not_duplicate_notification(db_session):
    """Requirement 7: Retrying failed deliveries does not duplicate events or successful deliveries."""
    db = db_session["db"]
    
    # Custom provider that fails the first time
    class FlakyProvider(BaseNotificationProvider):
        def __init__(self):
            self.should_fail = True

        def send_notification(self, device_token, title, body, data=None):
            if self.should_fail:
                return DeliveryResult(success=False, device_token=device_token, error_message="Network glitch")
            return DeliveryResult(success=True, device_token=device_token, message_id="msg_recovered")

    flaky_provider = FlakyProvider()
    service = NotificationService(db, provider=flaky_provider)

    dev = service.register_device(
        device_token="flaky_retry_token_uniq_1005",
        panchayat_id=1005,
    )
    db_session["device_ids"].append(dev.id)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1005,
        status="APPROVED",
        validation_status="VALIDATED",
    )

    # First attempt: failure
    res1 = service.process_advisory_alerts(adv.id)
    assert res1.failed_deliveries_count >= 1
    event_id = res1.event_id
    db_session["event_ids"].append(event_id)

    # Provider recovers
    flaky_provider.should_fail = False

    # Retry the event
    retry_res = service.retry_notification_event(event_id)
    assert retry_res.success is True
    assert retry_res.successful_deliveries_count >= 1
    assert retry_res.failed_deliveries_count == 0

    # Ensure total delivery rows for this device is still 1 (not duplicated)
    deliveries = db.query(NotificationDelivery).filter_by(
        event_id=event_id,
        target_device_id=dev.id,
    ).all()
    assert len(deliveries) == 1
    assert deliveries[0].delivery_status == "DELIVERED"


def test_stale_advisory_version_is_rejected(db_session):
    """Requirement 8: Stale advisory version is rejected if newer approved version exists."""
    db = db_session["db"]
    service = NotificationService(db)

    # Version 1 approved
    adv_v1 = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
        version=1,
    )

    # Version 2 approved later
    adv_v2 = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
        version=2,
    )

    # Evaluating v1 now must be rejected as stale
    is_eligible, reason = service.evaluate_advisory_eligibility(adv_v1)
    assert is_eligible is False
    assert "superseded" in reason.lower()


def test_missing_panchayat_is_rejected(db_session):
    """Requirement 9: Advisory with missing/zero Panchayat is rejected."""
    db = db_session["db"]
    service = NotificationService(db)

    adv = Advisory(
        forecast_id=9998,
        panchayat_id=0,
        forecast_date=date(2026, 9, 29),
        status="APPROVED",
        validation_status="VALIDATED",
        version=1,
        severity="HIGH",
    )
    is_eligible, reason = service.evaluate_advisory_eligibility(adv)
    assert is_eligible is False
    assert "missing target panchayat" in reason.lower()


def test_notification_provider_failure_is_handled_safely(db_session):
    """Requirement 10: Provider failure is caught and stored as FAILED without throwing exceptions."""
    db = db_session["db"]

    class FailingProvider(BaseNotificationProvider):
        def send_notification(self, device_token, title, body, data=None):
            return DeliveryResult(success=False, device_token=device_token, error_message="Provider 503 Service Unavailable")

    service = NotificationService(db, provider=FailingProvider())

    dev = service.register_device(
        device_token="tok_failing_provider_test",
        panchayat_id=1001,
    )
    db_session["device_ids"].append(dev.id)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
    )

    res = service.process_advisory_alerts(adv.id)
    assert res.success is True  # Batch processing finishes safely
    assert res.failed_deliveries_count >= 1
    db_session["event_ids"].append(res.event_id)

    delivery = db.query(NotificationDelivery).filter_by(
        event_id=res.event_id,
        target_device_id=dev.id,
    ).first()
    assert delivery is not None
    assert delivery.delivery_status == "FAILED"
    assert "503" in delivery.error_message


def test_invalid_notification_token_is_handled_safely(db_session):
    """Requirement 11: Invalid device tokens are detected and deactivated automatically."""
    db = db_session["db"]
    service = NotificationService(db)  # Default development provider treats 'mock_invalid_token' as dead

    dev = service.register_device(
        device_token="mock_invalid_token_test",
        panchayat_id=1001,
    )
    db_session["device_ids"].append(dev.id)
    assert dev.is_active is True

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
    )

    res = service.process_advisory_alerts(adv.id)
    db_session["event_ids"].append(res.event_id)

    # Device should now be deactivated
    db.refresh(dev)
    assert dev.is_active is False


# =============================================================================
# 2. FARMER API ENDPOINT INTEGRATION TESTS
# =============================================================================

def test_api_farmer_device_token_registration():
    """Requirement 12a: Farmer device token registration endpoint operates cleanly."""
    payload = {
        "device_token": "client_test_device_fcm_token_xyz",
        "panchayat_id": 1001,
        "platform": "android",
        "language_preference": "hi",
    }
    response = client.post("/api/v1/farmer/device-token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert data["device_token"] == payload["device_token"]
    assert data["panchayat_id"] == 1001


def test_api_farmer_panchayat_notifications(db_session):
    """Requirement 12b: Farmer notifications listing endpoint returns active alerts for Panchayat."""
    db = db_session["db"]
    service = NotificationService(db)

    adv = _create_advisory(
        db, db_session["advisory_ids"],
        panchayat_id=1001,
        status="APPROVED",
        validation_status="VALIDATED",
        severity="HIGH",
    )

    process_res = service.process_advisory_alerts(adv.id)
    db_session["event_ids"].append(process_res.event_id)

    response = client.get("/api/v1/farmer/notifications?panchayat_id=1001&limit=5")
    assert response.status_code == 200
    res_data = response.json()
    alerts = res_data.get("items", res_data) if isinstance(res_data, dict) else res_data
    assert isinstance(alerts, list)
    assert len(alerts) >= 1
    latest = alerts[0]
    assert latest["panchayat_id"] == 1001
    assert latest["severity"] == "HIGH"
    assert "advisory_id" in latest
    assert "published_at" in latest
