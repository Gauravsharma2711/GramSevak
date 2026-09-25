from sqlalchemy import Column, BigInteger, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Block(Base):
    """
    SQLAlchemy model for administrative Block / Tehsil / Taluka.
    """
    __tablename__ = "blocks"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    district_id = Column(BigInteger, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(Text, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    district = relationship("District", back_populates="blocks")
    panchayats = relationship("Panchayat", back_populates="block")

    __table_args__ = (
        UniqueConstraint("district_id", "name", name="uq_blocks_district_name"),
    )

    def __repr__(self) -> str:
        return f"<Block(id={self.id}, name='{self.name}', district_id={self.district_id})>"
