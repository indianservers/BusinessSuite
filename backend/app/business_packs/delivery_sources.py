"""Closed private native delivery origin and fresh recipient authorization.

Unowned legacy rows retain native behavior. A private origin is never inferred
from message text/event keys, and a retained certificate cannot declassify it.
"""
from contextlib import contextmanager,ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
from types import SimpleNamespace
from weakref import WeakKeyDictionary,WeakSet,ref
from fastapi import HTTPException
from sqlalchemy import and_,cast,event,exists,inspect,or_,select,String
from sqlalchemy.orm import Session
from app.branches.catalog import resource_key

_PLANS=WeakKeyDictionary()
_ISSUED=WeakSet()
_EMITTERS=WeakKeyDictionary()
EMAIL_FIELDS=('event_key','organization_id','module','recipient_user_id','recipient','subject','body','is_html')
NOTIFICATION_FIELDS=('company_id','user_id','title','message','module','event_type','related_entity_type','related_entity_id','action_url','priority','channels')


def _deny():raise HTTPException(403,'Private native delivery authorization is unavailable')


def _verify_emitter(db,binding):
    try:from .construction_outbox import verify_native_emitter
    except ImportError:_deny()
    if verify_native_emitter(db,binding['scope'],binding['parent'],binding['frame']) is not True:_deny()
    return binding


def bind_native_emitter(native,scope,*,parent,frame):
    """Bind only an owner-issued, currently verified finite native command frame."""
    if native in _EMITTERS:_deny()
    binding={'scope':scope,'parent':parent,'frame':frame}
    _verify_emitter(native,binding)
    _EMITTERS[native]=binding
    def cleanup():
        if _EMITTERS.get(native) is binding:_EMITTERS.pop(native,None)
    return cleanup


def _connection(db):
    """A verified finite emitter borrows only its actual issued outer Session."""
    binding=_EMITTERS.get(db)
    if binding is None:return db.connection()
    _verify_emitter(db,binding)
    parent=binding['parent']
    if not isinstance(parent,Session) or parent is db:_deny()
    return parent.connection()


def _models():
    from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt
    from app.shared.follow_ups import FollowUp
    from app.apps.project_management.models import PMSTask,PMSTaskAssignee,PMSWorkspaceMember
    from app.models.notification import Notification
    return {model.__tablename__:model for model in (SRMSalesOrder,SRMInvoice,SRMReceipt,FollowUp,PMSTask,PMSTaskAssignee,PMSWorkspaceMember,Notification)}


def _key(source):
    state=inspect(source,raiseerr=False)
    if state is None or not state.persistent or state.modified or state.deleted or type(source) not in _models().values():_deny()
    values={column.name:getattr(source,column.name) for column in state.mapper.primary_key}
    if any(type(value) is not int or value<=0 for value in values.values()):_deny()
    return resource_key(state.mapper.local_table,values)


def source_identity(table_name,key):
    model=_models().get(table_name)
    if model is None or not isinstance(key,str) or len(key)>500:_deny()
    columns=list(model.__table__.primary_key.columns);values=[]
    if len(columns)==1:values=[key]
    else:
        rest=key
        for index,column in enumerate(columns):
            length,separator,tail=rest.partition(':')
            if not separator or not length.isascii() or not length.isdigit() or not 1<=int(length)<=500:_deny()
            count=int(length);values.append(tail[:count]);rest=tail[count:]
            if index<len(columns)-1:
                if not rest.startswith(':'):_deny()
                rest=rest[1:]
        if rest:_deny()
    if any(not value.isascii() or not value.isdigit() or int(value)<=0 or str(int(value))!=value for value in values):_deny()
    result={column.name:int(value) for column,value in zip(columns,values)}
    if len(result)!=len(columns) or resource_key(model.__table__,result)!=key:_deny()
    return model,result


def _installation(db):
    from .models import PackRecordOwnership
    from .delivery_source_models import PackDeliverySource
    inspector=inspect(_connection(db));result=[]
    for model in (PackRecordOwnership,PackDeliverySource):
        if not inspector.has_table(model.__tablename__):result.append('absent')
        elif not {column.name for column in model.__table__.columns}<={column['name'] for column in inspector.get_columns(model.__tablename__)}:result.append('partial')
        else:result.append('full')
    return tuple(result)


def _owner(db,table,key):
    from .models import PackRecordOwnership
    if _installation(db)[0]!='full':return None
    row=_connection(db).execute(select(PackRecordOwnership.__table__).where(PackRecordOwnership.resource_table==table,PackRecordOwnership.resource_key==key)).mappings().one_or_none()
    return row


def _anchored(db,table,key,origin):
    from app.branches.models import BranchOwnership
    from .models import PackRecordOwnership
    owner=_owner(db,table,key)
    if owner is None or (owner['company_id'],owner['branch_id'],owner['context_id'])!=(origin.company_id,origin.branch_id,origin.context_id):return False
    native=BranchOwnership.__table__
    return _connection(db).scalar(select(exists().where(native.c.resource_table==table,native.c.resource_key==key,native.c.company_id==origin.company_id,native.c.branch_id==origin.branch_id))) is True


def _digest(values):return sha256(json.dumps(values,sort_keys=True,separators=(',',':'),default=str,ensure_ascii=False).encode()).hexdigest()


