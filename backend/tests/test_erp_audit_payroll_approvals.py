from decimal import Decimal

import pytest

from app.models.employee import Employee
from app.models.payroll import PayrollComponent, PayrollRecord, SalaryAdvance
from tests.payroll_test_utils import init_payroll_test_db, ensure_payroll_ready
from tests.test_expense_payroll_linkage import _login


@pytest.mark.parametrize("approved,expected", [("0", Decimal("0")), ("500", Decimal("500")), (None, Decimal("2500"))])
def test_audit_advance_approval_and_payroll_recovery_preserve_zero(client, db, approved, expected):
    init_payroll_test_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    ensure_payroll_ready(db, 5, 2026)
    created = client.post("/api/v1/payroll/salary-advances", headers=headers, json={"employee_id": employee.id, "requested_amount": "2500", "requested_deduction_month": 5, "requested_deduction_year": 2026})
    assert created.status_code == 201, created.text
    advance_id = created.json()["id"]
    reviewed = client.put(f"/api/v1/payroll/salary-advances/{advance_id}/review", headers=headers, json={"action": "approve", "approved_amount": approved})
    assert reviewed.status_code == 200, reviewed.text
    assert Decimal(str(reviewed.json()["approved_amount"])) == expected
    if approved is None:
        # Older approved rows can have NULL rather than a reviewed amount.
        db.get(SalaryAdvance, advance_id).approved_amount = None
        db.commit()
    run = client.post("/api/v1/payroll/run", headers=headers, json={"month": 5, "year": 2026})
    assert run.status_code == 201, run.text
    record = db.query(PayrollRecord).filter_by(payroll_run_id=run.json()["id"], employee_id=employee.id).one()
    recoveries = db.query(PayrollComponent).filter_by(record_id=record.id, component_name="Salary Advance Recovery").all()
    assert sum((row.amount for row in recoveries), Decimal("0")) == expected
    advance = db.get(SalaryAdvance, advance_id)
    original = (advance.status, advance.approved_amount, advance.payroll_record_id, advance.reviewed_by, advance.reviewed_at, advance.review_remarks)
    for action in ["approve", "reject"]:
        response = client.put(f"/api/v1/payroll/salary-advances/{advance_id}/review", headers=headers, json={"action": action, "approved_amount": "100", "remarks": "Attempt to change recovered advance"})
        assert response.status_code == 409, response.text
        db.refresh(advance)
        assert (advance.status, advance.approved_amount, advance.payroll_record_id, advance.reviewed_by, advance.reviewed_at, advance.review_remarks) == original


def test_audit_advance_review_rejects_negative_and_excess_approvals_without_writing(client, db):
    init_payroll_test_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    created = client.post("/api/v1/payroll/salary-advances", headers=headers, json={"employee_id": employee.id, "requested_amount": "2500", "requested_deduction_month": 5, "requested_deduction_year": 2026})
    assert created.status_code == 201, created.text
    advance = db.get(SalaryAdvance, created.json()["id"])
    for amount in ["-1", "2500.01"]:
        response = client.put(f"/api/v1/payroll/salary-advances/{advance.id}/review", headers=headers, json={"action": "approve", "approved_amount": amount})
        assert response.status_code == 422, response.text
        db.refresh(advance)
        assert advance.status == "Pending"
        assert advance.approved_amount == 0


def test_audit_reviewed_advance_cannot_change_decision_before_payroll(client, db):
    init_payroll_test_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    for decision in ["approve", "reject"]:
        created = client.post("/api/v1/payroll/salary-advances", headers=headers, json={"employee_id": employee.id, "requested_amount": "2500", "requested_deduction_month": 5, "requested_deduction_year": 2026})
        assert created.status_code == 201, created.text
        path = f"/api/v1/payroll/salary-advances/{created.json()['id']}/review"
        first = client.put(path, headers=headers, json={"action": decision, "approved_amount": "500", "remarks": "Original decision"})
        assert first.status_code == 200, first.text
        advance = db.get(SalaryAdvance, created.json()["id"])
        original = (advance.status, advance.approved_amount, advance.reviewed_by, advance.reviewed_at, advance.review_remarks)
        for repeated_decision in ["approve", "reject"]:
            response = client.put(path, headers=headers, json={"action": repeated_decision, "approved_amount": "100", "remarks": "Changed decision"})
            assert response.status_code == 409, response.text
            db.refresh(advance)
            assert (advance.status, advance.approved_amount, advance.reviewed_by, advance.reviewed_at, advance.review_remarks) == original
