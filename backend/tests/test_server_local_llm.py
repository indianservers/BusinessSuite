import json
import subprocess
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.ai_operator import server_local_llm as runtime


def test_offline_worker_has_bounded_input_timeout_and_no_inherited_credentials(monkeypatch):
    monkeypatch.setattr(runtime,'verify',lambda:None)
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-do-not-pass')
    monkeypatch.setenv('DATABASE_URL','synthetic-do-not-pass')
    observed=[]
    value={'kind':'ask','message':'What date?','question':'What date?'}
    def run(command,**kwargs):
        observed.append((command,kwargs))
        return SimpleNamespace(returncode=0,stdout=json.dumps({'content':json.dumps(value),'stopped':True}).encode())
    monkeypatch.setattr(runtime.subprocess,'run',run)
    assert runtime.generate([{'role':'system','content':'Rules'},{'role':'user','content':'Synthetic request'}],999)==value
    command,options=observed[0]
    assert options['timeout']==45 and 'shell' not in options
    assert command[1]=='-I'
    assert 'Synthetic request' not in ' '.join(command)
    assert 'GEMINI_API_KEY' not in options['env'] and 'DATABASE_URL' not in options['env']
    assert options['env']['HF_HUB_OFFLINE']=='1' and options['env']['TRANSFORMERS_OFFLINE']=='1'


def test_model_integrity_failure_never_starts_inference(monkeypatch):
    def invalid():raise ValueError('Private model corruption details')
    monkeypatch.setattr(runtime,'verify',invalid)
    response=None
    with pytest.raises(HTTPException) as exc:runtime.generate([])
    assert exc.value.status_code==503 and exc.value.detail=='LOCAL_MODEL_UNAVAILABLE'


def test_local_capacity_is_bounded_and_never_queues_unbounded_work():
    runtime._busy.acquire()
    try:
        with pytest.raises(HTTPException) as exc:runtime.generate([])
        assert exc.value.status_code==409
    finally:runtime._busy.release()


def test_timeout_is_safe_and_releases_capacity(monkeypatch):
    monkeypatch.setattr(runtime,'verify',lambda:None)
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('private-command',45)
    monkeypatch.setattr(runtime.subprocess,'run',timeout)
    with pytest.raises(HTTPException) as exc:runtime.generate([])
    assert exc.value.detail=='LOCAL_MODEL_TIMEOUT'
    assert runtime._busy.acquire(blocking=False)
    runtime._busy.release()


@pytest.mark.parametrize('output',[{'stopped':False,'content':'incomplete'},{'error':'context_limit'}])
def test_incomplete_generation_or_context_overflow_does_not_become_a_plan(monkeypatch,output):
    monkeypatch.setattr(runtime,'verify',lambda:None)
    monkeypatch.setattr(runtime.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(output).encode()))
    with pytest.raises(HTTPException) as exc:runtime.generate([])
    assert exc.value.status_code==422


def test_server_generation_preserves_private_history_and_requires_separate_review(client,db,monkeypatch):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator_brain import session,ROOT
    from tests.test_ai_operator import mock_provider,plan_for
    from app.apps.project_management.models import PMSTask
    h,_,project,task=setup_suite(client,db)
    row=session(client,h,project);endpoint=f'{ROOT}/{row["id"]}'
    calls=mock_provider(monkeypatch,{})
    packets=[]
    def generate(messages,seconds,**kwargs):
        packets.append(json.loads(messages[1]['content']))
        return {'kind':'task_plan','message':'Review this draft.','task_ids':[task],'task_plan':plan_for(task)}
    monkeypatch.setattr(runtime,'generate',generate)
    response=client.post(endpoint+'/local',headers=h,json={'text':'Raise priority and add QA','task_ids':[task]})
    assert response.status_code==200,response.text
    reply=response.json();assert reply['kind']=='task_plan'
    from app.ai_agents.models import AiAuditLog
    audit=db.query(AiAuditLog).filter_by(action='operator.brain.local').one()
    assert audit.input_json['conversation_id']==row['id']
    assert 'prompt=' in audit.input_json['policy'] and runtime.REVISION in audit.input_json['policy']
    assert audit.output_json['status']=='draft:task_plan' and audit.output_json['count']==0
    assert packets[0]['authorized_context']['selected_task_ids']==[task]
    assert db.get(PMSTask,task).priority!='High' and not calls
    response=client.post(endpoint+'/turns',headers=h,json={'request_key':'d07ff509-daa4-48bc-8f8d-f760fa1c42ff','revision':0,'text':'Raise priority and add QA','reply':reply,'runtime':'server','model':runtime.MODEL})
    assert response.status_code==200,response.text
    assert response.json()['turns'][0]['runtime']=='server'
    client.post(endpoint+'/local',headers=h,json={'text':'What next?','task_ids':[task]})
    assert packets[1]['conversation'][0]['execution']=='draft_only'
    assert db.get(PMSTask,task).priority!='High'