def _payload(row):
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    fields=EMAIL_FIELDS if type(row) is EmailOutbox else NOTIFICATION_FIELDS if type(row) is Notification else ()
    if not fields:_deny()
    return {name:getattr(row,name) for name in fields}


def _origin(db,table,key):
    from .models import PackContext
    owner=_owner(db,table,key)
    if owner is None:return None
    context=_connection(db).execute(select(PackContext.__table__).where(PackContext.id==owner['context_id'],PackContext.company_id==owner['company_id'],PackContext.branch_id==owner['branch_id'])).mappings().one_or_none()
    if context is None:_deny()
    return SimpleNamespace(company_id=owner['company_id'],branch_id=owner['branch_id'],context_id=owner['context_id'],pack_key=context['pack_key'],pack_version=context['pack_version'])


@contextmanager
def _reader(db,user_id,origin,module):
    from app.models.user import User
    from app.access.service import check_background_access,resolved_grants
    from app.branches.roles import effective_grants
    from app.access.scope import install_scope
    from app.core.tenant_boundary import install as install_tenant
    from app.branches.service import context as branch_context
    from app.branches.boundary import install as install_branch
    from .access import resolve_context
    from .boundary import install,_current
    from .native_policy import native_srm_policy
    from .common_core import _native_authority
    native=Session(bind=_connection(db),autoflush=False,expire_on_commit=False,join_transaction_mode='rollback_only')
    try:
        user=native.get(User,user_id,populate_existing=True)
        if user is None or not user.is_active:_deny()
        user.organization_id=origin.company_id
        native.info['security_write_request']=False
        native.info['shared_actor']=(user.id,origin.company_id)
        epoch=_native_authority(native,user,origin.company_id)
        with ExitStack() as stack:
            policy=check_background_access(native,user,module,'view',branch_id=origin.branch_id,administrative_read=False,stamp=False)
            grants=effective_grants(native,user,origin.company_id,origin.branch_id,resolved_grants(native,policy) if policy else None,administrative_read=False,stamp=False)
            if grants is not None:
                user._suite_grants=grants;user._suite_current_module=module;user._suite_permission_objects=None
                stack.callback(install_scope(native,user,origin.company_id,grants))
            stack.callback(install_tenant(native,user,origin.company_id))
            branch=branch_context(native,user,origin.company_id,str(origin.branch_id))
            stack.callback(install_branch(native,user,branch))
            scope=resolve_context(native,user,branch,origin.context_id)
            if scope is None or (scope.company_id,scope.branch_id,scope.context_id,scope.pack_key,scope.pack_version)!=(origin.company_id,origin.branch_id,origin.context_id,origin.pack_key,origin.pack_version):_deny()
            stack.callback(install(native,scope,policy=native_srm_policy(scope.pack_key).policy))
            yield native,user,scope
            _current(scope,native.connection())
            if epoch!=_native_authority(native,user,origin.company_id):_deny()
    finally:native.close()


def _source_allowed(db,certificate,recipient):
    model,identity=source_identity(certificate.source_table,certificate.source_key)
    module='project_management' if certificate.source_table.startswith('pms_') else 'srm'
    with _reader(db,recipient,certificate,module) as (native,user,scope):
        if certificate.source_table=='service_follow_ups':
            from .followup_delivery import source_allowed
            return source_allowed(native,certificate,user,scope) is True
        if certificate.source_table in {'pms_tasks','pms_task_assignees','pms_workspace_members'}:
            from .construction_outbox import source_allowed
            return source_allowed(native,certificate,user,scope) is True
        from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt
        from app.apps.srm.access import sales_order_query,SRM_VIEW_PERMISSIONS,SRM_INVOICE_PERMISSIONS,SRM_COLLECTION_PERMISSIONS
        from app.apps.srm.services.commercial import require,invoice_for,scoped
        from .request_operations import FINANCIAL_READ
        if not any(scope.pack_key+'.'+action in scope.capabilities for action in FINANCIAL_READ):return False
        if model is SRMSalesOrder:
            require(user,*SRM_VIEW_PERMISSIONS)
            return sales_order_query(native,user).filter(SRMSalesOrder.id==identity['id']).with_entities(SRMSalesOrder.id).first() is not None
        if model is SRMInvoice:
            require(user,*SRM_INVOICE_PERMISSIONS)
            return invoice_for(native,identity['id'],user) is not None
        if model is SRMReceipt:
            require(user,*SRM_COLLECTION_PERMISSIONS)
            return native.query(SRMReceipt.id).filter(scoped(SRMReceipt.organization_id,user),SRMReceipt.id==identity['id']).first() is not None
        return False


def _issuer_allowed(db,certificate,actor_id):
    if type(actor_id) is not int or actor_id<=0 or getattr(certificate,'actor_user_id',None)!=actor_id:return False
    if certificate.source_table in {'pms_tasks','pms_task_assignees','pms_workspace_members'}:
        try:from .construction_outbox import issuer_allowed
        except ImportError:return False
        with _reader(db,actor_id,certificate,'project_management') as (native,actual_issuer,scope):
            return actual_issuer.id==actor_id and issuer_allowed(native,certificate,actual_issuer,scope) is True
    return _source_allowed(db,certificate,actor_id)


