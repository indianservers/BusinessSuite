"""Read adapters for canonical CRM/commercial records and WhatsApp-only reporting."""
from collections import Counter, defaultdict

from fastapi import HTTPException
from sqlalchemy import and_, or_, func

from app.services import whatsapp_workspace as wa
from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage


def contact_for_user(db, user, ident):
    row=db.query(WhatsAppContact).filter_by(id=ident,organization_id=wa.organization(user),erased_at=None).first()
    if not row: raise HTTPException(404, 'Conversation not found')
    wa.contact_access(db,user,row)
    return row


def context(db, user, ident):
    from app.apps.crm import productivity as sales
    from app.apps.crm.models import CRMDeal, CRMDealContact, CRMQuotation
    from app.apps.crm.growth import pending
    row=contact_for_user(db,user,ident)
    result={'linked':bool(row.entity_id),'deals':[],'quotations':[],'invoices':[],'followUps':[],
        'sections':{},'canFollowUp':False,'canViewFinance':False}
    if not row.entity_id: return result
    entity={'lead':'leads','contact':'contacts','deal':'deals'}[row.entity_type]
    record=wa.record_access(db,user,row.entity_type,row.entity_id)
    person=record.id if entity=='contacts' else getattr(record,'contact_id',None) if entity=='deals' else getattr(record,'converted_contact_id',None)
    company=getattr(record,'company_id',None) or getattr(record,'converted_company_id',None)
    result['record']={'entity':entity,'id':record.id,'name':getattr(record,'full_name',None) or getattr(record,'name',None) or row.name or row.recipient}
    result['canFollowUp']=sales.allowed(user,entity,'manage')
    result['profile']={'priority':getattr(record,'priority',None),'currency':getattr(record,'currency',None),'email':getattr(record,'email',None),'lifecycle':getattr(record,'lifecycle_stage',None),'tags':getattr(record,'tags_text',None)}
    from app.apps.crm.models import CRMNote,CRMActivity
    link_field=row.entity_type+'_id'
    result['canNote']=sales.allowed(user,'notes','manage') and result['canFollowUp']
    result['notes']=[];result['activity']=[];result['offerings']=[]
    if sales.allowed(user,'notes','view'):
        notes=sales.rows(db,user,'notes').filter(getattr(CRMNote,link_field)==record.id,CRMNote.deleted_at.is_(None)).order_by(CRMNote.created_at.desc(),CRMNote.id.desc()).limit(20).all()
        result['notes']=[{'id':n.id,'body':n.body,'at':n.created_at,'authorId':n.author_user_id} for n in notes]
    if sales.allowed(user,'activities','view'):
        activity=sales.rows(db,user,'activities').filter(or_(getattr(CRMActivity,link_field)==record.id,and_(CRMActivity.entity_type==row.entity_type,CRMActivity.entity_id==record.id))).order_by(CRMActivity.created_at.desc(),CRMActivity.id.desc()).limit(20).all()
        result['activity']=[{'id':a.id,'title':a.title or a.subject,'status':a.status,'at':a.created_at,'type':a.activity_type} for a in activity]
    from app.apps.crm.growth_audience import offering_relations
    offerings=offering_relations(db,user,'all')
    result['offerings']=[dict(item._mapping) for item in db.execute(offerings.select().where(offerings.c.entity==entity,offerings.c.record_id==record.id).with_only_columns(offerings.c.kind,offerings.c.item_id,offerings.c.name).distinct().limit(50))]
    from app.branches.models import BranchAudit
    history=db.query(BranchAudit).filter(BranchAudit.company_id==wa.organization(user),BranchAudit.operation=='communication.handover',BranchAudit.details['kind'].as_string()=='whatsapp',BranchAudit.details['record_id'].as_integer()==row.id).order_by(BranchAudit.id.desc()).limit(30).all()
    result['history']=[{'id':h.id,'at':h.created_at,'actorId':h.actor_id,'status':h.details.get('status'),'previousStatus':h.details.get('previous_status'),'ownerId':h.details.get('assigned_user_id'),'note':h.details.get('handover_note','')} for h in history]

    creation={'personId':None,'companyId':None,'dealId':record.id if entity=='deals' else None,'canDeal':False,'canQuotation':False,'canInvoice':False,'canTask':False}
    if person:
        try:
            wa.record_access(db,user,'contact',person)
            creation['personId']=person
        except HTTPException as error:
            if error.status_code not in (403,404):raise
    if company and sales.allowed(user,'companies','view'):
        company_model=sales.lm.core()._get_resource('companies').model
        linked_company=sales.rows(db,user,'companies').filter(company_model.id==company).first()
        if linked_company:
            creation['companyId']=company
            result['profile']['companyName']=linked_company.name
    creation['canDeal']=bool(creation['personId'] and sales.allowed(user,'deals','manage'))
    creation['canQuotation']=bool((creation['personId'] or entity=='deals') and sales.allowed(user,'quotations','manage'))
    from app.shared.record_360 import module_access
    if row.entity_type in ('lead','contact') or creation['personId']:
        try:
            module_access(db,user,'project_management')
            from app.apps.project_management.access import accessible_project_query,can_access_project
            creation['canTask']=any(can_access_project(db,p,user,'manage_tasks') for p in accessible_project_query(db,user).yield_per(50))
        except HTTPException as error:
            if error.status_code not in (403,404):raise
    result['creation']=creation

    # Every relationship is intersected with its domain's existing visibility query.
    deal_ids=[]
    if sales.allowed(user,'deals','view'):
        predicates=[CRMDeal.id==record.id] if entity=='deals' else [CRMDeal.id==getattr(record,'converted_deal_id',None)] if entity=='leads' else []
        if person:
            linked=db.query(CRMDealContact.deal_id).filter_by(organization_id=wa.organization(user),contact_id=person)
            predicates.extend([CRMDeal.contact_id==person,CRMDeal.id.in_(linked)])
        deals=sales.rows(db,user,'deals').filter(or_(*predicates)).order_by(CRMDeal.id.desc()).limit(51).all() if predicates else []
        result['sections']['deals']='Showing latest 50' if len(deals)>50 else 'Available'
        for item in deals[:50]:
            deal_ids.append(item.id)
            result['deals'].append({'id':item.id,'name':item.name,'status':item.status,'amount':item.amount,'currency':item.currency,'url':f'/crm/deals/{item.id}'})
    else: result['sections']['deals']='Sales access required'
    if sales.allowed(user,'quotations','view'):
        predicates=[CRMQuotation.deal_id.in_(deal_ids)]
        if person: predicates.append(CRMQuotation.contact_id==person)
        quotes=sales.rows(db,user,'quotations').filter(or_(*predicates)).order_by(CRMQuotation.id.desc()).limit(51).all()
        result['sections']['quotations']='Showing latest 50' if len(quotes)>50 else 'Available'
        result['quotations']=[{'id':q.id,'name':q.quote_number,'status':q.status,'amount':q.total_amount,'currency':q.currency,'dueAt':q.expiry_date,'url':f'/crm/quotations/{q.id}'} for q in quotes[:50]]
    else: result['sections']['quotations']='Quotation access required'
    result['followUps']=pending(entity,record.id,db,user)['items']
    # Match explicit person links or the canonical customer, never fuzzy names/phones.
    try:
        from app.shared.record_360 import module_access
        from app.apps.srm.services.commercial import require, invoice_query, customer
        from app.apps.srm.models import SRMInvoice
        from app.apps.srm.commercial_models import InvoiceContext
        module_access(db,user,'srm')
        require(user,'srm_invoice_view','srm_invoice_create','srm_admin','srm_collection_view')
        predicates=[]
        if person:
            predicates.append(SRMInvoice.id.in_(db.query(InvoiceContext.invoice_id).filter_by(contact_id=person)))
        if company:
            try:
                customer(db,company,user)
                creation['companyId']=company
                from app.access.catalog import permission_names
                creation['canInvoice']=bool(user.is_superuser or permission_names(user).intersection({'srm_invoice_create','srm_admin'}))
                predicates.append(SRMInvoice.customer_id==company)
            except HTTPException as error:
                if error.status_code not in (403,404): raise
        invoices=invoice_query(db,user).filter(or_(*predicates)).order_by(SRMInvoice.id.desc()).limit(51).all() if predicates else []
        result['canViewFinance']=True
        result['sections']['invoices']='Showing latest 50' if len(invoices)>50 else 'Available'
        result['invoices']=[{'id':i.id,'name':i.invoice_number,'status':i.status,'amount':i.total_amount,'balance':i.balance_amount,'currency':i.currency,'dueAt':i.due_date,'url':f'/srm/invoices/{i.id}'} for i in invoices[:50]]
    except HTTPException as error:
        if error.status_code not in (403,404): raise
        result['sections']['invoices']='Finance access required'
    return result


