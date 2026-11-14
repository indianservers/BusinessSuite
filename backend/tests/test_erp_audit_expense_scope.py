from app.core.config import settings
from datetime import date

import pytest

from app.models.company import Department
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.payroll import PayrollRun, Reimbursement
from tests.payroll_test_utils import commit_payroll_fixture, init_payroll_test_db


@pytest.mark.parametrize("scope_name", ["department_id", "employee_category"])
@pytest.mark.parametrize("excluded_currency", ["INR", "USD"])
def test_expense_link_uses_selected_payroll_employee_scope(client, db, scope_name, excluded_currency):
    init_payroll_test_db(db)
    login = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": settings.BOOTSTRAP_ADMIN_PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    department = Department(name="Expense scope department", code="EXP-SCOPE", branch_id=employee.branch_id)
    db.add(department)
    db.flush()
    employee.department_id = department.id
    employee.worker_category = "ExpenseScopeQA"
    other = Employee(employee_id="EXP-SCOPE-OTHER", first_name="Other", last_name="Employee", date_of_joining=date(2024, 1, 1), branch_id=employee.branch_id, worker_category="Other", status="Active")
    db.add(other)
    db.flush()
    scopes = {"department_id": department.id, "employee_category": "ExpenseScopeQA"}
    run = PayrollRun(month=5, year=2026, status="approved", **{scope_name: scopes[scope_name]})
    selected = ExpenseClaim(employee_id=employee.id, claim_number="EXP-SCOPE-IN", claim_type="Travel", expense_date=date(2026, 5, 12), amount=100, approved_amount=100, currency="INR", status="finance_approved")
    # An out-of-scope claim must neither link nor require an FX rate.
    excluded = ExpenseClaim(employee_id=other.id, claim_number="EXP-SCOPE-OUT", claim_type="Travel", expense_date=date(2026, 5, 12), amount=20, approved_amount=20, currency=excluded_currency, status="finance_approved")
    db.add_all([run, selected, excluded])
    commit_payroll_fixture(db)
    response = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["claims_found"] == 1
    assert response.json()["linked_claim_ids"] == [selected.id]
    db.refresh(selected)
    db.refresh(excluded)
    assert selected.payroll_run_id == run.id
    assert excluded.payroll_reimbursement_id is None
    assert excluded.payroll_run_id is None
    assert db.query(Reimbursement).filter_by(employee_id=other.id).count() == 0
