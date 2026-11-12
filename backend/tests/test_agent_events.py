import asyncio
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_saved_agents import profile
from app.ai_operator import agent_events as events,agent_schedules as schedules
from app.apps.project_management.models import PMSProject,PMSActivity
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator.suite_models import SuiteRun
from app.shared.models import ServicePolicy

ROOT='/api/v1/ai-operator/suite/agents/events'


def setup(client,db):
    h,user,p,t=setup_suite(client,db);project=db.get(PMSProject,p)
    from test_identity_utils import provision_workflow_workspace
    workspace=provision_workflow_workspace(db,user);project.workspace_id=workspace.id;db.commit()
    agent=profile(client,h,modules=['PMS'],tools=['pms.tasks'],workspace_id=project.workspace_id,project_id=p)
    spec={'request_key':str(uuid4()),'agent_id':agent['id'],'event':'pms.task_created','prompt':'Show project tasks','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'min_interval_minutes':1,'max_per_day':2}
    r=client.post(ROOT+'/preview',headers=h,json=spec);assert r.status_code==200,r.text
    return h,user,project,t,agent,r.json(),spec


def control(client,h,value,action):
    r=client.post(ROOT+f'/{value["id"]}/{action}',headers=h,json={'revision':value['revision'],'preview_hash':value['preview_hash']});assert r.status_code==200,r.text
    return r.json()


def event(db,user,project,task,instant):
    row=PMSActivity(project_id=project.id,task_id=task,actor_user_id=user.id,action='task.created',entity_type='task',entity_id=task,summary='UNTRUSTED event text, never forward this.',metadata_json='{"secret":"not-forwarded"}',created_at=instant)
    db.add(row);db.commit();return row


def test_subscription_review_deduplicates_and_prepares_canonical_private_conversation(client,db):
    h,user,p,t,agent,draft,spec=setup(client,db)
    assert client.post(ROOT+'/preview',headers=h,json=spec).json()['id']==draft['id']
    value=control(client,h,draft,'activate');instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    source=event(db,user,p,t,instant)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    assert job.status=='agent_active' and job.payload_json['event_source']['source_id']==source.id
    assert job.payload_json['spec']['prompt']==spec['prompt'] and 'UNTRUSTED' not in str(job.payload_json)
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(seconds=1)))['processed']==0
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    db.refresh(job);assert job.status=='agent_complete',job.last_error
    run=db.get(SuiteRun,job.payload_json['occurrences'][0]['run_id']);assert run.status=='answered',run.result
    assert run.result['event_context']['records']==[{'entity':'task','id':t}]
    assert db.query(SuiteRun).count()==1


def test_pause_resume_skip_missed_events_and_expiry_stop_intake(client,db):
    h,user,p,t,agent,draft,spec=setup(client,db);value=control(client,h,draft,'activate')
    value=control(client,h,value,'pause');instant=datetime.now(timezone.utc)
    event(db,user,p,t,instant)
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(seconds=1)))['processed']==0
    value=control(client,h,value,'resume')
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==0
    assert db.query(Job).count()==0
    assert asyncio.run(events.dispatch(db,client.app,datetime.fromisoformat(spec['expires_at'])))['processed']==0
    assert db.get(ServicePolicy,value['id']).values_json['state']=='expired'


def test_source_access_is_rechecked_before_model_planning(client,db,monkeypatch):
    h,user,p,t,agent,draft,spec=setup(client,db);value=control(client,h,draft,'activate')
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);event(db,user,p,t,instant)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    from fastapi import HTTPException
    async def no_access(*args,**kwargs):raise HTTPException(403,'Synthetic record permission removal')
    monkeypatch.setattr(events,'authorize_source',no_access)
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==0
    db.expire_all();assert db.query(Job).one().status=='agent_blocked'
    assert db.query(SuiteRun).count()==0


