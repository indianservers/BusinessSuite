"""AI-only access consumes company controls without revealing business records."""
from uuid import uuid4
from datetime import datetime
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_suite_conversations import create,ROOT
from ai_test_utils import auth_headers
from app.access.models import AccessPolicy
from app.ai_agents.models import AiSecuritySetting,AiUsageLimit,AiUsageEvent


def managed(client,db):
    h,owner,_,_=setup_suite(client,db)
    headers,user=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','helpdesk_view'])
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={
        'ai':{'enabled':True,'role':'Employee','scope':'own','permissions':['ai_assistant'],'actions':['view','create','approve','delete']},
        'hrms':{'enabled':True,'role':'Requester','scope':'own','permissions':['helpdesk_view'],'actions':['view','create']},
    }));db.commit()
    return h,owner,headers,user


def test_private_suite_chat_needs_no_pms_grant_and_stays_owner_only(client,db):
    h,owner,headers,user=managed(client,db)
    chat=create(client,headers)
    assert client.get(ROOT+f'/conversations/{chat}',headers=headers).status_code==200
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/conversations/{chat}',headers=other).status_code==404
    assert client.get('/api/v1/project-management/projects',headers=headers).status_code==403


def test_company_ai_kill_switch_cannot_be_hidden_by_own_record_scope(client,db):
    h,owner,headers,user=managed(client,db)
    setting=AiSecuritySetting(company_id=1,ai_enabled=False)
    db.add(setting);db.commit()
    response=client.get(ROOT+'/tools',headers=headers)
    assert response.status_code==403,response.text
    assert 'AI_AGENT_DISABLED' in response.text
    assert db.query(AiSecuritySetting).filter_by(company_id=1).count()==1


def test_company_quota_counts_other_users_under_own_record_scope(client,db):
    h,owner,headers,user=managed(client,db)
    db.add(AiUsageEvent(company_id=1,user_id=owner.id,event_type='synthetic_company_usage',module='CROSS',created_at=datetime.utcnow()))
    db.add(AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True));db.commit()
    response=client.get(ROOT+'/tools',headers=headers)
    assert response.status_code==429,response.text
    assert 'AI_USAGE_LIMIT_EXCEEDED' in response.text


def test_other_company_usage_does_not_consume_current_company_quota(client,db):
    h,owner,headers,user=managed(client,db)
    _,other=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'],company_id=2)
    db.add(AiUsageEvent(company_id=2,user_id=other.id,event_type='synthetic_other_company_usage',module='CROSS',created_at=datetime.utcnow()))
    db.add(AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True));db.commit()
    assert client.get(ROOT+'/tools',headers=headers).status_code==200


def test_shared_suite_models_are_ai_and_legacy_pms_runs_keep_pms_scope():
    from app.access.scope import model_module
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
    from app.ai_operator.models import OperatorRun
    assert all(model_module(model)=='ai' for model in (SuiteRun,AssistantConversation,AssistantMessage))
    assert model_module(OperatorRun)=='project_management'


def test_normal_ai_reads_do_not_create_security_configuration(client,db):
    h,owner,headers,user=managed(client,db)
    before=db.query(AiSecuritySetting).count()
    assert client.get(ROOT+'/tools',headers=headers).status_code==200
    assert db.query(AiSecuritySetting).count()==before


def test_other_company_kill_switch_does_not_disable_current_company(client,db):
    h,owner,headers,user=managed(client,db)
    auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'],company_id=2)
    db.add(AiSecuritySetting(company_id=2,ai_enabled=False));db.commit()
    assert client.get(ROOT+'/tools',headers=headers).status_code==200


def test_hrms_account_lookup_does_not_require_crm_or_pms_grants(client,db):
    h,owner,headers,user=managed(client,db)
    from tests.test_suite_conversations import say
    from app.ai_operator.suite_tools import minimize_source
    result=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Read authorized HR account names',
        'context':[{'tool':'hrms.people','payload':{'q':user.email,'limit':5}}],
        'local_plan':{'summary':'Read selected company account metadata','steps':[]}})
    assert result.status_code==200,result.text
    assert result.json()['status']=='answered',result.json()
    assert minimize_source('hrms.people',{'items':[{'id':12,'displayName':'Ravi Example','email':'private@example.com','personId':99}]})==[{'id':12,'name':'Ravi Example'}]


def test_shared_user_search_uses_selected_company_instead_of_primary_company(client,db):
    h,owner,_,_=managed(client,db)
    _,first=auth_headers(client,db,email='ravi-scope-primary@example.com',permissions=['ai_assistant'],company_id=1)
    second_headers,second=auth_headers(client,db,email='ravi-scope-selected@example.com',permissions=['ai_assistant'],company_id=2)
    response=client.get('/api/v1/users/search',headers={**h,'X-Suite-Organization':'2','X-Suite-Branch':second_headers['X-Suite-Branch']},params={'q':'ravi-scope','limit':25})
    assert response.status_code==200,response.text
    assert {r['id'] for r in response.json()['items']}=={second.id}


def test_pending_company_kill_switch_is_enforced_in_same_transaction(client,db):
    import pytest
    from fastapi import HTTPException
    from app.ai_agents.services.advanced_security import AiSecuritySettingsService
    h,owner,headers,user=managed(client,db)
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False))
    with pytest.raises(HTTPException) as denied:AiSecuritySettingsService(db).ensure_enabled(user=user,module='CROSS')
    assert denied.value.status_code==403


def test_pending_company_quota_and_usage_are_enforced_in_same_transaction(client,db):
    import pytest
    from fastapi import HTTPException
    from app.ai_agents.services.advanced_security import AiUsageService
    h,owner,headers,user=managed(client,db)
    db.add(AiUsageEvent(company_id=1,user_id=owner.id,event_type='pending_synthetic_usage',module='CROSS',created_at=datetime.utcnow()))
    db.add(AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True))
    with pytest.raises(HTTPException) as denied:AiUsageService(db).check_limits(user=user,agent=None,module='CROSS')
    assert denied.value.status_code==429
