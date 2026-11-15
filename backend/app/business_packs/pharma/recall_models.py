"""Private recall history and quantity-free canonical lot state revisions."""
from sqlalchemy import Column,Integer,String,Text,Date,DateTime,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,event,inspect,func,select
from app.db.base_class import Base


class PharmaBatchControl(Base):
    __tablename__='business_pharma_batch_controls'
    __table_args__=(UniqueConstraint('batch_id',name='uq_pharma_batch_control'),CheckConstraint('revision > 0',name='ck_pharma_batch_control_revision'))
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False)
    batch_id=Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False)
    revision=Column(Integer,nullable=False)


class PharmaRecall(Base):
    __tablename__='business_pharma_recalls'
    __table_args__=(
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT',name='fk_pharma_recall_context'),
        UniqueConstraint('id','organization_id','branch_id','pack_context_id',name='uq_pharma_recall_scope'),
        CheckConstraint("state IN ('open','closed') AND revision > 0",name='ck_pharma_recall_state'),
    )
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    branch_id=Column(Integer,nullable=False)
    pack_context_id=Column(Integer,nullable=False)
    batch_id=Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False)
    product_id=Column(Integer,ForeignKey('srm_products.id',ondelete='RESTRICT'),nullable=False)
    warehouse_id=Column(Integer,ForeignKey('srm_warehouses.id',ondelete='RESTRICT'),nullable=False)
    batch_number=Column(String(120),nullable=False)
    expiry_date=Column(Date,nullable=False)
    reason=Column(Text,nullable=False)
    created_by=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    state=Column(String(12),nullable=False,default='open')
    revision=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    __mapper_args__={'version_id_col':revision}


class PharmaRecallEvent(Base):
    __tablename__='business_pharma_recall_events'
    __table_args__=(
        ForeignKeyConstraint(['recall_id','organization_id','branch_id','pack_context_id'],['business_pharma_recalls.id','business_pharma_recalls.organization_id','business_pharma_recalls.branch_id','business_pharma_recalls.pack_context_id'],ondelete='RESTRICT',name='fk_pharma_recall_event_root'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key',name='uq_pharma_recall_request'),
        UniqueConstraint('recall_id','revision',name='uq_pharma_recall_event_revision'),
        CheckConstraint("action IN ('quarantine','recall','close') AND state_after IN ('open','closed')",name='ck_pharma_recall_event_action'),
        CheckConstraint('revision > 0 AND batch_revision_before >= 0 AND batch_revision_after >= batch_revision_before',name='ck_pharma_recall_event_revision'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64',name='ck_pharma_recall_event_request'),
    )
    id=Column(Integer,primary_key=True)
    recall_id=Column(Integer,nullable=False)
    organization_id=Column(Integer,nullable=False,index=True)
    branch_id=Column(Integer,nullable=False)
    pack_context_id=Column(Integer,nullable=False)
    request_key=Column(String(36),nullable=False)
    request_sha256=Column(String(64),nullable=False)
    created_by=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    action=Column(String(16),nullable=False)
    reason=Column(Text,nullable=False)
    revision=Column(Integer,nullable=False)
    state_after=Column(String(12),nullable=False)
    batch_status_before=Column(String(40),nullable=False)
    batch_status_after=Column(String(40),nullable=False)
    batch_revision_before=Column(Integer,nullable=False)
    batch_revision_after=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


@event.listens_for(PharmaRecall,'before_update')
def recall_immutable(mapper,connection,row):
    state=inspect(row)
    actual=connection.execute(select(PharmaRecall.__table__.c.state,PharmaRecall.__table__.c.revision).where(PharmaRecall.id==state.identity[0])).first()
    if actual is None or actual.state!='open' or row.revision!=actual.revision+1:
        raise ValueError('Recall requires an open source and the next exact revision')
    for attr in state.mapper.column_attrs:
        history=state.attrs[attr.key].history
        if not history.has_changes():continue
        if attr.key=='revision':continue
        if attr.key=='state' and tuple(history.deleted)==('open',) and row.state=='closed':continue
        raise ValueError('Recall source and initial reason are immutable')


@event.listens_for(PharmaRecall,'before_delete')
@event.listens_for(PharmaRecallEvent,'before_update')
@event.listens_for(PharmaRecallEvent,'before_delete')
def immutable_history(mapper,connection,row):
    raise ValueError('Recall history is immutable')


@event.listens_for(PharmaRecallEvent,'before_insert')
def event_source(mapper,connection,row):
    from app.apps.srm.models import SRMInventoryBatch
    root=connection.execute(select(PharmaRecall.__table__).where(PharmaRecall.id==row.recall_id)).mappings().first()
    if root is None or (root['organization_id'],root['branch_id'],root['pack_context_id'],root['revision'],root['state'])!=(
        row.organization_id,row.branch_id,row.pack_context_id,row.revision,row.state_after):raise ValueError('Recall event actual private source differs')
    b=SRMInventoryBatch.__table__;c=PharmaBatchControl.__table__
    actual=connection.execute(select(b.c.status,c.c.revision).join(c,c.c.batch_id==b.c.id).where(b.c.id==root['batch_id'],
        b.c.organization_id==row.organization_id,c.c.organization_id==row.organization_id)).first()
    if actual is None or tuple(actual)!=(row.batch_status_after,row.batch_revision_after):raise ValueError('Recall event actual canonical state differs')
    if row.action=='close':
        if row.state_after!='closed' or row.batch_status_after!=row.batch_status_before or row.batch_revision_after!=row.batch_revision_before:
            raise ValueError('Closing recall cannot release or alter batch stock')
    elif row.state_after!='open' or row.batch_revision_after!=row.batch_revision_before+1 or row.batch_status_after!=('quarantined' if row.action=='quarantine' else 'recalled'):
        raise ValueError('Recall event state transition differs')


MODELS=(PharmaBatchControl,PharmaRecall,PharmaRecallEvent)
