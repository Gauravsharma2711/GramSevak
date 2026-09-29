"""
Farmer Preferences Model (Phase 6.3).

Persists farmer personalization preferences:
- farmer identity
- preferred Panchayat ID
- preferred language
- preference updated timestamp

Privacy & Architecture Invariants:
- Never stores raw GPS coordinates or location history.
- Scoped strictly to authoritative Panchayat administrative IDs.
"""

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.core.database import Base


class FarmerPreference(Base):
    __tablename__ = "farmer_preferences"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        index=True,
        autoincrement=True,
    )
    farmer_id = Column(String(255), unique=True, nullable=False, index=True)
    panchayat_id = Column(
        BigInteger,
        ForeignKey("panchayats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preferred_language = Column(String(10), nullable=False, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    panchayat = relationship("Panchayat", backref="farmer_preferences", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<FarmerPreference(id={self.id}, farmer_id='{self.farmer_id}', "
            f"panchayat_id={self.panchayat_id}, lang='{self.preferred_language}')>"
        )
