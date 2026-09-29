"""
Phase 5.6 Comprehensive Test Suite: Officer Review, Approval, Editing, Concurrency, and Audit Trail.

Validates the 20 minimum requirements defined in Phase 5.6:
1. Valid advisory enters review.
2. Invalid advisory cannot enter review.
3. Authorized officer can view advisory.
4. Unauthorized user cannot view advisory (403 Forbidden).
5. Authorized officer can edit advisory.
6. Invalid edit (banned dosage / unsafe phrasing) is rejected (422 Unprocessable Entity).
7. Numerical forecast cannot be changed through editing.
8. Authorized officer can approve validated advisory.
9. Unvalidated advisory cannot be approved (400 Bad Request).
10. Authorized officer can reject advisory.
11. Rejection requires a reason (422 Unprocessable Entity).
12. Invalid status transitions fail.
13. Duplicate approval fails safely (409 Conflict).
14. Audit record is created for each action and queryable via audit trail endpoint.
15. Original generated content is preserved after editing.
16. Final approved content is preserved.
17. Concurrent stale edit/approval is rejected (409 Conflict).
18. District/Panchayat spatial jurisdiction scope is enforced (403 Forbidden).
19. Farmer cannot approve or edit advisories (403 Forbidden).
20. Rejected advisory cannot be served to farmers (Farmer isolation guarantee).
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.advisory import Advisory, AdvisoryAuditLog
from backend.app.models.panchayat import Panchayat
from backend.app.models.block import Block
from backend.app.models.district import District
from backend.app.models.downscaled_forecast import DownscaledForecast
from src.advisory.lifecycle import (
    validate_status_transition,
    InvalidAdvisoryStatusTransitionError,
)
from backend.app.schemas.advisory_contracts import AdvisoryStatus

client = TestClient(app)


@pytest.fixture
def clean_records():
    """Cleanup test records after each test run."""
    advisory_ids = []
    panchayat_ids = []
    forecast_ids = []
    district_ids = []
    block_ids = []

    def _track(adv_id=None, p_id=None, f_id=None, d_id=None, b_id=None):
        if adv_id:
            advisory_ids.append(adv_id)
        if p_id:
            panchayat_ids.append(p_id)
        if f_id:
            forecast_ids.append(f_id)
        if d_id:
            district_ids.append(d_id)
        if b_id:
            block_ids.append(b_id)

    yield _track

    db = next(get_db())
    try:
        if advisory_ids:
            db.query(AdvisoryAuditLog).filter(AdvisoryAuditLog.advisory_id.in_(advisory_ids)).delete(synchronize_session=False)
            db.query(Advisory).filter(Advisory.id.in_(advisory_ids)).delete(synchronize_session=False)
        if forecast_ids:
            db.query(DownscaledForecast).filter(DownscaledForecast.id.in_(forecast_ids)).delete(synchronize_session=False)
        if panchayat_ids:
            db.query(Panchayat).filter(Panchayat.id.in_(panchayat_ids)).delete(synchronize_session=False)
        if block_ids:
            db.query(Block).filter(Block.id.in_(block_ids)).delete(synchronize_session=False)
        if district_ids:
            db.query(District).filter(District.id.in_(district_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def create_sample_advisory(db, clean_records, panchayat_id=1001, status="NEEDS_REVIEW", val_status="VALIDATED", rf_mm=25.0):
    adv = Advisory(
        panchayat_id=panchayat_id,
        forecast_id=101,
        forecast_date=date(2026, 9, 29),
        rainfall_mm=rf_mm,
        rainfall_category="Moderate rainfall",
        severity="MODERATE",
        advisory_title="Moderate Rain Drainage Advisory",
        advisory_text="• Clear drainage channels.\n• Postpone excessive nitrogenous fertilization.",
        rule_version="v1.0.0",
        status=status,
        version=1,
        advisory_source="DETERMINISTIC_RULES",
        validation_status=val_status,
        original_content={
            "advisory_title": "Moderate Rain Drainage Advisory",
            "advisory_text": "• Clear drainage channels.\n• Postpone excessive nitrogenous fertilization.",
            "severity": "MODERATE",
        },
    )
    db.add(adv)
    db.commit()
    db.refresh(adv)
    clean_records(adv_id=adv.id)
    return adv


# =============================================================================
# 1. VALID ADVISORY ENTERS REVIEW
# =============================================================================
def test_valid_advisory_enters_review(clean_records):
    """Test that a valid generated advisory transitions to NEEDS_REVIEW for officer inspection."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, status="NEEDS_REVIEW")
    assert adv.status == "NEEDS_REVIEW"
    assert adv.version == 1

    # Fetch from officer review endpoint
    resp = client.get(f"/api/v1/officer/advisories/{adv.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == adv.id
    assert data["status"] == "NEEDS_REVIEW"
    assert data["version"] == 1


# =============================================================================
# 2. INVALID ADVISORY CANNOT ENTER REVIEW
# =============================================================================
def test_invalid_advisory_cannot_enter_review():
    """Test that an illegal transition directly to PUBLISHED or from REJECTED is rejected by state machine."""
    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.GENERATED, AdvisoryStatus.PUBLISHED, "AI_SERVICE")

    with pytest.raises(InvalidAdvisoryStatusTransitionError):
        validate_status_transition(AdvisoryStatus.REJECTED, AdvisoryStatus.NEEDS_REVIEW, "EXTENSION_OFFICER")


