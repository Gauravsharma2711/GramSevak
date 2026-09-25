"""
Pydantic Schemas for Panchayat API responses and queries.
Ensures strict validation, serialization, and clean OpenAPI documentation
without leaking database internals, credentials, or unused fields.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PanchayatItem(BaseModel):
    """
    Schema representing a single Gram Panchayat in Nashik district.
    Contains geo-spatial and administrative identifiers required for downscaling.
    """
    model_config = ConfigDict(from_attributes=True)

    panchayat_id: int = Field(
        ...,
        description="Unique system Panchayat identifier",
        examples=[1001],
    )
    lgd_code: int = Field(
        ...,
        description="Official Local Government Directory (LGD) Panchayat Code",
        examples=[182597],
    )
    panchayat_name: str = Field(
        ...,
        description="Name of the Gram Panchayat",
        examples=["Ajmer Saundane"],
    )
    block_name: str = Field(
        ...,
        description="Administrative Tehsil / Block name",
        examples=["Baglan"],
    )
    district_name: str = Field(
        ...,
        description="District name (Nashik)",
        examples=["Nashik"],
    )
    latitude: float = Field(
        ...,
        description="Geographical latitude in decimal degrees (WGS84)",
        examples=[20.6385],
    )
    longitude: float = Field(
        ...,
        description="Geographical longitude in decimal degrees (WGS84)",
        examples=[74.1201],
    )
    elevation_m: float = Field(
        ...,
        description="Elevation above mean sea level in meters",
        examples=[585.0],
    )


class PanchayatDetailResponse(PanchayatItem):
    """
    Response schema for a single Gram Panchayat detail lookup.
    Inherits all core metadata fields from PanchayatItem.
    """
    pass


class PanchayatPagination(BaseModel):
    """
    Paginated response envelope for Panchayats list.
    """
    total: int = Field(
        ...,
        description="Total number of Panchayats matching the criteria",
        examples=[1388],
    )
    page: int = Field(
        ...,
        description="Current page number (1-indexed)",
        examples=[1],
    )
    page_size: int = Field(
        ...,
        description="Number of items per page",
        examples=[50],
    )
    total_pages: int = Field(
        ...,
        description="Total number of available pages",
        examples=[28],
    )
    items: List[PanchayatItem] = Field(
        ...,
        description="List of Panchayats for the current page",
    )


class DistrictItem(BaseModel):
    """Schema representing an administrative District."""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Unique District identifier", examples=[1])
    name: str = Field(..., description="District Name", examples=["Nashik", "Pune"])
    state: str = Field("Maharashtra", description="State", examples=["Maharashtra"])


class BlockItem(BaseModel):
    """Schema representing an administrative Block / Tehsil."""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Unique Block identifier", examples=[1])
    district_id: int = Field(..., description="Parent District identifier", examples=[1])
    name: str = Field(..., description="Block Name", examples=["Baglan", "Haveli"])

