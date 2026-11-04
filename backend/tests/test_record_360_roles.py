from datetime import date
from app.models.company import Branch
from app.models.user import Role, Permission
from app.branches.models import BranchOwnership
from app.apps.project_management.models import PMSProject, PMSTask, PMSProjectMember
from app.apps.crm.models import CRMContact
from app.apps.project_management.task_record_links import link_record
from tests.test_record_360 import seeded
from tests.test_pms_workspaces import account, middleware_database
from tests.tenant_test_utils import assign_company
from test_identity_utils import own_workflow_records, attach_workflow_branch


def test_selected_branch_limits_feed_counts_cursors_and_link_targets(client,db):
    actor,headers,company,_,project,task,_=seeded(db)
    branch_a=db.query(Branch).filter_by(company_id=1).first()
    branch_b=Branch(company_id=1,name='Private branch',code='R360-PRIVATE');db.add(branch_b);db.flush()
    extra=PMSTask(project_id=project.id,task_key='SECOND',title='Second visible',due_date=date.today())
    contact=CRMContact(organization_id=1,company_id=company.id,first_name='Branch',full_name='Branch A contact')
    db.add_all([extra,contact]);own_workflow_records(db,extra,contact)
    private_project=PMSProject(organization_id=1,branch_id=branch_b.id,project_key='PRIVATE',name='Private delivery')
    db.add(private_project);db.flush()
    private_task=PMSTask(project_id=private_project.id,task_key='PRIVATE-1',title='Private branch task',due_date=date.today())
    db.add(private_task);db.flush()
    for row in (private_project,private_task):
        db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch_b.id,source='explicit-test-fixture'))
    db.commit()
    ha={**headers,'X-Suite-Branch':str(branch_a.id)};hb={**headers,'X-Suite-Branch':str(branch_b.id)}
    url='/api/v1/record-360/work/queue/items'
    params={'view':'all','source_filter':'pms_task','per_page':1,'cursor_mode':True}
    first=client.get(url,params=params,headers=ha)
    assert first.status_code==200,first.text
    assert first.json()['next_cursor']
    private=client.get(url,params={**params,'cursor_mode':False},headers=hb)
    assert private.status_code==200,private.text
    assert private.json()['total']==1 and private.json()['items'][0]['title']=='Private branch task'
    replay=client.get(url,params={**params,'cursor':first.json()['next_cursor']},headers=hb)
    assert replay.status_code==422,replay.text
    root=f'/api/v1/project-management/task-workspace/tasks/{private_task.id}'
    denied=client.post(root+'/crm-links',json={'kind':'contact','record_id':contact.id},headers=hb)
    assert denied.status_code in (403,404),denied.text
    choices=client.get(root+'/crm-link-options',params={'kind':'contact'},headers=hb)
    assert choices.status_code==200,choices.text
    assert all(row['id']!=contact.id for row in choices.json()['items'])


def test_viewer_http_can_read_visible_links_but_cannot_change_them(client,db):
    actor,headers,company,_,project,task,_=seeded(db)
    viewer,vh=account(db,'record360-real-viewer@test.com');assign_company(db,viewer,1)
    permission=db.query(Permission).filter_by(name='crm_view').first() or Permission(name='crm_view',module='crm')
    viewer.role=Role(name='record360_task_viewer',permissions=[permission])
    member=PMSProjectMember(project_id=project.id,user_id=viewer.id,role='Viewer')
    contact=CRMContact(organization_id=1,first_name='Visible',full_name='Visible contact',company_id=company.id,owner_user_id=viewer.id,created_by_user_id=viewer.id)
    db.add_all([member,contact]);own_workflow_records(db,member,contact);db.commit()
    root=f'/api/v1/project-management/task-workspace/tasks/{task.id}'
    linked=client.post(root+'/crm-links',json={'kind':'contact','record_id':contact.id},headers=headers)
    assert linked.status_code==200,linked.text
    link=linked.json()
    result=client.get(root+'/crm-links',headers=vh)
    assert result.status_code==200,result.text
    assert result.json()['can_manage'] is False
    assert result.json()['items'][0]['name']=='Visible contact'
    assert client.post(root+'/crm-links',json={'kind':'contact','record_id':contact.id},headers=vh).status_code==403
    assert client.delete(root+f'/crm-links/{link["id"]}',headers=vh).status_code==403
    assert client.get(root+'/crm-link-options',params={'kind':'contact'},headers=vh).status_code==403


def test_other_tenant_cannot_open_or_link_task(client,db):
    actor,headers,company,_,project,task,_=seeded(db)
    foreign,fh=account(db,'record360-foreign@test.com');assign_company(db,foreign,2);attach_workflow_branch(db,foreign,2);db.commit()
    result=client.get(f'/api/v1/record-360/task/{task.id}',params={'source':'project_management'},headers=fh)
    assert result.status_code in (403,404),result.text
    assert client.get(f'/api/v1/project-management/task-workspace/tasks/{task.id}/crm-links',headers=fh).status_code in (403,404)
