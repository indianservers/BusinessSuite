from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Numeric, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class BackgroundVerificationVendor(Base):
    __tablename__ = "background_verification_vendors"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_bgv_vendor_company_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, default=1, server_default="1", index=True)
    name = Column(String(150), nullable=False)
    contact_email = Column(String(150))
    provider_code = Column(String(80))
    api_base_url = Column(String(500))
    api_key_ref = Column(String(200))
    webhook_secret_ref = Column(String(200))
    supports_api_submission = Column(String(10), default="No")
    status = Column(String(30), default="Active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BackgroundVerificationRequest(Base):
    __tablename__ = "background_verification_requests"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("background_verification_vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    package_name = Column(String(120), nullable=False)
    status = Column(String(30), default="Initiated", index=True)
    vendor_status = Column(String(80))
    initiated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    initiated_at = Column(DateTime(timezone=True), server_default=func.now())
    consent_status = Column(String(30), default="Pending", index=True)
    consent_captured_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True))
    expected_completion_date = Column(Date)
    completed_at = Column(DateTime(timezone=True))
    overall_result = Column(String(30))
    vendor_reference = Column(String(120))
    report_url = Column(String(500))
    consent_url = Column(String(500))
    remarks = Column(Text)
    purpose = Column(String(80), default="Employment verification")
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    version = Column(Integer, nullable=False, default=1, server_default="1")

    vendor = relationship("BackgroundVerificationVendor")
    candidate = relationship("Candidate")
    employee = relationship("Employee")
    owner = relationship("User", foreign_keys=[owner_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    checks = relationship("BackgroundVerificationCheck", back_populates="request", cascade="all, delete-orphan", order_by="BackgroundVerificationCheck.id")
    events = relationship("BackgroundVerificationConnectorEvent", back_populates="request", cascade="all, delete-orphan")

    @property
    def owner_name(self):
        return self.owner.email if self.owner else None

    @property
    def reviewer_name(self):
        return self.reviewer.email if self.reviewer else None


class BackgroundVerificationCheck(Base):
    __tablename__ = "background_verification_checks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("background_verification_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type = Column(String(80), nullable=False, index=True)  # Identity, Education, Employment, Address, Criminal
    status = Column(String(30), default="Pending", index=True)
    result = Column(String(30))
    score = Column(Numeric(5, 2))
    document_url = Column(String(500))
    employee_document_id = Column(Integer, ForeignKey("employee_documents.id", ondelete="RESTRICT"), nullable=True)
    verified_by = Column(String(150))
    verified_at = Column(DateTime(timezone=True))
    remarks = Column(Text)

    request = relationship("BackgroundVerificationRequest", back_populates="checks")


class BackgroundVerificationConnectorEvent(Base):
    __tablename__ = "background_verification_connector_events"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("background_verification_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("background_verification_vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    vendor_reference = Column(String(120), index=True)
    payload_json = Column(JSON, nullable=False)
    processing_status = Column(String(30), default="Processed", index=True)
    error_message = Column(Text)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    request = relationship("BackgroundVerificationRequest", back_populates="events")
    vendor = relationship("BackgroundVerificationVendor")
