from sqlalchemy import Column, BigInteger, Text, DateTime, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class District(Base):
    """
    SQLAlchemy model for administrative District.
    """
    __tablename__ = "districts"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    name = Column(Text, unique=True, nullable=False, index=True)
    state = Column(Text, nullable=False, default="Maharashtra")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    blocks = relationship("Block", back_populates="district", cascade="all, delete-orphan")
    panchayats = relationship("Panchayat", back_populates="district")

    def __repr__(self) -> str:
        return f"<District(id={self.id}, name='{self.name}', state='{self.state}')>"
