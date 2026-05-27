from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.payroll import PayrollRun, Reimbursement


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
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
        finance_approved_by=1,
    )
    db.add(claim)
    db.commit()

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
