import pytest
from app.models.company import Company, Branch, Department
from app.models.user import User, UserSession
from app.access.models import AccessMembership, AccessAudit
from tests.test_suite_access import access_account, login, secure, grant, apply

ROOT = "/api/v1/access/control"


def test_dashboard_and_registry_are_real(client, db, access_account, superuser_headers):
    dashboard = client.get(ROOT + "/dashboard", headers=superuser_headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["summary"]["Total users"] == db.query(User).count()
    modules = client.get(ROOT + "/modules", headers=superuser_headers)
    assert modules.status_code == 200, modules.text
    assert {m["key"] for m in modules.json()} >= {
        "crm",
        "hrms",
        "fam",
        "project_management",
    }
    assert all("integrationStatus" in m for m in modules.json())


def test_company_branch_department_and_stale_update(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    company = client.post(
        ROOT + "/organizations",
        headers=headers,
        json={"name": "New subsidiary", "reason": "Create test company"},
    )
    assert company.status_code == 201, company.text
    company_id = company.json()["id"]
    branch = client.post(
        ROOT + "/units/branches",
        headers=headers,
        json={
            "companyId": company_id,
            "name": "Head office",
            "code": "HQ",
            "reason": "Create branch",
        },
    )
    assert branch.status_code == 201, branch.text
    department = client.post(
        ROOT + "/units/departments",
        headers=headers,
        json={
            "companyId": company_id,
            "branch_id": branch.json()["id"],
            "name": "Engineering",
            "reason": "Create department",
        },
    )
    assert department.status_code == 201, department.text
    stale = client.put(
        ROOT + "/units/branches/" + str(branch.json()["id"]),
        headers=headers,
        json={
            "companyId": company_id,
            "name": "Edited",
            "expectedUpdatedAt": "stale",
            "reason": "Test stale write",
        },
    )
    assert stale.status_code == 409
    assert (
        db.query(Department).filter_by(id=department.json()["id"]).one().branch_id
        == branch.json()["id"]
    )
    audit = client.get(
        ROOT + "/audit", headers=headers, params={"companyId": company_id}
    ).json()
    assert {"company_created", "branches_saved", "departments_saved"} <= {
        e["operation"] for e in audit["items"]
    }


def test_company_disable_overrides_grants_and_restores(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    crm = grant(client, headers)
    assert apply(client, headers, access_account, {"crm": crm}).status_code == 200
    user_headers = login(client)
    assert (
        client.get(
            "/api/v1/crm/lead-management/leads", headers=user_headers
        ).status_code
        == 200
    )
    disabled = client.put(
        ROOT + "/modules/crm",
        headers=headers,
        json={
            "companyId": 1,
            "enabled": False,
            "version": 0,
            "reason": "Disable company CRM",
        },
    )
    assert disabled.status_code == 200, disabled.text
    assert (
        client.get(
            "/api/v1/crm/lead-management/leads", headers=user_headers
        ).status_code
        == 403
    )
    me = client.get("/api/v1/access/me", headers=user_headers)
    assert me.status_code == 200 and not me.json()["grants"]["crm"]["enabled"]
    stale = client.put(
        ROOT + "/modules/crm",
        headers=headers,
        json={"companyId": 1, "enabled": True, "version": 0, "reason": "Stale edit"},
    )
    assert stale.status_code == 409
    restored = client.put(
        ROOT + "/modules/crm",
        headers=headers,
        json={
            "companyId": 1,
            "enabled": True,
            "version": 1,
            "reason": "Restore company CRM",
        },
    )
    assert restored.status_code == 200
    assert (
        client.get(
            "/api/v1/crm/lead-management/leads", headers=user_headers
        ).status_code
        == 200
    )


def test_control_center_ordinary_user_denial_and_mass_assignment(
    client, access_account, superuser_headers
):
    headers = login(client)
    for path in ("/dashboard", "/organizations", "/security", "/audit", "/modules"):
        assert client.get(ROOT + path, headers=headers).status_code == 403
    response = client.post(
        ROOT + "/organizations",
        headers=secure(client, superuser_headers),
        json={"name": "Injected", "is_superuser": True, "reason": "Reject extra field"},
    )
    assert response.status_code == 422


def test_delegated_admin_cannot_cross_company_or_revoke_privileged_sessions(
    client, db, access_account, superuser_headers
):
    other = Company(name="Isolated company")
    db.add(other)
    db.flush()
    db.add(
        AccessMembership(
            user_id=access_account.id, company_id=1, is_admin=True, active=True
        )
    )
    db.commit()
    headers = login(client)
    assert client.get(ROOT + "/security", headers=headers).status_code == 200
    assert (
        client.get(
            ROOT + "/security", headers=headers, params={"companyId": other.id}
        ).status_code
        == 403
    )
    tree = client.get(ROOT + "/organizations", headers=headers)
    assert tree.status_code == 200 and other.id not in [c["id"] for c in tree.json()]
    assert (
        client.post(
            ROOT + "/organizations",
            headers=headers,
            json={"name": "Not authorized", "reason": "Prevent escalation"},
        ).status_code
        == 403
    )


def test_user360_identity_edit_and_session_revocation(
    client, db, access_account, superuser_headers
):
    user_headers = login(client)
    headers = secure(client, superuser_headers)
    profile = client.get(ROOT + f"/users/{access_account.id}/360", headers=headers)
    assert profile.status_code == 200, profile.text
    assert (
        "hashed_password" not in profile.text
        and "session_token_hash" not in profile.text
    )
    edit = client.put(
        ROOT + f"/users/{access_account.id}/identity",
        headers=headers,
        json={
            "companyId": 1,
            "name": "Updated Identity",
            "email": "updated@example.com",
            "expectedUpdatedAt": profile.json()["overview"]["updatedAt"],
            "reason": "Correct user identity",
        },
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["name"] == "Updated Identity"
    assert client.get("/api/v1/access/me", headers=user_headers).status_code == 401
    assert (
        db.query(AccessAudit)
        .filter_by(operation="identity_updated", target_id=access_account.id)
        .count()
        == 1
    )


def test_security_revoke_and_audit_export(
    client, db, access_account, superuser_headers
):
    user_headers = login(client)
    headers = secure(client, superuser_headers)
    revoked = client.post(
        ROOT + "/sessions/revoke",
        headers=headers,
        json={
            "companyId": 1,
            "userId": access_account.id,
            "reason": "Administrator session review",
        },
    )
    assert revoked.status_code == 200 and revoked.json()["revoked"] > 0
    assert client.get("/api/v1/access/me", headers=user_headers).status_code == 401
    report = client.get(ROOT + "/audit", headers=headers, params={"export": True})
    assert report.status_code == 200 and "sessions_revoked" in report.text


def test_password_policy_stepup_optimistic_and_mfa_lockout_safety(
    client, db, access_account, superuser_headers
):
    body = {
        "name": "Strong suite policy",
        "min_length": 12,
        "reason": "Configure secure default",
        "expected": {},
    }
    headers = secure(client, superuser_headers)
    security = client.get(ROOT + "/security", headers=headers).json()
    active = sorted(
        [p for p in security["passwordPolicies"] if p["is_active"]],
        key=lambda p: p["id"],
        reverse=True,
    )
    body["expected"] = active[0] if active else {}
    assert (
        client.put(
            ROOT + "/password-policy", headers=superuser_headers, json=body
        ).status_code
        == 403
    )
    success = client.put(ROOT + "/password-policy", headers=headers, json=body)
    assert success.status_code == 200, success.text
    assert (
        client.put(ROOT + "/password-policy", headers=headers, json=body).status_code
        == 409
    )

    body.update(expected=success.json(), mfa_required=True)
    assert (
        client.put(ROOT + "/password-policy", headers=headers, json=body).status_code
        == 409
    )


def test_invalid_identity_and_protected_admin_edit(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    profile = client.get(
        ROOT + f"/users/{access_account.id}/360", headers=headers
    ).json()
    body = {
        "companyId": 1,
        "name": "Valid Name",
        "email": "invalid-address",
        "reason": "Validate identity fields",
        "expectedUpdatedAt": profile["overview"]["updatedAt"],
    }
    assert (
        client.put(
            ROOT + f"/users/{access_account.id}/identity", headers=headers, json=body
        ).status_code
        == 422
    )
    admin_id = db.query(User).filter_by(is_superuser=True).first().id
    body["email"] = "testadmin@test.com"
    assert (
        client.put(
            ROOT + f"/users/{admin_id}/identity", headers=headers, json=body
        ).status_code
        == 403
    )


def test_unit_cross_company_parent_and_manager_idor(
    client, db, access_account, superuser_headers
):
    headers = secure(client, superuser_headers)
    other = Company(name="Different tenant")
    db.add(other)
    db.flush()
    branch = Branch(name="Other branch", company_id=other.id)
    db.add(branch)
    db.commit()
    body = {
        "companyId": 1,
        "name": "No cross-tenant parent",
        "branch_id": branch.id,
        "reason": "Validate parent ownership",
    }
    assert (
        client.post(ROOT + "/units/departments", headers=headers, json=body).status_code
        == 422
    )
    assert (
        client.put(
            ROOT + f"/units/branches/{branch.id}", headers=headers, json=body
        ).status_code
        == 404
    )


def test_company_entitlement_applies_to_legacy_users_and_background(
    client, db, access_account, superuser_headers
):
    from app.access.service import check_background_access
    from fastapi import HTTPException

    headers = secure(client, superuser_headers)
    user_headers = login(client)
    assert (
        client.put(
            ROOT + "/modules/crm",
            headers=headers,
            json={
                "companyId": 1,
                "enabled": False,
                "version": 0,
                "reason": "Check legacy tenant gate",
            },
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/crm/lead-management/leads", headers=user_headers
        ).status_code
        == 403
    )
    assert (
        "crm"
        in client.get("/api/v1/access/me", headers=user_headers).json()[
            "companyDisabledModules"
        ]
    )
    with pytest.raises(HTTPException) as denied:
        check_background_access(db, access_account, "crm")
    assert denied.value.status_code == 403


def test_shared_identity_security_is_hidden_from_delegated_admin(
    client, db, access_account, superuser_headers
):
    db.add(
        AccessMembership(
            user_id=access_account.id, company_id=1, active=True, is_admin=True
        )
    )
    db.commit()
    headers = login(client)
    admin_id = db.query(User).filter_by(is_superuser=True).first().id
    profile = client.get(ROOT + f"/users/{admin_id}/360", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["security"]["sessions"] == []
    assert profile.json()["security"]["loginHistory"] == []


def test_sensitive_operation_rate_limit(client, db, access_account, superuser_headers):
    headers = secure(client, superuser_headers)
    admin_id = db.query(User).filter_by(is_superuser=True).first().id
    db.add_all(
        [
            AccessAudit(
                actor_id=admin_id,
                company_id=1,
                operation="test_rate_limit",
                reason="Fixture event",
            )
            for _ in range(30)
        ]
    )
    db.commit()
    result = client.post(
        ROOT + "/organizations",
        headers=headers,
        json={"name": "Too many changes", "reason": "Check administrative rate limit"},
    )
    assert result.status_code == 429
