"""Permission-checked customer inbox, work queues and chronological channel history."""
from datetime import datetime, timedelta, timezone
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, func, cast, String
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.deps import get_db, RequirePermission
from app.access.catalog import permission_names
from app.models.user import User
from app.services import whatsapp_workspace as wa
from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage, WhatsAppReceipt
from .customer_models import CustomerRecipient, CustomerBinding, CustomerEmailReply, CustomerDelivery
from .models import CommunicationEmailMessage, CommunicationEmailAttachment, CommunicationDeliveryLog
from .engagement_models import ConversationWorkflow, ConversationReading

router = APIRouter(prefix='/communication/engagement', tags=['Customer inbox'])
view = RequirePermission('communication_view','crm_view','crm_manage','crm_admin')
Kind = Literal['whatsapp','customer','lead','contact']


def permitted(user, *names):
    return user.is_superuser or bool(permission_names(user).intersection(names))


def email_access(user):
    return permitted(user,'communication_view','communication_email_send','communication_logs_view')


def crm_access(user):
    return permitted(user,'crm_view','crm_manage','crm_admin')


def resolve(db, user, kind, identity):
    company = wa.organization(user)
    if kind=='whatsapp':
        if not crm_access(user): raise HTTPException(403,'CRM conversation access is required')
        row=db.query(WhatsAppContact).filter_by(id=identity,organization_id=company,erased_at=None).first()
        if not row: raise HTTPException(404,'Conversation not found')
        wa.contact_access(db,user,row)
        branch=wa.branch_ownership(db,row)
        record=wa.record_access(db,user,row.entity_type,row.entity_id) if row.entity_id else None
        return row,branch,record
    if not email_access(user): raise HTTPException(403,'Email conversation access is required')
    if kind=='customer':
        row=db.query(CustomerRecipient).filter_by(id=identity,organization_id=company).first()
        if not row: raise HTTPException(404,'Customer not found')
        record=wa.record_access(db,user,'contact',row.crm_contact_id) if row.crm_contact_id and crm_access(user) else None
        return row,row.branch_id,record
    if not crm_access(user): raise HTTPException(403,'CRM record access is required')
    record=wa.record_access(db,user,kind,identity)
    return record,wa.branch_ownership(db,record) or record.branch_id,record


def state(db,user,kind,identity):
    company=wa.organization(user)
    workflow=db.query(ConversationWorkflow).filter_by(organization_id=company,kind=kind,record_id=identity).first()
    reading=db.query(ConversationReading).filter_by(organization_id=company,kind=kind,record_id=identity,user_id=user.id).first()
    return workflow,reading


def state_data(workflow,reading):
    return {'assignedUserId':workflow.assigned_user_id if workflow else None,
        'handoverNote':workflow.handover_note if workflow else '', 'status':workflow.status if workflow else 'open',
        'whatsappReadId':reading.whatsapp_read_id if reading else 0,'emailReadId':reading.email_read_id if reading else 0,
        'snoozedUntil':wa.utc(reading.snoozed_until) if reading else None}


def header(row,branch,record,kind):
    return {'key':f'{kind}:{row.id}','kind':kind,'id':row.id,'branchId':branch,
        'name':getattr(record,'full_name',None) or getattr(row,'name',None) or getattr(row,'full_name',None) or '+'+str(getattr(row,'recipient','Customer')),
        'phone':('+'+row.recipient if kind=='whatsapp' else getattr(row,'phone',None)),
        'email':getattr(record,'email',None) or getattr(row,'email',None),
        'entityType':row.entity_type if kind=='whatsapp' else 'contact' if kind=='customer' and row.crm_contact_id else kind if kind in {'lead','contact'} else None,
        'entityId':row.entity_id if kind=='whatsapp' else row.crm_contact_id if kind=='customer' else row.id,
        'companyName':getattr(record,'company_name',None),'recordOwnerId':getattr(record,'owner_user_id',None),
        'tags':[t.strip() for t in str(getattr(record,'tags_text','') or '').split(',') if t.strip()], 'priority':getattr(record,'priority',None),
        'consent':getattr(row,'consent',None), 'serviceWindowOpen':wa.service_window(row) if kind=='whatsapp' else None}


