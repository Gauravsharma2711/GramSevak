"""
Phase 5 Advisory Lifecycle State Machine & Transition Rules.

Enforces safe, strictly regulated lifecycle status transitions across the
Phase 5 advisory workflow:
  DRAFT -> GENERATED -> VALIDATED -> NEEDS_REVIEW -> APPROVED -> PUBLISHED
  (with safe failure and rejection branches)

Safety Invariants:
1. No AI output can ever bypass safety validation.
2. No advisory can ever reach farmers (PUBLISHED) without explicit extension officer approval.
3. Once REJECTED, an advisory cannot be resurrected without generating a new draft revision.
4. Transitions must record the acting entity (SYSTEM_AI, SAFETY_VALIDATOR, OFFICER, PUBLICATION_SERVICE).
"""

from typing import Dict, Set, Tuple
from backend.app.schemas.advisory_contracts import AdvisoryStatus


class InvalidAdvisoryStatusTransitionError(ValueError):
    """Raised when an illegal or unsafe advisory status transition is attempted."""
    pass


class MissingRequiredTransitionDataError(ValueError):
    """Raised when data required for a specific status is missing."""
    pass


# Map of allowed source status -> set of allowed target statuses
ALLOWED_TRANSITIONS: Dict[AdvisoryStatus, Set[AdvisoryStatus]] = {
    AdvisoryStatus.DRAFT: {
        AdvisoryStatus.GENERATED,       # AI generation completed
        AdvisoryStatus.NEEDS_REVIEW,    # Deterministic rule path skips AI directly to review
    },
    AdvisoryStatus.GENERATED: {
        AdvisoryStatus.VALIDATED,          # Passed automated safety validation
        AdvisoryStatus.FAILED_VALIDATION,  # Failed automated safety validation
    },
    AdvisoryStatus.VALIDATED: {
        AdvisoryStatus.NEEDS_REVIEW,    # Queued for extension officer inspection
    },
    AdvisoryStatus.FAILED_VALIDATION: {
        AdvisoryStatus.NEEDS_REVIEW,    # Fallback to deterministic rule content queued for review
        AdvisoryStatus.REJECTED,        # Discarded entirely
    },
    AdvisoryStatus.NEEDS_REVIEW: {
        AdvisoryStatus.APPROVED,        # Officer approved
        AdvisoryStatus.REJECTED,        # Officer rejected
    },
    AdvisoryStatus.APPROVED: {
        AdvisoryStatus.PUBLISHED,       # Released to farmer delivery endpoints
    },
    AdvisoryStatus.PUBLISHED: set(),    # Terminal state; immutable
    AdvisoryStatus.REJECTED: set(),     # Terminal state; immutable (requires new draft)
}

# Explicit list of actors authorized for specific transitions
AUTHORIZED_TRANSITIONS: Set[Tuple[AdvisoryStatus, AdvisoryStatus, str]] = {
    (AdvisoryStatus.DRAFT, AdvisoryStatus.GENERATED, "AI_SERVICE"),
    (AdvisoryStatus.DRAFT, AdvisoryStatus.NEEDS_REVIEW, "RULE_ENGINE"),
    (AdvisoryStatus.GENERATED, AdvisoryStatus.VALIDATED, "SAFETY_VALIDATOR"),
    (AdvisoryStatus.GENERATED, AdvisoryStatus.FAILED_VALIDATION, "SAFETY_VALIDATOR"),
    (AdvisoryStatus.VALIDATED, AdvisoryStatus.NEEDS_REVIEW, "PIPELINE_ORCHESTRATOR"),
    (AdvisoryStatus.FAILED_VALIDATION, AdvisoryStatus.NEEDS_REVIEW, "FALLBACK_SERVICE"),
    (AdvisoryStatus.FAILED_VALIDATION, AdvisoryStatus.REJECTED, "PIPELINE_ORCHESTRATOR"),
    (AdvisoryStatus.NEEDS_REVIEW, AdvisoryStatus.APPROVED, "EXTENSION_OFFICER"),
    (AdvisoryStatus.NEEDS_REVIEW, AdvisoryStatus.REJECTED, "EXTENSION_OFFICER"),
    (AdvisoryStatus.APPROVED, AdvisoryStatus.PUBLISHED, "PUBLICATION_SERVICE"),
}


def validate_status_transition(
    current_status: AdvisoryStatus,
    target_status: AdvisoryStatus,
    actor: str = "SYSTEM",
) -> bool:
    """
    Validates whether an advisory status transition is permitted.
    
    Raises:
        InvalidAdvisoryStatusTransitionError: If the transition violates safety invariants.
    """
    if current_status == target_status:
        return True  # Idempotent no-op

    allowed_targets = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        raise InvalidAdvisoryStatusTransitionError(
            f"Illegal advisory status transition from '{current_status.value}' to '{target_status.value}'. "
            f"Allowed target states from '{current_status.value}': {[s.value for s in allowed_targets]}."
        )

    # Validate specific actor authorization if known actor provided
    if actor != "SYSTEM" and (current_status, target_status, actor) not in AUTHORIZED_TRANSITIONS:
        raise InvalidAdvisoryStatusTransitionError(
            f"Actor '{actor}' is not authorized to transition advisory from "
            f"'{current_status.value}' to '{target_status.value}'."
        )

    return True


def check_transition_data_requirements(
    target_status: AdvisoryStatus,
    has_draft_content: bool = False,
    is_safety_valid: bool = False,
    has_officer_id: bool = False,
) -> None:
    """
    Verifies that the prerequisite data exists before entering target state.
    """
    if target_status == AdvisoryStatus.GENERATED and not has_draft_content:
        raise MissingRequiredTransitionDataError(
            "Cannot transition to GENERATED without non-empty draft content."
        )
    if target_status == AdvisoryStatus.VALIDATED and not is_safety_valid:
        raise MissingRequiredTransitionDataError(
            "Cannot transition to VALIDATED without an approved safety validation report."
        )
    if target_status == AdvisoryStatus.APPROVED and not has_officer_id:
        raise MissingRequiredTransitionDataError(
            "Cannot transition to APPROVED without a valid officer identifier."
        )
