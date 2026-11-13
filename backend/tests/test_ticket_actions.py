"""Native ticket access, reviewed workflows, versioning and local follow-ups."""
from datetime import date
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,approve,tick
from tests.test_suite_conversations import create,say,ROOT
from ai_test_utils import auth_headers
from app.models.employee import Employee
from app.models.helpdesk import HelpdeskTicket,HelpdeskReply
from app.apps.project_management.models import PMSProject
from app.ai_operator.ticket_actions import Status,Assign,Reply,Escalate,interpret
from app.ai_operator.local_nlp import parse,contexts


def seed(client,db):
    h,user,p,_=setup_suite(client,db)
    employee=Employee(employee_id='TICKET-'+uuid4().hex[:8],first_name='Synthetic',last_name='Requester',user_id=user.id,
        branch_id=db.get(PMSProject,p).branch_id,date_of_joining=date(2026,1,1))
    db.add(employee);db.commit();db.expire(user,['employee'])
    r=client.post('/api/v1/helpdesk/tickets/json',headers=h,json={'subject':'Synthetic support request','description':'Synthetic access issue'})
    assert r.status_code==201,r.text
    return h,user,r.json()['id']


def final(client,h,run):
    r=client.get(ROOT+f'/runs/{run["id"]}',headers=h);assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('text,intent',[
    ('HRMS: resolve ticket #12','ticket.status'),('Close ticket #12','ticket.status'),('Reopen ticket #12','ticket.status'),
    ('Update ticket #12 status: Pending','ticket.status'),('Assign ticket #12 user id: 4','ticket.assign'),
    ('Escalate ticket #12 reason: SLA missed','ticket.escalate'),('Reply to ticket #12 message: Please retry','ticket.reply'),
    ('Add internal note to ticket #12 message: Review access','ticket.reply'),
])
def test_explicit_local_ticket_actions(text,intent):
    value=parse(text,'HRMS');assert value.intent==intent and not value.question
    assert contexts(value)==[{'tool':'hrms.ticket','record_id':12}]


@pytest.mark.parametrize('model,payload',[
    (Status,{'status':'Deleted','expected_version':1}),(Status,{'status':'Closed'}),
    (Status,{'status':'Closed','expected_version':True}),(Assign,{'assign_to_user_id':True,'expected_version':1}),
    (Assign,{'assign_to_user_id':0,'expected_version':1}),
    (Reply,{'message':'Text','expected_version':1}),(Reply,{'message':' ','is_internal':False,'expected_version':1}),
    (Reply,{'message':'Text','is_internal':False,'expected_version':1,'organization_id':2}),
    (Escalate,{'escalation_reason':'Review','expected_version':0}),
])
def test_tool_payloads_require_version_visibility_and_valid_fields(model,payload):
    with pytest.raises(ValueError):model.model_validate(payload)


def test_ticket_number_overflow_is_a_clarification():
    assert interpret('Resolve ticket #'+('9'*5000)).question


def test_native_requester_cannot_read_other_ticket_or_post_internal_note(client,db):
    h,user,ident=seed(client,db)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','helpdesk_view'])
    assert client.get(f'/api/v1/helpdesk/tickets/{ident}',headers=other).status_code==404
    assert client.get(f'/api/v1/helpdesk/tickets/{ident}/replies',headers=other).status_code==404
    assert client.post(f'/api/v1/helpdesk/tickets/{ident}/reply/json',headers=other,json={'message':'Wrong ticket','is_internal':False,'expected_version':1}).status_code==404
    assert not any(r['id']==ident for r in client.get('/api/v1/helpdesk/tickets',headers=other).json())
    assert db.query(HelpdeskReply).count()==0


