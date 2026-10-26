from datetime import timedelta
import pytest
from app.apps.interns_hub.router import today
from app.apps.interns_hub.models import InternApplication
from app.models.user import User
from app.models.employee import Employee


@pytest.fixture
def application_payload():
    return dict(full_name="Ananya Rao", parent_name="Parent Rao", mobile="9876543210", mobile_country_code="+91", email="applicant@example.com",
        identity_type="Other", identity_number="TEST-ID-1234", gender="Female", date_of_birth="2003-03-15",
        city="Hyderabad", state="Telangana", tenth_marks=92, twelfth_marks=88, degree="B.Tech / B.E.",
        current_year="3rd Year", college="Example University", specialization="Computer Science", passout_year=today().year+1,
        area_of_interest="Software Development", skills="Python, React", role="Software Development Intern", mode="Remote",
        available_from=str(today()), duration="3 Months", address="Example Road, Hyderabad", linkedin=None,
        emergency_contact="9123456789", emergency_contact_country_code="+91", password="Applicant@123456", consent=True)


def test_application_requires_approval_before_login(client, db, superuser_headers, application_payload):
    from app.models.company import Company, Branch, Department, Designation
    base="/api/v1/interns-hub"
    result=client.post(f"{base}/applications",json=application_payload)
    assert result.status_code==201, result.text
    assert result.json()["status"]=="Pending" and not result.json()["can_login"]
    assert not db.query(User).filter_by(email=application_payload["email"]).first()
    assert client.post('/api/v1/auth/login',json={"email":application_payload["email"],"password":application_payload["password"],"module":"interns_hub"}).status_code==401
    application=db.query(InternApplication).filter_by(email=application_payload["email"]).one()
    assert application.identity_number_encrypted != application_payload["identity_number"]
    assert application.password_hash != application_payload["password"]
    assert "password" not in application.details and "identity_number" not in application.details
    assert client.get(f"{base}/admin/applications").status_code==403
    admin_list=client.get(f"{base}/admin/applications",headers=superuser_headers)
    assert admin_list.status_code==200 and admin_list.json()[0]["identity_last4"]=="1234"
    assert "password_hash" not in admin_list.text and "TEST-ID-1234" not in admin_list.text
    company=db.get(Company,1) or Company(id=1,name="Application Company");db.add(company);db.flush()
    branch=Branch(name="HQ",company_id=company.id);db.add(branch);db.flush()
    department=Department(name="Engineering",branch_id=branch.id);db.add(department);db.flush()
    designation=Designation(name="Development Intern",department_id=department.id);db.add(designation)
    manager=Employee(employee_id="APP-MANAGER",first_name="Team",last_name="Manager",date_of_joining=today());db.add(manager);db.commit()
    decision=dict(status="Approved",branch_id=branch.id,department_id=department.id,designation_id=designation.id,reporting_manager_id=manager.id,date_of_joining=str(today()))
    approved=client.post(f"{base}/admin/applications/{application.id}/decision",headers=superuser_headers,json=decision)
    assert approved.status_code==200, approved.text
    assert approved.json()["can_login"] and approved.json()["intern_id"].startswith("IH-")
    assert client.post(f"{base}/admin/applications/{application.id}/decision",headers=superuser_headers,json=decision).status_code==409
    account=db.query(User).filter_by(email=application_payload["email"]).one()
    assert account.role.name=="intern" and account.employee.employee_id==approved.json()["intern_id"]
    assert account.employee.department_id==department.id and account.employee.reporting_manager_id==manager.id
    assert len(account.employee.educations)==3 and len(account.employee.skills)==2
    login=client.post('/api/v1/auth/login',json={"email":application_payload["email"],"password":application_payload["password"],"module":"interns_hub"})
    assert login.status_code==200, login.text
    headers={"Authorization":f"Bearer {login.json()['access_token']}"}
    assert client.get(f"{base}/me",headers=headers).json()["employee_id"]==approved.json()["intern_id"]
    status=client.post(f"{base}/applications/status",json={"email":application_payload["email"],"password":application_payload["password"]})
    assert status.status_code==200 and status.json()["intern_id"]==approved.json()["intern_id"]


