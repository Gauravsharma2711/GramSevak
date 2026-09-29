"""
API v1 Location Intelligence & Panchayat Resolution Endpoints (Phase 6.1).

Provides optional GPS-based Gram Panchayat resolution using backend PostGIS
point-in-polygon queries against authoritative boundary polygons.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.location import (
    LocationResolveRequest,
    LocationResolveResponse,
)
from backend.services.location_service import (
    LocationResolutionService,
    get_location_service,
    InvalidCoordinatesError,
    GeospatialLookupError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/location/resolve-panchayat",
    response_model=LocationResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve GPS Coordinates to Authoritative Gram Panchayat",
    description="""
    Resolves client-provided device GPS coordinates to an authoritative Gram Panchayat using
    server-side PostGIS point-in-polygon boundary queries.

    Key Invariants:
    - **GPS is Strictly Optional**: If resolution is unavailable or yields no match, client
      must fall back to manual District → Block → Panchayat selection.
    - **Zero Synthetic Geometry**: No centroids or nearest-neighbor extrapolations are used.
    - **Privacy Guaranteed**: Coordinates are evaluated strictly in-memory and never stored.
    - **Authoritative Hierarchy**: Returns official LGD code, Panchayat ID, District, and Block.
    """,
    responses={
        200: {
            "description": "Resolution evaluated. Check `matched` flag and `status` field.",
            "model": LocationResolveResponse,
        },
        400: {
            "description": "Invalid coordinates (out of bounds or non-numeric).",
        },
        422: {
            "description": "Pydantic payload schema validation failure.",
        },
        500: {
            "description": "Geospatial engine failure (sanitized; database details suppressed).",
        },
    },
    tags=["Location Intelligence"],
)
def resolve_panchayat_from_coordinates(
    payload: LocationResolveRequest,
    db: Session = Depends(get_db),
    service: LocationResolutionService = Depends(get_location_service),
) -> LocationResolveResponse:
    """
    HTTP POST handler to resolve device coordinates to an authoritative Panchayat.
    """
    try:
        result = service.resolve_panchayat_by_coordinates(
            latitude=payload.latitude,
            longitude=payload.longitude,
            gps_accuracy_m=payload.gps_accuracy_m,
            db=db,
        )
        return result
    except InvalidCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except GeospatialLookupError as exc:
        logger.error(f"Geospatial resolution failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Geospatial location resolution service is currently unavailable. Please use manual selection.",
        )
    except Exception as exc:
        logger.error(f"Unexpected error in resolve_panchayat_from_coordinates: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process location resolution. Please use manual selection.",
        )
