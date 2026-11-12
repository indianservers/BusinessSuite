from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_suite_operator import setup_suite
from tests.test_agent_builder import send,profiles,ROOT
from app.ai_operator.agent_builder import local_draft
from app.shared.models import ServicePolicy
from app.ai_operator.suite_models import SuiteRun
from app.apps.automation.models import AutomationScheduledJob as Job


@pytest.mark.parametrize('condition,event',[
 ('when a task is created','pms.task_created'),('when a task is updated','pms.task_updated'),
 ('when assignments change','pms.assignment_changed'),('when a deal enters a pipeline stage','crm.deal_stage'),
 ('when assets are handed over','hrms.asset_handover'),
])
def test_local_authoring_recognizes_only_supported_native_sources(condition,event):
    draft=local_draft('Create a project coordinator that reviews the source '+condition,None,'PMS')
    assert draft.trigger and draft.trigger.event==event and draft.schedule is None
    assert draft.run_prompt=='reviews the source'


def test_local_followups_retain_objective_and_refine_limits_without_creating_a_calendar():
    first=local_draft('Create a project coordinator that reviews tasks when assignments change',None,'PMS')
    second=local_draft('At most three preparations per day, cooldown 10 minutes, skip events older than 30 minutes, for 20 days',first.model_dump(),'PMS')
    assert second.trigger.max_per_day==3 and second.trigger.min_interval_minutes==10
    assert second.trigger.max_event_age_minutes==30 and second.trigger.expires_days==20
    assert second.run_prompt=='reviews tasks' and second.tools==first.tools and not second.question
    invalid=local_draft('At most 50 preparations per day',second.model_dump(),'PMS');assert invalid.question
    unsupported=local_draft('Trigger on an incoming email',second.model_dump(),'PMS');assert unsupported.question
    calendar=local_draft('Every morning at 9 am',second.model_dump(),'PMS');assert calendar.trigger is None and calendar.schedule
    manual=local_draft('Manual only',second.model_dump(),'PMS');assert manual.trigger is None and manual.schedule is None


def test_specific_field_conditions_are_clarified_and_assignee_changes_use_the_exact_source():
    value=local_draft('Create a project coordinator that reviews tasks when task priority changes',None,'PMS')
    assert value.question and 'any task update' in value.question
    assigned=local_draft('Create a project coordinator that reviews tasks when the task assignee changes',None,'PMS')
    assert assigned.trigger.event=='pms.assignment_changed' and not assigned.question


def test_builder_saves_agent_and_inactive_event_preview_atomically_and_idempotently(client,db):
    h,user,_,_=setup_suite(client,db)
    first,_=send(client,h,'Create a CRM sales assistant that reviews opportunities when a deal enters a pipeline stage')
    assert first['event_trigger']['event']=='crm.deal_stage' and not first['question']
    final,_=send(client,h,'At most 2 preparations per day, cooldown 5 minutes',first)
    assert final['event_trigger']['max_per_day']==2 and profiles(db)==0
    assert client.post(ROOT+f'/{first["context_id"]}/apply',headers=h,json={'preview_hash':first['preview_hash']}).status_code==409
    response=client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']});assert response.status_code==200,response.text
    result=response.json();assert result['event_preview']['state']=='preview' and result['event_preview']['spec']['max_per_day']==2
    again=client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']});assert again.status_code==200,again.text
    assert again.json()['event_subscription_id']==result['event_subscription_id'] and profiles(db)==1
    assert db.query(ServicePolicy).filter_by(kind='ai_agent_event_subscription').count()==1 and db.query(Job).count()==0 and db.query(SuiteRun).count()==0
    assert client.get('/api/v1/ai-operator/suite/agents/events/'+str(result['event_subscription_id']),headers=h).json()['state']=='preview'


def test_event_preview_failure_rolls_back_the_compound_agent_save(client,db,monkeypatch):
    from app.ai_operator import agent_events
    from fastapi import HTTPException
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Create a CRM sales assistant that reviews opportunities when a deal changes stage')
    original=agent_events.stage_preview
    def fail_after_staging(*args,**kwargs):
        original(*args,**kwargs)
        raise HTTPException(409,'Synthetic failure after staging event intake')
    monkeypatch.setattr(agent_events,'stage_preview',fail_after_staging)
    r=client.post(ROOT+f'/{draft["context_id"]}/apply',headers=h,json={'preview_hash':draft['preview_hash']})
    assert r.status_code==409 and profiles(db)==0
    assert db.query(ServicePolicy).filter_by(kind='ai_agent_event_subscription').count()==0
    assert client.get(ROOT+f'/{draft["context_id"]}',headers=h).json()['agent_id'] is None


