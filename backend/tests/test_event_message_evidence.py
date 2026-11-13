import asyncio
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_agent_events import control
from tests.test_agent_whatsapp_events import prepare as whatsapp,receive as receive_whatsapp
from tests.test_agent_email_events import prepare as email,receive as receive_email
from tests.test_agent_message_events import prepare as chat,send
from tests.test_bot_artifacts import command
from app.ai_operator import agent_events as events,agent_schedules as schedules,event_messages
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator.suite_models import SuiteRun

ROOT='/api/v1/ai-operator/suite'
READ=ROOT+'/agents/events/message-content'


def occurrence(client,db,monkeypatch,kind,enabled=True,write_tool=False):
    if kind=='whatsapp':
        h,contact,connection,draft,spec=whatsapp(client,db,monkeypatch,action=write_tool,message_read=enabled)
        control(client,h,draft,'activate');assert receive_whatsapp(client,db,connection,'wamid.evidence').status_code==200
    elif kind=='email':
        h,customer,secret,thread,draft,spec=email(client,db,message_read=enabled)
        control(client,h,draft,'activate');assert receive_email(client,customer,secret,thread,'evidence-reply').status_code==200
    else:
        h,user,other,oh,path,draft,spec=chat(client,db,message_read=enabled)
        control(client,h,draft,'activate');send(client,path,oh)
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    run=db.get(SuiteRun,pending['run_id'])
    return h,spec,pending['conversation_id'],run


@pytest.mark.parametrize('kind',['whatsapp','email','chat'])
def test_explicit_message_read_returns_exact_citation_and_no_action(client,db,monkeypatch,kind):
    h,spec,conversation,run=occurrence(client,db,monkeypatch,kind)
    assert run.status=='answered',run.result
    assert run.result['message_task_available'] is False
    assert run.result['message_action_options']==[]
    assert 'UNTRUSTED' in run.plan['summary'] and not run.receipts and run.approval_id is None
    citation=run.result['citations'][0];assert event_messages.lineage([citation])==[citation['id']]
    module='PMS' if kind=='chat' else 'CRM';hashed=citation['id'].split(':')[-1]
    params={'conversation_id':conversation,'agent_id':spec['agent_id'],'module':module,'expected_digest':hashed}
    response=client.get(READ,headers=h,params=params);assert response.status_code==200,response.text
    assert response.json()['content_hash']==hashed and 'UNTRUSTED' in response.json()['text']
    assert 'no-store' in response.headers['Cache-Control']
    assert client.get(READ,headers=h,params={**params,'agent_id':spec['agent_id']+99999}).status_code==403


def test_disabled_message_read_tool_never_exposes_content(client,db,monkeypatch):
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',False)
    response=client.get(READ,headers=h,params={'conversation_id':conversation,'agent_id':spec['agent_id'],'module':'CRM'})
    assert response.status_code==403 and 'UNTRUSTED' not in response.text


def test_edited_message_invalidates_old_citation_and_fresh_read_gets_new_hash(client,db,monkeypatch):
    from app.shared.whatsapp_models import WhatsAppMessage
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp')
    old=run.result['citations'][0]['id'];source=db.query(WhatsAppMessage).order_by(WhatsAppMessage.id.desc()).first()
    source.body='Updated customer request';db.commit()
    response=client.get(READ,headers=h,params={'conversation_id':conversation,'agent_id':spec['agent_id'],'module':'CRM','expected_digest':old.split(':')[-1]})
    assert response.status_code==409,response.text
    answer=command(client,h,'CRM','Read this message',conversation_id=conversation,agent_id=spec['agent_id'])
    assert answer['status']=='answered' and answer['result']['citations'][0]['id']!=old
    assert 'Updated customer request' in answer['plan']['summary']