def test_native_versions_and_internal_notes_are_visible_only_to_staff(client,db):
    h,user,ident=seed(client,db)
    requester,actor=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','helpdesk_view'])
    employee=Employee(employee_id='REQUESTER-'+uuid4().hex[:8],first_name='Own',last_name='Request',user_id=actor.id,
        branch_id=db.get(Employee,user.employee.id).branch_id,date_of_joining=date(2026,1,1));db.add(employee);db.commit();db.expire(actor,['employee'])
    ticket=db.get(HelpdeskTicket,ident);ticket.employee_id=employee.id;db.commit()
    assert client.post(f'/api/v1/helpdesk/tickets/{ident}/reply/json',headers=requester,json={'message':'Private note','is_internal':True,'expected_version':1}).status_code==403
    r=client.post(f'/api/v1/helpdesk/tickets/{ident}/reply/json',headers=h,json={'message':'Staff only','is_internal':True,'expected_version':1});assert r.status_code==201,r.text
    assert client.get(f'/api/v1/helpdesk/tickets/{ident}',headers=h).json()['version']==2
    r=client.post(f'/api/v1/helpdesk/tickets/{ident}/reply/json',headers=requester,json={'message':'Requester reply','is_internal':False,'expected_version':1});assert r.status_code==409
    assert client.post(f'/api/v1/helpdesk/tickets/{ident}/reply/json',headers=requester,json={'message':'Requester reply','is_internal':False,'expected_version':2}).status_code==201
    assert len(client.get(f'/api/v1/helpdesk/tickets/{ident}/replies',headers=h).json())==2
    replies=client.get(f'/api/v1/helpdesk/tickets/{ident}/replies',headers=requester).json()
    assert len(replies)==1 and replies[0]['message']=='Requester reply'


def test_local_ticket_followups_prepare_exact_status_and_cancel_without_execution(client,db):
    h,user,ident=seed(client,db);chat=create(client,h)
    value=say(client,h,chat,'HRMS: update ticket')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,f'ticket #{ident}')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,'yes');assert value['status']=='needs_clarification'
    value=say(client,h,chat,'status: Pending')
    assert value['status']=='awaiting_approval',value
    assert value['plan']['steps'][0]['payload']=={'status':'Pending','expected_version':1}
    assert value['result']['ticket_changes']['1']['changes']==[{'field':'status','before':'Open','after':'Pending'}]
    assert db.get(HelpdeskTicket,ident).status=='Open'
    cancelled=say(client,h,chat,'cancel');assert cancelled['status']=='answered' and not cancelled['plan']['steps']
    assert tick(client,db)==0


def test_reviewed_same_ticket_workflow_assigns_replies_escalates_and_resolves(client,db):
    h,user,ident=seed(client,db)
    member,recipient=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['helpdesk_view'])
    value=prepare(client,h,[
        {'tool':'hrms.assign_ticket','record_id':ident,'payload':{'assign_to_user_id':recipient.id,'expected_version':1}},
        {'tool':'hrms.reply_ticket','record_id':ident,'payload':{'message':'Synthetic progress update','is_internal':False,'expected_version':2}},
        {'tool':'hrms.escalate_ticket','record_id':ident,'payload':{'escalation_reason':'Synthetic escalation review','expected_version':3}},
        {'tool':'hrms.status_ticket','record_id':ident,'payload':{'status':'Resolved','expected_version':4}},
    ])
    assert value['status']=='awaiting_approval',value
    assert db.query(HelpdeskReply).count()==0
    approve(client,h,value);assert tick(client,db)==4
    completed=final(client,h,value);assert completed['status']=='succeeded',completed
    assert len(completed['receipts'])==4
    assert all(c['href']=='/hrms/helpdesk' for c in completed['result_cards'])
    db.expire_all();ticket=db.get(HelpdeskTicket,ident)
    assert ticket.status=='Resolved' and ticket.priority=='Critical' and ticket.assigned_to==recipient.id and ticket.version==5
    assert db.query(HelpdeskReply).count()==1
    approve(client,h,completed);assert tick(client,db)==0 and db.query(HelpdeskReply).count()==1


def test_ticket_change_after_review_pauses_and_preserves_external_change(client,db):
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.status_ticket','record_id':ident,'payload':{'status':'Resolved','expected_version':1}}]);approve(client,h,value)
    assert client.put(f'/api/v1/helpdesk/tickets/{ident}/status/json',headers=h,json={'status':'Pending','expected_version':1}).status_code==200
    tick(client,db);completed=final(client,h,value)
    assert completed['status']=='paused' and completed['error_code']=='CANONICAL_STEP_409',completed
    db.expire_all();assert db.get(HelpdeskTicket,ident).status=='Pending'


