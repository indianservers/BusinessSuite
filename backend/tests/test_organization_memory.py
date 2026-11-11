from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_agent_library import member
from app.shared.models import ServicePolicy
from app.ai_operator.organization_memory import sign
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite/organization-memory'
SUITE='/api/v1/ai-operator/suite'
TEXT='Delivery changes require an owner review before making a customer commitment.'


def preview(client,h,text=TEXT,**extra):
    body={'request_key':str(uuid4()),'definition':{'title':'Delivery review policy','text':text,'category':'constraint','module':'CRM'},'audience':{'kind':'organization'},**extra}
    r=client.post(ROOT+'/preview',headers=h,json=body);assert r.status_code==200,r.text
    return r.json(),body


def publish(client,h,draft):
    r=client.post(ROOT+f'/{draft["id"]}/publish',headers=h,json={'preview_hash':draft['pending']['preview_hash']});assert r.status_code==200,r.text
    return r.json()


def memories(client,h,**params):
    r=client.get(SUITE+'/memory',headers=h,params={'module':'CRM',**params});assert r.status_code==200,r.text
    return r.json()['items']


def test_publication_is_reviewed_and_private_memory_is_never_shared(client,db):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db)
    assert client.post(SUITE+'/memory',headers=owner,json={'level':'user','text':'My private personal preference.'}).status_code==200
    draft,body=preview(client,owner,audience={'kind':'members','member_ids':[user.id]})
    assert memories(client,recipient)==[]
    assert client.post(ROOT+'/preview',headers=owner,json=body).json()['id']==draft['id']
    assert client.post(ROOT+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':'0'*64}).status_code==409
    value=publish(client,owner,draft);assert publish(client,owner,draft)['revision']==value['revision']
    shared=memories(client,recipient);assert len(shared)==1 and shared[0]['level']=='organization' and shared[0]['text']==TEXT
    assert 'private personal preference' not in str(shared)
    assert client.get(ROOT,headers=recipient,params={'module':'CRM'}).json()['items'][0]['definition']['text']==TEXT
    assert client.post(ROOT+'/preview',headers=recipient,json={**body,'request_key':str(uuid4())}).status_code==403


def test_policy_correction_changes_audience_without_leaking_prior_versions(client,db):
    owner,_,_,_=setup_suite(client,db);one,u1=member(client,db);two,u2=member(client,db)
    draft,_=preview(client,owner,audience={'kind':'members','member_ids':[u1.id]});first=publish(client,owner,draft)
    draft,_=preview(client,owner,text='Newly approved review procedure.',policy_id=first['id'],revision=first['revision'],audience={'kind':'members','member_ids':[u2.id]})
    assert memories(client,one)[0]['text']==TEXT and memories(client,two)==[]
    latest=publish(client,owner,draft);assert latest['revision']==first['revision']+1
    assert memories(client,one)==[] and memories(client,two)[0]['text']=='Newly approved review procedure.'
    history=client.get(ROOT+f'/{latest["id"]}/versions',headers=two)
    assert history.status_code==200 and len(history.json()['items'])==1 and TEXT not in history.text
    assert len(client.get(ROOT+f'/{latest["id"]}/versions',headers=owner).json()['items'])==2


@pytest.mark.parametrize('stage',['before_approval','queued'])
def test_revocation_stops_drafts_and_queued_writes_that_used_policy(client,db,stage):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    draft,_=preview(client,owner,audience={'kind':'members','member_ids':[user.id]});value=publish(client,owner,draft)
    r=client.post(SUITE+'/commands',headers=h,json={'request_key':str(uuid4()),'module':'CRM','provider':'local','text':'Create CRM task called Policy dependency check'});assert r.status_code==200,r.text
    run=r.json();assert run['status']=='awaiting_approval',run
    assert run['result']['memory_used'][0]['key']==f'organization:{value["id"]}' and run['result']['memory_used'][0]['revision']==value['revision']
    if stage=='queued':approve(client,h,run)
    assert client.post(ROOT+f'/{value["id"]}/revoke',headers=owner,json={'revision':value['revision']}).status_code==200
    assert memories(client,h)==[]
    if stage=='before_approval':assert client.post(SUITE+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==409
    else:
        tick(client,db);assert client.get(SUITE+f'/runs/{run["id"]}',headers=h).json()['status']!='succeeded'
    assert db.query(CRMTask).count()==0


def test_expiry_forget_company_and_integrity_boundaries(client,db):
    owner,_,_,_=setup_suite(client,db);other,_=member(client,db,company_id=2)
    draft,_=preview(client,owner,definition={'title':'Temporary policy','text':TEXT,'module':'CRM','expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()});value=publish(client,owner,draft)
    assert client.get(ROOT+f'/{value["id"]}/versions',headers=other).status_code==404
    row=db.get(ServicePolicy,value['id']);row.values_json={**row.values_json,'definition':{**row.values_json['definition'],'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}};sign(row);db.commit()
    assert memories(client,owner)==[]
    r=client.post(ROOT+f'/{value["id"]}/forget',headers=owner,json={'revision':value['revision']});assert r.status_code==200,r.text
    db.refresh(row);assert row.values_json['definition'] is None and row.values_json['history']==[] and TEXT not in str(row.values_json)
    draft,_=preview(client,owner);value=publish(client,owner,draft)
    row=db.get(ServicePolicy,value['id']);row.values_json={**row.values_json,'definition':{**row.values_json['definition'],'text':'Unsigned modification'}};db.commit()
    assert client.get(ROOT,headers=owner,params={'module':'CRM'}).status_code==409


def test_module_workspace_and_live_team_membership_filter_shared_memory(client,db):
    from app.apps.project_management.models import PMSWorkspaceMember,PMSWorkspaceTeam,PMSWorkspaceTeamMember
    from test_identity_utils import provision_workflow_workspace
    owner,publisher,_,_=setup_suite(client,db);h,user=member(client,db)
    workspace=provision_workflow_workspace(db,publisher)
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Member'))
    team=PMSWorkspaceTeam(workspace_id=workspace.id,name='Policy reviewers',alias='policy-reviewers');db.add(team);db.commit()
    draft,_=preview(client,owner,definition={'title':'Team review','text':TEXT,'module':'CRM','workspace_id':workspace.id},audience={'kind':'workspace_teams','team_ids':[team.id]});publish(client,owner,draft)
    assert memories(client,h,workspace_id=workspace.id)==[]
    membership=PMSWorkspaceTeamMember(team_id=team.id,user_id=user.id);db.add(membership);db.commit()
    assert memories(client,h,workspace_id=workspace.id)[0]['text']==TEXT
    assert memories(client,h)==[]
    db.delete(membership);db.commit();assert memories(client,h,workspace_id=workspace.id)==[]
    assert client.get(ROOT,headers=owner,params={'module':'HRMS','workspace_id':workspace.id}).json()['items']==[]


@pytest.mark.parametrize('text',['AQ.'+'X'*32,'api_key: private-key','salary: 90000'])
def test_organization_memory_rejects_credentials_and_sensitive_records(client,db,text):
    owner,_,_,_=setup_suite(client,db)
    assert client.post(ROOT+'/preview',headers=owner,json={'request_key':str(uuid4()),'definition':{'title':'Invalid policy','text':text},'audience':{'kind':'organization'}}).status_code==422