def _birth_actor(db,origin,source):
    """Seal actual issued factory actor or exact canonical source creator."""
    from app.models.notification import Notification
    binding=_EMITTERS.get(db);family=source.__tablename__
    if binding is not None:
        _verify_emitter(db,binding);scope=binding['scope']
        if (scope.company_id,scope.branch_id,scope.context_id)!=(origin.company_id,origin.branch_id,origin.context_id):_deny()
        actor=scope.user_id
    elif type(source) is Notification:
        parent=_certificate(db,notification_id=source.id)
        if parent is not None:actor=parent.actor_user_id;family=parent.source_table
        else:
            plans=[plan for plan in _PLANS.get(db,[]) if plan['row'] is source and not plan.get('email')]
            if len(plans)!=1:_deny()
            actor=plans[0].get('actor_user_id');family=plans[0]['source'].__tablename__
    elif source.__tablename__ in {'srm_sales_orders','srm_invoices','srm_receipts','service_follow_ups'}:
        table=source.__table__;key=_key(source)
        actor=_connection(db).scalar(select(table.c.created_by).where(*(column==getattr(source,column.name) for column in table.primary_key.columns)))
        if actor!=getattr(source,'created_by',None):_deny()
    else:_deny()
    if type(actor) is not int or actor<=0:_deny()
    module='project_management' if binding is not None or family.startswith('pms_') else 'srm'
    with _reader(db,actor,origin,module) as (native,actual_actor,scope):
        if actual_actor.id!=actor or not inspect(actual_actor).persistent or inspect(actual_actor).session is not native:_deny()
    return actor


def _source_current(db,certificate):
    model,identity=source_identity(certificate.source_table,certificate.source_key)
    if not _anchored(db,certificate.source_table,certificate.source_key,certificate):return False
    if certificate.source_table=='notifications':
        parent=_certificate(db,notification_id=identity['id'])
        return (parent is not None and parent.source_table!='notifications' and parent.recipient_user_id==certificate.recipient_user_id and (parent.company_id,parent.branch_id,parent.context_id,parent.pack_key,parent.pack_version)==(certificate.company_id,certificate.branch_id,certificate.context_id,certificate.pack_key,certificate.pack_version) and parent.actor_user_id==getattr(certificate,'actor_user_id',None) and _allowed_certificate(db,parent,depth=1))
    actor=getattr(certificate,'actor_user_id',None)
    if not _issuer_allowed(db,certificate,actor):return False
    table=model.__table__
    creator=table.c.get('created_by')
    if creator is not None:
        user=_connection(db).scalar(select(creator).where(*(table.c[name]==value for name,value in identity.items())))
        if user is None:return False
        if user not in {actor,certificate.recipient_user_id} and not _source_allowed(db,certificate,user):return False
    return _source_allowed(db,certificate,certificate.recipient_user_id)


@dataclass(eq=False,frozen=True)
class DeliveryAuthority:
    dbref:object
    source:object
    origin:object
    recipient_user_id:int
    actor_user_id:int
    source_key:str
    source_snapshot:str


def authorize_source_delivery(db,actual_source,*,recipient_user_id,company_id,branch_id):
    key=_key(actual_source)
    if inspect(actual_source).session is not db:_deny()
    origin=_origin(db,actual_source.__tablename__,key)
    if origin is None:
        if _installation(db)[0]=='partial':_deny()
        return None
    if (origin.company_id,origin.branch_id)!=(company_id,branch_id):_deny()
    from app.core.company_writer import lock_company_writer
    actor=_birth_actor(db,origin,actual_source)
    certificate=SimpleNamespace(**vars(origin),source_table=actual_source.__tablename__,source_key=key,recipient_user_id=recipient_user_id,actor_user_id=actor)
    if not _source_current(db,certificate):_deny()
    lock_company_writer(db,company_id)
    if not _source_current(db,certificate):_deny()
    values={column.name:getattr(actual_source,column.name) for column in actual_source.__table__.columns}
    authority=DeliveryAuthority(ref(db),actual_source,origin,recipient_user_id,actor,key,_digest(values));_ISSUED.add(authority)
    return authority


def _current(db,authority):
    if type(authority) is not DeliveryAuthority or authority not in _ISSUED or authority.dbref() is not db:_deny()
    source=authority.source
    if inspect(source).session is not db or _key(source)!=authority.source_key:_deny()
    actual=_connection(db).execute(select(source.__table__).where(*(column==getattr(source,column.name) for column in source.__table__.primary_key.columns))).mappings().one_or_none()
    if actual is None or _digest(dict(actual))!=authority.source_snapshot:_deny()
    certificate=SimpleNamespace(**vars(authority.origin),source_table=source.__tablename__,source_key=authority.source_key,recipient_user_id=authority.recipient_user_id,actor_user_id=authority.actor_user_id)
    if not _source_current(db,certificate):_deny()
    return certificate


def _adapter(authority):
    if authority.source.__tablename__=='service_follow_ups':
        from . import followup_delivery
        return followup_delivery
    _deny()


def certify_notification(db,authority,notification,delivery_log=None):
    from app.models.notification import Notification,NotificationDeliveryLog
    if authority is None:return None
    _current(db,authority)
    if type(notification) is not Notification or notification not in db.new or notification.id is not None:_deny()
    if (notification.company_id,notification.user_id)!=(authority.origin.company_id,authority.recipient_user_id):_deny()
    if delivery_log is not None and (type(delivery_log) is not NotificationDeliveryLog or delivery_log not in db.new or delivery_log.id is not None):_deny()
    if _adapter(authority).validate_notification(db,authority,notification,delivery_log) is not True:_deny()
    plan={'authority':authority,'row':notification,'payload':_digest(_payload(notification)),'log':delivery_log,'reminder':None,'source':authority.source,'actor_user_id':authority.actor_user_id}
    _PLANS.setdefault(db,[]).append(plan)
    return notification