def test_application_rejection_and_validation(client, db, superuser_headers, application_payload):
    base="/api/v1/interns-hub"
    assert client.post(f"{base}/applications",json={**application_payload,"consent":False}).status_code==422
    assert client.post(f"{base}/applications",json={**application_payload,"resume_url":"https://example.com/resume.pdf"}).status_code==422
    assert client.post(f"{base}/applications",json={**application_payload,"tenth_marks":101}).status_code==422
    assert client.post(f"{base}/applications",json={**application_payload,"available_from":str(today()-timedelta(days=1))}).status_code==422
    assert client.post(f"{base}/applications",json=application_payload).status_code==201
    assert client.post(f"{base}/applications",json=application_payload).status_code==409
    item=db.query(InternApplication).one()
    assert client.post(f"{base}/admin/applications/{item.id}/decision",headers=superuser_headers,json={"status":"Approved"}).status_code==422
    rejected=client.post(f"{base}/admin/applications/{item.id}/decision",headers=superuser_headers,json={"status":"Rejected","review_note":"No places available in this cohort"})
    assert rejected.status_code==200 and not rejected.json()["can_login"]
    assert not db.query(User).filter_by(email=application_payload["email"]).first()
    assert client.post(f"{base}/applications/status",json={"email":application_payload["email"],"password":"WrongPassword"}).status_code==401
    status=client.post(f"{base}/applications/status",json={"email":application_payload["email"],"password":application_payload["password"]})
    assert status.json()["status"]=="Rejected" and status.json()["intern_id"] is None
    assert client.post(f"{base}/applications/status",json={"email":"missing@example.com","password":"unknown-application"}).status_code==401


def test_status_attempts_are_limited_per_applicant(client, application_payload):
    base="/api/v1/interns-hub"
    assert client.post(f"{base}/applications",json=application_payload).status_code==201
    for _ in range(10):
        assert client.post(f"{base}/applications/status",json={"email":application_payload["email"],"password":"WrongPassword"}).status_code==401
    assert client.post(f"{base}/applications/status",json={"email":application_payload["email"],"password":"WrongPassword"}).status_code==423
    assert client.post(f"{base}/applications/status",json={"email":"other@example.com","password":"WrongPassword"}).status_code==401


def test_application_roles_are_hrms_managed_and_enforced(client, superuser_headers, application_payload):
    base='/api/v1/interns-hub'
    assert client.get(base+'/admin/application-settings').status_code == 403
    initial=client.get(base+'/admin/application-settings',headers=superuser_headers).json()
    saved=client.put(base+'/admin/application-settings',headers=superuser_headers,json={'roles':['Security Intern'],'version':initial['version']})
    assert saved.status_code == 200, saved.text
    assert client.get(base+'/application-options').json()['roles'] == ['Security Intern']
    assert client.post(base+'/applications',json=application_payload).status_code == 422
    assert client.post(base+'/applications',json={**application_payload,'role':'Security Intern'}).status_code == 201
    assert client.put(base+'/admin/application-settings',headers=superuser_headers,json={'roles':['Other'],'version':initial['version']}).status_code == 409
    assert client.put(base+'/admin/application-settings',headers=superuser_headers,json={'roles':['Intern','intern'],'version':saved.json()['version']}).status_code == 422


@pytest.mark.parametrize('field,value',[('address','a'*201),('gender','Prefer not to say')])
def test_application_new_field_limits_reject_api_bypass(client,application_payload,field,value):
    result=client.post('/api/v1/interns-hub/applications',json={**application_payload,field:value})
    assert result.status_code == 422
    assert any(error['loc'][-1] == field for error in result.json()['detail'])


def test_application_address_allows_200_characters(client,application_payload):
    assert client.post('/api/v1/interns-hub/applications',json={**application_payload,'address':'a'*200}).status_code == 201


@pytest.fixture(autouse=True)
def _google_application_access(google_applicant):
    google_applicant('applicant@example.com')



def test_application_email_is_bound_to_google_identity(client,application_payload,google_applicant):
    google_applicant('another@example.com')
    response=client.post('/api/v1/interns-hub/applications',json=application_payload)
    assert response.status_code==403
