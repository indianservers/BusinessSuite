"""Retained origin certificate for private native notification/email delivery."""
import re
from sqlalchemy import Column,Integer,String,DateTime,ForeignKey,ForeignKeyConstraint,CheckConstraint,UniqueConstraint,event,func
from app.db.base_class import Base

class PackDeliverySource(Base):
    __tablename__='business_pack_delivery_sources'
    __table_args__=(
        ForeignKeyConstraint(['context_id','company_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],name='fk_pack_delivery_context',ondelete='RESTRICT'),
        UniqueConstraint('email_outbox_id',name='uq_pack_delivery_email'),
        UniqueConstraint('notification_id',name='uq_pack_delivery_notification'),
        CheckConstraint('(email_outbox_id IS NOT NULL AND notification_id IS NULL) OR (email_outbox_id IS NULL AND notification_id IS NOT NULL)',name='ck_pack_delivery_target'),
        CheckConstraint('company_id > 0 AND branch_id > 0 AND context_id > 0 AND pack_version > 0 AND actor_user_id > 0',name='ck_pack_delivery_scope'),
        CheckConstraint('length(payload_sha256)=64 AND length(source_key)>0',name='ck_pack_delivery_payload'),
    )
    id=Column(Integer,primary_key=True)
    email_outbox_id=Column(Integer,ForeignKey('email_outbox.id',ondelete='RESTRICT'),nullable=True)
    notification_id=Column(Integer,ForeignKey('notifications.id',ondelete='RESTRICT'),nullable=True)
    company_id=Column(Integer,nullable=False)
    branch_id=Column(Integer,nullable=False)
    context_id=Column(Integer,nullable=False)
    pack_key=Column(String(60),nullable=False)
    pack_version=Column(Integer,nullable=False)
    source_table=Column(String(120),nullable=False)
    source_key=Column(String(500),nullable=False)
    source_kind=Column(String(40),nullable=False)
    module=Column(String(60),nullable=False)
    actor_user_id=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    recipient_user_id=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=True)
    recipient_email=Column(String(254),nullable=True)
    payload_sha256=Column(String(64),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())

@event.listens_for(PackDeliverySource,'before_insert')
def _validate(mapper,connection,row):
    if type(row.actor_user_id) is not int or row.actor_user_id<=0:raise ValueError('An actual native delivery issuer is required')
    if bool(row.email_outbox_id)==bool(row.notification_id):raise ValueError('Exactly one native delivery target is required')
    if not isinstance(row.source_key,str) or not 1<=len(row.source_key)<=500:raise ValueError('Canonical native source identity is required')
    if not isinstance(row.payload_sha256,str) or not re.fullmatch('[0-9a-f]{64}',row.payload_sha256):raise ValueError('Canonical delivery snapshot is required')

@event.listens_for(PackDeliverySource,'before_update')
@event.listens_for(PackDeliverySource,'before_delete')
def _retained(mapper,connection,row):raise ValueError('Private delivery origin is immutable and retained')