def certify_followup_reminder(db,authority,reminder):
    if authority is None:return None
    _current(db,authority)
    from app.shared.follow_ups import FollowUpReminder
    plans=[plan for plan in _PLANS.get(db,[]) if plan.get('authority') is authority and plan.get('reminder') is None]
    if len(plans)!=1 or type(reminder) is not FollowUpReminder or reminder not in db.new or reminder.id is not None:_deny()
    if reminder.follow_up_id!=authority.source.id or _adapter(authority).validate_reminder(db,authority,reminder) is not True:_deny()
    plans[0]['reminder']=reminder
    return reminder


def _certificate(db,**target):
    from .delivery_source_models import PackDeliverySource
    if _installation(db)[1]!='full':return None
    rows=_connection(db).execute(select(PackDeliverySource.__table__).where(*(PackDeliverySource.__table__.c[name]==value for name,value in target.items()))).mappings().all()
    if len(rows)>1:_deny()
    return SimpleNamespace(**dict(rows[0])) if rows else None


def _allowed_certificate(db,certificate,*,depth=0):
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    if certificate is None or depth>1 or not certificate.recipient_user_id:return False
    model=EmailOutbox if certificate.email_outbox_id is not None else Notification
    identity=certificate.email_outbox_id or certificate.notification_id
    if not _anchored(db,model.__tablename__,str(identity),certificate):return False
    if certificate.source_table=='notifications' and depth:return False
    if not _source_current(db,certificate):return False
    fields=EMAIL_FIELDS if model is EmailOutbox else NOTIFICATION_FIELDS
    values=_connection(db).execute(select(*(model.__table__.c[name] for name in fields)).where(model.id==identity)).mappings().one_or_none()
    if values is None or _digest(dict(values))!=certificate.payload_sha256:return False
    user_field='recipient_user_id' if model is EmailOutbox else 'user_id'
    company_field='organization_id' if model is EmailOutbox else 'company_id'
    if values[user_field]!=certificate.recipient_user_id or values[company_field]!=certificate.company_id:return False
    if model is EmailOutbox:
        from app.models.user import User
        address=_connection(db).scalar(select(User.email).where(User.id==certificate.recipient_user_id,User.is_active.is_(True)))
        if not address or address.casefold()!=str(certificate.recipient_email).casefold() or values['recipient']!=certificate.recipient_email:return False
    return True


def _known_private_reference(db,row):
    from app.models.notification import Notification
    if type(row) is not Notification:return False
    aliases={'follow_up':'service_follow_ups','invoice':'srm_invoices','sales_order':'srm_sales_orders','receipt':'srm_receipts','task':'pms_tasks'}
    target=aliases.get(row.related_entity_type)
    if target is None or type(row.related_entity_id) is not int:return False
    owner=_owner(db,target,str(row.related_entity_id))
    return owner is not None and owner['company_id']==row.company_id


def delivery_allowed(db,row):
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    if type(row) not in {EmailOutbox,Notification}:return False
    owner_state,cert_state=_installation(db)
    if 'partial' in (owner_state,cert_state):return False
    owner=_owner(db,row.__tablename__,str(row.id))
    certificate=_certificate(db,**({'email_outbox_id':row.id} if type(row) is EmailOutbox else {'notification_id':row.id}))
    if owner is None and certificate is None:return not _known_private_reference(db,row)
    if certificate is None:return False
    from app.core.company_writer import lock_company_writer
    try:
        if not _allowed_certificate(db,certificate):return False
        lock_company_writer(db,certificate.company_id)
        return _allowed_certificate(db,certificate) and _digest(_payload(row))==certificate.payload_sha256
    except (HTTPException,ValueError,ModuleNotFoundError):return False


def filter_notifications(query,db,recipient):
    from app.models.notification import Notification
    from .models import PackRecordOwnership
    from .delivery_source_models import PackDeliverySource
    owner_state,cert_state=_installation(db)
    if owner_state==cert_state=='absent':return query
    if 'partial' in (owner_state,cert_state):return query.filter(False)
    conditions=[]
    if owner_state=='full':
        owner=PackRecordOwnership.__table__
        conditions.append(~exists().where(owner.c.resource_table=='notifications',owner.c.resource_key==cast(Notification.id,String)))
        for kind,table in [('follow_up','service_follow_ups'),('invoice','srm_invoices'),('sales_order','srm_sales_orders'),('receipt','srm_receipts'),('task','pms_tasks')]:
            conditions.append(~and_(Notification.related_entity_type==kind,exists().where(owner.c.resource_table==table,owner.c.resource_key==cast(Notification.related_entity_id,String),owner.c.company_id==Notification.company_id)))
    allowed=[]
    if cert_state=='full':
        table=PackDeliverySource.__table__
        conditions.append(~exists().where(table.c.notification_id==Notification.id))
        rows=_connection(db).execute(select(table).where(table.c.notification_id.is_not(None),table.c.recipient_user_id==recipient.id)).mappings()
        for row in rows:
            try:
                if _allowed_certificate(db,SimpleNamespace(**dict(row))):allowed.append(row['notification_id'])
            except (HTTPException,ValueError,ModuleNotFoundError):continue
    return query.filter(or_(and_(*conditions),Notification.id.in_(allowed)))