# =============================================================================
# 3. AUTHORIZED OFFICER CAN VIEW ADVISORY
# =============================================================================
def test_authorized_officer_can_view_advisory(clean_records):
    """Test that an authorized extension officer can inspect advisory details."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)
    resp = client.get(
        f"/api/v1/officer/advisories/{adv.id}",
        headers={"X-Officer-Id": "OFFICER_BAGLAN_01", "X-Officer-Role": "EXTENSION_OFFICER"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == adv.id


# =============================================================================
# 4. UNAUTHORIZED USER CANNOT VIEW ADVISORY
# =============================================================================
def test_unauthorized_user_cannot_view_advisory(clean_records):
    """Test that non-officer roles (e.g. FARMER, UNAUTHORIZED) are blocked with 403 Forbidden."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    resp = client.get(
        f"/api/v1/officer/advisories/{adv.id}",
        headers={"X-Officer-Id": "FARMER_USER_12", "X-Officer-Role": "FARMER"},
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()


# =============================================================================
# 5. AUTHORIZED OFFICER CAN EDIT ADVISORY
# =============================================================================
def test_authorized_officer_can_edit_advisory(clean_records):
    """Test that an authorized officer can edit wording, which increments version and logs audit trail."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    edit_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "advisory_title": "Heavy Drainage Advisory for Ajmer Saundane",
        "advisory_text": "• Actively drain low-lying soybean plots.\n• Suspend spraying until soil dries.",
        "severity": "HIGH",
        "officer_comment": "Emphasized drainage due to local clay soils.",
        "version": 1,
    }

    resp = client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json=edit_payload,
        headers={"X-Officer-Id": "OFFICER_BAGLAN_01", "X-Officer-Role": "EXTENSION_OFFICER"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["advisory_title"] == "Heavy Drainage Advisory for Ajmer Saundane"
    assert data["severity"] == "HIGH"
    assert data["version"] == 2
    assert data["advisory_source"] == "OFFICER_AMENDED"
    assert data["status"] == "NEEDS_REVIEW"
    assert data["edited_content"]["version"] == 2


# =============================================================================
# 6. INVALID EDIT IS REJECTED
# =============================================================================
def test_invalid_edit_rejected(clean_records):
    """Test that an officer edit containing dangerous chemical dosage recipes is rejected with 422."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    bad_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "advisory_title": "Pesticide Recipe Alert",
        "advisory_text": "• Mix 50 ml per acre of chlorpyrifos immediately with water.",
        "severity": "HIGH",
        "version": 1,
    }

    resp = client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json=bad_payload,
        headers={"X-Officer-Id": "OFFICER_BAGLAN_01", "X-Officer-Role": "EXTENSION_OFFICER"},
    )
    assert resp.status_code == 422
    assert "chemical safety violation" in resp.json()["detail"].lower()


# =============================================================================
# 7. NUMERICAL FORECAST CANNOT BE CHANGED THROUGH EDITING
# =============================================================================
def test_numerical_forecast_cannot_be_changed(clean_records):
    """Test that the numerical forecast remains immutable and contradicting rainfall text is rejected."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, rf_mm=25.0)

    # 1. Contradictory rainfall claim
    contradicting_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "advisory_title": "Contradictory Weather Alert",
        "advisory_text": "• Prepare for 180 mm of extreme downpour today across fields.",
        "version": 1,
    }
    resp = client.put(f"/api/v1/officer/advisories/{adv.id}", json=contradicting_payload)
    assert resp.status_code == 422
    assert "numerical forecast contradiction" in resp.json()["detail"].lower()

    # 2. Database numerical rainfall remains strictly unchanged
    db.refresh(adv)
    assert float(adv.rainfall_mm) == 25.0


# =============================================================================
# 8. AUTHORIZED OFFICER CAN APPROVE VALIDATED ADVISORY
# =============================================================================
def test_authorized_officer_can_approve(clean_records):
    """Test that an authorized officer can approve an advisory, transitioning it to APPROVED with approved snapshot."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, val_status="VALIDATED")

    approve_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "officer_comment": "Ground conditions validated. Release to farmers.",
        "version": 1,
    }

    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/approve", json=approve_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "APPROVED"
    assert data["officer_id"] == "OFFICER_BAGLAN_01"
    assert data["approved_at"] is not None
    assert data["version"] == 2
    assert data["approved_content"]["approved_by"] == "OFFICER_BAGLAN_01"


