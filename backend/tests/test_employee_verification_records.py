from tests.rich_text_test_utils import organization_context
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import time
import pytest
from app.models.employee import Employee, EmployeeDocument, EmployeeLifecycleEvent
from app.models.background_verification import BackgroundVerificationRequest as Case, BackgroundVerificationVendor as Vendor

BASE = "/api/v1/background-verification"


def people(db):
    current = Employee(employee_id="BGV-CURRENT", first_name="Current", last_name="Worker", date_of_joining=date(2024, 1, 1))
    former = Employee(employee_id="BGV-FORMER", first_name="Former", last_name="Worker", date_of_joining=date(2023, 1, 1), status="Resigned", date_of_exit=date(2025, 1, 1))
    db.add_all([current, former]); db.flush()
    docs = [EmployeeDocument(employee_id=p.id, document_type="Consent", document_name="Signed consent", file_url=f"/uploads/employee_docs/{p.id}/consent.pdf") for p in [current, former]]
    db.add_all(docs); db.commit()
    return current, former, docs


def create(client, headers, employee, **extra):
    return client.post(BASE+"/requests", headers=headers, json={"employee_id": employee.id, "package_name": "Standard", "checks": [{"check_type": "Identity"}], **extra})


def test_current_and_former_share_evidence_review_history_and_summary(client, db, superuser_headers):
    current, former, docs = people(db)
    for employee, document in zip([current, former], docs):
        created = create(client, superuser_headers, employee)
        assert created.status_code == 201, created.text
        row = created.json(); check_id = row["checks"][0]["id"]
        assert create(client, superuser_headers, employee).status_code == 409
        assert client.put(f"{BASE}/checks/{check_id}", headers=superuser_headers, json={"status":"Verified", "result":"Clear", "remarks":"Checked source"}).status_code == 422
        assert client.put(f"{BASE}/requests/{row['id']}/consent", headers=superuser_headers, json={"consent_status":"Captured", "employee_document_id": docs[1 if employee == current else 0].id}).status_code == 422
        consent = client.put(f"{BASE}/requests/{row['id']}/consent", headers=superuser_headers, json={"consent_status":"Captured", "employee_document_id":document.id, "version":row["version"]})
        assert consent.status_code == 200, consent.text
        assert client.put(f"{BASE}/requests/{row['id']}", headers=superuser_headers, json={"status":"Completed", "overall_result":"Clear", "review_notes":"Approved"}).status_code == 422
        updated = client.put(f"{BASE}/checks/{check_id}", headers=superuser_headers, json={"status":"Verified", "result":"Clear", "employee_document_id":document.id, "version":consent.json()["version"]})
        assert updated.status_code == 200, updated.text
        assert updated.json()["status"] == "Awaiting Review"
        db.refresh(employee); assert employee.background_verification_status == "In Progress"
        stale = client.put(f"{BASE}/requests/{row['id']}", headers=superuser_headers, json={"status":"Completed", "overall_result":"Clear", "review_notes":"Reviewed sources", "version":row["version"]})
        assert stale.status_code == 409
        closed = client.put(f"{BASE}/requests/{row['id']}", headers=superuser_headers, json={"status":"Completed", "overall_result":"Clear", "review_notes":"Reviewed sources", "version":updated.json()["version"]})
        assert closed.status_code == 200, closed.text
        assert closed.json()["reviewed_by"]
        db.refresh(employee); assert employee.background_verification_status == "Completed"
        assert client.put(f"{BASE}/checks/{check_id}", headers=superuser_headers, json={"status":"Pending"}).status_code == 409
        detail = client.get(f"{BASE}/employees/{employee.id}/file", headers=superuser_headers)
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["cases"]) == 1
        assert len(detail.json()["documents"]) == 1
        assert detail.json()["cases"][0]["checks"][0]["employee_document_id"] == document.id
        events = client.get(f"{BASE}/requests/{row['id']}/events", headers=superuser_headers).json()
        assert {e["event_type"] for e in events} >= {"verification.created", "verification.consent", "verification.check_updated", "verification.reviewed"}
    for population, expected in [("current",current.id),("former",former.id)]:
        register = client.get(BASE+"/register", params={"population":population}, headers=superuser_headers)
        assert register.status_code == 200, register.text
        assert [r["id"] for r in register.json()["items"]] == [expected]
    again = create(client, superuser_headers, current)
    assert again.status_code == 201
    assert db.query(Case).filter_by(employee_id=current.id).count() == 2
    db.refresh(current); assert current.background_verification_date is None
    assert current.background_verification_status == "In Progress"