def _stamp(db,row,origin):
    from app.branches.models import BranchOwnership
    from .models import PackRecordOwnership
    identity=inspect(row).identity
    if identity is None or len(identity)!=1 or type(identity[0]) is not int:_deny()
    key=str(identity[0]);table=row.__tablename__
    for model,values in ((BranchOwnership,{'company_id':origin.company_id,'branch_id':origin.branch_id}),
                         (PackRecordOwnership,{'company_id':origin.company_id,'branch_id':origin.branch_id,'context_id':origin.context_id,'revision':1})):
        existing=_connection(db).execute(select(model.__table__).where(model.resource_table==table,model.resource_key==key)).mappings().one_or_none()
        if existing is not None:
            if any(existing[name]!=value for name,value in values.items() if name!='revision'):_deny()
        else:_connection(db).execute(model.__table__.insert().values(resource_table=table,resource_key=key,source='typed-private-delivery',**values))


def _insert_certificate(db,row,origin,source,kind):
    from app.models.email_outbox import EmailOutbox
    from .delivery_source_models import PackDeliverySource
    values=_payload(row)
    is_email=type(row) is EmailOutbox
    target={'email_outbox_id':row.id} if is_email else {'notification_id':row.id}
    plans=[plan for plan in _PLANS.get(db,[]) if plan['row'] is row]
    if len(plans)!=1 or type(plans[0].get('actor_user_id')) is not int:_deny()
    actor=plans[0]['actor_user_id']
    existing=_certificate(db,**target)
    if existing is not None:
        if existing.payload_sha256!=_digest(values) or existing.actor_user_id!=actor or (existing.source_table,existing.source_key)!=(source.__tablename__,_key(source)):_deny()
        return
    _connection(db).execute(PackDeliverySource.__table__.insert().values(**target,
        company_id=origin.company_id,branch_id=origin.branch_id,context_id=origin.context_id,
        pack_key=origin.pack_key,pack_version=origin.pack_version,source_table=source.__tablename__,source_key=_key(source),
        source_kind=kind,module=row.module,actor_user_id=actor,recipient_user_id=(row.recipient_user_id if is_email else row.user_id),
        recipient_email=row.recipient if is_email else None,payload_sha256=_digest(values)))


def _email_template(row,source):
    from app.services.email_events import EVENTS
    from app.core.config import settings
    spec=EVENTS.get(source.__tablename__)
    if spec is None or source.__tablename__ not in {'srm_sales_orders','srm_invoices','srm_receipts','notifications'}:return False
    module,label,employee_fk,user_fks,watched,path=spec
    if row.module!=module or row.is_html or not row.recipient_user_id:return False
    if row.recipient_user_id not in {getattr(source,name,None) for name in user_fks}:return False
    status=str(getattr(source,'status',None) or '')
    body=f'{label} #{source.id} has an update.'+(f'\nCurrent status: {status}.' if status else '')
    body+=f"\nSign in to review details: {settings.FRONTEND_PUBLIC_URL.rstrip('/')}{path}"
    return row.body==body and row.subject in {f"{label}: {status or 'created'}",f"{label}: {status or 'updated'}"}


def prepare_native_notice(db,scope,notice,actual_member):
    """Exact new Member notice under its genuine owner-issued frame."""
    from app.models.notification import Notification
    from app.apps.project_management.models import PMSWorkspaceMember
    binding=_EMITTERS.get(db)
    if binding is None or binding['scope'] is not scope:_deny()
    _verify_emitter(db,binding)
    if type(notice) is not Notification or notice not in db.new or notice.id is not None:_deny()
    if type(actual_member) is not PMSWorkspaceMember or inspect(actual_member).session is not db:_deny()
    key=_key(actual_member)
    if getattr(notice,'_suite_source_record',None) is not actual_member:_deny()
    from .construction_outbox import notice_identity
    if notice_identity(db,notice,scope)!={'source_table':actual_member.__tablename__,'source_key':key}:_deny()
    origin=SimpleNamespace(company_id=scope.company_id,branch_id=scope.branch_id,context_id=scope.context_id,pack_key=scope.pack_key,pack_version=scope.pack_version)
    if (notice.company_id,notice.user_id)!=(scope.company_id,actual_member.user_id):_deny()
    if _installation(db)!=('full','full'):_deny()
    # Materialize only the actual native mapper defaults before sealing birth.
    if notice.priority is None:notice.priority='normal'
    if notice.channels is None:notice.channels=['in_app']
    if any(plan['row'] is notice for plan in _PLANS.get(db,[])):_deny()
    _PLANS.setdefault(db,[]).append({'row':notice,'source':actual_member,'origin':origin,'payload':_digest(_payload(notice)),'native_event':True,'emitter':binding,'actor_user_id':_birth_actor(db,origin,actual_member)})
    return notice


