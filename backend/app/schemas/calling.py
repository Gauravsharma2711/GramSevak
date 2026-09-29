"""
Pydantic schemas for Phase 6.4 Advisory Voice Calling.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AdvisoryCallRequest(BaseModel):
    """Payload to dispatch an optional advisory voice call."""
    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Recipient mobile phone number (Indian mobile format: +91XXXXXXXXXX or 10 digits)",
        examples=["+919876543210"],
    )
    language: Optional[str] = Field(
        "en",
        description="Requested language for speech articulation ('en', 'mr', 'hi')",
        examples=["mr"],
    )
    farmer_id: Optional[str] = Field(
        None,
        description="Optional farmer identity for audit correlation",
        examples=["farmer_kisan_01"],
    )


class AdvisoryCallResponse(BaseModel):
    """Response confirming voice call initiation."""
    success: bool
    status: str
    phone_number: str
    advisory_id: int
    call_id: Optional[str] = None
    message: str
    error_message: Optional[str] = None
