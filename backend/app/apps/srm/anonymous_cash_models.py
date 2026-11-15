"""Explicit scoped anonymous counter ledger account; never a person or global ID."""
from sqlalchemy import Column,Integer,String,Boolean,DateTime,ForeignKey,ForeignKeyConstraint,CheckConstraint,Index,event,select,inspect,text
from sqlalchemy.sql import func
from app.db.base_class import Base

class AnonymousCashAccount(Base):
    __tablename__='srm_anonymous_cash_accounts'
    __table_args__=(
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT'),
        Index('uq_anonymous_cash_legacy','organization_id','branch_id',unique=True,sqlite_where=text('pack_context_id IS NULL'),postgresql_where=text('pack_context_id IS NULL')),
        Index('uq_anonymous_cash_pack','organization_id','branch_id','pack_context_id',unique=True,sqlite_where=text('pack_context_id IS NOT NULL'),postgresql_where=text('pack_context_id IS NOT NULL')),
        CheckConstraint("kind='anonymous_cash'",name='ck_anonymous_cash_kind'),
        CheckConstraint('pack_context_id IS NULL OR pack_context_id>0',name='ck_anonymous_cash_context'),
        CheckConstraint('revision>0 AND length(jurisdiction_country)=2',name='ck_anonymous_cash_revision'),
    )
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey('companies.id',ondelete='RESTRICT'),nullable=False)
    branch_id=Column(Integer,ForeignKey('branches.id',ondelete='RESTRICT'),nullable=False)
    pack_context_id=Column(Integer,nullable=True)
    customer_id=Column(Integer,ForeignKey('crm_companies.id',ondelete='RESTRICT'),nullable=False,unique=True)
    kind=Column(String(32),nullable=False,default='anonymous_cash',server_default='anonymous_cash')
    jurisdiction_country=Column(String(2),nullable=False)
    account_label=Column(String(180),nullable=False)
    active=Column(Boolean(create_constraint=True,name='ck_anonymous_cash_active'),nullable=False,default=True,server_default='true')
    revision=Column(Integer,nullable=False,default=1,server_default='1')
    created_by=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    __mapper_args__={'version_id_col':revision}

@event.listens_for(AnonymousCashAccount,'before_update')
def identity(mapper,connection,target):
    original=connection.execute(select(target.__table__).where(target.__table__.c.id==inspect(target).identity[0])).mappings().one()
    fixed=('id','organization_id','branch_id','pack_context_id','customer_id','kind','jurisdiction_country','account_label','created_by')
    if any(getattr(target,key)!=original[key] for key in fixed):raise ValueError('Anonymous control account identity is immutable')
    if inspect(target).attrs.revision.history.has_changes() and target.revision!=original['revision']+1:raise ValueError('Anonymous control account revision must advance exactly once')

@event.listens_for(AnonymousCashAccount,'before_delete')
def no_delete(*args):raise ValueError('Anonymous control account history must be retained')


@event.listens_for(AnonymousCashAccount,'before_insert')
def validate_source(mapper,connection,target):
    from app.models.company import Branch
    from app.apps.crm.models import CRMCompany
    branch=connection.execute(select(Branch.company_id).where(Branch.id==target.branch_id)).scalar_one_or_none()
    customer=connection.execute(select(CRMCompany.organization_id).where(CRMCompany.id==target.customer_id)).scalar_one_or_none()
    if branch!=target.organization_id or customer!=target.organization_id:raise ValueError('Control account source company and branch must match exactly')