def analytics(db,user,start,end,employee=None,team=None):
    """Scan authorized contacts in bounded batches, then aggregate their real messages."""
    from app.apps.communication.engagement_models import ConversationWorkflow, ConversationReading
    from app.apps.communication.customer_models import CustomerAutomation, CustomerDelivery
    from app.apps.communication.engagement_api import assignees, permitted
    company=wa.organization(user)
    from app.apps.crm import productivity as sales
    from app.apps.crm.models import CRMTeam
    teams=sales.rows(db,user,'teams').order_by(CRMTeam.id).limit(200).all() if sales.allowed(user,'teams','view') else []
    if team and team not in {t.id for t in teams}:
        raise HTTPException(403,'Choose a CRM team visible in this branch')
    people=assignees(db,user)['items']
    if employee and employee not in {p['id'] for p in people}:
        raise HTTPException(403,'Choose an employee visible in this branch')
    campaign_access=permitted(user,'communication_view','communication_campaigns_view','communication_campaigns_manage','communication_campaigns_send')
    names={p['id']:p['name'] for p in people}
    totals=Counter({key:0 for key in ('messages','received','outbound','conversations','newConversations','unreadConversations')}); statuses=Counter(); daily=defaultdict(Counter); templates=defaultdict(Counter); campaigns=defaultdict(Counter); workload=defaultdict(Counter)
    first_response=[];resolution=[]; pending_ids=set(); access_cache={}; after=0
    while True:
        batch=db.query(WhatsAppContact).filter(WhatsAppContact.organization_id==company,WhatsAppContact.erased_at.is_(None),WhatsAppContact.id>after).order_by(WhatsAppContact.id).limit(250).all()
        if not batch: break
        after=batch[-1].id
        workflows={w.record_id:w for w in db.query(ConversationWorkflow).filter(ConversationWorkflow.organization_id==company,ConversationWorkflow.kind=='whatsapp',ConversationWorkflow.record_id.in_([c.id for c in batch])).all()}
        allowed=[]
        for row in batch:
            flow=workflows.get(row.id)
            if employee and (not flow or flow.assigned_user_id!=employee): continue
            key=(row.entity_type,row.entity_id)
            if key not in access_cache:
                try: wa.contact_access(db,user,row);access_cache[key]=True
                except HTTPException as error:
                    if error.status_code not in (403,404): raise
                    access_cache[key]=False
            if access_cache[key]:
                if team and (not row.entity_id or getattr(wa.record_access(db,user,row.entity_type,row.entity_id),'assigned_team_id',None)!=team):continue
                allowed.append(row.id)
        if not allowed: continue
        message=WhatsAppMessage
        base=db.query(message).filter(message.organization_id==company,message.contact_id.in_(allowed),message.created_at>=start,message.created_at<end)
        # Records are read in pages; no inbox page limit is used for these metrics.
        cursor=0; active=set()
        while True:
            messages=base.filter(message.id>cursor).order_by(message.id).limit(500).all()
            if not messages: break
            cursor=messages[-1].id
            for m in messages:
                active.add(m.contact_id); totals['messages']+=1
                bucket=daily[wa.utc(m.created_at).date().isoformat()]
                if m.direction=='inbound':
                    totals['received']+=1;bucket['received']+=1
                else:
                    totals['outbound']+=1;statuses[m.status]+=1;bucket['outbound']+=1
                    if m.kind=='template':
                        t=m.template_json or {};name=t.get('name','Unknown template')+' · '+str((t.get('language') or {}).get('code',''))
                        templates[name][m.status]+=1
        totals['conversations']+=len(active)
        if active:
            firsts=db.query(message.contact_id,func.min(message.created_at)).filter(message.organization_id==company,message.contact_id.in_(active)).group_by(message.contact_id).all()
            totals['newConversations']+=sum(1 for _,at in firsts if start<=wa.utc(at)<end)
            # Batch first-response and unread queries rather than one query per thread.
            inbound=base.filter(message.direction=='inbound').with_entities(message.contact_id.label('contact'),func.min(message.created_at).label('at')).group_by(message.contact_id).subquery()
            responses=base.join(inbound,and_(message.contact_id==inbound.c.contact,message.created_at>=inbound.c.at)).filter(message.direction=='outbound',message.status.in_(['accepted','sent','delivered','read'])).with_entities(func.min(message.created_at),inbound.c.at).group_by(message.contact_id,inbound.c.at).all()
            first_response.extend((wa.utc(response)-wa.utc(at)).total_seconds() for response,at in responses)
            reading=ConversationReading
            unread=base.outerjoin(reading,and_(reading.organization_id==company,reading.kind=='whatsapp',reading.record_id==message.contact_id,reading.user_id==user.id)).filter(message.direction=='inbound',message.id>func.coalesce(reading.whatsapp_read_id,0)).with_entities(message.contact_id).group_by(message.contact_id).all()
            totals['unreadConversations']+=len(unread)
            for ident in active:
                flow=workflows.get(ident);owner=flow.assigned_user_id if flow else None
                workload[owner]['conversations']+=1;workload[owner][flow.status if flow else 'open']+=1
            # Existing CRM pending activities, deduplicated across WhatsApp numbers.
            linked={(c.entity_type,c.entity_id) for c in batch if c.id in active and c.entity_id}
            from app.apps.crm.models import CRMActivity
            from app.apps.crm.productivity import OPEN_ACTIVITY
            if linked:
                matches=or_(*(and_(CRMActivity.entity_type==kind,CRMActivity.entity_id==ident) for kind,ident in linked))
                pending_ids.update(activity_id for activity_id, in db.query(CRMActivity.id).filter(CRMActivity.organization_id==company,matches,CRMActivity.status.in_(OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).all())
        # Append-only workflow audit supplies resolution cycles without a new store.
        # Older rows without an explicit previous state cannot prove a transition.
        from app.branches.models import BranchAudit
        history=db.query(BranchAudit).filter(BranchAudit.company_id==company,BranchAudit.operation=='communication.handover',BranchAudit.details['kind'].as_string()=='whatsapp',BranchAudit.details['record_id'].as_integer().in_(allowed),BranchAudit.created_at<end).order_by(BranchAudit.created_at,BranchAudit.id).yield_per(500)
        first_inbound=dict(db.query(message.contact_id,func.min(message.created_at)).filter(message.organization_id==company,message.contact_id.in_(allowed),message.direction=='inbound').group_by(message.contact_id).all())
        opened={}
        for event in history:
            detail=event.details;ident=detail.get('record_id');at=wa.utc(event.created_at)
            previous=detail.get('previous_status');status=detail.get('status')
            if previous=='resolved' and status in ('open','pending'):opened[ident]=at
            elif status=='resolved' and previous in ('open','pending'):
                since=opened.pop(ident,None) or wa.utc(first_inbound.get(ident))
                if start<=at<end and since and since<=at:resolution.append((at-since).total_seconds())
        # Campaign attribution comes only from canonical delivery -> message links.
        if campaign_access:
            linked_deliveries=db.query(CustomerDelivery.automation_id,message.status,func.count(func.distinct(message.id))).join(message,CustomerDelivery.whatsapp_message_id==message.id).join(CustomerAutomation,CustomerAutomation.id==CustomerDelivery.automation_id).filter(CustomerDelivery.organization_id==company,CustomerDelivery.channel=='whatsapp',CustomerAutomation.organization_id==company,CustomerAutomation.trigger=='campaign',message.organization_id==company,message.contact_id.in_(allowed),message.created_at>=start,message.created_at<end).group_by(CustomerDelivery.automation_id,message.status).all()
            for automation,state,count in linked_deliveries:campaigns[str(automation)][state]+=count
    sent=sum(statuses[s] for s in ('sent','delivered','read'));delivered=statuses['delivered']+statuses['read']
    return {'from':start,'until':end,'teams':[{'id':t.id,'name':t.name} for t in teams],'totals':{**totals,'sent':sent,'delivered':delivered,'read':statuses['read'],'failed':statuses['failed'],'pending':sum(statuses[s] for s in ('queued','pending','reserved','submitting','accepted','reconciliation_required')),'pendingFollowUps':len(pending_ids)},
        'statuses':dict(statuses),'daily':[{'date':day,**counts} for day,counts in sorted(daily.items())],
        'templates':[{'name':name,'statuses':dict(counts)} for name,counts in sorted(templates.items())],
        'campaignsAvailable':campaign_access,'campaigns':[{'automationId':name,'statuses':dict(counts)} for name,counts in sorted(campaigns.items())],
        'workload':[{'employeeId':owner,'name':names.get(owner,'Unassigned' if owner is None else f'Employee #{owner}'),**counts} for owner,counts in workload.items()],
        'firstResponseSeconds':sum(first_response)/len(first_response) if first_response else None,'firstResponseSamples':len(first_response),
        'resolutionSeconds':sum(resolution)/len(resolution) if resolution else None,'resolutionSamples':len(resolution),'notes':['Message counts use creation time in the selected range. Delivery/read counts reflect current confirmed states.', 'First response measures the first confirmed reply after the first inbound message per conversation in this range.', 'Ownership, unread counts and pending CRM follow-ups are current state for conversations active in this range.', 'Resolution duration uses recorded resolve transitions in this range, measured from the last recorded reopen or first inbound message. Older transitions lacking previous-state evidence are excluded.']}
