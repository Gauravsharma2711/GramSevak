"""
Calling Provider Abstraction for GramSevak (Phase 6.4).

Provides a provider-neutral telephony interface for optional automated advisory delivery.
Keeps telephony credentials isolated strictly on the backend, away from mobile clients.
Enforces idempotency, number validation, auditability, and graceful failure handling.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class CallingResult:
    """Outcome of an advisory voice call attempt."""
    success: bool
    phone_number: str
    advisory_id: int
    call_id: Optional[str] = None
    status: str = "INITIATED"  # INITIATED, COMPLETED, FAILED, BUSY, NO_ANSWER
    error_message: Optional[str] = None
    provider_name: str = "development_mock"
    dispatched_at: Optional[str] = None


class BaseCallingProvider(ABC):
    """Abstract interface for telephony/calling providers."""

    @abstractmethod
    def create_call(
        self,
        phone_number: str,
        speech_text: str,
        language: str,
        advisory_id: int,
    ) -> CallingResult:
        """Initiates an outbound voice call delivering approved advisory content."""
        pass

    @abstractmethod
    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Retrieves delivery status of a previously initiated call."""
        pass


class DevelopmentCallingProvider(BaseCallingProvider):
    """
    Safe in-memory / simulated telephony provider for development and testing.
    Validates E.164 and 10-digit Indian phone numbers without calling real networks.
    Stores audit records in-memory without persisting raw audio files.
    """

    PHONE_REGEX = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")

    def __init__(
        self,
        simulate_failure_numbers: Optional[List[str]] = None,
        simulate_busy_numbers: Optional[List[str]] = None,
    ):
        self.simulate_failure_numbers = simulate_failure_numbers or ["+919000000000"]
        self.simulate_busy_numbers = simulate_busy_numbers or []
        self.dispatched_calls: List[CallingResult] = []

    def normalize_phone_number(self, phone: str) -> str:
        """Normalizes Indian phone numbers into standard +91XXXXXXXXXX format."""
        cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
        if cleaned.startswith("+91"):
            return cleaned
        if cleaned.startswith("91") and len(cleaned) == 12:
            return f"+{cleaned}"
        if len(cleaned) == 10 and cleaned[0] in "6789":
            return f"+91{cleaned}"
        return cleaned

    def validate_phone_number(self, phone: str) -> bool:
        """Validates that the phone number matches Indian mobile format."""
        normalized = self.normalize_phone_number(phone)
        return bool(self.PHONE_REGEX.match(normalized))

    def create_call(
        self,
        phone_number: str,
        speech_text: str,
        language: str,
        advisory_id: int,
    ) -> CallingResult:
        normalized = self.normalize_phone_number(phone_number)
        now_iso = datetime.now(timezone.utc).isoformat()

        if not self.validate_phone_number(normalized):
            logger.warning(f"[CALLING_INVALID_PHONE] phone={phone_number} normalized={normalized}")
            return CallingResult(
                success=False,
                phone_number=phone_number,
                advisory_id=advisory_id,
                status="FAILED",
                error_message=f"Invalid phone number format: '{phone_number}'. Must be a valid 10-digit mobile number.",
                provider_name="development_mock",
                dispatched_at=now_iso,
            )

        if normalized in self.simulate_failure_numbers or "fail" in phone_number.lower():
            logger.warning(f"[CALLING_SIMULATED_FAILURE] phone={normalized}")
            return CallingResult(
                success=False,
                phone_number=normalized,
                advisory_id=advisory_id,
                status="FAILED",
                error_message="Downstream telephony provider gateway timeout or rejection.",
                provider_name="development_mock",
                dispatched_at=now_iso,
            )

        if normalized in self.simulate_busy_numbers:
            logger.info(f"[CALLING_SIMULATED_BUSY] phone={normalized}")
            return CallingResult(
                success=False,
                phone_number=normalized,
                advisory_id=advisory_id,
                status="BUSY",
                error_message="Recipient line was busy.",
                provider_name="development_mock",
                dispatched_at=now_iso,
            )

        call_id = f"mock-call-{advisory_id}-{len(self.dispatched_calls) + 1:04d}"
        result = CallingResult(
            success=True,
            phone_number=normalized,
            advisory_id=advisory_id,
            call_id=call_id,
            status="INITIATED",
            provider_name="development_mock",
            dispatched_at=now_iso,
        )
        self.dispatched_calls.append(result)
        logger.info(
            f"[CALLING_INITIATED_MOCK] call_id={call_id} phone={normalized} advisory_id={advisory_id} "
            f"lang={language} speech_len={len(speech_text)}"
        )
        return result

    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        for c in self.dispatched_calls:
            if c.call_id == call_id:
                return {
                    "call_id": c.call_id,
                    "phone_number": c.phone_number,
                    "status": c.status,
                    "success": c.success,
                    "dispatched_at": c.dispatched_at,
                }
        return {"call_id": call_id, "status": "UNKNOWN", "success": False}