def test_model_receives_untrusted_message_with_citations_and_not_prior_assistant_quotes(client,db,monkeypatch):
    from app.ai_operator import suite
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp')
    def generate(*args,**kwargs):
        value=json.loads(kwargs['prompt'])
        assert all(t['name'].endswith('.event_message') and not t['approval_required'] for t in value['tools'])
        assert 'UNTRUSTED' not in str(value['conversation_newest_first'])
        packet=value['authorized_context'][0]['records'];assert 'UNTRUSTED' in packet['text']
        assert 'never' in value['message_evidence_policy']
        return {'summary':'The sender text contains an untrusted request; no action was performed.','steps':[],'source_ids':[packet['source_citation']['id']]}
    monkeypatch.setattr(suite,'generate_json',generate)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM',
        'agent_id':spec['agent_id'],'conversation_id':conversation,'text':'Summarize this message'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='answered' and not response.json()['receipts'],response.json()


@pytest.mark.parametrize('failure',['erasure','no_citation','unexpected_write'])
def test_message_generation_rechecks_access_and_requires_cited_read_only_answers(client,db,monkeypatch,failure):
    from app.ai_operator import suite
    from app.shared.whatsapp_models import WhatsAppContact
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',write_tool=True)
    def generate(*args,**kwargs):
        packet=json.loads(kwargs['prompt'])['authorized_context'][0]['records']
        if failure=='erasure':
            db.query(WhatsAppContact).filter_by(id=spec['whatsapp_contact_id']).one().erased_at=datetime.now(timezone.utc);db.commit()
        return {'summary':'STALE_OR_UNREVIEWED_RESPONSE','steps':[{'tool':'crm.create_task','payload':{'title':'Not authorized by this read question'}}] if failure=='unexpected_write' else [],
            'source_ids':[] if failure=='no_citation' else [packet['source_citation']['id']]}
    monkeypatch.setattr(suite,'generate_json',generate)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM',
        'agent_id':spec['agent_id'],'conversation_id':conversation,'text':'Read this message'})
    assert response.status_code==200,response.text
    result=response.json();assert result['status']=='failed' and not result['receipts'] and result['approval_id'] is None,result
    assert 'STALE_OR_UNREVIEWED_RESPONSE' not in str(result.get('plan'))


def test_message_citation_cannot_read_another_users_private_occurrence(client,db,monkeypatch):
    from tests.test_agent_library import member
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp')
    outsider,_=member(client,db)
    response=client.get(READ,headers=outsider,params={'conversation_id':conversation,'agent_id':spec['agent_id'],'module':'CRM'})
    assert response.status_code==404 and 'UNTRUSTED' not in response.text


def test_message_edit_blocks_sourced_draft_approval_and_read_questions_preserve_pending_actions(client,db,monkeypatch):
    from app.shared.whatsapp_models import WhatsAppMessage
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',write_tool=True)
    source_id=run.result['citations'][0]['id']
    draft=command(client,h,'CRM','Prepare a followup task',conversation_id=conversation,agent_id=spec['agent_id'],
        context=[{'tool':'crm.event_message'}],local_plan={'summary':'Review a sourced followup','source_ids':[source_id],
            'steps':[{'tool':'crm.create_task','payload':{'title':'Review customer request'}}]})
    assert draft['status']=='awaiting_approval',(draft.get('error_code'),draft.get('result',{}).get('planning_issue'))
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'agent_id':spec['agent_id'],'conversation_id':conversation,'text':'Read this message'})
    assert response.status_code==409,response.text
    assert client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()['status']=='awaiting_approval'
    db.query(WhatsAppMessage).order_by(WhatsAppMessage.id.desc()).first().body='A changed customer request';db.commit()
    response=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==409,response.text