def mint_private_notice(db,scope,notice):
    from app.models.notification import Notification
    plans=[plan for plan in _PLANS.get(db,[]) if plan['row'] is notice and plan.get('native_event') and plan.get('emitter') is not None]
    if type(notice) is not Notification or len(plans)!=1:_deny()
    plan=plans[0];binding=_verify_emitter(db,plan['emitter'])
    if binding['scope'] is not scope or inspect(notice).session is not db or not inspect(notice).persistent:_deny()
    if _digest(_payload(notice))!=plan['payload']:_deny()
    if not _anchored(db,notice.__tablename__,str(notice.id),plan['origin']):_deny()
    certificate=SimpleNamespace(**vars(plan['origin']),source_table=plan['source'].__tablename__,source_key=_key(plan['source']),recipient_user_id=notice.user_id,module=notice.module,actor_user_id=plan['actor_user_id'])
    if not _source_current(db,certificate):_deny()
    _insert_certificate(db,notice,plan['origin'],plan['source'],'workspace_member')


def _reject_pending_target(db,row):
    """Reject only the exact invalid new message, never its business transaction."""
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    state=inspect(row,raiseerr=False)
    if type(row) not in {EmailOutbox,Notification} or state is None or not state.pending or state.session is not db or row.id is not None:_deny()
    db.expunge(row)
    import logging
    logging.getLogger(__name__).warning('private_delivery_rejected_company_mismatch')
    return None


def _retain_denied_birth(db,row,source,origin):
    """Deny-only origin for an exact new target; never a delivery permit."""
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    from app.core.tenant_boundary import tenant_company_column
    if type(row) not in {EmailOutbox,Notification} or row not in db.new or row.id is not None:_deny()
    state=inspect(source,raiseerr=False)
    if state is None or not state.persistent or state.session is not db:_deny()
    key=resource_key(state.mapper.local_table,{column.name:getattr(source,column.name) for column in state.mapper.primary_key})
    target_company=row.organization_id if type(row) is EmailOutbox else row.company_id
    if target_company!=origin.company_id:return _reject_pending_target(db,row)
    company=source.__table__.c.get('organization_id')
    if company is None and tenant_company_column(type(source)):company=source.__table__.c.get('company_id')
    if company is not None and getattr(source,company.key)!=origin.company_id:return _reject_pending_target(db,row)
    if not _anchored(db,source.__tablename__,key,origin):return None
    if any(plan['row'] is row for plan in _PLANS.get(db,[])):_deny()
    if type(row) is Notification:
        if row.priority is None:row.priority='normal'
        if row.channels is None:row.channels=['in_app']
    _PLANS.setdefault(db,[]).append({'row':row,'source':source,'source_key':key,'origin':origin,
        'payload':_digest(_payload(row)),'quarantine':True,'email':type(row) is EmailOutbox,'native_event':type(row) is Notification})
    return row


def _finish_denied_birth(db,plan):
    row=plan['row'];state=inspect(row)
    if state.session is not db or not state.persistent or _digest(_payload(row))!=plan['payload']:_deny()
    # The source/anchor may disappear later; retain the verified birth origin.
    target_company=getattr(row,'organization_id',None) if plan['email'] else row.company_id
    if target_company!=plan['origin'].company_id:_deny()
    _stamp(db,row,plan['origin'])


def prepare_email(db,row,source_record):
    """Called by actual queue_email after db.add, before any outbox flush."""
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    if source_record is None:return None
    if type(row) is not EmailOutbox or row not in db.new or row.id is not None:_deny()
    state=inspect(source_record,raiseerr=False)
    if state is None or not state.persistent or state.session is not db:_deny()
    if _installation(db)[0]=='absent':return None
    key=resource_key(state.mapper.local_table,{column.name:getattr(source_record,column.name) for column in state.mapper.primary_key})
    origin=_origin(db,source_record.__tablename__,key)
    emitter=None
    if source_record.__tablename__ in {'pms_tasks','pms_task_assignees'}:
        emitter=_EMITTERS.get(db)
        if emitter is not None:
            _verify_emitter(db,emitter)
            from .construction_outbox import source_identity as native_source_identity
            proof=native_source_identity(db,row,emitter['scope'])
            if proof!={'source_table':source_record.__tablename__,'source_key':key}:_deny()
            bound=emitter['scope']
            origin=SimpleNamespace(company_id=bound.company_id,branch_id=bound.branch_id,context_id=bound.context_id,pack_key=bound.pack_key,pack_version=bound.pack_version)
    parent=None
    if type(source_record) is Notification:
        parent=_certificate(db,notification_id=source_record.id)
        if parent is not None:origin=SimpleNamespace(**{name:getattr(parent,name) for name in ('company_id','branch_id','context_id','pack_key','pack_version')})
        elif any(plan['row'] is source_record for plan in _PLANS.get(db,[])):
            native_plan=next(plan for plan in _PLANS[db] if plan['row'] is source_record)
            origin=native_plan['origin'] if native_plan.get('native_event') else native_plan['authority'].origin
            if native_plan.get('emitter') is not None:emitter=_verify_emitter(db,native_plan['emitter'])
        if parent is not None and _EMITTERS.get(db) is not None:
            binding=_EMITTERS[db]
            if binding['scope'].pack_key=='construction':emitter=_verify_emitter(db,binding)
        if emitter is not None:
            from .construction_outbox import notification_email_identity
            if notification_email_identity(db,row,emitter['scope'])!={'source_table':source_record.__tablename__,'source_key':key}:_deny()
    if origin is None:
        # Preparation is not a grant. The native boundary may stamp the actual
        # source later in this same flush; finalization still requires both
        # persisted exact source and target anchors and can never adopt it.
        bound=db.info.get('business_pack_scope');policy=db.info.get('business_pack_policy')
        if bound is not None and policy is not None and source_record.__tablename__ in policy.record_tables:
            from .boundary import _current as current_scope
            current_scope(bound,_connection(db))
            origin=SimpleNamespace(company_id=bound.company_id,branch_id=bound.branch_id,context_id=bound.context_id,pack_key=bound.pack_key,pack_version=bound.pack_version)
    if origin is None:return None
    if row.organization_id!=origin.company_id:return _reject_pending_target(db,row)
    if emitter is None and not _email_template(row,source_record):
        row.status='suppressed';row.error='Private native delivery source is not integrated'
        return _retain_denied_birth(db,row,source_record,origin)
    if _installation(db)[1]!='full':
        row.status='suppressed'
        return _retain_denied_birth(db,row,source_record,origin)
    try:actor=_birth_actor(db,origin,source_record)
    except (HTTPException,ValueError,ModuleNotFoundError):
        row.status='suppressed';row.error='Private native delivery issuer is unavailable'
        return _retain_denied_birth(db,row,source_record,origin)
    plan={'row':row,'source':source_record,'origin':origin,'payload':_digest(_payload(row)),'email':True,'emitter':emitter,'actor_user_id':actor}
    _PLANS.setdefault(db,[]).append(plan)
    return row


