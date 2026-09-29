"""
Notification Provider Abstraction for GramSevak (Phase 6.2).

Decouples notification dispatch from specific push providers (Firebase Cloud Messaging / Mock).
Provides clean error handling, invalid/expired token detection, and auditability.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Outcome of an individual device push notification attempt."""
    success: bool
    device_token: str
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    invalid_token: bool = False


class BaseNotificationProvider(ABC):
    """Abstract interface for push notification delivery providers."""

    @abstractmethod
    def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> DeliveryResult:
        """Sends a push notification to a single device token."""
        pass

    def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> List[DeliveryResult]:
        """Sends a push notification to multiple device tokens."""
        return [self.send_notification(tok, title, body, data) for tok in device_tokens]


class DevelopmentNotificationProvider(BaseNotificationProvider):
    """
    Safe in-memory / logging notification provider for development and testing.
    Active by default when external FCM credentials are not configured.
    """

    def __init__(self, simulate_failure_tokens: Optional[List[str]] = None, simulate_invalid_tokens: Optional[List[str]] = None):
        self.simulate_failure_tokens = simulate_failure_tokens or []
        self.simulate_invalid_tokens = simulate_invalid_tokens or []
        self.sent_notifications: List[Dict[str, Any]] = []

    def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> DeliveryResult:
        if device_token in self.simulate_invalid_tokens or "invalid" in device_token.lower():
            logger.warning(f"[NOTIFICATION_MOCK_INVALID_TOKEN] token={device_token[:12]}...")
            return DeliveryResult(
                success=False,
                device_token=device_token,
                error_message="Invalid or unregistered device token.",
                invalid_token=True,
            )

        if device_token in self.simulate_failure_tokens:
            logger.warning(f"[NOTIFICATION_MOCK_FAILURE] token={device_token[:12]}...")
            return DeliveryResult(
                success=False,
                device_token=device_token,
                error_message="Simulated downstream provider network timeout.",
                invalid_token=False,
            )

        msg_id = f"mock-msg-{len(self.sent_notifications) + 1}"
        record = {
            "message_id": msg_id,
            "device_token": device_token,
            "title": title,
            "body": body,
            "data": data or {},
        }
        self.sent_notifications.append(record)
        logger.info(f"[NOTIFICATION_DISPATCHED_MOCK] msg_id={msg_id} token={device_token[:12]}... title='{title}'")
        return DeliveryResult(
            success=True,
            device_token=device_token,
            message_id=msg_id,
        )

    def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> List[DeliveryResult]:
        return [self.send_notification(tok, title, body, data) for tok in device_tokens]


class FCMNotificationProvider(BaseNotificationProvider):
    """
    Firebase Cloud Messaging (FCM) production provider.
    Initializes safely if firebase_admin is installed and configured.
    """

    def __init__(self, app=None):
        self._app = app
        self._initialized = False
        try:
            import firebase_admin
            from firebase_admin import messaging
            self._messaging = messaging
            self._initialized = True
            logger.info("FCMNotificationProvider initialized successfully.")
        except ImportError:
            logger.warning("firebase_admin is not installed; falling back to simulated provider.")
            self._initialized = False

    def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> DeliveryResult:
        if not self._initialized:
            return DeliveryResult(
                success=False,
                device_token=device_token,
                error_message="FCM SDK not initialized. Ensure firebase-admin is configured.",
            )

        try:
            message = self._messaging.Message(
                notification=self._messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=device_token,
            )
            response = self._messaging.send(message)
            return DeliveryResult(
                success=True,
                device_token=device_token,
                message_id=str(response),
            )
        except Exception as exc:
            err_str = str(exc)
            is_unregistered = "registration-token-not-registered" in err_str.lower() or "not registered" in err_str.lower()
            logger.error(f"FCM delivery error: {err_str}", exc_info=True)
            return DeliveryResult(
                success=False,
                device_token=device_token,
                error_message=err_str,
                invalid_token=is_unregistered,
            )

    def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> List[DeliveryResult]:
        return [self.send_notification(tok, title, body, data) for tok in device_tokens]


# Default singleton provider instance (pluggable/mockable)
_global_provider: BaseNotificationProvider = DevelopmentNotificationProvider()


def get_notification_provider() -> BaseNotificationProvider:
    """Dependency provider returning the active notification provider."""
    return _global_provider


def set_notification_provider(provider: BaseNotificationProvider) -> None:
    """Configures the global notification provider (useful for testing and configuration)."""
    global _global_provider
    _global_provider = provider