@pytest.mark.parametrize('alternate_branch',[False,True])
def test_conversational_message_action_refreshes_stale_review_and_executes_once(client,db,monkeypatch,alternate_branch):
    from app.ai_operator import suite
    from app.apps.crm.models import CRMTask
    from app.shared.whatsapp_models import WhatsAppMessage
    from tests.test_suite_operator import approve,tick
    h,contact,connection,review,spec=whatsapp(client,db,monkeypatch,action=True,message_read=True,alternate_branch=alternate_branch)
    control(client,h,review,'activate');assert receive_whatsapp(client,db,connection,'wamid.action-refresh').status_code==200
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    occurrence_data=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=occurrence_data['conversation_id']
    message=db.query(WhatsAppMessage).order_by(WhatsAppMessage.id.desc()).first()
    message.body='Please arrange a delivery call for the initial order.';db.commit()
    calls=[]
    def generate(*args,**kwargs):
        prompt=json.loads(kwargs['prompt']);calls.append(prompt)
        assert {'crm.event_message','crm.create_task'}<={t['name'] for t in prompt['tools']}
        packets=[p['records'] for p in prompt['authorized_context'] if p['tool']=='crm.event_message']
        if not packets:
            return {'summary':'Retrieve the authorized source before drafting.','steps':[],
                'context_requests':[{'tool':'crm.event_message','payload':{}}]}
        assert len(packets)==1
        source=packets[0]
        title='Confirm revised delivery date' if 'revised' in source['text'] else 'Arrange delivery call'
        return {'summary':'Review this follow-up draft; no task has been created.','source_ids':[source['source_citation']['id']],
            'steps':[{'tool':'crm.create_task','payload':{'title':title}}]}
    monkeypatch.setattr(suite,'generate_json',generate)
    def request(text,key=None):
        body={'request_key':key or str(uuid4()),'provider':'gemini','module':'CRM',
            'agent_id':spec['agent_id'],'conversation_id':conversation,'text':text}
        response=client.post(ROOT+'/commands',headers=h,json=body)
        assert response.status_code==200,response.text
        result=response.json();assert result['status']=='awaiting_approval',result
        return result,body
    draft,_=request('Prepare a follow-up task from this message')
    assert len(calls)==2 and db.query(CRMTask).count()==0
    old_id=draft['result']['citations'][0]['id']
    message.body='Please confirm the revised delivery date instead.';db.commit()
    blocked=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert blocked.status_code==409,blocked.text
    fresh,body=request('Re-read the updated message and prepare a fresh follow-up task')
    assert fresh['result']['citations'][0]['id']!=old_id
    assert fresh['plan']['steps'][0]['payload']['title']=='Confirm revised delivery date'
    assert client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()['status']=='superseded'
    assert client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409
    retry=client.post(ROOT+'/commands',headers=h,json=body)
    assert retry.status_code==200 and retry.json()['id']==fresh['id']
    approve(client,h,fresh);tick(client,db);tick(client,db)
    result=client.get(ROOT+f'/runs/{fresh["id"]}',headers=h).json()
    assert result['status']=='succeeded',result
    assert len(result['receipts'])==1 and result['receipts'][0]['status']=='succeeded'
    assert db.query(CRMTask).count()==1 and db.query(CRMTask).one().title=='Confirm revised delivery date'


@pytest.mark.parametrize('wording',['Create a task from this message','Please draft a follow-up task about this WhatsApp message.'])
def test_local_message_task_collects_title_cites_sender_and_executes_only_after_review(client,db,monkeypatch,wording):
    from app.apps.crm.models import CRMTask
    from tests.test_suite_operator import approve,tick
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',write_tool=True)
    def say(text):
        return command(client,h,'CRM',text,conversation_id=conversation,agent_id=spec['agent_id'])
    assert run.result['message_task_available'] is True
    question=say(wording)
    assert question['status']=='needs_clarification' and question['result']['message_action_query'],question
    assert question['result']['local_nlp']['slots']['_awaiting']=='title'
    assert question['result']['citations'] and not question['plan']['steps']
    ambiguous=say('yes')
    assert ambiguous['status']=='needs_clarification' and db.query(CRMTask).count()==0
    draft=say('Review delivery commitment')
    assert draft['status']=='awaiting_approval',draft
    assert draft['plan']['steps'][0]['payload']['title']=='Review delivery commitment'
    assert 'UNTRUSTED' in draft['plan']['steps'][0]['payload']['description']
    assert draft['result']['citations'][0]['id']==run.result['citations'][0]['id']
    revised=say('change title to "Confirm delivery call"')
    assert revised['status']=='awaiting_approval',revised
    assert revised['plan']['steps'][0]['payload']['title']=='Confirm delivery call'
    assert revised['result']['citations'] and db.query(CRMTask).count()==0
    approve(client,h,revised);tick(client,db);tick(client,db)
    assert db.query(CRMTask).count()==1 and db.query(CRMTask).one().title=='Confirm delivery call'
    assert client.get(ROOT+f'/runs/{revised["id"]}',headers=h).json()['status']=='succeeded'


