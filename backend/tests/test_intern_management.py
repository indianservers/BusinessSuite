from datetime import timedelta
from uuid import uuid4
import pytest
from tests.test_interns_hub import interns
from app.apps.interns_hub.router import today
from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview
from app.apps.interns_hub.management_models import InternBatchMembership, InternDistribution
from app.models.user import User

ROOT='/api/v1/interns-hub/management'
PMS='/api/v1/project-management'

@pytest.fixture
def program(client,db,interns,superuser_headers):
    admin=db.query(User).filter_by(email='testadmin@test.com').one()
    project=PMSProject(name='Intern delivery',project_key='IDEL',organization_id=1,manager_user_id=admin.id)
    db.add(project);db.commit()
    def batch(code,capacity=10):
        data=dict(name='Intern '+code,code=code,department_id=interns[0][0].department_id,manager_user_id=admin.id,mentor_user_id=admin.id,project_id=project.id,start_date=str(today()-timedelta(days=30)),end_date=str(today()+timedelta(days=60)),capacity=capacity,policy={'weights':{'quality':40,'timeliness':20,'reports':15,'completion':15,'communication':10},'completion':{'minimum_days':0,'minimum_tasks':1,'minimum_reports_percent':0}})
        r=client.post(ROOT+'/batches',headers=superuser_headers,json=data);assert r.status_code==201,r.text
        bid=r.json()['id']
        for status in ['Upcoming','Active']:
            r=client.post(f'{ROOT}/batches/{bid}/transition',headers=superuser_headers,json={'status':status});assert r.status_code==200,r.text
        return bid
    first,second=batch('A'),batch('B')
    for bid in [first,second]:
        r=client.post(f'{ROOT}/batches/{bid}/members',headers=superuser_headers,json={'employee_ids':[e.id for e,_,_ in interns]});assert r.status_code==200,r.text
    return dict(admin=admin,project=project,batches=[first,second],headers=superuser_headers,interns=interns)

def publish(client,p,**overrides):
    body=dict(project_id=p['project'].id,title='Shared campaign brief',description='One authoritative description',target_type='batches',batch_ids=p['batches'],reviewer_user_id=p['admin'].id,due_date=str(today()),idempotency_key=str(uuid4()))
    body.update(overrides)
    r=client.post(ROOT+'/distributions',headers=p['headers'],json=body)
    assert r.status_code==201,r.text
    return r.json(),body

def test_shared_task_deduplication_and_independent_execution(client,db,program):
    p=program;job,body=publish(client,p)
    assert job['status']=='Completed' and job['cursor']==2
    again=client.post(ROOT+'/distributions',headers=p['headers'],json=body)
    assert again.json()['id']==job['id']
    assert client.post(ROOT+'/distributions',headers=p['headers'],json={**body,'title':'Changed'}).status_code==409
    assert db.query(PMSTask).count()==1
    assert db.query(PMSTaskAssignee).count()==2
    e,h,_=p['interns'][0]
    started=client.post(f"/api/v1/interns-hub/tasks/{job['task_id']}/start",headers=h)
    assert started.status_code==200,started.text
    statuses={a.user_id:a.execution_status for a in db.query(PMSTaskAssignee)}
    assert statuses[e.user_id]=='In Progress'
    assert statuses[p['interns'][1][0].user_id]=='To Do'
    # Ordinary PMS editing preserves execution metadata and membership history.
    task=db.get(PMSTask,job['task_id']);task.assignee_user_ids=[];db.commit()
    assert db.query(PMSTaskAssignee).count()==2
    for endpoint in ['/dashboard','/interns','/batches','/options','/batch-analytics','/distributions','/reports','/reviews']:
        r=client.get(ROOT+endpoint,headers=p['headers']);assert r.status_code==200,(endpoint,r.text)

