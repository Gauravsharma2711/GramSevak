from sqlalchemy import Column, BigInteger, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class PanchayatBoundary(Base):
    """
    SQLAlchemy model for Gram Panchayat administrative polygon boundary.
    Stores PostGIS polygon geometry separately from core Panchayat tabular metadata.
    """
    __tablename__ = "panchayat_boundaries"

    id = Column(BigInteger, primary_key=True, index=True)
    panchayat_id = Column(
        BigInteger,
        ForeignKey("panchayats.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # PostGIS geometry stored as Geometry(Geometry, 4326) in PostgreSQL
    # Handled via raw SQL / PostGIS ST_Contains/ST_Point queries for maximum portability
    source = Column(Text, nullable=False, default="AUTHORITATIVE_LGD")
    properties = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    panchayat = relationship("Panchayat", back_populates="boundary")

    def __repr__(self) -> str:
        return f"<PanchayatBoundary(id={self.id}, panchayat_id={self.panchayat_id}, source='{self.source}')>"
