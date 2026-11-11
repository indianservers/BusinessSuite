from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_saved_agents import profile,command
from ai_test_utils import auth_headers
from app.access.models import AccessMembership
from app.ai_operator.assistant_models import AssistantConversation
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite/agents/library'
AGENTS='/api/v1/ai-operator/suite/agents'


def member(client,db,company_id=1,permissions=None):
    h,user=auth_headers(client,db,email=f'{uuid4()}@example.com',company_id=company_id,permissions=permissions or ['ai_assistant','crm_view','crm_manage','crm_activities_manage'])
    existing=db.query(AccessMembership).filter_by(user_id=user.id,company_id=company_id).first()
    if not existing:db.add(AccessMembership(user_id=user.id,company_id=company_id,active=True,is_admin=False))
    else:existing.active=True
    db.commit();return h,user


def proposal(client,h,asset,kind='agent',audience=None,**extra):
    body={'request_key':str(uuid4()),'asset_type':kind,'source_id':asset['id'],'source_revision':asset['revision'],'audience':audience or {'kind':'organization'},**extra}
    r=client.post(ROOT+'/preview',headers=h,json=body);assert r.status_code==200,r.text
    return r.json(),body


def publish(client,h,draft):
    r=client.post(ROOT+f'/{draft["id"]}/publish',headers=h,json={'preview_hash':draft['pending']['preview_hash']});assert r.status_code==200,r.text
    return r.json()


def install(client,h,publication,**extra):
    r=client.post(ROOT+f'/{publication["id"]}/install',headers=h,json={'revision':publication['revision'],'definition_hash':publication['definition_hash'],**extra})
    assert r.status_code==200,r.text
    return r.json()['asset']


def test_agent_publication_is_reviewed_and_never_shares_private_memory_or_history(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    agent=profile(client,owner,name='Shared customer followup',memory=['I prefer private operator notes.'])
    draft,body=proposal(client,owner,agent)
    assert draft['status']=='draft' and draft['pending']['definition']['omitted']['private_memory']==1
    assert client.get(ROOT,headers=h).json()['items']==[]
    assert 'I prefer private operator notes' not in client.get(ROOT+f'/{draft["id"]}',headers=owner).text
    assert client.post(ROOT+'/preview',headers=owner,json=body).json()['id']==draft['id']
    publication=publish(client,owner,draft)
    assert publish(client,owner,draft)['id']==publication['id']
    imported=install(client,h,publication)
    assert imported['id']!=agent['id'] and imported['memory']==[] and imported['connection_ids']==[] and imported['mcp_ids']==[]
    assert imported['library_origin']['publication_id']==publication['id']
    assert install(client,h,publication)['id']==imported['id']
    assert client.get(AGENTS+f'/{agent["id"]}/activity',headers=h).status_code==404
    run=command(client,h,imported)
    assert run['status']=='awaiting_approval',run
    assert db.query(CRMTask).count()==0


def test_revoke_blocks_pending_approval_future_runs_and_schedules(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    agent=profile(client,owner);draft,_=proposal(client,owner,agent);publication=publish(client,owner,draft);imported=install(client,h,publication)
    run=command(client,h,imported)
    r=client.post(ROOT+f'/{publication["id"]}/revoke',headers=owner,json={'revision':publication['revision']});assert r.status_code==200,r.text
    assert client.get(ROOT,headers=h).json()['items']==[]
    assert client.post('/api/v1/ai-operator/suite/runs/'+str(run['id'])+'/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==403
    r=client.post('/api/v1/ai-operator/suite/commands',headers=h,json={'request_key':str(uuid4()),'agent_id':imported['id'],'module':'CRM','provider':'local','text':'Create CRM task called Blocked publication'})
    assert r.status_code==403,r.text
    from app.ai_operator.agent_schedules import snapshot
    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException):snapshot(db,user,imported['id'])
    assert client.delete(AGENTS+f'/{imported["id"]}',headers=h).status_code==200
    assert db.query(CRMTask).count()==0


def test_publishing_and_selected_member_audiences_do_not_grant_permissions(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db,permissions=['ai_assistant','crm_view']);other,_=member(client,db)
    agent=profile(client,owner);draft,_=proposal(client,owner,agent,audience={'kind':'members','member_ids':[user.id]});publication=publish(client,owner,draft)
    assert client.get(ROOT+f'/{publication["id"]}',headers=other).status_code==404
    assert client.post(ROOT+f'/{publication["id"]}/install',headers=other,json={'revision':publication['revision'],'definition_hash':publication['definition_hash']}).status_code==404
    mine=install(client,h,publication)
    assert client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'asset_type':'agent','source_id':mine['id'],'source_revision':1,'audience':{'kind':'organization'}}).status_code==403
    run=command(client,h,mine)
    assert run['status']=='failed' and run['approval_id'] is None,run
    assert db.query(CRMTask).count()==0