def test_register_unassessed_overdue_and_discrepancy_not_clear(client, db, superuser_headers):
    current, former, docs = people(db)
    unassessed = client.get(BASE+"/register", headers=superuser_headers, params={"population":"all", "verification":"unassessed"})
    assert unassessed.status_code == 200, unassessed.text
    assert unassessed.json()["total"] == 2
    row = create(client, superuser_headers, current, expected_completion_date="2020-01-01").json()
    assert client.get(BASE+"/register", headers=superuser_headers, params={"verification":"overdue"}).json()["total"] == 1
    client.put(f"{BASE}/requests/{row['id']}/consent", headers=superuser_headers, json={"employee_document_id":docs[0].id})
    client.put(f"{BASE}/checks/{row['checks'][0]['id']}", headers=superuser_headers, json={"status":"Completed", "result":"Discrepancy", "remarks":"Source did not match; employee explanation pending"})
    assert client.put(f"{BASE}/requests/{row['id']}", headers=superuser_headers, json={"status":"Completed", "overall_result":"Clear", "review_notes":"Approved"}).status_code == 422
    closed = client.put(f"{BASE}/requests/{row['id']}", headers=superuser_headers, json={"status":"Completed", "overall_result":"Discrepancy", "review_notes":"Reviewed employee response; discrepancy confirmed"})
    assert closed.status_code == 200, closed.text
    db.refresh(current); assert current.background_verification_status == "Failed"
    former_file = client.get(f"{BASE}/employees/{former.id}/file", headers=superuser_headers).json()
    assert "Exit record missing" in former_file["missing"]
    assert "Verification not assessed" in former_file["missing"]


def test_signed_callback_is_replay_safe_and_cannot_close_hr_review(client, db, superuser_headers, monkeypatch):
    current, _, docs = people(db)
    monkeypatch.setenv("TEST_BGV_WEBHOOK", "synthetic-callback-secret")
    vendor = client.post(BASE+"/vendors", headers=superuser_headers, json={"name":"Vendor", "webhook_secret_ref":"env:TEST_BGV_WEBHOOK"})
    assert vendor.status_code == 201, vendor.text
    row = create(client, superuser_headers, current, vendor_id=vendor.json()["id"]).json()
    client.put(f"{BASE}/requests/{row['id']}/consent", headers=superuser_headers, json={"employee_document_id":docs[0].id})
    submitted = client.post(f"{BASE}/requests/{row['id']}/submit", headers=superuser_headers)
    assert submitted.status_code == 200, submitted.text
    payload = {"vendor_reference":submitted.json()["vendor_reference"], "status":"Completed", "overall_result":"Clear", "checks":[{"check_type":"Identity", "status":"Verified", "result":"Clear", "remarks":"Source checked"}]}
    body = json.dumps(payload).encode(); stamp = str(int(time.time()))
    headers = {"Content-Type":"application/json", "X-BGV-Timestamp":stamp, "X-BGV-Signature":hmac.new(b"synthetic-callback-secret",stamp.encode()+b"."+body,hashlib.sha256).hexdigest()}
    url = f"{BASE}/webhooks/{vendor.json()['id']}"
    assert client.post(url, content=body).status_code == 401
    first = client.post(url, content=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"received":True,"duplicate":False}
    assert client.post(url, content=body, headers=headers).json()["duplicate"] is True
    db.expire_all(); stored = db.get(Case,row["id"])
    assert stored.status == "Awaiting Review" and stored.reviewed_by is None


def test_exit_completion_preserves_file_and_rehire_keeps_old_exit(client, db, superuser_headers):
    current, _, _ = people(db)
    exit_response = client.post("/api/v1/exit/records", headers=superuser_headers, json={"employee_id":current.id,"exit_type":"Resignation","last_working_date":"2025-01-01","reason":"Historical exit imported"})
    assert exit_response.status_code == 201, exit_response.text
    ident = exit_response.json()["id"]
    assert client.post("/api/v1/exit/records", headers=superuser_headers, json={"employee_id":current.id}).status_code == 409
    tasks = client.get(f"/api/v1/exit/records/{ident}/checklist", headers=superuser_headers).json()
    assert len(tasks) == 5
    for task in tasks:
        result = client.put(f"/api/v1/exit/checklist/{task['id']}/complete",headers=superuser_headers,params={"remarks":"Evidence reviewed"})
        assert result.status_code == 200, result.text
    completed = client.put(f"/api/v1/exit/records/{ident}/complete",headers=superuser_headers)
    assert completed.status_code == 200, completed.text
    db.refresh(current); assert current.status == "Resigned" and current.date_of_exit == date(2025,1,1)
    assert client.get(f"{BASE}/employees/{current.id}/file",headers=superuser_headers).json()["exits"][0]["id"] == ident
    from app.models.exit import ExitRecord
    prior = db.get(ExitRecord,ident); prior.created_at = datetime(2024,1,1,tzinfo=timezone.utc)
    current.status = "Active"; current.date_of_exit = None
    db.add(EmployeeLifecycleEvent(employee_id=current.id,event_type="Employment reactivated",event_date=date(2026,1,1),created_at=datetime(2026,1,1,tzinfo=timezone.utc),reason="Rehired")); db.commit()
    rehire_exit = client.post("/api/v1/exit/records",headers=superuser_headers,json={"employee_id":current.id,"last_working_date":"2026-02-01"})
    assert rehire_exit.status_code == 201, rehire_exit.text
    assert db.query(ExitRecord).filter_by(employee_id=current.id).count() == 2