# =============================================================================
# 9. UNVALIDATED ADVISORY CANNOT BE APPROVED
# =============================================================================
def test_unvalidated_advisory_cannot_be_approved(clean_records):
    """Test that an advisory marked as FAILED_VALIDATION cannot be approved."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, val_status="FAILED_VALIDATION")

    approve_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "officer_comment": "Attempting approval of unsafe draft.",
        "version": 1,
    }

    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/approve", json=approve_payload)
    assert resp.status_code == 400
    assert "failed automated safety validation" in resp.json()["detail"].lower()


# =============================================================================
# 10. AUTHORIZED OFFICER CAN REJECT ADVISORY
# =============================================================================
def test_authorized_officer_can_reject(clean_records):
    """Test that an authorized officer can reject an advisory with a recorded reason."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    reject_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "reason": "Microclimate hill shadow negated rainfall forecast.",
        "version": 1,
    }

    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/reject", json=reject_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REJECTED"
    assert data["rejection_reason"] == "Microclimate hill shadow negated rainfall forecast."
    assert data["version"] == 2


# =============================================================================
# 11. REJECTION REQUIRES A REASON
# =============================================================================
def test_rejection_requires_reason(clean_records):
    """Test that rejecting an advisory without a reason returns HTTP 422."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    reject_payload = {
        "officer_id": "OFFICER_BAGLAN_01",
        "reason": "   ",  # Whitespace only
        "officer_comment": "",
        "version": 1,
    }

    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/reject", json=reject_payload)
    assert resp.status_code == 422
    assert "explicit reason" in resp.json()["detail"].lower()


# =============================================================================
# 12. INVALID STATUS TRANSITIONS FAIL
# =============================================================================
def test_invalid_status_transitions_fail(clean_records):
    """Test that invalid transitions, such as approving a REJECTED advisory, fail with 400."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, status="REJECTED")

    approve_payload = {"officer_id": "OFFICER_TEST", "version": 1}
    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/approve", json=approve_payload)
    assert resp.status_code == 400
    assert "cannot approve" in resp.json()["detail"].lower()


# =============================================================================
# 13. DUPLICATE APPROVAL FAILS SAFELY
# =============================================================================
def test_duplicate_approval_fails_safely(clean_records):
    """Test that approving an already APPROVED advisory returns 409 Conflict."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records, status="APPROVED")

    approve_payload = {"officer_id": "OFFICER_TEST", "version": 1}
    resp = client.post(f"/api/v1/officer/advisories/{adv.id}/approve", json=approve_payload)
    assert resp.status_code == 409
    assert "already approved" in resp.json()["detail"].lower()


# =============================================================================
# 14. AUDIT RECORD CREATED FOR EACH ACTION
# =============================================================================
def test_audit_record_created_for_each_action(clean_records):
    """Test that all lifecycle events (EDITED, APPROVED) create immutable audit entries."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    # 1. Edit
    client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json={
            "officer_id": "OFFICER_AUDIT_1",
            "advisory_title": "Audited Edit Title",
            "advisory_text": "• Verified soil advice text.",
            "version": 1,
        },
    )

    # 2. Approve
    client.post(
        f"/api/v1/officer/advisories/{adv.id}/approve",
        json={"officer_id": "OFFICER_AUDIT_2", "version": 2},
    )

    # 3. Query Audit Trail
    resp = client.get(f"/api/v1/officer/advisories/{adv.id}/audit-trail")
    assert resp.status_code == 200
    trail = resp.json()
    assert len(trail) >= 2
    actions = [t["action"] for t in trail]
    assert "EDITED" in actions
    assert "APPROVED" in actions


# =============================================================================
# 15. ORIGINAL GENERATED CONTENT IS PRESERVED AFTER EDITING
# =============================================================================
def test_original_content_preserved_after_editing(clean_records):
    """Test that editing retains the original generated content intact."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)
    original_title = adv.advisory_title

    client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json={
            "officer_id": "OFFICER_EDIT_PRESERVE",
            "advisory_title": "Brand New Officer Title",
            "advisory_text": "• Brand new guidance advice.",
            "version": 1,
        },
    )

    db.refresh(adv)
    assert adv.advisory_title == "Brand New Officer Title"
    assert adv.original_content is not None
    assert adv.original_content["advisory_title"] == original_title


# =============================================================================
# 16. FINAL APPROVED CONTENT IS PRESERVED
# =============================================================================
def test_final_approved_content_preserved(clean_records):
    """Test that approval saves a snapshot in approved_content."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    client.post(
        f"/api/v1/officer/advisories/{adv.id}/approve",
        json={"officer_id": "OFFICER_FINAL", "version": 1},
    )

    db.refresh(adv)
    assert adv.approved_content is not None
    assert adv.approved_content["approved_by"] == "OFFICER_FINAL"
    assert adv.approved_content["advisory_title"] == adv.advisory_title


