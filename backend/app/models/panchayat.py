from sqlalchemy import Column, BigInteger, Text, Numeric, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Panchayat(Base):
    """
    SQLAlchemy model for normalized Gram Panchayat metadata.
    """
    __tablename__ = "panchayats"

    id = Column(BigInteger, primary_key=True, index=True)
    lgd_code = Column(BigInteger, nullable=False, index=True)
    panchayat_code = Column(Text, nullable=True)
    name = Column(Text, nullable=False, index=True)
    block_id = Column(BigInteger, ForeignKey("blocks.id", ondelete="RESTRICT"), nullable=True, index=True)
    district_id = Column(BigInteger, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=True, index=True)
    latitude = Column(Numeric, nullable=True)
    longitude = Column(Numeric, nullable=True)
    elevation_m = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    district = relationship("District", back_populates="panchayats")
    block = relationship("Block", back_populates="panchayats")
    weather_observations = relationship("WeatherObservation", back_populates="panchayat")
    downscaled_forecasts = relationship("DownscaledForecast", back_populates="panchayat")

    def __repr__(self) -> str:
        return f"<Panchayat(id={self.id}, name='{self.name}', lgd_code={self.lgd_code})>"
