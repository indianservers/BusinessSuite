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
from sqlalchemy import String, cast, exists, func, literal, or_, select, union_all
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
    if entity=='deals':
        item.update(amount=str(row.amount or 0),currency=row.currency)
        if row.contact_id and sales.allowed(user,'contacts','view'):
            contact=sales.rows(db,user,'contacts').filter(CRMContact.id==row.contact_id).first()
            if contact: item.update(email=contact.email,phone=contact.phone,phone_country_code=contact.phone_country_code,contact_name=contact.full_name)
    return item


@router.get('/records')
def records(entity:Literal['all','leads','contacts','companies','deals']='all',scope:Literal['all','mine','team']='all',kind:Literal['product','service']|None=None,item_id:int|None=Query(None,gt=0),search:str=Query('',max_length=150),bucket:Literal['all','overdue','today','upcoming','missing']='all',active_only:bool=False,occasion:Literal['all','birthday','anniversary']='all',timezone_name:str='Asia/Kolkata',page:int=Query(1,ge=1),per_page:int=Query(25,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if item_id and not kind: raise HTTPException(422,'Choose product or service for the selected item')
    tz=zone(timezone_name); now=datetime.now(timezone.utc); local=now.astimezone(tz)
    start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc); end=(local.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc)
    counts={}; buckets={key:0 for key in ('overdue','today','upcoming','missing')}; queries={}; combined=[]
    org=crm()._organization_id(db,user)
    for resource_name in ENTITIES:
        if not sales.allowed(user,resource_name,'view'): continue
        model=crm()._get_resource(resource_name).model
        q=filtered(db,user,resource_name,scope,kind,item_id,search.strip(),active_only)
        due=due_expression(model,resource_name,org)
        if occasion!='all':
            date=getattr(model,'date_of_birth' if occasion=='birthday' else 'customer_since',None)
            q=q.filter(func.extract('month',date)==local.month,func.extract('day',date)==local.day) if date is not None else q.filter(False)
        counts[resource_name]=q.count()
        if entity!='all' and entity!=resource_name: continue
        for key,clause in [('overdue',due<start),('today',(due>=start)&(due<end)),('upcoming',due>=end),('missing',due.is_(None))]:
            buckets[key]+=q.filter(clause).count()
            if bucket==key: selected=clause
        if bucket!='all': q=q.filter(selected)
        queries[resource_name]=q
        combined.append(q.with_entities(literal(resource_name).label('entity'),model.id.label('id'),due.label('due')).statement)
    if not queries: raise HTTPException(403,'CRM record access is required')
    selection=union_all(*combined).subquery()
    total=db.scalar(select(func.count()).select_from(selection)) or 0
    found=db.execute(select(selection).order_by(selection.c.due.is_(None),selection.c.due,selection.c.entity,selection.c.id).offset((page-1)*per_page).limit(per_page)).all()
    items=[]
    for name in queries:
        ids=[r.id for r in found if r.entity==name]
        if not ids: continue
        model=crm()._get_resource(name).model
        rows={r.id:r for r in queries[name].filter(model.id.in_(ids)).all()}
        items.extend(card(db,user,name,rows[r.id],r.due) for r in found if r.entity==name and r.id in rows)
    order={(r.entity,r.id):i for i,r in enumerate(found)}
    items.sort(key=lambda row:order[(row['entity'],row['id'])])
    return {'items':items,'total':total,'page':page,'pages':(total+per_page-1)//per_page,'counts':counts,'buckets':buckets}


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class FollowUp(Strict):
    entity:Entity
    record_id:int=Field(gt=0)
    action:Literal['schedule','complete']='schedule'
    activity_id:int|None=None
    due_at:datetime|None=None
    title:str=Field(default='Customer follow-up',min_length=1,max_length=220)
    channel:Literal['call','email','whatsapp','sms','meeting']='call'
    notes:str=Field(default='',max_length=4000)
    outcome:str=Field(default='',max_length=120)


@router.post('/follow-up')
def follow_up(data:FollowUp,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    core=crm(); core._assert_entity_permission(data.entity,user,'manage')
    model=core._get_resource(data.entity).model
    row=sales.rows(db,user,data.entity,lock=True).filter(model.id==data.record_id).first()
    if not row: raise HTTPException(404,'Record not found in your permitted scope')
    resource=core._get_resource(data.entity)
    core._assert_write_scope(resource,{resource.owner_field:getattr(row,resource.owner_field,None)} if resource.owner_field else {},user,db)
    org=core._organization_id(db,user); kind='account' if data.entity=='companies' else sales.record_kind(data.entity)
    if data.due_at and (data.due_at.utcoffset() is None or data.due_at<=datetime.now(timezone.utc)): raise HTTPException(422,'Choose a future follow-up time including its time zone')
    activity=None
    if data.activity_id:
        activity=db.query(CRMActivity).filter_by(id=data.activity_id,organization_id=org,entity_type=kind,entity_id=row.id).with_for_update().first()
        if not activity or activity.status not in sales.OPEN_ACTIVITY or activity.activity_type=='greeting_batch': raise HTTPException(409,'This follow-up changed. Refresh before updating it.')
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
        activity.title=data.title; activity.subject=data.title; activity.activity_type=data.channel; activity.status='Scheduled'; activity.due_date=data.due_at; activity.description=data.notes
    core._create_timeline_activity(db,organization_id=org,entity_type=kind,entity_id=row.id,activity_type='follow_up_update',title='Follow-up completed' if data.action=='complete' else 'Follow-up scheduled',body=data.notes,user_id=user.id,metadata={'outcome':data.outcome,'nextFollowUp':data.due_at.isoformat() if data.due_at else None})
    db.flush()
    if hasattr(row,'next_follow_up_at'):
        row.next_follow_up_at=db.query(func.min(CRMActivity.due_date)).filter(CRMActivity.organization_id==org,CRMActivity.entity_type==kind,CRMActivity.entity_id==row.id,CRMActivity.status.in_(sales.OPEN_ACTIVITY)).scalar()
    db.commit()
    return {'message':'Follow-up saved','activity_id':activity.id if activity else None}


@router.get('/pending/{entity}/{record_id}')
def pending(entity:Entity,record_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    model=crm()._get_resource(entity).model
    if not sales.rows(db,user,entity).filter(model.id==record_id).first(): raise HTTPException(404,'Record not found')
    rows=db.query(CRMActivity).filter_by(organization_id=crm()._organization_id(db,user),entity_type='account' if entity=='companies' else sales.record_kind(entity),entity_id=record_id).filter(CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).all()
    return {'items':[{'id':r.id,'title':r.title,'due_at':r.due_date,'channel':r.activity_type} for r in rows]}


class Recipient(Strict):
    entity:Entity
    id:int=Field(gt=0)


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