def associated_recipients(db,user,kind,row,branch):
    if not email_access(user): return []
    company=wa.organization(user)
    if kind=='customer': return [row]
    entity=row.entity_type if kind=='whatsapp' else kind
    identity=row.entity_id if kind=='whatsapp' else row.id
    if not entity or not identity: return []
    ids=db.query(CustomerBinding.recipient_id).filter_by(organization_id=company,source_type=entity,source_id=identity)
    query=db.query(CustomerRecipient).filter(CustomerRecipient.organization_id==company,CustomerRecipient.branch_id==branch,
        or_(CustomerRecipient.id.in_(ids),CustomerRecipient.crm_contact_id==identity if entity=='contact' else False))
    return query.all()


def events_for(db,user,kind,row,branch,record):
    company=wa.organization(user);events=[]
    recipients=associated_recipients(db,user,kind,row,branch)
    contacts=[]
    if kind=='whatsapp': contacts=[row]
    elif crm_access(user):
        entity='contact' if kind=='customer' and row.crm_contact_id else kind
        identity=row.crm_contact_id if kind=='customer' else row.id
        if entity in {'lead','contact'} and identity:
            for contact in db.query(WhatsAppContact).filter_by(organization_id=company,entity_type=entity,entity_id=identity,erased_at=None).all():
                try:
                    wa.contact_access(db,user,contact)
                    if wa.branch_ownership(db,contact)==branch: contacts.append(contact)
                except HTTPException as error:
                    if error.status_code not in {403,404}: raise
    for message in db.query(WhatsAppMessage).filter(WhatsAppMessage.organization_id==company,WhatsAppMessage.contact_id.in_([c.id for c in contacts])).order_by(WhatsAppMessage.id.desc()).limit(300).all() if contacts else []:
        events.append({'key':'wa:'+str(message.id),'channel':'whatsapp','id':message.id,'contactId':message.contact_id,'direction':message.direction,'body':message.body,'status':message.status,'createdAt':message.created_at,'errorCode':message.error_code,'media':wa.message_data(message).get('media'),'providerMessageId':message.provider_message_id,'replyTo':wa.message_data(message).get('replyTo')})
    if email_access(user):
        ids=[r.id for r in recipients]
        if ids:
            for message in db.query(CustomerEmailReply).filter(CustomerEmailReply.organization_id==company,CustomerEmailReply.branch_id==branch,CustomerEmailReply.recipient_id.in_(ids)).order_by(CustomerEmailReply.id.desc()).limit(300).all():
                events.append({'key':'reply:'+str(message.id),'channel':'email','id':message.id,'direction':'inbound','subject':message.subject,'body':message.body,'status':'received','createdAt':message.received_at})
            for delivery in db.query(CustomerDelivery).filter(CustomerDelivery.organization_id==company,CustomerDelivery.branch_id==branch,CustomerDelivery.recipient_id.in_(ids),CustomerDelivery.channel=='email').order_by(CustomerDelivery.id.desc()).limit(300).all():
                events.append({'key':'delivery:'+str(delivery.id),'channel':'email','id':delivery.id,'deliveryId':delivery.id,'direction':'outbound','subject':delivery.subject,'body':delivery.body,'status':delivery.status,'createdAt':delivery.created_at})
        entity=row.entity_type if kind=='whatsapp' else 'contact' if kind=='customer' else kind
        identity=row.entity_id if kind=='whatsapp' else row.crm_contact_id if kind=='customer' else row.id
        if record and entity in {'lead','contact'} and identity:
            messages=db.query(CommunicationEmailMessage).filter_by(organization_id=company,related_record_type=entity,related_record_id=identity).order_by(CommunicationEmailMessage.id.desc()).limit(300).all()
            for message in messages:
                attachments=db.query(CommunicationEmailAttachment).filter_by(message_id=message.id).all()
                events.append({'key':'email:'+str(message.id),'channel':'email','id':message.id,'emailMessageId':message.id,'direction':'outbound','subject':message.subject,'body':message.body,'status':message.status,'createdAt':message.created_at,'attachments':[{'name':a.file_name,'size':a.size_bytes} for a in attachments]})
    for event in events: event['createdAt']=wa.utc(event['createdAt'])
    return sorted(events,key=lambda e:(e['createdAt'] or datetime.min.replace(tzinfo=timezone.utc),e['key']))


