"""Product audiences, relationship follow-ups and reviewed customer greetings."""
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, case, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.input_validation import calling_code, national_phone
from app.models.user import User
from app.shared.catalog_models import CatalogLink
from . import productivity as sales
from .models import CRMActivity, CRMContact, CRMDeal, CRMDealContact, CRMDealProduct

router = APIRouter(prefix='/growth', tags=['CRM relationship growth'])
ENTITIES = ('leads', 'contacts', 'companies', 'deals')
TARGETS = {'leads':'lead', 'contacts':'contact', 'companies':'customer', 'deals':'deal'}
Entity = Literal['leads', 'contacts', 'companies', 'deals']
Channel = Literal['email', 'whatsapp', 'sms']
CLOSED = {'won','lost','converted','closed','cancelled','inactive','do not contact'}


def crm():
    return sales.lm.core()


def zone(name):
    try: return ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError): raise HTTPException(422, 'Choose a valid time zone')


def due_expression(model, entity, org):
    kind = 'account' if entity=='companies' else sales.record_kind(entity)
    pending = select(func.min(CRMActivity.due_date)).where(CRMActivity.organization_id==org, CRMActivity.entity_type==kind, CRMActivity.entity_id==model.id, CRMActivity.status.in_(sales.OPEN_ACTIVITY)).correlate(model).scalar_subquery()
    stored = getattr(model, 'next_follow_up_at', None)
    return func.coalesce(pending, stored) if stored is not None else pending


def deal_match(db, kind, item_id):
    column = CRMDeal.catalog_items
    if db.bind.dialect.name == 'postgresql':
        match = cast(column, JSONB).contains([{'kind':kind, **({'item_id':item_id} if item_id else {})}])
    else:
        entries = func.json_each(column).table_valued('key', 'value').alias('growth_items')
        match = exists(select(1).select_from(entries).where(func.json_extract(entries.c.value, '$.kind')==kind, *([func.json_extract(entries.c.value, '$.item_id')==item_id] if item_id else [])))
    from app.apps.srm.models import SRMProduct
    legacy = select(CRMDealProduct.deal_id).join(SRMProduct, SRMProduct.id==CRMDealProduct.product_id).where(SRMProduct.product_type=='service' if kind=='service' else func.coalesce(SRMProduct.product_type,'stock')!='service')
    if item_id: legacy=legacy.where(CRMDealProduct.product_id==item_id)
    return or_(match, (column.is_(None)) & CRMDeal.id.in_(legacy))


def filtered(db, user, entity, scope, kind, item_id, search, active_only):
    q = sales.rows(db,user,entity,scope)
    model = crm()._get_resource(entity).model
    org = crm()._organization_id(db,user)
    if search:
        fields = [getattr(model,key) for key in ('full_name','name','email','phone','company_name') if hasattr(model,key)]
        q=q.filter(or_(*(field.ilike('%'+search+'%') for field in fields)))
    if active_only and hasattr(model,'status'):
        q=q.filter(~func.lower(func.coalesce(model.status,'')).in_(CLOSED))
    if entity=='leads':
        from .lead_models import CRMLeadOperatingState
        archived=select(CRMLeadOperatingState.lead_id).where(CRMLeadOperatingState.organization_id==org,CRMLeadOperatingState.data_json['archived'].as_boolean().is_(True))
        q=q.filter(~model.id.in_(archived))
        if active_only: q=q.filter(model.is_converted.is_(False))
    if kind:
        if item_id:
            from app.shared.catalog import item_record
            item_record(db,user,'crm',kind,item_id,archived=True)
        if entity=='deals': q=q.filter(deal_match(db,kind,item_id))
        else:
            target = [TARGETS[entity]] + (['account'] if entity=='companies' else [])
            links=select(CatalogLink.target_id).where(CatalogLink.organization_id==org,CatalogLink.target_type.in_(target),getattr(CatalogLink,kind+'_id').isnot(None))
            if item_id: links=links.where(getattr(CatalogLink,kind+'_id')==item_id)
            conditions=[model.id.in_(links)]
            # Show customers and contacts reached through their visible deals too.
            if sales.allowed(user,'deals','view'):
                deals=sales.rows(db,user,'deals',scope).filter(deal_match(db,kind,item_id))
                if entity=='companies': conditions.append(model.id.in_(deals.with_entities(CRMDeal.company_id)))
                if entity=='contacts':
                    conditions.append(model.id.in_(deals.with_entities(CRMDeal.contact_id)))
                    conditions.append(model.id.in_(select(CRMDealContact.contact_id).where(CRMDealContact.organization_id==org,CRMDealContact.deal_id.in_(deals.with_entities(CRMDeal.id)))))
                if entity=='leads': conditions.append(model.converted_deal_id.in_(deals.with_entities(CRMDeal.id)))
            q=q.filter(or_(*conditions))
    return q


def card(db,user,entity,row,due=None):
    item={'entity':entity,'id':row.id,'key':f'{entity}:{row.id}','name':getattr(row,'full_name',None) or getattr(row,'name',None), 'email':getattr(row,'email',None),'phone':getattr(row,'phone',None),'phone_country_code':getattr(row,'phone_country_code',None),'status':getattr(row,'status',None),'company':getattr(row,'company_name',None),'due':due,'can_edit':sales.allowed(user,entity,'manage'),'url':f'/crm/{entity}/{row.id}'}
    if item['can_edit']:
        resource=crm()._get_resource(entity)
        try:crm()._assert_write_scope(resource,{resource.owner_field:getattr(row,resource.owner_field,None)} if resource.owner_field else {},user,db)
        except HTTPException:item['can_edit']=False
    if entity=='deals':
        item.update(amount=str(row.amount or 0),currency=row.currency)
        if row.contact_id and sales.allowed(user,'contacts','view'):
            contact=sales.rows(db,user,'contacts').filter(CRMContact.id==row.contact_id).first()
            if contact: item.update(email=contact.email,phone=contact.phone,phone_country_code=contact.phone_country_code,contact_name=contact.full_name)
    return item


