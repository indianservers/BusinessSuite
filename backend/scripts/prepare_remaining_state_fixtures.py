import os,json,time,hashlib,requests
from datetime import date,timedelta,datetime,timezone
os.environ.setdefault('PRESERVED_QA_UPLOADS','C:/Users/SAISAT~1/AppData/Local/Temp/suite-navigation-qa-t5op8r7a/uploads')
from serve_verified_1582 import SessionLocal,ROOT,User,CommonPerson,get_password_hash
from app.models.employee import Employee
from app.access.models import AccessMembership
from app.branches.models import BranchGrant
from app.apps.project_management.models import PMSTask,PMSTaskAssignee,PMSInternTaskPack,PMSInternPackRun,PMSInternAssignmentPlan,PMSNote
from test_identity_utils import own_workflow_records
b='http://127.0.0.1:1582';a=requests.post(b+'/api/v1/auth/login',json={'email':'admin@suiteqa.example.com','password':'SuiteQA@12345'},timeout=40).json();h={'Authorization':'Bearer '+a['access_token']};tag=str(time.time_ns())[-12:]
def seed(path,body):
 r=requests.post(b+'/api/v1'+path,headers=h,json=body,timeout=40);r.raise_for_status();return r.json()
with SessionLocal() as db:
 creator=db.query(User).filter_by(email='conditional-creator@suiteqa.example.com').one();deleter=db.query(User).filter_by(email='conditional-deleter@suiteqa.example.com').one()
 project=seed('/project-management/projects',{'name':'Conditional assignment states '+tag,'project_key':'ST'+tag,'workspace_id':1})
 seed('/project-management/projects/'+str(project['id'])+'/members',{'user_id':creator.id,'role':'Member','add_to_workspace':True})
 tasks={}
 for index,kind in enumerate(['prerequisite','blocked','future','cancelled','done','revision']):
  tasks[kind]=seed('/project-management/projects/'+str(project['id'])+'/tasks',{'title':'Conditional '+kind+' '+tag,'task_key':'ST'+tag+str(index),'assignee_user_ids':[creator.id]})
 pack=PMSInternTaskPack(organization_id=1,project_id=project['id'],name='Synthetic state fixtures '+tag,steps=[],created_by=a['user_id']);db.add(pack);db.flush()
 run=PMSInternPackRun(organization_id=1,project_id=project['id'],pack_id=pack.id,pack_version=1,snapshot={},result={},request_key='conditional-'+tag,request_hash=hashlib.sha256(tag.encode()).hexdigest(),created_by=a['user_id']);db.add(run);db.flush()
 plans=[]
 for kind in ['blocked','future']:
  task=db.get(PMSTask,tasks[kind]['id']);task.start_date=date.today()+timedelta(days=7) if kind=='future' else date.today()
  plan=PMSInternAssignmentPlan(task_id=task.id,user_id=creator.id,run_id=run.id,step_key=kind,skill_level='beginner',prerequisites=[tasks['prerequisite']['id']] if kind=='blocked' else [],rubric=[]);db.add(plan);plans.append(plan)
 for kind,status in [('cancelled','To Do'),('done','Done'),('revision','Revision Requested')]:
  assignment=db.get(PMSTaskAssignee,(tasks[kind]['id'],creator.id));assignment.execution_status=status
  if kind=='cancelled':assignment.cancelled_at=datetime.now(timezone.utc)
  if kind=='done':assignment.progress_percent=100
 own_workflow_records(db,pack,run,*plans,company_id=1);db.commit()
 emp=seed('/employees/',{'employee_id':'LINK'+tag,'first_name':'Wizard link '+tag,'last_name':'Acceptance','work_email':'wizard-link-'+tag+'@example.com','date_of_joining':'2026-11-01','status':'Active'})
 user=User(email='wizard-unlinked-'+tag+'@example.com',hashed_password=get_password_hash('WizardLink@12345'),is_active=True,is_superuser=False,person=CommonPerson(organization_id=1,primary_email='wizard-unlinked-'+tag+'@example.com',display_name='Synthetic unlinked wizard account'))
 db.add(user);db.flush();db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=False));db.add(BranchGrant(user_id=user.id,company_id=1,branch_id=1,can_write=False));own_workflow_records(db,user,company_id=1);db.commit()
 note=seed('/project-management/notes',{'title':'Attachment owner fixture '+tag,'content':'Private synthetic file'})
 r=requests.post(b+'/api/v1/project-management/notes/'+str(note['id'])+'/attachments',headers=h,files={'file':('role-attachment-'+tag+'.txt',b'Synthetic private note permission fixture','text/plain')},timeout=40);r.raise_for_status();attachment=r.json()
 record=db.get(PMSNote,note['id']);record.owner_id=deleter.id;db.commit()
 out={'tasks':{k:{'id':v['id'],'title':v['title']} for k,v in tasks.items()},'wizard':{'employee_id':emp['id'],'employee_name':emp['first_name'],'user_id':user.id,'email':user.email},'attachment':{'note_id':note['id'],'file_id':attachment['id'],'filename':attachment['filename']}}
 (ROOT/'outputs/conditional-121/remaining-state-fixtures.json').write_text(json.dumps(out),encoding='utf-8');print(json.dumps(out))
