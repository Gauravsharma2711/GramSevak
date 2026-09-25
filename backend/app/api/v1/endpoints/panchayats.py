"""
Panchayat API Endpoints.
Provides access to Nashik Gram Panchayats with geo-spatial attributes for weather downscaling.
"""

import math
import logging
from typing import Optional, List
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends, Query, Path as FastAPIPath, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, cast, String

from backend.app.core.database import get_db
from backend.app.core.logging import log_db_operation
from backend.app.models.panchayat_weather import PanchayatWeatherData
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.schemas.panchayat import (
    PanchayatItem,
    PanchayatPagination,
    PanchayatDetailResponse,
    DistrictItem,
    BlockItem,
    BlockPanchayatItem,
    BlockPanchayatPagination,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PROCESSED_DATA_PATH = Path("data/processed/nashik_weather_clean.csv")


@router.get(
    "/panchayats",
    response_model=PanchayatPagination,
    summary="List Nashik District Panchayats",
    description=(
        "Retrieves a paginated list of Gram Panchayats in Nashik District with geographical "
        "coordinates (latitude, longitude, elevation) required for micro-level weather downscaling. "
        "Supports optional filtering by administrative block and case-insensitive search."
    ),
    response_description="Paginated list of Nashik Panchayats",
    tags=["Panchayats"],
)
def get_panchayats(
    district_name: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Optional filter by administrative district (e.g. 'Nashik', 'Pune'). Case-insensitive.",
        examples=["Nashik"],
    ),
    block_name: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Optional filter by administrative block/tehsil (e.g., 'Baglan', 'Dindori', 'Surgana', 'Haveli'). Case-insensitive.",
        examples=["Baglan"],
    ),
    search: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Optional search query matching panchayat name, block name, or LGD code (case-insensitive).",
        examples=["Ajmer"],
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed). Must be greater than or equal to 1.",
        examples=[1],
    ),
    page_size: int = Query(
        50,
        ge=1,
        le=500,
        description="Number of records to return per page (1 to 500). Default is 50.",
        examples=[50],
    ),
    district_id: Optional[int] = Query(
        None,
        ge=1,
        description="Optional filter by administrative district ID.",
        examples=[1],
    ),
    block_id: Optional[int] = Query(
        None,
        ge=1,
        description="Optional filter by administrative block ID.",
        examples=[1],
    ),
    db: Session = Depends(get_db),
) -> PanchayatPagination:
    """
    Fetch paginated Gram Panchayats from Supabase PostgreSQL database.
    Applies optional block filter and search query, returning safe public fields.
    """
    logger.info(
        f"[REQUEST] request_type=GET /api/v1/panchayats district_name={district_name} "
        f"district_id={district_id} block_name={block_name} block_id={block_id} "
        f"search={search} page={page} page_size={page_size}"
    )
    try:
        # Build base query for distinct Panchayat metadata
        query = db.query(
            PanchayatWeatherData.panchayat_id,
            PanchayatWeatherData.lgd_code,
            PanchayatWeatherData.panchayat_name,
            PanchayatWeatherData.block_name,
            PanchayatWeatherData.district_name,
            PanchayatWeatherData.panchayat_latitude.label("latitude"),
            PanchayatWeatherData.panchayat_longitude.label("longitude"),
            PanchayatWeatherData.elevation_m,
        ).group_by(
            PanchayatWeatherData.panchayat_id,
            PanchayatWeatherData.lgd_code,
            PanchayatWeatherData.panchayat_name,
            PanchayatWeatherData.block_name,
            PanchayatWeatherData.district_name,
            PanchayatWeatherData.panchayat_latitude,
            PanchayatWeatherData.panchayat_longitude,
            PanchayatWeatherData.elevation_m,
        )

        # Apply district_id filter if provided
        if district_id is not None:
            dist = db.query(District).filter(District.id == district_id).first()
            if dist:
                query = query.filter(
                    func.lower(PanchayatWeatherData.district_name) == dist.name.strip().lower()
                )

        # Apply district_name filter
        if district_name and district_name.strip():
            clean_dist = district_name.strip().lower()
            query = query.filter(
                func.lower(PanchayatWeatherData.district_name) == clean_dist
            )

        # Apply block_id filter if provided
        if block_id is not None:
            blk = db.query(Block).filter(Block.id == block_id).first()
            if blk:
                query = query.filter(
                    func.lower(PanchayatWeatherData.block_name) == blk.name.strip().lower()
                )

        # Apply block_name filter
        if block_name and block_name.strip():
            clean_block = block_name.strip().lower()
            query = query.filter(
                func.lower(PanchayatWeatherData.block_name) == clean_block
            )

        # Apply search filter across panchayat_name, block_name, and lgd_code
        if search and search.strip():
            search_pattern = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(PanchayatWeatherData.panchayat_name).ilike(search_pattern),
                    func.lower(PanchayatWeatherData.block_name).ilike(search_pattern),
                    cast(PanchayatWeatherData.lgd_code, String).ilike(search_pattern),
                    cast(PanchayatWeatherData.panchayat_id, String).ilike(search_pattern),
                )
            )

        # Order consistently by panchayat_id
        query = query.order_by(PanchayatWeatherData.panchayat_id.asc())

        # Count total distinct results
        total = query.count()

        # Apply pagination offset and limit
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        items = [
            PanchayatItem(
                panchayat_id=int(row.panchayat_id),
                lgd_code=int(row.lgd_code),
                panchayat_name=str(row.panchayat_name),
                block_name=str(row.block_name),
                district_name=str(row.district_name),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                elevation_m=float(row.elevation_m),
            )
            for row in results
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PanchayatPagination(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    except Exception as db_exc:
        logger.warning(
            f"Database query failed ({db_exc}). Attempting fallback to local processed registry."
        )
        if PROCESSED_DATA_PATH.exists():
            try:
                df = pd.read_csv(PROCESSED_DATA_PATH)
                cols = [
                    "panchayat_id",
                    "lgd_code",
                    "panchayat_name",
                    "block_name",
                    "district_name",
                    "panchayat_latitude",
                    "panchayat_longitude",
                    "elevation_m",
                ]
                df_unique = df[cols].drop_duplicates().rename(
                    columns={
                        "panchayat_latitude": "latitude",
                        "panchayat_longitude": "longitude",
                    }
                )

                if block_name and block_name.strip():
                    df_unique = df_unique[
                        df_unique["block_name"].str.lower() == block_name.strip().lower()
                    ]

                if search and search.strip():
                    st = search.strip().lower()
                    match_mask = (
                        df_unique["panchayat_name"].str.lower().str.contains(st, na=False)
                        | df_unique["block_name"].str.lower().str.contains(st, na=False)
                        | df_unique["lgd_code"].astype(str).str.contains(st, na=False)
                        | df_unique["panchayat_id"].astype(str).str.contains(st, na=False)
                    )
                    df_unique = df_unique[match_mask]

                df_unique = df_unique.sort_values(by="panchayat_id")
                total = len(df_unique)
                total_pages = math.ceil(total / page_size) if total > 0 else 0

                offset = (page - 1) * page_size
                paged_df = df_unique.iloc[offset : offset + page_size]

                items = [
                    PanchayatItem(
                        panchayat_id=int(r["panchayat_id"]),
                        lgd_code=int(r["lgd_code"]),
                        panchayat_name=str(r["panchayat_name"]),
                        block_name=str(r["block_name"]),
                        district_name=str(r["district_name"]),
                        latitude=float(r["latitude"]),
                        longitude=float(r["longitude"]),
                        elevation_m=float(r["elevation_m"]),
                    )
                    for _, r in paged_df.iterrows()
                ]

                return PanchayatPagination(
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                    items=items,
                )
            except Exception as file_exc:
                logger.error(f"Fallback registry failed: {file_exc}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve panchayats from database or fallback store.",
        )


@router.get(
    "/panchayats/{panchayat_id}",
    response_model=PanchayatDetailResponse,
    summary="Get Panchayat Details by ID",
    description=(
        "Retrieves detailed geographic and administrative metadata for a specific Gram Panchayat "
        "by its unique system ID (panchayat_id). Returns HTTP 404 if the Panchayat does not exist."
    ),
    response_description="Detailed metadata for the requested Gram Panchayat",
    responses={
        200: {"description": "Panchayat found and metadata returned successfully."},
        404: {"description": "Panchayat with the specified ID was not found."},
    },
    tags=["Panchayats"],
)
def get_panchayat_by_id(
    panchayat_id: int = FastAPIPath(
        ...,
        ge=1,
        description="Unique identifier of the Gram Panchayat (e.g., 1001, 2099)",
        examples=[1001],
    ),
    db: Session = Depends(get_db),
) -> PanchayatDetailResponse:
    """
    Fetch a single Gram Panchayat by ID from Supabase PostgreSQL database.
    Returns HTTP 404 if the Panchayat is not found.
    """
    logger.info(
        f"[REQUEST] request_type=GET /api/v1/panchayats/{{panchayat_id}} panchayat_id={panchayat_id}"
    )
    try:
        # 1. Query normalized Panchayat model (with block and district relationships)
        p_row = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
        if p_row is not None:
            b_name = p_row.block.name if p_row.block else "Unknown"
            d_name = p_row.district.name if p_row.district else "Unknown"
            log_db_operation(
                logger=logger,
                operation="SELECT",
                table="panchayats",
                status="SUCCESS",
                panchayat_id=panchayat_id,
                details=f"panchayat_name=\"{p_row.name}\" block_name=\"{b_name}\" district_name=\"{d_name}\"",
            )
            return PanchayatDetailResponse(
                panchayat_id=int(p_row.id),
                lgd_code=int(p_row.lgd_code),
                panchayat_name=str(p_row.name),
                block_name=str(b_name),
                district_name=str(d_name),
                latitude=float(p_row.latitude) if p_row.latitude is not None else 0.0,
                longitude=float(p_row.longitude) if p_row.longitude is not None else 0.0,
                elevation_m=float(p_row.elevation_m) if p_row.elevation_m is not None else 0.0,
                id=int(p_row.id),
                name=str(p_row.name),
                block_id=int(p_row.block_id) if p_row.block_id is not None else None,
                district_id=int(p_row.district_id) if p_row.district_id is not None else None,
            )

        # 2. Query legacy panchayat_weather_data table
        row = (
            db.query(
                PanchayatWeatherData.panchayat_id,
                PanchayatWeatherData.lgd_code,
                PanchayatWeatherData.panchayat_name,
                PanchayatWeatherData.block_name,
                PanchayatWeatherData.district_name,
                PanchayatWeatherData.panchayat_latitude.label("latitude"),
                PanchayatWeatherData.panchayat_longitude.label("longitude"),
                PanchayatWeatherData.elevation_m,
            )
            .filter(PanchayatWeatherData.panchayat_id == panchayat_id)
            .first()
        )

        if row is not None:
            log_db_operation(
                logger=logger,
                operation="SELECT",
                table="panchayat_weather_data",
                status="SUCCESS",
                panchayat_id=panchayat_id,
                details=f"panchayat_name=\"{row.panchayat_name}\" block_name=\"{row.block_name}\"",
            )
            return PanchayatDetailResponse(
                panchayat_id=int(row.panchayat_id),
                lgd_code=int(row.lgd_code),
                panchayat_name=str(row.panchayat_name),
                block_name=str(row.block_name),
                district_name=str(row.district_name),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                elevation_m=float(row.elevation_m),
                id=int(row.panchayat_id),
                name=str(row.panchayat_name),
            )

        # If not found in DB, log warning and return 404
        log_db_operation(
            logger=logger,
            operation="SELECT",
            table="panchayat_weather_data",
            status="NOT_FOUND",
            panchayat_id=panchayat_id,
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panchayat with ID {panchayat_id} not found.",
        )

    except HTTPException:
        # Re-raise explicit HTTP 404
        raise
    except Exception as db_exc:
        logger.warning(
            f"Database query failed for panchayat_id={panchayat_id} ({db_exc}). Attempting fallback."
        )
        if PROCESSED_DATA_PATH.exists():
            try:
                df = pd.read_csv(PROCESSED_DATA_PATH)
                match = df[df["panchayat_id"] == panchayat_id]
                if not match.empty:
                    r = match.iloc[0]
                    return PanchayatDetailResponse(
                        panchayat_id=int(r["panchayat_id"]),
                        lgd_code=int(r["lgd_code"]),
                        panchayat_name=str(r["panchayat_name"]),
                        block_name=str(r["block_name"]),
                        district_name=str(r["district_name"]),
                        latitude=float(r["panchayat_latitude"]),
                        longitude=float(r["panchayat_longitude"]),
                        elevation_m=float(r["elevation_m"]),
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Panchayat with ID {panchayat_id} not found.",
                    )
            except HTTPException:
                raise
            except Exception as file_exc:
                logger.error(f"Fallback registry failed for panchayat_id={panchayat_id}: {file_exc}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve panchayat details from database or fallback store.",
        )


@router.get(
    "/districts",
    response_model=List[DistrictItem],
    summary="List All Administrative Districts",
    description="Retrieves list of all configured districts (e.g. Nashik, Pune).",
    tags=["Panchayats"],
)
def get_districts(db: Session = Depends(get_db)) -> List[DistrictItem]:
    districts = db.query(District).order_by(District.name.asc()).all()
    if not districts:
        rows = db.query(PanchayatWeatherData.district_name).distinct().all()
        return [DistrictItem(id=i + 1, name=r[0], state="Maharashtra") for i, r in enumerate(rows) if r[0]]
    return [DistrictItem(id=d.id, name=d.name, state=d.state) for d in districts]


@router.get(
    "/districts/{district_id}/blocks",
    response_model=List[BlockItem],
    summary="List Blocks for a Specific District",
    description="Retrieves all administrative blocks / tehsils belonging to a specific district ID.",
    tags=["Panchayats"],
)
def get_district_blocks(
    district_id: int = FastAPIPath(..., ge=1, description="Unique District identifier"),
    db: Session = Depends(get_db),
) -> List[BlockItem]:
    dist = db.query(District).filter(District.id == district_id).first()
    if not dist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District with ID {district_id} not found.",
        )
    blocks = db.query(Block).filter(Block.district_id == district_id).order_by(Block.name.asc()).all()
    return [BlockItem(id=b.id, district_id=b.district_id, name=b.name) for b in blocks]


@router.get(
    "/blocks/{block_id}/panchayats",
    response_model=BlockPanchayatPagination,
    summary="List Panchayats for a Specific Block",
    description=(
        "Retrieves a paginated list of Gram Panchayats belonging to a specific administrative Block ID. "
        "Supports optional case-insensitive search and bounded pagination."
    ),
    tags=["Panchayats"],
)
def get_block_panchayats(
    block_id: int = FastAPIPath(..., ge=1, description="Unique Block identifier"),
    search: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Optional search query matching panchayat name or LGD code (case-insensitive).",
        examples=["Ajmer"],
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed). Must be greater than or equal to 1.",
        examples=[1],
    ),
    page_size: int = Query(
        50,
        ge=1,
        le=200,
        description="Number of records to return per page (1 to 200). Default is 50.",
        examples=[50],
    ),
    db: Session = Depends(get_db),
) -> BlockPanchayatPagination:
    """
    Fetch paginated Gram Panchayats for a specific block using the normalized hierarchy.
    """
    block = db.query(Block).filter(Block.id == block_id).first()
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block with ID {block_id} not found.",
        )

    query = db.query(Panchayat).filter(Panchayat.block_id == block_id)

    if search and search.strip():
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Panchayat.name).ilike(search_pattern),
                cast(Panchayat.lgd_code, String).ilike(search_pattern),
                cast(Panchayat.id, String).ilike(search_pattern),
            )
        )

    # Deterministic ordering leveraging composite index (block_id, name)
    query = query.order_by(Panchayat.name.asc(), Panchayat.id.asc())

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    offset = (page - 1) * page_size
    results = query.offset(offset).limit(page_size).all()

    items = [
        BlockPanchayatItem(
            id=int(p.id),
            lgd_code=int(p.lgd_code),
            name=str(p.name),
            block_id=int(p.block_id),
            district_id=int(p.district_id) if p.district_id else int(block.district_id),
            latitude=float(p.latitude) if p.latitude is not None else None,
            longitude=float(p.longitude) if p.longitude is not None else None,
            elevation_m=float(p.elevation_m) if p.elevation_m is not None else None,
            panchayat_id=int(p.id),
            panchayat_name=str(p.name),
        )
        for p in results
    ]

    return BlockPanchayatPagination(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get(
    "/blocks",
    response_model=List[BlockItem],
    summary="List All Administrative Blocks",
    description="Retrieves administrative blocks across all districts with optional district name filter.",
    tags=["Panchayats"],
)
def get_all_blocks(
    district_name: Optional[str] = Query(None, description="Optional filter by district name (e.g. 'Nashik', 'Pune')"),
    db: Session = Depends(get_db),
) -> List[BlockItem]:
    query = db.query(Block)
    if district_name and district_name.strip():
        dist = db.query(District).filter(func.lower(District.name) == district_name.strip().lower()).first()
        if dist:
            query = query.filter(Block.district_id == dist.id)
    blocks = query.order_by(Block.name.asc()).all()
    return [BlockItem(id=b.id, district_id=b.district_id, name=b.name) for b in blocks]

