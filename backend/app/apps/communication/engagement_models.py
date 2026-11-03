"""Shared customer work queues and private per-user reading/snooze positions."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from app.db.base_class import Base


class ConversationWorkflow(Base):
    __tablename__ = 'communication_conversation_workflows'
    __table_args__ = (UniqueConstraint('organization_id','kind','record_id',name='uq_communication_workflow'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    record_id = Column(Integer, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey('users.id'))
    handover_note = Column(Text, nullable=False, default='')
    status = Column(String(20), nullable=False, default='open')
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationReading(Base):
    __tablename__ = 'communication_conversation_reading'
    __table_args__ = (UniqueConstraint('organization_id','kind','record_id','user_id',name='uq_communication_reading'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    record_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    whatsapp_read_id = Column(Integer, nullable=False, default=0)
    email_read_id = Column(Integer, nullable=False, default=0)
    snoozed_until = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
