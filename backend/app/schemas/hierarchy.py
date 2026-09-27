"""
Administrative Hierarchy Schemas (Phase 3.3).

Provides canonical Pydantic request and response schemas for:
- Districts
- Blocks (Tehsils)
- Panchayats

Follows clean REST collection and detail conventions while maintaining complete
backward compatibility with existing Panchayat schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.app.schemas.panchayat import (
    DistrictResponse,
    DistrictItem,
    DistrictListResponse,
    BlockResponse,
    BlockItem,
    BlockListResponse,
    PanchayatResponse,
    BlockPanchayatItem,
    PanchayatListResponse,
    BlockPanchayatPagination,
    PanchayatDetailResponse,
)

__all__ = [
    "DistrictResponse",
    "DistrictItem",
    "DistrictListResponse",
    "BlockResponse",
    "BlockItem",
    "BlockListResponse",
    "PanchayatResponse",
    "BlockPanchayatItem",
    "PanchayatListResponse",
    "BlockPanchayatPagination",
    "PanchayatDetailResponse",
]
