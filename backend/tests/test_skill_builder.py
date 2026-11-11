from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_suite_operator import setup_suite
from tests.test_agent_builder import send,profiles,ROOT
from ai_test_utils import auth_headers
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_models import SuiteRun
from app.apps.automation.models import AutomationScheduledJob as Job


@pytest.mark.parametrize('description,module',[
    ('customer onboarding','CRM'),('project risk assessment','PMS'),('leave and attendance analysis','HRMS'),
    ('payroll verification','HRMS'),('sales performance analysis','CRM'),
])
def test_local_skill_templates_select_the_business_module(description,module):
    from app.ai_operator.agent_builder import local_draft
    from app.ai_operator.suite_tools import TOOLS
    value=local_draft('Create a '+description+' skill',None,None)
    assert value.tools and {TOOLS[t].module for t in value.tools}=={module}


def test_procedure_correction_does_not_replace_the_existing_tool_scope():
    from app.ai_operator.agent_builder import local_draft
    first=local_draft('Create a lead qualification skill',None,'CRM')
    changed=local_draft('Procedure: Check invoices before qualifying the lead.',first.model_dump(),'CRM')
    assert changed.tools==first.tools


def test_skill_builder_followups_persist_and_save_a_versioned_skill_only(client,db):
    h,_,_,_=setup_suite(client,db)
    first,body=send(client,h,'Create a lead qualification skill that checks customer fit',asset_type='skill')
    assert first['asset_type']=='skill' and not first['question']
    assert client.post(ROOT+'/messages',headers=h,json=body).json()['context_id']==first['context_id']
    second,_=send(client,h,'Procedure: Check sector fit, budget and next steps.',first,asset_type='skill')
    third,_=send(client,h,'Add step: Ask the owner to review uncertain opportunities.',second,asset_type='skill')
    final,_=send(client,h,'Call it Qualified prospect review',third,asset_type='skill')
    assert 'Check sector fit' in final['config']['instructions'] and 'uncertain opportunities' in final['config']['instructions']
    assert client.post(ROOT+f'/{first["context_id"]}/apply',headers=h,json={'preview_hash':first['preview_hash']}).status_code==409
    r=client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']});assert r.status_code==200,r.text
    skill=r.json()['skill'];assert skill['revision']==1 and skill['name']=='Qualified prospect review'
    assert client.post(ROOT+f'/{final["context_id"]}/apply',headers=h,json={'preview_hash':final['preview_hash']}).json()['skill']['id']==skill['id']
    assert client.get('/api/v1/ai-operator/suite/agents/catalog/skills/'+str(skill['id'])+'/versions',headers=h).json()['current_revision']==1
    assert client.get(ROOT,headers=h).json()['items']==[]
    assert client.get(ROOT,headers=h,params={'asset_type':'skill'}).json()['items'][0]['skill_id']==skill['id']
    assert len(client.get(ROOT+f'/{final["context_id"]}',headers=h).json()['messages'])==4
    assert profiles(db)==0 and db.query(Job).count()==0 and db.query(SuiteRun).count()==0


def test_skill_designs_cannot_switch_mode_or_be_read_by_another_user(client,db):
    h,_,_,_=setup_suite(client,db);first,_=send(client,h,'Create a CRM followup skill',asset_type='skill')
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.get(ROOT+f'/{first["context_id"]}',headers=other).status_code==404
    response=client.post(ROOT+'/messages',headers=h,json={'request_key':str(uuid4()),'context_id':first['context_id'],'revision':first['revision'],'text':'Call it An agent now','provider':'local'})
    assert response.status_code==409
    assert profiles(db)==0


@pytest.mark.parametrize('feature',['every morning','remember: I prefer a short summary'])
def test_skill_builder_clarifies_agent_features_instead_of_saving_or_scheduling(client,db,feature):
    h,_,_,_=setup_suite(client,db)
    draft,_=send(client,h,'Create a CRM sales skill that checks overdue tasks '+feature,asset_type='skill')
    assert draft['question'] and draft['schedule'] is None and draft['config']['memory']==[]
    assert client.post(ROOT+f'/{draft["context_id"]}/apply',headers=h,json={'preview_hash':draft['preview_hash']}).status_code==409
    clarified,_=send(client,h,'Manual only',draft,asset_type='skill')
    assert not clarified['question']
    assert db.query(Job).count()==0 and profiles(db)==0


def test_cloud_skill_builder_reuses_permission_constraints_and_review(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    mock_provider(monkeypatch,{'name':'Delivery procedure','instructions':'Review customer delivery commitments.','tools':['crm.tasks','crm.create_task'],'memory':[],'schedule':None,'question':None})
    value,_=send(client,h,'Create a read only CRM delivery skill',asset_type='skill',provider='gemini')
    assert value['config']['tools']==['crm.tasks'] and value['asset_type']=='skill'
    response=client.post(ROOT+f'/{value["context_id"]}/apply',headers=h,json={'preview_hash':value['preview_hash']})
    assert response.status_code==200,response.text
    assert response.json()['skill']['tools']==['crm.tasks']
    assert profiles(db)==0 and db.query(SuiteRun).count()==0