def mint_private(db,scope,outbox):
    plans=[plan for plan in _PLANS.get(db,[]) if plan['row'] is outbox and plan.get('email')]
    if len(plans)!=1:_deny()
    plan=plans[0]
    if plan.get('emitter') is not None:
        binding=_verify_emitter(db,plan['emitter'])
        if binding['scope'] is not scope:_deny()
        certificate=SimpleNamespace(**vars(plan['origin']),source_table=plan['source'].__tablename__,source_key=_key(plan['source']),recipient_user_id=outbox.recipient_user_id,module=outbox.module,actor_user_id=plan['actor_user_id'])
        if not _source_current(db,certificate):_deny()
    _finish_email(db,plan)


def _finish_email(db,plan):
    row,source,origin=plan['row'],plan['source'],plan['origin']
    if inspect(row).session is not db or not inspect(row).persistent or getattr(row,'_suite_source_record',None) is not source or _digest(_payload(row))!=plan['payload']:_deny()
    if not _anchored(db,source.__tablename__,_key(source),origin):_deny()
    if plan.get('emitter') is not None and not _anchored(db,row.__tablename__,str(row.id),origin):_deny()
    if source.__tablename__=='notifications':
        parent=_certificate(db,notification_id=source.id)
        if parent is None or parent.recipient_user_id!=row.recipient_user_id or not _allowed_certificate(db,parent):_deny()
    # The historical template/status was sealed at actual birth. Native source
    # status may legitimately advance later in the same financial transaction.
    _stamp(db,row,origin);_insert_certificate(db,row,origin,source,'notification' if source.__tablename__=='notifications' else 'native_event')


def _validate_births(db):
    for plan in _PLANS.get(db,[]):
        if plan.get('quarantine'):
            if _digest(_payload(plan['row']))!=plan['payload']:_deny()
            if plan['email'] and plan['row'].status!='suppressed':plan['row'].status='suppressed'
            continue
        if plan.get('email'):
            if _digest(_payload(plan['row']))!=plan['payload']:_deny()
            if plan['source'].__tablename__=='notifications':
                parent=next((item for item in _PLANS.get(db,[]) if item['row'] is plan['source'] and not item.get('email')),None)
                if parent is not None:
                    if not parent.get('native_event'):_current(db,parent['authority'])
                elif not _allowed_certificate(db,_certificate(db,notification_id=plan['source'].id)):_deny()
            continue
        if plan.get('native_event'):
            if _digest(_payload(plan['row']))!=plan['payload'] or inspect(plan['source']).session is not db or not inspect(plan['source']).persistent:_deny()
            continue
        _current(db,plan['authority'])
        if _digest(_payload(plan['row']))!=plan['payload'] or _adapter(plan['authority']).validate_notification(db,plan['authority'],plan['row'],plan['log']) is not True:_deny()
        validator=_adapter(plan['authority']).validate_retry_reminder if plan.get('retry') else _adapter(plan['authority']).validate_reminder
        if plan['reminder'] is None or validator(db,plan['authority'],plan['reminder']) is not True:_deny()


def finalize_births(db,context=None):
    _validate_births(db)
    # Class listener prepended before generic email_events.enqueue_email_events:
    # Notification origin exists before any derivative email is queued.
    for plan in _PLANS.get(db,[]):
        if plan.get('quarantine'):
            if inspect(plan['row']).persistent and db.info.get('business_pack_policy') is None:_finish_denied_birth(db,plan)
            continue
        if plan.get('email') or plan.get('emitter') is not None:continue
        if not inspect(plan['row']).persistent:continue
        origin=plan['origin'] if plan.get('native_event') else plan['authority'].origin
        if db.info.get('business_pack_policy') is None:
            for row in (plan['row'],plan.get('log'),plan.get('reminder')):
                if row is not None and inspect(row).persistent:_stamp(db,row,origin)
        if db.info.get('business_pack_policy') is None:
            _insert_certificate(db,plan['row'],origin,plan['source'],'native_event' if plan.get('native_event') else 'follow_up')
    for plan in _PLANS.get(db,[]):
        if plan.get('email') and not plan.get('quarantine') and inspect(plan['row']).persistent and db.info.get('business_pack_policy') is None and plan.get('emitter') is None:_finish_email(db,plan)


