"""
GramSevak Administrative Hierarchy Domain Service (Phase 3.2).

Provides high-level business logic, entity relationship validation, and spatial context
resolution for the District -> Block -> Panchayat hierarchy.

Key Invariants:
1. Thread-safe session management: accepts an explicit SQLAlchemy Session or obtains one
   safely via SessionLocal.
2. Complete spatial and administrative resolution without hardcoded district strings.
3. Decoupled from REST routing layer (callable by backend services, ML pipelines, and future APIs).
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.repositories.hierarchy_repository import HierarchyRepository
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat

logger = logging.getLogger(__name__)


class HierarchyServiceError(Exception):
    """Base exception for Hierarchy domain service errors."""
    pass


class PanchayatNotFoundError(HierarchyServiceError):
    """Raised when the requested Panchayat ID cannot be resolved in the database."""
    pass


class HierarchyParentageMismatchError(HierarchyServiceError):
    """Raised when a Panchayat does not belong to the claimed Block or District."""
    pass


class HierarchyService:
    """
    Domain service for administrative hierarchy operations.
    """

    def __init__(self, repository: Optional[HierarchyRepository] = None):
        self.repo = repository or HierarchyRepository()

    def resolve_panchayat_spatial_context(
        self,
        panchayat_id: int,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Resolve authoritative spatial, terrain, and administrative context for a Gram Panchayat.
        Returns a clean dictionary ready for ML downscaling or advisory generation.
        """
        local_db = False
        if db is None:
            db = SessionLocal()
            local_db = True

        try:
            panchayat = self.repo.get_panchayat_by_id(db, panchayat_id, eager_load_parents=True)
            if not panchayat:
                raise PanchayatNotFoundError(
                    f"Panchayat with ID '{panchayat_id}' does not exist in the administrative hierarchy."
                )

            block = panchayat.block
            district = panchayat.district

            return {
                "panchayat_id": int(panchayat.id),
                "panchayat_name": str(panchayat.name),
                "lgd_code": int(panchayat.lgd_code) if panchayat.lgd_code else None,
                "block_id": int(panchayat.block_id) if panchayat.block_id else None,
                "block_name": str(block.name) if block else "Unknown Block",
                "district_id": int(panchayat.district_id) if panchayat.district_id else None,
                "district_name": str(district.name) if district else "Unknown District",
                "state_name": str(district.state) if district else "Maharashtra",
                "latitude": float(panchayat.latitude) if panchayat.latitude is not None else None,
                "longitude": float(panchayat.longitude) if panchayat.longitude is not None else None,
                "elevation_m": float(panchayat.elevation_m) if panchayat.elevation_m is not None else None,
            }
        finally:
            if local_db:
                db.close()

    def validate_hierarchy_parentage(
        self,
        panchayat_id: int,
        expected_block_id: Optional[int] = None,
        expected_district_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Validate that a Panchayat legitimately belongs to the specified Block and/or District.
        Returns True if valid, raises HierarchyParentageMismatchError otherwise.
        """
        local_db = False
        if db is None:
            db = SessionLocal()
            local_db = True

        try:
            panchayat = self.repo.get_panchayat_by_id(db, panchayat_id, eager_load_parents=False)
            if not panchayat:
                raise PanchayatNotFoundError(f"Panchayat ID '{panchayat_id}' not found.")

            if expected_block_id is not None and panchayat.block_id != expected_block_id:
                raise HierarchyParentageMismatchError(
                    f"Panchayat {panchayat_id} belongs to Block {panchayat.block_id}, not {expected_block_id}."
                )

            if expected_district_id is not None and panchayat.district_id != expected_district_id:
                raise HierarchyParentageMismatchError(
                    f"Panchayat {panchayat_id} belongs to District {panchayat.district_id}, not {expected_district_id}."
                )

            return True
        finally:
            if local_db:
                db.close()

    def get_hierarchy_summary(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of active administrative entities and integrity health.
        """
        local_db = False
        if db is None:
            db = SessionLocal()
            local_db = True

        try:
            districts = self.repo.get_districts(db)
            district_summaries = []
            total_blocks = 0
            total_panchayats = 0

            for dist in districts:
                blocks = self.repo.get_blocks_by_district(db, dist.id)
                p_count = self.repo.get_panchayats_count(db, district_id=dist.id)
                total_blocks += len(blocks)
                total_panchayats += p_count

                district_summaries.append({
                    "id": dist.id,
                    "name": dist.name,
                    "state": dist.state,
                    "code": dist.code,
                    "blocks_count": len(blocks),
                    "panchayats_count": p_count,
                    "block_names": [b.name for b in blocks],
                })

            orphans = self.repo.detect_orphans(db)

            return {
                "total_districts": len(districts),
                "total_blocks": total_blocks,
                "total_panchayats": total_panchayats,
                "districts": district_summaries,
                "orphan_audit": orphans,
                "healthy": orphans["is_clean"],
            }
        finally:
            if local_db:
                db.close()


# Singleton instance for convenient application-wide access
_hierarchy_service_instance: Optional[HierarchyService] = None


def get_hierarchy_service() -> HierarchyService:
    """Obtain or initialize the application-wide HierarchyService singleton."""
    global _hierarchy_service_instance
    if _hierarchy_service_instance is None:
        _hierarchy_service_instance = HierarchyService()
    return _hierarchy_service_instance
