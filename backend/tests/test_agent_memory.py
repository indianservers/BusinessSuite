from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from datetime import datetime,timezone,timedelta
import pytest
from tests.test_suite_operator import setup_suite,ROOT,tick,approve
from tests.test_ai_operator import mock_provider,isolate_generic_http_audit
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.agent_memory import collect
from app.apps.project_management.models import PMSProject
from ai_test_utils import auth_headers
M=ROOT+'/memory'


def save(client,h,**kwargs):
    response=client.post(M,headers=h,json={'text':'Prefer concise summaries','level':'user',**kwargs})
    assert response.status_code==200,response.text
    return response.json()


def test_memory_crud_private_module_isolation_and_forget(client,db):
    h,u,_,_=setup_suite(client,db)
    user=save(client,h)
    crm=save(client,h,level='module',module='CRM',text='Use a friendly CRM tone')
    crm_items=client.get(M+'?module=CRM',headers=h).json()['items']
    assert {r['key'] for r in crm_items}=={user['key'],crm['key']}
    hr_items=client.get(M+'?module=HRMS',headers=h).json()['items']
    assert [r['key'] for r in hr_items]==[user['key']]
    h2,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    other=client.get(M+'?module=CRM',headers=h2)
    assert other.status_code==200,other.text
    assert other.json()['items']==[]
    assert client.delete(M+f'/module/{crm["id"]}',headers=h2).status_code==404
    edit={'level':'module','module':'CRM','text':'Use brief CRM notes','revision':1}
    updated=client.put(M+f'/module/{crm["id"]}',headers=h,json=edit)
    assert updated.status_code==200,updated.text
    assert updated.json()['revision']==2
    assert client.put(M+f'/module/{crm["id"]}',headers=h,json=edit).status_code==409
    assert client.delete(M+f'/module/{crm["id"]}',headers=h).status_code==200
    assert not any(r['key']==crm['key'] for r in client.get(M+'?module=CRM',headers=h).json()['items'])
    assert db.get(AssistantConversation,crm['id']).references['text']==''


def test_project_memory_reuses_workbench_and_precedence(client,db):
    h,u,p,_=setup_suite(client,db)
    workspace=db.get(PMSProject,p).workspace_id
    save(client,h,text='General preference')
    save(client,h,level='module',module='PMS',workspace_id=workspace,text='Module preference')
    project=save(client,h,level='project',module='PMS',project_id=p,workspace_id=workspace,text='Project decision')
    packet=collect(db,u,workspace,'PMS',p)
    assert [r['level'] for r in packet]==['project','module','user']
    assert packet[0]['key']==project['key']
    legacy=client.get('/api/v1/ai-operator/workbench/items',headers=h,params={'project_id':p}).json()['items']
    assert any(r['kind']=='memory' and r['payload']['text']=='Project decision' for r in legacy)
    assert client.get(M,headers=h,params={'module':'PMS','project_id':p,'workspace_id':999999}).status_code in (403,404)
    from app.ai_operator.workbench import memory_context
    assert len(memory_context(db,u,p))==3


@pytest.mark.parametrize('text',['api_key: very-secret','password=hidden','Bearer secret-token','salary: 90000','   '])
def test_memory_rejects_sensitive_or_blank_content(client,db,text):
    h,_,_,_=setup_suite(client,db)
    r=client.post(M,headers=h,json={'level':'user','text':text})
    assert r.status_code==422,r.text


def test_expiration_and_cloud_injection(client,db,monkeypatch):
    h,u,_,_=setup_suite(client,db)
    record=save(client,h,text='Private user preference')
    exp=save(client,h,level='module',module='CRM',text='Temporary decision',expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    row=db.get(AssistantConversation,exp['id']);row.references={**row.references,'expires_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()};db.commit()
    assert len(client.get(M+'?module=CRM',headers=h).json()['items'])==1
    calls=mock_provider(monkeypatch,{'summary':'Need details','question':'Which task?','steps':[]})
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':'Prepare a followup'})
    assert r.status_code==200,r.text
    import json
    body=json.loads(calls[0].content)
    outbound=json.loads(body['contents'][0]['parts'][0]['text'])
    assert outbound['agent_memory'][0]['text']=='Private user preference'
    assert 'Temporary decision' not in str(outbound['agent_memory'])
    assert r.json()['result']['memory_used'][0]['key']==record['key']


@pytest.mark.parametrize('module',['CRM','PMS'])
def test_local_remember_requires_review_then_recall(client,db,module):
    h,_,_,_=setup_suite(client,db)
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':module,'text':'Remember that use concise customer followups'})
    assert r.status_code==200,r.text
    run=r.json();assert run['status']=='awaiting_approval', str({'error_code':run['error_code'],'result':run['result'],'plan':run['plan']})
    assert client.get(M+f'?module={module}',headers=h).json()['items']==[]
    approve(client,h,run);tick(client,db)
    assert client.get(M+f'?module={module}',headers=h).json()['items'][0]['text']=='use concise customer followups'
    recall=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':module,'text':'What do you remember?'})
    assert recall.status_code==200,recall.text
    assert recall.json()['status']=='answered',recall.text
    assert 'use concise customer followups' in recall.json()['plan']['summary']


def test_module_workspace_isolation_and_user_memory_inheritance(client,db):
    h,u,_,_=setup_suite(client,db)
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    spaces=[]
    for name in ('Memory workspace A','Memory workspace B'):
        ws=PMSWorkspace(name=name,organization_id=1);db.add(ws);db.flush()
        db.add(PMSWorkspaceMember(workspace_id=ws.id,user_id=u.id,role='Owner'));spaces.append(ws.id)
    db.commit()
    global_memory=save(client,h,text='Private global preference')
    scoped=save(client,h,level='module',module='CRM',workspace_id=spaces[0],text='Workspace A only')
    a=client.get(M,headers=h,params={'module':'CRM','workspace_id':spaces[0]})
    b=client.get(M,headers=h,params={'module':'CRM','workspace_id':spaces[1]})
    assert a.status_code==b.status_code==200,(a.text,b.text)
    assert {r['key'] for r in a.json()['items']}=={global_memory['key'],scoped['key']}
    assert {r['key'] for r in b.json()['items']}=={global_memory['key']}
