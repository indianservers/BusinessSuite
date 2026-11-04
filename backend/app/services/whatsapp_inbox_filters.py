"""WhatsApp inbox projections of existing CRM priorities, tags and offerings."""
from datetime import datetime,timezone
from sqlalchemy import and_,func,literal,or_,select
from app.apps.crm import productivity as sales
from app.apps.crm.models import CRMActivity
from app.apps.crm import growth_audience as audience
from app.services import whatsapp_workspace as wa
from app.shared.whatsapp_models import WhatsAppContact


def apply(db,user,query,offerings,priority,team=None,followups=False):
    chosen=audience.parse_offerings(offerings)
    if not chosen and not priority and not team and not followups:return query
    relations=audience.offering_relations(db,user,'all') if chosen else None
    predicates=[]
    for kind,entity in [('lead','leads'),('contact','contacts'),('deal','deals')]:
        if not sales.allowed(user,entity,'view'):continue
        model=sales.lm.core()._get_resource(entity).model
        visible=sales.rows(db,user,entity)
        if chosen:visible=audience.apply_audience(visible,model,entity,relations,chosen,'any')
        if team:visible=visible.filter(getattr(model,'assigned_team_id',literal(None))==team)
        if followups:
            visible=visible.filter(select(1).where(CRMActivity.organization_id==wa.organization(user),CRMActivity.entity_type==kind,CRMActivity.entity_id==model.id,CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).correlate(model).exists())
        if priority:
            upcoming=select(CRMActivity.priority).where(CRMActivity.organization_id==wa.organization(user),CRMActivity.entity_type==kind,CRMActivity.entity_id==model.id,CRMActivity.status.in_(sales.OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).limit(1).correlate(model).scalar_subquery()
            effective=func.coalesce(upcoming,getattr(model,'priority',literal(None)))
            visible=visible.filter(func.lower(effective)==priority.lower())
        predicates.append((WhatsAppContact.entity_type==kind)&WhatsAppContact.entity_id.in_(visible.with_entities(model.id)))
    return query.filter(or_(*predicates) if predicates else False)


def matches_tag(record,tag):
    return not tag or bool(record and tag.strip().casefold() in {value.strip().casefold() for value in str(getattr(record,'tags_text','') or '').split(',') if value.strip()})


def classification(record,kind):
    values={v.strip().casefold() for v in str(getattr(record,'tags_text','') or '').split(',') if v.strip()}
    values.add(str(getattr(record,'lifecycle_stage','') or '').casefold())
    if values.intersection({'employee','staff','intern','manager','admin'}):return 'employee'
    if values.intersection({'vendor','supplier'}):return 'vendor'
    if 'customer' in values:return 'customer'
    if kind=='lead' or values.intersection({'lead','prospect'}):return 'lead'
    return 'other'


def search(db,user,query,term):
    if not term.strip():return query
    from app.shared.whatsapp_models import WhatsAppMessage
    term=term.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    pattern='%'+term+'%'
    predicates=[WhatsAppContact.name.ilike(pattern,escape='\\'),WhatsAppContact.recipient.ilike(pattern.replace('+',''),escape='\\'),select(1).where(WhatsAppMessage.organization_id==wa.organization(user),WhatsAppMessage.contact_id==WhatsAppContact.id,WhatsAppMessage.body.ilike(pattern,escape='\\')).correlate(WhatsAppContact).exists()]
    import re
    digits=re.sub(r'\D','',term)
    if len(digits)>=5 and not re.search(r'[a-zA-Z]',term):predicates.append(WhatsAppContact.recipient.contains(digits))
    relations=audience.offering_relations(db,user,'all')
    for kind,entity in [('lead','leads'),('contact','contacts'),('deal','deals')]:
        if not sales.allowed(user,entity,'view'):continue
        model=sales.lm.core()._get_resource(entity).model
        checks=[getattr(model,key).ilike(pattern,escape='\\') for key in ('full_name','name','email','phone','company_name') if hasattr(model,key)]
        checks.append(select(1).where(relations.c.entity==entity,relations.c.record_id==model.id,relations.c.name.ilike(pattern,escape='\\')).correlate(model).exists())
        if hasattr(model,'company_id') and sales.allowed(user,'companies','view'):
            company=sales.lm.core()._get_resource('companies').model
            checks.append(model.company_id.in_(sales.rows(db,user,'companies').filter(company.name.ilike(pattern,escape='\\')).with_entities(company.id)))
        visible=sales.rows(db,user,entity).filter(or_(*checks)).with_entities(model.id)
        predicates.append(and_(WhatsAppContact.entity_type==kind,WhatsAppContact.entity_id.in_(visible)))
    return query.filter(or_(*predicates))


def state(db,user,query,view,owner=None,message_status=None):
    from app.apps.communication.engagement_models import ConversationWorkflow as Flow,ConversationReading as Read
    from app.shared.whatsapp_models import WhatsAppMessage as Message
    company=wa.organization(user)
    flow=[Flow.organization_id==company,Flow.kind=='whatsapp',Flow.record_id==WhatsAppContact.id]
    reading=[Read.organization_id==company,Read.kind=='whatsapp',Read.record_id==WhatsAppContact.id,Read.user_id==user.id]
    status=select(Flow.status).where(*flow).correlate(WhatsAppContact).scalar_subquery()
    assigned=select(Flow.assigned_user_id).where(*flow).correlate(WhatsAppContact).scalar_subquery()
    snooze=select(Read.snoozed_until).where(*reading).correlate(WhatsAppContact).scalar_subquery()
    read_id=select(Read.whatsapp_read_id).where(*reading).correlate(WhatsAppContact).scalar_subquery()
    if owner:query=query.filter(assigned==owner)
    if view=='resolved':query=query.filter(status=='resolved')
    elif view=='pending':query=query.filter(status=='pending')
    elif view=='snoozed':query=query.filter(snooze>wa.now())
    else:
        if view not in ('followups','unlinked'):query=query.filter(func.coalesce(status,'open')!='resolved',or_(snooze.is_(None),snooze<=wa.now()))
        if view=='mine':query=query.filter(assigned==user.id)
        elif view=='unassigned':query=query.filter(assigned.is_(None))
        elif view=='unlinked':query=query.filter(WhatsAppContact.entity_id.is_(None))
        elif view=='unread':query=query.filter(select(1).where(Message.organization_id==company,Message.contact_id==WhatsAppContact.id,Message.direction=='inbound',Message.id>func.coalesce(read_id,0)).correlate(WhatsAppContact).exists())
        elif view in ('awaiting','waiting'):
            last=select(Message.direction).where(Message.organization_id==company,Message.contact_id==WhatsAppContact.id).order_by(Message.id.desc()).limit(1).correlate(WhatsAppContact).scalar_subquery()
            query=query.filter(last==('inbound' if view=='awaiting' else 'outbound'))
    if message_status:
        last=select(Message.status).where(Message.organization_id==company,Message.contact_id==WhatsAppContact.id).order_by(Message.id.desc()).limit(1).correlate(WhatsAppContact).scalar_subquery()
        query=query.filter(last==message_status)
    return query


def encode_cursor(row):
    import base64,json
    at=wa.utc(row.last_message_at) or datetime(1970,1,1,tzinfo=timezone.utc)
    return base64.urlsafe_b64encode(json.dumps([at.isoformat(),row.id]).encode()).decode().rstrip('=')


def cursor_query(query,cursor):
    if not cursor:return query
    import base64,json
    from datetime import datetime,timezone
    from fastapi import HTTPException
    try:
        at,ident=json.loads(base64.urlsafe_b64decode(cursor+'='*((4-len(cursor)%4)%4)))
        at=datetime.fromisoformat(at)
        if at.utcoffset() is None or type(ident)!=int or ident<=0:raise ValueError()
    except Exception:raise HTTPException(422,'Invalid conversation cursor') from None
    key=func.coalesce(WhatsAppContact.last_message_at,datetime(1970,1,1,tzinfo=timezone.utc))
    return query.filter(or_(key<at,and_(key==at,WhatsAppContact.id<ident)))
