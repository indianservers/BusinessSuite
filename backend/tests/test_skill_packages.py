from datetime import timedelta
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from ai_test_utils import auth_headers
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_models import SuiteRun

ROOT='/api/v1/ai-operator/suite/agents/catalog'
PACKAGE={'format':'businesssuite-agent-skill-v1','name':'Delivery review','instructions':'Review authorized delivery dates before preparing followups.','tools':['crm.tasks','crm.create_task']}


def preview(client,h,**extra):
    body={'request_key':str(uuid4()),'package':PACKAGE,**extra}
    r=client.post(ROOT+'/skill-imports/preview',headers=h,json=body);assert r.status_code==200,r.text
    return r.json(),body


def skill_count(db):return db.query(AssistantConversation).filter(AssistantConversation.references['agent_skill'].as_boolean()==True).count()


def test_import_is_reviewed_idempotent_private_and_reuses_skill_versions(client,db):
    h,_,_,_=setup_suite(client,db);review,body=preview(client,h)
    assert skill_count(db)==0
    assert client.post(ROOT+'/skill-imports/preview',headers=h,json=body).json()['id']==review['id']
    path=ROOT+f'/skill-imports/{review["id"]}/confirm'
    assert client.post(path,headers=h,json={'preview_hash':'0'*64}).status_code==409
    r=client.post(path,headers=h,json={'preview_hash':review['preview_hash']});assert r.status_code==200,r.text
    skill=r.json()['skill'];assert skill['revision']==1 and skill_count(db)==1
    assert client.post(path,headers=h,json={'preview_hash':review['preview_hash']}).json()['skill']['id']==skill['id']
    assert client.get(ROOT+f'/skills/{skill["id"]}/versions',headers=h).json()['items'][0]['revision']==1
    exported=client.get(ROOT+f'/skills/{skill["id"]}/export',headers=h)
    assert exported.status_code==200 and exported.json()==PACKAGE
    assert db.query(SuiteRun).count()==0


@pytest.mark.parametrize('change',[
    {'tools':['crm.nonexistent']},{'tools':['crm.tasks','crm.tasks']},{'provider':'gemini'},
    {'workspace_id':99},{'instructions':'api key: do-not-store'},
    {'instructions':'AQ.'+'X'*35},{'format':'unknown-format'},
])
def test_untrusted_packages_reject_unknown_fields_credentials_and_tools(client,db,change):
    h,_,_,_=setup_suite(client,db)
    r=client.post(ROOT+'/skill-imports/preview',headers=h,json={'request_key':str(uuid4()),'package':{**PACKAGE,**change}})
    assert r.status_code==422,r.text
    assert skill_count(db)==0


def test_import_is_session_scoped_and_rejects_changed_definition_and_key(client,db):
    h,_,_,_=setup_suite(client,db);review,body=preview(client,h)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.post(ROOT+f'/skill-imports/{review["id"]}/confirm',headers=other,json={'preview_hash':review['preview_hash']}).status_code==404
    assert client.post(ROOT+'/skill-imports/preview',headers=h,json={**body,'package':{**PACKAGE,'name':'Changed'}}).status_code==409
    row=db.get(AssistantConversation,review['id']);row.references={**row.references,'package':{**PACKAGE,'instructions':'Modified after review.'}};db.commit()
    assert client.post(ROOT+f'/skill-imports/{review["id"]}/confirm',headers=h,json={'preview_hash':review['preview_hash']}).status_code==409
    assert skill_count(db)==0


def test_expired_import_and_missing_module_access_cannot_create_skills(client,db,monkeypatch):
    from app.ai_operator import skill_packages
    h,_,_,_=setup_suite(client,db);review,_=preview(client,h)
    instant=skill_packages.now()+timedelta(hours=2);monkeypatch.setattr(skill_packages,'now',lambda:instant)
    r=client.post(ROOT+f'/skill-imports/{review["id"]}/confirm',headers=h,json={'preview_hash':review['preview_hash']})
    assert r.status_code==409 and skill_count(db)==0
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.post(ROOT+'/skill-imports/preview',headers=other,json={'request_key':str(uuid4()),'package':PACKAGE}).status_code==403


def test_export_is_private_and_linked_definitions_keep_library_controls(client,db):
    h,_,_,_=setup_suite(client,db)
    r=client.post(ROOT+'/skills',headers=h,json={k:v for k,v in PACKAGE.items() if k!='format'});assert r.status_code==200,r.text
    ident=r.json()['id']
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.get(ROOT+f'/skills/{ident}/export',headers=other).status_code==404
    row=db.get(AssistantConversation,ident);row.references={**row.references,'library_origin':{'publication_id':123,'revision':1}};db.commit()
    assert client.get(ROOT+f'/skills/{ident}/export',headers=h).status_code==409
