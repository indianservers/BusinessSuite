from datetime import date, datetime, timedelta, timezone
import json

from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.rich_text_test_utils import organization_context
from app.models.user import Role, Permission, UserSession
from app.models.audit import AuditLog
from app.models.approval_os import ApprovalRequest
from app.apps.project_management.models import PMSWorkspaceMember, PMSProjectMember, PMSProject, PMSTask
from app.core.security import get_password_hash

ROOT = BASE + "/people-management"


def make_hr(db):
    actor, headers = account(db, "people-hr@test.com")
    role = db.query(Role).filter_by(name="hr").first()
    if not role:
        role = Role(name="hr"); db.add(role)
    permission = db.query(Permission).filter_by(name="employee_update").first()
    if not permission:
        permission = Permission(name="employee_update", module="employees"); db.add(permission)
    if permission not in role.permissions:
        role.permissions.append(permission)
    actor.role = role
    db.commit()
    return actor, headers


def project_fixture(client, db):
    owner, oh = account(db, "people-owner@test.com", True)
    target, th = account(db, "people-target@test.com")
    replacement, rh = account(db, "people-replacement@test.com")
    wid = client.post(BASE + "/workspaces", headers=oh, json={"name": "People test workspace"}).json()["id"]
    pid = client.post(BASE + "/projects", headers=oh, json={"name": "People project", "project_key": "PEO", "workspace_id": wid}).json()["id"]
    for user in (target, replacement):
        db.add(PMSWorkspaceMember(workspace_id=wid, user_id=user.id, role="Member"))
        db.add(PMSProjectMember(project_id=pid, user_id=user.id, role="Member"))
    db.commit()
    task = client.post(f"{BASE}/projects/{pid}/tasks", headers=oh, json={"title": "Hand over delivery", "task_key": "PEO-1", "assignee_user_ids": [target.id]}).json()
    return owner, oh, target, th, replacement, rh, wid, pid, task["id"]


def test_hr_direct_add_and_bulk_atomic_scope(client, db):
    owner, oh = account(db, "bulk-owner@test.com", True)
    actor, ah = make_hr(db)
    target, _ = account(db, "bulk-target@test.com")
    foreign, _ = account(db, "bulk-foreign@test.com")
    foreign.person.organization_id = 2; db.commit()
    wid = client.post(BASE + "/workspaces", headers=oh, json={"name": "HR managed workspace"}).json()["id"]
    pid = client.post(BASE + "/projects", headers=oh, json={"name": "HR managed project", "project_key": "HRP", "workspace_id": wid}).json()["id"]
    assert client.get(f"{BASE}/workspaces/{wid}/members", headers=ah).status_code == 200
    assert not db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=actor.id).first()
    result = client.post(ROOT + "/memberships/bulk", headers=ah, json={"user_ids": [target.id], "workspace_ids": [wid], "project_ids": [pid], "reason": "HR staffed project"})
    assert {row["destination_type"] for row in result.json()["results"]} == {"workspace", "project"}
    assert all(row["status"] == "added" and row["email"] == target.email for row in result.json()["results"])
    assert result.status_code == 200, result.text
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=target.id).one().role == "Member"
    assert db.query(PMSProjectMember).filter_by(project_id=pid, user_id=target.id).one()
    options = client.get(ROOT + "/assignment-options", headers=ah, params={"project_id":pid}).json()
    assert options["can_add_existing"]
    assert any(p["id"] == target.id and p["availability"] for p in options["items"])
    assert client.get(ROOT + f"/{foreign.id}", headers=ah).status_code == 404
    before = db.query(PMSWorkspaceMember).count()
    result = client.post(ROOT + "/memberships/bulk", headers=ah, json={"user_ids": [actor.id, foreign.id], "workspace_ids": [wid], "reason": "Invalid mixed company request"})
    assert result.status_code == 404
    assert db.query(PMSWorkspaceMember).count() == before