def test_local_message_task_can_cancel_title_collection(client,db,monkeypatch):
    from app.apps.crm.models import CRMTask
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',write_tool=True)
    first=command(client,h,'CRM','Create a task from this message',conversation_id=conversation,agent_id=spec['agent_id'])
    assert first['status']=='needs_clarification',first
    result=command(client,h,'CRM','cancel it',conversation_id=conversation,agent_id=spec['agent_id'])
    assert result['status']=='answered',result
    assert not result['plan']['steps'] and db.query(CRMTask).count()==0
    assert client.get(ROOT+f'/runs/{first["id"]}',headers=h).json()['status']=='cancelled'


@pytest.mark.parametrize('explicit_project',[False,True])
def test_pms_message_task_collects_authorized_project_and_title_then_creates_once(client,db,explicit_project):
    from app.apps.project_management.models import PMSProject,PMSTask
    from tests.test_suite_operator import approve,tick
    h,user,other,oh,path,review,spec=chat(client,db,message_read=True,write_tool=True)
    workspace=int(path.split('/workspaces/')[1].split('/')[0])
    project=db.query(PMSProject).filter_by(workspace_id=workspace).first()
    before=db.query(PMSTask).count()
    control(client,h,review,'activate');send(client,path,oh)
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=pending['conversation_id']
    def say(text,**extra):
        return command(client,h,'PMS',text,workspace_id=workspace,conversation_id=conversation,agent_id=spec['agent_id'],**extra)
    first=say('Create a PMS task from this message')
    assert first['status']=='needs_clarification',first
    assert first['result']['local_nlp']['slots']['_awaiting']=='project_id'
    assert first['result']['request']['project_id'] is None and first['result']['citations']
    selected=say(f'project #{project.id}',**({'project_id':project.id} if explicit_project else {}))
    assert selected['status']=='needs_clarification',selected
    assert selected['result']['request']['project_id']==project.id
    assert selected['result']['local_nlp']['slots']['_awaiting']=='title'
    draft=say('Review project delivery commitment')
    assert draft['status']=='awaiting_approval',draft
    step=draft['plan']['steps'][0]
    assert step['tool']=='pms.create_task' and step['record_id']==project.id
    assert 'UNTRUSTED' in step['payload']['description'] and draft['result']['citations']
    rejected=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'text':'change title to "Other project"','workspace_id':workspace,'agent_id':spec['agent_id'],
        'conversation_id':conversation,'project_id':project.id+9999})
    assert rejected.status_code==409,rejected.text
    assert db.query(PMSTask).count()==before
    revised=say('change title to "Confirm implementation deadline"')
    assert revised['status']=='awaiting_approval',revised
    assert revised['plan']['steps'][0]['payload']['title']=='Confirm implementation deadline'
    assert revised['result']['citations'][0]['id']==first['result']['citations'][0]['id']
    approve(client,h,revised);tick(client,db);tick(client,db)
    result=client.get(ROOT+f'/runs/{revised["id"]}',headers=h).json()
    assert result['status']=='succeeded' and len(result['receipts'])==1,result
    assert db.query(PMSTask).count()==before+1
    created=db.query(PMSTask).filter_by(title='Confirm implementation deadline').one()
    assert created.project_id==project.id



def test_local_message_draft_does_not_silently_substitute_the_requested_module(client,db,monkeypatch):
    from app.apps.crm.models import CRMTask
    h,spec,conversation,run=occurrence(client,db,monkeypatch,'whatsapp',write_tool=True)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'agent_id':spec['agent_id'],'conversation_id':conversation,'text':'Create a PMS task from this message'})
    assert response.status_code==403,response.text
    assert 'must be enabled' in response.json()['detail'] and db.query(CRMTask).count()==0


