"""Administrative revocation remains available when execution is stopped."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_saved_agents import profile
from tests.test_agent_library import proposal,publish,install,member,ROOT
from app.ai_agents.models import AiSecuritySetting,AiUsageLimit,AiUsageEvent
from uuid import uuid4
import pytest

@pytest.mark.parametrize('stop',['emergency','quota'])
def test_admin_can_inspect_and_revoke_during_stop_without_enabling_new_work(client,db,stop):
    owner,actor,_,_=setup_suite(client,db)
    headers,user=member(client,db)
    source=profile(client,owner)
    draft,_=proposal(client,owner,source);publication=publish(client,owner,draft)
    mine=install(client,headers,publication)
    pending,_=proposal(client,owner,source)
    setting=None;limit=None
    if stop=='emergency':
        setting=AiSecuritySetting(company_id=1,ai_enabled=False);db.add(setting)
    else:
        limit=AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True);db.add(limit)
        db.add(AiUsageEvent(company_id=1,user_id=actor.id,event_type='synthetic_stop',module='CROSS'))
    db.commit()
    response=client.get(ROOT,headers=owner)
    assert response.status_code==200,response.text
    response=client.get(ROOT+f'/{publication["id"]}',headers=owner)
    assert response.status_code==200,response.text
    response=client.get(ROOT+f'/{publication["id"]}/versions',headers=owner)
    assert response.status_code==200,response.text
    response=client.post(ROOT+'/preview',headers=owner,json={'request_key':str(uuid4()),'asset_type':'agent','source_id':source['id'],'source_revision':source['revision'],'audience':{'kind':'organization'}})
    assert response.status_code==(403 if stop=='emergency' else 429),response.text
    response=client.post(ROOT+f'/{pending["id"]}/publish',headers=owner,json={'preview_hash':pending['pending']['preview_hash']})
    assert response.status_code==(403 if stop=='emergency' else 429),response.text
    response=client.post(ROOT+f'/{publication["id"]}/install',headers=headers,json={'revision':publication['revision'],'definition_hash':publication['definition_hash']})
    assert response.status_code==(403 if stop=='emergency' else 429),response.text
    response=client.post(ROOT+f'/{pending["id"]}/discard-preview',headers=owner,json={'preview_hash':'0'*64})
    assert response.status_code==409,response.text
    response=client.post(ROOT+f'/{pending["id"]}/discard-preview',headers=owner,json={'preview_hash':pending['pending']['preview_hash']})
    assert response.status_code==200,response.text
    assert response.json()['pending'] is None
    response=client.post(ROOT+f'/{publication["id"]}/revoke',headers=headers,json={'revision':publication['revision']})
    assert response.status_code==403,response.text
    response=client.post(ROOT+f'/{publication["id"]}/revoke',headers=owner,json={'revision':publication['revision']+50})
    assert response.status_code==409,response.text
    response=client.post(ROOT+f'/{publication["id"]}/revoke',headers=owner,json={'revision':publication['revision']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='revoked'
    if setting:setting.ai_enabled=True
    if limit:limit.is_active=False
    db.commit()
    response=client.post('/api/v1/ai-operator/suite/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Create a customer follow-up task','module':'CRM','agent_id':mine['id'],'provider':'preferred'})
    assert response.status_code==403,response.text


@pytest.mark.parametrize('configured',[False,True])
def test_stopped_revocation_requires_managed_admin_configure_grant(client,db,configured):
    from tests.test_suite_module_scope import managed
    from app.access.models import AccessMembership,AccessPolicy
    owner,_,headers,user=managed(client,db)
    db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=True))
    if configured:
        policy=db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
        policy.grants={**policy.grants,'ai':{**policy.grants['ai'],'actions':['view','configure']}}
    db.commit()
    publisher=owner
    source=profile(client,publisher,name='Reviewed HRMS read-only definition',modules=['HRMS'],tools=['hrms.ticket'])
    draft,_=proposal(client,publisher,source);publication=publish(client,publisher,draft)
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False));db.commit()
    response=client.post(ROOT+f'/{publication["id"]}/revoke',headers=headers,json={'revision':publication['revision']})
    assert response.status_code==(200 if configured else 403),response.text
    response=client.get(ROOT+f'/{publication["id"]}',headers=owner)
    assert response.status_code==200,response.text
    assert response.json()['status']==('revoked' if configured else 'active')
