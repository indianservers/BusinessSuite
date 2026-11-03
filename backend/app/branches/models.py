from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index, JSON, UniqueConstraint, event
from sqlalchemy.sql import func
from app.db.base_class import Base


class BranchPolicy(Base):
    __tablename__ = "suite_branch_policies"
    __table_args__ = (UniqueConstraint("company_id", "user_id"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    all_branches = Column(Boolean, nullable=False, default=False)
    manage_access = Column(Boolean, nullable=False, default=False)
    use_home_branch = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)


class BranchLifecycle(Base):
    """Recovery metadata only. Branch records, grants and business data stay in place."""
    __tablename__ = "suite_branch_lifecycle"
    branch_id = Column(Integer, ForeignKey("branches.id"), primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    protected_at = Column(DateTime(timezone=True), nullable=True)
    protected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    retain_until = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=0)


class BranchGrant(Base):
    __tablename__ = "suite_branch_grants"
    __table_args__ = (UniqueConstraint("company_id", "user_id", "branch_id"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    can_write = Column(Boolean, nullable=False, default=False)
    # NULL inherits the company role; an object is an explicit module whitelist.
    module_grants = Column(JSON, nullable=True)


class AccountingBranchMap(Base):
    __tablename__ = "suite_accounting_branch_map"
    # FAM is optional; the administration service validates this external ID.
    accounting_branch_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)


class BranchOwnership(Base):
    """Indexed ownership for legacy roots; no guessing from a creator's branch.

    Composite keys are encoded from the model's ordered primary key columns.
    This extends the suite's existing resource-ownership approach without adding
    hundreds of nullable columns to unrelated/reference tables.
    """
    __tablename__ = "suite_branch_ownership"
    resource_table = Column(String(120), primary_key=True)
    resource_key = Column(String(500), primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    source = Column(String(80), nullable=False)
    __table_args__ = (Index("ix_suite_branch_owner_scope", "company_id", "branch_id", "resource_table", "resource_key"),)


class BranchAudit(Base):
    __tablename__ = "suite_branch_audit"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation = Column(String(80), nullable=False)
    reason = Column(Text, nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BranchRecordShare(Base):
    __tablename__ = "suite_branch_record_shares"
    company_id = Column(Integer, ForeignKey("companies.id"), primary_key=True)
    resource_table = Column(String(120), primary_key=True)
    resource_key = Column(String(500), primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), primary_key=True)
    __table_args__ = (Index("ix_suite_branch_share_scope", "company_id", "branch_id", "resource_table", "resource_key"),)


@event.listens_for(BranchAudit, "before_update")
@event.listens_for(BranchAudit, "before_delete")
def immutable_branch_audit(*args):
    raise ValueError("Branch audit events are append-only")
