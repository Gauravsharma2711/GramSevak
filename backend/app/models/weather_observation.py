from sqlalchemy import Column, BigInteger, Text, Numeric, Date, DateTime, UniqueConstraint, func
from backend.app.core.database import Base


class WeatherObservation(Base):
    """
    SQLAlchemy model for Panchayat-level Weather Observations.
    """
    __tablename__ = "weather_observations"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    panchayat_id = Column(BigInteger, nullable=False, index=True)
    lgd_code = Column(BigInteger, nullable=False, index=True)
    station_id = Column(Text, nullable=True, index=True)
    observation_date = Column(Date, nullable=False, index=True)
    actual_rainfall_mm = Column(Numeric, nullable=True)
    station_distance_km = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("panchayat_id", "observation_date", name="uq_weather_observations"),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherObservation(id={self.id}, panchayat_id={self.panchayat_id}, "
            f"date={self.observation_date}, rainfall_mm={self.actual_rainfall_mm})>"
        )
