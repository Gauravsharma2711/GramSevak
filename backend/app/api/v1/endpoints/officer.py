"""
API v1 Extension Officer Advisory Endpoints.

Provides endpoints for agricultural extension officers to review, inspect, edit,
approve, and reject agricultural advisories before they are served to farmers,
with optimistic concurrency locking and immutable audit logging.
"""

from datetime import date, datetime, timezone
import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.advisory import Advisory, AdvisoryAuditLog
from backend.app.schemas.advisory import (
    AdvisoryResponse,
    OfficerApproveRequest,
    OfficerRejectRequest,
    OfficerEditRequest,
    AdvisoryAuditLogResponse,
)
from src.advisory.audit_service import (
    record_advisory_audit_log,
    validate_officer_authorization,
    validate_officer_edit_safety,
)

logger = logging.getLogger(__name__)

router = APIRouter()

REVIEWABLE_STATUSES = {"DRAFT", "NEEDS_REVIEW", "EDITED"}


@router.get(
    "/officer/advisories",
    response_model=List[AdvisoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Advisories for Extension Officer Review",
    description="""
    Retrieve a paginated list of agricultural advisories with optional filtering by review status,
    Panchayat ID, and forecast date.

    Review Statuses:
    - `DRAFT` / `NEEDS_REVIEW`: Generated advisories awaiting officer inspection.
    - `EDITED`: Revised advisories undergoing review.
    - `APPROVED`: Validated advisories available to farmer-facing endpoints.
    - `REJECTED`: Discarded or invalid drafts.
    """,
)
def list_officer_advisories(
    review_status: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by workflow status (DRAFT, NEEDS_REVIEW, APPROVED, REJECTED, EDITED)",
        examples=["DRAFT"],
    ),
    panchayat_id: Optional[int] = Query(
        None,
        ge=1,
        description="Filter by specific Gram Panchayat ID",
        examples=[1001],
    ),
    forecast_date: Optional[date] = Query(
        None,
        description="Filter by forecast validity date (YYYY-MM-DD)",
        examples=["2026-09-08"],
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Number of records to return per page (max 100)",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP GET handler to list agricultural advisories with filtering and pagination.
    """
    if x_officer_role and x_officer_role.strip().upper() in ("FARMER", "ANONYMOUS", "UNAUTHORIZED"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Role '{x_officer_role}' is not authorized to access officer review queues.",
        )

    query = db.query(Advisory)

    if review_status:
        query = query.filter(Advisory.status == review_status.upper())

    if panchayat_id:
        query = query.filter(Advisory.panchayat_id == panchayat_id)

    if forecast_date:
        query = query.filter(Advisory.forecast_date == forecast_date)

    advisories = (
        query
        .order_by(
            Advisory.forecast_date.desc(),
            Advisory.created_at.desc(),
            Advisory.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    logger.info(
        f"[OFFICER_LIST_ADVISORIES] count={len(advisories)} status={review_status} "
        f"panchayat_id={panchayat_id} forecast_date={forecast_date}"
    )
    return advisories


@router.get(
    "/officer/advisories/{advisory_id}",
    response_model=AdvisoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Advisory Detail for Officer Review",
    description="""
    Retrieve full inspection details of an agricultural advisory by its unique ID.
    """,
)
def get_officer_advisory(
    advisory_id: int = Path(
        ...,
        ge=1,
        description="Unique identifier of the target advisory",
        examples=[1],
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP GET handler to retrieve detailed advisory record by ID.
    """
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        logger.warning(f"[OFFICER_ADVISORY_NOT_FOUND] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory with ID '{advisory_id}' not found.",
        )

    validate_officer_authorization(
        db=db,
        panchayat_id=advisory.panchayat_id,
        officer_role=x_officer_role,
        officer_district_scope=x_district_scope,
    )

    return advisory


@router.put(
    "/officer/advisories/{advisory_id}",
    response_model=AdvisoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit Agricultural Advisory Content",
    description="""
    Edit the textual recommendations and title of an agricultural advisory under review.

    Safety & Invariant Rules:
    - Numerical forecast values cannot be altered through advisory editing.
    - Edited text must satisfy Phase 5.5 safety checks (no chemical recipes, no panic phrasing, no forecast contradictions).
    - Preserves the original generated content in `original_content`.
    - Increments the optimistic concurrency `version` integer.
    - Transitions advisory status to `NEEDS_REVIEW` (or `EDITED`).
    - Records an immutable audit log entry.
    """,
)
def edit_advisory(
    payload: OfficerEditRequest,
    advisory_id: int = Path(
        ...,
        ge=1,
        description="Unique identifier of the advisory to edit",
        examples=[1],
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP PUT handler to edit advisory wording.
    """
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        logger.warning(f"[OFFICER_EDIT_NOT_FOUND] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory with ID '{advisory_id}' not found.",
        )

    # Authorization and spatial scope validation
    validate_officer_authorization(
        db=db,
        panchayat_id=advisory.panchayat_id,
        officer_role=x_officer_role,
        officer_district_scope=x_district_scope,
    )

    # Status check: only reviewable advisories can be edited
    if advisory.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advisory with ID '{advisory_id}' is already APPROVED. Approved advisories cannot be edited directly.",
        )
    if advisory.status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit advisory with ID '{advisory_id}' because it has been REJECTED. Create a new revision instead.",
        )
    if advisory.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit advisory with status '{advisory.status}'. Only pending review advisories can be edited.",
        )

    # Optimistic concurrency check
    if payload.version is not None and advisory.version != payload.version:
        logger.warning(
            f"[OFFICER_EDIT_VERSION_CONFLICT] advisory_id={advisory_id} "
            f"current_version={advisory.version} provided_version={payload.version}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Version conflict: Advisory has been modified by another officer. "
                f"Current version is {advisory.version}, but request specified {payload.version}. "
                f"Please refresh and review the latest content."
            ),
        )

    # Validate safety boundaries on edited text
    rf_mm = float(advisory.rainfall_mm) if advisory.rainfall_mm is not None else None
    is_safe, safety_violations = validate_officer_edit_safety(
        title=payload.advisory_title,
        text=payload.advisory_text,
        rainfall_mm=rf_mm,
    )
    if not is_safe:
        logger.warning(f"[OFFICER_EDIT_SAFETY_VIOLATION] advisory_id={advisory_id} violations={safety_violations}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Officer edit failed safety validation: {'; '.join(safety_violations)}",
        )

    # Preserve original content if not already saved
    if not advisory.original_content:
        advisory.original_content = {
            "advisory_title": advisory.advisory_title,
            "advisory_text": advisory.advisory_text,
            "severity": advisory.severity,
            "advisory_source": advisory.advisory_source,
            "rule_version": advisory.rule_version,
            "version": advisory.version,
        }

    # Record snapshot of this edit
    advisory.edited_content = {
        "advisory_title": payload.advisory_title.strip(),
        "advisory_text": payload.advisory_text.strip(),
        "severity": payload.severity.strip().upper() if payload.severity else advisory.severity,
        "officer_id": payload.officer_id.strip(),
        "officer_comment": payload.officer_comment.strip() if payload.officer_comment else None,
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "version": advisory.version + 1,
    }

    prev_status = advisory.status
    advisory.advisory_title = payload.advisory_title.strip()
    advisory.advisory_text = payload.advisory_text.strip()
    if payload.severity:
        advisory.severity = payload.severity.strip().upper()
    advisory.officer_id = payload.officer_id.strip()
    advisory.officer_comment = payload.officer_comment.strip() if payload.officer_comment else None
    advisory.advisory_source = "OFFICER_AMENDED"
    advisory.status = "NEEDS_REVIEW"
    advisory.version += 1
    advisory.updated_at = datetime.now(timezone.utc)

    # Record audit log
    record_advisory_audit_log(
        db=db,
        advisory_id=advisory.id,
        action="EDITED",
        officer_id=payload.officer_id,
        previous_status=prev_status,
        new_status=advisory.status,
        version=advisory.version,
        reason=payload.officer_comment,
        details={
            "edited_title": advisory.advisory_title,
            "version": advisory.version,
            "advisory_source": advisory.advisory_source,
        },
    )

    db.commit()
    db.refresh(advisory)

    logger.info(
        f"[OFFICER_ADVISORY_EDITED] advisory_id={advisory.id} officer_id=\"{advisory.officer_id}\" "
        f"new_version={advisory.version}"
    )
    return advisory


@router.post(
    "/officer/advisories/{advisory_id}/approve",
    response_model=AdvisoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Draft Advisory for Farmer Distribution",
    description="""
    Approve an agricultural advisory, transitioning its workflow status to `APPROVED`.

    Review & Safety Rules:
    - Only `DRAFT`, `NEEDS_REVIEW`, or `EDITED` advisories can be approved.
    - Advisories that failed Phase 5.5 safety validation cannot be approved.
    - If already approved, returns HTTP 409 Conflict.
    - If rejected, returns HTTP 400 Bad Request.
    - Checks optimistic concurrency version if supplied; rejects stale approvals with HTTP 409.
    - Records approved snapshot in `approved_content`, increments version, and writes audit record.
    """,
)
def approve_advisory(
    payload: OfficerApproveRequest,
    advisory_id: int = Path(
        ...,
        ge=1,
        description="Unique identifier of the draft advisory to approve",
        examples=[1],
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP POST handler to approve an advisory.
    """
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        logger.warning(f"[OFFICER_APPROVE_NOT_FOUND] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory with ID '{advisory_id}' not found.",
        )

    # Authorization and spatial scope validation
    validate_officer_authorization(
        db=db,
        panchayat_id=advisory.panchayat_id,
        officer_role=x_officer_role,
        officer_district_scope=x_district_scope,
    )

    # Validate state transition
    if advisory.status == "APPROVED":
        logger.warning(
            f"[OFFICER_APPROVE_CONFLICT_ALREADY_APPROVED] advisory_id={advisory_id} "
            f"existing_officer_id={advisory.officer_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advisory with ID '{advisory_id}' is already APPROVED. Approved advisories cannot be modified silently.",
        )

    if advisory.status == "REJECTED":
        logger.warning(f"[OFFICER_APPROVE_REJECTED_BLOCKED] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve advisory with ID '{advisory_id}' because it has been REJECTED. Create a new revision instead.",
        )

    if advisory.status not in REVIEWABLE_STATUSES:
        logger.warning(f"[OFFICER_APPROVE_INVALID_STATUS] advisory_id={advisory_id} status={advisory.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve advisory with ID '{advisory_id}' with status '{advisory.status}'. Only reviewable advisories can be approved.",
        )

    # Validation safety requirement: cannot approve an advisory marked as FAILED_VALIDATION
    if advisory.validation_status == "FAILED_VALIDATION":
        logger.warning(f"[OFFICER_APPROVE_FAILED_VALIDATION_BLOCKED] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot approve advisory with ID '{advisory_id}': Advisory failed automated safety validation. "
                f"Officer must edit the advisory to correct violations or apply deterministic fallback before approval."
            ),
        )

    # Optimistic concurrency check
    if payload.version is not None and advisory.version != payload.version:
        logger.warning(
            f"[OFFICER_APPROVE_VERSION_CONFLICT] advisory_id={advisory_id} "
            f"current_version={advisory.version} provided_version={payload.version}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Version conflict: Advisory was updated by another officer. "
                f"Current version is {advisory.version}, but approval request was based on version {payload.version}. "
                f"Please refresh and review the latest content before approving."
            ),
        )

    prev_status = advisory.status
    now_utc = datetime.now(timezone.utc)

    # Record approved content snapshot
    advisory.approved_content = {
        "advisory_title": advisory.advisory_title,
        "advisory_text": advisory.advisory_text,
        "severity": advisory.severity,
        "approved_by": payload.officer_id.strip(),
        "approved_at": now_utc.isoformat(),
        "version": advisory.version + 1,
    }

    advisory.status = "APPROVED"
    advisory.officer_id = payload.officer_id.strip()
    advisory.officer_comment = payload.officer_comment.strip() if payload.officer_comment else None
    advisory.approved_at = now_utc
    advisory.version += 1
    advisory.updated_at = now_utc

    # Record audit log
    record_advisory_audit_log(
        db=db,
        advisory_id=advisory.id,
        action="APPROVED",
        officer_id=payload.officer_id,
        previous_status=prev_status,
        new_status="APPROVED",
        version=advisory.version,
        reason=payload.officer_comment,
        details={
            "approved_at": now_utc.isoformat(),
            "version": advisory.version,
        },
    )

    db.commit()
    db.refresh(advisory)

    logger.info(
        f"[OFFICER_ADVISORY_APPROVED] advisory_id={advisory_id} officer_id=\"{advisory.officer_id}\" "
        f"panchayat_id={advisory.panchayat_id} approved_at={advisory.approved_at} version={advisory.version}"
    )
    return advisory


@router.post(
    "/officer/advisories/{advisory_id}/reject",
    response_model=AdvisoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Draft Advisory",
    description="""
    Reject an agricultural advisory, transitioning its workflow status to `REJECTED`.

    Review & Safety Rules:
    - Only `DRAFT`, `NEEDS_REVIEW`, or `EDITED` advisories can be rejected.
    - Approved advisories cannot be rejected directly (returns HTTP 409 Conflict).
    - If already rejected, returns HTTP 409 Conflict.
    - Rejection requires an explicit reason (via `reason` or `officer_comment`).
    - Checks optimistic concurrency version if supplied; rejects stale rejections with HTTP 409.
    - Records audit log entry.
    """,
)
def reject_advisory(
    payload: OfficerRejectRequest,
    advisory_id: int = Path(
        ...,
        ge=1,
        description="Unique identifier of the draft advisory to reject",
        examples=[1],
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP POST handler to reject an advisory.
    """
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        logger.warning(f"[OFFICER_REJECT_NOT_FOUND] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory with ID '{advisory_id}' not found.",
        )

    # Authorization and spatial scope validation
    validate_officer_authorization(
        db=db,
        panchayat_id=advisory.panchayat_id,
        officer_role=x_officer_role,
        officer_district_scope=x_district_scope,
    )

    # Validate state transition
    if advisory.status == "APPROVED":
        logger.warning(
            f"[OFFICER_REJECT_CONFLICT_APPROVED] advisory_id={advisory_id} "
            f"existing_officer_id={advisory.officer_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advisory with ID '{advisory_id}' is already APPROVED. Approved advisories cannot be modified silently. An explicit revision process is required.",
        )

    if advisory.status == "REJECTED":
        logger.warning(f"[OFFICER_REJECT_ALREADY_REJECTED] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advisory with ID '{advisory_id}' is already REJECTED.",
        )

    if advisory.status not in REVIEWABLE_STATUSES:
        logger.warning(f"[OFFICER_REJECT_INVALID_STATUS] advisory_id={advisory_id} status={advisory.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject advisory with ID '{advisory_id}' with status '{advisory.status}'. Only reviewable advisories can be rejected.",
        )

    # Rejection Reason Validation: Reason is mandatory
    reason_text = (payload.reason or payload.officer_comment or "").strip()
    if not reason_text:
        logger.warning(f"[OFFICER_REJECT_MISSING_REASON] advisory_id={advisory_id}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection requires an explicit reason or remarks explaining why the advisory was rejected.",
        )

    # Optimistic concurrency check
    if payload.version is not None and advisory.version != payload.version:
        logger.warning(
            f"[OFFICER_REJECT_VERSION_CONFLICT] advisory_id={advisory_id} "
            f"current_version={advisory.version} provided_version={payload.version}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Version conflict: Advisory was updated by another officer. "
                f"Current version is {advisory.version}, but rejection request specified version {payload.version}. "
                f"Please refresh and review the latest content before rejecting."
            ),
        )

    prev_status = advisory.status
    advisory.status = "REJECTED"
    advisory.officer_id = payload.officer_id.strip()
    advisory.rejection_reason = reason_text
    advisory.officer_comment = reason_text
    advisory.version += 1
    advisory.updated_at = datetime.now(timezone.utc)

    # Record audit log
    record_advisory_audit_log(
        db=db,
        advisory_id=advisory.id,
        action="REJECTED",
        officer_id=payload.officer_id,
        previous_status=prev_status,
        new_status="REJECTED",
        version=advisory.version,
        reason=reason_text,
        details={
            "rejection_reason": reason_text,
            "version": advisory.version,
        },
    )

    db.commit()
    db.refresh(advisory)

    logger.info(
        f"[OFFICER_ADVISORY_REJECTED] advisory_id={advisory_id} officer_id=\"{advisory.officer_id}\" "
        f"panchayat_id={advisory.panchayat_id} version={advisory.version}"
    )
    return advisory


@router.get(
    "/officer/advisories/{advisory_id}/audit-trail",
    response_model=List[AdvisoryAuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve Advisory Audit Trail",
    description="""
    Retrieve the immutable chronological audit trail for a specific advisory.
    Answers: Who changed this advisory, what changed, what was the status transition, and when?
    """,
)
def get_advisory_audit_trail(
    advisory_id: int = Path(
        ...,
        ge=1,
        description="Unique identifier of the advisory",
        examples=[1],
    ),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_district_scope: Optional[str] = Header(None, alias="X-District-Scope"),
    db: Session = Depends(get_db),
) -> Any:
    """
    HTTP GET handler to fetch the audit log records of an advisory.
    """
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory with ID '{advisory_id}' not found.",
        )

    validate_officer_authorization(
        db=db,
        panchayat_id=advisory.panchayat_id,
        officer_role=x_officer_role,
        officer_district_scope=x_district_scope,
    )

    logs = (
        db.query(AdvisoryAuditLog)
        .filter(AdvisoryAuditLog.advisory_id == advisory_id)
        .order_by(AdvisoryAuditLog.id.asc())
        .all()
    )
    return logs