def test_inaccessible_event_is_recorded_once_without_leaking_event_text(client,db,monkeypatch):
    h,user,p,t,agent,draft,spec=setup(client,db);value=control(client,h,draft,'activate')
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);source=event(db,user,p,t,instant)
    from fastapi import HTTPException
    async def no_access(*args,**kwargs):raise HTTPException(404,'Hidden source')
    monkeypatch.setattr(events,'authorize_source',no_access)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(seconds=1)))['processed']==0
    response=client.get(ROOT,headers=h,params={'workspace_id':p.workspace_id});assert response.status_code==200,response.text
    assert response.json()['items'][0]['deliveries']==[] and 'UNTRUSTED' not in response.text
    assert client.get('/api/v1/ai-operator/suite/agents/schedules',headers=h).json()['items']==[]
    assert db.query(Job).count()==1 and db.query(SuiteRun).count()==0


def test_profile_changes_and_source_tampering_block_subscriptions(client,db):
    h,user,p,t,agent,draft,spec=setup(client,db);value=control(client,h,draft,'activate')
    from app.ai_operator.assistant_models import AssistantConversation
    row=db.get(AssistantConversation,agent['id']);row.references={**row.references,'revision':2};db.commit()
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);event(db,user,p,t,instant)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==0
    db.expire_all();assert db.get(ServicePolicy,value['id']).values_json['state']=='blocked'
    assert db.query(Job).count()==0


def test_a_real_native_task_creation_enters_the_event_queue(client,db):
    h,user,p,t,agent,draft,spec=setup(client,db);control(client,h,draft,'activate')
    created=client.post(f'/api/v1/project-management/projects/{p.id}/tasks',headers=h,json={'title':'Native event task','task_key':'EV-'+uuid4().hex[:8]});assert created.status_code==200,created.text
    source=db.query(PMSActivity).filter_by(task_id=created.json()['id'],action='task.created').one()
    assert asyncio.run(events.dispatch(db,client.app,datetime.now(timezone.utc)+timedelta(seconds=1)))['processed']==1
    assert db.query(Job).one().payload_json['event_source']['source_id']==source.id


def test_late_committed_lower_event_id_is_not_lost_after_a_higher_delivery(client,db):
    from sqlalchemy import func
    h,user,p,t,agent,draft,spec=setup(client,db);control(client,h,draft,'activate')
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);low=(db.query(func.max(PMSActivity.id)).scalar() or 0)+100
    high=PMSActivity(id=low+1,project_id=p.id,task_id=t,actor_user_id=user.id,action='task.created',entity_type='task',entity_id=t,summary='Higher ID committed first',created_at=instant);db.add(high);db.commit()
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    job=db.query(Job).one();job.status='agent_complete';job.run_at=None;db.commit()
    late=PMSActivity(id=low,project_id=p.id,task_id=t,actor_user_id=user.id,action='task.created',entity_type='task',entity_id=t,summary='Lower ID committed late',created_at=instant);db.add(late);db.commit()
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(minutes=2)))['processed']==1
    assert {j.payload_json['event_source']['source_id'] for j in db.query(Job)}=={low,low+1}


def test_throttle_and_daily_budget_do_not_create_more_occurrences(client,db):
    h,user,p,t,agent,draft,spec=setup(client,db);control(client,h,draft,'activate')
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);event(db,user,p,t,instant)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    job=db.query(Job).one();job.status='agent_complete';job.run_at=None;db.commit()
    event(db,user,p,t,instant+timedelta(seconds=20))
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(seconds=30)))['processed']==0
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(minutes=2)))['processed']==1
    for job in db.query(Job):job.status='agent_complete';job.run_at=None
    db.commit();event(db,user,p,t,instant+timedelta(minutes=3))
    assert asyncio.run(events.dispatch(db,client.app,instant+timedelta(minutes=4)))['processed']==0
    assert db.query(Job).count()==2


