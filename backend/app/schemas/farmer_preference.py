"""
Pydantic Schemas for Farmer Personalization & Preferences (Phase 6.3).
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class FarmerPreferenceUpdateRequest(BaseModel):
    """
    Request schema to update or set a farmer's preferred Panchayat and language.
    """
    panchayat_id: int = Field(
        ...,
        ge=1,
        description="Authoritative Gram Panchayat ID from the administrative hierarchy",
        examples=[1001],
    )
    preferred_language: str = Field(
        "en",
        description="Farmer preferred language code ('en', 'mr', 'hi')",
        examples=["en"],
    )
    farmer_id: Optional[str] = Field(
        None,
        description="Optional client-supplied farmer ID. If provided, must match authenticated identity.",
        examples=["farmer_device_Nashik_01"],
    )


class FarmerPreferenceResponse(BaseModel):
    """
    Response schema returning authoritative farmer preference details with spatial hierarchy metadata.
    """
    model_config = ConfigDict(from_attributes=True)

    farmer_id: str = Field(..., description="Authenticated unique farmer identity")
    panchayat_id: int = Field(..., description="Authoritative preferred Gram Panchayat ID")
    preferred_language: str = Field(..., description="Preferred language code")
    panchayat_name: str = Field(..., description="Authoritative Gram Panchayat name")
    block_name: str = Field(..., description="Authoritative Block / Taluka name")
    district_name: str = Field(..., description="Authoritative District name")
    updated_at: datetime = Field(..., description="Timestamp of the latest preference update")
    is_valid: bool = Field(True, description="True if preferred Panchayat exists and is active")
    available_languages: List[str] = Field(
        default=["en", "mr", "hi"],
        description="Supported farmer application languages",
    )
