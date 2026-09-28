"""
GramSevak Administrative Hierarchy Repository (Phase 3.2).

Provides high-performance, parameterized data-access methods for:
- Districts
- Blocks (Tehsils / Talukas)
- Gram Panchayats

Key Invariants:
1. Strict use of parameterized SQLAlchemy queries to prevent SQL injection.
2. Identifiers (integer IDs) used for parent-child navigation, never fragile name strings.
3. Eager relationship joins where needed (joinedload) to eliminate N+1 query patterns.
4. Bounded pagination and deterministic sorting for all multi-record lookups.
5. Zero HTTP / REST dependencies (pure data-access layer).
"""

import math
import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, cast, String, text

from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.weather_observation import WeatherObservation

logger = logging.getLogger(__name__)


class HierarchyRepository:
    """
    Centralized data-access layer for the District -> Block -> Panchayat administrative hierarchy.
    """

    # =========================================================================
    # 1. DISTRICT QUERIES
    # =========================================================================

    @staticmethod
    def get_districts(db: Session) -> List[District]:
        """
        Retrieve all configured administrative districts, ordered deterministically by name.
        """
        return db.query(District).order_by(District.name.asc(), District.id.asc()).all()

    @staticmethod
    def get_districts_paginated(
        db: Session,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> Tuple[List[District], int]:
        """
        Retrieve a paginated, searchable list of administrative districts.
        Ordered deterministically by name ASC, id ASC.
        Returns a tuple of (items, total_count).
        """
        query = db.query(District)
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(District.name).ilike(pattern),
                    cast(District.id, String).ilike(pattern),
                    func.lower(District.state).ilike(pattern),
                )
            )
        query = query.order_by(District.name.asc(), District.id.asc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def get_district_by_id(db: Session, district_id: int) -> Optional[District]:
        """
        Retrieve a single District by its primary key ID.
        """
        return db.query(District).filter(District.id == district_id).first()

    @staticmethod
    def get_district_by_name(db: Session, name: str) -> Optional[District]:
        """
        Retrieve a District by case-insensitive name match.
        """
        if not name or not name.strip():
            return None
        return (
            db.query(District)
            .filter(func.lower(District.name) == name.strip().lower())
            .first()
        )

    # =========================================================================
    # 2. BLOCK QUERIES
    # =========================================================================

    @staticmethod
    def get_blocks_by_district(db: Session, district_id: int) -> List[Block]:
        """
        Retrieve all blocks belonging to a specific district ID, ordered alphabetically.
        """
        return (
            db.query(Block)
            .filter(Block.district_id == district_id)
            .order_by(Block.name.asc(), Block.id.asc())
            .all()
        )

    @staticmethod
    def get_blocks_by_district_paginated(
        db: Session,
        district_id: int,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> Tuple[List[Block], int]:
        """
        Retrieve a paginated, searchable list of blocks scoped strictly to a district ID.
        Ordered deterministically by name ASC, id ASC.
        Returns a tuple of (items, total_count).
        """
        query = db.query(Block).filter(Block.district_id == district_id)
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Block.name).ilike(pattern),
                    cast(Block.id, String).ilike(pattern),
                )
            )
        query = query.order_by(Block.name.asc(), Block.id.asc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def get_block_by_id(db: Session, block_id: int, eager_district: bool = False) -> Optional[Block]:
        """
        Retrieve a single Block by ID, with optional eager loading of parent District.
        """
        query = db.query(Block).filter(Block.id == block_id)
        if eager_district:
            query = query.options(joinedload(Block.district))
        return query.first()

    @staticmethod
    def get_block_by_name(db: Session, district_id: int, name: str) -> Optional[Block]:
        """
        Retrieve a Block by parent district_id and block name.
        """
        if not name or not name.strip():
            return None
        return (
            db.query(Block)
            .filter(
                Block.district_id == district_id,
                func.lower(Block.name) == name.strip().lower(),
            )
            .first()
        )

    # =========================================================================
    # 3. PANCHAYAT QUERIES
    # =========================================================================

    @staticmethod
    def get_panchayats_by_block(
        db: Session,
        block_id: int,
        offset: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> Tuple[List[Panchayat], int]:
        """
        Retrieve a paginated, searchable list of Panchayats scoped strictly by Block ID.
        Returns a tuple of (items, total_count).
        """
        query = db.query(Panchayat).filter(Panchayat.block_id == block_id)

        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Panchayat.name).ilike(pattern),
                    cast(Panchayat.lgd_code, String).ilike(pattern),
                    cast(Panchayat.id, String).ilike(pattern),
                )
            )

        # Deterministic sorting on composite index (name, id)
        query = query.order_by(Panchayat.name.asc(), Panchayat.id.asc())

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def get_panchayat_by_id(
        db: Session,
        panchayat_id: int,
        eager_load_parents: bool = True,
    ) -> Optional[Panchayat]:
        """
        Retrieve a single Panchayat by primary key ID.
        Optionally eager-loads parent Block and District in a single JOIN.
        """
        query = db.query(Panchayat).filter(Panchayat.id == panchayat_id)
        if eager_load_parents:
            query = query.options(
                joinedload(Panchayat.block),
                joinedload(Panchayat.district),
            )
        return query.first()

    @staticmethod
    def get_panchayat_by_lgd(db: Session, lgd_code: int) -> Optional[Panchayat]:
        """
        Retrieve a Panchayat by official Ministry of Panchayati Raj 6-digit LGD Code.
        """
        return db.query(Panchayat).filter(Panchayat.lgd_code == lgd_code).first()

    @staticmethod
    def get_panchayats_count(
        db: Session,
        district_id: Optional[int] = None,
        block_id: Optional[int] = None,
    ) -> int:
        """
        Count total Panchayats with optional scoping by district or block.
        """
        query = db.query(Panchayat)
        if district_id is not None:
            query = query.filter(Panchayat.district_id == district_id)
        if block_id is not None:
            query = query.filter(Panchayat.block_id == block_id)
        return query.count()

    # =========================================================================
    # 4. ORPHAN INTEGRITY AUDITING
    # =========================================================================

    @staticmethod
    def detect_orphans(db: Session) -> Dict[str, int]:
        """
        Detect any dangling or unlinked records across the administrative hierarchy.
        Returns a dictionary of orphan counts. Zero indicates complete integrity.
        """
        orphan_blocks = db.execute(text("""
            SELECT count(*) FROM blocks b
            LEFT JOIN districts d ON b.district_id = d.id
            WHERE d.id IS NULL;
        """)).scalar() or 0

        orphan_panchayats_block = db.execute(text("""
            SELECT count(*) FROM panchayats p
            LEFT JOIN blocks b ON p.block_id = b.id
            WHERE b.id IS NULL;
        """)).scalar() or 0

        orphan_panchayats_district = db.execute(text("""
            SELECT count(*) FROM panchayats p
            LEFT JOIN districts d ON p.district_id = d.id
            WHERE d.id IS NULL;
        """)).scalar() or 0

        orphan_weather_panchayat = db.execute(text("""
            SELECT count(*) FROM weather_observations w
            LEFT JOIN panchayats p ON w.panchayat_id = p.id
            WHERE p.id IS NULL;
        """)).scalar() or 0

        return {
            "orphan_blocks": int(orphan_blocks),
            "orphan_panchayats_block": int(orphan_panchayats_block),
            "orphan_panchayats_district": int(orphan_panchayats_district),
            "orphan_weather_panchayat": int(orphan_weather_panchayat),
            "is_clean": (
                orphan_blocks == 0
                and orphan_panchayats_block == 0
                and orphan_panchayats_district == 0
                and orphan_weather_panchayat == 0
            ),
        }

    # =========================================================================
    # 5. IDEMPOTENT UPSERT HELPERS
    # =========================================================================

    @staticmethod
    def upsert_district(
        db: Session,
        name: str,
        state: str = "Maharashtra",
        code: Optional[str] = None,
    ) -> District:
        """
        Idempotently find or create an administrative District.
        """
        clean_name = name.strip()
        existing = db.query(District).filter(func.lower(District.name) == clean_name.lower()).first()
        if existing:
            if code and existing.code != code:
                existing.code = code
                db.flush()
            return existing

        new_dist = District(name=clean_name, state=state.strip(), code=code)
        db.add(new_dist)
        db.flush()
        return new_dist

    @staticmethod
    def upsert_block(
        db: Session,
        district_id: int,
        name: str,
        code: Optional[str] = None,
    ) -> Block:
        """
        Idempotently find or create an administrative Block under a District.
        """
        clean_name = name.strip()
        existing = (
            db.query(Block)
            .filter(
                Block.district_id == district_id,
                func.lower(Block.name) == clean_name.lower(),
            )
            .first()
        )
        if existing:
            if code and existing.code != code:
                existing.code = code
                db.flush()
            return existing

        new_blk = Block(district_id=district_id, name=clean_name, code=code)
        db.add(new_blk)
        db.flush()
        return new_blk

    @staticmethod
    def upsert_panchayat(
        db: Session,
        id: int,
        lgd_code: int,
        name: str,
        block_id: int,
        district_id: int,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        elevation_m: Optional[float] = None,
        panchayat_code: Optional[str] = None,
    ) -> Panchayat:
        """
        Idempotently find or create a Gram Panchayat under a Block and District.
        """
        existing = db.query(Panchayat).filter(Panchayat.id == id).first()
        if existing:
            # Update attributes if modified
            existing.lgd_code = lgd_code
            existing.name = name.strip()
            existing.block_id = block_id
            existing.district_id = district_id
            if latitude is not None:
                existing.latitude = latitude
            if longitude is not None:
                existing.longitude = longitude
            if elevation_m is not None:
                existing.elevation_m = elevation_m
            if panchayat_code is not None:
                existing.panchayat_code = panchayat_code
            db.flush()
            return existing

        new_p = Panchayat(
            id=id,
            lgd_code=lgd_code,
            name=name.strip(),
            block_id=block_id,
            district_id=district_id,
            latitude=latitude,
            longitude=longitude,
            elevation_m=elevation_m,
            panchayat_code=panchayat_code,
        )
        db.add(new_p)
        db.flush()
        return new_p
