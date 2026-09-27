from sqlalchemy import Column, BigInteger, Text, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class WeatherObservation(Base):
    """
    SQLAlchemy model for Panchayat-level Weather Observations (Phase 1.6 Canonical Schema).
    """
    __tablename__ = "weather_observations"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    panchayat_id = Column(BigInteger, ForeignKey("panchayats.id", ondelete="RESTRICT"), nullable=False, index=True)
    lgd_code = Column(BigInteger, nullable=False, index=True)
    station_id = Column(Text, nullable=True, index=True)
    observation_date = Column(Date, nullable=False, index=True)
    actual_rainfall_mm = Column(Numeric, nullable=True)
    station_distance_km = Column(Numeric, nullable=True)
    
    # Phase 1.6 Canonical Weather Attributes
    forecast_issue_date = Column(Date, nullable=True, index=True)
    lead_days = Column(BigInteger, default=0, nullable=True)
    block_forecast_rainfall_mm = Column(Numeric, nullable=True)
    station_latitude = Column(Numeric, nullable=True)
    station_longitude = Column(Numeric, nullable=True)
    source_dataset = Column(Text, nullable=True, index=True)
    source_file = Column(Text, nullable=True)
    source_row_id = Column(BigInteger, nullable=True)
    source_panchayat_id = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    panchayat = relationship("Panchayat", back_populates="weather_observations")

    __table_args__ = (
        UniqueConstraint("panchayat_id", "observation_date", name="uq_weather_observations"),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherObservation(id={self.id}, panchayat_id={self.panchayat_id}, "
            f"date={self.observation_date}, rainfall_mm={self.actual_rainfall_mm})>"
        )

