import pytest
from sqlalchemy import update,delete
from app.ai_agents import security
from app.ai_operator.assistant_models import AssistantConversation
from app.apps.project_management.models import PMSSavedFilter,PMSProject
from tests.test_saved_view_actions import setup
from tests.test_suite_workspace import say,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def native_view(client,h,project,shared=False):
    response=client.post('/api/v1/project-management/saved-views',headers=h,json={
        'name':'Synthetic history view','project_id':project,'entity_type':'task','view_type':'task_list',
        'filters':{'projectId':str(project),'status':'Blocked'},'visibility':'workspace' if shared else 'private','is_shared':shared})
    assert response.status_code==201
    return response.json()['id']


def test_private_view_edits_and_deletion_preserve_existing_conversation(client,db):
    h,user,project,workspace,chat=setup(client,db);view=native_view(client,h,project)
    draft=say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    assert draft['status']=='needs_clarification'
    original=db.get(AssistantConversation,chat).security_context.copy()
    changed=client.patch(f'/api/v1/project-management/saved-views/{view}',headers=h,json={'name':'Renamed filter','filters':{'status':'Done'}})
    assert changed.status_code==200
    assert client.delete(f'/api/v1/project-management/saved-views/{view}',headers=h).status_code==200
    assert db.get(AssistantConversation,chat).security_context==original
    restored=client.get(ROOT+f'/conversations/{chat}',headers=h)
    assert restored.status_code==200 and restored.json()['runs'][0]['id']==draft['id']
    assert client.get(ROOT+f'/runs/{draft["id"]}',headers=h).status_code==200
    assert client.delete(ROOT+f'/conversations/{chat}',headers=h).status_code==200


def test_shared_view_deletion_still_invalidates_cached_history(client,db):
    h,user,project,workspace,chat=setup(client,db);view=native_view(client,h,project,True)
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    assert client.delete(f'/api/v1/project-management/saved-views/{view}',headers=h).status_code==200
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404


def test_saved_view_sharing_changes_invalidate_cached_history(client,db):
    h,user,project,workspace,chat=setup(client,db);view=native_view(client,h,project)
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    assert client.patch(f'/api/v1/project-management/saved-views/{view}',headers=h,json={'visibility':'workspace','is_shared':True}).status_code==200
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404


def test_native_project_deletion_still_invalidates_history(client,db):
    h,user,project,workspace,chat=setup(client,db)
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    assert client.delete(f'/api/v1/project-management/projects/{project}',headers=h).status_code==200
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404


@pytest.mark.parametrize('field',['user_id','organization_id','project_id'])
def test_saved_view_scope_changes_revoke_previous_owner_history(client,db,field):
    from app.models.company import Company
    h,user,project,workspace,chat=setup(client,db);view=native_view(client,h,project)
    if field=='organization_id':
        if not db.get(Company,2):db.add(Company(id=2,name='Synthetic destination company'));db.commit()
        destination=2
    elif field=='project_id':destination=None
    else:destination=None
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    row=db.get(PMSSavedFilter,view);setattr(row,field,destination);db.commit()
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404


@pytest.mark.parametrize('bulk',['update','delete'])
def test_bulk_saved_view_scope_changes_still_invalidate_history(client,db,bulk):
    h,user,project,workspace,chat=setup(client,db);view=native_view(client,h,project)
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    # Reproduce the request-bound bulk ORM path used by native module services.
    db.info['ai_request_context']={'user_id':user.id,'company_id':1}
    before=db.query(AssistantConversation).execution_options(ai_owner_control=True).filter_by(id=chat).first()
    assert before is not None and db.info['ai_request_context'].get('control_fingerprint')
    statement=update(PMSSavedFilter).where(PMSSavedFilter.id==view).values(visibility='workspace',is_shared=True) if bulk=='update' else delete(PMSSavedFilter).where(PMSSavedFilter.id==view)
    db.execute(statement);db.commit()
    hidden=db.query(AssistantConversation).execution_options(ai_owner_control=True).filter_by(id=chat).first()
    db.info.pop('ai_request_context',None)
    assert hidden is None  # Even a second read in the same request must fail closed.
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404


def test_background_workspace_role_change_invalidates_actual_parent_company(client,db):
    from app.models.company import Company
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    from app.shared.models import ServicePolicy
    h,user,project,workspace,chat=setup(client,db)
    if not db.get(Company,2):db.add(Company(id=2,name='Synthetic parent company'));db.commit()
    other=PMSWorkspace(name='Synthetic parent workspace',organization_id=2);db.add(other);db.flush()
    member=PMSWorkspaceMember(workspace_id=other.id,user_id=user.id,role='Owner');db.add(member);db.commit()
    member.role='Viewer';db.commit()
    epoch=db.query(ServicePolicy).filter_by(kind='ai_acl_epoch',scope_key='company:2:ai_acl_epoch').one()
    assert epoch.version>=1


def test_task_reparenting_invalidates_cached_history_of_both_companies(client,db):
    from app.models.company import Company
    from app.apps.project_management.models import PMSWorkspace,PMSTask
    from app.shared.models import ServicePolicy
    h,user,project,workspace,chat=setup(client,db)
    if not db.get(Company,2):db.add(Company(id=2,name='Synthetic destination'));db.commit()
    other=PMSWorkspace(name='Synthetic destination workspace',organization_id=2);db.add(other);db.flush()
    destination=PMSProject(name='Synthetic destination project',project_key='DEST',workspace_id=other.id,organization_id=2,owner_user_id=user.id)
    db.add(destination);db.commit()
    say(client,h,chat,'Create a task',module='CRM',workspace_id=workspace)
    task=db.query(PMSTask).filter_by(project_id=project).first();task.project_id=destination.id;db.commit()
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==404
    assert db.query(ServicePolicy).filter_by(kind='ai_acl_epoch',scope_key='company:2:ai_acl_epoch').one().version>=1
