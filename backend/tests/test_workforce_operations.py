from uuid import uuid4
from datetime import timedelta
from tests.test_intern_management import program, publish
from tests.test_interns_hub import interns
from tests.test_intern_applications import application_payload
from app.models.employee import Employee
from app.models.user import User, Role
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.apps.interns_hub.operations_models import WorkforceJob, WorkforceMessage
from app.apps.interns_hub.operations import process_job, scheduled_tick
from app.apps.interns_hub.router import today
from app.apps.project_management.models import PMSTask, PMSTaskAssignee

ROOT = "/api/v1/interns-hub/operations"
PMS = "/api/v1/project-management/operations"


def operation(client, program, **overrides):
    body = dict(operation="warning", employee_ids=[e.id for e, _, _ in program["interns"]],
        title="Please submit your report", message="Send your daily report by 5 PM.", severity="important", request_key=str(uuid4()))
    body.update(overrides)
    response = client.post(ROOT + "/jobs", headers=program["headers"], json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def test_warning_delivery_acknowledgement_resolution_and_idempotency(client, db, program):
    p = program
    job, body = operation(client, p)
    assert job["status"] == "Completed" and job["cursor"] == 2
    assert client.post(ROOT + "/jobs", headers=p["headers"], json=body).json()["id"] == job["id"]
    assert db.query(WorkforceMessage).count() == 2
    assert db.query(Notification).filter_by(event_type="workforce_warning").count() == 2
    e, h, _ = p["interns"][0]
    inbox = client.get(ROOT + "/inbox", headers=h)
    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["unacknowledged"] == 1
    message = inbox.json()["items"][0]
    other_h = p["interns"][1][1]
    assert client.post(ROOT + f"/inbox/{message['id']}/acknowledge", headers=other_h).status_code == 404
    ack = client.post(ROOT + f"/inbox/{message['id']}/acknowledge", headers=h)
    assert ack.status_code == 200 and ack.json()["acknowledged_at"]
    assert ack.json()["resolved_at"] is None
    resolved = client.post(PMS + f"/messages/{message['id']}/resolve", headers=p["headers"], json={"note": "Report received"})
    assert resolved.status_code == 200 and resolved.json()["resolution"] == "Report received"
    history = client.get(PMS + f"/people/{e.id}/history", headers=p["headers"])
    assert history.status_code == 200 and history.json()["total"] == 1


def test_directory_filters_exceptions_pagination_and_employee_support(client, db, program):
    p = program
    e = p["interns"][0][0]
    e.employment_type = "Full-time"
    db.commit()
    job, _ = publish(client, p, target_type="interns", employee_ids=[e.id], batch_ids=[], due_date=str(today()-timedelta(days=1)))
    r = client.get(PMS + "/people", headers=p["headers"], params={"kind": "employee", "exception": "overdue", "per_page": 1})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1 and r.json()["items"][0]["overdue"] == 1
    assert r.json()["items"][0]["id"] == e.id
    assert client.get(ROOT + "/people", headers=p["headers"], params={"search": e.employee_id}).json()["total"] == 1
    notice, _ = operation(client, p, operation="notice", employee_ids=[e.id])
    assert notice["status"] == "Completed"
    assert client.get(ROOT + "/summary", headers=p["headers"]).json()["people"] == db.query(Employee).filter_by(deleted_at=None).count()


def test_reassign_superadmin_and_prevent_reporting_cycles(client, db, program):
    p = program
    admin = p["admin"]
    job, _ = operation(client, p, operation="reassign", reporting_manager_id=-admin.id)
    assert job["status"] == "Completed", job
    manager = db.query(Employee).filter_by(user_id=admin.id).one()
    assert all(db.get(Employee, e.id).reporting_manager_id == manager.id for e, _, _ in p["interns"])
    assert db.query(AuditLog).filter_by(action="UPDATE", description="Bulk supervisor reassignment").count() == 2
    employee = p["interns"][0][0]
    employee.employment_type = "Full-time"
    db.commit()
    result = client.post(ROOT + "/jobs", headers=p["headers"], json={"operation": "reassign", "employee_ids": [manager.id], "reporting_manager_id": employee.id, "request_key": str(uuid4())})
    assert result.status_code == 422


def test_chunk_retry_is_durable_and_access_rechecked(client, db, program):
    p = program
    ids = [e.id for e, _, _ in p["interns"]]
    job = WorkforceJob(organization_id=1, created_by=p["admin"].id, request_key=str(uuid4()), payload_hash="test",
        operation="notice", payload={"title": "Welcome", "message": "Read your program plan", "severity": "normal"}, recipients=ids)
    db.add(job); db.commit()
    process_job(db, job.id, chunk_size=1)
    assert db.get(WorkforceJob, job.id).cursor == 1
    second_user = db.get(User, p["interns"][1][0].user_id)
    second_user.is_active = False
    db.commit()
    process_job(db, job.id)
    assert db.get(WorkforceJob, job.id).status == "Failed"
    assert db.query(WorkforceMessage).filter_by(job_id=job.id).count() == 1
    second_user.is_active = True
    db.commit()
    process_job(db, job.id)
    process_job(db, job.id)
    assert db.get(WorkforceJob, job.id).status == "Completed"
    assert db.query(WorkforceMessage).filter_by(job_id=job.id).count() == 2


def test_management_not_available_to_interns_and_selection_is_atomic(client, db, program):
    p = program
    h = p["interns"][0][1]
    for endpoint in ["/people", "/summary", "/jobs", "/managers"]:
        assert client.get(ROOT + endpoint, headers=h).status_code == 403
    result = client.post(ROOT + "/preview", headers=p["headers"], json={"employee_ids": [p["interns"][0][0].id, 999999]})
    assert result.status_code == 403
    result = client.post(ROOT + "/jobs", headers=p["headers"], json={"operation": "warning", "employee_ids": [], "title": "Test", "message": "Test", "request_key": str(uuid4())})
    assert result.status_code == 422
    assert db.query(WorkforceJob).count() == 0


def test_all_filtered_preview_uses_fixed_recipient_snapshot(client, db, program):
    p = program
    preview = client.post(PMS + "/preview", headers=p["headers"], json={"all_filtered": True, "kind": "intern"})
    assert preview.status_code == 200 and preview.json()["total"] == 2
    job, body = operation(client, p, all_filtered=True, employee_ids=[], kind="intern")
    assert job["total"] == 2
    conflict = client.post(ROOT + "/jobs", headers=p["headers"], json={**body, "title": "Different request"})
    assert conflict.status_code == 409


def test_bulk_onboarding_is_durable_and_reports_individual_failures(client, db, program, application_payload, google_applicant):
    from app.apps.interns_hub.models import InternApplication
    from app.core.security import get_password_hash
    p = program
    google_applicant(application_payload["email"])
    assert client.post("/api/v1/interns-hub/applications", json=application_payload).status_code == 201
    original = db.query(InternApplication).filter_by(email=application_payload["email"]).one()
    details = dict(original.details)
    for i in range(29):
        db.add(InternApplication(organization_id=1, reference=f"BULK-{i}", email=f"bulk{i}@example.com", full_name=f"Bulk Applicant {i}",
            password_hash=original.password_hash, details=details, status="Pending",
            identity_number_encrypted=original.identity_number_encrypted, identity_last4=original.identity_last4))
    # One application now conflicts with an existing account; others must still succeed.
    db.add(User(email="bulk0@example.com", hashed_password=original.password_hash, is_active=True))
    db.commit()
    e = p["interns"][0][0]
    body = {"all_filtered": True, "status": "Pending", "request_key": str(uuid4()), "decision": {
        "status": "Approved", "branch_id": e.branch_id, "department_id": e.department_id, "designation_id": e.designation_id,
        "reporting_manager_user_id": p["admin"].id, "date_of_joining": str(today())}}
    response = client.post("/api/v1/interns-hub/admin/application-jobs", headers=p["headers"], json=body)
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "Pending" and job["cursor"] == 25 and job["total"] == 30, job
    assert job["result"]["succeeded"] == 24 and len(job["result"]["failed"]) == 1
    assert client.post("/api/v1/interns-hub/admin/application-jobs", headers=p["headers"], json=body).json()["id"] == job["id"]
    response = client.post(f"/api/v1/interns-hub/admin/application-jobs/{job['id']}/continue", headers=p["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Completed" and response.json()["result"]["succeeded"] == 29
    assert db.query(InternApplication).filter_by(status="Approved").count() == 29
    intake = client.get("/api/v1/interns-hub/admin/application-intake", headers=p["headers"], params={"status": "Approved", "per_page": 10, "page": 2})
    assert intake.status_code == 200 and intake.json()["total"] == 29 and len(intake.json()["items"]) == 10


def test_directory_paginates_20000_people_without_loading_every_profile(client, db, program):
    from sqlalchemy import event
    p = program
    e = p["interns"][0][0]
    db.bulk_insert_mappings(Employee, [{"employee_id": f"SCALE-{i:05}", "first_name": "Scale", "last_name": str(i),
        "employment_type": "Intern", "status": "Active", "date_of_joining": today(), "branch_id": e.branch_id,
        "department_id": e.department_id} for i in range(20000)])
    db.commit()
    queries = []
    def track(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)
    event.listen(db.bind, "before_cursor_execute", track)
    try:
        response = client.get(ROOT + "/people", headers=p["headers"], params={"search": "SCALE-", "page": 400, "per_page": 50})
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 20000 and len(response.json()["items"]) == 50
        assert len(queries) < 35, f"Directory issued {len(queries)} queries"
    finally:
        event.remove(db.bind, "before_cursor_execute", track)


def test_backup_supervisor_scope_and_view_only_permissions(client, db, program):
    from app.models.user import Permission
    from app.apps.interns_hub.management_models import InternBatch
    p = program
    permission = db.query(Permission).filter_by(name="employee_view").first() or Permission(name="employee_view", module="employees")
    role = Role(name="manager", permissions=[permission])
    db.add(role); db.flush()
    account = User(email="backup-supervisor@example.com", hashed_password=p["admin"].hashed_password, role_id=role.id, is_active=True)
    db.add(account); db.commit()
    response = client.post("/api/v1/auth/login", json={"email": account.email, "password": "Admin@123456"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert client.get(ROOT + "/people", headers=headers).json()["total"] == 0
    batch = db.get(InternBatch, p["batches"][0]); batch.additional_mentors = [account.id, p["admin"].id]
    db.commit()
    result = client.get(ROOT + "/people", headers=headers)
    assert result.status_code == 200 and result.json()["total"] == 2, result.text
    denied = client.post(ROOT + "/jobs", headers=headers, json={"operation": "warning", "employee_ids": [p["interns"][0][0].id],
        "title": "Test", "message": "Test", "request_key": str(uuid4())})
    assert denied.status_code == 403
    batch.additional_mentors = []; db.commit()
    assert client.get(ROOT + "/people", headers=headers).json()["total"] == 0
