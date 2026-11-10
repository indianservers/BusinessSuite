"""Cross-application authorization regressions; requests use disposable test data."""
import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app.core.route_policy import dependency_names
from app.core.security import create_access_token
from app.main import app
from app.models.user import Permission, Role, User, UserSession
from test_identity_utils import attach_test_identity, attach_workflow_branch


def routes(router, prefix=""):
    for route in router.routes:
        if hasattr(route, "original_router"):
            yield from routes(route.original_router, prefix + route.include_context.prefix)
        elif isinstance(route, APIRoute):
            yield prefix + route.path, route


def test_all_user_authenticated_operations_reject_anonymous_requests(client):
    failures = []
    checked = 0
    for path, route in routes(app.router):
        if not path.startswith("/api/v1/") or "get_current_user" not in set(dependency_names(route.dependant)):
            continue
        path = re.sub(r"\{[^}]+\}", "1", path)
        for method in sorted(route.methods):
            response = client.request(method, path, json={} if method in {"POST", "PUT", "PATCH"} else None,
                                      follow_redirects=False)
            checked += 1
            if response.status_code not in {401, 403}:
                failures.append((method, path, response.status_code))
    assert checked > 3000
    assert failures == [], failures


def identity(db, role_name, permissions=()):
    selected = []
    for name in permissions:
        permission = db.query(Permission).filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name, module="ai")
            db.add(permission)
        selected.append(permission)
    role = Role(name=role_name, permissions=selected)
    db.add(role); db.flush()
    user = User(email=uuid4().hex + "@example.invalid", hashed_password="unused", is_active=True,
                is_superuser=False, role_id=role.id)
    db.add(user); db.flush()
    attach_test_identity(db, user)
    branch = attach_workflow_branch(db, user)
    session = UserSession(user_id=user.id, session_token_hash="pending", status="Active",
                          expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                          last_seen_at=datetime.now(timezone.utc))
    db.add(session); db.flush()
    token = create_access_token(user.id, session_id=session.id)
    session.session_token_hash = sha256(token.encode()).hexdigest()
    db.commit()
    return user, {"Authorization": "Bearer " + token,
                  "X-Suite-Branch": str(branch.id)}


@pytest.mark.parametrize("role_name", ["admin", "super_admin"])
def test_role_labels_do_not_grant_suite_audit_access(client, db, role_name):
    _, headers = identity(db, role_name)
    response = client.get("/api/v1/logs/audit", headers=headers)
    assert response.status_code == 403, response.text
    assert client.get("/api/v1/logs/requests", headers=headers).status_code == 403


@pytest.mark.parametrize("role_name", ["admin", "super_admin", "developer"])
def test_ai_user_role_labels_do_not_grant_configuration(client, db, role_name):
    _, headers = identity(db, role_name, ["ai_assistant"])
    response = client.get("/api/v1/ai-agents/security/settings", headers=headers)
    assert response.status_code == 403, response.text
    assert client.put("/api/v1/ai-agents/security/permissions", headers=headers, json=[]).status_code == 403


def test_explicit_ai_configuration_permission_still_authorizes(client, db):
    _, headers = identity(db, "custom_ai_configuration", ["settings_manage"])
    response = client.get("/api/v1/ai-agents/security/settings", headers=headers)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("role_name", ["hr", "hr_admin", "hr_manager", "super_admin"])
def test_hr_role_labels_do_not_grant_leave_or_expense_administration(db, role_name):
    from app.api.v1.leave import _is_hr_admin
    from app.api.v1.expenses import _can_hr_or_finance

    user, _ = identity(db, role_name)
    assert not _is_hr_admin(user)
    assert not _can_hr_or_finance(user)


def test_explicit_hr_permissions_authorize_custom_role(db):
    from app.api.v1.leave import _is_hr_admin
    from app.api.v1.expenses import _can_hr_or_finance

    user, _ = identity(db, "custom_hr_administrator", ["leave_manage", "payroll_run"])
    assert _is_hr_admin(user)
    assert _can_hr_or_finance(user)


@pytest.mark.parametrize("permissions,expected", [(["reports_view"], 0),
                                                 (["reports_view", "reports_manage"], 1)])
def test_manager_report_fallback_requires_permission_not_role_name(client, db, permissions, expected):
    from app.models.employee import Employee
    from app.models.company import Branch
    from test_identity_utils import own_workflow_records

    _, headers = identity(db, "hr_manager", permissions)
    branch = db.query(Branch).filter_by(company_id=1).first()
    employee = Employee(employee_id="REPORT-SCOPE", first_name="Other", last_name="Employee",
                        date_of_joining=datetime.now(timezone.utc).date(), branch_id=branch.id,
                        status="Active")
    db.add(employee); db.flush()
    own_workflow_records(db, employee)
    db.commit()
    response = client.get("/api/v1/reports/manager-dashboard", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["team_size"] == expected
