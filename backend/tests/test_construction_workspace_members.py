""" run only after team helper/source/common121 integration approval."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import inspect

from app.models.user import User, Permission
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.srm.industry_models import IndustryRecord
from app.business_packs import construction_workspace_members as team
from tests.test_business_pack_construction import construction,scenario,catalog,directory_identity
from tests.test_construction_planning import selected
from tests.test_construction_definition import project_body,task_body
from tests.test_construction_workspaces import post,ROOT


@pytest.fixture
def workspace(client,db,construction,catalog):
    headers = {**catalog[0],'X-Suite-Pack-Context':str(construction[2])}
    created = post(client,headers,'/workspace-definitions',{'request_id':str(uuid4()),'name':'Native team '+uuid4().hex[:8]})
    return {'case':construction,'headers':headers,'id':created['id']}


def person(db,case,*,role='site_engineer',actions=('view',),pack='construction'):
    from app.access.models import AccessPolicy
    from app.business_packs.models import PackContext
    from tests.test_business_pack_http_integration import native_actor,grant
    headers,user = native_actor(db,case[1])
    if db.query(Permission).filter_by(name='pms_view').first() is None:
        db.add(Permission(name='pms_view',module='project_management',description='Native PMS view'))
    policy = db.query(AccessPolicy).filter_by(company_id=1,user_id=user.id).one()
    policy.grants = {**policy.grants,'project_management':{'enabled':True,'permissions':['pms_view'],
        'actions':list(actions),'scope':'organization'}}
    db.commit()
    context,_ = grant(db,user,case[1],pack,role,db.get(PackContext,case[2]) if pack == 'construction' else None)
    return {**headers,'X-Suite-Pack-Context':str(context.id)},user


def command(uid,role='Member'):
    return {'request_id':str(uuid4()),'user_id':uid,'role':role}


def test_real_workspace_team_bootstrap_to_independent_boq_resource_schedule_and_actuals(client,db,workspace):
    case,headers,wid = workspace['case'],workspace['headers'],workspace['id']
    _,engineer = person(db,case)
    reviewer_headers,reviewer = person(db,case,role='project_manager',actions=('view','create','edit','approve'))
    options = client.get(ROOT+f'/workspaces/{wid}/member-options',headers=headers)
    assert options.status_code == 200,options.text
    assert {engineer.id,reviewer.id} <= {row['id'] for row in options.json()['items']}
    assert not db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.user_id.in_([engineer.id,reviewer.id]),PMSWorkspaceMember.workspace_id == wid).count()
    first = command(engineer.id)
    member = post(client,headers,f'/workspaces/{wid}/member-definitions',first)
    assert post(client,headers,f'/workspaces/{wid}/member-definitions',first) == member
    admin = post(client,headers,f'/workspaces/{wid}/member-definitions',command(reviewer.id,'Admin'))
    assert member['role'] == 'Member' and admin['role'] == 'Admin'
    assert db.query(Notification).filter_by(user_id=engineer.id,event_type='workspace.member_added').count() == 1
    notice = db.query(Notification).filter_by(user_id=engineer.id,event_type='workspace.member_added').one()
    assert notice.company_id == 1
    assert db.query(AuditLog).filter_by(entity_type='user',entity_id=engineer.id,action='PMS_WORKSPACE_ADDED',workspace_id=wid).count() == 1
    site = post(client,headers,'/site-projects',project_body({'workspace':wid}))
    boq = post(client,headers,'/boq',{'request_id':str(uuid4()),'title':'Actual team scope','project_id':site['id'],
        'code':'TEAM','unit':'m3','quantity':'1','unit_rate':'500','tax_rate':'0'})
    post(client,reviewer_headers,f'/records/{boq["id"]}/transition',{'expected_revision':1,'status':'approved'},200)
    task = post(client,headers,f'/projects/{site["id"]}/wbs-tasks',task_body(assignee_user_ids=[engineer.id]))
    path = f'/api/v1/project-management/projects/{site["id"]}'
    preview = client.post(path+'/schedule-preview',headers=headers,json={'level_resources':True})
    assert preview.status_code == 200,preview.text
    assert engineer.id in {row['user_id'] for row in preview.json()['resource_allocations']}
    applied = client.post(path+'/schedule-apply',headers=headers,json={'level_resources':True,'expected_revision':preview.json()['revision']})
    assert applied.status_code == 200,applied.text
    sources = client.get(ROOT+f'/projects/{site["id"]}/planning-tasks',headers=headers)
    assert sources.status_code == 200,sources.text
    source = next(row for row in sources.json()['items'] if row['id'] == task['id'])
    done = post(client,headers,f'/projects/{site["id"]}/task-actuals/{task["id"]}',{
        'request_id':str(uuid4()),'expected_updated_at':source['updated_at'],'status':'Done','actual_hours':'16'},200)
    assert done['completed_at']


def test_team_native_actor_is_genuine_and_target_orm_stays_self_only(db,workspace,monkeypatch):
    from app.apps.project_management import workspaces as native
    case,wid = workspace['case'],workspace['id']
    _,target = person(db,case)
    target_id,target_email = target.id,target.email
    original,checked = native.add_workspace_member_operation,[]
    def instrument(workspace_id,data,reader,actor,**kwargs):
        assert type(actor) is User and inspect(actor).session is reader
        assert actor.id == case[0].id
        assert reader.query(User).filter(User.id != actor.id).count() == 0
        reference = reader.get(User,target_id)
        assert type(reference) is team.TargetReference and inspect(reference,raiseerr=False) is None
        assert (reference.id,reference.email,reference.is_active,reference.organization_id) == (target_id,target_email,True,1)
        checked.append(True)
        return original(workspace_id,data,reader,actor,**kwargs)
    with selected(db,case) as actor,monkeypatch.context() as fault:
        fault.setattr(native,'add_workspace_member_operation',instrument)
        team.create(wid,team.MemberInput(request_id=uuid4(),user_id=target_id),db,actor)
    assert checked


def test_native_admin_cannot_appoint_another_admin_but_owner_can(client,db,workspace):
    case,headers,wid = workspace['case'],workspace['headers'],workspace['id']
    admin_headers,admin = person(db,case,role='project_manager',actions=('view','create','edit','approve'))
    _,target = person(db,case)
    post(client,headers,f'/workspaces/{wid}/member-definitions',command(admin.id,'Admin'))
    post(client,admin_headers,f'/workspaces/{wid}/member-definitions',command(target.id,'Admin'),403)
    post(client,headers,f'/workspaces/{wid}/member-definitions',command(target.id,'Admin'))


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef')])
def test_target_without_own_construction_grant_cannot_join(client,db,workspace,pack,role):
    _,target = person(db,workspace['case'],pack=pack,role=role)
    post(client,workspace['headers'],f'/workspaces/{workspace["id"]}/member-definitions',command(target.id),404)
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace['id'],user_id=target.id).count() == 0


def test_team_native_failure_rolls_back_member_audit_notice_and_same_uuid_retries(db,workspace,monkeypatch):
    from app.apps.project_management import workspaces as native
    case,wid = workspace['case'],workspace['id']
    _,target = person(db,case)
    target_id = target.id
    data = team.MemberInput(request_id=uuid4(),user_id=target_id)
    original = native.add_workspace_member_operation
    def late(*args,**kwargs):
        original(*args,**kwargs)
        raise HTTPException(409,'Native team add failed after its genuine outputs')
    with selected(db,case) as actor:
        with monkeypatch.context() as fault:
            fault.setattr(native,'add_workspace_member_operation',late)
            with pytest.raises(HTTPException) as failed:
                team.create(wid,data,db,actor)
            assert failed.value.status_code == 409
        assert not db.query(IndustryRecord).filter_by(kind='workspace_member_definition').count()
        result = team.create(wid,data,db,actor)
        assert result['user_id'] == target_id
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=wid,user_id=target_id).count() == 1
    assert db.query(Notification).filter_by(user_id=target_id,event_type='workspace.member_added').count() == 1


def test_owner_role_and_unregistered_target_fields_are_not_accepted(client,workspace):
    data = command(999,'Member')
    post(client,workspace['headers'],f'/workspaces/{workspace["id"]}/member-definitions',{**data,'role':'Owner'},422)
    post(client,workspace['headers'],f'/workspaces/{workspace["id"]}/member-definitions',{**data,'email':'new@example.com'},422)


def test_native_target_reference_cannot_read_another_identity_or_unregistered_model(db,workspace,monkeypatch):
    from app.apps.project_management import workspaces as native
    from app.models.employee import Employee
    from app.apps.crm.models import CRMDeal
    case,wid = workspace['case'],workspace['id']
    _,target = person(db,case)
    target_id = target.id
    original = native.add_workspace_member_operation
    def unreviewed(workspace_id,data,reader,actor,**kwargs):
        assert reader.get(User,target_id+1000000) is None
        assert reader.query(Employee).filter(Employee.user_id != actor.id).count() == 0
        reader.query(CRMDeal).all()
        return original(workspace_id,data,reader,actor,**kwargs)
    with selected(db,case) as actor,monkeypatch.context() as fault:
        fault.setattr(native,'add_workspace_member_operation',unreviewed)
        with pytest.raises(HTTPException) as denied:
            team.create(wid,team.MemberInput(request_id=uuid4(),user_id=target_id),db,actor)
        assert denied.value.status_code == 403
