"""AI administration reuses native provider storage without PMS access."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_suite_module_scope import managed
from ai_test_utils import auth_headers
from app.access.models import AccessPolicy
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from uuid import uuid4


def admin(client,db,company=1,configure=True):
    headers,user=auth_headers(client,db,email=f'{uuid4()}@example.com',company_id=company,permissions=['ai_assistant','settings_manage'])
    db.add(AccessPolicy(company_id=company,user_id=user.id,status='active',grants={'ai':{'enabled':True,'role':'Administrator','scope':'own','permissions':['ai_assistant','settings_manage'],'actions':['view',*(['configure'] if configure else [])]}}));db.commit()
    return headers,user


def test_ai_admin_updates_shared_company_provider_without_pms_or_key_replacement(client,db,monkeypatch):
    setup_suite(client,db)
    headers,user=admin(client,db)
    row=db.query(OperatorProvider).filter_by(provider='gemini').one();encrypted=row.encrypted_key
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'updated-model','enabled':True,'data_sharing_allowed':True})
    assert response.status_code==200,response.text
    assert response.json()['model']=='updated-model'
    db.refresh(row);assert row.encrypted_key==encrypted and row.updated_by==user.id
    assert db.query(OperatorProvider).filter_by(provider='gemini').count()==1
    calls=mock_provider(monkeypatch,{'summary':'Connection verified','steps':[]})
    response=client.post(ROOT+'/providers/gemini/test',headers=headers)
    assert response.status_code==200,response.text
    assert len(calls)==1
    assert db.query(OperatorApiLog).filter_by(user_id=user.id,purpose='test').one().module=='CROSS'
    response=client.get('/api/v1/project-management/projects',headers=headers)
    assert response.status_code==403,response.text


def test_ai_admin_creates_provider_in_existing_table_without_disclosing_key(client,db):
    setup_suite(client,db)
    headers,user=admin(client,db)
    response=client.put(ROOT+'/providers/openai',headers=headers,json={'model':'test-model','api_key':'synthetic-provider-admin-key','enabled':True,'data_sharing_allowed':True})
    assert response.status_code==200,response.text
    assert response.json()['has_key'] is True
    assert 'synthetic-provider-admin-key' not in response.text and 'encrypted_key' not in response.text
    row=db.query(OperatorProvider).filter_by(provider='openai',scope_key='company:1').one()
    assert row.encrypted_key!='synthetic-provider-admin-key'


def test_viewer_and_settings_role_without_configure_cannot_change_or_test(client,db):
    _,_,viewer,_=managed(client,db)
    no_configure,_=admin(client,db,configure=False)
    for headers in (viewer,no_configure):
        for path,method in [('/providers/gemini','put'),('/providers/gemini/test','post')]:
            response=getattr(client,method)(ROOT+path,headers=headers,json={'model':'unapproved-change'} if method=='put' else {})
            assert response.status_code==403,response.text
    assert db.query(OperatorProvider).filter_by(provider='gemini').one().model=='test-model'


def test_ai_admin_company_isolation_and_missing_new_key(client,db):
    setup_suite(client,db)
    headers,user=admin(client,db,company=2)
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'company-two'})
    assert response.status_code==422,response.text
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'company-two','api_key':'synthetic-company-two-key'})
    assert response.status_code==200,response.text
    assert db.query(OperatorProvider).filter_by(provider='gemini',scope_key='company:1').one().model=='test-model'
    assert db.query(OperatorProvider).filter_by(provider='gemini',scope_key='company:2').one().model=='company-two'


def test_admin_can_repair_configuration_during_emergency_stop(client,db):
    _,_,viewer,_=managed(client,db)
    headers,user=admin(client,db)
    from app.ai_agents.models import AiSecuritySetting
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False));db.commit()
    response=client.get(ROOT+'/providers',headers=headers)
    assert response.status_code==200,response.text
    response=client.get(ROOT+'/providers',headers=viewer)
    assert response.status_code==403,response.text
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'repaired-model','enabled':False,'data_sharing_allowed':False})
    assert response.status_code==200,response.text
    assert not response.json()['enabled']


def test_configure_action_without_native_settings_permission_is_denied(client,db):
    setup_suite(client,db)
    headers,user=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={'ai':{'enabled':True,'role':'Employee','scope':'own','permissions':['ai_assistant'],'actions':['view','configure']}}));db.commit()
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'not-authorized'})
    assert response.status_code==403,response.text


def test_ai_admin_cannot_override_unmanaged_native_workspace(client,db):
    setup_suite(client,db)
    headers,user=admin(client,db)
    from app.apps.project_management.models import PMSWorkspace
    workspace=db.query(PMSWorkspace).first();assert workspace
    response=client.put(ROOT+'/providers/gemini',params={'workspace_id':workspace.id},headers=headers,json={'model':'not-authorized','api_key':'synthetic-unapproved-key'})
    assert response.status_code in {403,404},response.text
    assert db.query(OperatorProvider).filter_by(provider='gemini',scope_key='company:1').one().model=='test-model'
