from datetime import date
import json
import pytest
from app.models.employee import Employee
from app.models.user import User, Role, Permission, UserSession
from app.models.audit import AuditLog
from app.core.security import get_password_hash
from tests.test_suite_access import secure

ROOT = "/api/v1/employees/accounts"


@pytest.fixture
def account(db):
    role = Role(name="employee", permissions=[Permission(name="employee_view", module="hrms")])
    db.add(role); db.flush()
    user = User(email="managed@example.com", hashed_password=get_password_hash("Initial@123456"), role_id=role.id, is_active=True)
    db.add(user); db.flush()
    employee = Employee(employee_id="MANAGED-01", first_name="Managed", last_name="Employee", user_id=user.id, date_of_joining=date(2026, 1, 1))
    db.add(employee); db.commit()
    return user


def snapshot(client, headers, email="managed@example.com"):
    r = client.get(ROOT, headers=headers, params={"search": email})
    assert r.status_code == 200, r.text
    return next(u for u in r.json()["items"] if u["email"] == email)


def sign_in(client, email="managed@example.com", password="Initial@123456"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def act(client, headers, user, action, **extra):
    return client.post(f"{ROOT}/{user['id']}/actions", headers=headers,
        json={"action": action, "version": user["version"], "reason": "Authorized HRMS administration", **extra})


def test_account_create_requires_superadmin_and_verification(client, db, account, superuser_headers):
    payload = {"email": "new.account@example.com", "password": "NewUser@123456", "role_id": account.role_id, "reason": "Onboard employee"}
    ordinary = sign_in(client)
    for path in [ROOT, ROOT + "/options", f"{ROOT}/{account.id}/history"]:
        assert client.get(path, headers=ordinary).status_code == 403
    assert client.post(ROOT, headers=ordinary, json=payload).status_code == 403
    assert client.post(ROOT, headers=superuser_headers, json=payload).status_code == 403
    headers = secure(client, superuser_headers)
    r = client.post(ROOT, headers=headers, json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["email"] == payload["email"]
    assert "password" not in r.text and "hashed_password" not in r.text
    assert client.post(ROOT, headers=headers, json={**payload, "email": payload["email"].upper()}).status_code == 409
    assert client.post(ROOT, headers=headers, json={**payload, "email": "invalid-role@example.com", "role_id": 999999}).status_code == 422
    assert sign_in(client, payload["email"], payload["password"])


def test_suspension_termination_and_reactivation_revoke_access(client, db, account, superuser_headers):
    old_session = sign_in(client)
    headers = secure(client, superuser_headers)
    user = snapshot(client, headers)
    r = act(client, headers, user, "suspended")
    assert r.status_code == 200, r.text
    assert snapshot(client, headers)["status"] == "suspended"
    assert client.get("/api/v1/auth/me", headers=old_session).status_code in {401, 403}
    assert client.post("/api/v1/auth/login", json={"email": account.email, "password": "Initial@123456"}).status_code != 200
    user = snapshot(client, headers)
    assert act(client, headers, user, "terminated").status_code == 200
    assert snapshot(client, headers)["status"] == "terminated"
    result = client.get(ROOT, headers=headers, params={"status": "terminated"}).json()
    assert account.id in [u["id"] for u in result["items"]]
    assert act(client, headers, snapshot(client, headers), "active").status_code == 200
    assert snapshot(client, headers)["status"] == "active"
    assert client.get("/api/v1/auth/me", headers=old_session).status_code == 401
    assert sign_in(client)


def test_password_reset_and_session_revocation_are_audited_without_secrets(client, db, account, superuser_headers):
    old_session = sign_in(client)
    headers = secure(client, superuser_headers)
    r = act(client, headers, snapshot(client, headers), "reset_password", password="Replacement@123456")
    assert r.status_code == 200, r.text
    assert "Replacement@123456" not in r.text
    assert client.get("/api/v1/auth/me", headers=old_session).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": account.email, "password": "Initial@123456"}).status_code == 401
    new_session = sign_in(client, password="Replacement@123456")
    assert act(client, headers, snapshot(client, headers), "revoke_sessions").status_code == 200
    assert client.get("/api/v1/auth/me", headers=new_session).status_code == 401
    events = client.get(f"{ROOT}/{account.id}/history", headers=headers)
    assert events.status_code == 200 and len(events.json()) == 2
    assert "Replacement@123456" not in events.text
    assert all("Replacement@123456" not in str(row.new_values) for row in db.query(AuditLog))


def test_edit_detects_stale_changes_and_protects_self_admin(client, db, account, superuser_headers):
    headers = secure(client, superuser_headers)
    user = snapshot(client, headers)
    payload = {"email": "updated@example.com", "role_id": user["role_id"], "is_superuser": False, "version": user["version"], "reason": "Update login address"}
    r = client.patch(f"{ROOT}/{account.id}", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    assert client.patch(f"{ROOT}/{account.id}", headers=headers, json=payload).status_code == 409
    own = snapshot(client, headers, "testadmin@test.com")
    for action in ["suspended", "terminated"]:
        assert act(client, headers, own, action).status_code == 409
    r = client.patch(f"{ROOT}/{own['id']}", headers=headers,
        json={"email": own["email"], "role_id": own["role_id"], "is_superuser": False, "version": own["version"], "reason": "Cannot demote last administrator"})
    assert r.status_code == 409
    db.refresh(db.get(User, own["id"]))
    assert db.get(User, own["id"]).is_active and db.get(User, own["id"]).is_superuser


def test_custom_roles_validate_permissions_and_revoke_assigned_sessions(client, db, account, superuser_headers):
    session = sign_in(client)
    headers = secure(client, superuser_headers)
    permission = db.query(Permission).filter_by(name="employee_view").one()
    data = {"name": "Custom HRMS reader", "description": "Restricted profile reader", "permission_ids": [permission.id], "reason": "Create least privilege role"}
    invalid = client.post(ROOT + "/roles", headers=headers, json={**data, "permission_ids": [999999]})
    assert invalid.status_code == 422
    r = client.post(ROOT + "/roles", headers=headers, json=data)
    assert r.status_code == 201, r.text
    role_id = r.json()["id"]
    user = snapshot(client, headers)
    r = client.patch(f"{ROOT}/{account.id}", headers=headers,
        json={"email": user["email"], "role_id": role_id, "is_superuser": False, "version": user["version"], "reason": "Assign custom role"})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/auth/me", headers=session).status_code == 401
    session = sign_in(client)
    roles = client.get(ROOT + "/options", headers=headers).json()["roles"]
    role = next(r for r in roles if r["id"] == role_id)
    updated = client.put(f"{ROOT}/roles/{role_id}", headers=headers,
        json={**data, "permission_ids": [], "version": role["version"]})
    assert updated.status_code == 200, updated.text
    assert client.get("/api/v1/auth/me", headers=session).status_code == 401
    assert client.put(f"{ROOT}/roles/{role_id}", headers=headers, json={**data, "version": role["version"]}).status_code == 409


def test_create_can_link_employee_and_legacy_create_is_superadmin_only(client, db, account, superuser_headers):
    employee = Employee(employee_id="NEW-LOGIN", first_name="New", last_name="User", date_of_joining=date(2026, 1, 1))
    db.add(employee); db.commit()
    ordinary = sign_in(client)
    payload = {"email": "linked@example.com", "password": "Employee@123456", "role_id": account.role_id}
    assert client.post(f"/api/v1/employees/{employee.id}/user-account", headers=ordinary, json=payload).status_code == 403
    assert client.put(f"/api/v1/employees/{employee.id}/user-link", headers=ordinary, json={"user_id": account.id}).status_code == 403
    headers = secure(client, superuser_headers)
    result = client.post(ROOT, headers=headers, json={**payload, "employee_id": employee.id, "reason": "Create linked login"})
    assert result.status_code == 201, result.text
    db.refresh(employee)
    assert employee.user_id == result.json()["id"]
    assert client.post(ROOT, headers=headers, json={**payload, "email": "duplicate-link@example.com", "employee_id": employee.id, "reason": "Cannot reuse employee"}).status_code == 409
