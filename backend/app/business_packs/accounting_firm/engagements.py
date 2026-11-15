"""Canonical client engagements through a closed, atomic Accounts command.

No client/CRM/PMS graph is created. Native engagement visibility remains the
ceiling; private period assignment never supplies native engagement access.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from weakref import WeakKeyDictionary
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from app.apps.srm.models import SRMEngagement
from app.apps.srm.schemas import SRMEngagementCreate
from app.apps.srm.access import engagement_query
from app.apps.srm.services.commercial import customer, require, lock_tenant
from app.apps.srm.service_checkout import _source_scope
from app.business_packs.native_checkout_authority import capture
from .models import AccountsEngagementCommand as Command
from . import service


def _json(value):
    if isinstance(value, (date,datetime)):
        return value.isoformat()
    if isinstance(value,Decimal):
        return str(value)
    raise TypeError('Unsupported engagement source value')


def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=_json).encode()).hexdigest()


def _snapshot(db,ident):
    row=db.connection().execute(select(SRMEngagement.__table__).where(SRMEngagement.id==ident)).mappings().first()
    return json.loads(json.dumps(dict(row),default=_json)) if row else None


def authority(db,actor,action='engagements.view',*,write=False):
    scope=service.authority(db,actor,action,write=write)
    inspector=inspect(db.connection())
    if (not inspector.has_table(Command.__tablename__) or not set(Command.__table__.c.keys()) <=
            {column['name'] for column in inspector.get_columns(Command.__tablename__)}):
        service.fail('Install reviewed Accounts engagement migration 116 before using this workflow',503)
    return scope


def _epoch(db,actor,scope,*,write):
    return capture(db,actor,scope,order=write,billing=False,payments=False,write=write)


def _client_query(db,actor,scope):
    from app.apps.srm.pos_surface import customer_query
    from app.apps.srm.commercial_api import DIRECTORY
    from app.access.catalog import permission_objects
    require(actor,*DIRECTORY)
    query=customer_query(db,scope.company_id)
    # Match commercial.customer's native CRM-only visibility decision.
    names={permission.name for permission in permission_objects(actor)}
    if not actor.is_superuser and not names.intersection({'srm_admin','srm_invoice_create','srm_invoice_view',
            'srm_invoice_approve','srm_view','pms_manage_projects','pms_admin'}):
        from app.apps.crm.api.router import _apply_record_visibility,_get_resource
        query=_apply_record_visibility(query,_get_resource('companies'),actor,db)
    return query


def _client(db,actor,scope,ident):
    from app.apps.crm.models import CRMCompany
    row=_client_query(db,actor,scope).filter(CRMCompany.id==ident).first()
    if row is None:
        service.fail('Active client is unavailable',404)
    customer(db,ident,actor)
    _source_scope(db,scope,scope.company_id,scope.branch_id,CRMCompany,ident,master=True)
    return row


def clients(db,actor,*,search='',after=0,limit=50):
    from app.apps.crm.models import CRMCompany
    scope=authority(db,actor,'engagements.manage')
    _epoch(db,actor,scope,write=False)
    query=_client_query(db,actor,scope).filter(CRMCompany.id>after)
    if search:
        query=query.filter(CRMCompany.name.contains(search,autoescape=True))
    rows=query.order_by(CRMCompany.id).limit(limit+1).all()
    return {'items':[{'id':row.id,'name':row.name} for row in rows[:limit]],
        'next':rows[limit-1].id if len(rows)>limit else None}


def _proof(db,actor,scope,command):
    state=inspect(command,raiseerr=False)
    if (type(command) is not Command or state is None or state.session is not db or not state.persistent or
            command in db.dirty or command in db.deleted):
        service.fail('An unchanged persistent Accounts creation command is required')
    stored=db.connection().execute(select(Command.__table__).where(Command.id==command.id,
        Command.organization_id==scope.company_id,Command.branch_id==scope.branch_id,
        Command.pack_context_id==scope.context_id)).mappings().first()
    if stored is None or dict(stored)!={column.name:getattr(command,column.name) for column in Command.__table__.c}:
        service.fail('Accounts creation command differs from its stored source',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,Command,command.id)
    native=engagement_query(db,actor).filter(SRMEngagement.id==command.engagement_id).first()
    if native is None:
        service.fail('Client engagement is unavailable',404)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMEngagement,native.id)
    actual=_snapshot(db,native.id)
    original=command.source_snapshot
    from app.apps.srm.api.router import ENGAGEMENT_STATUSES
    from .project_links import validate_birth_project
    validate_birth_project(db,actor,scope,command,actual)
    immutable=lambda value:{key:item for key,item in value.items() if key not in {'status','updated_at','pms_project_id'}}
    if (command.action!='engagement.create' or actual is None or immutable(actual)!=immutable(original) or
            actual['status'] not in ENGAGEMENT_STATUSES or _digest(original)!=command.source_sha256 or actual['organization_id']!=scope.company_id or
            actual['customer_id']!=command.client_id or actual['created_by']!=command.created_by):
        service.fail('Canonical engagement differs from its immutable creation source',409)
    _client(db,actor,scope,command.client_id)
    if command.result!=_dto(original):
        service.fail('Engagement creation result differs from its source',409)
    return _dto(actual)


def _dto(snapshot):
    return {name:snapshot[name] for name in ('id','engagement_number','customer_id','name','status','billing_type',
        'budget_amount','currency','planned_start_date','planned_end_date')}


@dataclass
class _Birth:
    actor:object
    scope:object
    epoch:str
    data:object
    digest:str
    request_key:str
    request_hash:str
    command:object=None
    native:object=None


_births=WeakKeyDictionary()


def _check(db,plan):
    if (db.info.get('business_pack_scope') is not plan.scope or inspect(plan.actor).session is not db or
            authority(db,plan.actor,'engagements.manage',write=True) is not plan.scope or
            _epoch(db,plan.actor,plan.scope,write=True)!=plan.epoch or
            _digest(plan.data.model_dump(mode='json'))!=plan.digest):
        service.fail('Accounts engagement creation authority or source changed')


@contextmanager
def _birth(db,actor,scope,epoch,data,request_key,request_hash):
    if db in _births:
        service.fail('An Accounts engagement command is already in progress')
    plan=_Birth(actor,scope,epoch,data,_digest(data.model_dump(mode='json')),str(request_key),request_hash)
    _births[db]=plan
    try:
        _check(db,plan)
        yield plan
    finally:
        _births.pop(db,None)


@event.listens_for(SRMEngagement,'before_insert')
def _capture_native_birth(mapper,connection,row):
    db=inspect(row).session
    plan=_births.get(db) if db is not None else None
    if plan is None:
        return
    _check(db,plan)
    state=inspect(row)
    expected={'organization_id':plan.scope.company_id,'created_by':plan.actor.id,
        **plan.data.model_dump(exclude={'engagement_number'})}
    if (plan.native is not None or not state.pending or state.session is not db or row.id is not None or
            any(getattr(row,name)!=value for name,value in expected.items()) or row.pms_project_id is not None or
            row.deleted_at is not None or row.status not in (None,'created') or not row.engagement_number):
        service.fail('Native engagement birth differs from the exact command',409)
    plan.native=row


@event.listens_for(Command,'before_insert')
def _certify_command(mapper,connection,row):
    db=inspect(row).session
    plan=_births.get(db) if db is not None else None
    if plan is None or plan.command is not row or plan.native is None:
        service.fail('A genuine native engagement birth certificate is required')
    _check(db,plan)
    native=plan.native
    current=_snapshot(db,native.id)
    if (row.id is not None or row.created_at is not None or inspect(native).session is not db or not inspect(native).persistent or row.engagement_id!=native.id or
            (row.organization_id,row.branch_id,row.pack_context_id,row.created_by,row.client_id,row.action)!=
            (plan.scope.company_id,plan.scope.branch_id,plan.scope.context_id,plan.actor.id,plan.data.customer_id,'engagement.create') or
            (row.request_key,row.request_sha256)!=(plan.request_key,plan.request_hash) or
            current!=row.source_snapshot or _digest(current)!=row.source_sha256 or row.result!=_dto(current)):
        service.fail('Engagement command differs from its actual native birth',409)


@event.listens_for(Session,'before_commit')
def _atomic_birth(db):
    plan=_births.get(db)
    if plan is None or db.in_nested_transaction():
        return
    # No root commit belongs inside this scope. The public command commits
    # once after both the native source and its certificate have completed.
    # Reject before issuing SQL: an accidental inner commit may already have
    # released its savepoint and closed that transaction context.
    service.fail('An in-progress Accounts engagement creation cannot commit',409)



def create(data,db,actor,*,commit=True):
    scope=authority(db,actor,'engagements.manage',write=True)
    epoch=_epoch(db,actor,scope,write=True)
    lock_tenant(db,actor)
    if (authority(db,actor,'engagements.manage',write=True) is not scope or
            _epoch(db,actor,scope,write=True)!=epoch):
        service.fail('Native engagement authority changed while waiting; reload')
    old=service.scoped(db,Command,scope).filter(Command.request_key==str(data.request_key)).one_or_none()
    fingerprint=service.fingerprint('engagement.create',None,data)
    if old is not None:
        if old.created_by!=actor.id or old.request_sha256!=fingerprint:
            service.fail('Request key was already used for a different engagement',409)
        _proof(db,actor,scope,old)
        return dict(old.result)
    with db.begin_nested():
        _client(db,actor,scope,data.client_id)
        native_input=SRMEngagementCreate(customer_id=data.client_id,name=data.name,currency=data.currency,
            assigned_user_id=actor.id,project_manager_user_id=actor.id,budget_amount=Decimal('0.00'),billing_type='fixed_fee',
            planned_start_date=data.planned_start_date,planned_end_date=data.planned_end_date)
        with _birth(db,actor,scope,epoch,native_input,data.request_key,fingerprint) as plan:
            from app.apps.srm.api.router import create_engagement_operation
            created=create_engagement_operation(native_input,db,actor,commit=False)
            if plan.native is None or inspect(plan.native).session is not db or not inspect(plan.native).persistent or plan.native.id!=created['id']:
                service.fail('Canonical engagement return does not match its actual new source',409)
            snapshot=_snapshot(db,created['id'])
            expected={'organization_id':scope.company_id,'customer_id':data.client_id,'created_by':actor.id,
                **native_input.model_dump(exclude={'engagement_number'})}
            if (snapshot is None or any(snapshot[name]!=json.loads(json.dumps(value,default=_json)) for name,value in expected.items())
                    or snapshot['status']!='created' or snapshot['pms_project_id'] is not None or snapshot['deleted_at'] is not None):
                service.fail('Native engagement differs from its exact creation command',409)
            _check(db,plan)
            row=Command(**service.fields(scope,actor),engagement_id=snapshot['id'],client_id=data.client_id,
                request_key=str(data.request_key),request_sha256=fingerprint,source_sha256=_digest(snapshot),
                action='engagement.create',source_snapshot=snapshot,result=_dto(snapshot))
            plan.command=row
            db.add(row);db.flush()
            result=_proof(db,actor,scope,row)
    if commit:
        db.commit()
    return result


def _visible_commands(db,actor,scope):
    from app.apps.crm.models import CRMCompany
    native=engagement_query(db,actor).with_entities(SRMEngagement.id)
    client=_client_query(db,actor,scope).with_entities(CRMCompany.id)
    return service.scoped(db,Command,scope).filter(Command.engagement_id.in_(native),Command.client_id.in_(client))


def get(ident,db,actor):
    scope=authority(db,actor)
    _epoch(db,actor,scope,write=False)
    row=_visible_commands(db,actor,scope).filter(Command.engagement_id==ident).first()
    if row is None:
        service.fail('Client engagement is unavailable',404)
    return _proof(db,actor,scope,row)


def listing(db,actor,*,after=0,limit=50):
    scope=authority(db,actor)
    _epoch(db,actor,scope,write=False)
    rows=_visible_commands(db,actor,scope).filter(Command.engagement_id>after).order_by(Command.engagement_id).limit(limit+1).all()
    return {'items':[_proof(db,actor,scope,row) for row in rows[:limit]],
        'next':rows[limit-1].engagement_id if len(rows)>limit else None}


def validate_created_source(db,actor,scope,ident):
    """Validate this command's births without adopting legacy engagements."""
    if not inspect(db.connection()).has_table(Command.__tablename__):
        return
    row=service.scoped(db,Command,scope).filter(Command.engagement_id==ident).first()
    if row is not None:
        _proof(db,actor,scope,row)
