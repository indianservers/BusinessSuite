from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Numeric, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class BackgroundVerificationVendor(Base):
    __tablename__ = "background_verification_vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
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

    vendor = relationship("BackgroundVerificationVendor")
    candidate = relationship("Candidate")
    employee = relationship("Employee")
    checks = relationship("BackgroundVerificationCheck", back_populates="request", cascade="all, delete-orphan", order_by="BackgroundVerificationCheck.id")
    events = relationship("BackgroundVerificationConnectorEvent", back_populates="request", cascade="all, delete-orphan")


class BackgroundVerificationCheck(Base):
    __tablename__ = "background_verification_checks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("background_verification_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type = Column(String(80), nullable=False, index=True)  # Identity, Education, Employment, Address, Criminal
    status = Column(String(30), default="Pending", index=True)
    result = Column(String(30))
    score = Column(Numeric(5, 2))
    document_url = Column(String(500))
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
