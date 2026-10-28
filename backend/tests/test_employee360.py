from datetime import date, timedelta

from app.core.security import create_access_token
from app.models.asset import Asset, AssetAssignment
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.payroll import EmployeeSalary, SalaryRevisionRequest
from app.models.user import Permission, Role, User


def seed_overview(db):
    employee = Employee(employee_id="360-ONE", first_name="Overview", last_name="Employee", date_of_joining=date.today(), salary_currency="INR")
    other = Employee(employee_id="360-TWO", first_name="Other", last_name="Employee", date_of_joining=date.today())
    db.add_all([employee, other]); db.flush()
    today = date.today()
    db.add_all([
        EmployeeSalary(employee_id=employee.id, ctc=600000, effective_from=today - timedelta(days=30)),
        EmployeeSalary(employee_id=employee.id, ctc=720000, effective_from=today + timedelta(days=30)),
        EmployeeSalary(employee_id=other.id, ctc=9999999, effective_from=today),
        SalaryRevisionRequest(employee_id=employee.id, current_ctc=600000, proposed_ctc=720000,
                              effective_from=today + timedelta(days=30), reason="Annual review"),
        ExpenseClaim(employee_id=employee.id, claim_number="EXP-360-INR", claim_type="Travel", expense_date=today,
                     amount=1200, approved_amount=1000, currency="INR", status="finance_approved"),
        ExpenseClaim(employee_id=employee.id, claim_number="EXP-360-USD", claim_type="Travel", expense_date=today,
                     amount=20, currency="USD", status="submitted"),
        ExpenseClaim(employee_id=other.id, claim_number="EXP-FOREIGN", claim_type="Travel", expense_date=today,
                     amount=9000, currency="INR"),
    ])
    asset = Asset(asset_tag="360-LAPTOP", name="Work laptop")
    db.add(asset); db.flush()
    db.add(AssetAssignment(employee_id=employee.id, asset_id=asset.id, assigned_date=today, acknowledgement_signed=False))
    db.commit()
    return employee, other


def test_employee360_connects_only_employee_records_and_uses_effective_salary(client, db, superuser_headers):
    employee, _ = seed_overview(db)
    response = client.get(f"/api/v1/employees/{employee.id}/360", headers=superuser_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert float(data["salary"]["ctc"]) == 600000
    assert len(data["salary_history"]) == 2
    assert data["increments"][0]["reason"] == "Annual review"
    assert data["assets"][0]["asset_tag"] == "360-LAPTOP"
    assert {row["currency"] for row in data["expenses"]} == {"INR", "USD"}
    assert "FOREIGN" not in response.text and "9999999" not in response.text
    assert {row["section"] for row in data["pending_actions"]} == {"increments", "assets", "expenses"}
    assert client.get("/api/v1/employees/2147483647/360", headers=superuser_headers).status_code == 404


def test_directory_access_does_not_grant_salary_assets_or_unrelated_expenses(client, db):
    from app.models.company import Company, Branch
    employee, _ = seed_overview(db)
    company = Company(name="360 Directory Company")
    db.add(company); db.flush()
    branch = Branch(name="360 Directory HQ", company_id=company.id)
    db.add(branch); db.flush()
    employee.branch_id = branch.id
    role = Role(name="360_directory_reader", permissions=[Permission(name="employee_view")])
    user = User(email="360-reader@example.com", hashed_password="unused", role=role, is_active=True)
    db.add(user); db.flush()
    db.add(Employee(employee_id="360-READER", first_name="Directory", last_name="Reader", date_of_joining=date.today(), user_id=user.id, branch_id=branch.id))
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(user.id)}
    response = client.get(f"/api/v1/employees/{employee.id}/360", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["salary"] is None
    assert data["salary_history"] == data["increments"] == data["assets"] == data["expenses"] == data["pending_actions"] == []
    assert not any(data["access"].values())


def test_employee360_rejects_cross_tenant_even_with_payroll_access(client, db):
    from app.models.company import Company, Branch
    companies = [Company(name="360 Tenant A"), Company(name="360 Tenant B")]
    db.add_all(companies); db.flush()
    branches = [Branch(name="360 HQ", company_id=row.id) for row in companies]
    db.add_all(branches); db.flush()
    role = Role(name="360_payroll_reader", permissions=[Permission(name="employee_view"), Permission(name="payroll_view")])
    user = User(email="360-tenant@example.com", hashed_password="unused", role=role, is_active=True)
    db.add(user); db.flush()
    own = Employee(employee_id="360-TENANT-OWN", first_name="Own", last_name="Employee", date_of_joining=date.today(), branch_id=branches[0].id, user_id=user.id)
    other = Employee(employee_id="360-TENANT-OTHER", first_name="Other", last_name="Employee", date_of_joining=date.today(), branch_id=branches[1].id)
    db.add_all([own, other]); db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(user.id)}
    assert client.get(f"/api/v1/employees/{own.id}/360", headers=headers).status_code == 200
    assert client.get(f"/api/v1/employees/{other.id}/360", headers=headers).status_code == 404
