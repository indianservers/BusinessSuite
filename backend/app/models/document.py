from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, DateTime, Text, JSON, LargeBinary, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class StudioAsset(Base):
    __tablename__ = "document_studio_assets"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    content_type = Column(String(80), nullable=False)
    content = Column(LargeBinary, nullable=False)
    sha256 = Column(String(64), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudioLetterhead(Base):
    __tablename__ = "document_studio_letterheads"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    header_text = Column(Text, nullable=False, default="")
    footer_text = Column(Text, nullable=False, default="")
    accent_color = Column(String(7), nullable=False, default="#173b56")
    show_company_header = Column(Boolean, nullable=False, default=True)
    logo_asset_id = Column(Integer, ForeignKey("document_studio_assets.id"))
    background_asset_id = Column(Integer, ForeignKey("document_studio_assets.id"))
    signature_asset_id = Column(Integer, ForeignKey("document_studio_assets.id"))
    signatory_name = Column(String(150), nullable=False, default="")
    signatory_title = Column(String(150), nullable=False, default="Authorized Signatory")
    top_margin_mm = Column(Integer, nullable=False, default=44)
    bottom_margin_mm = Column(Integer, nullable=False, default=25)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudioTemplate(Base):
    __tablename__ = "document_studio_templates"
    __table_args__ = (UniqueConstraint("organization_id", "starter_key", name="uq_studio_template_starter"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    document_type = Column(String(80), nullable=False)
    kind = Column(String(20), nullable=False)
    orientation = Column(String(20), nullable=False, default="portrait")
    recipient_scope = Column(String(20), nullable=False, default="both")
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    custom_fields = Column(JSON, nullable=False, default=list)
    letterhead_id = Column(Integer, ForeignKey("document_studio_letterheads.id"))
    starter_key = Column(String(60))
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudioDocument(Base):
    __tablename__ = "document_studio_documents"
    __table_args__ = (UniqueConstraint("organization_id", "request_key", name="uq_studio_document_request"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    reference = Column(String(60), nullable=False, unique=True)
    template_id = Column(Integer, ForeignKey("document_studio_templates.id", ondelete="SET NULL"))
    template_version = Column(Integer, nullable=False)
    recipient_type = Column(String(20), nullable=False)
    recipient_id = Column(Integer, nullable=False, index=True)
    recipient_name = Column(String(250), nullable=False)
    title = Column(String(250), nullable=False)
    document_type = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="Issued")
    issue_date = Column(Date, nullable=False)
    snapshot = Column(JSON, nullable=False)
    request_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    issued_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    revoked_at = Column(DateTime(timezone=True))
    revoke_reason = Column(Text)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, default=1, server_default='1', index=True)
    name = Column(String(200), nullable=False)
    template_type = Column(String(50))  # Offer Letter, Appointment, Experience, Relieving, Payslip, etc.
    description = Column(Text)
    content = Column(Text)  # HTML/Jinja2 template
    variables = Column(Text)  # JSON list of available variables
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("document_templates.id", ondelete="SET NULL"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(100))
    document_name = Column(String(200))
    file_url = Column(String(500))
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_signed = Column(Boolean, default=False)
    signed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CompanyPolicy(Base):
    __tablename__ = "company_policies"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, default=1, server_default='1', index=True)
    title = Column(String(300), nullable=False)
    category = Column(String(100))  # HR, IT, Finance, Legal
    content = Column(Text)
    document_url = Column(String(500))
    version = Column(String(20), default="1.0")
    effective_date = Column(DateTime(timezone=True))
    is_published = Column(Boolean, default=False)
    require_acknowledgement = Column(Boolean, default=False)
    embedding_data = Column(Text)  # AI embeddings for Q&A

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CompanyPolicyVersion(Base):
    __tablename__ = "company_policy_versions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("company_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    content = Column(Text)
    document_url = Column(String(500))
    effective_date = Column(DateTime(timezone=True))
    change_summary = Column(Text)
    published_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = Column(DateTime(timezone=True), server_default=func.now())

    policy = relationship("CompanyPolicy")


class EmployeeCertificate(Base):
    __tablename__ = "employee_certificates"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # Study, Class, Old Company, Professional, Other
    certificate_type = Column(String(100), nullable=False)
    title = Column(String(250), nullable=False)
    issuing_entity = Column(String(250))
    issuing_entity_type = Column(String(50))  # School, College, University, Previous Employer, Institute
    class_or_grade = Column(String(80))
    course_or_program = Column(String(200))
    certificate_number = Column(String(120))
    issue_date = Column(Date)
    expiry_date = Column(Date)
    file_url = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    content_type = Column(String(120))
    file_size_bytes = Column(Integer)
    verification_status = Column(String(30), default="Pending", index=True)  # Pending, Verified, Rejected
    verified_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verifier_name = Column(String(150))
    verifier_company = Column(String(200))
    verifier_designation = Column(String(150))
    verifier_contact = Column(String(150))
    verified_at = Column(DateTime(timezone=True))
    verification_notes = Column(Text)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee")
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


class CertificateImportExportBatch(Base):
    __tablename__ = "certificate_import_export_batches"

    id = Column(Integer, primary_key=True, index=True)
    operation_type = Column(String(20), nullable=False, index=True)  # Import, Export
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    source_file_url = Column(String(500))
    output_file_url = Column(String(500))
    error_report_url = Column(String(500))
    original_filename = Column(String(255))
    status = Column(String(30), default="Uploaded", index=True)  # Uploaded, Processing, Completed, Failed
    total_records = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    remarks = Column(Text)

    employee = relationship("Employee")
    requester = relationship("User")
