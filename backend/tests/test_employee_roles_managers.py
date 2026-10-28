from datetime import date

from app.models.employee import Employee
from app.models.user import Role, User


def person(db, code, kind="Full-time", user_id=None):
    row = Employee(employee_id=code, first_name="Test", last_name=code,
                   date_of_joining=date(2026, 1, 1), employment_type=kind, user_id=user_id)
    db.add(row)
    db.commit()
    return row


def test_intern_and_self_manager_rejected(client, db, superuser_headers):
    intern = person(db, "INTERN", " Intern ")
    employee = person(db, "EMPLOYEE")
    url = f"/api/v1/employees/{employee.id}"
    for manager in (intern, employee):
        result = client.put(url, headers=superuser_headers, json={"reporting_manager_id": manager.id})
        assert result.status_code == 422, result.text
    manager = person(db, "MANAGER", user_id=db.query(User).filter_by(email="testadmin@test.com").one().id)
    result = client.put(url, headers=superuser_headers, json={"reporting_manager_id": manager.id})
    assert result.status_code == 200, result.text
    assert result.json()["reporting_manager_id"] == manager.id


def test_admin_changes_linked_account_role(client, db, superuser_headers):
    role = Role(name="intern")
    db.add(role)
    db.flush()
    account = User(email="role-test@example.com", hashed_password="unused", is_active=True)
    db.add(account)
    db.commit()
    employee = person(db, "ROLE-EMPLOYEE", user_id=account.id)
    result = client.put(f"/api/v1/employees/{employee.id}", headers=superuser_headers,
                        json={"role_id": role.id, "employment_type": "Intern"})
    assert result.status_code == 200, result.text
    db.refresh(account)
    assert account.role_id == role.id
    assert result.json()["employment_type"] == "Intern"
    options = client.get("/api/v1/employees/user-options", headers=superuser_headers,
                         params={"include_employee_id": employee.id})
    assert next(row for row in options.json() if row["id"] == account.id)["role_id"] == role.id


def test_invalid_or_unlinked_role_rejected(client, db, superuser_headers):
    employee = person(db, "UNLINKED")
    url = f"/api/v1/employees/{employee.id}"
    for role_id in (None, 999999):
        result = client.put(url, headers=superuser_headers, json={"role_id": role_id})
        assert result.status_code == 422, result.text
    role = db.query(Role).first()
    result = client.put(url, headers=superuser_headers, json={"role_id": role.id})
    assert result.status_code == 422, result.text


def test_non_admin_cannot_change_role(db):
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from app.api.v1.employees import update_employee
    from app.schemas.employee import EmployeeUpdate
    employee = person(db, "NO-PRIVILEGE")
    with pytest.raises(HTTPException) as error:
        update_employee(employee.id, EmployeeUpdate(role_id=1), db, SimpleNamespace(is_superuser=False))
    assert error.value.status_code == 403


def test_reporting_manager_role_allowlist(client, db, superuser_headers):
    allowed = {"super_admin", "ceo", "hr", "hr_manager", "pms_project_manager", "project_manager"}
    expected = set()
    for name in sorted(allowed | {"intern", "employee", "manager", "pms_team_member", "crm_super_admin"}):
        role = db.query(Role).filter_by(name=name).first()
        if role is None:
            role = Role(name=name)
            db.add(role)
            db.flush()
        account = User(email=f"{name}@example.com", hashed_password="unused", role_id=role.id, is_active=True)
        db.add(account)
        db.commit()
        row = person(db, "ROLE-"+name, user_id=account.id)
        if name in allowed:
            expected.add(row.id)
    # Employment type takes precedence even when the account has an allowed role.
    role = db.query(Role).filter_by(name="ceo").one()
    account = User(email="intern-ceo@example.com", hashed_password="unused", role_id=role.id, is_active=True)
    db.add(account)
    db.commit()
    person(db, "INTERN-CEO", "Intern", account.id)
    result = client.get("/api/v1/employees/reporting-managers", headers=superuser_headers)
    assert result.status_code == 200, result.text
    assert {row["id"] for row in result.json()} == expected
    intern_result = client.get("/api/v1/interns-hub/admin/reporting-managers", headers=superuser_headers)
    assert intern_result.status_code == 200, intern_result.text
    assert {row["id"] for row in intern_result.json() if row["id"] > 0} == expected
    target = person(db, "TARGET")
    forbidden = db.query(Employee).filter_by(employee_id="ROLE-employee").one()
    result = client.put(f"/api/v1/employees/{target.id}", headers=superuser_headers,
                        json={"reporting_manager_id": forbidden.id})
    assert result.status_code == 422, result.text
