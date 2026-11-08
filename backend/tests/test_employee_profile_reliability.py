from datetime import date,timedelta
from tests.rich_text_test_utils import organization_context
from tests.test_employee_profile_records import profile_employee
from app.models.employee import Employee,EmployeeDocument,EmployeeCertification,EmployeeChangeRequest
ROOT='/api/v1/employees'


def test_history_private_values(client,db,superuser_headers,profile_employee):
 ident,_=profile_employee
 assert client.put(f'{ROOT}/{ident}',json={'first_name':'Revised','bio':'private biography'},headers=superuser_headers).status_code==200
 r=client.post(f'{ROOT}/{ident}/education',json={'degree':'B.Tech'},headers=superuser_headers);assert r.status_code==201,r.text
 rid=r.json()['id'];assert client.put(f'{ROOT}/{ident}/education/{rid}',json={'degree':'M.Tech'},headers=superuser_headers).status_code==200
 assert client.delete(f'{ROOT}/{ident}/education/{rid}',headers=superuser_headers).status_code==200
 rows=client.get(f'{ROOT}/{ident}/history',headers=superuser_headers).json()['items']
 assert any(r['field']=='first_name' and r['before']=='Profile' and r['after']=='Revised' and r['actor_id'] for r in rows)
 assert {r['action'] for r in rows if r['field']=='degree'}=={'created','updated','deleted'}
 assert 'private biography' not in str(rows)


def test_stale_writes_and_retries(client,db,superuser_headers,profile_employee):
 ident,_=profile_employee
 initial=client.get(f'{ROOT}/{ident}',headers=superuser_headers).json()['profile_version'];h={**superuser_headers,'If-Match':initial}
 r=client.put(f'{ROOT}/{ident}',json={'work_location':'Winner'},headers=h);assert r.status_code==200,r.text
 assert r.json()['profile_version']!=initial
 assert client.put(f'{ROOT}/{ident}',json={'work_location':'Lost'},headers=h).status_code==409
 db.expire_all();assert db.get(Employee,ident).work_location=='Winner'
 h['If-Match']=r.json()['profile_version']
 added=client.post(f'{ROOT}/{ident}/skills',json={'skill_name':'Python'},headers=h);assert added.status_code==201,added.text
 assert client.post(f'{ROOT}/{ident}/skills',json={'skill_name':'Python'},headers=h).status_code==409
 url=f'{ROOT}/{ident}/skills/{added.json()["id"]}'
 assert client.put(url,json={'skill_name':'Overwrite'},headers=h).status_code==409
 assert client.delete(url,headers=h).status_code==409


def test_duplicate_contacts(client,db,superuser_headers,profile_employee):
 ident,_=profile_employee;emp=db.get(Employee,ident);emp.personal_email='same@example.com'
 from app.models.company import Department,Designation
 department=Department(name='Duplicate review QA',branch_id=emp.branch_id);db.add(department);db.flush();db.add(Designation(name='Duplicate review QA',department_id=department.id));db.commit()
 r=client.post(ROOT+'/duplicate-check',json={'work_email':' SAME@example.com '},headers=superuser_headers);assert r.status_code==200,r.text
 assert r.json()['items'][0]['id']==ident
 payload={'first_name':'New','last_name':'Person','date_of_joining':'2026-01-01','personal_email':'same@example.com','branch_id':emp.branch_id,'create_user_account':False}
 r=client.post(ROOT+'/',json=payload,headers=superuser_headers);assert r.status_code==409 and 'duplicate' in r.text.lower(),r.text
 payload['allow_contact_duplicate']=True
 r=client.post(ROOT+'/',json=payload,headers=superuser_headers);assert r.status_code==201,r.text


def test_expiry_and_document_rejection(client,db,superuser_headers,profile_employee):
 ident,_=profile_employee
 for days in [-1,0,20,45,75,100]:db.add(EmployeeCertification(employee_id=ident,certification_name=f'License {days}',expiry_date=date.today()+timedelta(days=days)))
 doc=EmployeeDocument(employee_id=ident,document_type='Education',document_name='Degree certificate');db.add(doc);db.commit()
 r=client.get(f'{ROOT}/{ident}/profile-checks?days=30',headers=superuser_headers);assert r.status_code==200,r.text
 assert len(r.json()['certifications'])==3
 assert len(client.get(f'{ROOT}/{ident}/profile-checks?days=90',headers=superuser_headers).json()['certifications'])==5
 url=f'{ROOT}/{ident}/documents/{doc.id}/verify'
 assert client.put(url,json={'verification_status':'Rejected'},headers=superuser_headers).status_code==422
 r=client.put(url,json={'verification_status':'Rejected','verification_notes':'Unreadable certificate'},headers=superuser_headers);assert r.status_code==200,r.text
 assert r.json()['verification_status']=='Rejected' and not r.json()['is_verified']


def test_reader_access(client,db,superuser_headers,profile_employee):
 from app.models.user import User,Role,Permission
 from app.core.security import create_access_token
 from test_identity_utils import attach_test_identity,attach_workflow_branch
 p=db.query(Permission).filter_by(name='employee_view').first()
 if not p:p=Permission(name='employee_view',module='hrms');db.add(p)
 role=Role(name='profile_audit_viewer',permissions=[p]);u=User(email='profile-viewer@example.com',hashed_password='unused',role=role,is_active=True)
 db.add(u);db.flush();attach_test_identity(db,u);attach_workflow_branch(db,u);db.commit()
 h={'Authorization':'Bearer '+create_access_token(u.id)};ident,_=profile_employee
 r=client.get(f'{ROOT}/{ident}',headers=h);assert r.status_code==200,r.text
 assert r.json()['can_edit_profile'] is False
 assert client.get(f'{ROOT}/{ident}/history',headers=h).status_code==403
 assert client.put(f'{ROOT}/{ident}',json={'work_location':'Illegal'},headers=h).status_code==403


def test_stale_approval(client,db,superuser_headers,profile_employee):
 ident,_=profile_employee;db.get(Employee,ident).personal_email='later@example.com'
 item=EmployeeChangeRequest(employee_id=ident,organization_id=1,request_type='Profile Update',field_changes_json={'personal_email':'requested@example.com'},old_value_json={'personal_email':'original@example.com'},status='Pending')
 db.add(item);db.commit()
 r=client.post(f'/api/v1/hrms/profile-change-requests/{item.id}/approve',json={'applyChanges':True},headers=superuser_headers);assert r.status_code==409,r.text
 db.expire_all();assert db.get(Employee,ident).personal_email=='later@example.com'
 assert db.get(EmployeeChangeRequest,item.id).status=='Pending'
