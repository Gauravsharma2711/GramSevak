from sqlalchemy import Column, BigInteger, Text, Numeric, Date, DateTime, Integer, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Advisory(Base):
    """
    SQLAlchemy Model for the 'advisories' table in Supabase PostgreSQL.
    Stores deterministic and AI-augmented agricultural advisories linked to downscaled panchayat forecasts,
    with full support for versioning, optimistic concurrency, and officer review lifecycle.
    """
    __tablename__ = "advisories"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, nullable=False)
    panchayat_id = Column(BigInteger, index=True, nullable=False)
    forecast_id = Column(BigInteger, nullable=True)
    forecast_date = Column(Date, nullable=False, index=True)
    rainfall_mm = Column(Numeric, nullable=True)
    rainfall_category = Column(Text, nullable=True)
    severity = Column(Text, nullable=True)
    advisory_title = Column(Text, nullable=True)
    advisory_text = Column(Text, nullable=True)
    rule_version = Column(Text, nullable=True)
    status = Column(Text, default="DRAFT", index=True, nullable=True)
    officer_id = Column(Text, nullable=True)
    officer_comment = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    # Phase 5.6: Versioning, Concurrency, and Content Traceability
    version = Column(Integer, default=1, nullable=False)
    advisory_source = Column(Text, default="DETERMINISTIC_RULES", nullable=True)
    validation_status = Column(Text, default="VALIDATED", nullable=True)
    validation_report = Column(JSON, nullable=True)
    original_content = Column(JSON, nullable=True)
    edited_content = Column(JSON, nullable=True)
    approved_content = Column(JSON, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    # Relationship to audit logs
    audit_logs = relationship("AdvisoryAuditLog", back_populates="advisory", cascade="all, delete-orphan", order_by="AdvisoryAuditLog.id.desc()")

    def __repr__(self) -> str:
        return (
            f"<Advisory(id={self.id}, panchayat_id={self.panchayat_id}, "
            f"forecast_date={self.forecast_date}, severity={self.severity}, "
            f"status={self.status}, version={self.version})>"
        )


class AdvisoryAuditLog(Base):
    """
    SQLAlchemy Model for the 'advisory_audit_logs' table in Supabase PostgreSQL.
    Maintains an immutable historical record of all state transitions, content edits,
    and administrative decisions performed on an agricultural advisory.
    """
    __tablename__ = "advisory_audit_logs"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, nullable=False)
    advisory_id = Column(BigInteger, ForeignKey("advisories.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(Text, nullable=False, index=True)  # GENERATED, VALIDATED, REVIEWED, EDITED, APPROVED, REJECTED, PUBLISHED
    officer_id = Column(Text, nullable=True)
    previous_status = Column(Text, nullable=True)
    new_status = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    advisory = relationship("Advisory", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AdvisoryAuditLog(id={self.id}, advisory_id={self.advisory_id}, "
            f"action={self.action}, officer_id={self.officer_id}, version={self.version})>"
        )
