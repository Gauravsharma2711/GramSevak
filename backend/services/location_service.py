"""
GramSevak Location Resolution Domain Service (Phase 6.1).

Responsible for:
Farmer GPS coordinates -> Validation -> PostGIS Geospatial Lookup -> Authoritative Panchayat Resolution.

Key Architectural Guarantees:
1. GPS is strictly optional: Manual District -> Block -> Panchayat selection remains the primary fallback.
2. Zero geometry invention: Never constructs synthetic boundaries or nearest-neighbor centroids.
3. PostGIS Spatial Indexing: Uses ST_Contains with GiST spatial indexing for O(log N) lookup.
4. Privacy: Farmer coordinates are processed strictly in-memory and never persisted.
5. Authoritative Identity: Resolves strictly to verified Panchayat IDs and LGD codes.
6. Decoupled Service Boundary: Clean separation between domain lookup and HTTP routing.
"""

import math
import logging
from typing import Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.database import SessionLocal
from backend.app.schemas.location import (
    LocationResolutionStatus,
    LocationResolveResponse,
    ResolvedPanchayatItem,
)

logger = logging.getLogger(__name__)

# Accuracy thresholds in meters
ACCURACY_WARNING_THRESHOLD_M = 500.0
ACCURACY_REJECTION_THRESHOLD_M = 2500.0


class LocationServiceError(Exception):
    """Base exception for location service errors."""
    pass


class InvalidCoordinatesError(LocationServiceError):
    """Raised when latitude or longitude are outside valid WGS84 physical ranges."""
    pass


class GeospatialLookupError(LocationServiceError):
    """Raised when the database geospatial query encounters an operational failure."""
    pass


