from sqlalchemy import Column, Text, Numeric, DateTime, func
from backend.app.core.database import Base


class StationMetadata(Base):
    """
    SQLAlchemy model for Weather Station Metadata.
    """
    __tablename__ = "station_metadata"

    station_id = Column(Text, primary_key=True, index=True)
    station_name = Column(Text, nullable=True)
    latitude = Column(Numeric, nullable=True)
    longitude = Column(Numeric, nullable=True)
    district_name = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<StationMetadata(station_id='{self.station_id}', name='{self.station_name}')>"