def test_read_only_staff_cannot_prepare_ticket_status_update(client,db):
    h,user,ident=seed(client,db)
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','helpdesk_view'])
    value=prepare(client,headers,[{'tool':'hrms.status_ticket','record_id':ident,'payload':{'status':'Closed','expected_version':1}}])
    assert value['status']=='failed' and not value['approval_id']


def test_native_assignment_rejects_inactive_user_without_mutating_ticket(client,db):
    h,user,ident=seed(client,db)
    _,recipient=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['helpdesk_view'])
    recipient.is_active=False;db.commit()
    r=client.put(f'/api/v1/helpdesk/tickets/{ident}/assign/json',headers=h,json={'assign_to_user_id':recipient.id,'expected_version':1})
    assert r.status_code==422,r.text
    db.expire_all();ticket=db.get(HelpdeskTicket,ident)
    assert ticket.assigned_to is None and ticket.version==1


def test_cross_company_ticket_and_assignee_are_rejected(client,db):
    from app.models.company import Company,Branch
    h,user,ident=seed(client,db)
    other=Company(name='Other synthetic ticket company',is_active=True);db.add(other);db.flush()
    branch=Branch(company_id=other.id,name='Other ticket branch');db.add(branch);db.flush()
    employee=Employee(employee_id='OTHER-'+uuid4().hex[:8],first_name='Foreign',last_name='Requester',date_of_joining=date(2026,1,1),branch_id=branch.id);db.add(employee);db.flush()
    ticket=HelpdeskTicket(organization_id=other.id,employee_id=employee.id,ticket_number='OTHER-'+uuid4().hex[:8],subject='Foreign canary',description='Other company issue');db.add(ticket);db.commit();foreign_id=ticket.id
    assert client.get(f'/api/v1/helpdesk/tickets/{foreign_id}',headers=h).status_code==404
    assert client.put(f'/api/v1/helpdesk/tickets/{foreign_id}/status/json',headers=h,json={'status':'Closed','expected_version':1}).status_code==404
    _,recipient=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['helpdesk_view'],company_id=other.id)
    assert client.put(f'/api/v1/helpdesk/tickets/{ident}/assign/json',headers=h,json={'assign_to_user_id':recipient.id,'expected_version':1}).status_code==422
    db.expire_all();assert db.get(HelpdeskTicket,ident).assigned_to is None


def test_created_ticket_receipt_can_target_a_reviewed_dependent_update(client,db):
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.create_ticket','payload':{'subject':'Dependent synthetic ticket','description':'Synthetic dependent issue'}},
        {'tool':'hrms.status_ticket','record_id':{'$step':1,'field':'id'},'payload':{'status':'Pending','expected_version':1}}])
    assert value['status']=='awaiting_approval',value
    approve(client,h,value);assert tick(client,db)==2
    completed=final(client,h,value);assert completed['status']=='succeeded',completed
    created=db.query(HelpdeskTicket).filter_by(subject='Dependent synthetic ticket').one()
    assert created.id!=ident and created.status=='Pending' and created.version==2