@pytest.mark.parametrize('output',[{'kind':'task_plan','message':'Unsafe','task_ids':[999999],'task_plan':{'summary':'Unsafe','steps':[{'tool':'update_task','task_id':999999,'changes':{'priority':'High'}}]}},{'kind':'answer','message':'Done','execute':True},{'kind':'help','message':'Review?','question':'Proceed?','task_ids':[999999]}])
def test_local_output_still_requires_native_schema_and_record_validation(client,db,monkeypatch,output):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator_brain import session,ROOT
    h,_,project,task=setup_suite(client,db);row=session(client,h,project)
    monkeypatch.setattr(runtime,'generate',lambda *a,**k:output)
    response=client.post(f'{ROOT}/{row["id"]}/local',headers=h,json={'text':'Review selected work','task_ids':[task]})
    assert response.status_code==422,response.text


@pytest.mark.parametrize('kind',['Ask','help','clarification','question','ask_question'])
def test_model_clarification_envelope_is_adapted_without_inventing_action_fields(client,db,monkeypatch,kind):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator_brain import session,ROOT
    h,_,project,_=setup_suite(client,db);row=session(client,h,project)
    value={'kind':kind,'message':'What is the target date?'}
    if kind!='Ask':value['question']='What is the target date?'
    monkeypatch.setattr(runtime,'generate',lambda *a,**k:value)
    response=client.post(f'{ROOT}/{row["id"]}/local',headers=h,json={'text':'Help plan this project'})
    assert response.status_code==200,response.text
    assert response.json()['question']=='What is the target date?' and not response.json().get('task_plan')


def test_private_session_and_generation_failure_never_fall_back_to_cloud(client,db,monkeypatch):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator_brain import session,ROOT
    from tests.test_ai_operator import mock_provider
    from ai_test_utils import auth_headers
    h,_,project,_=setup_suite(client,db);row=session(client,h,project)
    cloud=mock_provider(monkeypatch,{})
    def unavailable(*args,**kwargs):raise HTTPException(503,'LOCAL_MODEL_UNAVAILABLE')
    monkeypatch.setattr(runtime,'generate',unavailable)
    endpoint=f'{ROOT}/{row["id"]}/local'
    response=client.post(endpoint,headers=h,json={'text':'Review work'})
    assert response.status_code==503,response.text
    from app.ai_agents.models import AiAuditLog
    failed=db.query(AiAuditLog).filter_by(action='operator.brain.local',status='failed').one()
    assert failed.output_json['error_code']=='LOCAL_MODEL_UNAVAILABLE'
    other,_=auth_headers(client,db,email='private-local@example.com',permissions=['ai_assistant','pms_manage_tasks','pms_manage_projects'])
    response=client.post(endpoint,headers=other,json={'text':'Review work'})
    assert response.status_code in {403,404},response.text
    assert not cloud


def test_revision_context_is_loaded_from_the_owned_run_not_the_browser(client,db,monkeypatch):
    from uuid import uuid4
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator_brain import session,ROOT
    from tests.test_ai_operator import plan_for
    h,_,project,task=setup_suite(client,db);row=session(client,h,project)
    prepared=client.post('/api/v1/ai-operator/workbench/plans/preview',headers=h,json={
        'project_id':project,'plan':plan_for(task),'request_key':str(uuid4()),'mode':'atomic'})
    assert prepared.status_code==200,prepared.text
    run=prepared.json();observed=[]
    def generate(messages,seconds,**kwargs):
        observed.append(json.loads(messages[1]['content']))
        return {'kind':'task_plan','message':'Review this revision.','task_ids':[task],'task_plan':plan_for(task)}
    monkeypatch.setattr(runtime,'generate',generate)
    response=client.post(f'{ROOT}/{row["id"]}/local',headers=h,json={'text':'Revise only pending work','task_ids':[task],'revision_id':run['id']})
    assert response.status_code==200,response.text
    assert observed[0]['authorized_context']['revision_of']['id']==run['id']
    assert observed[0]['authorized_context']['revision_of']['selection']==[task]
    response=client.post(f'{ROOT}/{row["id"]}/local',headers=h,json={'text':'Override context','context':{'task_ids':[999999]}})
    assert response.status_code==422,response.text
    assert len(observed)==1


@pytest.mark.parametrize('body',[{'text':'x','timezone':'invalid-zone'},{'text':'x','task_ids':[1]*26},{'text':'x'*4001},{'text':'x','provider':'gemini'}])
def test_server_generation_input_cannot_expand_its_scope_or_choose_a_cloud_provider(body):
    from app.ai_operator.brain_api import ServerLocalInput
    with pytest.raises(ValueError):ServerLocalInput.model_validate(body)
