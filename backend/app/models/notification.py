"""
SQLAlchemy models for Phase 6.2 Panchayat Location Alerts and Notifications.
"""

from sqlalchemy import Column, BigInteger, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class FarmerDevice(Base):
    """
    Registered farmer client device token associated with an authoritative Gram Panchayat.
    Privacy Guarantee: No precise farmer GPS coordinates or user identities are stored.
    """
    __tablename__ = "farmer_devices"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    device_token = Column(Text, unique=True, nullable=False, index=True)
    panchayat_id = Column(
        BigInteger,
        ForeignKey("panchayats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_platform = Column(Text, nullable=False, default="android")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    panchayat = relationship("Panchayat")
    deliveries = relationship("NotificationDelivery", back_populates="target_device", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FarmerDevice(id={self.id}, panchayat_id={self.panchayat_id}, active={self.is_active})>"


class NotificationEvent(Base):
    """
    Location-scoped notification event generated exclusively from an approved advisory revision.
    Idempotency Guarantee: `idempotency_key` ensures zero duplicate events across retries.
    """
    __tablename__ = "notification_events"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    idempotency_key = Column(Text, unique=True, nullable=False, index=True)
    advisory_id = Column(
        BigInteger,
        ForeignKey("advisories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    advisory_version = Column(Integer, nullable=False)
    panchayat_id = Column(
        BigInteger,
        ForeignKey("panchayats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_id = Column(BigInteger, nullable=True)
    alert_category = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="PENDING", index=True)
    target_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    published_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    advisory = relationship("Advisory")
    panchayat = relationship("Panchayat")
    deliveries = relationship("NotificationDelivery", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<NotificationEvent(id={self.id}, key='{self.idempotency_key}', "
            f"category='{self.alert_category}', severity='{self.severity}', status='{self.status}')>"
        )


class NotificationDelivery(Base):
    """
    Individual device delivery attempt record for auditability, idempotency, and safe retries.
    """
    __tablename__ = "notification_deliveries"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    event_id = Column(
        BigInteger,
        ForeignKey("notification_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_device_id = Column(
        BigInteger,
        ForeignKey("farmer_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(Text, nullable=False, default="PENDING", index=True)
    attempt_count = Column(Integer, nullable=False, default=1)
    last_attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("NotificationEvent", back_populates="deliveries")
    target_device = relationship("FarmerDevice", back_populates="deliveries")

    __table_args__ = (
        UniqueConstraint("event_id", "target_device_id", name="uq_notification_delivery_event_target"),
    )

    @property
    def device_id(self) -> int:
        return self.target_device_id

    @property
    def delivery_status(self) -> str:
        return self.status

    def __repr__(self) -> str:
        return f"<NotificationDelivery(id={self.id}, event_id={self.event_id}, status='{self.status}')>"