def test_new_edition_requires_reviewed_update_and_keeps_private_preferences(client,db):
    owner,_,_,_=setup_suite(client,db);h,_=member(client,db)
    agent=profile(client,owner);draft,_=proposal(client,owner,agent);first=publish(client,owner,draft);mine=install(client,h,first)
    body={k:mine[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','mcp_ids','environment')};body.update(revision=mine['revision'],memory=['Prefer concise answers.'])
    r=client.put(AGENTS+f'/{mine["id"]}',headers=h,json=body);assert r.status_code==200,r.text
    mine=r.json()
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','mcp_ids','environment')};body.update(revision=1,instructions='Prepare recovery tasks and explain source limits.')
    r=client.put(AGENTS+f'/{agent["id"]}',headers=owner,json=body);assert r.status_code==200,r.text
    draft,_=proposal(client,owner,r.json(),publication_id=first['id'],revision=first['revision'])
    assert command(client,h,mine)['status']=='awaiting_approval'  # Pending edition is not active.
    latest=publish(client,owner,draft)
    r=client.post(ROOT+f'/{latest["id"]}/install',headers=h,json={'revision':latest['revision'],'definition_hash':latest['definition_hash'],'asset_revision':1})
    assert r.status_code==409
    updated=install(client,h,latest,asset_revision=mine['revision'])
    assert updated['id']==mine['id'] and updated['memory']==['Prefer concise answers.'] and updated['revision']==mine['revision']+1
    assert updated['instructions']==body['instructions']
    assert len(client.get(ROOT+f'/{latest["id"]}/versions',headers=h).json()['items'])==2


def test_skill_publications_and_bundled_skills_install_atomically(client,db):
    owner,_,_,_=setup_suite(client,db);h,_=member(client,db)
    r=client.post(AGENTS+'/catalog/skills',headers=owner,json={'name':'Customer recovery procedure','instructions':'Review delivery dates before drafting followups.','tools':['crm.tasks','crm.create_task']});assert r.status_code==200,r.text
    skill=r.json();draft,_=proposal(client,owner,skill,kind='skill');publication=publish(client,owner,draft);private=install(client,h,publication)
    assert private['id']!=skill['id'] and private['library_origin']['component']=='skill'
    agent=profile(client,owner,tools=skill['tools'],skill_ids=[skill['id']]);draft,_=proposal(client,owner,agent);publication=publish(client,owner,draft)
    imported=install(client,h,publication)
    assert len(imported['skill_ids'])==1 and imported['skill_ids'][0] not in (skill['id'],private['id'])
    copied=db.get(AssistantConversation,imported['skill_ids'][0]);assert copied.references['library_origin']['component']=='agent-skill:0'
    assert install(client,h,publication)['skill_ids']==imported['skill_ids']


def test_cross_company_source_changes_and_tampering_fail_closed(client,db):
    from app.shared.models import ServicePolicy
    owner,_,_,_=setup_suite(client,db);other,_=member(client,db,company_id=2)
    agent=profile(client,owner);draft,_=proposal(client,owner,agent);publication=publish(client,owner,draft)
    assert client.get(ROOT+f'/{publication["id"]}',headers=other).status_code==404
    row=db.get(ServicePolicy,publication['id']);row.values_json={**row.values_json,'definition':{**row.values_json['definition'],'instructions':'Tampered'}};db.commit()
    assert client.get(ROOT+f'/{publication["id"]}',headers=owner).status_code==409


def test_workspace_team_membership_is_checked_again_at_runtime(client,db):
    from app.apps.project_management.models import PMSWorkspaceMember,PMSWorkspaceTeam,PMSWorkspaceTeamMember
    from test_identity_utils import provision_workflow_workspace
    owner,publisher,_,_=setup_suite(client,db);h,user=member(client,db)
    workspace=provision_workflow_workspace(db,publisher)
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Member'))
    team=PMSWorkspaceTeam(workspace_id=workspace.id,name='Delivery reviewers',alias='delivery-reviewers');db.add(team);db.commit()
    agent=profile(client,owner,workspace_id=workspace.id)
    draft,_=proposal(client,owner,agent,audience={'kind':'workspace_teams','team_ids':[team.id]});publication=publish(client,owner,draft)
    assert client.get(ROOT+f'/{publication["id"]}',headers=h).status_code==404
    membership=PMSWorkspaceTeamMember(team_id=team.id,user_id=user.id);db.add(membership);db.commit()
    mine=install(client,h,publication)
    db.delete(membership);db.commit()
    r=client.post('/api/v1/ai-operator/suite/commands',headers=h,json={'request_key':str(uuid4()),'agent_id':mine['id'],'workspace_id':workspace.id,'module':'CRM','provider':'local','text':'Create CRM task called Removed team access'})
    assert r.status_code in (403,404),r.text
    assert db.query(CRMTask).count()==0


def test_shared_skill_revocation_stops_already_queued_actions(client,db):
    owner,_,_,_=setup_suite(client,db);h,_=member(client,db)
    r=client.post(AGENTS+'/catalog/skills',headers=owner,json={'name':'Reviewed CRM procedure','instructions':'Use clear followup titles.','tools':['crm.create_task']})
    skill=r.json();draft,_=proposal(client,owner,skill,kind='skill');publication=publish(client,owner,draft);mine=install(client,h,publication)
    agent=profile(client,h,skill_ids=[mine['id']]);run=command(client,h,agent);approve(client,h,run)
    assert client.post(ROOT+f'/{publication["id"]}/revoke',headers=owner,json={'revision':publication['revision']}).status_code==200
    tick(client,db)
    current=client.get('/api/v1/ai-operator/suite/runs/'+str(run['id']),headers=h).json()
    assert current['status']!='succeeded' and db.query(CRMTask).count()==0


def test_previous_editions_keep_their_own_audience_restrictions(client,db):
    owner,_,_,_=setup_suite(client,db);a,user_a=member(client,db);b,user_b=member(client,db)
    agent=profile(client,owner,instructions='Earlier restricted customer procedure.')
    draft,_=proposal(client,owner,agent,audience={'kind':'members','member_ids':[user_a.id]});first=publish(client,owner,draft)
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','mcp_ids','environment')};body.update(revision=1,instructions='New edition for a different audience.')
    changed=client.put(AGENTS+f'/{agent["id"]}',headers=owner,json=body).json()
    draft,_=proposal(client,owner,changed,audience={'kind':'members','member_ids':[user_b.id]},publication_id=first['id'],revision=first['revision']);latest=publish(client,owner,draft)
    history=client.get(ROOT+f'/{latest["id"]}/versions',headers=b);assert history.status_code==200,history.text
    assert len(history.json()['items'])==1 and 'Earlier restricted' not in history.text
    assert client.get(ROOT+f'/{latest["id"]}/versions',headers=a).status_code==404
    assert len(client.get(ROOT+f'/{latest["id"]}/versions',headers=owner).json()['items'])==2


def test_source_changes_after_preview_require_a_fresh_review(client,db):
    owner,_,_,_=setup_suite(client,db);agent=profile(client,owner)
    draft,_=proposal(client,owner,agent)
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','mcp_ids','environment')};body.update(revision=1,instructions='Changed after the publication preview.')
    assert client.put(AGENTS+f'/{agent["id"]}',headers=owner,json=body).status_code==200
    r=client.post(ROOT+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':draft['pending']['preview_hash']})
    assert r.status_code==409,r.text


def test_bundled_skill_updates_check_private_revisions(client,db):
    owner,_,_,_=setup_suite(client,db);h,_=member(client,db)
    original={'name':'Delivery checks','instructions':'Review customer due dates.','tools':['crm.create_task']}
    skill=client.post(AGENTS+'/catalog/skills',headers=owner,json=original).json()
    agent=profile(client,owner,skill_ids=[skill['id']]);draft,_=proposal(client,owner,agent);first=publish(client,owner,draft);mine=install(client,h,first)
    component=mine['skill_ids'][0]
    changed=client.put(AGENTS+f'/catalog/skills/{skill["id"]}',headers=owner,json={**original,'instructions':'Review dates and responsible owners.','revision':1});assert changed.status_code==200
    draft,_=proposal(client,owner,agent,publication_id=first['id'],revision=first['revision']);latest=publish(client,owner,draft)
    edited=client.put(AGENTS+f'/catalog/skills/{component}',headers=h,json={**original,'instructions':'A personal edit while update review is open.','revision':1});assert edited.status_code==200
    body={'revision':latest['revision'],'definition_hash':latest['definition_hash'],'asset_revision':mine['revision'],'component_revisions':{str(component):1}}
    assert client.post(ROOT+f'/{latest["id"]}/install',headers=h,json=body).status_code==409
    assert db.get(AssistantConversation,component).references['revision']==2
    updated=install(client,h,latest,asset_revision=mine['revision'],component_revisions={str(component):2})
    assert updated['skill_ids']==[component] and db.get(AssistantConversation,component).references['revision']==3


def test_failed_install_rolls_back_bundled_skills(client,db,monkeypatch):
    from app.ai_operator import saved_agents
    from fastapi import HTTPException
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    skill=client.post(AGENTS+'/catalog/skills',headers=owner,json={'name':'Bundle','instructions':'Prepare reviewed customer followups.','tools':['crm.create_task']}).json()
    agent=profile(client,owner,skill_ids=[skill['id']]);draft,_=proposal(client,owner,agent);publication=publish(client,owner,draft)
    original=saved_agents.access
    def deny_agent(session,actor,config):
        if actor.id==user.id and config.skill_ids:raise HTTPException(403,'Synthetic authorization change after staging skills')
        return original(session,actor,config)
    monkeypatch.setattr(saved_agents,'access',deny_agent)
    r=client.post(ROOT+f'/{publication["id"]}/install',headers=h,json={'revision':publication['revision'],'definition_hash':publication['definition_hash']})
    assert r.status_code==403,r.text
    assert db.query(AssistantConversation).filter_by(user_id=user.id).filter(AssistantConversation.references['library_origin']['publication_id'].as_integer()==publication['id']).count()==0


def test_another_org_admin_can_review_a_new_edition_without_reading_private_source(client,db):
    owner,_,_,_=setup_suite(client,db);admin_h,administrator=member(client,db)
    membership=db.query(AccessMembership).filter_by(user_id=administrator.id,company_id=1).one();membership.is_admin=True;db.commit()
    original=profile(client,owner,instructions='Original approved procedure.',memory=['Private owner preference.'])
    draft,_=proposal(client,owner,original);first=publish(client,owner,draft)
    replacement=profile(client,admin_h,instructions='Updated organization procedure from a new maintainer.')
    assert client.get(AGENTS+f'/{original["id"]}/activity',headers=admin_h).status_code==404
    draft,_=proposal(client,admin_h,replacement,publication_id=first['id'],revision=first['revision'])
    latest=publish(client,admin_h,draft)
    assert latest['revision']==first['revision']+1 and latest['definition']['instructions']==replacement['instructions']
    assert 'Private owner preference' not in client.get(ROOT+f'/{latest["id"]}',headers=admin_h).text


def test_install_refreshes_a_preloaded_private_revision_before_update(client,db):
    from sqlalchemy import update
    from sqlalchemy.orm.attributes import set_committed_value
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    original=profile(client,owner);draft,_=proposal(client,owner,original);first=publish(client,owner,draft)
    mine=install(client,h,first)
    changed=client.put(AGENTS+f'/{original["id"]}',headers=owner,json={**{k:v for k,v in original.items() if k not in ('id','execution','trigger_support','library_origin')},'instructions':'A newly reviewed organization procedure.'})
    assert changed.status_code==200,changed.text
    draft,_=proposal(client,owner,changed.json(),publication_id=first['id'],revision=first['revision']);latest=publish(client,owner,draft)
    cached=db.get(AssistantConversation,mine['id'])
    # Simulate a committed editor revision that the session identity map has not seen.
    previous=cached.references
    revised={**previous,'revision':mine['revision']+1,'config':{**previous['config'],'memory':['Keep this concurrent private edit.']}}
    db.execute(update(AssistantConversation).where(AssistantConversation.id==cached.id).values(references=revised).execution_options(synchronize_session=False))
    db.commit()
    set_committed_value(cached,'references',previous)
    assert cached.references['revision']==mine['revision']
    response=client.post(ROOT+f'/{latest["id"]}/install',headers=h,json={'revision':latest['revision'],'definition_hash':latest['definition_hash'],'asset_revision':mine['revision']})
    assert response.status_code==409,response.text
    db.refresh(cached)
    assert cached.references['config']['memory']==['Keep this concurrent private edit.']
