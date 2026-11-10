"""Adversarial record and file isolation using real routes and synthetic data."""
from datetime import date

import pytest

from app.core.audit_context import context, set_audit_actor
from app.core.config import settings
from app.core.storage import signed_file_url
from app.models.company import Branch
from app.models.employee import Employee
from app.models.document import GeneratedDocument
from app.models.user import Permission, User
from app.branches.models import BranchGrant, BranchOwnership
from tests.test_company_security_boundary import tenants
from test_identity_utils import complete_workflow_company


@pytest.fixture
def branch_files(db, tenants, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    (tmp_path / "private-evidence.pdf").write_bytes(b"%PDF-1.4\nSynthetic private evidence")
    user = tenants["users"][0]
    first = tenants["branches"][0]
    complete_workflow_company(db, 1)
    user.role.permissions.append(Permission(name="employee_update", module="employees"))
    second = Branch(company_id=1, name="Separate private branch", code="PRIVATE-B")
    db.add(second); db.flush()
    db.add(BranchGrant(company_id=1, user_id=user.id, branch_id=second.id, can_write=True))
    employees = []
    for branch in (first, second):
        employee = Employee(employee_id=f"BRANCH-FILE-{branch.id}", first_name="Synthetic",
                            last_name="Recipient", date_of_joining=date.today(), branch_id=branch.id)
        db.add(employee); db.flush()
        db.add(BranchOwnership(company_id=1, branch_id=branch.id, resource_table="employees",
                               resource_key=str(employee.id), source="explicit-security-fixture"))
        employees.append(employee)
    db.commit()
    user.organization_id = 1
    user._suite_branch_id = first.id
    audit = context.set({})
    try:
        set_audit_actor(user)
        link = signed_file_url(str(tmp_path / "private-evidence.pdf"))
    finally:
        context.reset(audit)
    return tenants["headers"][0], first, second, employees, link


def test_file_reference_cannot_be_rebound_to_another_branch(client, db, branch_files):
    headers, first, second, employees, link = branch_files
    response = client.post("/api/v1/documents/generated", headers={**headers, "X-Suite-Branch": str(second.id)},
                           json={"employee_id": employees[1].id, "document_name": "Cross-branch copy",
                                 "file_url": link})
    assert response.status_code == 403, response.text
    assert db.query(GeneratedDocument).count() == 0


def test_same_branch_file_reference_remains_usable(client, db, branch_files):
    headers, first, second, employees, link = branch_files
    response = client.post("/api/v1/documents/generated", headers=headers,
                           json={"employee_id": employees[0].id, "document_name": "Allowed attachment",
                                 "file_url": link})
    assert response.status_code == 201, response.text
    assert db.query(GeneratedDocument).count() == 1


@pytest.mark.parametrize("change", ["delete", "replace", "move_branch", "reassign_employee"])
def test_document_download_rechecks_its_source_record(client, db, branch_files, change):
    from test_identity_utils import own_workflow_records

    headers, first, second, employees, upload_link = branch_files
    document = GeneratedDocument(employee_id=employees[0].id, document_name="Private evidence",
                                  file_url="/uploads/private-evidence.pdf")
    db.add(document); db.flush()
    own_workflow_records(db, document)
    db.commit()
    listing = client.get("/api/v1/documents/generated", headers=headers)
    assert listing.status_code == 200, listing.text
    link = next(row["file_url"] for row in listing.json() if row["id"] == document.id)
    allowed = client.get(link)
    assert allowed.status_code == 200, allowed.text
    if change == "delete":
        db.delete(document)
    elif change == "replace":
        document.file_url = "/uploads/replacement.pdf"
    elif change == "move_branch":
        db.get(BranchOwnership, (document.__tablename__, str(document.id))).branch_id = second.id
    else:
        document.employee_id = employees[1].id
    db.commit()
    denied = client.get(link)
    assert denied.status_code == 403, denied.text


def test_document_capability_rechecks_own_record_scope_without_policy_change(client, db, branch_files):
    from app.access.models import AccessPolicy
    from test_identity_utils import own_workflow_records

    headers, first, second, employees, upload_link = branch_files
    user = db.query(User).filter_by(email="alpha@example.com").one()
    employees[0].user_id = user.id
    grants = {"hrms": {"enabled": True, "role": "custom", "permissions": ["employee_view", "employee_update"],
                        "actions": ["view", "create", "edit"], "scope": "own"}}
    policy = AccessPolicy(company_id=1, user_id=user.id, status="active", grants=grants, version=1)
    db.add(policy)
    document = GeneratedDocument(employee_id=employees[0].id, document_name="Own record",
                                  file_url="/uploads/private-evidence.pdf")
    db.add(document); db.flush(); own_workflow_records(db, document)
    db.commit()
    db.expire(user, ["employee"])
    response = client.get("/api/v1/documents/generated", headers=headers)
    assert response.status_code == 200, response.text
    link = response.json()[0]["file_url"]
    assert client.get(link).status_code == 200
    employees[0].user_id = None
    db.commit()
    assert policy.version == 1
    assert client.get(link).status_code == 403


@pytest.mark.parametrize("method,suffix,body", [
    ("GET", "", None), ("PATCH", "", {"title": "Unauthorized edit"}), ("DELETE", "", None),
    ("GET", "/comments", None), ("GET", "/attachments", None),
    ("POST", "/comments", {"body": "Unauthorized comment"}),
])
def test_valid_task_operations_do_not_cross_companies(client, db, tenants, method, suffix, body):
    foreign = tenants["tasks"][1]
    response = client.request(method, f"/api/v1/project-management/tasks/{foreign.id}{suffix}",
                              headers=tenants["headers"][0], json=body)
    assert response.status_code in {403, 404}, response.text
    db.refresh(foreign)
    assert foreign.deleted_at is None and foreign.title != "Unauthorized edit"


def test_record_scope_filters_details_lists_search_and_exports(client, db, tenants):
    from app.access.models import AccessPolicy
    from app.apps.crm.models import CRMLead
    from test_identity_utils import complete_workflow_company

    user = tenants["users"][0]
    complete_workflow_company(db, 1)
    hidden = CRMLead(organization_id=1, first_name="SCOPE-CANARY", full_name="SCOPE-CANARY",
                      owner_user_id=tenants["users"][2].id)
    db.add(hidden); db.flush()
    db.add(BranchOwnership(company_id=1, branch_id=tenants["branches"][0].id,
                           resource_table=hidden.__tablename__, resource_key=str(hidden.id),
                           source="explicit-security-fixture"))
    db.add(AccessPolicy(company_id=1, user_id=user.id, status="active", grants={
        "crm": {"enabled": True, "role": "custom", "permissions": ["crm_view", "crm_manage"],
                "actions": ["view", "create", "edit", "delete", "export"], "scope": "own"}}))
    db.commit()
    headers = tenants["headers"][0]
    assert client.get(f"/api/v1/crm/leads/{tenants['leads'][0].id}", headers=headers).status_code == 200
    for path in ["/api/v1/crm/leads", "/api/v1/crm/leads?search=SCOPE-CANARY", "/api/v1/crm/leads/export"]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert "SCOPE-CANARY" not in response.text
    assert client.get(f"/api/v1/crm/leads/{hidden.id}", headers=headers).status_code == 404
    assert client.put(f"/api/v1/crm/leads/{hidden.id}", headers=headers,
                       json={"first_name": "Tampered"}).status_code in {403, 404}


@pytest.fixture
def branch_records(db, branch_files):
    from app.apps.crm.models import CRMLead
    from app.apps.project_management.models import PMSProject, PMSTask

    headers, first, second, employees, link = branch_files
    user = db.query(User).filter_by(email="alpha@example.com").one()
    lead = CRMLead(organization_id=1, first_name="BRANCH-CANARY", full_name="BRANCH-CANARY", owner_user_id=user.id)
    project = PMSProject(organization_id=1, name="BRANCH-CANARY", project_key="PRIV-B", manager_user_id=user.id)
    db.add_all([lead, project]); db.flush()
    task = PMSTask(project_id=project.id, title="BRANCH-CANARY", task_key="PRIV-B-1", reporter_user_id=user.id)
    db.add(task); db.flush()
    for row in (lead, project, task):
        db.add(BranchOwnership(company_id=1, branch_id=second.id, resource_table=row.__tablename__,
                               resource_key=str(row.id), source="explicit-security-fixture"))
    db.commit()
    return headers, second, lead, task


@pytest.mark.parametrize("kind,method", [(kind, method) for kind in ("lead", "task")
                                       for method in ("GET", "PATCH", "DELETE")])
def test_selected_branch_constrains_otherwise_authorized_record_operations(client, db, branch_records, kind, method):
    headers, branch, lead, task = branch_records
    row = lead if kind == "lead" else task
    path = f"/api/v1/crm/leads/{row.id}" if kind == "lead" else f"/api/v1/project-management/tasks/{row.id}"
    # The user really has authority in the other branch, but must explicitly enter it.
    assert client.get(path, headers={**headers, "X-Suite-Branch": str(branch.id)}).status_code == 200
    if kind == "lead" and method == "PATCH":
        method = "PUT"
    response = client.request(method, path, headers=headers,
                              json={"first_name": "Unauthorized", "title": "Unauthorized"} if method in {"PUT", "PATCH"} else None)
    assert response.status_code in {403, 404}, response.text
    db.refresh(row)
    assert row.deleted_at is None


def test_mixed_branch_bulk_action_is_atomic(client, db, tenants, branch_records):
    from app.apps.project_management.models import PMSTask

    headers, branch, lead, hidden_task = branch_records
    own = tenants["tasks"][0]
    result = client.patch("/api/v1/project-management/tasks/bulk", headers=headers,
                           json={"task_ids": [own.id, hidden_task.id], "priority": "High"})
    assert result.status_code in {403, 404}, result.text
    db.expire_all()
    assert db.get(PMSTask, own.id).priority != "High"
    assert db.get(PMSTask, hidden_task.id).priority != "High"


def test_pre_hardening_file_links_require_record_reauthorization(client, branch_files):
    import jwt
    from urllib.parse import parse_qs, urlsplit

    headers, first, second, employees, link = branch_files
    claims = jwt.decode(parse_qs(urlsplit(link).query)["token"][0], settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM], audience="private-file")
    claims.pop("capability_version")
    legacy = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = client.get("/api/v1/files/blob", params={"token": legacy})
    assert response.status_code == 403
    assert "open the record again" in response.json()["detail"]