def test_company_scope_and_sensitive_permission_apply_to_all_case_paths(client, db):
    from app.models.company import Company, Branch
    from app.models.user import User, Role, Permission
    from app.core.security import create_access_token
    from test_identity_utils import attach_test_identity, attach_workflow_branch, own_workflow_records
    companies = [Company(name="BGV scope A"), Company(name="BGV scope B")]
    db.add_all(companies); db.flush()
    branches = [Branch(name="BGV branch", company_id=c.id) for c in companies]
    db.add_all(branches); db.flush()
    permissions = [Permission(name=n) for n in ["employee_view", "employee_sensitive_view", "recruitment_view", "recruitment_manage", "exit_view", "exit_manage"]]
    role = Role(name="bgv-scoped-hr", permissions=permissions)
    user = User(email="bgv-scope@example.com", hashed_password="unused", role=role, is_active=True)
    db.add(user); db.flush()
    own = Employee(employee_id="BGV-OWN",first_name="Own",last_name="Employee",date_of_joining=date(2024,1,1),branch_id=branches[0].id,user_id=user.id)
    other = Employee(employee_id="BGV-OTHER",first_name="Other",last_name="Employee",date_of_joining=date(2024,1,1),branch_id=branches[1].id)
    db.add_all([own,other]); db.flush()
    attach_test_identity(db,user,companies[0].id); attach_workflow_branch(db,user,companies[0].id)
    own_workflow_records(db,own,company_id=companies[0].id); own_workflow_records(db,other,company_id=companies[1].id)
    case = Case(employee_id=other.id, package_name="Private case")
    db.add(case); db.commit()
    headers = {"Authorization":"Bearer "+create_access_token(user.id)}
    register = client.get(BASE+"/register",headers=headers)
    assert register.status_code == 200, register.text
    assert [r["id"] for r in register.json()["items"]] == [own.id]
    assert client.get(f"{BASE}/employees/{other.id}/file",headers=headers).status_code == 404
    assert create(client,headers,other).status_code == 404
    assert client.put(f"{BASE}/requests/{case.id}",headers=headers,json={"status":"In Progress"}).status_code == 404
    assert client.get(f"{BASE}/requests/{case.id}/events",headers=headers).status_code == 404
    assert client.get(BASE+"/requests",headers=headers).json() == []
    role.permissions = [p for p in permissions if p.name != "employee_sensitive_view"]; db.commit()
    assert client.get(BASE+"/register",headers=headers).status_code == 403
    assert client.get(BASE+"/requests",headers=headers).status_code == 403


def test_candidate_conversion_links_existing_case_without_duplicate_employee(client, db, superuser_headers):
    from app.models.recruitment import Candidate, Job
    current, _, _ = people(db)
    job = Job(title="Engineer",branch_id=current.branch_id)
    db.add(job); db.flush()
    candidate = Candidate(job_id=job.id, first_name="Candidate", last_name="Converted", email="bgv-candidate@example.com", status="Offered")
    db.add(candidate); db.commit()
    result = client.post(BASE+"/requests",headers=superuser_headers,json={"candidate_id":candidate.id,"package_name":"Hiring checks","checks":[{"check_type":"Identity"}]})
    assert result.status_code == 201,result.text
    verification_id = result.json()["id"]
    converted = client.post(f"/api/v1/recruitment/candidates/{candidate.id}/convert",headers=superuser_headers,json={"employee_id":"BGV-CONVERTED","date_of_joining":"2026-01-01"})
    assert converted.status_code == 201,converted.text
    employee_id = converted.json()["id"]
    db.expire_all(); case = db.get(Case,verification_id)
    assert case.employee_id == employee_id and case.candidate_id == candidate.id
    detail = client.get(f"{BASE}/employees/{employee_id}/file",headers=superuser_headers)
    assert detail.status_code == 200,detail.text
    assert [c["id"] for c in detail.json()["cases"]] == [verification_id]
    duplicate = client.post(f"/api/v1/recruitment/candidates/{candidate.id}/convert",headers=superuser_headers,json={"employee_id":"BGV-DUPLICATE","date_of_joining":"2026-01-01"})
    assert duplicate.status_code == 409, duplicate.text
    assert db.query(Employee).filter(Employee.employee_id == "BGV-DUPLICATE").count() == 0


