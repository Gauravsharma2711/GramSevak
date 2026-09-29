"""
GramSevak Location-Based Alert & Notification Service (Phase 6.2).

Responsible for:
Approved Advisory -> Deterministic Alert Eligibility -> Idempotent Event Generation -> Farmer Notification Dispatch.

Key Invariants:
1. Strict Publication Boundary: Exclusively generates alerts from validated, approved advisories.
2. Zero Bypassing: Rejects draft, rejected, safety-failed, or stale advisory versions.
3. Idempotent Business Key: Eliminates duplicate notifications across retries using stable idempotency keys.
4. Privacy First: Farmer coordinates are never persisted or used for notification targeting;
   notifications are strictly scoped to authoritative Panchayat IDs.
5. Decoupled Provider: Dispatches through BaseNotificationProvider abstraction.
6. Safe Retry Semantics: Failed deliveries can be retried without duplicate records.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.core.database import SessionLocal
from backend.app.models.advisory import Advisory
from backend.app.models.panchayat import Panchayat
from backend.app.models.notification import FarmerDevice, NotificationEvent, NotificationDelivery
from backend.app.schemas.notification import (
    ProcessAdvisoryNotificationResponse,
    RetryNotificationResponse,
    FarmerNotificationItem,
)
from backend.services.notification_provider import (
    BaseNotificationProvider,
    get_notification_provider,
    DeliveryResult,
)

logger = logging.getLogger(__name__)

APPROVED_STATUSES = {"APPROVED", "PUBLISHED"}
DISALLOWED_STATUSES = {"DRAFT", "NEEDS_REVIEW", "EDITED", "REJECTED"}


class NotificationServiceError(Exception):
    """Base exception for notification service failures."""
    pass


class IneligibleAdvisoryError(NotificationServiceError):
    """Raised when an advisory does not meet deterministic notification criteria."""
    pass


class NotificationService:
    """
    Domain service orchestrating Panchayat-scoped location alerts for farmers.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        provider: Optional[BaseNotificationProvider] = None,
    ):
        if isinstance(db, BaseNotificationProvider):
            provider = db
            db = None
        self.db = db
        self.provider = provider or get_notification_provider()

    def register_device(
        self,
        *args,
        db: Optional[Session] = None,
        device_token: Optional[str] = None,
        panchayat_id: Optional[int] = None,
        platform: str = "android",
        language_preference: Optional[str] = None,
        **kwargs,
    ) -> FarmerDevice:
        """
        Idempotently registers or updates a farmer device push notification token
        linked strictly to an authoritative Panchayat ID.
        """
        session = db or self.db
        if args:
            if isinstance(args[0], Session):
                session = args[0]
                if len(args) > 1: device_token = args[1]
                if len(args) > 2: panchayat_id = args[2]
                if len(args) > 3: platform = args[3]
            elif isinstance(args[0], str):
                device_token = args[0]
                if len(args) > 1: panchayat_id = args[1]
                if len(args) > 2: platform = args[2]

        if session is None:
            raise ValueError("Database session is required.")
        if not device_token or not device_token.strip():
            raise ValueError("Device token must not be empty.")
        if not panchayat_id:
            raise ValueError("Panchayat ID is required.")

        token = device_token.strip()

        # Verify Panchayat exists
        panchayat = session.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
        if not panchayat:
            raise ValueError(f"Panchayat with ID '{panchayat_id}' does not exist.")

        device = session.query(FarmerDevice).filter(FarmerDevice.device_token == token).first()
        now_utc = datetime.now(timezone.utc)

        if device:
            device.panchayat_id = panchayat_id
            device.device_platform = platform
            device.is_active = True
            device.updated_at = now_utc
        else:
            device = FarmerDevice(
                device_token=token,
                panchayat_id=panchayat_id,
                device_platform=platform,
                is_active=True,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(device)

        session.commit()
        session.refresh(device)
        logger.info(f"[DEVICE_REGISTERED] token={token[:12]}... panchayat_id={panchayat_id} platform={platform}")
        return device

    def evaluate_advisory_eligibility(
        self,
        advisory: Advisory,
        db: Optional[Session] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Deterministic eligibility check ensuring:
        - Status is APPROVED or PUBLISHED
        - Advisory passed automated safety validation
        - Target Panchayat exists
        - Advisory version is current (not superseded)
        """
        session = db or self.db
        if session is None:
            raise ValueError("Database session is required.")

        if advisory.status not in APPROVED_STATUSES:
            return False, f"Advisory status is '{advisory.status}', which is not approved for farmer alerts."

        if advisory.validation_status == "FAILED_VALIDATION":
            return False, "Advisory failed automated safety validation and cannot be broadcast."

        if not advisory.panchayat_id:
            return False, "Advisory is missing target Panchayat identity."

        # Verify latest version invariant: check if a newer approved version exists
        newer_version_exists = session.query(Advisory).filter(
            Advisory.panchayat_id == advisory.panchayat_id,
            Advisory.forecast_date == advisory.forecast_date,
            Advisory.version > advisory.version,
            Advisory.status.in_(APPROVED_STATUSES),
        ).first()

        if newer_version_exists:
            return False, f"Advisory version {advisory.version} is superseded by version {newer_version_exists.version}."

        return True, None

    def derive_alert_category(self, advisory: Advisory) -> str:
        """Derives a standardized alert category from the approved advisory."""
        rf_cat = (advisory.rainfall_category or "").upper()
        if "EXTREMELY HEAVY" in rf_cat or "VERY HEAVY" in rf_cat:
            return "EXTREME_WEATHER_ALERT"
        if "HEAVY" in rf_cat:
            return "HEAVY_RAINFALL"
        if advisory.severity in ("CRITICAL", "HIGH"):
            return "URGENT_AGRO_ADVISORY"
        return "WEATHER_ADVISORY"

    def format_farmer_message(self, advisory: Advisory) -> str:
        """Formats a clean, farmer-safe alert message without internal debugging metadata."""
        # Prefer approved title/text snapshot if available
        title = advisory.advisory_title or "GramSevak Weather Advisory"
        if advisory.approved_content and isinstance(advisory.approved_content, dict):
            approved_text = advisory.approved_content.get("advisory_text")
            if approved_text:
                # Return first sentence or up to 140 chars
                first_sentence = approved_text.split(".")[0].strip()
                return f"{title}: {first_sentence}." if first_sentence else title

        if advisory.advisory_text:
            first_sentence = advisory.advisory_text.split(".")[0].strip()
            return f"{title}: {first_sentence}." if first_sentence else title

        rf_mm = f"{float(advisory.rainfall_mm):.1f}mm" if advisory.rainfall_mm is not None else "precipitation"
        return f"{title}: Expected {rf_mm} on {advisory.forecast_date}."

    def process_advisory_alerts(
        self,
        *args,
        db: Optional[Session] = None,
        advisory_id: Optional[int] = None,
        **kwargs,
    ) -> ProcessAdvisoryNotificationResponse:
        """
        Evaluates an advisory for alert eligibility, creates an idempotent event,
        and dispatches to registered farmer devices in the targeted Panchayat.
        """
        session = db or self.db
        if args:
            if isinstance(args[0], Session):
                session = args[0]
                if len(args) > 1: advisory_id = args[1]
            elif isinstance(args[0], int):
                advisory_id = args[0]

        if session is None:
            raise ValueError("Database session is required.")
        if advisory_id is None:
            raise ValueError("Advisory ID is required.")

        advisory = session.query(Advisory).filter(Advisory.id == advisory_id).first()
        if not advisory:
            raise NotificationServiceError(f"Advisory ID '{advisory_id}' does not exist.")

        is_eligible, ineligibility_reason = self.evaluate_advisory_eligibility(advisory, session)
        if not is_eligible:
            logger.info(f"[ADVISORY_ALERT_INELIGIBLE] advisory_id={advisory_id} reason='{ineligibility_reason}'")
            return ProcessAdvisoryNotificationResponse(
                advisory_id=advisory.id,
                advisory_version=advisory.version,
                panchayat_id=advisory.panchayat_id,
                eligible=False,
                ineligibility_reason=ineligibility_reason,
                status="INELIGIBLE",
            )

        # Stable business idempotency key: prevents duplicate notifications for same version & panchayat
        idempotency_key = f"adv:{advisory.id}:v{advisory.version}:p{advisory.panchayat_id}"
        existing_event = session.query(NotificationEvent).filter(
            NotificationEvent.idempotency_key == idempotency_key
        ).first()

        if existing_event:
            logger.info(f"[ADVISORY_ALERT_DUPLICATE_PREVENTED] key='{idempotency_key}' event_id={existing_event.id}")
            return ProcessAdvisoryNotificationResponse(
                advisory_id=advisory.id,
                advisory_version=advisory.version,
                panchayat_id=advisory.panchayat_id,
                eligible=True,
                event_id=existing_event.id,
                idempotency_key=existing_event.idempotency_key,
                target_count=existing_event.target_count,
                success_count=existing_event.success_count,
                failure_count=existing_event.failure_count,
                status=existing_event.status,
                status_message=f"Advisory already processed for event {existing_event.id}.",
            )

        alert_category = self.derive_alert_category(advisory)
        title = advisory.advisory_title or "GramSevak Weather Advisory"
        message = self.format_farmer_message(advisory)
        severity = (advisory.severity or "LOW").upper()

        event = NotificationEvent(
            idempotency_key=idempotency_key,
            advisory_id=advisory.id,
            advisory_version=advisory.version,
            panchayat_id=advisory.panchayat_id,
            forecast_id=advisory.forecast_id,
            alert_category=alert_category,
            severity=severity,
            title=title,
            message=message,
            status="PENDING",
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        # Discover active farmer devices registered for this Panchayat
        active_devices = session.query(FarmerDevice).filter(
            FarmerDevice.panchayat_id == advisory.panchayat_id,
            FarmerDevice.is_active == True,
        ).all()

        target_count = len(active_devices)
        event.target_count = target_count

        if target_count == 0:
            event.status = "COMPLETED_NO_TARGETS"
            session.commit()
            session.refresh(event)
            return ProcessAdvisoryNotificationResponse(
                advisory_id=advisory.id,
                advisory_version=advisory.version,
                panchayat_id=advisory.panchayat_id,
                eligible=True,
                event_id=event.id,
                idempotency_key=event.idempotency_key,
                target_count=0,
                success_count=0,
                failure_count=0,
                status=event.status,
            )

        success_count = 0
        failure_count = 0
        now_utc = datetime.now(timezone.utc)

        data_payload = {
            "event_id": str(event.id),
            "advisory_id": str(advisory.id),
            "panchayat_id": str(advisory.panchayat_id),
            "category": alert_category,
            "severity": severity,
            "deep_link": f"gramsevak://panchayat/{advisory.panchayat_id}/advisory/{advisory.id}",
        }

        for dev in active_devices:
            result = self.provider.send_notification(
                device_token=dev.device_token,
                title=title,
                body=message,
                data=data_payload,
            )

            # Record individual delivery attempt
            delivery = NotificationDelivery(
                event_id=event.id,
                target_device_id=dev.id,
                status="DELIVERED" if result.success else "FAILED",
                attempt_count=1,
                last_attempted_at=now_utc,
                error_message=result.error_message,
            )
            session.add(delivery)

            if result.success:
                success_count += 1
            else:
                failure_count += 1
                if result.invalid_token:
                    # Deactivate stale/unregistered token
                    dev.is_active = False
                    dev.updated_at = now_utc

        event.success_count = success_count
        event.failure_count = failure_count
        event.status = "SENT" if failure_count == 0 else ("PARTIALLY_DELIVERED" if success_count > 0 else "FAILED")
        session.commit()
        session.refresh(event)

        logger.info(
            f"[ADVISORY_ALERT_DISPATCHED] event_id={event.id} targets={target_count} "
            f"success={success_count} failure={failure_count} status={event.status}"
        )

        return ProcessAdvisoryNotificationResponse(
            advisory_id=advisory.id,
            advisory_version=advisory.version,
            panchayat_id=advisory.panchayat_id,
            eligible=True,
            event_id=event.id,
            idempotency_key=event.idempotency_key,
            target_count=target_count,
            success_count=success_count,
            failure_count=failure_count,
            status=event.status,
        )

    def retry_notification_event(
        self,
        *args,
        db: Optional[Session] = None,
        event_id: Optional[int] = None,
        **kwargs,
    ) -> RetryNotificationResponse:
        """
        Retries failed notification deliveries for an event safely without duplicating successful records.
        """
        session = db or self.db
        if args:
            if isinstance(args[0], Session):
                session = args[0]
                if len(args) > 1: event_id = args[1]
            elif isinstance(args[0], int):
                event_id = args[0]

        if session is None:
            raise ValueError("Database session is required.")
        if event_id is None:
            raise ValueError("Event ID is required.")

        event = session.query(NotificationEvent).filter(NotificationEvent.id == event_id).first()
        if not event:
            raise NotificationServiceError(f"Notification event ID '{event_id}' not found.")

        failed_deliveries = session.query(NotificationDelivery).filter(
            NotificationDelivery.event_id == event.id,
            NotificationDelivery.status == "FAILED",
        ).all()

        retried_count = len(failed_deliveries)
        if retried_count == 0:
            return RetryNotificationResponse(
                event_id=event.id,
                idempotency_key=event.idempotency_key,
                status=event.status,
                retried_count=0,
                success_count=event.success_count,
                failure_count=event.failure_count,
            )

        now_utc = datetime.now(timezone.utc)
        data_payload = {
            "event_id": str(event.id),
            "advisory_id": str(event.advisory_id),
            "panchayat_id": str(event.panchayat_id),
            "category": event.alert_category,
            "severity": event.severity,
            "deep_link": f"gramsevak://panchayat/{event.panchayat_id}/advisory/{event.advisory_id}",
        }

        new_successes = 0
        still_failing = 0

        for delivery in failed_deliveries:
            target_dev = delivery.target_device
            if not target_dev or not target_dev.is_active:
                still_failing += 1
                continue

            result = self.provider.send_notification(
                device_token=target_dev.device_token,
                title=event.title,
                body=event.message,
                data=data_payload,
            )

            delivery.attempt_count += 1
            delivery.last_attempted_at = now_utc

            if result.success:
                delivery.status = "DELIVERED"
                delivery.error_message = None
                new_successes += 1
            else:
                delivery.error_message = result.error_message
                still_failing += 1
                if result.invalid_token:
                    target_dev.is_active = False

        event.success_count += new_successes
        event.failure_count = max(0, event.failure_count - new_successes)
        event.status = "SENT" if event.failure_count == 0 else "PARTIALLY_DELIVERED"
        event.updated_at = now_utc

        session.commit()
        session.refresh(event)

        logger.info(
            f"[NOTIFICATION_RETRIED] event_id={event.id} retried={retried_count} "
            f"new_successes={new_successes} remaining_failures={still_failing}"
        )

        return RetryNotificationResponse(
            event_id=event.id,
            idempotency_key=event.idempotency_key,
            status=event.status,
            retried_count=retried_count,
            success_count=event.success_count,
            failure_count=event.failure_count,
        )

    def list_panchayat_alerts(
        self,
        *args,
        db: Optional[Session] = None,
        panchayat_id: Optional[int] = None,
        limit: int = 10,
        **kwargs,
    ) -> List[FarmerNotificationItem]:
        """
        Retrieves recent published location alerts for a Gram Panchayat for farmer-facing display.
        """
        session = db or self.db
        if args:
            if isinstance(args[0], Session):
                session = args[0]
                if len(args) > 1: panchayat_id = args[1]
                if len(args) > 2: limit = args[2]
            elif isinstance(args[0], int):
                panchayat_id = args[0]
                if len(args) > 1: limit = args[1]

        if session is None:
            raise ValueError("Database session is required.")
        if panchayat_id is None:
            raise ValueError("Panchayat ID is required.")

        events = session.query(NotificationEvent).filter(
            NotificationEvent.panchayat_id == panchayat_id,
            NotificationEvent.status.in_(["SENT", "PARTIALLY_DELIVERED", "COMPLETED_NO_TARGETS"]),
        ).order_by(NotificationEvent.published_at.desc()).limit(limit).all()

        return [
            FarmerNotificationItem(
                event_id=e.id,
                advisory_id=e.advisory_id,
                advisory_version=e.advisory_version,
                panchayat_id=e.panchayat_id,
                alert_category=e.alert_category,
                severity=e.severity,
                title=e.title,
                message=e.message,
                published_at=e.published_at.isoformat() if e.published_at else "",
                deep_link=f"gramsevak://panchayat/{e.panchayat_id}/advisory/{e.advisory_id}",
            )
            for e in events
        ]


def get_notification_service() -> NotificationService:
    """FastAPI dependency provider for NotificationService."""
    return NotificationService()
