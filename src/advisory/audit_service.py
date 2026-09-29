"""
Phase 5.6 Officer Review, Concurrency, Safety Validation, and Audit Logging Service.

Provides core business logic for:
1. Immutable advisory audit logging (action, actor, statuses, diff details, version, timestamp).
2. Optimistic concurrency control and conflict prevention.
3. Content validation for officer edits (safety boundaries, dosage bans, forecast grounding).
4. RBAC and district/Panchayat spatial authorization guards.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.advisory import Advisory, AdvisoryAuditLog
from backend.app.models.panchayat import Panchayat
from backend.app.models.district import District
from src.advisory.safety_validator import (
    BANNED_DOSAGE_PATTERNS,
    BANNED_MEDICAL_AND_EMERGENCY_WORDS,
    BANNED_UNSUPPORTED_DISASTERS,
    UNSUPPORTED_CERTAINTY_PATTERNS,
    UNSUPPORTED_DISEASE_DIAGNOSIS_PATTERNS,
    DANGEROUS_PHYSICAL_PATTERNS,
)

logger = logging.getLogger(__name__)


def record_advisory_audit_log(
    db: Session,
    advisory_id: int,
    action: str,
    officer_id: Optional[str],
    previous_status: Optional[str],
    new_status: Optional[str],
    version: int,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AdvisoryAuditLog:
    """
    Creates and records an immutable audit log entry in advisory_audit_logs.
    """
    audit_entry = AdvisoryAuditLog(
        advisory_id=advisory_id,
        action=action.upper(),
        officer_id=officer_id.strip() if officer_id else "SYSTEM",
        previous_status=previous_status,
        new_status=new_status,
        version=version,
        reason=reason.strip() if reason else None,
        details=details or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit_entry)
    db.flush()
    logger.info(
        f"[AUDIT_LOG_RECORDED] advisory_id={advisory_id} action={action} "
        f"actor={officer_id} prev={previous_status} new={new_status} version={version}"
    )
    return audit_entry


def validate_officer_authorization(
    db: Session,
    panchayat_id: int,
    officer_role: Optional[str] = None,
    officer_district_scope: Optional[str] = None,
) -> None:
    """
    Verifies that the caller has officer privileges and spatial jurisdiction over the target Panchayat.
    
    Prevents:
    - Farmer role or unauthorized roles approving/editing advisories (403 Forbidden).
    - Officers acting outside their assigned district jurisdiction (403 Forbidden).
    """
    clean_role = (officer_role or "").strip().upper()
    if clean_role in ("FARMER", "ANONYMOUS", "UNAUTHORIZED", "PUBLIC"):
        logger.warning(f"[AUTH_VIOLATION_ROLE] Blocked unauthorized role '{clean_role}' from officer review.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Role '{clean_role}' is not authorized to review or approve agricultural advisories.",
        )

    # If district scope is enforced, check spatial containment
    if officer_district_scope:
        clean_scope = officer_district_scope.strip().lower()
        panchayat = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
        if panchayat and panchayat.district_id:
            district = db.query(District).filter(District.id == panchayat.district_id).first()
            if district and district.name.strip().lower() != clean_scope:
                logger.warning(
                    f"[AUTH_VIOLATION_SCOPE] Officer scope '{officer_district_scope}' "
                    f"does not match Panchayat {panchayat_id} district '{district.name}'."
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Access denied: Officer district jurisdiction '{officer_district_scope}' "
                        f"does not cover Gram Panchayat in district '{district.name}'."
                    ),
                )


def validate_officer_edit_safety(
    title: str,
    text: str,
    rainfall_mm: Optional[float] = None,
) -> Tuple[bool, List[str]]:
    """
    Applies Phase 5.5 safety checks to extension officer edits:
    - Banned chemical dosage and mixing recipes.
    - Medical and emergency panic claims.
    - Unsupported disaster hallucinations.
    - Unsupported certainty claims.
    - Unsupported disease diagnoses without diagnostic backing.
    - Dangerous physical instructions.
    - Numerical forecast contradictions (e.g. contradicting authoritative rainfall mm).
    """
    violations: List[str] = []
    combined_text = f"{title} {text}"
    lower_text = combined_text.lower()

    # 1. Chemical Dosages
    for pattern in BANNED_DOSAGE_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            violations.append(
                f"Chemical safety violation: Prohibited dosage or chemical recipe pattern '{match.group(0)}'. "
                f"Advisories must provide agronomic management principles, not uncalibrated chemical recipes."
            )

    # 2. Medical & Emergency Panic
    for banned in BANNED_MEDICAL_AND_EMERGENCY_WORDS:
        if banned in lower_text:
            violations.append(f"Medical/Emergency violation: Text contains prohibited phrasing '{banned}'.")

    # 3. Unsupported Disasters
    for disaster in BANNED_UNSUPPORTED_DISASTERS:
        if disaster in lower_text:
            violations.append(f"Unsupported disaster claim: Text contains '{disaster}'.")

    # 4. Unsupported Certainty
    for pattern in UNSUPPORTED_CERTAINTY_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            violations.append(f"Unsupported certainty violation: Text claims '{match.group(0)}'.")

    # 5. Unsupported Disease Diagnosis
    for pattern in UNSUPPORTED_DISEASE_DIAGNOSIS_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            violations.append(f"Unsupported disease diagnosis: Text contains '{match.group(0)}'.")

    # 6. Dangerous Physical Instructions
    for pattern in DANGEROUS_PHYSICAL_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            violations.append(f"Hazardous physical instruction: Text contains '{match.group(0)}'.")

    # 7. Numerical Forecast Grounding: If text mentions explicit rainfall mm values
    if rainfall_mm is not None:
        rainfall_mentions = re.findall(r"(\d+(?:\.\d+)?)\s*mm\b", combined_text, re.IGNORECASE)
        for mention in rainfall_mentions:
            try:
                val = float(mention)
                if abs(val - float(rainfall_mm)) > 0.5:
                    violations.append(
                        f"Numerical forecast contradiction: Text mentions '{val} mm', but authoritative "
                        f"downscaled forecast is '{rainfall_mm} mm'. Officer edits cannot modify underlying weather numbers."
                    )
            except ValueError:
                pass

    return len(violations) == 0, violations
