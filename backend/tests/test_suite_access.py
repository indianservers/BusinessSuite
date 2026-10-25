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
            "crm": {**g, "roleId": role.json()["id"]},
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
