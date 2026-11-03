"""Regression coverage for the eleven issues in the user's screenshot."""
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import pytest
from app.models.employee import Employee
from app.models.user import User
from app.models.attendance import Attendance

@pytest.fixture
def actor(db):
    u=User(email='issue-audit@example.test',hashed_password='unused',is_active=True,is_superuser=True)
    db.add(u);db.flush();return u

def person(db,code,**values):
    e=Employee(employee_id=code,first_name=code,last_name='Audit',date_of_joining=date(2026,1,1),status='Active',**values)
    db.add(e);db.flush();return e

def test_city_options_deduplicate_case_and_whitespace(db,actor):
    from app.api.v1.employees import employee_filter_options
    from app.core.employee_directory import apply_employee_directory_filters
    for i,city in enumerate([' Chennai ','CHENNAI','chennai']):person(db,f'CITY-{i}',present_city=city)
    choices=employee_filter_options(db,actor)['city']
    assert len(choices)==1 and choices[0].casefold()=='chennai'
    rows=apply_employee_directory_filters(db.query(Employee),{'city':choices[0]}).all()
    assert len(rows)==3

def test_attendance_exact_counts_filters_and_previous_dates(db,actor):
    from app.api.v1.attendance import attendance_register
    yesterday=date(2026,11,2)
    for i,status in enumerate(['Present','WFH','Half-day','Absent',None]):
        e=person(db,f'ATT-AUDIT-{i}')
        if status:db.add(Attendance(employee_id=e.id,attendance_date=yesterday,status=status))
    person(db,'FUTURE',date_of_birth=None).date_of_joining=date(2026,11,3)
    db.flush()
    def register(status=None):return attendance_register(work_date=yesterday,search=None,status=status,branch_id=None,department_id=None,db=db,current_user=actor)
    all_rows=register()
    assert all_rows['present']==1 and all_rows['wfh']==1 and all_rows['half_day']==1
    assert all_rows['absent']==1 and all_rows['not_marked']==1 and all_rows['cohort_total']==5
    assert all_rows['credited_present']==Decimal('2.5')
    for status in ['Present','Absent','WFH','Not marked']:
        result=register(status)
        assert result['total']==1 and result['items'][0]['status']==status
        assert result['date']==yesterday

def test_open_execution_counts_are_shared_and_exclude_cancelled(db,actor):
    from app.apps.project_management.models import PMSProject,PMSTask,PMSTaskAssignee
    from app.apps.interns_hub.pms_adapter import summary
    from app.apps.project_management.work_api import my_assignments
    e=person(db,'TASK-AUDIT',user_id=actor.id,employment_type='Intern')
    p=PMSProject(organization_id=1,name='Task audit',project_key='TASK-AUDIT');db.add(p);db.flush()
    for i,status in enumerate(['To Do','In Progress','Done','Cancelled','Rejected']):
        t=PMSTask(project_id=p.id,title=f'Work {i}',task_key=f'AUDIT-{i}',status=status)
        db.add(t);db.flush();db.add(PMSTaskAssignee(task_id=t.id,user_id=actor.id,execution_status=status))
    db.flush()
    hr=summary(db,e,date(2026,11,3))
    pms=my_assignments(page=1,per_page=50,user=actor,db=db)
    assert hr['open_tasks']==pms['summary']['open_tasks']==2
    assert hr['completed']==pms['summary']['completed']==1

