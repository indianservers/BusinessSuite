"""Shared definitions honor central roles and remain private installed copies."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_module_scope import managed
from tests.test_saved_agents import profile
from tests.test_agent_library import proposal,publish,install,ROOT,AGENTS
from app.access.models import AccessMembership
from uuid import uuid4


def test_library_installs_bundled_hrms_agent_without_unrelated_module_access(client,db):
    owner,_,headers,user=managed(client,db)
    db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=False));db.commit()
    response=client.post(AGENTS+'/catalog/skills',headers=owner,json={'name':'Reviewed ticket reading','instructions':'Read only a ticket selected by the user.','tools':['hrms.ticket']})
    assert response.status_code==200,response.text
    skill=response.json()
    source=profile(client,owner,name='Shared HRMS reader',modules=['HRMS'],tools=['hrms.ticket'],skill_ids=[skill['id']],memory=['PRIVATE OWNER PREFERENCE'])
    draft,_=proposal(client,owner,source,audience={'kind':'members','member_ids':[user.id]})
    publication=publish(client,owner,draft)
    response=client.get(ROOT,headers=headers)
    assert response.status_code==200,response.text
    assert publication['id'] in [item['id'] for item in response.json()['items']]
    mine=install(client,headers,publication)
    assert mine['memory']==[] and mine['id']!=source['id'] and mine['skill_ids']!=source['skill_ids']
    assert install(client,headers,publication)['id']==mine['id']
    response=client.get(AGENTS+f'/catalog/skills/{mine["skill_ids"][0]}/versions',headers=headers)
    assert response.status_code==200,response.text
    assert len(response.json()['items'])==1
    assert 'PRIVATE OWNER PREFERENCE' not in response.text
    response=client.get(AGENTS+f'/catalog/skills/{skill["id"]}/versions',headers=headers)
    assert response.status_code==404,response.text
    response=client.post('/api/v1/ai-operator/suite/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Review the selected ticket','module':'HRMS','agent_id':mine['id'],'provider':'local','local_plan':{'summary':'Need one record','question':'Which ticket?','steps':[]}})
    assert response.status_code==200,response.text
    assert response.json()['status']=='needs_clarification',response.json()
    assert response.json()['result']['agent']['id']==mine['id']
    response=client.get('/api/v1/project-management/projects',headers=headers)
    assert response.status_code==403,response.text
    response=client.get(AGENTS+f'/{source["id"]}/activity',headers=headers)
    assert response.status_code==404,response.text


def test_organization_admin_membership_does_not_override_central_ai_configure_denial(client,db):
    owner,_,headers,user=managed(client,db)
    db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=True));db.commit()
    source=profile(client,headers,name='Private HRMS reader',modules=['HRMS'],tools=['hrms.ticket'])
    response=client.post(ROOT+'/preview',headers=headers,json={'request_key':str(uuid4()),'asset_type':'agent','source_id':source['id'],'source_revision':source['revision'],'audience':{'kind':'organization'}})
    assert response.status_code==403,response.text
    shared=profile(client,owner,name='Approved HRMS reader',modules=['HRMS'],tools=['hrms.ticket'])
    draft,_=proposal(client,owner,shared)
    publication=publish(client,owner,draft)
    response=client.get(ROOT,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['can_publish'] is False
    item=next(row for row in response.json()['items'] if row['id']==publication['id'])
    assert item['can_manage'] is False and item['can_install'] is True
    response=client.post(ROOT+f'/{publication["id"]}/revoke',headers=headers,json={'revision':publication['revision']})
    assert response.status_code==403,response.text


def test_centrally_authorized_organization_admin_can_publish_without_pms(client,db):
    _,_,headers,user=managed(client,db)
    from app.access.models import AccessPolicy
    db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=True))
    policy=db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
    policy.grants={**policy.grants,'ai':{**policy.grants['ai'],'actions':[*policy.grants['ai']['actions'],'configure']}};db.commit()
    source=profile(client,headers,name='Reviewed HRMS reader',modules=['HRMS'],tools=['hrms.ticket'])
    draft,_=proposal(client,headers,source)
    publication=publish(client,headers,draft)
    assert publication['status']=='active'
    response=client.get(ROOT,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['can_publish'] is True
    response=client.get('/api/v1/project-management/projects',headers=headers)
    assert response.status_code==403,response.text