def test_preview_required_reassignment_and_effective_access(client, db):
    owner, oh, target, th, replacement, rh, wid, pid, tid = project_fixture(client, db)
    outsider, xh = account(db, "people-outsider@test.com")
    assert client.get(ROOT + f"/{target.id}", headers=xh).status_code == 403
    detail = client.get(ROOT + f"/{target.id}", headers=oh)
    assert detail.status_code == 200, detail.text
    sources = detail.json()["access_sources"]
    assert {s["source"] for s in sources} == {"Organization role", "Workspace membership", "Project role"}
    assert detail.json()["permissions"]["suspend"]
    endpoint = ROOT + f"/{target.id}/actions"
    payload = {"action":"remove_project", "project_id":pid, "reason":"Transfer this project responsibility"}
    assert client.post(endpoint, headers=oh, json=payload).status_code == 409
    preview = client.get(ROOT + f"/{target.id}/preview", headers=oh, params={"project_id":pid}).json()
    assert preview["tasks"][0]["id"] == tid
    assert client.post(endpoint, headers=oh, json={**payload, "preview_version":preview["version"]}).status_code == 422
    result = client.post(endpoint, headers=oh, json={**payload, "preview_version":preview["version"], "replacement_user_id":replacement.id})
    assert result.status_code == 200, result.text
    db.expire_all()
    assert db.get(PMSTask, tid).assignee_user_ids == [replacement.id]
    assert not db.query(PMSProjectMember).filter_by(project_id=pid, user_id=target.id).first()
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=target.id).first()
    assert any(h["action"] == "PMS_REMOVE_PROJECT" for h in client.get(ROOT + f"/{target.id}", headers=oh).json()["history"])