def test_crm_native_pipeline_event_has_a_current_record_access_check(client,db):
    from tests.test_pipeline_configuration import crm_draft
    from app.shared.models import ServiceEvent
    h,user,_,_=setup_suite(client,db);agent=profile(client,h,tools=['crm.deals'],modules=['CRM'])
    spec={'request_key':str(uuid4()),'agent_id':agent['id'],'event':'crm.deal_stage','prompt':'Show CRM deals','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    r=client.post(ROOT+'/preview',headers=h,json=spec);assert r.status_code==200,r.text;control(client,h,r.json(),'activate')
    pipeline,draft=crm_draft(client,h)
    r=client.post('/api/v1/crm/deals',headers=h,json={'name':'Event-linked opportunity','pipeline_id':pipeline,'stage_id':int(draft['stages'][0]['id']),'amount':1000,'currency':'INR'});assert r.status_code==201,r.text
    event_row=db.query(ServiceEvent).filter_by(event_type='pipeline.stage_entered',entity_type='deal',entity_id=r.json()['id']).one()
    assert asyncio.run(events.dispatch(db,client.app,datetime.now(timezone.utc)+timedelta(seconds=1)))['processed']==1
    job=db.query(Job).one();assert job.payload_json['event_source']['source_id']==event_row.id and job.payload_json['event_source']['eligible'] is True


def test_hrms_native_handover_uses_authorized_asset_references_only(client,db):
    from tests.test_asset_lifecycle import person,create,batch
    from app.shared.models import ServiceEvent
    h,user,_,_=setup_suite(client,db);agent=profile(client,h,modules=['HRMS'],tools=['hrms.directory'])
    spec={'request_key':str(uuid4()),'agent_id':agent['id'],'event':'hrms.asset_handover','prompt':'Show employee directory','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    r=client.post(ROOT+'/preview',headers=h,json=spec);assert r.status_code==200,r.text;control(client,h,r.json(),'activate')
    employee=person(db);asset=create(client,h);r=batch(client,h,employee,[asset['id']]);assert r.status_code==201,r.text
    source=db.query(ServiceEvent).filter_by(event_type='asset.handover',entity_id=asset['id']).one()
    count=asyncio.run(events.dispatch(db,client.app,datetime.now(timezone.utc)+timedelta(seconds=1)))['processed']
    record=db.query(ServicePolicy).filter_by(kind=events.KIND).one()
    assert count==1,{'state':record.values_json['state'],'error':record.values_json.get('error'),'source_kind':(source.module_key,source.entity_type,source.organization_id),'floor':record.values_json['floor'],'source_id':source.id}
    job=db.query(Job).one();assert job.payload_json['event_source']['source_id']==source.id and job.payload_json['event_source']['records']==[{'entity':'asset','id':asset['id']}]


def test_event_subscriptions_are_private_and_validate_intake_limits(client,db):
    from ai_test_utils import auth_headers
    h,user,p,t,agent,draft,spec=setup(client,db)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT,headers=other).json()['items']==[]
    assert client.post(ROOT+f'/{draft["id"]}/cancel',headers=other,json={'revision':draft['revision']}).status_code==404
    for change in ({'max_per_day':25},{'min_interval_minutes':0},{'event':'unregistered.webhook'}):
        assert client.post(ROOT+'/preview',headers=h,json={**spec,'request_key':str(uuid4()),**change}).status_code==422


def test_pause_during_source_read_fences_the_old_intake_lease(client,db,monkeypatch):
    h,user,p,t,agent,draft,spec=setup(client,db);value=control(client,h,draft,'activate')
    instant=datetime.now(timezone.utc)+timedelta(seconds=2);event(db,user,p,t,instant)
    original=events.authorize_source
    async def interrupted(*args,**kwargs):
        refs=await original(*args,**kwargs)
        control(client,h,value,'pause')
        return refs
    monkeypatch.setattr(events,'authorize_source',interrupted)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==0
    db.expire_all();assert db.get(ServicePolicy,value['id']).values_json['state']=='paused' and db.query(Job).count()==0