@router.get('/records')
def records(entity:Literal['all','leads','contacts','customers','customers_companies','companies','deals']='all',scope:Literal['all','mine','team']='all',kind:Literal['product','service']|None=None,item_id:int|None=Query(None,gt=0),search:str=Query('',max_length=150),bucket:Literal['all','overdue','today','upcoming','missing']='all',active_only:bool=False,occasion:Literal['all','birthday','anniversary']='all',timezone_name:str='Asia/Kolkata',page:int=Query(1,ge=1),per_page:int=Query(25,ge=1,le=200),owner_id:int|None=Query(None,gt=0),date_from:datetime|None=None,date_to:datetime|None=None,state:str|None=Query(None,max_length=16000),offerings:str|None=Query(None,max_length=5000),match:Literal['any','all']='any',audience:bool=False,include_analytics:bool=False,trend_days:int=Query(30,ge=7,le=90),trend_interval:Literal['daily','weekly','monthly']='daily',status:str=Query('',max_length=80),stage:str=Query('',max_length=100),branch_id:int|None=Query(None,gt=0),workspace_id:int|None=Query(None,gt=0),created_from:datetime|None=None,created_to:datetime|None=None,activity_from:datetime|None=None,deal_scope:Literal['all','active']='all',unassigned:bool=False,exporting:bool=False,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    grant=(getattr(user,'_suite_grants',None) or {}).get('crm')
    can_export=bool(user.is_superuser or grant is None or 'export' in grant.get('actions',[]))
    if exporting and not can_export:raise HTTPException(403,'CRM export permission is required')
    if item_id and not kind: raise HTTPException(422,'Choose product or service for the selected item')
    from . import growth_audience as audience_tools
    if trend_days not in (7,30,90):raise HTTPException(422,'Choose a 7, 30 or 90 day trend period')
    chosen=audience_tools.parse_offerings(offerings)
    use_audience=audience or include_analytics or bool(chosen) or bool(workspace_id) or unassigned
    if chosen and (kind or item_id): raise HTTPException(422,'Use either the multi-select offerings or the legacy single offering filter')
    if created_from and created_to and created_from>created_to: raise HTTPException(422,'Choose a valid creation date range')
    if chosen:
        from app.shared.catalog import item_record
        for selected_kind,selected_id in chosen:item_record(db,user,'crm',selected_kind,selected_id,archived=True)
    relations=audience_tools.offering_relations(db,user,scope) if use_audience else None
    tz=zone(timezone_name); now=datetime.now(timezone.utc); local=now.astimezone(tz)
    start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc); end=(local.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc)
    from app.shared.data_grid import GridField, parse_query, apply_filters
    parsed=parse_query(state) if state else None
    if parsed:
        page,per_page,search=parsed.page,parsed.pageSize,parsed.search
        if parsed.grouping: raise HTTPException(422,'Relationship grouping is not available; use the record type filter')
    if date_from and date_to and date_from>date_to:raise HTTPException(422,'Choose a valid follow-up date range')
    counts={}; buckets={key:0 for key in ('overdue','today','upcoming','missing')}; queries={}; combined=[]
    org=crm()._organization_id(db,user)
    for resource_name in ENTITIES:
        if not sales.allowed(user,resource_name,'view'): continue
        model=crm()._get_resource(resource_name).model
        q=filtered(db,user,resource_name,scope,kind,item_id,'' if use_audience else search.strip(),active_only)
        if use_audience:q=audience_tools.apply_audience(q,model,resource_name,relations,chosen,match,search.strip(),workspace_id)
        if branch_id:q=q.filter(model.branch_id==branch_id)
        if status:q=q.filter(model.status==status)
        if created_from:q=q.filter(model.created_at>=created_from)
        if created_to:q=q.filter(model.created_at<=created_to)
        due=due_expression(model,resource_name,org)
        activity_kind='account' if resource_name=='companies' else sales.record_kind(resource_name)
        activity_scope=[CRMActivity.organization_id==org,CRMActivity.entity_type==activity_kind,CRMActivity.entity_id==model.id]
        pending_owner=select(CRMActivity.owner_user_id).where(*activity_scope,CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).limit(1).correlate(model).scalar_subquery()
        pending_priority=select(CRMActivity.priority).where(*activity_scope,CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).limit(1).correlate(model).scalar_subquery()
        last_contact=select(func.max(CRMActivity.completed_at)).where(*activity_scope,CRMActivity.status=='Completed').correlate(model).scalar_subquery()
        if use_audience:
            from .models import CRMTimelineEvent
            recent=select(func.max(func.coalesce(CRMActivity.updated_at,CRMActivity.completed_at,CRMActivity.created_at))).where(*activity_scope).correlate(model).scalar_subquery()
            timeline=select(func.max(CRMTimelineEvent.occurred_at)).where(CRMTimelineEvent.organization_id==org,CRMTimelineEvent.record_type.in_([sales.record_kind(resource_name),resource_name,'account' if resource_name=='companies' else sales.record_kind(resource_name)]),CRMTimelineEvent.record_id==model.id).correlate(model).scalar_subquery()
            # CASE is portable to both SQLite and PostgreSQL, including null dates.
            last_contact=case((recent.is_(None),timeline),(timeline.is_(None),recent),(recent>=timeline,recent),else_=timeline)
        expressions={'entity':literal(resource_name),'id':model.id,'name':getattr(model,'full_name',getattr(model,'name',literal(None,String))),
            'status':getattr(model,'status',literal(None,String)),'email':getattr(model,'email',literal(None,String)),
            'phone':getattr(model,'phone',literal(None,String)),'company':getattr(model,'company_name',getattr(model,'name',literal(None,String))),
            'due':due,'owner_id':func.coalesce(pending_owner,getattr(model,'owner_user_id',literal(None))),
            'last_contact':func.coalesce(last_contact,getattr(model,'last_contacted_at',getattr(model,'last_activity_at',last_contact))),
            'priority':func.coalesce(pending_priority,getattr(model,'priority',literal(None,String)))}
        from .models import CRMPipelineStage
        from sqlalchemy import Numeric, DateTime
        expressions.update(created_at=model.created_at,
            amount=cast(getattr(model,'amount',literal(0)),Numeric(18,2)),currency=getattr(model,'currency',literal(None,String)),
            converted=case((getattr(model,'is_converted',literal(False)).is_(True),1),else_=0),
            converted_at=getattr(model,'converted_at',cast(literal(None),DateTime(timezone=True))),
            closed_at=func.coalesce(model.won_at,model.closed_at,model.actual_close_date) if resource_name=='deals' else cast(literal(None),DateTime(timezone=True)),
            stage=select(CRMPipelineStage.name).where(CRMPipelineStage.id==model.stage_id).correlate(model).scalar_subquery() if resource_name=='deals' else getattr(model,'status',literal(None,String)),
            customer=case((func.lower(model.lifecycle_stage)=='customer',1),else_=0) if resource_name=='contacts' else case((func.lower(model.account_type)=='customer',1),else_=0) if resource_name=='companies' else literal(0))
        if entity=='customers':q=q.filter(expressions['customer']==1)
        if entity=='customers_companies':q=q.filter(or_(literal(resource_name=='companies'),expressions['customer']==1))
        if stage:q=q.filter(expressions['stage']==stage)
        if activity_from:q=q.filter(expressions['last_contact']>=activity_from)
        if deal_scope=='active':q=q.filter(resource_name=='deals',~func.lower(model.status).in_(['won','lost','closed','cancelled']))
        if unassigned and relations is not None:q=q.filter(~select(1).select_from(relations).where(relations.c.entity==resource_name,relations.c.record_id==model.id).correlate(model).exists())
        if owner_id:q=q.filter(expressions['owner_id']==owner_id)
        if date_from:q=q.filter(due>=date_from)
        if date_to:q=q.filter(due<=date_to)
        if parsed:
            fields={key:GridField(value,'datetime' if key in {'due','last_contact','created_at','converted_at','closed_at'} else 'number' if key in {'amount','converted','customer'} else 'id' if key in {'id','owner_id'} else 'text',groupable=False) for key,value in expressions.items()}
            q=apply_filters(q,parsed,fields)
        if occasion!='all':
            date=getattr(model,'date_of_birth' if occasion=='birthday' else 'customer_since',None)
            q=q.filter(func.extract('month',date)==local.month,func.extract('day',date)==local.day) if date is not None else q.filter(False)
        bucket_clauses=[('overdue',due<start),('today',(due>=start)&(due<end)),('upcoming',due>=end),('missing',due.is_(None))]
        summary=q.with_entities(func.count(model.id),*(func.sum(case((clause,1),else_=0)) for _,clause in bucket_clauses)).order_by(None).one()
        counts[resource_name]=summary[0]
        if entity not in ('all','customers','customers_companies') and entity!=resource_name: continue
        for index,(key,clause) in enumerate(bucket_clauses,1):
            buckets[key]+=summary[index] or 0
            if bucket==key: selected=clause
        if bucket!='all': q=q.filter(selected)
        queries[resource_name]=q
        combined.append(q.with_entities(*(value.label(key) for key,value in expressions.items())).statement)
    if not queries: raise HTTPException(403,'CRM record access is required')
    selection=union_all(*combined).subquery()
    total=db.scalar(select(func.count()).select_from(selection)) or 0
    sorting=[(selection.c[sort.id].desc() if sort.desc else selection.c[sort.id].asc()).nullslast() for sort in parsed.sorting] if parsed else []
    found=db.execute(select(selection).order_by(*sorting,selection.c.due.is_(None),selection.c.due,selection.c.entity,selection.c.id).offset((page-1)*per_page).limit(per_page)).all()
    items=[]
    for name in queries:
        ids=[r.id for r in found if r.entity==name]
        if not ids: continue
        model=crm()._get_resource(name).model
        rows={r.id:r for r in queries[name].filter(model.id.in_(ids)).all()}
        items.extend(card(db,user,name,rows[r.id],r.due) for r in found if r.entity==name and r.id in rows)
    order={(r.entity,r.id):i for i,r in enumerate(found)}
    items.sort(key=lambda row:order[(row['entity'],row['id'])])
    extra={(r.entity,r.id):r for r in found}
    owners={r.owner_id for r in found if r.owner_id}
    owner_names={r.id:r.email for r in db.query(User).filter(User.id.in_(owners))} if owners else {}
    for item in items:
        values=extra[(item['entity'],item['id'])]
        item.update(owner_id=values.owner_id,owner_name=owner_names.get(values.owner_id,'Unassigned'),last_contact=values.last_contact,priority=values.priority,stage=values.stage,created_at=values.created_at,customer=bool(values.customer))
    result={'can_create':{entity:sales.allowed(user,entity,'manage') for entity in ENTITIES},'can_export':can_export,'items':items,'total':total,'page':page,'pages':(total+per_page-1)//per_page,'counts':counts,'buckets':buckets}
    if use_audience:
        audience_tools.enrich(db,items,relations)
        result['counts']={r.entity:r.n for r in db.execute(select(selection.c.entity,func.count().label('n')).group_by(selection.c.entity))}
        result['buckets']={key:db.scalar(select(func.count()).select_from(selection).where(clause)) or 0 for key,clause in [('overdue',selection.c.due<start),('today',(selection.c.due>=start)&(selection.c.due<end)),('upcoming',selection.c.due>=end),('missing',selection.c.due.is_(None))]}
        if include_analytics:result['analytics']=audience_tools.analytics(db,selection,relations,trend_days,trend_interval)
    return result


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class FollowUp(Strict):
    entity:Entity
    record_id:int=Field(gt=0)
    action:Literal['schedule','complete']='schedule'
    activity_id:int|None=None
    due_at:datetime|None=None
    title:str=Field(default='Customer follow-up',min_length=1,max_length=220)
    channel:Literal['call','email','whatsapp','sms','meeting','visit','other']='call'
    notes:str=Field(default='',max_length=4000)
    outcome:str=Field(default='',max_length=120)
    owner_id:int|None=Field(default=None,gt=0)
    priority:Literal['High','Medium','Low']|None=None
    reminder_at:datetime|None=None
    next_action:str=Field(default='',max_length=1000)
    offering_kind:Literal['product','service']|None=None
    offering_id:int|None=Field(default=None,gt=0)
    activity_version:datetime|None=None


@router.post('/follow-up')
def follow_up(data:FollowUp,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return save_follow_up(data,db,user)


def save_follow_up(data,db,user,commit=True):
    core=crm(); core._assert_entity_permission(data.entity,user,'manage')
    model=core._get_resource(data.entity).model
    row=sales.rows(db,user,data.entity,lock=True).filter(model.id==data.record_id).first()
    if not row: raise HTTPException(404,'Record not found in your permitted scope')
    resource=core._get_resource(data.entity)
    core._assert_write_scope(resource,{resource.owner_field:getattr(row,resource.owner_field,None)} if resource.owner_field else {},user,db)
    org=core._organization_id(db,user); kind='account' if data.entity=='companies' else sales.record_kind(data.entity)
    if data.owner_id:sales.lm.check_owner(db,user,data.owner_id)
    if data.offering_id:
        if not data.offering_kind:raise HTTPException(422,'Choose a product or service type')
        from app.shared.catalog import item_record
        item_record(db,user,'crm',data.offering_kind,data.offering_id)
    if data.reminder_at and (data.reminder_at.utcoffset() is None or data.reminder_at<=datetime.now(timezone.utc) or data.due_at and data.reminder_at>data.due_at):raise HTTPException(422,'Choose a future reminder before the follow-up')
    if data.due_at and (data.due_at.utcoffset() is None or data.due_at<=datetime.now(timezone.utc)): raise HTTPException(422,'Choose a future follow-up time including its time zone')
    activity=None
    if data.activity_id:
        activity=db.query(CRMActivity).filter_by(id=data.activity_id,organization_id=org,entity_type=kind,entity_id=row.id).with_for_update().first()
        if not activity or activity.status not in sales.OPEN_ACTIVITY or activity.activity_type=='greeting_batch': raise HTTPException(409,'This follow-up changed. Refresh before updating it.')
        if data.activity_version:
            actual=activity.updated_at or activity.created_at
            if actual and actual.replace(tzinfo=actual.tzinfo or timezone.utc)!=data.activity_version:raise HTTPException(409,'This follow-up changed. Refresh before updating it.')
    if data.action=='complete':
        if not activity: raise HTTPException(422,'Choose a pending follow-up to complete')
        if not data.outcome.strip(): raise HTTPException(422,'Record the outcome before completing this follow-up')
        activity.status='Completed'; activity.completed_at=datetime.now(timezone.utc); activity.outcome=data.outcome+'\n'+data.notes
        activity=None
    elif not data.due_at: raise HTTPException(422,'Choose the next follow-up date and time')
    if data.due_at:
        if not activity:
            field=core.ENTITY_FIELD_BY_TYPE.get(kind)
            activity=CRMActivity(organization_id=org,owner_user_id=getattr(row,'owner_user_id',None) or user.id,entity_type=kind,entity_id=row.id,created_by_user_id=user.id,**({field:row.id} if field else {})); db.add(activity)
        activity.title=data.title; activity.subject=data.title[:180]; activity.activity_type=data.channel; activity.status='Scheduled'; activity.due_date=data.due_at; activity.description=data.notes
        if data.owner_id:activity.owner_user_id=data.owner_id
        if data.priority:activity.priority=data.priority
        previous=activity.metadata_json or {}
        reminder=data.reminder_at.astimezone(timezone.utc).isoformat() if data.reminder_at else None
        offering={'offering_kind':data.offering_kind if data.offering_id else None,'offering_id':data.offering_id} if 'offering_id' in data.model_fields_set else {}
        activity.metadata_json={**previous,'next_action':data.next_action,'reminder_at':reminder,'reminded_at':previous.get('reminded_at') if reminder==previous.get('reminder_at') else None,**offering}
    core._create_timeline_activity(db,organization_id=org,entity_type=kind,entity_id=row.id,activity_type='follow_up_update',title='Follow-up completed' if data.action=='complete' else 'Follow-up scheduled',body=data.notes,user_id=user.id,metadata={'outcome':data.outcome,'nextFollowUp':data.due_at.isoformat() if data.due_at else None})
    db.flush()
    if hasattr(row,'next_follow_up_at'):
        row.next_follow_up_at=db.query(func.min(CRMActivity.due_date)).filter(CRMActivity.organization_id==org,CRMActivity.entity_type==kind,CRMActivity.entity_id==row.id,CRMActivity.status.in_(sales.OPEN_ACTIVITY)).scalar()
    if commit:db.commit()
    return {'message':'Follow-up saved','activity_id':activity.id if activity else None}


@router.get('/pending/{entity}/{record_id}')
def pending(entity:Entity,record_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    model=crm()._get_resource(entity).model
    if not sales.rows(db,user,entity).filter(model.id==record_id).first(): raise HTTPException(404,'Record not found')
    rows=db.query(CRMActivity).filter_by(organization_id=crm()._organization_id(db,user),entity_type='account' if entity=='companies' else sales.record_kind(entity),entity_id=record_id).filter(CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).all()
    return {'items':[{'id':r.id,'title':r.title,'due_at':r.due_date,'channel':r.activity_type,'notes':r.description,'priority':r.priority,'owner_id':r.owner_user_id,'metadata':r.metadata_json or {},'version':r.updated_at or r.created_at} for r in rows]}


@router.get('/files/{entity}/{record_id}')
def relationship_files(entity:Entity,record_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    resource=crm()._get_resource(entity)
    if not sales.rows(db,user,entity).filter(resource.model.id==record_id).first():raise HTTPException(404,'Record not found')
    field={'leads':'lead_id','contacts':'contact_id','companies':'company_id','deals':'deal_id'}[entity]
    files=sales.rows(db,user,'files').filter(getattr(crm()._get_resource('files').model,field)==record_id).order_by(crm()._get_resource('files').model.id.desc()).limit(100).all()
    return {'items':[{'id':r.id,'name':r.original_name,'size':r.size_bytes,'created_at':r.created_at,'url':f'/crm/file-workspace/files/{r.id}/download'} for r in files]}


def scheduled_relationship_reminders(db,org,limit=200):
    """In-app reminders through the existing protected CRM scheduler."""
    from app.models.notification import Notification,NotificationDeliveryLog
    from app.branches.models import BranchOwnership
    from app.branches.service import context as branch_context
    at=datetime.now(timezone.utc)
    activities=db.query(CRMActivity).filter(CRMActivity.organization_id==org,CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.metadata_json['reminder_at'].as_string()<=at.isoformat(),CRMActivity.metadata_json['reminded_at'].as_string().is_(None)).order_by(CRMActivity.id).limit(limit).with_for_update(skip_locked=True).all()
    count=0
    for activity in activities:
        recipient=db.get(User,activity.owner_user_id) if activity.owner_user_id else None
        entity={'lead':'leads','contact':'contacts','account':'companies','company':'companies','deal':'deals'}.get(activity.entity_type)
        if not recipient or not recipient.is_active or not entity:continue
        try:
            branch=db.query(BranchOwnership.branch_id).filter_by(resource_table='crm_activities',resource_key=str(activity.id),company_id=org).scalar()
            if not branch:continue
            branch_context(db,recipient,org,str(branch))
            resource=crm()._get_resource(entity)
            if not sales.rows(db,recipient,entity).filter(resource.model.id==activity.entity_id).first():continue
        except HTTPException:continue
        notification=Notification(company_id=org,user_id=recipient.id,module='crm',event_type='relationship_follow_up_reminder',title='Upcoming CRM follow-up',message=activity.subject,related_entity_type=activity.entity_type,related_entity_id=activity.entity_id,action_url=f'/crm/customer-follow-ups?entity={entity}&record_id={activity.entity_id}',priority='high' if activity.priority=='High' else 'normal')
        db.add(notification);db.flush()
        # The background worker has no request-bound branch hooks. Stamp its
        # notification from the verified activity so the assignee can see it.
        if not db.query(BranchOwnership).filter_by(resource_table='notifications',resource_key=str(notification.id),company_id=org).first():
            db.add(BranchOwnership(resource_table='notifications',resource_key=str(notification.id),company_id=org,branch_id=branch,source='crm-reminder'))
        receipt=NotificationDeliveryLog(notification_id=notification.id,channel='in_app',status='delivered',delivered_at=at)
        db.add(receipt);db.flush()
        if not db.query(BranchOwnership).filter_by(resource_table='notification_delivery_logs',resource_key=str(receipt.id),company_id=org).first():
            db.add(BranchOwnership(resource_table='notification_delivery_logs',resource_key=str(receipt.id),company_id=org,branch_id=branch,source='crm-reminder'))
        activity.metadata_json={**activity.metadata_json,'reminded_at':at.isoformat()};count+=1
    return count


def dispatch_relationship_reminders(db,limit=200):
    organizations=db.query(CRMActivity.organization_id).filter(CRMActivity.organization_id.is_not(None),CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.metadata_json['reminder_at'].as_string().isnot(None),CRMActivity.metadata_json['reminded_at'].as_string().is_(None)).distinct().all()
    count=sum(scheduled_relationship_reminders(db,org,limit) for (org,) in organizations)
    db.commit()
    return count


class Recipient(Strict):
    entity:Entity
    id:int=Field(gt=0)


class RelationshipExport(Strict):
    format:Literal['csv','clipboard','xlsx','pdf']='csv'
    recipients:list[Recipient]=Field(max_length=20000)
    columns:list[str]=Field(min_length=1,max_length=12)
    summary:bool=False


@router.post('/export')
def export_relationships(data:RelationshipExport,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    grant=(getattr(user,'_suite_grants',None) or {}).get('crm')
    if not user.is_superuser and grant is not None and 'export' not in grant.get('actions',[]):raise HTTPException(403,'CRM export permission is required')
    import csv,io
    from fastapi.responses import Response
    from app.shared.data_grid import safe_cell
    headings={'name':'Relationship','entity':'Type','company':'Company','email':'Email','phone':'Phone','due':'Next conversation','owner_id':'Assigned employee','priority':'Priority','last_contact':'Last contact','status':'Status'}
    if any(key not in headings for key in data.columns):raise HTTPException(422,'Unsupported export column')
    if data.format=='pdf' and len(data.recipients)>2000:raise HTTPException(422,'PDF exports support at most 2,000 relationships')
    org=crm()._organization_id(db,user);found={}
    for entity in ENTITIES:
        ids={r.id for r in data.recipients if r.entity==entity}
        if not ids:continue
        model=crm()._get_resource(entity).model
        due=due_expression(model,entity,org)
        for row,next_due in sales.rows(db,user,entity).filter(model.id.in_(ids)).with_entities(model,due).all():
            found[(entity,row.id)]={**card(db,user,entity,row,next_due),'owner_id':getattr(row,'owner_user_id',None),'priority':getattr(row,'priority',None)}
    if any((r.entity,r.id) not in found for r in data.recipients):raise HTTPException(404,'An exported relationship is no longer in your permitted scope')
    activities=db.query(CRMActivity).filter(CRMActivity.organization_id==org,or_(*[( (CRMActivity.entity_type==('account' if entity=='companies' else sales.record_kind(entity))) & CRMActivity.entity_id.in_([r.id for r in data.recipients if r.entity==entity])) for entity in ENTITIES if any(r.entity==entity for r in data.recipients)])).order_by(CRMActivity.due_date.asc().nullslast(),CRMActivity.id).all() if data.recipients else []
    from collections import defaultdict
    by_record=defaultdict(list)
    for activity in activities:by_record[(activity.entity_type,activity.entity_id)].append(activity)
    for (entity,ident),item in found.items():
        kind='account' if entity=='companies' else sales.record_kind(entity)
        related=by_record[(kind,ident)]
        pending=next((a for a in related if a.status in sales.OPEN_ACTIVITY and a.due_date),None)
        item['owner_id']=pending.owner_user_id if pending else item['owner_id'];item['priority']=pending.priority if pending else item['priority']
        item['last_contact']=max((a.completed_at for a in related if a.completed_at),default=None)
    owners={row.id:row.email for row in db.query(User).filter(User.id.in_({item['owner_id'] for item in found.values() if item['owner_id']}))}
    table=[[headings[key] for key in data.columns]]
    for recipient in data.recipients:
        row=found[(recipient.entity,recipient.id)]
        table.append([safe_cell(owners.get(row.get('owner_id'),'Unassigned') if key=='owner_id' else row.get(key)) for key in data.columns])
    if data.summary:table.append([f'{len(data.recipients)} relationships']+['']*(len(data.columns)-1))
    if data.format=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill
        book=Workbook();sheet=book.active;sheet.title='Follow-ups'
        for row in table:sheet.append(row)
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='7426ED')
        for column in sheet.columns:sheet.column_dimensions[column[0].column_letter].width=28
        output=io.BytesIO();book.save(output);content=output.getvalue();mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif data.format=='pdf':
        from reportlab.platypus import SimpleDocTemplate,LongTable,TableStyle,Paragraph
        from reportlab.lib.pagesizes import A4,landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
        styles=getSampleStyleSheet();styles['BodyText'].fontSize=7;styles['BodyText'].leading=10
        rendered=[[Paragraph(escape(str(value or '')),styles['BodyText']) for value in row] for row in table]
        report=LongTable(rendered,repeatRows=1,colWidths=[(landscape(A4)[0]-48)/len(data.columns)]*len(data.columns))
        report.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#ede2ff')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8f6ff')])]))
        output=io.BytesIO();SimpleDocTemplate(output,pagesize=landscape(A4),leftMargin=24,rightMargin=24).build([Paragraph('CRM relationship follow-ups',styles['Title']),report]);content=output.getvalue();mime='application/pdf'
    else:
        output=io.StringIO();csv.writer(output,delimiter='\t' if data.format=='clipboard' else ',').writerows(table)
        content=output.getvalue();mime='text/tab-separated-values' if data.format=='clipboard' else 'text/csv'
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="follow-ups.{data.format}"','Cache-Control':'private, no-store'})


class BulkFollowUp(Strict):
    recipients:list[Recipient]=Field(min_length=1,max_length=50)
    action:Literal['schedule','assign']
    owner_id:int|None=Field(default=None,gt=0)
    due_at:datetime|None=None
    request_id:UUID


@router.post('/follow-ups/bulk')
def bulk_follow_ups(data:BulkFollowUp,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if len({(r.entity,r.id) for r in data.recipients})!=len(data.recipients):raise HTTPException(422,'Choose each relationship once')
    if data.action=='assign' and not data.owner_id:raise HTTPException(422,'Choose an assigned employee')
    if data.action=='schedule' and not data.due_at:raise HTTPException(422,'Choose a follow-up date')
    signature=hashlib.sha256(data.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
    org=crm()._organization_id(db,user); results=[]
    for recipient in data.recipients:
        savepoint=db.begin_nested()
        try:
            core=crm();core._assert_entity_permission(recipient.entity,user,'manage')
            resource=core._get_resource(recipient.entity)
            row=sales.rows(db,user,recipient.entity,lock=True).filter(resource.model.id==recipient.id).first()
            if not row:raise HTTPException(404,'Record not found in your permitted scope')
            core._assert_write_scope(resource,{resource.owner_field:getattr(row,resource.owner_field,None)} if resource.owner_field else {},user,db)
            if data.owner_id:sales.lm.check_owner(db,user,data.owner_id)
            kind='account' if recipient.entity=='companies' else sales.record_kind(recipient.entity)
            activity_query=db.query(CRMActivity).filter_by(organization_id=org,entity_type=kind,entity_id=row.id)
            replay=activity_query.filter(CRMActivity.created_by_user_id==user.id,CRMActivity.metadata_json['bulk_request'].as_string()==str(data.request_id)).first()
            if replay:
                if (replay.metadata_json or {}).get('bulk_signature')!=signature:raise HTTPException(409,'Request identifier was already used for another operation')
                savepoint.commit();results.append({'key':f'{recipient.entity}:{recipient.id}','saved':True,'replayed':True});continue
            if data.action=='assign':
                activities=activity_query.filter(CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).with_for_update().all()
                if not activities:raise HTTPException(422,'Schedule a follow-up before assigning it')
                for activity in activities:activity.owner_user_id=data.owner_id
                core._create_timeline_activity(db,organization_id=org,entity_type=kind,entity_id=row.id,activity_type='follow_up_assignment',title='Follow-ups reassigned',body='Assigned employee updated',user_id=user.id,metadata={'bulk_request':str(data.request_id),'bulk_signature':signature,'owner_id':data.owner_id})
                savepoint.commit();db.commit()
            else:
                result=save_follow_up(FollowUp(entity=recipient.entity,record_id=row.id,due_at=data.due_at,owner_id=data.owner_id,title='Follow up with '+(getattr(row,'full_name',None) or getattr(row,'name','relationship'))),db,user,commit=False)
                activity=db.get(CRMActivity,result['activity_id'])
                activity.metadata_json={**(activity.metadata_json or {}),'bulk_request':str(data.request_id),'bulk_signature':signature};savepoint.commit();db.commit()
            results.append({'key':f'{recipient.entity}:{recipient.id}','saved':True})
        except HTTPException as error:
            if savepoint.is_active:savepoint.rollback()
            results.append({'key':f'{recipient.entity}:{recipient.id}','saved':False,'message':error.detail})
    return {'items':results,'saved':sum(r['saved'] for r in results)}


class Greeting(Strict):
    recipients:list[Recipient]=Field(min_length=1,max_length=50)
    channel:Channel='email'
    occasion:str=Field(default='Greeting',max_length=100)
    subject:str=Field(default='A greeting for {{name}}',min_length=1,max_length=240)
    body:str=Field(min_length=1,max_length=4000)
    product_name:str=Field(default='',max_length=180)


class GreetingSend(Greeting):
    preview_token:str
    request_id:UUID


def outreach(db,user,data):
    from app.apps.communication.models import CommunicationConsent
    from app.apps.communication.services.delivery import is_opted_out
    output=[];seen=set();org=crm()._organization_id(db,user)
    if not data.body.strip() or not data.subject.strip(): raise HTTPException(422,'Enter a greeting subject and message')
    unknown={value.strip() for value in re.findall(r'{{([^{}]+)}}',data.body+' '+data.subject)} - {'name','company','product','sender'}
    if unknown: raise HTTPException(422,'Unknown greeting placeholders: '+', '.join(sorted(unknown)))
    for target in data.recipients:
        model=crm()._get_resource(target.entity).model
        row=sales.rows(db,user,target.entity).filter(model.id==target.id).first()
        if not row: raise HTTPException(404,'A selected recipient is no longer in your permitted scope')
        item=card(db,user,target.entity,row)
        variables={'name':item.get('contact_name') or item['name'],'company':item.get('company') or item['name'] if target.entity=='companies' else item.get('company') or '', 'product':data.product_name,'sender':getattr(user,'name',None) or user.email}
        def render(text): return re.sub(r'{{\s*(name|company|product|sender)\s*}}',lambda m:str(variables[m.group(1)] or ''),text)
        destination=item.get('email') or ''
        reason=''
        if data.channel!='email':
            try: destination=calling_code(item.get('phone_country_code'))+national_phone(item.get('phone'))
            except (ValueError,TypeError): destination='';reason='A valid phone number and country code are required'
        elif not destination: reason='No email address recorded'
        if str(item.get('status') or '').lower()=='do not contact': reason='Marked Do Not Contact'
        phone_match=(CommunicationConsent.phone==item.get('phone'))&(CommunicationConsent.phone_country_code==item.get('phone_country_code')) if item.get('phone') else False
        preferences=db.query(CommunicationConsent).filter(CommunicationConsent.consent_type==data.channel,or_((CommunicationConsent.record_type==sales.record_kind(target.entity))&(CommunicationConsent.record_id==target.id),CommunicationConsent.email==item.get('email') if item.get('email') else False,phone_match)).order_by(CommunicationConsent.updated_at.desc()).all()
        if any(p.status in {'opted_out','unsubscribed','denied'} for p in preferences): reason='Customer has opted out of this channel'
        if destination and is_opted_out(db,destination,data.channel): reason='Customer has opted out of '+data.channel
        key=destination.strip().lower()
        if key and key in seen: reason='Duplicate destination already selected'
        if key: seen.add(key)
        body=render(data.body);subject=render(data.subject)
        url=f'https://wa.me/{destination.lstrip("+")}?text={quote(body)}' if data.channel=='whatsapp' else f'sms:{destination}?body={quote(body)}' if data.channel=='sms' else f'mailto:{quote(destination)}?subject={quote(subject)}&body={quote(body)}'
        output.append({**item,'destination':destination,'body':body,'subject':subject,'eligible':not bool(reason),'reason':reason,'compose_url':url})
    return output


def email_ready():
    from app.core.email import email_configured
    from app.apps.communication.services.delivery import configured_email_provider
    provider=configured_email_provider()
    return (provider in {'smtp','ses'} and email_configured()) or (provider=='stub' and settings.ENVIRONMENT in {'test','development','local'})


def signature(user,data,items,expiry):
    payload={'user':user.id,'org':getattr(user,'organization_id',None),'expiry':expiry,'data':data.model_dump(mode='json',exclude={'preview_token','request_id'}),'recipients':[{k:r[k] for k in ('entity','id','destination','body','subject','eligible','reason')} for r in items]}
    return hmac.new(settings.SECRET_KEY.encode(),json.dumps(payload,sort_keys=True).encode(),hashlib.sha256).hexdigest()


@router.post('/greetings/preview')
def greeting_preview(data:Greeting,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    items=outreach(db,user,data);expiry=int((datetime.now(timezone.utc)+timedelta(minutes=15)).timestamp())
    ready=data.channel=='email' and email_ready()
    permitted=all(sales.allowed(user,r['entity'],'manage') for r in items if r['eligible'])
    from app.apps.communication.services.delivery import configured_email_provider
    simulated=ready and configured_email_provider()=='stub'
    if simulated: note='Test email provider: these messages are simulated and will not reach customers.'
    elif ready and permitted: note='Send through the connected email provider.'
    elif ready: note='Your CRM role does not allow provider sending. You can review or open a draft.'
    elif data.channel=='email': note='Email delivery is not connected. Open a draft in your email app.'
    else: note=f'Open each personalized {data.channel.title()} draft and send it in that app. Opening a draft is not delivery.'
    return {'items':items,'eligible':sum(r['eligible'] for r in items),'blocked':sum(not r['eligible'] for r in items),'preview_token':f'{expiry}.{signature(user,data,items,expiry)}','can_send':ready and permitted,'simulation':simulated,'delivery_mode':'simulation' if simulated else 'email_provider' if ready and permitted else 'external_draft','channel_note':note}


@router.post('/greetings/send')
def send_greetings(data:GreetingSend,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if data.channel!='email' or not email_ready(): raise HTTPException(409,'Use the channel draft buttons, or connect email delivery before sending')
    items=outreach(db,user,data)
    try: expiry,digest=data.preview_token.split('.',1);expiry=int(expiry)
    except (ValueError,TypeError): raise HTTPException(409,'Preview the recipients and message before sending')
    if expiry<int(datetime.now(timezone.utc).timestamp()) or not hmac.compare_digest(digest,signature(user,data,items,expiry)): raise HTTPException(409,'Recipients or content changed. Review a fresh preview before sending')
    for target in data.recipients:
        core=crm();core._assert_entity_permission(target.entity,user,'manage')
        resource=core._get_resource(target.entity)
        record=sales.rows(db,user,target.entity).filter(resource.model.id==target.id).first()
        core._assert_write_scope(resource,{resource.owner_field:getattr(record,resource.owner_field,None)} if resource.owner_field else {},user,db)
    eligible=[r for r in items if r['eligible']]
    if not eligible: raise HTTPException(422,'No eligible recipients selected')
    # A persisted journal prevents a browser retry from sending the same batch twice.
    db.query(User).filter_by(id=user.id).with_for_update().one()
    org=crm()._organization_id(db,user);request_id=str(data.request_id)
    marker=db.query(CRMActivity).filter(CRMActivity.organization_id==org,CRMActivity.created_by_user_id==user.id,CRMActivity.activity_type=='greeting_batch',CRMActivity.metadata_json['request_id'].as_string()==request_id).with_for_update().first()
    if marker:
        meta=marker.metadata_json or {}
        if meta.get('signature')!=digest: raise HTTPException(409,'This request was already used for a different greeting')
        if marker.status!='Completed': raise HTTPException(409,'This batch is already processing. Check the delivery log before trying again')
        return {'results':meta.get('results',[]),'replayed':True}
    first=eligible[0]
    marker=CRMActivity(organization_id=org,owner_user_id=user.id,created_by_user_id=user.id,entity_type=sales.record_kind(first['entity']),entity_id=first['id'],activity_type='greeting_batch',title=data.occasion+' greetings',subject=data.occasion+' greetings',status='In Progress',metadata_json={'request_id':request_id,'signature':digest,'results':[]})
    db.add(marker);db.commit();db.refresh(marker)
    from app.apps.communication.models import CommunicationEmailMessage
    from app.apps.communication.services.delivery import deliver_email
    results=[]
    for item in items:
        result={'key':item['key'],'status':'skipped','reason':item['reason']}
        if item['eligible']:
            message=CommunicationEmailMessage(organization_id=org,related_record_type=sales.record_kind(item['entity']),related_record_id=item['id'],to_email=item['destination'],subject=item['subject'],body=item['body'],status='queued',sent_by=user.id)
            db.add(message);db.flush()
            try:
                deliver_email(db,message,user)
            except Exception:
                message.status='failed';message.error_message='Provider could not confirm delivery. Check the delivery log before retrying.'
            result.update(status=message.status,reason=message.error_message or '',message_id=message.id)
        results.append(result)
        marker.metadata_json={**marker.metadata_json,'results':list(results)}
        db.commit()
    marker.status='Completed';db.commit()
    return {'results':results,'replayed':False}
