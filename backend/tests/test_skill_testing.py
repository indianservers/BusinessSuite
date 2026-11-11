from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,tick
from ai_test_utils import auth_headers
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite'


def setup(client,db,tools=None):
    h,user,_,_=setup_suite(client,db)
    r=client.post(ROOT+'/agents/catalog/skills',headers=h,json={'name':'Test procedure','instructions':'Prepare reviewed followups for authorized customers.','tools':tools or ['crm.create_task']});assert r.status_code==200,r.text
    conversation=client.post(ROOT+'/conversations',headers=h,json={'title':'Testing a skill'}).json()
    return h,user,r.json(),conversation


def body(skill,conversation,**extra):return {'request_key':str(uuid4()),'text':'Create CRM task called Synthetic skill test','provider':'local','conversation_id':conversation['id'],'test_skill_id':skill['id'],'test_skill_revision':skill['revision'],**extra}


def test_skill_test_prepares_native_review_but_cannot_approve_or_write(client,db):
    h,_,skill,c=setup(client,db);command=body(skill,c)
    response=client.post(ROOT+'/commands',headers=h,json=command);assert response.status_code==200,response.text
    run=response.json();assert run['status']=='awaiting_approval',run
    assert run['result']['request']['test_skill_id']==skill['id']
    assert client.post(ROOT+'/commands',headers=h,json=command).json()['id']==run['id']
    assert client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==409
    tick(client,db);assert db.query(CRMTask).count()==0
    assert db.query(AssistantConversation).filter(AssistantConversation.references['saved_agent'].as_boolean()==True).count()==0


def test_followups_inherit_test_binding_without_allowing_mode_escape(client,db):
    h,_,skill,c=setup(client,db)
    first=client.post(ROOT+'/commands',headers=h,json=body(skill,c)).json();assert first['status']=='awaiting_approval',first
    next_body={'request_key':str(uuid4()),'text':'Make it high priority','provider':'local','conversation_id':c['id']}
    response=client.post(ROOT+'/commands',headers=h,json=next_body);assert response.status_code==200,response.text
    revised=response.json();assert revised['result']['request']['test_skill_id']==skill['id'] and revised['status']=='awaiting_approval'
    assert client.post(ROOT+f'/runs/{revised["id"]}/approve',headers=h,json={'plan_hash':revised['plan_hash']}).status_code==409
    other=client.post(ROOT+'/agents/catalog/skills',headers=h,json={'name':'Other procedure','instructions':'Review tasks.','tools':['crm.create_task']}).json()
    response=client.post(ROOT+'/commands',headers=h,json=body(other,c,text='Create CRM task called Escape'))
    assert response.status_code==409,response.text
    assert db.query(CRMTask).count()==0


@pytest.mark.parametrize('change',['revision','archive'])
def test_skill_changes_stop_existing_test_followups(client,db,change):
    h,_,skill,c=setup(client,db)
    first=client.post(ROOT+'/commands',headers=h,json=body(skill,c)).json();assert first['status']=='awaiting_approval'
    if change=='revision':
        r=client.put(ROOT+f'/agents/catalog/skills/{skill["id"]}',headers=h,json={'name':skill['name'],'instructions':'A changed procedure.','tools':skill['tools'],'revision':1});assert r.status_code==200,r.text
    else:assert client.delete(ROOT+f'/agents/catalog/skills/{skill["id"]}',headers=h).status_code==200
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Make it high priority','provider':'local','conversation_id':c['id']})
    assert response.status_code==(409 if change=='revision' else 404),response.text
    assert db.query(CRMTask).count()==0


def test_skill_testing_enforces_private_ownership_and_tool_scope(client,db):
    h,_,skill,c=setup(client,db,tools=['crm.tasks'])
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    response=client.post(ROOT+'/commands',headers=other,json=body(skill,{'id':None},conversation_id=None))
    assert response.status_code==404,response.text
    response=client.post(ROOT+'/commands',headers=h,json=body(skill,c))
    assert response.status_code in (200,403,422),response.text
    if response.status_code==200:assert response.json()['status']!='awaiting_approval',response.json()
    assert db.query(CRMTask).count()==0


def test_execution_guard_rejects_test_writes_even_if_a_run_is_queued(client,db):
    from app.ai_operator.skill_testing import enforce
    from app.ai_operator.suite import Plan
    from fastapi import HTTPException
    h,user,skill,c=setup(client,db)
    response=client.post(ROOT+'/commands',headers=h,json=body(skill,c)).json()
    run=db.get(SuiteRun,response['id']);run.status='queued'
    with pytest.raises(HTTPException) as error:enforce(db,user,run,Plan.model_validate(run.plan).steps)
    assert error.value.status_code==403 and db.query(CRMTask).count()==0


def test_regular_commands_keep_their_previous_serialized_shape():
    from app.ai_operator.suite import Command
    value=Command(request_key='legacy-request',text='Show CRM tasks',provider='local').model_dump(mode='json')
    assert 'test_skill_id' not in value and 'test_skill_revision' not in value


def test_pms_skill_preview_does_not_mint_an_independent_executable_child(client,db,monkeypatch):
    from app.ai_operator import pms_agent
    from app.ai_operator.models import OperatorRun,OperatorProposal
    from app.apps.project_management.models import PMSProject
    h,_,project_id,task_id=setup_suite(client,db);project=db.get(PMSProject,project_id)
    r=client.post(ROOT+'/agents/catalog/skills',headers=h,json={'name':'Project task procedure','instructions':'Prepare a task draft.','tools':['pms.task_plan'],'workspace_id':project.workspace_id});assert r.status_code==200,r.text
    skill=r.json();c=client.post(ROOT+'/conversations',headers=h,json={'title':'Project skill test','workspace_id':project.workspace_id}).json()
    async def unexpected_child(*args,**kwargs):raise AssertionError('A test must not create an independently executable PMS child')
    monkeypatch.setattr(pms_agent,'prepare_step',unexpected_child)
    initial=db.query(OperatorRun).count()+db.query(OperatorProposal).count()
    response=client.post(ROOT+'/commands',headers=h,json=body(skill,c,text='Prepare a PMS priority change',workspace_id=project.workspace_id,project_id=project.id,local_plan={'summary':'Review test task','steps':[{'tool':'pms.task_plan','record_id':project.id,'payload':{'plan':{'summary':'Test a priority change','clarification':None,'steps':[{'tool':'update_task','task_id':task_id,'changes':{'priority':'High'}}]}}}]}))
    assert response.status_code==200,response.text
    result=response.json();assert result['status']=='awaiting_approval',result
    assert not result['pms_previews'] and db.query(OperatorRun).count()+db.query(OperatorProposal).count()==initial
    assert client.post(ROOT+f'/runs/{result["id"]}/resume',headers=h,json={'plan_hash':result['plan_hash']}).status_code==409