@pytest.mark.parametrize('alternate_branch',[False,True])
def test_local_crm_message_can_create_reviewed_pms_task_in_authorized_workspace(client,db,monkeypatch,alternate_branch):
    from app.apps.project_management.models import PMSProject,PMSTask
    from app.apps.crm.models import CRMTask
    from tests.test_suite_operator import approve,tick
    h,contact,connection,review,spec=whatsapp(client,db,monkeypatch,action=True,message_read=True,cross_module=True,alternate_branch=alternate_branch)
    workspace=review['workspace_id'];project=db.query(PMSProject).filter_by(workspace_id=workspace).first()
    before=db.query(PMSTask).count()
    control(client,h,review,'activate');assert receive_whatsapp(client,db,connection,'wamid.cross-module').status_code==200
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=pending['conversation_id']
    def say(module,text):
        return command(client,h,module,text,workspace_id=workspace,conversation_id=conversation,agent_id=spec['agent_id'])
    first=say('CRM','Create a PMS task from this message')
    assert first['status']=='needs_clarification',first
    assert first['result']['request']['module']=='PMS' and first['result']['request']['project_id'] is None
    assert first['result']['local_nlp']['slots']['_awaiting']=='project_id'
    citation=first['result']['citations'][0]['id'];assert ':CRM:' in citation
    selected=say('PMS',f'project #{project.id}')
    assert selected['status']=='needs_clarification' and selected['result']['local_nlp']['slots']['_awaiting']=='title',selected
    draft=say('PMS','Confirm customer delivery commitment')
    assert draft['status']=='awaiting_approval',draft
    assert draft['plan']['steps'][0]['tool']=='pms.create_task'
    assert draft['plan']['steps'][0]['record_id']==project.id
    assert draft['result']['citations'][0]['id']==citation
    assert db.query(CRMTask).count()==0 and db.query(PMSTask).count()==before
    approve(client,h,draft);tick(client,db);tick(client,db)
    result=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert result['status']=='succeeded',result
    assert len(result['receipts'])==1 and db.query(PMSTask).count()==before+1
    assert db.query(PMSTask).filter_by(title='Confirm customer delivery commitment',project_id=project.id).count()==1
    assert db.query(CRMTask).count()==0


@pytest.mark.parametrize('destination_write',[False,True])
def test_local_pms_message_to_crm_task_requires_destination_tool_and_preserves_source(client,db,destination_write):
    from app.apps.project_management.models import PMSTask
    from app.apps.crm.models import CRMTask
    from tests.test_suite_operator import approve,tick
    h,user,other,oh,path,review,spec=chat(client,db,message_read=True,cross_module=True,destination_write=destination_write)
    workspace=review['workspace_id'];before=db.query(PMSTask).count()
    control(client,h,review,'activate');send(client,path,oh)
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=pending['conversation_id']
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'workspace_id':workspace,'conversation_id':conversation,'agent_id':spec['agent_id'],'text':'Create a CRM task from this message'})
    if not destination_write:
        assert response.status_code==403,response.text
        assert 'creation tool' in response.json()['detail']
    else:
        assert response.status_code==200,response.text
        first=response.json();assert first['status']=='needs_clarification',first
        assert first['result']['request']['module']=='CRM' and first['result']['request']['project_id'] is None
        assert first['result']['local_nlp']['slots']['_awaiting']=='title'
        source=first['result']['citations'][0]['id'];assert ':PMS:' in source
        draft=command(client,h,'CRM','Call customer about project delivery',workspace_id=workspace,conversation_id=conversation,agent_id=spec['agent_id'])
        assert draft['status']=='awaiting_approval',draft
        assert draft['plan']['steps'][0]['tool']=='crm.create_task' and draft['result']['citations'][0]['id']==source
        assert db.query(CRMTask).count()==0
        approve(client,h,draft);tick(client,db);tick(client,db)
        result=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
        assert result['status']=='succeeded' and len(result['receipts'])==1,result
        assert db.query(CRMTask).count()==1 and db.query(CRMTask).one().title=='Call customer about project delivery'
    assert db.query(PMSTask).count()==before


