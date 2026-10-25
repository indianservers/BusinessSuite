import copy
import pytest
from datetime import datetime, timezone
from app.access.models import AccessPolicy, AccessAudit, AccessMembership, AccessRole
from app.models.user import User, Role, Permission
from app.models.company import Company
from app.common.models import CommonPerson
from app.core.security import get_password_hash

ROOT = "/api/v1/access"


@pytest.fixture
def access_account(db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Main company"))
        db.flush()
    permissions = []
    for name in [
        "crm_view",
        "crm_manage",
        "crm_admin",
        "pms_view",
        "pms_manage_tasks",
        "fam_view",
        "fam_export",
        "employee_view",
    ]:
        permission = db.query(Permission).filter_by(name=name).first()
        if not permission:
            permission = Permission(name=name, module=name.split("_")[0])
            db.add(permission)
        permissions.append(permission)
    role = Role(name="access_employee", permissions=permissions)
    db.add(role)
    db.flush()
    user = User(
        email="access.employee@example.com",
        hashed_password=get_password_hash("Sales@123456"),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        CommonPerson(
            user_id=user.id,
            organization_id=1,
            display_name="Access Employee",
            status="active",
        )
    )
    db.commit()
    return user


def login(client, email="access.employee@example.com", module=None):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Sales@123456", "module": module},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def secure(client, headers):
    response = client.post(
        ROOT + "/step-up", headers=headers, json={"password": "Admin@123456"}
    )
    assert response.status_code == 200, response.text
    return {**headers, "X-Access-Step-Up": response.json()["token"]}


def grant(client, headers, module="crm", tier="viewer"):
    response = client.get(ROOT + "/catalog", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["presets"][module][tier]


def apply(client, headers, user, grants, version=0, **extra):
    return client.post(
        ROOT + "/changes/apply",
        headers=headers,
        json={
            "companyId": 1,
            "changes": [
                {"userId": user.id, "version": version, "grants": grants, **extra}
            ],
            "reason": "Access security regression",
        },
    )


def test_catalog_discovers_modules_and_routes(
    client, access_account, superuser_headers
):
    result = client.get(ROOT + "/catalog", headers=superuser_headers)
    assert result.status_code == 200, result.text
    modules = {m["key"]: m for m in result.json()["modules"]}
    assert {
        "crm",
        "hrms",
        "project_management",
        "srm",
        "fam",
        "forms",
        "automation",
        "ai",
        "security",
        "interns_hub",
    } <= set(modules)
    assert modules["crm"]["routeCount"] > 50
    assert any(p["name"] == "crm_view" for p in modules["crm"]["permissions"])


def test_grant_revoke_persists_and_invalidates_live_session(
    client, db, access_account, superuser_headers
):
    old = login(client)
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    result = apply(client, headers, access_account, {"crm": g})
    assert result.status_code == 200, result.text
    assert client.get(ROOT + "/me", headers=old).status_code == 401
    fresh = login(client, module="crm")
    data = client.get(ROOT + "/me", headers=fresh).json()
    assert data["managed"] and data["grants"]["crm"]["enabled"]
    assert (
        client.get("/api/v1/crm/lead-management/leads", headers=fresh).status_code
        == 200
    )
    version = result.json()["results"][0]["user"]["version"]
    revoked = apply(
        client, headers, access_account, {"crm": {**g, "enabled": False}}, version
    )
    assert revoked.status_code == 200, revoked.text
    fresh = login(client)
    assert (
        client.get("/api/v1/crm/lead-management/leads", headers=fresh).status_code
        == 403
    )
    assert (
        db.query(AccessAudit)
        .filter_by(target_id=access_account.id, operation="access.updated")
        .count()
        == 2
    )


def test_granular_actions_and_record_scope_are_enforced(
    client, db, access_account, superuser_headers
):
    from app.apps.crm.models import CRMLead

    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    db.add_all(
        [
            CRMLead(
                first_name="Own",
                full_name="Own",
                organization_id=1,
                owner_user_id=access_account.id,
                status="New",
            ),
            CRMLead(
                first_name="Secret",
                full_name="Secret",
                organization_id=1,
                owner_user_id=None,
                status="New",
            ),
        ]
    )
    db.commit()
    response = apply(
        client,
        headers,
        access_account,
        {"crm": g, "fam": {**grant(client, headers, "fam"), "enabled": False}},
    )
    assert response.status_code == 200, response.text
    own = login(client)
    listed = client.get("/api/v1/crm/lead-management/leads", headers=own)
    assert listed.status_code == 200, listed.text
    assert [r["full_name"] for r in listed.json()["items"]] == ["Own"]
    assert (
        client.post(
            "/api/v1/crm/lead-management/leads",
            headers=own,
            json={"values": {"full_name": "Blocked"}},
        ).status_code
        == 403
    )
    assert (
        client.get("/api/v1/crm/lead-management/excel/export", headers=own).status_code
        == 403
    )
    assert client.get("/api/v1/fam/dashboard", headers=own).status_code == 403


def test_bulk_is_atomic_and_stale_versions_are_rejected(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    payload = {
        "companyId": 1,
        "reason": "Bulk access update",
        "changes": [
            {"userId": access_account.id, "version": 0, "grants": {"crm": g}},
            {"userId": 999999, "version": 0, "grants": {"crm": g}},
        ],
    }
    assert (
        client.post(ROOT + "/changes/apply", headers=headers, json=payload).status_code
        == 404
    )
    assert not db.query(AccessPolicy).filter_by(user_id=access_account.id).first()
    payload["atomic"] = False
    partial = client.post(ROOT + "/changes/apply", headers=headers, json=payload)
    assert partial.status_code == 200, partial.text
    assert partial.json()["updated"] == 1 and len(partial.json()["results"]) == 2
    assert apply(client, headers, access_account, {"crm": g}).status_code == 409


def test_last_superadmin_is_protected_and_stepup_required(
    client, db, access_account, superuser_headers
):
    g = grant(client, superuser_headers)
    assert (
        apply(client, superuser_headers, access_account, {"crm": g}).status_code == 403
    )
    admin = db.query(User).filter_by(is_superuser=True).one()
    headers = secure(client, superuser_headers)
    assert apply(client, headers, admin, {}, status="suspended").status_code == 409
    db.refresh(admin)
    assert admin.is_active and admin.is_superuser
    bad = client.post(
        ROOT + "/step-up", headers=superuser_headers, json={"password": "wrong"}
    )
    assert bad.status_code == 403


def test_ordinary_user_cannot_administer_or_escalate(
    client, access_account, superuser_headers
):
    headers = login(client)
    assert client.get(ROOT + "/users", headers=headers).status_code == 403
    assert (
        client.post(
            ROOT + "/memberships",
            headers=headers,
            json={
                "companyId": 1,
                "userId": access_account.id,
                "isAdmin": True,
                "reason": "self escalate",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "email": "escalation@example.com",
                "password": "Admin@123456",
                "is_superuser": True,
            },
        ).status_code
        == 403
    )


def test_custom_roles_templates_and_role_impact(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    role = client.post(
        ROOT + "/roles",
        headers=headers,
        json={
            "companyId": 1,
            "module": "crm",
            "name": "Account Viewer",
            "permissions": g["permissions"],
            "actions": ["view"],
            "scope": "own",
            "reason": "Create scoped role",
        },
    )
    assert role.status_code == 200, role.text
    assigned = apply(
        client,
        headers,
        access_account,
        {
            "crm": {
                **g,
                "roleId": role.json()["id"],
                "roleVersion": role.json()["version"],
            },
            "project_management": grant(
                client, headers, "project_management", "contributor"
            ),
        },
    )
    assert assigned.status_code == 200, assigned.text
    own = login(client)
    me = client.get(ROOT + "/me", headers=own).json()
    assert (
        me["grants"]["crm"]["role"] == "Account Viewer"
        and me["grants"]["project_management"]["role"] == "contributor"
    )
    users = client.get(
        ROOT + f"/roles/{role.json()['id']}/users",
        params={"companyId": 1},
        headers=headers,
    )
    assert users.json()["items"][0]["id"] == access_account.id
    retire = {
        "companyId": 1,
        "module": "crm",
        "name": "Account Viewer",
        "permissions": g["permissions"],
        "actions": ["view"],
        "scope": "own",
        "active": False,
        "version": role.json()["version"],
        "reason": "Retire used role",
    }
    assert (
        client.put(
            ROOT + f"/roles/{role.json()['id']}", headers=headers, json=retire
        ).status_code
        == 409
    )
    template = client.post(
        ROOT + "/templates",
        headers=headers,
        json={
            "companyId": 1,
            "name": "CRM viewer preset",
            "grants": {"crm": g},
            "reason": "Create access template",
        },
    )
    assert template.status_code == 200, template.text
    assert template.json()["version"] == 1
    assert client.get(ROOT + "/templates", headers=headers).json()["items"]


def test_company_memberships_are_explicit_and_policies_independent(
    client, db, access_account, superuser_headers
):
    db.add(Company(id=2, name="Second company"))
    db.commit()
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    assert (
        client.get(
            ROOT + "/me", headers={**login(client), "X-Suite-Organization": "2"}
        ).status_code
        == 403
    )
    membership = client.post(
        ROOT + "/memberships",
        headers=headers,
        json={
            "companyId": 2,
            "userId": access_account.id,
            "reason": "Authorized second company",
        },
    )
    assert membership.status_code == 200, membership.text
    response = client.post(
        ROOT + "/changes/apply",
        headers=headers,
        json={
            "companyId": 2,
            "reason": "Company two CRM",
            "changes": [
                {"userId": access_account.id, "version": 1, "grants": {"crm": g}}
            ],
        },
    )
    assert response.status_code == 200, response.text
    own = login(client)
    me = client.get(ROOT + "/me", headers={**own, "X-Suite-Organization": "2"})
    assert me.status_code == 200, me.text
    assert me.json()["companyId"] == 2 and me.json()["grants"]["crm"]["enabled"]
    assert not client.get(ROOT + "/me", headers=own).json()["managed"]


def test_invitation_uses_existing_reset_and_starts_with_no_modules(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    response = client.post(
        ROOT + "/users",
        headers=headers,
        json={
            "companyId": 1,
            "name": "New Colleague",
            "email": "invited@example.com",
            "invite": True,
            "reason": "Invite new colleague",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["delivery"] == "manual" and body["user"]["moduleCount"] == 0
    accepted = client.post(
        "/api/v1/auth/reset-password",
        json={"token": body["invitationToken"], "new_password": "Sales@123456"},
    )
    assert accepted.status_code == 200, accepted.text
    own = login(client, "invited@example.com")
    assert (
        client.get("/api/v1/crm/lead-management/leads", headers=own).status_code == 403
    )


def test_suspension_and_native_permission_validation(
    client, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    assert (
        apply(
            client,
            headers,
            access_account,
            {"crm": {**g, "permissions": ["payroll_run"]}},
        ).status_code
        == 422
    )
    assert (
        apply(
            client, headers, access_account, {"crm": g}, status="suspended"
        ).status_code
        == 200
    )
    assert client.get(ROOT + "/me", headers=login(client)).status_code == 403


@pytest.mark.parametrize(
    "scope,expected",
    [
        ("own", 1),
        ("assigned", 1),
        ("team", 2),
        ("department", 2),
        ("branch", 3),
        ("organization", 4),
    ],
)
def test_all_crm_record_scopes(
    client, db, access_account, superuser_headers, scope, expected
):
    from datetime import date
    from app.models.employee import Employee
    from app.models.company import Branch, Department
    from app.apps.crm.models import CRMLead

    first = Branch(name="HQ", company_id=1)
    second = Branch(name="Other", company_id=1)
    db.add_all([first, second])
    db.flush()
    a = Department(name="Sales", branch_id=first.id)
    b = Department(name="Finance", branch_id=first.id)
    c = Department(name="Remote", branch_id=second.id)
    db.add_all([a, b, c])
    db.flush()
    boss = Employee(
        employee_id="ACCESS-1",
        user_id=access_account.id,
        first_name="Boss",
        last_name="Manager",
        date_of_joining=date.today(),
        branch_id=first.id,
        department_id=a.id,
    )
    db.add(boss)
    db.flush()
    owners = [access_account]
    for i, (branch, dept) in enumerate([(first, a), (first, b), (second, c)], 2):
        user = User(
            email=f"scope{i}@example.com",
            hashed_password=access_account.hashed_password,
            is_active=True,
            role_id=access_account.role_id,
        )
        db.add(user)
        db.flush()
        db.add(
            CommonPerson(
                user_id=user.id,
                organization_id=1,
                display_name=f"Scope {i}",
                status="active",
            )
        )
        db.add(
            Employee(
                employee_id=f"ACCESS-{i}",
                user_id=user.id,
                first_name=f"Scope {i}",
                last_name="Employee",
                date_of_joining=date.today(),
                branch_id=branch.id,
                department_id=dept.id,
                reporting_manager_id=boss.id if i == 2 else None,
            )
        )
        owners.append(user)
    for i, user in enumerate(owners):
        db.add(
            CRMLead(
                first_name=f"Lead{i}",
                full_name=f"Lead{i}",
                owner_user_id=user.id,
                organization_id=1,
                status="New",
            )
        )
    db.commit()
    headers = secure(client, superuser_headers)
    g = {**grant(client, headers), "scope": scope}
    assert apply(client, headers, access_account, {"crm": g}).status_code == 200
    response = client.get("/api/v1/crm/lead-management/leads", headers=login(client))
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == expected


def test_worker_checks_revocation_and_data_scope(
    client, db, access_account, superuser_headers
):
    from app.access.service import check_background_access, background_scope
    from app.apps.crm.models import CRMLead
    from fastapi import HTTPException

    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    assert apply(client, headers, access_account, {"crm": g}).status_code == 200
    with pytest.raises(HTTPException):
        check_background_access(db, access_account, "crm", "create")
    db.add(
        CRMLead(
            first_name="Private", full_name="Private", organization_id=1, status="New"
        )
    )
    db.commit()
    with background_scope(db, access_account, "crm", "view"):
        assert db.query(CRMLead).count() == 0
    policy = db.query(AccessPolicy).filter_by(user_id=access_account.id).one()
    policy.grants = {**policy.grants, "crm": {**g, "enabled": False}}
    db.commit()
    with pytest.raises(HTTPException):
        check_background_access(db, access_account, "crm", "view")


def test_intern_only_receives_explicit_restricted_project_access(
    client, db, access_account, superuser_headers
):
    access_account.role.name = "intern"
    access_account.role.permissions = [
        p for p in access_account.role.permissions if p.name.startswith("pms_")
    ]
    db.commit()
    headers = secure(client, superuser_headers)
    g = grant(client, headers, "project_management", "contributor")
    assert "pms_manage_tasks" in g["permissions"]
    allowed = apply(
        client,
        headers,
        access_account,
        {"project_management": {**g, "scope": "assigned"}},
    )
    assert allowed.status_code == 200, allowed.text
    own = login(client, module="pms")
    me = client.get(ROOT + "/me", headers=own)
    assert me.status_code == 200, me.text
    assert client.get("/api/v1/employees", headers=own).status_code == 403
    version = allowed.json()["results"][0]["user"]["version"]
    assert (
        apply(
            client,
            headers,
            access_account,
            {"hrms": grant(client, headers, "hrms")},
            version,
        ).status_code
        == 422
    )


def test_templates_apply_with_version_and_preserve_other_grants(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    template = client.post(
        ROOT + "/templates",
        headers=headers,
        json={
            "companyId": 1,
            "name": "Sales template",
            "grants": {"crm": g},
            "reason": "Sales access template",
        },
    ).json()
    payload = {
        "companyId": 1,
        "reason": "Apply sales template",
        "templateId": template["id"],
        "templateVersion": template["version"],
        "changes": [
            {"userId": access_account.id, "version": 0, "grants": template["grants"]}
        ],
    }
    response = client.post(ROOT + "/changes/apply", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]["user"]
    assert result["grants"]["crm"]["enabled"] and result["grants"]["fam"]["enabled"]
    payload["templateVersion"] = 0
    payload["changes"][0]["version"] = result["version"]
    assert (
        client.post(ROOT + "/changes/apply", headers=headers, json=payload).status_code
        == 409
    )


def test_assigned_pms_tasks_and_other_submission_rows_are_filtered(
    client, db, access_account, superuser_headers
):
    from app.apps.project_management.models import (
        PMSProject,
        PMSProjectMember,
        PMSTask,
        PMSTaskAssignee,
    )
    from app.access.service import background_scope

    admin = db.query(User).filter_by(is_superuser=True).one()
    project = PMSProject(
        name="Assigned project",
        project_key="ACL",
        organization_id=1,
        owner_user_id=admin.id,
    )
    db.add(project)
    db.flush()
    db.add(
        PMSProjectMember(
            project_id=project.id, user_id=access_account.id, role="Member"
        )
    )
    own = PMSTask(
        project_id=project.id,
        task_key="ACL-1",
        title="Own task",
        assignee_user_id=access_account.id,
    )
    other = PMSTask(
        project_id=project.id,
        task_key="ACL-2",
        title="Other person's task",
        assignee_user_id=admin.id,
    )
    db.add_all([own, other])
    db.flush()
    db.add_all(
        [
            PMSTaskAssignee(task_id=own.id, user_id=access_account.id),
            PMSTaskAssignee(task_id=own.id, user_id=admin.id),
        ]
    )
    db.commit()
    headers = secure(client, superuser_headers)
    g = grant(client, headers, "project_management", "contributor")
    assert (
        apply(
            client,
            headers,
            access_account,
            {"project_management": {**g, "scope": "assigned"}},
        ).status_code
        == 200
    )
    with background_scope(db, access_account, "project_management", "view"):
        assert [row.id for row in db.query(PMSTask).all()] == [own.id]
        assert [row.user_id for row in db.query(PMSTaskAssignee).all()] == [
            access_account.id
        ]
    user_headers = login(client, module="pms")
    assert (
        client.get(
            f"/api/v1/project-management/tasks/{own.id}", headers=user_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/project-management/tasks/{other.id}", headers=user_headers
        ).status_code
        == 404
    )


def test_managed_file_links_stop_working_after_access_revocation(
    client, db, access_account, superuser_headers, monkeypatch, tmp_path
):
    from datetime import date
    from app.models.employee import Employee
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    path = tmp_path / "_private" / "profiles" / "photo.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"private-image")
    db.add(
        Employee(
            employee_id="PHOTO-ACCESS",
            user_id=access_account.id,
            first_name="Access",
            last_name="Employee",
            date_of_joining=date.today(),
            profile_photo_url="/uploads/_private/profiles/photo.png",
        )
    )
    db.commit()
    headers = secure(client, superuser_headers)
    g = grant(client, headers, "hrms")
    saved = apply(client, headers, access_account, {"hrms": g})
    assert saved.status_code == 200, saved.text
    own = login(client)
    profile = client.get("/api/v1/profiles/me", headers=own)
    assert profile.status_code == 200, profile.text
    url = profile.json()["photoUrl"]
    assert "token=" in url
    assert client.get(url).status_code == 200
    assert (
        apply(
            client,
            headers,
            access_account,
            {"hrms": {**g, "enabled": False}},
            saved.json()["results"][0]["user"]["version"],
        ).status_code
        == 200
    )
    assert client.get(url).status_code == 403


def test_delegated_admin_cannot_use_role_id_to_bypass_permission_ceiling(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    assert apply(client, headers, access_account, {"crm": g}).status_code == 200
    db.add(
        AccessMembership(
            user_id=access_account.id, company_id=1, active=True, is_admin=True
        )
    )
    db.commit()
    high = client.post(
        ROOT + "/roles",
        headers=headers,
        json={
            "companyId": 1,
            "module": "crm",
            "name": "Privileged CRM role",
            "permissions": ["crm_admin"],
            "actions": ["view", "edit", "assign"],
            "scope": "organization",
            "reason": "Administrator role",
        },
    ).json()
    target = User(
        email="restricted-target@example.com",
        hashed_password=access_account.hashed_password,
        is_active=True,
    )
    db.add(target)
    db.flush()
    db.add(
        CommonPerson(
            user_id=target.id, organization_id=1, display_name="Target", status="active"
        )
    )
    db.commit()
    delegated = login(client)
    verified = client.post(
        ROOT + "/step-up", headers=delegated, json={"password": "Sales@123456"}
    )
    assert verified.status_code == 200, verified.text
    delegated = {**delegated, "X-Access-Step-Up": verified.json()["token"]}
    payload = {
        "companyId": 1,
        "reason": "Attempt hidden escalation",
        "changes": [
            {
                "userId": target.id,
                "version": 0,
                "grants": {
                    "crm": {
                        "enabled": True,
                        "roleId": high["id"],
                        "roleVersion": high["version"],
                        "role": "Viewer",
                        "permissions": [],
                        "actions": ["view"],
                        "scope": "own",
                    }
                },
            }
        ],
    }
    assert (
        client.post(
            ROOT + "/changes/apply", headers=delegated, json=payload
        ).status_code
        == 403
    )
    assert client.get(ROOT + "/users?companyId=2", headers=delegated).status_code in {
        403,
        404,
    }


def test_access_audit_is_append_only_and_unscoped_raw_queries_are_blocked(
    client, db, access_account, superuser_headers
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from app.access.service import background_scope
    from fastapi import HTTPException

    headers = secure(client, superuser_headers)
    g = grant(client, headers)
    assert apply(client, headers, access_account, {"crm": g}).status_code == 200
    audit = db.query(AccessAudit).filter_by(target_id=access_account.id).first()
    with pytest.raises(ValueError):
        with db.begin_nested():
            audit.reason = "Rewrite history"
            db.flush()
    if db.bind.dialect.name == "postgresql":
        with pytest.raises(DBAPIError):
            with db.begin_nested():
                db.execute(
                    text(
                        "UPDATE suite_access_audit SET reason='tampered' WHERE id=:id"
                    ),
                    {"id": audit.id},
                )
    with background_scope(db, access_account, "crm", "view"):
        with pytest.raises(HTTPException):
            db.execute(text("SELECT id FROM crm_leads"))


def test_concurrent_administrators_cannot_overwrite_each_other(client, db):
    if db.bind.dialect.name != "postgresql":
        pytest.skip("Real concurrent row-lock validation uses PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.db.base_class import Base
    from app.core.deps import get_db
    from app.core.security import create_access_token

    url = db.bind.engine.url
    assert (url.database or "").endswith(
        "_test"
    ), "Concurrency sandbox requires an isolated test database"
    schema = "access_race_" + uuid4().hex
    engine = create_engine(
        url, connect_args={"options": "-c search_path=" + schema + ",public"}
    )
    with db.bind.engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA " + schema))
    factory = sessionmaker(bind=engine)
    originals = {
        name: getattr(client.app.state, name, None)
        for name in (
            "business_os_session_factory",
            "business_os_close_session",
            "audit_session_factory",
            "audit_close_session",
            "audit_commit",
        )
    }
    original_db = client.app.dependency_overrides[get_db]
    try:
        Base.metadata.create_all(
            bind=engine.execution_options(schema_translate_map={None: schema})
        )
        with factory() as session:
            session.add(Company(id=1, name="Concurrency sandbox"))
            session.flush()
            actors = [
                User(
                    email=f"race-admin-{i}@example.com",
                    hashed_password=get_password_hash("Sales@123456"),
                    is_active=True,
                    is_superuser=True,
                )
                for i in range(2)
            ]
            target = User(
                email="race-target@example.com",
                hashed_password=get_password_hash("Sales@123456"),
                is_active=True,
            )
            session.add_all([*actors, target])
            session.flush()
            target_id = target.id
            headers = [
                {"Authorization": "Bearer " + create_access_token(actor.id)}
                for actor in actors
            ]
            session.add(
                AccessPolicy(
                    user_id=target.id,
                    company_id=1,
                    status="active",
                    version=1,
                    grants={},
                )
            )
            session.commit()

        def sandbox_db():
            with factory() as session:
                yield session

        client.app.dependency_overrides[get_db] = sandbox_db
        client.app.state.business_os_session_factory = factory
        client.app.state.business_os_close_session = True
        client.app.state.audit_session_factory = factory
        client.app.state.audit_close_session = True
        client.app.state.audit_commit = True
        for header in headers:
            verified = client.post(
                ROOT + "/step-up", headers=header, json={"password": "Sales@123456"}
            )
            assert verified.status_code == 200, verified.text
            header["X-Access-Step-Up"] = verified.json()["token"]
        barrier = Barrier(2)

        def attempt(index):
            barrier.wait(timeout=15)
            return client.post(
                ROOT + "/changes/apply",
                headers=headers[index],
                json={
                    "companyId": 1,
                    "reason": "Concurrent administrator proposal",
                    "changes": [
                        {
                            "userId": target_id,
                            "version": 1,
                            "grants": {
                                "crm": {
                                    "enabled": bool(index),
                                    "role": "viewer",
                                    "permissions": [],
                                    "actions": ["view"],
                                    "scope": "own",
                                }
                            },
                        }
                    ],
                },
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(attempt, range(2)))
        assert sorted(response.status_code for response in responses) == [200, 409], [
            response.text for response in responses
        ]
        with factory() as session:
            assert (
                session.query(AccessPolicy).filter_by(user_id=target_id).one().version
                == 2
            )
    finally:
        client.app.dependency_overrides[get_db] = original_db
        for name, value in originals.items():
            if value is None:
                if hasattr(client.app.state, name):
                    delattr(client.app.state, name)
            else:
                setattr(client.app.state, name, value)
        engine.dispose()
        with db.bind.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA " + schema + " CASCADE"))


def test_existing_auth_remains_usable_before_access_migration(
    client, db, access_account, superuser_headers, monkeypatch
):
    from app.access import service

    monkeypatch.setattr(service, "schema_ready", lambda session: False)
    headers = login(client)
    assert (
        client.get("/api/v1/crm/lead-management/leads", headers=headers).status_code
        == 200
    )
    own = client.get(ROOT + "/me", headers=headers)
    assert own.status_code == 200 and own.json()["managed"] is False
    assert client.get(ROOT + "/users", headers=superuser_headers).status_code == 503
