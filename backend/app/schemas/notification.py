"""
Pydantic schemas for Phase 6.2 Panchayat Location Alerts and Notifications.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class DeviceTokenRegistrationRequest(BaseModel):
    """Payload for registering a farmer client push notification token."""
    device_token: str = Field(
        ...,
        min_length=10,
        max_length=512,
        description="FCM or push notification device registration token",
        examples=["fcm_token_sample_abc1234567890"],
    )
    panchayat_id: int = Field(
        ...,
        ge=1,
        description="Unique Gram Panchayat ID to which alerts should be scoped",
        examples=[1001],
    )
    platform: Optional[str] = Field(
        "android",
        description="Client device operating platform ('android', 'ios', 'web')",
        examples=["android"],
    )


class DeviceTokenRegistrationResponse(BaseModel):
    """Response confirming device token registration."""
    success: bool = True
    status: str = "registered"
    message: str
    panchayat_id: int
    device_token: Optional[str] = None
    is_active: bool = True


class ProcessAdvisoryNotificationResponse(BaseModel):
    """Response returned when evaluating and dispatching an advisory alert."""
    advisory_id: int
    advisory_version: int
    panchayat_id: int
    eligible: bool
    ineligibility_reason: Optional[str] = None
    event_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    target_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    status: str
    status_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.eligible

    @property
    def eligible_devices_count(self) -> int:
        return self.target_count

    @property
    def successful_deliveries_count(self) -> int:
        return self.success_count

    @property
    def failed_deliveries_count(self) -> int:
        return self.failure_count


class RetryNotificationResponse(BaseModel):
    """Response returned when retrying a notification event."""
    event_id: int
    idempotency_key: str
    status: str
    retried_count: int
    success_count: int
    failure_count: int = 0

    @property
    def success(self) -> bool:
        return True

    @property
    def successful_deliveries_count(self) -> int:
        return self.success_count

    @property
    def failed_deliveries_count(self) -> int:
        return self.failure_count


class FarmerNotificationItem(BaseModel):
    """Farmer-safe notification contract without technical debug internals."""
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    advisory_id: int
    advisory_version: int
    panchayat_id: int
    alert_category: str
    severity: str
    title: str
    message: str
    published_at: str
    deep_link: Optional[str] = None


class FarmerNotificationListResponse(BaseModel):
    """List of location alerts for the active Gram Panchayat."""
    panchayat_id: int
    total: int
    items: List[FarmerNotificationItem]