# =============================================================================
# 17. CONCURRENT STALE EDIT / APPROVAL IS REJECTED
# =============================================================================
def test_concurrent_stale_actions_rejected(clean_records):
    """Test optimistic locking: Officer A and Officer B concurrent scenario."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)
    assert adv.version == 1

    # Officer A edits and moves version to 2
    resp_a = client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json={
            "officer_id": "OFFICER_A",
            "advisory_title": "Officer A Update",
            "advisory_text": "• Officer A recommendations.",
            "version": 1,
        },
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["version"] == 2

    # Officer B attempts to approve stale version 1
    resp_b = client.post(
        f"/api/v1/officer/advisories/{adv.id}/approve",
        json={"officer_id": "OFFICER_B", "version": 1},
    )
    assert resp_b.status_code == 409
    assert "version conflict" in resp_b.json()["detail"].lower()


# =============================================================================
# 18. DISTRICT / PANCHAYAT SCOPE IS ENFORCED
# =============================================================================
def test_district_panchayat_scope_enforced(clean_records):
    """Test that an officer assigned to Pune cannot edit an advisory in Nashik."""
    db = next(get_db())
    d_nashik = District(name="Nashik_Scope_Test", state="Maharashtra")
    db.add(d_nashik)
    db.commit()
    db.refresh(d_nashik)
    clean_records(d_id=d_nashik.id)

    p = Panchayat(
        id=88801,
        lgd_code=88801,
        name="Scope Test Panchayat",
        district_id=d_nashik.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    clean_records(p_id=p.id)

    adv = create_sample_advisory(db, clean_records, panchayat_id=p.id)

    # Officer from Pune tries to edit Nashik advisory
    resp = client.put(
        f"/api/v1/officer/advisories/{adv.id}",
        json={
            "officer_id": "OFFICER_PUNE_01",
            "advisory_title": "Out of Scope Edit",
            "advisory_text": "• Valid guidance text.",
            "version": 1,
        },
        headers={"X-Officer-Role": "EXTENSION_OFFICER", "X-District-Scope": "Pune"},
    )
    assert resp.status_code == 403
    assert "jurisdiction" in resp.json()["detail"].lower()


# =============================================================================
# 19. FARMER CANNOT APPROVE
# =============================================================================
def test_farmer_cannot_approve(clean_records):
    """Test that requests with farmer role cannot approve advisories."""
    db = next(get_db())
    adv = create_sample_advisory(db, clean_records)

    resp = client.post(
        f"/api/v1/officer/advisories/{adv.id}/approve",
        json={"officer_id": "FARMER_BOB", "version": 1},
        headers={"X-Officer-Role": "FARMER"},
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()


# =============================================================================
# 20. REJECTED ADVISORY CANNOT BE PUBLISHED / SERVED TO FARMERS
# =============================================================================
def test_rejected_advisory_cannot_be_served_to_farmers(clean_records):
    """Test that an advisory in REJECTED state is never served by farmer-facing endpoint."""
    db = next(get_db())
    panchayat_id = 99901
    f_date = date(2026, 9, 29)

    # Create dummy panchayat
    p = Panchayat(id=panchayat_id, lgd_code=panchayat_id, name="Farmer Isolation Panchayat")
    db.add(p)
    db.commit()
    clean_records(p_id=p.id)

    # Create dummy forecast
    fc = DownscaledForecast(
        id=77701,
        panchayat_id=panchayat_id,
        forecast_date=f_date,
        forecast_issue_date=date(2026, 9, 28),
        downscaled_rainfall_mm=30.0,
        model_name="XGBoost",
        model_version="v1.0.0",
    )
    db.add(fc)
    db.commit()
    db.refresh(fc)
    clean_records(f_id=fc.id)

    # Create REJECTED advisory
    adv = create_sample_advisory(db, clean_records, panchayat_id=panchayat_id, status="REJECTED")

    # Farmer endpoint request
    resp = client.get(f"/api/v1/farmer/panchayat/{panchayat_id}?forecast_date={f_date}")
    assert resp.status_code == 200
    farmer_data = resp.json()
    # Advisory status must indicate NO_APPROVED_ADVISORY
    assert farmer_data["advisory_status"] == "NO_APPROVED_ADVISORY"
    assert farmer_data["advisory_points"] == []
    assert farmer_data["advisory_title"] is None
