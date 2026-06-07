from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class AdminProfile(Base):
    __tablename__ = "admin_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    description = Column(Text)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AdminProfilePermission(Base):
    __tablename__ = "admin_profile_permissions"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("admin_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_name = Column(String(120), nullable=False, index=True)
    allowed = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("profile_id", "permission_name", name="uq_admin_profile_permission"),)


class AdminRole(Base):
    __tablename__ = "admin_roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    description = Column(Text)
    profile_id = Column(Integer, ForeignKey("admin_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AdminRoleHierarchy(Base):
    __tablename__ = "admin_role_hierarchy"
    id = Column(Integer, primary_key=True, index=True)
    parent_role_id = Column(Integer, ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    child_role_id = Column(Integer, ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("parent_role_id", "child_role_id", name="uq_admin_role_hierarchy"),)


class AdminFieldSecurity(Base):
    __tablename__ = "admin_field_security"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    field_name = Column(String(120), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("admin_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    can_view = Column(Boolean, default=True, index=True)
    can_edit = Column(Boolean, default=True, index=True)
    mask_value = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("module_name", "field_name", "profile_id", name="uq_admin_field_security"),)


class AdminRecordSharingRule(Base):
    __tablename__ = "admin_record_sharing_rules"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    rule_name = Column(String(160), nullable=False)
    condition_json = Column(JSON)
    share_with_type = Column(String(40), nullable=False, index=True)
    share_with_id = Column(Integer, nullable=False, index=True)
    access_level = Column(String(20), default="read", index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminManualRecordShare(Base):
    __tablename__ = "admin_manual_record_shares"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    share_with_type = Column(String(40), nullable=False, index=True)
    share_with_id = Column(Integer, nullable=False, index=True)
    access_level = Column(String(20), default="read", index=True)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("module_name", "record_id", "share_with_type", "share_with_id", name="uq_admin_manual_share"),)


class AdminDataSharingRule(Base):
    __tablename__ = "admin_data_sharing_rules"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    rule_json = Column(JSON)
    access_level = Column(String(20), default="read")
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminIPRestriction(Base):
    __tablename__ = "admin_ip_restrictions"
    id = Column(Integer, primary_key=True, index=True)
    cidr = Column(String(80), nullable=False, index=True)
    action = Column(String(20), default="allow", index=True)
    description = Column(String(255))
    active = Column(Boolean, default=True, index=True)
    environment_safe = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    module_name = Column(String(100), index=True)
    resource_type = Column(String(100), index=True)
    resource_id = Column(Integer, index=True)
    status = Column(String(30), default="completed", index=True)
    detail_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdminImportJob(Base):
    __tablename__ = "admin_import_jobs"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    filename = Column(String(240), nullable=False)
    status = Column(String(30), default="uploaded", index=True)
    total_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    mapping_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class AdminImportJobRow(Base):
    __tablename__ = "admin_import_job_rows"
    id = Column(Integer, primary_key=True, index=True)
    import_job_id = Column(Integer, ForeignKey("admin_import_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    raw_json = Column(JSON)
    mapped_json = Column(JSON)
    status = Column(String(30), default="pending", index=True)
    error_message = Column(Text)


class AdminDuplicateRule(Base):
    __tablename__ = "admin_duplicate_rules"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    match_fields_json = Column(JSON)
    match_logic = Column(String(40), default="any")
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminDuplicateCandidate(Base):
    __tablename__ = "admin_duplicate_candidates"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("admin_duplicate_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    duplicate_record_id = Column(Integer, nullable=False, index=True)
    confidence_score = Column(Integer, default=0)
    status = Column(String(30), default="open", index=True)
    evidence_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminMergeLog(Base):
    __tablename__ = "admin_merge_logs"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    winner_record_id = Column(Integer, nullable=False)
    loser_record_ids_json = Column(JSON)
    merged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    detail_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminExportControl(Base):
    __tablename__ = "admin_export_controls"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    max_rows = Column(Integer, default=1000)
    require_approval = Column(Boolean, default=False)
    watermark = Column(Boolean, default=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminBackupRequest(Base):
    __tablename__ = "admin_backup_requests"
    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(100), default="crm")
    status = Column(String(30), default="requested", index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    detail_json = Column(JSON)


class AdminComplianceSetting(Base):
    __tablename__ = "admin_compliance_settings"
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(120), unique=True, nullable=False, index=True)
    setting_value_json = Column(JSON)
    active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminDataRetentionRule(Base):
    __tablename__ = "admin_data_retention_rules"
    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    retention_days = Column(Integer, nullable=False)
    action = Column(String(40), default="archive")
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