@pytest.mark.parametrize('alternate_branch,write_enabled',[(False,True),(True,True),(False,False)])
def test_crm_message_to_local_hr_ticket_preserves_citation_and_requires_review(client,db,monkeypatch,alternate_branch,write_enabled):
    from app.models.helpdesk import HelpdeskTicket
    from app.models.employee import Employee
    from tests.test_suite_operator import approve,tick
    h,contact,connection,review,spec=whatsapp(client,db,monkeypatch,action=True,message_read=True,hr_ticket=True,hr_ticket_write=write_enabled,alternate_branch=alternate_branch)
    control(client,h,review,'activate');assert receive_whatsapp(client,db,connection,'wamid.hr-ticket').status_code==200
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=pending['conversation_id']
    read=db.get(SuiteRun,pending['run_id'])
    assert ('HRMS' in {o['module'] for o in read.result['message_action_options']}) is write_enabled
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'conversation_id':conversation,'agent_id':spec['agent_id'],'text':'Create an HR ticket from this message'})
    if not write_enabled:
        assert response.status_code==403,response.text
        assert db.query(HelpdeskTicket).count()==0
        return
    assert response.status_code==200,response.text
    first=response.json();assert first['status']=='needs_clarification',first
    assert first['result']['request']['module']=='HRMS' and first['result']['local_nlp']['slots']['_awaiting']=='title'
    citation=first['result']['citations'][0]['id'];assert ':CRM:' in citation
    def say(text):return command(client,h,'HRMS',text,conversation_id=conversation,agent_id=spec['agent_id'])
    assert say('yes')['status']=='needs_clarification'
    draft=say('Request staffing support for customer delivery')
    assert draft['status']=='awaiting_approval',(draft.get('error_code'),draft['result'].get('planning_issue'),draft['result'].get('local_nlp'))
    assert draft['plan']['steps'][0]['tool']=='hrms.create_ticket'
    assert 'UNTRUSTED' in draft['plan']['steps'][0]['payload']['description']
    assert draft['result']['citations'][0]['id']==citation and db.query(HelpdeskTicket).count()==0
    revised=say('change title to "Delivery staffing assistance"')
    assert revised['status']=='awaiting_approval',revised
    assert revised['plan']['steps'][0]['payload']['subject']=='Delivery staffing assistance'
    assert revised['result']['citations'][0]['id']==citation
    approve(client,h,revised);tick(client,db);tick(client,db)
    result=client.get(ROOT+f'/runs/{revised["id"]}',headers=h).json()
    assert result['status']=='succeeded' and len(result['receipts'])==1,result
    ticket=db.query(HelpdeskTicket).one();assert ticket.subject=='Delivery staffing assistance'
    employee=db.get(Employee,ticket.employee_id);assert employee.user_id==db.get(SuiteRun,revised['id']).user_id
    assert db.query(HelpdeskTicket).count()==1
    from app.branches.models import BranchOwnership
    owned=db.query(BranchOwnership).filter_by(resource_table='helpdesk_tickets',resource_key=str(ticket.id)).one()
    assert owned.branch_id==job.payload_json['branch_id']


def test_pms_message_can_become_a_local_hr_ticket_without_inferring_a_project(client,db):
    from app.models.helpdesk import HelpdeskTicket
    from tests.test_suite_operator import approve,tick
    h,user,other,oh,path,review,spec=chat(client,db,message_read=True,hr_ticket=True)
    control(client,h,review,'activate');send(client,path,oh)
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    def say(module,text):return command(client,h,module,text,workspace_id=review['workspace_id'],conversation_id=pending['conversation_id'],agent_id=spec['agent_id'])
    first=say('PMS','Raise an HRMS ticket based on this message')
    assert first['status']=='needs_clarification',first
    assert first['result']['request']['module']=='HRMS' and first['result']['request']['project_id'] is None
    assert first['result']['local_nlp']['slots']['_awaiting']=='title'
    citation=first['result']['citations'][0]['id'];assert ':PMS:' in citation
    draft=say('HRMS','Request project staffing clarification')
    assert draft['status']=='awaiting_approval' and draft['plan']['steps'][0]['tool']=='hrms.create_ticket',draft
    assert draft['result']['citations'][0]['id']==citation and db.query(HelpdeskTicket).count()==0
    approve(client,h,draft);tick(client,db);tick(client,db)
    result=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert result['status']=='succeeded',result
    ticket=db.query(HelpdeskTicket).one();assert ticket.employee_id==user.employee.id
    assert ticket.subject=='Request project staffing clarification'