def test_legacy_archived_employees_remain_in_former_records(client, db, superuser_headers):
    current, former, _ = people(db)
    former.deleted_at = datetime.now(timezone.utc)
    db.commit()
    result = client.get(BASE+"/register",headers=superuser_headers,params={"population":"former"})
    assert result.status_code == 200,result.text
    assert [r["id"] for r in result.json()["items"]] == [former.id]
    detail = client.get(f"{BASE}/employees/{former.id}/file",headers=superuser_headers)
    assert detail.status_code == 200,detail.text
    assert detail.json()["employee"]["archived"] is True
    assert detail.json()["documents"]
    assert create(client,superuser_headers,former).status_code == 201
    db.refresh(former); assert former.deleted_at is not None and former.status == "Resigned"
    active = client.get(BASE+"/register",headers=superuser_headers,params={"population":"current"})
    assert [r["id"] for r in active.json()["items"]] == [current.id]


def test_old_settlement_and_letter_do_not_clear_a_later_exit(client, db, superuser_headers):
    from app.models.exit import ExitRecord
    from app.models.payroll import FullFinalSettlement
    from app.models.document import GeneratedDocument
    _, former, _ = people(db)
    prior = ExitRecord(employee_id=former.id,status="Completed",last_working_date=date(2024,1,1))
    latest = ExitRecord(employee_id=former.id,status="Completed",last_working_date=date(2025,1,1))
    db.add_all([prior,latest]); db.flush()
    db.add(FullFinalSettlement(employee_id=former.id,exit_record_id=prior.id,settlement_date=date(2024,1,1),status="Paid",paid_at=datetime(2024,1,1,tzinfo=timezone.utc)))
    db.add(GeneratedDocument(employee_id=former.id,document_type="Relieving Letter",document_name="Previous period",created_at=datetime(2024,1,1,tzinfo=timezone.utc)))
    db.commit()
    result = client.get(f"{BASE}/employees/{former.id}/file",headers=superuser_headers)
    assert result.status_code == 200,result.text
    assert "Final settlement payment not recorded" in result.json()["missing"]
    assert "Settlement is not linked to the latest exit" in result.json()["missing"]
    assert "Relieving / experience letter missing" in result.json()["missing"]
    assert len(result.json()["exits"]) == 2 and len(result.json()["letters"]) == 1


def test_legacy_profile_summary_is_preserved_when_first_case_starts(client, db, superuser_headers):
    current, _, _ = people(db)
    current.background_verification_status = "Completed"
    current.background_verification_date = date(2024,1,1)
    current.background_verification_agency = "Historical agency"
    db.commit()
    detail = client.get(f"{BASE}/employees/{current.id}/file",headers=superuser_headers).json()
    assert detail["legacy_verification"]["agency"] == "Historical agency"
    row = create(client,superuser_headers,current).json()
    history = client.get(f"{BASE}/requests/{row['id']}/events",headers=superuser_headers).json()
    assert history[0]["payload_json"]["previous_profile_verification"] == {"status":"Completed","date":"2024-01-01","agency":"Historical agency"}
    db.refresh(current); assert current.background_verification_status == "In Progress"


@pytest.mark.skipif(__import__("os").environ.get("RUN_BGV_BROWSER") != "1", reason="Requires Vite on port 5198")
def test_verification_browser_database(client, db, superuser_headers):
    import os, socket, subprocess, threading
    from pathlib import Path
    import uvicorn
    from app.main import app
    from app.models.company import Branch
    current, former, _ = people(db)
    branch = db.get(Branch, current.branch_id)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1",0)); port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,lifespan="off",log_level="error"))
    thread = threading.Thread(target=server.run,daemon=True); thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.05)
        assert server.started
        env = dict(os.environ, BGV_API=f"http://127.0.0.1:{port}", BGV_CURRENT=str(current.id), BGV_FORMER=str(former.id),
                   BGV_TOKEN=superuser_headers["Authorization"].split(" ",1)[1], BGV_COMPANY=str(branch.company_id), BGV_BRANCH=str(branch.id))
        result = subprocess.run(["node","scripts/test-employee-verification.cjs"],cwd=Path(__file__).resolve().parents[2]/"frontend",env=env,capture_output=True,text=True,timeout=240)
        assert result.returncode == 0, result.stdout+result.stderr
        print(result.stdout)
        db.expire_all()
        assert db.query(Case).filter(Case.employee_id.in_([current.id,former.id]), Case.reviewed_at.is_not(None)).count() == 2
    finally:
        server.should_exit = True; thread.join(timeout=10)