def test_ticket_reply_lost_receipt_is_not_automatically_repeated(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.reply_ticket','record_id':ident,'payload':{'message':'Synthetic exact reply','is_internal':False,'expected_version':1}}]);approve(client,h,value)
    original=suite.api_call;posted=[]
    async def lost(app,auth,method,path,payload=None,**kwargs):
        result=await original(app,auth,method,path,payload,**kwargs)
        if path.endswith('/reply/json'):
            posted.append(path);raise RuntimeError('Synthetic lost reply receipt')
        return result
    monkeypatch.setattr(suite,'api_call',lost)
    tick(client,db);assert final(client,h,value)['status']=='needs_reconciliation'
    assert db.query(HelpdeskReply).count()==1
    assert tick(client,db)==0 and len(posted)==1 and db.query(HelpdeskReply).count()==1


def test_native_version_rejects_write_between_final_read_and_dispatch(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.status_ticket','record_id':ident,'payload':{'status':'Resolved','expected_version':1}}]);approve(client,h,value)
    original=suite.api_call;changed=[]
    async def concurrent(app,auth,method,path,payload=None,**kwargs):
        if path==f'/helpdesk/tickets/{ident}/status/json' and method=='PUT' and not changed:
            changed.append(True);await original(app,auth,method,path,{'status':'Pending','expected_version':1})
        return await original(app,auth,method,path,payload,**kwargs)
    monkeypatch.setattr(suite,'api_call',concurrent)
    tick(client,db);completed=final(client,h,value)
    assert completed['status']=='needs_reconciliation' and completed['error_code']=='CANONICAL_STEP_409',completed
    db.expire_all();assert db.get(HelpdeskTicket,ident).status=='Pending'


def test_requester_reply_and_internal_note_visibility_are_explicit_local_drafts(client,db):
    h,user,ident=seed(client,db)
    for command,internal in [('Reply to ticket',False),('Add internal note to ticket',True)]:
        chat=create(client,h);value=say(client,h,chat,f'HRMS: {command} #{ident}')
        assert value['status']=='needs_clarification'
        value=say(client,h,chat,'message: Synthetic reviewed response')
        assert value['status']=='awaiting_approval',value
        assert value['plan']['steps'][0]['payload']['is_internal'] is internal
        assert ('internal staff note' if internal else 'visible to the requester') in value['plan']['summary']
        assert db.query(HelpdeskReply).count()==0
        say(client,h,chat,'cancel')


def test_ticket_projection_excludes_admin_diagnostics_and_attachment_urls():
    from app.ai_operator.ticket_actions import projection
    value=projection({'id':12,'subject':'Help','description':'Request','version':1,'detail_json':{'relatedErrors':['Private diagnostics']},'attachment_url':'Private file','ai_suggested_reply':'Unreviewed text'})
    assert value=={'id':12,'subject':'Help','description':'Request','version':1}


def test_escalation_reason_cannot_be_blank_and_does_not_clear_existing_recipient(client,db):
    h,user,ident=seed(client,db)
    with pytest.raises(ValueError):Escalate.model_validate({'escalation_reason':' ','expected_version':1})
    ticket=db.get(HelpdeskTicket,ident);ticket.escalated_to=user.id;db.commit()
    r=client.put(f'/api/v1/helpdesk/tickets/{ident}/escalate',headers=h,json={'escalation_reason':'Review urgency','expected_version':1})
    assert r.status_code==200,r.text
    db.expire_all();assert db.get(HelpdeskTicket,ident).escalated_to==user.id


@pytest.mark.parametrize('text,expected',[
    ('message: Please retry, status: Pending','Please retry, status: Pending'),
    ('message: "Please retry, user id: 4"','Please retry, user id: 4'),
    ('message: The response was "yes"','The response was "yes"'),
])
def test_reply_body_labels_remain_literal_content(text,expected):
    from app.ai_operator.ticket_actions import fields
    assert fields(text)=={'message':expected}


def test_enterprise_diagnostics_ticket_does_not_leak_through_hr_sla_or_analytics(client,db):
    from datetime import datetime,timedelta,timezone
    from app.services.helpdesk_access import company
    h,user,ident=seed(client,db)
    private=HelpdeskTicket(organization_id=company(user),module_key='crm',ticket_number='ADMIN-'+uuid4().hex[:8],
        subject='Private enterprise diagnostics',description='Not an HR ticket',detail_json={'relatedErrors':['Canary diagnostics']},
        resolution_due_at=datetime.now(timezone.utc)-timedelta(hours=2))
    db.add(private);db.commit();private_id=private.id
    assert client.get(f'/api/v1/helpdesk/tickets/{private_id}',headers=h).status_code==404
    assert private_id not in {r['id'] for r in client.get('/api/v1/helpdesk/tickets',headers=h).json()}
    assert private_id not in {r['id'] for r in client.get('/api/v1/helpdesk/sla/breaches',headers=h).json()}
    result=client.get('/api/v1/helpdesk/analytics',headers=h)
    assert result.status_code==200,result.text
    assert result.json()['total']==1


def test_legacy_ticket_without_company_keeps_authorized_employee_access(client,db):
    h,user,ident=seed(client,db)
    row=db.get(HelpdeskTicket,ident);row.organization_id=None;db.commit()
    assert client.get(f'/api/v1/helpdesk/tickets/{ident}',headers=h).status_code==200


def test_cloud_planner_reads_exact_requested_ticket_instead_of_first_page(client,db,monkeypatch):
    from tests.test_ai_operator import mock_provider
    from app.ai_operator import suite
    h,user,ident=seed(client,db)
    provider_calls=mock_provider(monkeypatch,{'summary':'Review closing the selected ticket','steps':[
        {'tool':'hrms.status_ticket','record_id':ident,'payload':{'status':'Closed','expected_version':1}}]})
    original=suite.api_call;reads=[]
    async def observe(app,auth,method,path,payload=None,**kwargs):
        if method=='GET':reads.append(path)
        return await original(app,auth,method,path,payload,**kwargs)
    monkeypatch.setattr(suite,'api_call',observe)
    response=client.post(ROOT+'/commands',headers=h,json={'provider':'gemini','module':'HRMS','request_key':str(uuid4()),'text':f'Close ticket #{ident}'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='awaiting_approval',response.json()
    assert f'/helpdesk/tickets/{ident}' in reads
    assert '/helpdesk/tickets' not in reads
    assert any(b'helpdesk_planning_policy' in request.content for request in provider_calls)
    assert db.get(HelpdeskTicket,ident).status=='Open'


def test_requester_can_review_own_reply_but_cannot_preview_internal_staff_note(client,db):
    from app.access.models import AccessPolicy
    from app.services.helpdesk_access import company
    h,user,ident=seed(client,db)
    headers,actor=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','helpdesk_view'])
    employee=Employee(employee_id='SELF-'+uuid4().hex[:8],first_name='Own',last_name='Requester',user_id=actor.id,
        branch_id=user.employee.branch_id,date_of_joining=date(2026,1,1));db.add(employee);db.flush()
    db.get(HelpdeskTicket,ident).employee_id=employee.id;db.commit();db.expire(actor,['employee'])
    read_only=prepare(client,headers,[{'tool':'hrms.reply_ticket','record_id':ident,'payload':{'message':'Own requester reply','is_internal':False,'expected_version':1}}])
    assert read_only['status']=='failed' and not read_only['approval_id']
    # Native self-service access does not override central AI write policy.
    db.add(AccessPolicy(company_id=company(user),user_id=actor.id,status='active',grants={
        'ai':{'enabled':True,'role':'Employee','scope':'own','permissions':['ai_assistant'],'actions':['view','create','approve']},
        'hrms':{'enabled':True,'role':'Requester','scope':'own','permissions':['helpdesk_view'],'actions':['view','create']},
    }));db.commit()
    assert client.get('/api/v1/project-management/projects',headers=headers).status_code==403
    denied=prepare(client,headers,[{'tool':'hrms.reply_ticket','record_id':ident,'payload':{'message':'Private staff note','is_internal':True,'expected_version':1}}])
    assert denied['status']=='failed' and not denied['approval_id']
    chat=create(client,headers)
    assert client.get(ROOT+f'/conversations/{chat}',headers=headers).status_code==200
    draft=prepare(client,headers,[{'tool':'hrms.reply_ticket','record_id':ident,'payload':{'message':'Own requester reply','is_internal':False,'expected_version':1}}],conversation_id=chat)
    assert draft['status']=='awaiting_approval',(draft['status'],draft['error_code'])
    approve(client,headers,draft);tick(client,db)
    assert final(client,headers,draft)['status']=='succeeded'
    assert db.query(HelpdeskReply).one().message=='Own requester reply'


def test_suite_route_classification_is_ai_and_does_not_reclassify_pms_operator(monkeypatch):
    from types import SimpleNamespace
    from starlette.requests import Request
    from app.access.catalog import request_module,ROUTES
    for path in ('/api/v1/ai-operator/suite','/api/v1/ai-operator/suite/commands','/api/v1/ai-operator/suite/runs/12/approve'):
        assert request_module(Request({'type':'http','method':'POST','path':path,'headers':[]}))=='ai'
    def legacy_endpoint():pass
    route=SimpleNamespace(path='/api/v1/ai-operator/plans',endpoint=legacy_endpoint)
    monkeypatch.setitem(ROUTES,(id(legacy_endpoint),'/ai-operator/plans','POST'),'project_management')
    assert request_module(Request({'type':'http','method':'POST','path':'/api/v1/ai-operator/plans','headers':[],'route':route}))=='project_management'
