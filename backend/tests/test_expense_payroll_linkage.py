from app.core.config import settings
from tests.payroll_test_utils import commit_payroll_fixture
from datetime import date
from decimal import Decimal
import pytest

from tests.payroll_test_utils import init_payroll_test_db as init_db
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.payroll import PayrollExchangeRate, PayrollRun, Reimbursement
from app.models.user import User


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": settings.BOOTSTRAP_ADMIN_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_link_expense_claims_creates_traceable_reimbursement_and_skips_duplicates(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    run = PayrollRun(
        month=5,
        year=2026,
        status="approved",
        pay_period_start=date(2026, 5, 1),
        pay_period_end=date(2026, 5, 31),
    )
    db.add(run)
    db.flush()
    claim = ExpenseClaim(
        employee_id=employee.id,
        claim_number="EXP-LINK-001",
        claim_type="Travel",
        expense_date=date(2026, 5, 12),
        amount=Decimal("2500"),
        approved_amount=Decimal("2000"),
        currency="INR",
        receipt_url="/uploads/expenses/taxi.pdf",
        status="finance_approved",
        finance_approved_by=db.query(User.id).filter(User.email == "admin@aihrms.com").scalar(),
    )
    db.add(claim)
    commit_payroll_fixture(db)

    first = client.post(
        "/api/v1/payroll/reimbursements/link-expense-claims",
        params={"payroll_run_id": run.id},
        headers=headers,
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["claims_found"] == 1
    assert first_body["reimbursements_created"] == 1
    assert first_body["skipped_duplicates"] == 0
    assert first_body["linked_claim_ids"] == [claim.id]

    db.refresh(claim)
    reimbursement = db.query(Reimbursement).filter(Reimbursement.id == claim.payroll_reimbursement_id).first()
    assert reimbursement
    assert reimbursement.amount == Decimal("2000.00")
    assert claim.payroll_run_id == run.id

    second = client.post(
        "/api/v1/payroll/reimbursements/link-expense-claims",
        params={"payroll_run_id": run.id},
        headers=headers,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["claims_found"] == 1
    assert second_body["reimbursements_created"] == 0
    assert second_body["skipped_duplicates"] == 1
    assert db.query(Reimbursement).filter(Reimbursement.employee_id == employee.id, Reimbursement.receipt_url == claim.receipt_url).count() == 1


@pytest.mark.parametrize("approved_amount,expected", [(Decimal("0"), Decimal("0")), (None, Decimal("2500"))])
def test_expense_link_preserves_zero_approval_and_legacy_missing_amount(client, db, approved_amount, expected):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    run = PayrollRun(month=5, year=2026, status="approved", pay_period_start=date(2026, 5, 1), pay_period_end=date(2026, 5, 31))
    db.add(run)
    claim = ExpenseClaim(employee_id=employee.id, claim_number="EXP-AUDIT-ZERO", claim_type="Travel", expense_date=date(2026, 5, 12), amount=Decimal("2500"), approved_amount=approved_amount, currency="INR", status="finance_approved")
    db.add(claim)
    commit_payroll_fixture(db)
    # ORM defaults can populate a missing amount. Preserve the explicit legacy
    # NULL case separately from a reviewer-approved zero.
    claim.approved_amount = approved_amount
    db.commit()
    response = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    assert response.status_code == 200, response.text
    db.refresh(claim)
    reimbursement = db.get(Reimbursement, claim.payroll_reimbursement_id)
    assert reimbursement.amount == expected
    repeated = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["reimbursements_created"] == 0


@pytest.mark.parametrize("rate_available", [True, False])
def test_foreign_expenses_convert_to_payroll_currency_atomically(client, db, rate_available):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    run = PayrollRun(month=5, year=2026, status="approved")
    db.add(run)
    local = ExpenseClaim(employee_id=employee.id, claim_number="EXP-FX-LOCAL", claim_type="Travel", expense_date=date(2026, 5, 12), amount=100, approved_amount=100, currency="INR", status="finance_approved")
    foreign = ExpenseClaim(employee_id=employee.id, claim_number="EXP-FX-USD", claim_type="Travel", expense_date=date(2026, 5, 12), amount=20, approved_amount=Decimal("10.01"), currency="usd", description="Taxi", status="finance_approved")
    db.add_all([local, foreign])
    # Future rates must not be used for this payroll period.
    db.add(PayrollExchangeRate(from_currency="USD", to_currency="INR", rate=100, effective_date=date(2026, 5, 2)))
    if rate_available:
        db.add_all([
            PayrollExchangeRate(from_currency="USD", to_currency="INR", rate=80, effective_date=date(2026, 4, 1)),
            PayrollExchangeRate(from_currency="USD", to_currency="INR", rate=Decimal("83.25"), effective_date=date(2026, 5, 1)),
        ])
    commit_payroll_fixture(db)
    response = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    db.refresh(local)
    db.refresh(foreign)
    if not rate_available:
        assert response.status_code == 400, response.text
        assert "USD->INR" in response.json()["detail"]
        assert local.payroll_reimbursement_id is None
        assert foreign.payroll_reimbursement_id is None
        assert db.query(Reimbursement).filter_by(employee_id=employee.id).count() == 0
        return
    assert response.status_code == 200, response.text
    reimbursement = db.get(Reimbursement, foreign.payroll_reimbursement_id)
    assert reimbursement.amount == Decimal("833.33")
    assert "10.01 USD" in reimbursement.description
    assert "83.25" in reimbursement.description
    assert "2026-05-01" in reimbursement.description
    assert foreign.approved_amount == Decimal("10.01")
    assert db.get(Reimbursement, local.payroll_reimbursement_id).amount == Decimal("100")
    again = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    assert again.status_code == 200
    assert again.json()["reimbursements_created"] == 0
    assert db.get(Reimbursement, foreign.payroll_reimbursement_id).amount == Decimal("833.33")


@pytest.mark.parametrize("status", ["locked", "paid", "Locked", "Paid"])
def test_expense_link_cannot_add_inputs_to_frozen_payroll(client, db, status):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    run = PayrollRun(month=5, year=2026, status=status)
    claim = ExpenseClaim(employee_id=employee.id, claim_number="EXP-FROZEN", claim_type="Travel", expense_date=date(2026, 5, 12), amount=100, approved_amount=100, currency="INR", status="finance_approved")
    db.add_all([run, claim])
    commit_payroll_fixture(db)
    response = client.post("/api/v1/payroll/reimbursements/link-expense-claims", params={"payroll_run_id": run.id}, headers=headers)
    assert response.status_code == 400, response.text
    assert "locked" in response.json()["detail"].lower()
    db.refresh(claim)
    assert claim.payroll_run_id is None
    assert claim.payroll_reimbursement_id is None
    assert db.query(Reimbursement).filter_by(employee_id=employee.id).count() == 0
