"""
Calling Service Implementation for GramSevak (Phase 6.4).

Orchestrates outbound advisory voice calling with strict safety invariant enforcement:
1. ONLY approved/published advisories (`status in ('APPROVED', 'PUBLISHED')`) may be spoken/delivered.
2. Validates Indian phone number format (+91 or 10-digit mobile).
3. Idempotency: prevents duplicate simultaneous or rapid calls to the same recipient for the same advisory.
4. Generates speech-clean text preserving exact agronomic values, rainfall mm, timing, and severity.
5. Injects provider abstraction (`BaseCallingProvider`), isolating credentials from mobile clients.
"""

import time
import logging
from typing import Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session

from backend.app.models.advisory import Advisory
from backend.services.calling_provider import (
    BaseCallingProvider,
    DevelopmentCallingProvider,
    CallingResult,
)

logger = logging.getLogger(__name__)


class CallingServiceError(Exception):
    """Base exception for calling service operations."""
    pass


class IneligibleAdvisoryCallError(CallingServiceError):
    """Raised when an advisory is not in an approved/published state."""
    pass


class InvalidPhoneNumberError(CallingServiceError):
    """Raised when a recipient phone number is malformed or invalid."""
    pass


class DuplicateCallError(CallingServiceError):
    """Raised when a duplicate call attempt is made within the cooldown window."""
    pass


class CallingService:
    """
    Service managing authorized advisory voice call delivery.
    """

    # 15-minute cooldown to prevent spamming farmers with duplicate automated calls
    DUPLICATE_COOLDOWN_SECONDS = 900

    def __init__(self, provider: Optional[BaseCallingProvider] = None):
        self.provider = provider or DevelopmentCallingProvider()
        # In-memory recent calls cache: (advisory_id, normalized_phone) -> timestamp
        self._recent_dispatches: Dict[Tuple[int, str], float] = {}

    def _normalize_phone(self, phone: str) -> str:
        if isinstance(self.provider, DevelopmentCallingProvider):
            return self.provider.normalize_phone_number(phone)
        import re
        cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
        if cleaned.startswith("+91"):
            return cleaned
        if len(cleaned) == 10 and cleaned[0] in "6789":
            return f"+91{cleaned}"
        return cleaned

    def _is_valid_phone(self, phone: str) -> bool:
        if isinstance(self.provider, DevelopmentCallingProvider):
            return self.provider.validate_phone_number(phone)
        import re
        return bool(re.match(r"^(\+91[\-\s]?)?[6-9]\d{9}$", phone.strip()))

    def prepare_advisory_speech(self, advisory: Advisory, language: str = "en") -> str:
        """
        Extracts and formats verified advisory content into clear spoken text.
        Preserves exact numbers, units, warnings, and recommendations without regeneration.
        """
        title = advisory.advisory_title or "Agricultural Advisory"
        rainfall_desc = f"{float(advisory.rainfall_mm or 0.0):.1f} millimeters"
        category = advisory.rainfall_category or "Forecasted rainfall"
        severity = advisory.severity or "MODERATE"

        # Check for structured approved content
        content = advisory.approved_content or {}
        if isinstance(content, dict):
            # Check for localized content if language requested
            lang_content = content.get(language) or content
            what = lang_content.get("what_is_happening") or advisory.advisory_text or ""
            why = lang_content.get("why_it_matters") or ""
            actions = lang_content.get("recommended_actions") or []
            timing = lang_content.get("timing") or ""
            warnings = lang_content.get("warnings") or []
        else:
            what = advisory.advisory_text or ""
            why = ""
            actions = []
            timing = ""
            warnings = []

        parts = [
            f"GramSevak agro-advisory for {advisory.forecast_date}.",
            f"Rainfall forecast: {rainfall_desc}, {category}. Severity: {severity}.",
            f"{title}.",
        ]
        if what:
            parts.append(f"What is happening: {what}.")
        if why:
            parts.append(f"Why it matters: {why}.")
        if actions and isinstance(actions, list):
            parts.append("Recommended actions: " + " ".join([f"Action {i+1}: {act}." for i, act in enumerate(actions)]))
        if timing:
            parts.append(f"Timing outlook: {timing}.")
        if warnings and isinstance(warnings, list):
            parts.append("Important warnings: " + " ".join([f"Warning: {w}." for w in warnings]))

        return " ".join(parts)

    def dispatch_advisory_call(
        self,
        db: Session,
        advisory_id: int,
        phone_number: str,
        language: str = "en",
        farmer_id: Optional[str] = None,
    ) -> CallingResult:
        """
        Dispatches an advisory voice call with all safety checks.
        """
        # 1. Phone number validation
        if not phone_number or not self._is_valid_phone(phone_number):
            raise InvalidPhoneNumberError(
                f"Invalid recipient phone number: '{phone_number}'. Must be a valid 10-digit mobile number."
            )

        normalized_phone = self._normalize_phone(phone_number)

        # 2. Advisory verification & authorization boundaries
        advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
        if not advisory:
            raise IneligibleAdvisoryCallError(f"Advisory with ID {advisory_id} does not exist.")

        status_str = (advisory.status or "").upper()
        if status_str not in ("APPROVED", "PUBLISHED"):
            logger.warning(
                f"[CALLING_REJECTED_UNAPPROVED] advisory_id={advisory_id} status={status_str} "
                f"phone={normalized_phone}"
            )
            raise IneligibleAdvisoryCallError(
                f"Cannot deliver unapproved advisory (status='{status_str}'). "
                f"Only APPROVED or PUBLISHED advisories may be delivered via voice calling."
            )

        # 3. Idempotency & duplicate call prevention
        now = time.time()
        key = (advisory_id, normalized_phone)
        last_dispatched = self._recent_dispatches.get(key)
        if last_dispatched and (now - last_dispatched) < self.DUPLICATE_COOLDOWN_SECONDS:
            logger.warning(f"[CALLING_DUPLICATE_BLOCKED] key={key} elapsed={now - last_dispatched:.1f}s")
            raise DuplicateCallError(
                f"A voice call for advisory {advisory_id} was already initiated to {normalized_phone} "
                f"within the cooldown window ({int(self.DUPLICATE_COOLDOWN_SECONDS / 60)} minutes)."
            )

        # 4. Speech preparation
        speech_text = self.prepare_advisory_speech(advisory, language=language)

        # 5. Dispatch via provider
        logger.info(
            f"[CALLING_DISPATCH] advisory_id={advisory_id} phone={normalized_phone} "
            f"lang={language} farmer_id={farmer_id}"
        )
        result = self.provider.create_call(
            phone_number=normalized_phone,
            speech_text=speech_text,
            language=language,
            advisory_id=advisory_id,
        )

        if result.success:
            self._recent_dispatches[key] = now

        return result


# Global singleton provider instance for FastAPI dependency injection
_global_calling_provider: Optional[BaseCallingProvider] = None


def get_calling_service() -> CallingService:
    global _global_calling_provider
    if _global_calling_provider is None:
        _global_calling_provider = DevelopmentCallingProvider()
    return CallingService(provider=_global_calling_provider)
