from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class PayrollLegalEntity(Base):
    __tablename__ = "payroll_legal_entities"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    legal_name = Column(String(200), nullable=False)
    registered_address = Column(Text)
    state = Column(String(100))
    city = Column(String(100))
    pincode = Column(String(20))
    pan = Column(String(20))
    tan = Column(String(20))
    cin = Column(String(30))
    gstin = Column(String(30))
    pf_establishment_code = Column(String(50))
    esi_employer_code = Column(String(50))
    pt_registration_number = Column(String(80))
    lwf_registration_number = Column(String(80))
    signatory_name = Column(String(120))
    signatory_designation = Column(String(120))
    logo_url = Column(String(500))
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Form16Document(Base):
    __tablename__ = "form16_documents"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    part_a_url = Column(String(500))
    part_b_url = Column(String(500))
    combined_pdf_url = Column(String(500))
    taxable_income = Column(Numeric(14, 2), default=0)
    tax_deducted = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Draft", index=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    remarks = Column(Text)

    legal_entity = relationship("PayrollLegalEntity")
    employee = relationship("Employee")


class Form16Record(Base):
    __tablename__ = "form16_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    part_a_file_path = Column(String(500))
    part_b_file_path = Column(String(500))
    combined_file_path = Column(String(500))
    signed_file_path = Column(String(500))
    signature_status = Column(String(30), nullable=False, default="pending")
    signed_sha256 = Column(String(64))
    signature_evidence_json = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    status = Column(String(30), default="draft", index=True)
    taxable_income = Column(Numeric(14, 2), default=0)
    tax_deducted = Column(Numeric(14, 2), default=0)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))

    employee = relationship("Employee")


class TDSReturnFiling(Base):
    __tablename__ = "tds_return_filings"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    quarter = Column(String(10), nullable=False, index=True)  # Q1, Q2, Q3, Q4
    form_type = Column(String(20), default="24Q", index=True)
    due_date = Column(Date)
    status = Column(String(30), default="Draft", index=True)
    return_file_url = Column(String(500))
    fvu_file_url = Column(String(500))
    acknowledgement_number = Column(String(100))
    filed_at = Column(DateTime(timezone=True))
    filed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    total_tax_deducted = Column(Numeric(14, 2), default=0)
    remarks = Column(Text)

    legal_entity = relationship("PayrollLegalEntity")


class StatutoryPortalSubmission(Base):
    __tablename__ = "statutory_portal_submissions"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    portal_type = Column(String(30), nullable=False, index=True)  # EPFO, ESIC
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    submission_type = Column(String(50), nullable=False)  # ECR, ESIC_CHALLAN
    due_date = Column(Date)
    status = Column(String(30), default="Draft", index=True)
    upload_file_url = Column(String(500))
    challan_file_url = Column(String(500))
    acknowledgement_number = Column(String(100))
    payment_reference = Column(String(100))
    total_amount = Column(Numeric(14, 2), default=0)
    submitted_at = Column(DateTime(timezone=True))
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks = Column(Text)

    legal_entity = relationship("PayrollLegalEntity")


class StatutoryComplianceEvent(Base):
    __tablename__ = "statutory_compliance_events"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    compliance_type = Column(String(40), nullable=False, index=True)  # PF, ESI, PT, TDS
    period_month = Column(Integer)
    period_year = Column(Integer)
    financial_year = Column(String(20))
    due_date = Column(Date, nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="Open", index=True)
    source_entity_type = Column(String(80))
    source_entity_id = Column(Integer)
    alert_status = Column(String(30), default="Pending")
    reminder_sent_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    legal_entity = relationship("PayrollLegalEntity")