@router.get('/inbox')
def inbox(search: str=Query('',max_length=160), before: int|None=Query(None,gt=0), offerings: str=Query('',max_length=5000), tag: str=Query('',max_length=100), priority: Literal['High','Medium','Low','Urgent','Critical']|None=Query(None), channel:Literal['all','whatsapp','email']=Query('all'), queue:Literal['all','unread','mine','unassigned','awaiting','waiting','snoozed','resolved','pending','followups','unlinked']=Query('all'), owner:int|None=Query(None,gt=0), team:int|None=Query(None,gt=0), contact_type:Literal['lead','customer','vendor','employee','other']|None=Query(None), message_status:Literal['received','queued','pending','reserved','accepted','sent','delivered','read','failed','submitting','reconciliation_required']|None=Query(None), since:datetime|None=Query(None), until:datetime|None=Query(None), cursor:str=Query('',max_length=500), db:Session=Depends(get_db), user=Depends(view)):
    company=wa.organization(user);items=[];contacts=[];next_cursor=None
    advanced=channel=='whatsapp'
    if any(at and at.utcoffset() is None for at in (since,until)) or since and until and since>=until:
        raise HTTPException(422,'Choose a valid timezone-aware activity date range')
    if crm_access(user) and channel!='email':
        query=db.query(WhatsAppContact).filter_by(organization_id=company,erased_at=None)
        if before: query=query.filter(WhatsAppContact.id<before)
        from app.services import whatsapp_inbox_filters as filters
        query=filters.apply(db,user,query,offerings,priority,team,advanced and queue=='followups')
        if advanced:
            query=filters.search(db,user,query,search)
            query=filters.state(db,user,query,queue,owner,message_status)
            if since:query=query.filter(WhatsAppContact.last_message_at>=since)
            if until:query=query.filter(WhatsAppContact.last_message_at<until)
            query=filters.cursor_query(query,cursor)
        last_scanned=None;last_row=None
        activity=func.coalesce(WhatsAppContact.last_message_at,datetime(1970,1,1,tzinfo=timezone.utc))
        while len(contacts)<200:
            batch=filters.cursor_query(query,filters.encode_cursor(last_row)) if advanced and last_row else query.filter(WhatsAppContact.id<last_scanned) if last_scanned else query
            rows=batch.order_by(activity.desc(),WhatsAppContact.id.desc()).limit(200).all() if advanced else batch.order_by(WhatsAppContact.id.desc()).limit(200).all()
            if not rows:break
            for row in rows:
                last_scanned=row.id;last_row=row
                try:
                    wa.contact_access(db,user,row)
                    record=wa.record_access(db,user,row.entity_type,row.entity_id) if row.entity_id else None
                    if filters.matches_tag(record,tag) and (not contact_type or filters.classification(record,row.entity_type)==contact_type):contacts.append(row)
                except HTTPException as error:
                    if error.status_code not in {403,404}:raise
                if len(contacts)==200:break
            if len(rows)<200:break
        next_before=last_scanned if last_scanned and query.filter(WhatsAppContact.id<last_scanned).first() else None
        if advanced:
            next_cursor=filters.encode_cursor(last_row) if last_row and filters.cursor_query(query,filters.encode_cursor(last_row)).first() else None
            next_before=None
    else: next_before=None
    readings={(r.kind,r.record_id):r for r in db.query(ConversationReading).filter_by(organization_id=company,user_id=user.id).all()}
    workflows={(r.kind,r.record_id):r for r in db.query(ConversationWorkflow).filter_by(organization_id=company).all()}
    contact_ids=[r.id for r in contacts]
    latest_ids=db.query(func.max(WhatsAppMessage.id).label('id')).filter(WhatsAppMessage.organization_id==company,WhatsAppMessage.contact_id.in_(contact_ids)).group_by(WhatsAppMessage.contact_id).subquery()
    latest={r.contact_id:r for r in db.query(WhatsAppMessage).join(latest_ids,WhatsAppMessage.id==latest_ids.c.id).all()}
    read=ConversationReading
    unread=dict(db.query(WhatsAppMessage.contact_id,func.count(WhatsAppMessage.id)).outerjoin(read,and_(read.organization_id==company,read.kind=='whatsapp',read.record_id==WhatsAppMessage.contact_id,read.user_id==user.id)).filter(WhatsAppMessage.organization_id==company,WhatsAppMessage.contact_id.in_(contact_ids),WhatsAppMessage.direction=='inbound',WhatsAppMessage.id>func.coalesce(read.whatsapp_read_id,0)).group_by(WhatsAppMessage.contact_id).all())
    for row in contacts:
        branch=wa.branch_ownership(db,row);record=wa.record_access(db,user,row.entity_type,row.entity_id) if row.entity_id else None
        item=header(row,branch,record,'whatsapp');message=latest.get(row.id)
        item.update(state_data(workflows.get(('whatsapp',row.id)),readings.get(('whatsapp',row.id))))
        item.update(lastMessage=message.body[:180] if message else '',lastAt=row.last_message_at if advanced else message.created_at if message else row.last_message_at,lastDirection=message.direction if message else None,unread=unread.get(row.id,0),needsMatch=not bool(row.entity_id))
        items.append(item)
    if channel!='whatsapp' and email_access(user) and not (offerings or tag.strip() or priority):
        represented_customers={(i['entityType'],i['entityId'],i['branchId']):i for i in items if i['entityId']}
        for recipient in db.query(CustomerRecipient).filter_by(organization_id=company,active=True).order_by(CustomerRecipient.id.desc()).limit(200).all():
            try:
                row,branch,record=resolve(db,user,'customer',recipient.id)
            except HTTPException as error:
                if error.status_code not in {403,404}: raise
                continue
            item=header(row,branch,record,'customer');reading=readings.get(('customer',row.id))
            bound=[('contact',row.crm_contact_id)] if row.crm_contact_id else [(b.source_type,b.source_id) for b in db.query(CustomerBinding).filter_by(organization_id=company,recipient_id=row.id).filter(CustomerBinding.source_type.in_(['lead','contact'])).all()]
            combined=next((represented_customers[(entity,identity,branch)] for entity,identity in bound if (entity,identity,branch) in represented_customers),None)
            if combined:
                reading=readings.get((combined['kind'],combined['id']))
            reply=db.query(CustomerEmailReply).filter_by(organization_id=company,recipient_id=row.id).order_by(CustomerEmailReply.id.desc()).first()
            item.update(state_data(workflows.get(('customer',row.id)),reading))
            count=db.query(func.count(CustomerEmailReply.id)).filter(CustomerEmailReply.organization_id==company,CustomerEmailReply.recipient_id==row.id,CustomerEmailReply.id>(reading.email_read_id if reading else 0)).scalar()
            if combined:
                combined['unread']+=count
                combined['email']=combined.get('email') or row.email
                if reply and (not combined['lastAt'] or wa.utc(reply.received_at)>wa.utc(combined['lastAt'])):
                    combined.update(lastMessage=reply.body[:180],lastAt=reply.received_at,lastDirection='inbound')
                continue
            item.update(lastMessage=reply.body[:180] if reply else 'Customer email history',lastAt=reply.received_at if reply else row.created_at,lastDirection='inbound' if reply else None,unread=count,needsMatch=not bool(row.crm_contact_id))
            items.append(item)
        # Existing CRM-linked individual emails also appear without requiring
        # creation of a consent/automation recipient or inventing an inbound email.
        if crm_access(user):
            recent=db.query(CommunicationEmailMessage).filter(CommunicationEmailMessage.organization_id==company,CommunicationEmailMessage.related_record_type.in_(['lead','contact'])).order_by(CommunicationEmailMessage.id.desc()).limit(200).all()
            represented={(i['entityType'],i['entityId']):i for i in items if i['entityId']}
            for email in recent:
                key=(email.related_record_type,email.related_record_id)
                if key in represented:
                    item=represented[key]
                    if not item['lastAt'] or wa.utc(email.created_at)>wa.utc(item['lastAt']):
                        item.update(lastMessage=email.subject,lastAt=email.created_at,lastDirection='outbound')
                    continue
                try: row,branch,record=resolve(db,user,*key)
                except HTTPException as error:
                    if error.status_code not in {403,404}: raise
                    continue
                item=header(row,branch,record,key[0]);represented[key]=item
                item.update(state_data(workflows.get(key),readings.get(key)))
                item.update(lastMessage=email.subject,lastAt=email.created_at,lastDirection='outbound',unread=0,needsMatch=False)
                items.append(item)
    if search.strip() and not advanced:
        term=search.strip().casefold();digits=re.sub(r'\D','',term)
        items=[item for item in items if term in ' '.join(str(item.get(k) or '') for k in ('name','phone','email','companyName')).casefold() or digits and digits in re.sub(r'\D','',item.get('phone') or '')]
    for item in items: item['lastAt']=wa.utc(item['lastAt'])
    items.sort(key=lambda i:i['lastAt'] or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
    counts={'unread':sum(i['unread'] for i in items),'awaitingReply':sum(i['lastDirection']=='inbound' and i['status']!='resolved' for i in items),'unmatched':sum(i['needsMatch'] for i in items)}
    return {'items':items,'counts':counts,'nextBefore':next_before,'nextCursor':next_cursor,'serverFiltered':advanced,'userId':user.id}


@router.get('/conversations/{kind}/{identity}')
def conversation(kind:Kind,identity:int,db:Session=Depends(get_db),user=Depends(view)):
    row,branch,record=resolve(db,user,kind,identity)
    events=events_for(db,user,kind,row,branch,record)
    workflow,reading=state(db,user,kind,identity)
    detail=header(row,branch,record,kind);detail.update(state_data(workflow,reading))
    context=db.info.get('branch_context')
    detail['canManage']=bool(context and branch in context.writable and permitted(user,'crm_admin','crm_manage','communication_email_send'))
    if kind=='whatsapp':
        detail['whatsappContact']={**wa.contact_data(row),'crmName':getattr(record,'full_name',None),'crmEmail':getattr(record,'email',None)}
    return {'conversation':detail,'events':events,'historyLimitPerSource':300}


def writable(db,user,branch):
    context=db.info.get('branch_context')
    if not branch or not context or branch not in context.writable:
        raise HTTPException(403,'This conversation requires a writable branch')


class ReadingInput(BaseModel):
    whatsappReadId:int=Field(default=0,ge=0)
    emailReadId:int=Field(default=0,ge=0)


def reading_row(db,user,kind,identity,branch):
    query=db.query(ConversationReading).filter_by(organization_id=wa.organization(user),kind=kind,record_id=identity,user_id=user.id)
    row=query.with_for_update().first()
    if row: return row
    try:
        with db.begin_nested():
            row=ConversationReading(organization_id=wa.organization(user),branch_id=branch,kind=kind,record_id=identity,user_id=user.id,whatsapp_read_id=0,email_read_id=0)
            db.add(row);db.flush()
        return row
    except IntegrityError:
        return query.with_for_update().one()


@router.post('/conversations/{kind}/{identity}/read')
def mark_read(kind:Kind,identity:int,data:ReadingInput,db:Session=Depends(get_db),user=Depends(view)):
    row,branch,record=resolve(db,user,kind,identity)
    if not branch: raise HTTPException(409,'Assign a branch before saving a reading position')
    events=events_for(db,user,kind,row,branch,record)
    allowed_wa={e['id'] for e in events if e['channel']=='whatsapp' and e['direction']=='inbound'}
    allowed_email={e['id'] for e in events if e['key'].startswith('reply:')}
    if data.whatsappReadId and data.whatsappReadId not in allowed_wa or data.emailReadId and data.emailReadId not in allowed_email:
        raise HTTPException(422,'Reading position must be an incoming message visible in this conversation')
    reading=reading_row(db,user,kind,identity,branch)
    reading.whatsapp_read_id=max(reading.whatsapp_read_id,data.whatsappReadId)
    reading.email_read_id=max(reading.email_read_id,data.emailReadId)
    db.commit();return {'ok':True}


class SnoozeInput(BaseModel):
    until:datetime|None=None


@router.post('/conversations/{kind}/{identity}/snooze')
def snooze(kind:Kind,identity:int,data:SnoozeInput,db:Session=Depends(get_db),user=Depends(view)):
    row,branch,record=resolve(db,user,kind,identity)
    if not branch: raise HTTPException(409,'Assign a branch before snoozing')
    if data.until and (data.until.tzinfo is None or not wa.now()<data.until<=wa.now()+timedelta(days=90)):
        raise HTTPException(422,'Choose a timezone-aware snooze time within the next 90 days')
    reading=reading_row(db,user,kind,identity,branch);reading.snoozed_until=data.until
    db.commit();return {'snoozedUntil':reading.snoozed_until}


class WorkflowInput(BaseModel):
    assignedUserId:int|None=Field(default=None,gt=0)
    handoverNote:str=Field(default='',max_length=3000)
    status:Literal['open','pending','resolved']='open'


@router.put('/conversations/{kind}/{identity}/workflow')
def workflow(kind:Kind,identity:int,data:WorkflowInput,db:Session=Depends(get_db),user=Depends(view)):
    row,branch,record=resolve(db,user,kind,identity);writable(db,user,branch)
    if not permitted(user,'crm_admin','crm_manage','communication_email_send'):
        raise HTTPException(403,'Conversation management permission is required')
    if data.assignedUserId:
        from app.core.tenant_boundary import company_ids
        from app.branches.service import access
        assignee=db.get(User,data.assignedUserId)
        if not assignee or not assignee.is_active or wa.organization(user) not in company_ids(db,assignee) or branch not in access(db,assignee,wa.organization(user))[0]:
            raise HTTPException(403,'Assignee must be an active member with access to this branch')
        resolve(db,assignee,kind,identity)
    company=wa.organization(user)
    query=db.query(ConversationWorkflow).filter_by(organization_id=company,kind=kind,record_id=identity)
    workflow=query.with_for_update().first()
    if not workflow:
        try:
            with db.begin_nested():
                workflow=ConversationWorkflow(organization_id=company,branch_id=branch,kind=kind,record_id=identity,updated_by=user.id,status='open',handover_note='')
                db.add(workflow);db.flush()
        except IntegrityError:
            workflow=query.with_for_update().one()
    previous_status=workflow.status
    workflow.assigned_user_id=data.assignedUserId;workflow.handover_note=data.handoverNote.strip();workflow.status=data.status;workflow.updated_by=user.id
    from app.branches.service import audit
    audit(db,user,company,'communication.handover','Conversation assignment/status updated',{'kind':kind,'record_id':identity,'assigned_user_id':data.assignedUserId,'status':data.status,'previous_status':previous_status,'handover_note':data.handoverNote.strip()})
    db.commit();return state_data(workflow,None)


@router.get('/assignees')
def assignees(db:Session=Depends(get_db),user=Depends(view)):
    from app.branches.service import access
    context=db.info.get('branch_context')
    if not context or not context.branch_id: return {'items':[]}
    from app.core.tenant_boundary import company_ids
    items=[]
    for candidate in db.query(User).filter_by(is_active=True).limit(500).all():
        if wa.organization(user) in company_ids(db,candidate) and context.branch_id in access(db,candidate,wa.organization(user))[0]:
            items.append({'id':candidate.id,'name':getattr(candidate,'full_name',None) or candidate.email})
    return {'items':items}


@router.get('/records')
def find_records(kind:Literal['lead','contact','deal','company','order','invoice','service','follow_up','contract','meeting','quotation','shipment'], search:str=Query('',max_length=160),db:Session=Depends(get_db),user=Depends(view)):
    from .customer_api import authorized_source
    if kind in {'lead','contact','deal','company'}:
        if not crm_access(user): raise HTTPException(403,'CRM access is required')
        from app.apps.crm.api.router import _get_resource,_base_query,_apply_record_visibility
        resource=_get_resource('companies' if kind=='company' else kind+'s')
        model=resource.model
        query=_apply_record_visibility(_base_query(db,resource,wa.organization(user)),resource,user,db)
    else:
        from .customer_service import source_model
        model=source_model(kind)
        if model is None: return {'items':[]}
        query=db.query(model).filter(model.organization_id==wa.organization(user))
        if hasattr(model,'deleted_at'): query=query.filter(model.deleted_at.is_(None))
    fields=[getattr(model,key) for key in ('full_name','name','title','email','phone','order_number','invoice_number','reference','contract_number','engagement_number','id') if hasattr(model,key)]
    if search.strip():
        term=search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.filter(or_(*(cast(field,String).ilike('%'+term+'%',escape='\\') for field in fields)))
    items=[]
    for row in query.order_by(model.id.desc()).limit(30).all():
        if kind not in {'lead','contact','deal','company'}:
            try: authorized_source(db,user,kind,row.id)
            except HTTPException as error:
                if error.status_code not in {403,404}: raise
                continue
        name=next((str(getattr(row,key)) for key in ('full_name','name','title','order_number','invoice_number','reference','contract_number','engagement_number') if getattr(row,key,None)),kind+' #'+str(row.id))
        items.append({'id':row.id,'entity':kind,'name':name,'email':getattr(row,'email',None),'phone':getattr(row,'phone',None)})
    return {'items':items}


@router.get('/delivery/{kind}/{identity}')
def delivery_evidence(kind:Literal['whatsapp','email'],identity:int,db:Session=Depends(get_db),user=Depends(view)):
    company=wa.organization(user)
    if kind=='whatsapp':
        row=db.query(WhatsAppMessage).filter_by(id=identity,organization_id=company).first()
        if not row: raise HTTPException(404,'Message not found')
        resolve(db,user,'whatsapp',row.contact_id)
        events=[{'status':'recorded','at':row.created_at}]
        events += [{'status':r.status,'at':r.created_at,'errorCode':r.error_code} for r in db.query(WhatsAppReceipt).filter_by(organization_id=company,connection_id=row.connection_id,provider_message_id=row.provider_message_id).order_by(WhatsAppReceipt.id).all()] if row.provider_message_id else []
        return {'status':row.status,'events':events,'canRetry':False,'guidance':'Uncertain sends must be reconciled using their original request. Accepted is not confirmed delivery.'}
    if not email_access(user): raise HTTPException(403,'Email access is required')
    row=db.query(CommunicationEmailMessage).filter_by(id=identity,organization_id=company).first()
    if not row or row.related_record_type not in {'lead','contact'}: raise HTTPException(404,'Email not found')
    resolve(db,user,row.related_record_type,row.related_record_id)
    logs=db.query(CommunicationDeliveryLog).filter_by(organization_id=company,channel='email',related_message_id=row.id).order_by(CommunicationDeliveryLog.id).all()
    return {'status':row.status,'events':[{'status':'recorded','at':row.created_at}]+[{'status':r.status,'at':r.created_at} for r in logs],'canRetry':False,'guidance':'Email provider acceptance does not confirm recipient delivery or reading.'}


@router.get('/health-summary')
def summary(db:Session=Depends(get_db),user=Depends(view)):
    result=inbox(search='',before=None,offerings='',tag='',priority=None,channel='all',queue='all',owner=None,team=None,contact_type=None,message_status=None,since=None,until=None,cursor='',db=db,user=user)
    failed=0
    if crm_access(user):
        ids=[i['id'] for i in result['items'] if i['kind']=='whatsapp']
        failed=db.query(func.count(WhatsAppMessage.id)).filter(WhatsAppMessage.organization_id==wa.organization(user),WhatsAppMessage.contact_id.in_(ids),WhatsAppMessage.status.in_(['failed','reconciliation_required'])).scalar()
    if email_access(user):
        # Match the same authorized inbox page as the other queue counters.
        # Organization-wide delivery counts would reveal other branches' activity.
        recipients=set()
        for item in result['items']:
            row,branch,_=resolve(db,user,item['kind'],item['id'])
            recipients.update((recipient.id,branch) for recipient in associated_recipients(db,user,item['kind'],row,branch))
        if recipients:
            allowed=or_(*(and_(CustomerDelivery.recipient_id==identity,CustomerDelivery.branch_id==branch) for identity,branch in recipients))
            failed+=db.query(func.count(CustomerDelivery.id)).filter(CustomerDelivery.organization_id==wa.organization(user),CustomerDelivery.channel=='email',allowed,CustomerDelivery.status.in_(['failed','blocked'])).scalar()
    return {**result['counts'],'deliveryIssues':failed,'conversationCount':len(result['items']),'hasMore':bool(result['nextBefore'])}


@router.get('/email-eligibility')
def email_eligibility(email:str=Query(...,max_length=254),db:Session=Depends(get_db),user=Depends(view)):
    if not email_access(user): raise HTTPException(403,'Email communication access is required')
    from .services.delivery import normalize_email,validate_email,is_opted_out
    address=normalize_email(email);validate_email(address)
    blocked=is_opted_out(db,address)
    return {'blocked':blocked,'reason':'This recipient has opted out of email.' if blocked else 'No active email opt-out blocks this recipient. Provider and record checks still apply when sending.'}