def test_one_review_history_revision_and_completion(client,db,program):
    p=program;job,_=publish(client,p);tid=job['task_id'];e,h,_=p['interns'][0]
    def submit(notes):
        r=client.post(f'/api/v1/interns-hub/tasks/{tid}/submissions',headers=h,json={'notes':notes,'confirmed':True});assert r.status_code==201,r.text
        return r.json()['id']
    sid=submit('First version')
    decision={'status':'Needs Revision','score':50,'feedback':'Please improve the layout','inspected':True}
    assert client.post(f'{PMS}/work/submissions/{sid}/review',headers=p['headers'],json={**decision,'inspected':False}).status_code==422
    r=client.post(f'{PMS}/work/submissions/{sid}/review',headers=p['headers'],json=decision);assert r.status_code==200,r.text
    assert client.post(f'/api/v1/interns-hub/admin/submissions/{sid}/review',headers=p['headers'],json=decision).status_code==409
    newer=submit('Improved version')
    r=client.post(f'/api/v1/interns-hub/admin/submissions/{newer}/review',headers=p['headers'],json={**decision,'status':'Approved','score':90});assert r.status_code==200,r.text
    assert db.query(PMSWorkSubmission).count()==2 and db.query(PMSWorkReview).count()==2
    score=client.get(ROOT+'/interns',headers=p['headers'],params={'batch_id':p['batches'][0]}).json()['items'][0]
    assert score['parts']['quality']==90 and score['accepted']==1 and score['eligible']
    assert client.get(ROOT+'/dashboard',headers=p['headers']).json()['average_score']==90
    assert db.get(PMSTask,tid).status!='Done' # second intern remains independent
    r=client.post(ROOT+'/completions',headers=p['headers'],json={'batch_id':p['batches'][0],'employee_id':e.id,'decision':'Approved','note':'Program requirements verified'})
    assert r.status_code==200,r.text
    cid=r.json()['id']
    cert=client.post(f'{ROOT}/completions/{cid}/certificate',headers=p['headers']);assert cert.status_code==200,cert.text
    assert cert.json()['document_certificate_id'] and cert.json()['verification_id']
    assert client.post(f'{ROOT}/completions/{cid}/certificate',headers=p['headers']).json()['id']==cert.json()['id']
    other=p['interns'][1][0]
    assert client.post(ROOT+'/completions',headers=p['headers'],json={'batch_id':p['batches'][0],'employee_id':other.id,'decision':'Approved','note':'Cannot bypass PMS'}).status_code==409

def test_capacity_transfers_and_history(client,db,program):
    p=program;eid=p['interns'][0][0].id;a,b=p['batches']
    for action in ['remove','reactivate']:
        r=client.post(f'{ROOT}/batches/{a}/members',headers=p['headers'],json={'employee_ids':[eid],'action':action,'reason':'Program adjustment'});assert r.status_code==200,r.text
    r=client.post(f'{ROOT}/batches/{a}/members',headers=p['headers'],json={'employee_ids':[eid],'action':'transfer','target_batch_id':b,'reason':'Changed specialization'});assert r.status_code==200,r.text
    history=client.get(f'{ROOT}/memberships/{eid}',headers=p['headers']).json()
    assert len(history)==3 and any(m['status']=='Transferred' for m in history)
    assert db.query(InternBatchMembership).filter_by(employee_id=eid,status='Active').count()==1

def test_portal_and_tenant_boundaries(client,db,program):
    p=program
    for path in ['/access','/interns','/dashboard','/batches','/reviews']:
        assert client.get(ROOT+path,headers=p['interns'][0][1]).status_code==403
    alien=PMSProject(name='Other customer',project_key='OTHER',organization_id=999)
    db.add(alien);db.commit()
    body=dict(project_id=alien.id,title='Invalid',description='No cross tenant',target_type='all',reviewer_user_id=p['admin'].id,due_date=str(today()),idempotency_key=str(uuid4()))
    assert client.post(ROOT+'/distributions',headers=p['headers'],json=body).status_code in {403,404}
    assert client.get(ROOT+f'/projects/{alien.id}/tasks',headers=p['headers']).status_code in {403,404}

