from datetime import date
from decimal import Decimal

import pytest

from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun, Reimbursement, ReimbursementLedger
from tests.payroll_test_utils import commit_payroll_fixture, ensure_payroll_ready, init_payroll_test_db
from tests.test_expense_payroll_linkage import _login


def test_payroll_consumed_reimbursement_cannot_be_reviewed_again(client, db):
    init_payroll_test_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    ensure_payroll_ready(db, 5, 2026)
    reimbursement = Reimbursement(employee_id=employee.id, category="Travel", amount=Decimal("1250"), date=date(2026, 5, 12), status="Approved")
    db.add(reimbursement)
    commit_payroll_fixture(db)
    run = client.post("/api/v1/payroll/run", headers=headers, json={"month": 5, "year": 2026})
    assert run.status_code == 201, run.text
    db.refresh(reimbursement)
    assert reimbursement.status == "Paid"
    original = (reimbursement.status, reimbursement.payroll_record_id, reimbursement.approved_by)
    record = db.get(PayrollRecord, reimbursement.payroll_record_id)
    original_pay = (record.gross_salary, record.total_deductions, record.net_salary)
    ledger_count = db.query(ReimbursementLedger).filter_by(reimbursement_id=reimbursement.id).count()
    for action in ["approve", "reject"]:
        response = client.put(f"/api/v1/payroll/reimbursements/{reimbursement.id}/review", headers=headers, json={"action": action, "remarks": "Attempt to change payroll input"})
        assert response.status_code == 409, response.text
        db.refresh(reimbursement)
        assert (reimbursement.status, reimbursement.payroll_record_id, reimbursement.approved_by) == original
        assert db.query(ReimbursementLedger).filter_by(reimbursement_id=reimbursement.id).count() == ledger_count
    rerun = client.post("/api/v1/payroll/run", headers=headers, json={"month": 5, "year": 2026})
    assert rerun.status_code == 201, rerun.text
    updated = db.query(PayrollRecord).filter_by(payroll_run_id=rerun.json()["id"], employee_id=employee.id).one()
    assert (updated.gross_salary, updated.total_deductions, updated.net_salary) == original_pay


def test_unconsumed_reimbursement_review_respects_locked_period(client, db):
    init_payroll_test_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    reimbursement = Reimbursement(employee_id=employee.id, amount=Decimal("1250"), date=date(2026, 5, 12), status="Pending")
    db.add_all([PayrollRun(month=5, year=2026, status="locked"), reimbursement])
    commit_payroll_fixture(db)
    for action in ["approve", "reject"]:
        response = client.put(f"/api/v1/payroll/reimbursements/{reimbursement.id}/review", headers=headers, json={"action": action})
        assert response.status_code == 400, response.text
        assert "locked" in response.json()["detail"].lower()
        db.refresh(reimbursement)
        assert reimbursement.status == "Pending"
        assert reimbursement.approved_by is None
        assert db.query(ReimbursementLedger).filter_by(reimbursement_id=reimbursement.id).count() == 0


@pytest.mark.parametrize("action,expected_status", [("approve", "Approved"), ("reject", "Rejected")])
def test_pending_reimbursement_review_retains_submission_and_decision_trail(client, db, action, expected_status):
    init_payroll_test_db(db)
    headers = _login(client)
    login = client.post("/api/v1/auth/login", json={"email": "employee@aihrms.com", "password": "Employee@123456"})
    assert login.status_code == 200
    employee_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post("/api/v1/payroll/reimbursements", headers=employee_headers, json={"category": "Travel", "amount": "1250", "date": "2026-05-12", "description": "Taxi receipt"})
    assert created.status_code == 201, created.text
    reimbursement_id = created.json()["id"]
    reviewed = client.put(f"/api/v1/payroll/reimbursements/{reimbursement_id}/review", headers=headers, json={"action": action, "remarks": "Receipt reviewed"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == expected_status
    ledger = client.get(f"/api/v1/payroll/reimbursements/{reimbursement_id}/ledger", headers=headers)
    assert ledger.status_code == 200
    entries = sorted(ledger.json(), key=lambda row: row["id"])
    assert len(entries) == 2
    assert entries[0]["action"] == "Submitted"
    assert entries[1]["status_from"] == "Pending"
    assert entries[1]["status_to"] == expected_status
    assert entries[1]["remarks"] == "Receipt reviewed"
    assert Decimal(str(entries[1]["amount"])) == Decimal("1250")
