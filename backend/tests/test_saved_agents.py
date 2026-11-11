from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from ai_test_utils import auth_headers
ROOT='/api/v1/ai-operator/suite'


def profile(client,h,**extra):
    response=client.post(ROOT+'/agents',headers=h,json={'name':'Delivery coordinator','instructions':'Prepare the requested delivery actions and ask for missing scope.','modules':['CRM'],'tools':['crm.create_task'],'provider':'local',**extra})
    assert response.status_code==200,response.text
    return response.json()


def command(client,h,agent,text='Create CRM task called Customer followup',**extra):
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'preferred','module':'CRM','agent_id':agent['id'],'text':text,**extra})
    assert response.status_code==200,response.text
    return response.json()


def test_agents_are_private_and_run_through_existing_reviews(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h)
    run=command(client,h,agent)
    assert run['status']=='awaiting_approval',run
    assert run['result']['agent']['id']==agent['id']
    assert run['result']['request']['provider']=='local'
    approve(client,h,run);tick(client,db)
    activity=client.get(ROOT+f'/agents/{agent["id"]}/activity',headers=h)
    assert activity.status_code==200 and activity.json()['items'][0]['status']=='succeeded',activity.text
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.get(ROOT+f'/agents/{agent["id"]}/activity',headers=other).status_code==404


def test_agent_tool_restrictions_apply_to_model_and_manual_plans(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h)
    run=command(client,h,agent,local_plan={'summary':'Not allowed','steps':[{'tool':'crm.add_note','payload':{'lead_id':123,'body':'Not authorized by profile'}}]})
    assert run['status']=='failed' and run['approval_id'] is None


def test_agent_edit_invalidates_pending_review(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h);run=command(client,h,agent)
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','environment')}
    body['revision']=1;body['instructions']='Ask for delivery owner before drafting.'
    assert client.put(ROOT+f'/agents/{agent["id"]}',headers=h,json=body).status_code==200
    response=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==409,response.text


def test_skills_are_versioned_private_and_cannot_broaden_agent_tools(client,db):
    h,_,_,_=setup_suite(client,db)
    body={'name':'Customer followup','instructions':'Use concise customer follow-up titles.','tools':['crm.create_task']}
    made=client.post(ROOT+'/agents/catalog/skills',headers=h,json=body)
    assert made.status_code==200,made.text
    skill=made.json();agent=profile(client,h,skill_ids=[skill['id']])
    run=command(client,h,agent)
    assert run['status']=='awaiting_approval',run
    edited=client.put(ROOT+f'/agents/catalog/skills/{skill["id"]}',headers=h,json={**body,'instructions':'Use clear customer handoff titles.','revision':1})
    assert edited.status_code==200,edited.text
    assert client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==409
    bad=client.post(ROOT+'/agents',headers=h,json={'name':'Unsafe','instructions':'Do work','modules':['CRM'],'tools':['crm.tasks'],'skill_ids':[skill['id']]})
    assert bad.status_code==403,bad.text


def test_connector_bridge_rejects_unbound_connections_and_unreviewed_writes(client,db):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h)
    response=client.get(ROOT+'/agents/connectors/read',headers=h,params={'agent_id':agent['id'],'connection_id':999999,'action_id':'read_rows'})
    assert response.status_code in (403,404),response.text
    response=client.post(ROOT+'/agents/connectors/execute-approved',headers=h,json={'connection_id':999999,'action_id':'send_message','input':{},'suite_run_id':1,'suite_step':1})
    assert response.status_code==403,response.text


def test_connector_read_cannot_mutate_and_generic_code_is_not_agent_executable(monkeypatch):
    from types import SimpleNamespace
    from app.ai_operator.agent_connectors import invoke,permitted
    from app.apps.power_apps.integrations import service
    fake=SimpleNamespace(connector_id='google_sheets',id=1)
    calls=[]
    monkeypatch.setattr(service,'typed_action',lambda *a:({},None,True))
    monkeypatch.setattr(service,'invoke',lambda *a,**kw:calls.append(kw))
    with pytest.raises(HTTPException) as caught:invoke(None,None,fake,'append_rows',{},False,'test')
    assert caught.value.status_code==403 and calls==[]
    with pytest.raises(HTTPException):permitted(SimpleNamespace(connector_id='http'),'request')
    with pytest.raises(HTTPException):permitted(fake,'delete_rows')


def test_invalid_skill_is_validation_error_not_server_error(client,db):
    h,_,_,_=setup_suite(client,db)
    response=client.post(ROOT+'/agents/catalog/skills',headers=h,json={'name':'Unsupported','instructions':'Do work','tools':['shell.execute']})
    assert response.status_code==422,response.text


def test_pending_agent_cannot_change_during_followup(client,db):
    h,_,_,_=setup_suite(client,db);first=profile(client,h);second=profile(client,h)
    run=command(client,h,first)
    request=run['result']['request']
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','agent_id':second['id'],'conversation_id':request['conversation_id'],'parent_run_id':run['id'],'text':'Change priority to high'})
    assert response.status_code==409,response.text
