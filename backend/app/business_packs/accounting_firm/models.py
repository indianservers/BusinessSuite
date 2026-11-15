from sqlalchemy import (Column, Integer, String, Text, Date, DateTime, JSON,
    ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, event, inspect, func)
from app.db.base_class import Base


class Scope:
    organization_id = Column(Integer, nullable=False)
    branch_id = Column(Integer, nullable=False)
    pack_context_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def scope_constraints(name):
    return (ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],
        ['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],
        name='fk_accounts_'+name+'_context', ondelete='RESTRICT'),
        UniqueConstraint('id','organization_id','branch_id','pack_context_id',name='uq_accounts_'+name+'_source'))


class AccountsPeriod(Scope, Base):
    __tablename__ = 'business_accounts_periods'
    __table_args__ = (*scope_constraints('period'),
        UniqueConstraint('pack_context_id','engagement_id','starts_on','ends_on',name='uq_accounts_engagement_period'),
        CheckConstraint('starts_on <= ends_on AND due_on >= starts_on',name='ck_accounts_period_dates'),
        CheckConstraint('preparer_employee_id != reviewer_employee_id',name='ck_accounts_independent_staff'),
        CheckConstraint("state IN ('draft','submitted','returned','approved') AND revision > 0 AND work_revision >= 0",name='ck_accounts_period_state'),
        CheckConstraint('(work_revision = 0 AND prepared_by_user_id IS NULL) OR (work_revision > 0 AND prepared_by_user_id IS NOT NULL)',name='ck_accounts_preparation_author'),
        CheckConstraint("state NOT IN ('submitted','approved') OR (work_revision > 0 AND submitted_work_revision IS NOT NULL AND submitted_work_revision = work_revision)",name='ck_accounts_submitted_revision'),
        CheckConstraint("(state = 'approved' AND approved_work_revision IS NOT NULL AND approved_work_revision = work_revision) OR (state != 'approved' AND approved_work_revision IS NULL)",name='ck_accounts_approval_revision'))
    id = Column(Integer, primary_key=True)
    engagement_id = Column(Integer, ForeignKey('srm_engagements.id', ondelete='RESTRICT'), nullable=False)
    client_id = Column(Integer, ForeignKey('crm_companies.id', ondelete='RESTRICT'), nullable=False)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    due_on = Column(Date, nullable=False)
    title = Column(String(200), nullable=False)
    preparer_employee_id = Column(Integer, ForeignKey('employees.id', ondelete='RESTRICT'), nullable=False)
    reviewer_employee_id = Column(Integer, ForeignKey('employees.id', ondelete='RESTRICT'), nullable=False)
    state = Column(String(20), nullable=False, default='draft')
    revision = Column(Integer, nullable=False, default=1)
    work_revision = Column(Integer, nullable=False, default=0)
    work_summary = Column(Text, nullable=False, default='')
    review_reason = Column(Text, nullable=False, default='')
    prepared_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    submitted_work_revision = Column(Integer)
    approved_work_revision = Column(Integer)


class AccountsCommand(Scope, Base):
    __tablename__ = 'business_accounts_commands'
    __table_args__ = (*scope_constraints('command'),
        ForeignKeyConstraint(['period_id','organization_id','branch_id','pack_context_id'],
            ['business_accounts_periods.id','business_accounts_periods.organization_id','business_accounts_periods.branch_id','business_accounts_periods.pack_context_id'],name='fk_accounts_command_period',ondelete='RESTRICT'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key',name='uq_accounts_command_request'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64',name='ck_accounts_command_request'))
    id = Column(Integer, primary_key=True)
    period_id = Column(Integer, nullable=False)
    request_key = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)
    action = Column(String(30), nullable=False)
    reason = Column(Text, nullable=False, default='')
    result = Column(JSON, nullable=False)


@event.listens_for(AccountsPeriod, 'before_update')
def immutable_source(mapper, connection, row):
    if any(inspect(row).attrs[name].history.has_changes() for name in
        ('organization_id','branch_id','pack_context_id','engagement_id','client_id','starts_on','ends_on','created_by','created_at')):
        raise ValueError('Accounts service period source is immutable')


def immutable_command(mapper, connection, row):
    raise ValueError('Accounts review history is immutable')


class AccountsEngagementCommand(Scope, Base):
    """One immutable certificate for a canonical native engagement birth."""
    __tablename__ = 'business_accounts_engagement_commands'
    __table_args__ = (*scope_constraints('engagement_command'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key',name='uq_accounts_engagement_command_request'),
        UniqueConstraint('engagement_id',name='uq_accounts_engagement_command_native'),
        CheckConstraint("action = 'engagement.create' AND length(request_key)=36 AND length(request_sha256)=64 AND length(source_sha256)=64",name='ck_accounts_engagement_command_values'))
    id = Column(Integer,primary_key=True)
    engagement_id = Column(Integer,ForeignKey('srm_engagements.id',ondelete='RESTRICT'),nullable=False)
    client_id = Column(Integer,ForeignKey('crm_companies.id',ondelete='RESTRICT'),nullable=False)
    request_key = Column(String(36),nullable=False)
    request_sha256 = Column(String(64),nullable=False)
    source_sha256 = Column(String(64),nullable=False)
    action = Column(String(30),nullable=False)
    source_snapshot = Column(JSON,nullable=False)
    result = Column(JSON,nullable=False)


event.listen(AccountsEngagementCommand,'before_update',immutable_command)
event.listen(AccountsEngagementCommand,'before_delete',immutable_command)

event.listen(AccountsCommand,'before_update',immutable_command)
event.listen(AccountsCommand,'before_delete',immutable_command)
MODELS = (AccountsPeriod, AccountsCommand, AccountsEngagementCommand)
RECORD_TABLES = frozenset(model.__tablename__ for model in MODELS)
