"""Scoped, redacted query examples. Approval is separate from observed predictions."""
from sqlalchemy import Column,Integer,String,Text,Float,DateTime,Boolean,JSON,ForeignKey,UniqueConstraint,Index,CheckConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class NlpQuery(Base):
    __tablename__='ai_nlp_queries'
    __table_args__=(UniqueConstraint('user_id','request_key_hash',name='uq_nlp_query_request'),
                   UniqueConstraint('suite_run_id',name='uq_nlp_query_run'),
                   CheckConstraint("review_status IN ('pending','approved','rejected','deleted')",name='ck_nlp_review_status'),
                   CheckConstraint('revision >= 1',name='ck_nlp_revision'),
                   Index('ix_nlp_query_review_scope','company_id','branch_id','module','review_status','id'))
    id=Column(Integer,primary_key=True)
    company_id=Column(Integer,ForeignKey('companies.id',ondelete='CASCADE'),nullable=False)
    branch_id=Column(Integer,nullable=True)
    user_id=Column(Integer,ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    workspace_id=Column(Integer,ForeignKey('pms_workspaces.id',ondelete='SET NULL'),nullable=True)
    project_id=Column(Integer,nullable=True)
    suite_run_id=Column(Integer,ForeignKey('ai_suite_runs.id',ondelete='SET NULL'),nullable=True)
    request_key_hash=Column(String(64),nullable=False)
    submission_hash=Column(String(64),nullable=False)
    query_text=Column(Text,nullable=False)
    normalized_query=Column(Text,nullable=False)
    query_hash=Column(String(64),nullable=False,index=True)
    module=Column(String(20),nullable=False)
    provider=Column(String(20),nullable=False)
    input_mode=Column(String(20),nullable=False)
    predicted_intent=Column(String(80),nullable=True)
    confidence=Column(Float,nullable=True)
    model_version=Column(String(160),nullable=True)
    outcome=Column(String(40),nullable=False,default='received')
    error_code=Column(String(80),nullable=True)
    review_status=Column(String(20),nullable=False,default='pending')
    reviewed_module=Column(String(20),nullable=True)
    reviewed_intent=Column(String(80),nullable=True)
    training_text=Column(Text,nullable=True)
    privacy_reviewed=Column(Boolean,nullable=False,default=False)
    reviewed_by=Column(Integer,ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    reviewed_at=Column(DateTime(timezone=True),nullable=True)
    revision=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())


class NlpDataset(Base):
    __tablename__='ai_nlp_datasets'
    id=Column(Integer,primary_key=True)
    company_id=Column(Integer,ForeignKey('companies.id',ondelete='CASCADE'),nullable=False,index=True)
    branch_id=Column(Integer,nullable=False,index=True)
    workspace_id=Column(Integer,ForeignKey('pms_workspaces.id',ondelete='SET NULL'),nullable=True)
    created_by=Column(Integer,ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    name=Column(String(180),nullable=False)
    samples=Column(JSON,nullable=False)
    counts=Column(JSON,nullable=False)
    content_hash=Column(String(64),nullable=False)
    status=Column(String(20),nullable=False,default='pending')
    revision=Column(Integer,nullable=False,default=1)
    reviewed_by=Column(Integer,ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