def test_empty_batches_hidden_and_reactivation_keeps_history(db,actor):
    from app.apps.interns_hub.management_api import batches,membership,MembershipInput
    from app.apps.interns_hub.management_models import InternBatch,InternBatchMembership
    e=person(db,'BATCH-AUDIT',user_id=actor.id,employment_type='Intern')
    from app.models.company import Company,Branch,Department
    from app.apps.project_management.models import PMSProject
    if not db.get(Company,1):db.add(Company(id=1,name='Audit company'))
    branch=Branch(company_id=1,name='Audit branch');db.add(branch);db.flush()
    department=Department(branch_id=branch.id,name='Audit department');db.add(department)
    project=PMSProject(organization_id=1,name='Batch project',project_key='BATCH-AUDIT');db.add(project);db.flush()

    def batch(code):
        row=InternBatch(department_id=department.id,project_id=project.id,organization_id=1,name=code,code=code,manager_user_id=actor.id,mentor_user_id=actor.id,start_date=date(2026,1,1),end_date=date(2026,12,31),capacity=10,status='Active')
        db.add(row);db.flush();return row
    occupied=batch('OCCUPIED');empty=batch('EMPTY')
    db.add(InternBatchMembership(batch_id=occupied.id,employee_id=e.id,status='Active',active_slot=1,assigned_by=actor.id));db.flush()
    db.connection().execute(InternBatchMembership.__table__.insert().values(batch_id=occupied.id,employee_id=e.id,status='Active',active_slot=None,assigned_by=actor.id))
    db.flush()
    disabled=User(email='disabled-batch@example.test',hashed_password='unused',is_active=False)
    db.add(disabled);db.flush()
    disabled_person=person(db,'DISABLED-BATCH',user_id=disabled.id,employment_type='Intern')
    db.add(InternBatchMembership(batch_id=occupied.id,employee_id=disabled_person.id,status='Active',active_slot=1,assigned_by=actor.id));db.flush()
    def listing(hide):return batches(mentor_id=None,date_from=None,date_to=None,batch_type='',search='',status='',hide_empty=hide,department_id=None,page=1,per_page=50,user=actor,db=db)
    assert [r['id'] for r in listing(True)['items']]==[occupied.id]
    assert listing(False)['total']==2
    assert listing(True)['items'][0]['members']==1
    from app.apps.interns_hub.management_api import batch_analytics
    assert next(row for row in batch_analytics(f={},user=actor,db=db) if row['id']==occupied.id)['members']==1
    membership(occupied.id,MembershipInput(employee_ids=[e.id],action='deactivate'),actor,db)
    assert listing(True)['total']==0
    membership(occupied.id,MembershipInput(employee_ids=[e.id],action='reactivate'),actor,db)
    rows=db.query(InternBatchMembership).filter_by(batch_id=occupied.id).all()
    assert {r.status for r in rows}=={'Inactive','Active'}
    assert listing(True)['items'][0]['members']==1

def test_name_save_completeness_and_approval_preserve_permissions(db):
    from tests.test_shared_profiles import account
    from app.common.services.profiles import serialize_profile,update_profile,apply_approved_profile
    user,employee=account(db,'reported-profile',intern=True)
    before=serialize_profile(db,user,user)
    changed=update_profile(db,user,user,{'first_name':'Updated','bio':'Profile details','skills':['Python']},version=before['version'])
    assert changed['profile']['completeness']>before['completeness']
    assert changed['pendingRequestId'] is not None
    assert employee.first_name=='Profile'
    apply_approved_profile(db,employee,{'first_name':'Updated'})
    assert serialize_profile(db,user,user)['displayName'].startswith('Updated')


def test_active_member_count_separates_registered_and_disabled_people(db,actor):
    from app.apps.interns_hub.management_api import dashboard
    person(db,'MEMBER-ACTIVE',user_id=actor.id,employment_type='Intern')
    inactive=User(email='disabled-member@example.test',hashed_password='unused',is_active=False)
    db.add(inactive);db.flush()
    person(db,'MEMBER-DISABLED',user_id=inactive.id,employment_type='Intern')
    person(db,'MEMBER-NO-LOGIN',employment_type='Intern')
    result=dashboard(f={},user=actor,db=db)
    assert result['total_interns']==3 and result['member_count']==1

def test_workspace_overview_loads_real_projects_tasks_and_members(client,db,superuser_headers):
    from tests.tenant_test_utils import assign_company
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember,PMSProject,PMSTask
    admin=db.query(User).filter_by(email='testadmin@test.com').one();assign_company(db,admin,1)
    branch=Branch(company_id=1,name='Workspace audit',code='WSAUDIT');db.add(branch);db.flush()
    w=PMSWorkspace(organization_id=1,name='Actual workspace');db.add(w);db.flush()
    m=PMSWorkspaceMember(workspace_id=w.id,user_id=admin.id,role='Owner');db.add(m)
    p=PMSProject(workspace_id=w.id,organization_id=1,name='Actual project',project_key='WSAUDIT',manager_user_id=admin.id);db.add(p);db.flush()
    t=PMSTask(project_id=p.id,title='Actual task',task_key='WSAUDIT-1',status='To Do');db.add(t);db.flush()
    for row in [w,m,p,t]:db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch.id,source='test'))
    db.commit()
    headers={**superuser_headers,'X-Suite-Branch':str(branch.id)}
    response=client.get(f'/api/v1/project-management/workspaces/{w.id}/overview',headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['projects'][0]['id']==p.id and response.json()['tasks'][0]['id']==t.id
    members=client.get(f'/api/v1/project-management/workspaces/{w.id}/members',headers=headers)
    assert members.status_code==200,members.text
    assert members.json()[0]['user_id']==admin.id
