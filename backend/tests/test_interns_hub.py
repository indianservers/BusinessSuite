from datetime import timedelta
import pytest
from app.models.user import Role, User
from app.models.employee import Employee
from app.models.company import Company, Branch, Department, Designation
from app.core.security import get_password_hash, verify_access_token
from app.apps.interns_hub.router import today


@pytest.fixture
def interns(db, client, monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    role = Role(name="employee")
    db.add(role)
    db.flush()
    # PostgreSQL fixtures already seed the administrator's organization (1).
    company = db.get(Company, 1) or Company(id=1, name="Hub Company")
    db.add(company)
    db.flush()
    branch = Branch(name="HQ", company_id=company.id)
    db.add(branch)
    db.flush()
    dept = Department(name="Marketing", branch_id=branch.id)
    db.add(dept)
    db.flush()
    desig = Designation(name="Marketing Intern", department_id=dept.id)
    db.add(desig)
    manager = Employee(employee_id="MGR-HUB", first_name="Arjun", last_name="Mehta", date_of_joining=today())
    db.add(manager)
    db.flush()
    records = []
    for index in range(2):
        user = User(email=f"intern{index}@example.com", hashed_password=get_password_hash("Intern@123456"), role_id=role.id, is_active=True)
        db.add(user)
        db.flush()
        employee = Employee(employee_id=f"INT-HUB-{index}", first_name="Riya" if not index else "Karan", last_name="Sharma", employment_type="Intern", date_of_joining=today()-timedelta(days=30), user_id=user.id, department_id=dept.id, designation_id=desig.id, branch_id=branch.id, reporting_manager_id=manager.id)
        db.add(employee)
        db.commit()
        result = client.post("/api/v1/auth/login", json={"email":user.email,"password":"Intern@123456","module":"interns_hub"})
        assert result.status_code == 200, result.text
        records.append((employee, {"Authorization": f"Bearer {result.json()['access_token']}"}, result.json()))
    return records


def test_login_scope_and_hrms_sync(client, db, interns, superuser_headers):
    employee, headers, tokens = interns[0]
    assert verify_access_token(tokens["access_token"])["portal"] == "interns_hub"
    default_login = client.post("/api/v1/auth/login", json={"email":"intern0@example.com", "password":"Intern@123456"})
    assert verify_access_token(default_login.json()["access_token"])["portal"] == "interns_hub"
    assert client.post("/api/v1/auth/login", json={"email":"intern0@example.com", "password":"Intern@123456", "module":"hrms"}).status_code == 403
    me = client.get("/api/v1/interns-hub/me", headers=headers).json()
    assert (me["department"], me["designation"], me["manager"]) == ("Marketing", "Marketing Intern", "Arjun Mehta")
    assert "aadhaar_number" not in me
    assert client.get("/api/v1/employees/", headers=headers).status_code == 403
    assert client.get("/api/v1/interns-hub/admin/interns", headers=headers).status_code == 403
    assert client.get("/api/v1/interns-hub/me", headers=superuser_headers).status_code == 403
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert verify_access_token(refreshed.json()["access_token"])["portal"] == "interns_hub"
    changed = client.patch("/api/v1/interns-hub/me", headers=headers, json={"present_city":"Hyderabad"})
    assert changed.status_code == 200
    db.refresh(employee)
    assert employee.present_city == "Hyderabad"
    employee.employment_type = "Full-time"
    db.commit()
    assert client.get("/api/v1/interns-hub/me", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/login", json={"email":"intern0@example.com","password":"Intern@123456","module":"interns_hub"}).status_code == 403


def test_task_submission_review_certificate(client, db, interns, superuser_headers):
    from app.apps.project_management.models import PMSProject
    project=PMSProject(name="Intern Work",project_key="IW",organization_id=1)
    db.add(project);db.commit()
    employee, headers, _ = interns[0]
    other_headers = interns[1][1]
    task = client.post("/api/v1/interns-hub/admin/tasks", headers=superuser_headers, json={"project_id":project.id,"employee_id":employee.id,"title":"Create a social media post","description":"Build a campaign post","due_date":str(today()),"points":10})
    assert task.status_code == 201, task.text
    task_id = task.json()["id"]
    assert client.post(f"/api/v1/interns-hub/tasks/{task_id}/start", headers=other_headers).status_code == 404
    file = client.post("/api/v1/interns-hub/files", headers=headers, data={"task_id":task_id}, files={"file":("proof.txt",b"Original work","text/plain")})
    assert file.status_code == 201, file.text
    file_id = file.json()["id"]
    assert client.get(f"/api/v1/interns-hub/files/{file_id}", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/interns-hub/files/{file_id}", headers=headers).content == b"Original work"
    submission = client.post(f"/api/v1/interns-hub/tasks/{task_id}/submissions", headers=headers, json={"notes":"My completed work", "confirmed":True,"files":[file_id]})
    assert submission.status_code == 201, submission.text
    cert_data = {"employee_id":employee.id,"title":"Internship Completion","certificate_type":"Internship"}
    assert client.post("/api/v1/interns-hub/admin/certificates", headers=superuser_headers, json=cert_data).status_code == 409
    reviewed = client.post(f"/api/v1/interns-hub/admin/submissions/{submission.json()['id']}/review", headers=superuser_headers, json={"status":"Approved","score":92,"feedback":"Excellent original work","inspected":True})
    assert reviewed.status_code == 200, reviewed.text
    stats = client.get("/api/v1/interns-hub/overview", headers=headers).json()
    assert stats["completed"] == 1 and stats["score"] == 92
    assert client.post("/api/v1/interns-hub/admin/certificates", headers=superuser_headers, json=cert_data).status_code == 409
    certificate = client.post("/api/v1/interns-hub/admin/certificates", headers=superuser_headers, json={**cert_data,"certificate_type":"Module Completion"})
    assert certificate.status_code == 201
    certificate_id = certificate.json()["id"]
    assert client.get(f"/api/v1/interns-hub/certificates/{certificate_id}/download", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/interns-hub/certificates/{certificate_id}/download", headers=headers).status_code == 200


def test_reports_attendance_learning_support(client, db, interns, superuser_headers):
    from app.models.attendance import Attendance
    employee, headers, _ = interns[0]
    url = "/api/v1/interns-hub"
    assert client.post(f"{url}/attendance/check-in", headers=headers).status_code == 200
    assert client.post(f"{url}/attendance/check-in", headers=headers).status_code == 409
    assert db.query(Attendance).filter_by(employee_id=employee.id).count() == 1
    assert client.post(f"{url}/attendance/check-out", headers=headers).status_code == 200
    assert client.post(f"{url}/attendance/check-out", headers=headers).status_code == 409
    payload = {"report_date":str(today()),"work":"Campaign design","learning":"Brand guidelines","status":"Submitted"}
    assert client.put(f"{url}/reports", headers=headers, json=payload).status_code == 200
    assert client.put(f"{url}/reports", headers=headers, json={**payload,"work":"Updated design"}).status_code == 200
    assert len(client.get(f"{url}/reports", headers=headers).json()) == 1
    course = client.post(f"{url}/admin/learning", headers=superuser_headers, json={"title":"Communication Skills", "lessons":[{"title":"Introduction","url":"https://example.com/lesson"}],"questions":[{"prompt":"Choose the clear message","options":["Clear","Vague"],"answer":0}]})
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    course_data = client.get(f"{url}/learning", headers=headers).json()[0]
    assert "answer" not in course_data["questions"][0]
    progress = client.post(f"{url}/learning/{course_id}/progress", headers=headers, json={"lesson":0,"answers":[0]})
    assert progress.status_code == 200 and progress.json()["score"] == 100
    ticket = client.post(f"{url}/support", headers=headers, json={"subject":"Need help","message":"Please clarify the brief"})
    assert ticket.status_code == 201
    assert client.post(f"{url}/admin/support/{ticket.json()['id']}/reply", headers=superuser_headers, json={"reply":"Updated instructions available"}).status_code == 200
    assert client.get(f"{url}/support", headers=headers).json()[0]["status"] == "Resolved"
    assert client.post(f"{url}/logout", headers=headers).status_code == 200
    assert client.get(f"{url}/me", headers=headers).status_code == 401


def test_manager_cannot_manage_other_interns(client, db, interns):
    manager_role = Role(name="manager")
    db.add(manager_role)
    db.flush()
    user = User(email="manager@example.com", hashed_password=get_password_hash("Manager@123456"), is_active=True, role_id=manager_role.id)
    db.add(user)
    db.flush()
    manager = Employee(employee_id="OTHER-MGR",first_name="Other",last_name="Manager",date_of_joining=today(),user_id=user.id)
    db.add(manager)
    db.commit()
    login = client.post("/api/v1/auth/login",json={"email":user.email,"password":"Manager@123456","module":"hrms"})
    headers={"Authorization":f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/interns-hub/admin/interns",headers=headers).status_code == 403
    assert client.post("/api/v1/interns-hub/admin/tasks",headers=headers,json={"project_id":1,"employee_id":interns[0][0].id,"title":"Other intern task","description":"Forbidden","due_date":str(today())}).status_code == 403


def test_hrms_provisions_intern_login(client, db, superuser_headers):
    response = client.post("/api/v1/employees/", headers=superuser_headers, json={"first_name":"New", "last_name":"Intern", "date_of_joining":str(today()), "employment_type":"Intern", "create_user_account":True, "user_email":"newintern@example.com", "user_password":"Intern@123456"})
    assert response.status_code == 201, response.text
    employee = db.get(Employee, response.json()["id"])
    assert employee.user.role.name == "intern"
    login = client.post("/api/v1/auth/login", json={"email":"newintern@example.com","password":"Intern@123456","module":"interns_hub"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post("/api/v1/interns-hub/password", headers=headers, json={"current_password":"Intern@123456", "new_password":"UpdatedIntern@123456"})
    assert changed.status_code == 200, changed.text
    assert client.post("/api/v1/auth/login", json={"email":"newintern@example.com","password":"UpdatedIntern@123456","module":"interns_hub"}).status_code == 200


def test_mfa_challenge_keeps_portal_scope(client, db, interns, monkeypatch):
    from app.api.v1 import auth
    employee, _, _ = interns[0]
    employee.user.mfa_enabled = True
    db.commit()
    monkeypatch.setattr(auth, "_trusted_device_valid", lambda *args: False)
    login = client.post("/api/v1/auth/login", json={"email":"intern0@example.com","password":"Intern@123456","module":"interns_hub"})
    assert login.status_code == 200 and login.json()["mfa_required"]
    payload = auth._decode_mfa_token(login.json()["mfa_token"])
    assert payload["module"] == "interns_hub"
    # A changed employee type must be rejected before accepting the second factor.
    employee.employment_type = "Full-time"
    db.commit()
    assert client.post("/api/v1/auth/mfa/verify", json={"mfa_token":login.json()["mfa_token"],"code":"123456"}).status_code == 403