class LocationResolutionService:
    """
    Domain service for resolving GPS coordinates to authoritative Gram Panchayats.
    """

    def validate_coordinates(self, latitude: float, longitude: float) -> None:
        """
        Validates latitude and longitude against WGS84 physical boundaries and finite numeric bounds.
        """
        if latitude is None or longitude is None:
            raise InvalidCoordinatesError("Latitude and longitude must not be null.")

        if not math.isfinite(latitude) or not math.isfinite(longitude):
            raise InvalidCoordinatesError("Coordinates must be finite real numbers.")

        if not (-90.0 <= latitude <= 90.0):
            raise InvalidCoordinatesError(
                f"Latitude {latitude} is out of bounds. Must be between -90.0 and +90.0 degrees."
            )

        if not (-180.0 <= longitude <= 180.0):
            raise InvalidCoordinatesError(
                f"Longitude {longitude} is out of bounds. Must be between -180.0 and +180.0 degrees."
            )

    def resolve_panchayat_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        gps_accuracy_m: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> LocationResolveResponse:
        """
        Resolves (latitude, longitude) to an authoritative Panchayat using PostGIS point-in-polygon.
        
        Args:
            latitude: Device latitude (-90.0 to 90.0)
            longitude: Device longitude (-180.0 to 180.0)
            gps_accuracy_m: Optional horizontal GPS accuracy radius in meters
            db: Optional active SQLAlchemy Session
        
        Returns:
            LocationResolveResponse detailing resolution status, matched Panchayat, and metadata.
        """
        # 1. Validate coordinates
        self.validate_coordinates(latitude, longitude)

        # 2. Check GPS accuracy limits
        accuracy_warning: Optional[str] = None
        if gps_accuracy_m is not None:
            if not math.isfinite(gps_accuracy_m) or gps_accuracy_m < 0.0:
                gps_accuracy_m = None
            elif gps_accuracy_m > ACCURACY_REJECTION_THRESHOLD_M:
                logger.info(
                    f"Rejecting GPS resolution: accuracy radius {gps_accuracy_m:.1f}m exceeds "
                    f"maximum safe threshold of {ACCURACY_REJECTION_THRESHOLD_M:.1f}m."
                )
                return LocationResolveResponse(
                    matched=False,
                    status=LocationResolutionStatus.ACCURACY_TOO_LOW,
                    message=(
                        f"GPS accuracy is too low (radius ±{gps_accuracy_m:.0f}m) to reliably "
                        "determine your Panchayat boundary. Please select your Panchayat manually."
                    ),
                    panchayat=None,
                    accuracy_warning=f"Low accuracy radius: ±{gps_accuracy_m:.0f}m",
                )
            elif gps_accuracy_m > ACCURACY_WARNING_THRESHOLD_M:
                accuracy_warning = (
                    f"GPS accuracy is moderate (±{gps_accuracy_m:.0f}m). "
                    "Please verify that the detected village matches your farm location."
                )

        # 3. Session management
        session_created = False
        if db is None:
            db = SessionLocal()
            session_created = True

        try:
            # 4. Point-in-polygon query using PostGIS ST_Contains and spatial GiST index
            # ST_Point in PostGIS expects (longitude, latitude)
            spatial_query = text("""
                SELECT 
                    p.id AS panchayat_id,
                    p.lgd_code AS lgd_code,
                    p.name AS panchayat_name,
                    p.district_id AS district_id,
                    d.name AS district_name,
                    p.block_id AS block_id,
                    b.name AS block_name,
                    p.latitude AS latitude,
                    p.longitude AS longitude,
                    p.elevation_m AS elevation_m
                FROM panchayat_boundaries pb
                JOIN panchayats p ON p.id = pb.panchayat_id
                LEFT JOIN districts d ON d.id = p.district_id
                LEFT JOIN blocks b ON b.id = p.block_id
                WHERE ST_Contains(pb.boundary, ST_SetSRID(ST_Point(:lng, :lat), 4326))
                LIMIT 2;
            """)

            matches = db.execute(
                spatial_query,
                {"lng": longitude, "lat": latitude},
            ).fetchall()

            if len(matches) == 1:
                row = matches[0]
                panchayat_item = ResolvedPanchayatItem(
                    id=row.panchayat_id,
                    lgd_code=row.lgd_code,
                    name=row.panchayat_name,
                    district_id=row.district_id,
                    district_name=row.district_name,
                    block_id=row.block_id,
                    block_name=row.block_name,
                    latitude=float(row.latitude) if row.latitude is not None else None,
                    longitude=float(row.longitude) if row.longitude is not None else None,
                    elevation_m=float(row.elevation_m) if row.elevation_m is not None else None,
                )
                return LocationResolveResponse(
                    matched=True,
                    status=LocationResolutionStatus.MATCHED,
                    message=(
                        f"Resolved to {row.panchayat_name} Gram Panchayat "
                        f"({row.block_name or 'Block'}, {row.district_name or 'District'})."
                    ),
                    panchayat=panchayat_item,
                    accuracy_warning=accuracy_warning,
                )

            elif len(matches) > 1:
                # Ambiguous boundary: coordinates overlap multiple registered boundaries
                logger.warning(
                    f"Ambiguous boundary intersection at lat={latitude:.4f}, lng={longitude:.4f}. "
                    f"Panchayat IDs: {[m.panchayat_id for m in matches]}"
                )
                return LocationResolveResponse(
                    matched=False,
                    status=LocationResolutionStatus.AMBIGUOUS_MATCH,
                    message=(
                        "Your location falls in a boundary zone between multiple Panchayats. "
                        "Please select your village manually from the hierarchy list."
                    ),
                    panchayat=None,
                    accuracy_warning="Multiple adjacent boundaries matched.",
                )

            else:
                # Zero matches: Distinguish between boundary data missing vs truly outside known boundaries
                boundary_count_query = text("SELECT EXISTS (SELECT 1 FROM panchayat_boundaries LIMIT 1);")
                has_boundaries = db.execute(boundary_count_query).scalar()

                if not has_boundaries:
                    return LocationResolveResponse(
                        matched=False,
                        status=LocationResolutionStatus.BOUNDARY_DATA_UNAVAILABLE,
                        message=(
                            "Authoritative Panchayat boundary datasets are currently being ingested. "
                            "Please use manual District -> Block -> Panchayat selection."
                        ),
                        panchayat=None,
                        accuracy_warning=accuracy_warning,
                    )
                else:
                    return LocationResolveResponse(
                        matched=False,
                        status=LocationResolutionStatus.NO_MATCH,
                        message=(
                            "No Gram Panchayat boundary found matching your current location. "
                            "Please select your Panchayat manually."
                        ),
                        panchayat=None,
                        accuracy_warning=accuracy_warning,
                    )

        except SQLAlchemyError as exc:
            logger.error(f"Geospatial lookup failed in database: {exc}", exc_info=True)
            raise GeospatialLookupError("An error occurred during geospatial boundary lookup.")
        finally:
            if session_created:
                db.close()


def get_location_service() -> LocationResolutionService:
    """FastAPI dependency provider for LocationResolutionService."""
    return LocationResolutionService()
