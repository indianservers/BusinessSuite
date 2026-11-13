"""Cloud proposals traverse the real scoped planner, approval and native APIs.

Provider HTTP is simulated; business persistence, identity, permissions and
worker receipts use the isolated application database and canonical routers.
"""
from datetime import date
import json
from uuid import uuid4
import httpx
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider,setup_operator,plan_for
from tests.test_suite_operator import setup_suite,approve,tick
from app.ai_operator.structured_output import closed_schema,restore_omitted_defaults

ROOT='/api/v1/ai-operator/suite'


def test_strict_schema_closes_objects_preserves_required_and_optional_null_semantics():
    schema={'type':'object','required':['title'],'properties':{
        'title':{'type':'string'},'count':{'type':'integer','default':2},
        'owner':{'anyOf':[{'type':'integer'},{'type':'null'}],'default':None}}}
    closed=closed_schema(schema)
    assert closed['additionalProperties'] is False
    assert closed['required']==['title','count','owner']
    assert closed['properties']['count']['anyOf']==[{'type':'integer'},{'type':'null'}]
    assert restore_omitted_defaults({'title':'Review','count':None,'owner':None,'unknown':1},schema)=={
        'title':'Review','owner':None,'unknown':1}
    assert 'additionalProperties' not in schema


def test_open_dictionary_schema_explicitly_falls_back_instead_of_silently_losing_keys():
    assert closed_schema({'type':'object','additionalProperties':True}) is None
    assert closed_schema({'type':'object','properties':{'arguments':{'type':'object','additionalProperties':{'type':'string'}}}}) is None


@pytest.mark.parametrize('provider',['openai','claude','gemini'])
def test_provider_contract_is_strict_where_supported_and_always_domain_validated(client,db,monkeypatch,provider):
    from app.ai_operator import providers
    from app.ai_operator.provider_scope import resolve_provider
    from app.ai_operator.schemas import TaskPlan
    h,user,project,task=setup_operator(client,db,provider=provider)
    captured=[];output=plan_for(task)
    def response(url,headers,body,seconds):
        captured.append(body)
        if provider=='openai':value={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(output)}]}]}
        elif provider=='claude':value={'stop_reason':'tool_use','content':[{'type':'tool_use','name':'submit_plan','input':output}]}
        else:value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}]}
        return httpx.Response(200,json=value,request=httpx.Request('POST',url))
    monkeypatch.setattr(providers,'request_json',response)
    config=resolve_provider(db,user,provider,None)
    providers.generate_json(db,user,config,prompt='Review selected task',schema=TaskPlan.model_json_schema(),output_type=TaskPlan)
    if provider=='openai':assert captured[0]['text']['format']['strict'] is True
    elif provider=='claude':assert captured[0]['tools'][0]['strict'] is True
    else:assert 'responseJsonSchema' not in captured[0]['generationConfig']
    output['steps'][0]['changes']['unexpected_tenant_id']=77
    with pytest.raises(Exception) as invalid:
        providers.generate_json(db,user,config,prompt='Review selected task',schema=TaskPlan.model_json_schema(),output_type=TaskPlan)
    assert getattr(invalid.value,'status_code',None)==502


