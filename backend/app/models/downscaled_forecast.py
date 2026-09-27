from sqlalchemy import Column, BigInteger, Text, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class DownscaledForecast(Base):
    """
    SQLAlchemy Model for the 'downscaled_forecasts' table in Supabase PostgreSQL.
    Stores ML model predictions, confidence levels, model versions, and comparison metrics.
    """
    __tablename__ = "downscaled_forecasts"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, nullable=False)
    panchayat_id = Column(BigInteger, ForeignKey("panchayats.id", ondelete="RESTRICT"), index=True, nullable=False)
    forecast_date = Column(Date, nullable=True, index=True)
    forecast_issue_date = Column(Date, nullable=True)
    block_forecast_rainfall_mm = Column(Numeric, nullable=True)
    downscaled_rainfall_mm = Column(Numeric, nullable=True)
    actual_rainfall_mm = Column(Numeric, nullable=True)
    model_name = Column(Text, nullable=True)
    model_version = Column(Text, nullable=True)
    # Note: confidence is nullable. Kept null in Day 4 to avoid arbitrary percentages.
    # TODO (Day 5+): Implement defensible uncertainty/confidence calibration based on historical model residuals (e.g. Conformal Prediction or quantile error distributions).
    confidence = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    panchayat = relationship("Panchayat", back_populates="downscaled_forecasts")

    def __repr__(self) -> str:
        return (
            f"<DownscaledForecast(id={self.id}, panchayat_id={self.panchayat_id}, "
            f"forecast_date={self.forecast_date}, "
            f"downscaled_rainfall={self.downscaled_rainfall_mm}, "
            f"model={self.model_name})>"
        )