def _before_flush(db,*args):_validate_births(db)
def _before_commit(db):
    _validate_births(db)
    for plan in _PLANS.get(db,[]):
        if plan.get('emitter') is not None and inspect(plan['row']).persistent:
            certificate=_certificate(db,**({'email_outbox_id':plan['row'].id} if plan.get('email') else {'notification_id':plan['row'].id}))
            if certificate is None or certificate.payload_sha256!=plan['payload'] or certificate.actor_user_id!=plan['actor_user_id']:_deny()
def _end(db,transaction):
    if transaction.parent is None:_PLANS.pop(db,None)


event.listen(Session,'before_flush',_before_flush)
event.listen(Session,'before_commit',_before_commit)
event.listen(Session,'after_flush_postexec',finalize_births,insert=True)
event.listen(Session,'after_transaction_end',_end)


def finalize_pack_births(db,scope,queue):
    from app.models.email_outbox import EmailOutbox
    from app.models.notification import Notification
    for row in queue:
        denied=next((plan for plan in _PLANS.get(db,[]) if plan['row'] is row and plan.get('quarantine')),None)
        if denied is not None:
            _finish_denied_birth(db,denied);continue
        if type(row) is Notification:
            plan=next((item for item in _PLANS.get(db,[]) if item['row'] is row and item.get('native_event')),None)
            if plan is not None:
                if plan.get('emitter') is not None:continue
                if not _anchored(db,plan['source'].__tablename__,_key(plan['source']),plan['origin']):_deny()
                _insert_certificate(db,row,plan['origin'],plan['source'],'native_event')
        if type(row) is not EmailOutbox:continue
        plan=next((item for item in _PLANS.get(db,[]) if item['row'] is row and item.get('email')),None)
        if plan is not None:
            if plan.get('emitter') is not None:continue
            if (scope.company_id,scope.branch_id,scope.context_id)!=(plan['origin'].company_id,plan['origin'].branch_id,plan['origin'].context_id):_deny()
            _finish_email(db,plan)
        else:
            row.status='suppressed';row.error='Private native delivery source is not integrated'



def certify_native_notification(db,source,row):
    """Exact native SRM invoice-draft event; no request text/source-id adoption."""
    from app.apps.srm.models import SRMInvoice
    from app.models.notification import Notification
    if source is None:return None
    if type(source) is not SRMInvoice or inspect(source).session is not db or not inspect(source).persistent:_deny()
    origin=_origin(db,source.__tablename__,str(source.id))
    if origin is None:return None
    if type(row) is not Notification or row not in db.new or row.id is not None:_deny()
    if (row.user_id!=source.created_by or row.module!='srm' or row.event_type!='srm.lifecycle'
            or row.related_entity_type!='invoice' or row.related_entity_id!=source.id
            or row.action_url!=f'/srm/invoices/{source.id}' or row.title!='Invoice draft created'
            or row.message!=f'{source.invoice_number} is ready for review.'):_deny()
    if row.company_id not in {None,origin.company_id}:return _reject_pending_target(db,row)
    row.company_id=origin.company_id
    # ORM defaults are fixed native birth values, not a user-configurable grant.
    if row.priority is None:row.priority='normal'
    if row.channels is None:row.channels=['in_app']
    try:actor=_birth_actor(db,origin,source)
    except (HTTPException,ValueError,ModuleNotFoundError):return _retain_denied_birth(db,row,source,origin)
    _PLANS.setdefault(db,[]).append({'row':row,'source':source,'origin':origin,'payload':_digest(_payload(row)),'native_event':True,'actor_user_id':actor})
    return row



def bind_followup_retry(db,authority,reminder):
    """Only an existing same-source owned undelivered intent can be rebound."""
    if authority is None:return None
    _current(db,authority)
    from app.shared.follow_ups import FollowUpReminder
    plans=[plan for plan in _PLANS.get(db,[]) if plan.get('authority') is authority and plan.get('reminder') is None]
    state=inspect(reminder,raiseerr=False)
    if (len(plans)!=1 or type(reminder) is not FollowUpReminder or state is None or not state.persistent
            or state.session is not db or state.modified or reminder.notification_id is not None
            or reminder.delivery_status not in {'pending','retry','deferred','blocked'}
            or reminder.follow_up_id!=authority.source.id
            or not _anchored(db,FollowUpReminder.__tablename__,str(reminder.id),authority.origin)):_deny()
    actual=_connection(db).execute(select(FollowUpReminder.__table__).where(FollowUpReminder.id==reminder.id)).mappings().one_or_none()
    if actual is None or actual['follow_up_id']!=authority.source.id or actual['schedule_key']!=reminder.schedule_key or actual['notification_id'] is not None:_deny()
    if _adapter(authority).validate_retry_reminder(db,authority,reminder) is not True:_deny()
    plans[0]['reminder']=reminder;plans[0]['retry']=True
    return reminder


def _prune_rolled_back(db,transaction):
    if transaction.parent is None:return
    retained=[]
    for plan in _PLANS.get(db,[]):
        state=inspect(plan['row'],raiseerr=False)
        if state is not None and state.session is db and (state.pending or state.persistent):retained.append(plan)
    if retained:_PLANS[db]=retained
    else:_PLANS.pop(db,None)


event.listen(Session,'after_soft_rollback',_prune_rolled_back)
