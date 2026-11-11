from datetime import date
from tests.rich_text_test_utils import organization_context
from app.models.employee import Employee
from app.models.user import User, Role, Permission
from app.models.company import Company, Branch
from app.core.security import create_access_token

ROOT = "/api/v1/employees/workbench/request-context"


def person(db, code, **values):
    row = Employee(employee_id=code, first_name=code, last_name="Person", date_of_joining=date.today(), **values)
    db.add(row)
    db.flush()
    return row


def test_request_context_has_reporting_path_without_sensitive_fields(client, db, superuser_headers):
    manager = person(db, "CREATE-MANAGER", personal_email="private-manager@example.test")
    worker = person(db, "CREATE-WORKER", reporting_manager_id=manager.id, account_number="sensitive-account")
    db.commit()
    response = client.get(ROOT, params={"employee_id": worker.id, "kind": "expense"}, headers=superuser_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["approval_path"] == ["CREATE-MANAGER Person", "Finance review"]
    assert result["initial_status"] == "submitted"
    assert "private-manager" not in response.text and "sensitive-account" not in response.text
    assert client.get(ROOT, params={"employee_id": worker.id, "kind": "unknown"}, headers=superuser_headers).status_code == 422


def test_request_context_missing_employee_and_manager_fallback(client, db, superuser_headers):
    assert client.get(ROOT, headers=superuser_headers).status_code == 400
    worker = person(db, "CREATE-NO-MANAGER")
    db.commit()
    response = client.get(ROOT, params={"employee_id": worker.id}, headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()["approval_path"] == ["Authorized HR reviewer"]
    assert client.get(ROOT, params={"employee_id": 999999}, headers=superuser_headers).status_code == 404


def test_request_context_respects_company_scope(client, db):
    companies = [Company(name="Create scope A"), Company(name="Create scope B")]
    db.add_all(companies)
    db.flush()
    branches = [Branch(name="Create branch", company_id=company.id) for company in companies]
    db.add_all(branches)
    db.flush()
    permission = db.query(Permission).filter_by(name="employee_view").first()
    if not permission:
        permission = Permission(name="employee_view")
    role = Role(name="create-context-reader", permissions=[permission])
    user = User(email="create-context@example.test", hashed_password="unused", is_active=True, role=role)
    db.add(user)
    db.flush()
    own = person(db, "CREATE-OWN", branch_id=branches[0].id, user_id=user.id)
    foreign = person(db, "CREATE-FOREIGN", branch_id=branches[1].id)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(user.id)}
    assert client.get(ROOT, headers=headers).json()["employee_id"] == own.id
    assert client.get(ROOT, params={"employee_id": foreign.id}, headers=headers).status_code == 404


def test_employee_can_preview_own_request_without_employee_directory_access(client, db):
    company = Company(name="Self service create context")
    db.add(company)
    db.flush()
    branch = Branch(name="Self service branch", company_id=company.id)
    db.add(branch)
    role = Role(name="employee", permissions=[])
    user = User(email="self-create-context@example.test", hashed_password="unused", is_active=True, role=role)
    db.add(user)
    db.flush()
    own = person(db, "SELF-CREATE", branch_id=branch.id, user_id=user.id)
    other = person(db, "OTHER-CREATE", branch_id=branch.id)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(user.id)}
    response = client.get(ROOT, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["employee_id"] == own.id
    assert client.get(ROOT, params={"employee_id": other.id}, headers=headers).status_code == 404