def test_stale_preview_and_temporary_suspension_reactivation(client, db):
    owner, oh, target, th, replacement, rh, wid, pid, tid = project_fixture(client, db)
    target.hashed_password = get_password_hash("People@12345"); db.commit()
    preview = client.get(ROOT + f"/{target.id}/preview", headers=oh).json()
    task = db.get(PMSTask, tid); task.title = "Changed after preview"; db.commit()
    payload = {"action":"suspend", "reason":"Temporary leave", "preview_version":preview["version"], "replacement_user_id":replacement.id, "end_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    assert client.post(ROOT + f"/{target.id}/actions", headers=oh, json=payload).status_code == 409
    preview = client.get(ROOT + f"/{target.id}/preview", headers=oh).json()
    result = client.post(ROOT + f"/{target.id}/actions", headers=oh, json={**payload, "preview_version":preview["version"]})
    assert result.status_code == 200, result.text
    db.refresh(target); assert not target.is_active
    assert client.get(BASE + "/workspaces", headers=th).status_code == 403
    assert client.post("/api/v1/auth/login", json={"email":target.email,"password":"People@12345"}).status_code == 403
    past = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    target.person.external_refs_json = {**target.person.external_refs_json, "pms_suspension": {**target.person.external_refs_json["pms_suspension"], "end_at":past}}
    audit = db.query(AuditLog).filter_by(entity_type="user", entity_id=target.id, action="ACCOUNT_SUSPEND").order_by(AuditLog.id.desc()).first()
    audit.new_values = json.dumps({**json.loads(audit.new_values), "end_at":past}); db.commit()
    result = client.post("/api/v1/auth/login", json={"email":target.email,"password":"People@12345"})
    assert result.status_code == 200, result.text
    db.refresh(target); assert target.is_active
    assert target.person.external_refs_json["pms_suspension"] is None


def test_profile_field_permissions_and_organization_audit(client, db):
    owner, oh, target, th, replacement, rh, wid, pid, tid = project_fixture(client, db)
    actor, ah = make_hr(db)
    result = client.get(ROOT + f"/{target.id}", headers=ah)
    assert result.status_code == 200, result.text
    profile = result.json()["profile"]
    assert profile["field_permissions"]["preferred_display_name"]["can_edit"]
    patch = {"version":profile["version"], "values":{"preferred_display_name":"Delivery specialist"}, "reason":"Correct directory display name"}
    result = client.patch(ROOT + f"/{target.id}/profile", headers=ah, json=patch)
    assert result.status_code == 200, result.text
    assert client.patch(ROOT + f"/{target.id}/profile", headers=rh, json=patch).status_code == 403
    detail = client.get(ROOT + f"/{target.id}", headers=ah).json()
    assert any(h["action"] == "PMS_PROFILE_EDIT" for h in detail["history"])
    assert client.post(ROOT + f"/{owner.id}/actions", headers=ah, json={"action":"suspend", "reason":"Cannot suspend protected administrator"}).status_code == 403
    from app.apps.admin_security.models import AdminProfile, AdminFieldSecurity
    rules = AdminProfile(name="hr", active=True); db.add(rules); db.flush()
    db.add(AdminFieldSecurity(profile_id=rules.id, module_name="employees", field_name="preferred_display_name", can_view=True, can_edit=False)); db.commit()
    detail = client.get(ROOT + f"/{target.id}", headers=ah).json()
    assert not detail["profile"]["field_permissions"]["preferred_display_name"]["can_edit"]
    assert client.patch(ROOT + f"/{target.id}/profile", headers=ah, json={**patch, "version": detail["profile"]["version"]}).status_code == 403


def test_offboarding_transfers_ownership_and_approvals(client, db):
    owner, oh, target, th, replacement, rh, wid, pid, tid = project_fixture(client, db)
    role = Role(name="admin"); db.add(role); replacement.role=role
    member = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=replacement.id).one(); member.role="Admin"
    project = db.get(PMSProject, pid); project.owner_user_id=target.id; project.manager_user_id=target.id
    approval = ApprovalRequest(organization_id=1, source_module="pms", approval_type="delivery", entity_type="project", entity_id=pid, title="Approve launch", assigned_to_user_id=target.id, status="Pending")
    db.add(approval); db.commit()
    preview = client.get(ROOT + f"/{target.id}/preview", headers=oh).json()
    assert preview["projects"][0]["id"] == pid
    assert preview["approvals"][0]["id"] == approval.id
    result = client.post(ROOT + f"/{target.id}/actions", headers=oh, json={"action":"offboard", "reason":"Transfer departing colleague responsibilities", "replacement_user_id":replacement.id, "preview_version":preview["version"]})
    assert result.status_code == 200, result.text
    db.expire_all()
    assert db.get(PMSProject,pid).owner_user_id == replacement.id
    assert db.get(ApprovalRequest,approval.id).assigned_to_user_id == replacement.id
    assert db.get(PMSTask,tid).assignee_user_ids == [replacement.id]
    assert not db.query(PMSWorkspaceMember).filter_by(user_id=target.id).first()
    assert not target.is_active


def test_termination_and_reactivation_are_distinct(client, db):
    from app.models.employee import Employee
    owner, oh = account(db, "terminate-owner@test.com", True)
    target, _ = account(db, "terminate-person@test.com")
    employee = Employee(user_id=target.id, employee_id="PMS-LIFECYCLE-1", first_name="Delivery", last_name="Person", date_of_joining=date(2026,1,1), status="Active")
    db.add(employee); db.commit()
    detail = client.get(ROOT + f"/{target.id}", headers=oh).json()
    assert detail["permissions"]["terminate"]
    preview = client.get(ROOT + f"/{target.id}/preview", headers=oh).json()
    result = client.post(ROOT + f"/{target.id}/actions", headers=oh, json={"action":"terminate", "reason":"Employment ended after completed handover", "preview_version":preview["version"]})
    assert result.status_code == 200, result.text
    db.refresh(employee); db.refresh(target)
    assert employee.status == "Terminated" and employee.date_of_exit is not None and not target.is_active
    assert client.post(ROOT + f"/{target.id}/actions", headers=oh, json={"action":"reactivate", "reason":"Cannot bypass HR rehire process"}).status_code == 409
    statuses = client.get(ROOT + "/directory", headers=oh, params={"status":"terminated"}).json()
    assert statuses["counts"]["terminated"] == 1 and statuses["items"][0]["id"] == target.id
