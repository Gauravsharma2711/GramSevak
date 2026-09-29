"""
API v1 Notification & Location Alerts Endpoints (Phase 6.2).

Provides farmer device token registration, approved advisory alert processing,
idempotent retries, and Panchayat-scoped alert retrieval.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.notification import (
    DeviceTokenRegistrationRequest,
    DeviceTokenRegistrationResponse,
    ProcessAdvisoryNotificationResponse,
    RetryNotificationResponse,
    FarmerNotificationListResponse,
)
from backend.services.notification_service import (
    NotificationService,
    get_notification_service,
    NotificationServiceError,
    IneligibleAdvisoryError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/farmer/device-token",
    response_model=DeviceTokenRegistrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Register Farmer Device Push Notification Token",
    description="""
    Registers or updates a farmer device push notification token linked strictly to
    an authoritative Gram Panchayat ID.

    Privacy & Architecture Invariants:
    - Never persists raw GPS coordinates.
    - Token is associated solely with authoritative Panchayat administrative ID.
    - Idempotent: repeated calls with the same token update the target Panchayat.
    """,
    tags=["Farmer Notifications"],
)
def register_farmer_device(
    payload: DeviceTokenRegistrationRequest,
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> DeviceTokenRegistrationResponse:
    try:
        device = service.register_device(
            db=db,
            device_token=payload.device_token,
            panchayat_id=payload.panchayat_id,
            platform=payload.platform or "android",
        )
        return DeviceTokenRegistrationResponse(
            success=True,
            status="registered",
            message="Device token registered successfully for Panchayat location alerts.",
            panchayat_id=device.panchayat_id,
            device_token=device.device_token,
            is_active=device.is_active,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error registering farmer device token: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device token.",
        )


@router.post(
    "/notifications/process-advisory/{advisory_id}",
    response_model=ProcessAdvisoryNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Approved Advisory for Location Alert Delivery",
    description="""
    Evaluates an advisory against strict publication boundaries and alert eligibility rules:
    - Must be `APPROVED` or `PUBLISHED`.
    - Must have passed safety validation (`VALIDATED`).
    - Must not be a draft, rejected, or superseded version.
    - Idempotently dispatches alerts to registered devices in the Panchayat.
    """,
    tags=["Farmer Notifications"],
)
def process_advisory_notifications(
    advisory_id: int = Path(..., ge=1, description="Unique Advisory ID to evaluate"),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> ProcessAdvisoryNotificationResponse:
    try:
        return service.process_advisory_alerts(db=db, advisory_id=advisory_id)
    except NotificationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error processing advisory notifications: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process advisory notifications.",
        )


@router.post(
    "/notifications/retry/{event_id}",
    response_model=RetryNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry Failed Deliveries for an Alert Event",
    description="""
    Safely retries failed notification deliveries for a previously generated event.
    Idempotent: will not create duplicate delivery records for devices that already succeeded.
    """,
    tags=["Farmer Notifications"],
)
def retry_notification(
    event_id: int = Path(..., ge=1, description="Unique Notification Event ID"),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> RetryNotificationResponse:
    try:
        return service.retry_notification_event(db=db, event_id=event_id)
    except NotificationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error retrying notification deliveries: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry notification deliveries.",
        )


@router.get(
    "/farmer/notifications",
    response_model=FarmerNotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Location Alerts for Active Panchayat",
    description="""
    Retrieves recent published location alerts for a Gram Panchayat.
    Allows farmers to view historical or unread alerts in their app.
    """,
    tags=["Farmer Notifications"],
)
def get_panchayat_alerts(
    panchayat_id: int = Query(..., ge=1, description="Active Gram Panchayat ID"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of alerts to return"),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> FarmerNotificationListResponse:
    try:
        items = service.list_panchayat_alerts(db=db, panchayat_id=panchayat_id, limit=limit)
        return FarmerNotificationListResponse(
            panchayat_id=panchayat_id,
            total=len(items),
            items=items,
        )
    except Exception as exc:
        logger.error(f"Error retrieving alerts for panchayat {panchayat_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve panchayat alerts.",
        )
