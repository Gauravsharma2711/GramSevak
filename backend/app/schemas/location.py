"""
Pydantic schemas for Phase 6.1 Location Intelligence and Panchayat Resolution.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class LocationResolutionStatus(str, Enum):
    """Authoritative status codes for coordinate-to-Panchayat resolution."""
    MATCHED = "MATCHED"
    NO_MATCH = "NO_MATCH"
    BOUNDARY_DATA_UNAVAILABLE = "BOUNDARY_DATA_UNAVAILABLE"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    ACCURACY_TOO_LOW = "ACCURACY_TOO_LOW"


class LocationResolveRequest(BaseModel):
    """
    Request payload for resolving a farmer's coordinates to an authoritative Panchayat.
    
    Security & Privacy:
    - Coordinates are used strictly in-memory for point-in-polygon resolution.
    - Farmer coordinates are never persisted or logged.
    """
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS84 Latitude in decimal degrees (-90.0 to 90.0)",
        examples=[19.035569],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS84 Longitude in decimal degrees (-180.0 to 180.0)",
        examples=[73.787065],
    )
    gps_accuracy_m: Optional[float] = Field(
        None,
        ge=0.0,
        description="Optional device GPS horizontal accuracy radius in meters",
        examples=[15.0],
    )


class ResolvedPanchayatItem(BaseModel):
    """Authoritative administrative metadata for a matched Gram Panchayat."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal unique Panchayat identifier")
    lgd_code: int = Field(..., description="Official Local Government Directory (LGD) code")
    name: str = Field(..., description="Panchayat name")
    district_id: Optional[int] = Field(None, description="Parent District ID")
    district_name: Optional[str] = Field(None, description="Parent District name")
    block_id: Optional[int] = Field(None, description="Parent Block ID")
    block_name: Optional[str] = Field(None, description="Parent Block name")
    latitude: Optional[float] = Field(None, description="Panchayat reference latitude")
    longitude: Optional[float] = Field(None, description="Panchayat reference longitude")
    elevation_m: Optional[float] = Field(None, description="Panchayat elevation in meters")


class LocationResolveResponse(BaseModel):
    """
    Standardized response for Panchayat coordinate resolution.
    """
    matched: bool = Field(
        ...,
        description="True if coordinates unambiguously resolved to an authoritative Panchayat boundary",
    )
    status: LocationResolutionStatus = Field(
        ...,
        description="Standardized resolution status code",
    )
    message: str = Field(
        ...,
        description="Farmer-friendly explanatory message or fallback guidance",
    )
    panchayat: Optional[ResolvedPanchayatItem] = Field(
        None,
        description="Authoritative Panchayat metadata if matched, else null",
    )
    accuracy_warning: Optional[str] = Field(
        None,
        description="Warning message if GPS accuracy radius is poor or boundary-edge caution is warranted",
    )