def test_chunk_retry_and_schedule_are_idempotent(client,db,program):
    from app.apps.interns_hub.distribution import publish as publish_operation, process_job, scheduled_tick
    from app.apps.interns_hub.management_models import InternTaskSchedule
    p=program
    _,body=publish(client,p)
    body['idempotency_key']=str(uuid4());body['due_date']=today();body['recurrence']='daily';body['recurrence_until']=today()+timedelta(days=2)
    job=publish_operation(db,p['admin'],body,process=False)
    process_job(db,job.id,chunk_size=1)
    assert db.get(InternDistribution,job.id).status=='Pending'
    process_job(db,job.id,chunk_size=1);process_job(db,job.id,chunk_size=1)
    assert db.query(PMSTaskAssignee).filter_by(task_id=job.task_id).count()==2
    scheduled_tick(db,today()+timedelta(days=1));count=db.query(PMSTask).count()
    scheduled_tick(db,today()+timedelta(days=1));assert db.query(PMSTask).count()==count
    assert db.query(InternTaskSchedule).count()==1

def test_pms_viewer_and_hr_manager_cannot_bypass_review(client,db,program):
    from app.models.user import Role,Permission
    from app.models.employee import Employee
    from app.core.security import get_password_hash
    from app.apps.project_management.models import PMSProjectMember
    p=program;job,_=publish(client,p);e,h,_=p['interns'][0]
    submission=client.post(f"/api/v1/interns-hub/tasks/{job['task_id']}/submissions",headers=h,json={'notes':'Evidence for a genuine PMS reviewer','confirmed':True}).json()
    permission=Permission(name='employee_view');role=Role(name='manager',permissions=[permission]);db.add(role);db.flush()
    viewer=User(email='scoped-manager@example.com',hashed_password=get_password_hash('Manager@123456'),role_id=role.id,is_active=True);db.add(viewer);db.flush()
    manager=Employee(employee_id='SCOPED-MGR',first_name='Scoped',last_name='Manager',date_of_joining=today(),user_id=viewer.id,branch_id=e.branch_id,department_id=e.department_id);db.add(manager);db.flush();e.reporting_manager_id=manager.id
    db.add(PMSProjectMember(project_id=p['project'].id,user_id=viewer.id,role='Viewer'));db.commit()
    login=client.post('/api/v1/auth/login',json={'email':viewer.email,'password':'Manager@123456','module':'hrms'});assert login.status_code==200,login.text
    headers={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.get(ROOT+'/interns',headers=headers).json()['total']==1
    assert client.get(PMS+'/work/submissions',headers=headers).json()=={'items':[],'total':0}
    decision={'status':'Approved','score':100,'feedback':'Forbidden','inspected':True}
    assert client.post(f"{PMS}/work/submissions/{submission['id']}/review",headers=headers,json=decision).status_code==403
    assert client.post(f"/api/v1/interns-hub/admin/submissions/{submission['id']}/review",headers=headers,json=decision).status_code==403
    assert db.query(PMSWorkReview).count()==0
    assert client.get(f"{ROOT}/memberships/{p['interns'][1][0].id}",headers=headers).status_code==404

def test_approved_leave_and_date_range_do_not_create_false_report_risk(client,db,program):
    from app.models.leave import LeaveRequest,LeaveType
    p=program;e=p['interns'][0][0]
    leave=LeaveType(name='Approved leave',code='BENCH-LEAVE',days_allowed=30);db.add(leave);db.flush()
    start=today()-timedelta(days=7)
    db.add(LeaveRequest(employee_id=e.id,leave_type_id=leave.id,from_date=start,to_date=today(),days_count=8,status='Approved'));db.commit()
    r=client.get(ROOT+'/interns',headers=p['headers'],params={'date_from':str(start),'date_to':str(today())});assert r.status_code==200,r.text
    row=next(i for i in r.json()['items'] if i['id']==e.id)
    assert row['expected_reports']==0 and not any('Missing' in risk for risk in row['risks'])
    assert r.json()['total']==2 # report window must not remove interns who joined earlier

def test_legacy_history_import_is_explicit_and_idempotent(client,db,program):
    from app.apps.interns_hub.models import InternTask,InternSubmission
    from app.apps.interns_hub.management_models import InternLegacyTaskMap
    p=program;e,h,_=p['interns'][0]
    old=InternTask(employee_id=e.id,title='Legacy completed work',description='Preserve this history',due_date=today(),status='Completed');db.add(old);db.flush()
    db.add(InternSubmission(task_id=old.id,employee_id=e.id,notes='Historical evidence',links=['https://example.test/work'],files=[],status='Approved',score=87,feedback='Original review',reviewed_by=p['admin'].id));db.commit()
    assert client.get('/api/v1/interns-hub/tasks',headers=h).json()==[]
    body={'project_id':p['project'].id,'reviewer_user_id':p['admin'].id}
    r=client.post(ROOT+'/legacy/import',headers=p['headers'],json=body);assert r.status_code==200,r.text
    assert r.json()=={'converted':1,'remaining':0,'errors':[]}
    mapping=db.get(InternLegacyTaskMap,old.id);assert mapping
    assert db.get(InternTask,old.id) # original evidence never deleted
    assert db.query(PMSWorkReview).one().score==87
    assert client.post(ROOT+'/legacy/import',headers=p['headers'],json=body).json()['converted']==0
    assert db.query(PMSWorkSubmission).count()==1
    assert client.get('/api/v1/interns-hub/overview',headers=h).json()['score']==87

def test_one_intern_completion_updates_parent_and_preserves_approved_evidence(client,db,program):
    p=program;e,h,_=p['interns'][0]
    job,_=publish(client,p,target_type='interns',employee_ids=[e.id],batch_ids=[])
    sid=client.post(f"/api/v1/interns-hub/tasks/{job['task_id']}/submissions",headers=h,json={'notes':'Approved once','confirmed':True}).json()['id']
    r=client.post(f'{PMS}/work/submissions/{sid}/review',headers=p['headers'],json={'status':'Approved','score':95,'feedback':'Meets requirements','inspected':True});assert r.status_code==200,r.text
    assert db.get(PMSTask,job['task_id']).status=='Done'
    assert client.get(ROOT+'/distributions',headers=p['headers']).json()['items'][0]['submitted']==1
    assert client.post(f"/api/v1/interns-hub/tasks/{job['task_id']}/submissions",headers=h,json={'notes':'Cannot change approved work','confirmed':True}).status_code==409

def test_intern_cannot_submit_scores_and_dashboard_uses_selected_project(client,db,program):
    p=program;e,h,_=p['interns'][0]
    job,_=publish(client,p,target_type='interns',employee_ids=[e.id],batch_ids=[])
    assert client.post(f"/api/v1/interns-hub/tasks/{job['task_id']}/submissions",headers=h,json={'notes':'Cannot self-score','confirmed':True,'score':100,'status':'Approved'}).status_code==422
    first=PMSWorkSubmission(task_id=job['task_id'],user_id=e.user_id,version=1,notes='Evaluated',links=[],files=[],status='Approved');db.add(first);db.flush()
    db.add(PMSWorkReview(submission_id=first.id,reviewer_user_id=p['admin'].id,decision='Approved',score=90,maximum_score=100,feedback='Quality work'))
    other=PMSProject(name='Unrelated program',project_key='UNREL',organization_id=1,manager_user_id=p['admin'].id);db.add(other);db.flush()
    task=PMSTask(project_id=other.id,title='Unrelated task',task_key='UNREL-1',status='Done',due_date=today());db.add(task);db.flush()
    db.add(PMSTaskAssignee(task_id=task.id,user_id=e.user_id,execution_status='Done'))
    second=PMSWorkSubmission(task_id=task.id,user_id=e.user_id,version=1,notes='Other evaluation',links=[],files=[],status='Approved');db.add(second);db.flush()
    db.add(PMSWorkReview(submission_id=second.id,reviewer_user_id=p['admin'].id,decision='Approved',score=10,maximum_score=100,feedback='Other program'));db.commit()
    assert client.get(ROOT+'/dashboard',headers=p['headers']).json()['average_score']==50
    scoped=client.get(ROOT+'/dashboard',headers=p['headers'],params={'batch_id':p['batches'][0]}).json()
    assert scoped['average_score']==90 and scoped['assigned_tasks']==1

def test_learning_global_courses_are_tenant_scoped(client,db,program):
    from app.apps.interns_hub.models import InternCourse
    p=program;h=p['interns'][0][1]
    db.add_all([InternCourse(title='Own course',organization_id=1),InternCourse(title='Other tenant course',organization_id=999)])
    db.commit()
    titles=[r['title'] for r in client.get('/api/v1/interns-hub/learning',headers=h).json()]
    assert 'Own course' in titles and 'Other tenant course' not in titles

