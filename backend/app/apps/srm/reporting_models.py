"""Durable native report preferences and jobs; no financial values are rewritten."""
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class SRMReportView(Base):
    __tablename__='srm_report_views'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey('companies.id'),nullable=False,index=True)
    branch_id=Column(Integer,ForeignKey('branches.id'),nullable=False,index=True)
    owner_id=Column(Integer,ForeignKey('users.id'),nullable=False,index=True)
    name=Column(String(100),nullable=False)
    report=Column(String(40),nullable=False)
    filters_json=Column(JSON,nullable=False,default=dict)
    columns_json=Column(JSON,nullable=False,default=list)
    revision=Column(Integer,nullable=False,default=1,server_default='1')
    deleted_at=Column(DateTime(timezone=True))
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at=Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)


class SRMReportFlag(Base):
    __tablename__='srm_report_flags'
    __table_args__=(UniqueConstraint('organization_id','entity','resource_id',name='uq_srm_report_test_flag'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey('companies.id'),nullable=False,index=True)
    branch_id=Column(Integer,ForeignKey('branches.id'),nullable=False,index=True)
    entity=Column(String(30),nullable=False)
    resource_id=Column(Integer,nullable=False)
    is_test=Column(Boolean,nullable=False,default=False)
    reason=Column(String(500),nullable=False)
    updated_by=Column(Integer,ForeignKey('users.id'),nullable=False)
    updated_at=Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)


class SRMReportJob(Base):
    __tablename__='srm_report_jobs'
    __table_args__=(UniqueConstraint('organization_id','request_key',name='uq_srm_report_job_request'),
                   Index('ix_srm_report_job_queue','status','created_at'))
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey('companies.id'),nullable=False,index=True)
    branch_id=Column(Integer,ForeignKey('branches.id'),nullable=False,index=True)
    owner_id=Column(Integer,ForeignKey('users.id'),nullable=False,index=True)
    request_key=Column(String(36),nullable=False)
    report=Column(String(40),nullable=False)
    format=Column(String(10),nullable=False)
    filters_json=Column(JSON,nullable=False)
    columns_json=Column(JSON,nullable=False,default=list)
    status=Column(String(20),nullable=False,default='queued',index=True)
    row_count=Column(Integer,nullable=False,default=0)
    file_path=Column(Text)
    content_sha256=Column(String(64))
    error=Column(String(500))
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    completed_at=Column(DateTime(timezone=True))
    expires_at=Column(DateTime(timezone=True),nullable=False)


class SRMReportSchedule(Base):
    __tablename__='srm_report_schedules'
    __table_args__=(UniqueConstraint('organization_id','branch_id','owner_id',name='uq_srm_report_owner_schedule'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey('companies.id'),nullable=False,index=True)
    branch_id=Column(Integer,ForeignKey('branches.id'),nullable=False,index=True)
    owner_id=Column(Integer,ForeignKey('users.id'),nullable=False,index=True)
    enabled=Column(Boolean,nullable=False,default=False)
    config_json=Column(JSON,nullable=False,default=dict)
    state_json=Column(JSON,nullable=False,default=dict)
    next_run_at=Column(DateTime(timezone=True),index=True)
    last_run_at=Column(DateTime(timezone=True))
    last_error=Column(String(500))
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


REPORT_MODELS=(SRMReportView,SRMReportFlag,SRMReportJob,SRMReportSchedule)