@pytest.mark.parametrize('module',['PMS','CRM','HRMS'])
@pytest.mark.parametrize('scenario',['success','unknown_argument','revoked'])
def test_scoped_cloud_workflow_approves_persists_and_retries_without_duplicate_writes(client,db,monkeypatch,module,scenario):
    from app.apps.project_management.models import PMSProject,PMSTask
    from app.apps.crm.models import CRMTask
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskTicket
    h,user,project,_=setup_suite(client,db)
    if module=='HRMS':
        db.add(Employee(employee_id='ARCH-HR',user_id=user.id,first_name='Architecture',last_name='QA',date_of_joining=date.today()));db.commit()
    title='Architecture complete '+module
    model=HelpdeskTicket if module=='HRMS' else PMSTask if module=='PMS' else CRMTask
    query=lambda:db.query(model).filter_by(**({'subject':title} if module=='HRMS' else {'title':title}))
    payload={'subject':title,'description':'Review access request'} if module=='HRMS' else {'title':title}
    if module=='PMS':payload.update(task_key='ARCH-PMS',assignee_user_ids=[user.id])
    if module=='CRM':payload['owner_user_id']=user.id
    if scenario=='unknown_argument':payload['unreviewed_tenant_id']=999
    tool=module.lower()+('.create_ticket' if module=='HRMS' else '.create_task')
    step={'tool':tool,'payload':payload,**({'record_id':project} if module=='PMS' else {})}
    calls=mock_provider(monkeypatch,{'summary':'Review exact native creation','steps':[step]})
    body={'request_key':str(uuid4()),'text':'Prepare the requested '+module+' record','provider':'gemini','module':module}
    if module=='PMS':body.update(project_id=project,workspace_id=db.get(PMSProject,project).workspace_id)
    result=client.post(ROOT+'/commands',headers=h,json=body)
    assert result.status_code==200,result.text
    run=result.json()
    if scenario=='unknown_argument':
        assert run['status']=='failed' and run['approval_id'] is None,run
        assert query().count()==0
        return
    assert run['status']=='awaiting_approval',run
    wire=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    assert wire['tools'] and all(t['module']==module for t in wire['tools'])
    assert tool in {t['name'] for t in wire['tools']}
    assert all('path' not in t and 'method' not in t for t in wire['tools'])
    assert query().count()==0
    if scenario=='revoked':
        from app.ai_agents.models import AiSecuritySetting
        settings=db.query(AiSecuritySetting).filter_by(company_id=1).first()
        if settings is None:settings=AiSecuritySetting(company_id=1);db.add(settings)
        setattr(settings,module.lower()+'_ai_enabled',False);db.commit()
        denied=client.post(f'{ROOT}/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
        assert denied.status_code in {403,409},denied.text
        tick(client,db)
        assert query().count()==0
        return
    again=client.post(ROOT+'/commands',headers=h,json=body)
    assert again.json()['id']==run['id'] and len(calls)==1
    approve(client,h,run);tick(client,db);db.expire_all()
    final=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==1,final
    record=query().one()
    assert final['receipts'][0]['record_id']==record.id
    if module=='CRM':assert record.owner_user_id==user.id
    if module=='PMS':assert record.assignee_user_ids==[user.id]
    if module=='HRMS':assert record.employee_id==user.employee.id
    approve(client,h,final);tick(client,db)
    assert query().count()==1


@pytest.mark.parametrize('kind',['write','read'])
def test_cloud_cannot_propose_a_hidden_cross_module_action(client,db,monkeypatch,kind):
    from app.apps.crm.models import CRMTask
    h,_,_,_=setup_suite(client,db)
    proposal={'summary':'Wrong module','steps':[{'tool':'crm.create_task','payload':{'title':'Hidden write'}}]}
    if kind=='read':proposal={'summary':'Wrong source','steps':[],'context_requests':[{'tool':'crm.people','payload':{'q':'secret'}}]}
    mock_provider(monkeypatch,proposal)
    result=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Review HR policies',
        'module':'HRMS','provider':'gemini'})
    assert result.status_code==200,result.text
    assert result.json()['status']=='failed',result.text
    assert result.json()['error_code']=='AI_POLICY_HTTP_422'
    assert not db.query(CRMTask).filter_by(title='Hidden write').count()


def test_discovery_filters_permissions_and_saved_agent_before_prompting(client,db):
    from tests.test_suite_module_scope import managed
    from app.ai_operator.planning_catalog import available
    h,_,headers,user=managed(client,db)
    # Install the real request's access context before discovery.
    assert client.get(ROOT+'/tools',headers=headers).status_code==200
    entries=available(db,user,None,module='CRM')
    assert entries==[]
    assert available(db,user,None,module='HRMS',agent_tools=[])==[]


def test_tool_schema_only_advertises_adapter_fields():
    from app.ai_operator.suite_tools import catalog
    for entry in catalog():
        schema=entry['payload_schema']
        assert schema['additionalProperties'] is False
        assert set(schema['properties'])==set(entry['fields'])
        assert set(schema.get('required',[]))<=set(entry['fields'])


@pytest.mark.parametrize('complete,people,expected',[
    (True,[{'id':1,'name':'Maya'},{'id':2,'name':'Maya'}],None),
    (False,[{'id':1,'name':'Maya'}],None),
    (True,[{'id':1,'name':'Other'}],None),
    (True,[{'id':1,'name':'Maya'}],1),
])
def test_people_resolution_never_guesses_from_ambiguous_or_partial_results(complete,people,expected):
    from app.ai_operator.identity_resolution import person_id
    assert person_id('Maya',people,complete=complete)==expected


def test_local_crm_assignment_uses_fresh_native_lookup_and_retains_owner_on_draft_edit(client,db):
    from app.apps.crm.models import CRMTask
    from tests.test_conversational_actions import new_chat,send
    h,user,_,_=setup_suite(client,db);chat=new_chat(client,h)
    run=send(client,h,chat,f'Create a CRM task called "Local owner resolution" and assign it to {user.email}',module='CRM')
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['payload']['owner_user_id']==user.id
    updated=send(client,h,chat,'make it high priority',parent_run_id=run['id'],module='CRM')
    assert updated['plan']['steps'][0]['payload']['owner_user_id']==user.id,updated
    approve(client,h,updated);tick(client,db)
    record=db.query(CRMTask).filter_by(title='Local owner resolution').one()
    assert record.owner_user_id==user.id and record.priority=='High'