def test_cloud_authoring_proposes_a_typed_event_without_activating_it(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    mock_provider(monkeypatch,{'name':'Deal reviewer','instructions':'Review authorized opportunities.','tools':['crm.deals'],'memory':[],
        'run_prompt':'Show CRM deals','schedule':None,'trigger':{'event':'crm.deal_stage','max_per_day':2,'expires_days':10},'question':None})
    draft,_=send(client,h,'Create a deal reviewer when the deal changes stage',provider='gemini')
    assert draft['event_trigger']['max_per_day']==2 and not draft['question']
    r=client.post(ROOT+f'/{draft["context_id"]}/apply',headers=h,json={'preview_hash':draft['preview_hash']});assert r.status_code==200,r.text
    assert r.json()['event_preview']['state']=='preview' and db.query(Job).count()==0


def test_missing_workspace_and_skill_event_requests_require_clarification(client,db):
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Create a project coordinator that reviews tasks when assignments change',module='PMS')
    assert 'workspace' in draft['question'].casefold()
    assert client.post(ROOT+f'/{draft["context_id"]}/apply',headers=h,json={'preview_hash':draft['preview_hash']}).status_code==409
    skill,_=send(client,h,'Create a CRM sales skill that reviews deals when a deal changes stage',asset_type='skill')
    assert skill['question'] and skill['event_trigger'] is None


def test_missing_work_followup_retains_event_instead_of_replacing_the_design(client,db):
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Create a CRM sales assistant when a deal changes stage')
    assert draft['question'] and draft['event_trigger']['event']=='crm.deal_stage'
    filled,_=send(client,h,'Show CRM deals',draft)
    assert not filled['question'] and filled['event_trigger']['event']=='crm.deal_stage'
    assert filled['event_trigger']['prompt']=='Show CRM deals'
    changed,_=send(client,h,'Work: Review opportunities and prepare next steps',filled)
    assert changed['event_trigger']['prompt']=='Review opportunities and prepare next steps'


def test_cloud_must_clarify_calendar_and_event_combination_before_saving(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    mock_provider(monkeypatch,{'name':'Deal reviewer','instructions':'Review authorized opportunities.','tools':['crm.deals'],'memory':[],
        'run_prompt':'Show CRM deals','schedule':{'frequency':'daily'},'trigger':{'event':'crm.deal_stage'},'question':None})
    value,_=send(client,h,'Review deals each morning and when their stage changes',provider='gemini')
    assert value['question'] and 'one' in value['question']
    assert client.post(ROOT+f'/{value["context_id"]}/apply',headers=h,json={'preview_hash':value['preview_hash']}).status_code==409
    assert profiles(db)==0 and db.query(ServicePolicy).filter_by(kind='ai_agent_event_subscription').count()==0
    from app.ai_operator.assistant_models import AssistantConversation
    stored=db.get(AssistantConversation,value['context_id']);stored.references={**stored.references,'question':None};db.commit()
    assert client.post(ROOT+f'/{value["context_id"]}/apply',headers=h,json={'preview_hash':value['preview_hash']}).status_code==409


def test_cloud_cannot_silently_turn_a_specific_field_condition_into_any_update(client,db,monkeypatch):
    from test_identity_utils import provision_workflow_workspace
    h,user,_,_=setup_suite(client,db);workspace=provision_workflow_workspace(db,user);db.commit()
    configured=client.put('/api/v1/ai-operator/providers/gemini',headers=h,params={'workspace_id':workspace.id},json={'model':'test-model','api_key':'unit-test-secret-key','enabled':True,'data_sharing_allowed':True})
    assert configured.status_code==200,configured.text
    mock_provider(monkeypatch,{'name':'Task reviewer','instructions':'Review task priority.','tools':['pms.tasks'],'memory':[],
        'run_prompt':'Review priority','schedule':None,'trigger':{'event':'pms.task_updated'},'question':None})
    value,_=send(client,h,'Create a project reviewer that checks tasks when task priority changes',provider='gemini',module='PMS',workspace_id=workspace.id)
    assert value['question'] and 'any task update' in value['question']
    assert client.post(ROOT+f'/{value["context_id"]}/apply',headers=h,json={'preview_hash':value['preview_hash']}).status_code==409
    assert profiles(db)==0
