from datetime import date
from decimal import Decimal

import pytest

from app.models.leave import LeaveBalance, LeaveBalanceLedger, LeaveRequest
from tests.rich_text_test_utils import organization_context
from tests.test_leave import _create_employee_with_leave


def context(client, db, next_year=True):
    employee, leave_type, user = _create_employee_with_leave(db, client, {})
    year = date.today().year
    first = db.query(LeaveBalance).filter_by(employee_id=employee.id, leave_type_id=leave_type.id, year=year).one()
    first.allocated = Decimal("1")
    second = None
    if next_year:
        second = LeaveBalance(employee_id=employee.id, leave_type_id=leave_type.id, year=year+1, allocated=Decimal("1"), used=Decimal("0"), pending=Decimal("0"))
        db.add(second)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {"leave_type_id": leave_type.id, "from_date": f"{year}-12-31", "to_date": f"{year+1}-01-01", "reason": "Year boundary test"}
    return employee, first, second, headers, payload


@pytest.mark.parametrize("decision", ["Approved", "Rejected", "Cancelled"])
def test_audit_cross_year_leave_uses_each_year_balance_through_decision(client, db, superuser_headers, decision):
    employee, first, second, headers, payload = context(client, db)
    response = client.post("/api/v1/leave/apply", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    assert Decimal(response.json()["days_count"]) == 2
    db.refresh(first); db.refresh(second)
    assert first.pending == second.pending == 1
    pending = db.query(LeaveBalanceLedger).filter_by(leave_request_id=request_id, transaction_type="request_pending").all()
    assert {(row.year, row.amount) for row in pending} == {(first.year, Decimal("-1")), (second.year, Decimal("-1"))}
    if decision == "Cancelled":
        reviewed = client.put(f"/api/v1/leave/requests/{request_id}/cancel", headers=headers)
    else:
        reviewed = client.put(f"/api/v1/leave/requests/{request_id}/approve", headers=superuser_headers, json={"status": decision, "review_remarks": "Reviewed year boundary"})
    assert reviewed.status_code == 200, reviewed.text
    db.refresh(first); db.refresh(second)
    assert first.pending == second.pending == 0
    assert first.used == second.used == (1 if decision == "Approved" else 0)
    final_kind = {"Approved": "request_approved", "Rejected": "request_rejected", "Cancelled": "request_cancelled"}[decision]
    final = db.query(LeaveBalanceLedger).filter_by(leave_request_id=request_id, transaction_type=final_kind).all()
    assert {row.year for row in final} == {first.year, second.year}
    assert all(row.balance_after == (0 if decision == "Approved" else 1) for row in final)


def test_audit_missing_next_year_allowance_rejects_without_any_pending_or_ledger_write(client, db):
    employee, first, _, headers, payload = context(client, db, next_year=False)
    first.allocated = Decimal("21")
    db.commit()
    response = client.post("/api/v1/leave/apply", headers=headers, json=payload)
    assert response.status_code == 400, response.text
    db.refresh(first)
    assert first.pending == 0
    assert db.query(LeaveRequest).filter_by(employee_id=employee.id).count() == 0
    assert db.query(LeaveBalanceLedger).filter_by(employee_id=employee.id).count() == 0


@pytest.mark.parametrize("ledger_linked", [True, False])
def test_audit_legacy_cross_year_request_restores_the_year_originally_charged(client, db, superuser_headers, ledger_linked):
    employee, first, second, _, payload = context(client, db)
    first.allocated = Decimal("3")
    first.pending = Decimal("2")
    legacy = LeaveRequest(company_id=1, employee_id=employee.id, leave_type_id=first.leave_type_id, from_date=date.fromisoformat(payload["from_date"]), to_date=date.fromisoformat(payload["to_date"]), days_count=Decimal("2"), is_half_day=False, status="Pending", reason="Historical request")
    db.add(legacy)
    db.flush()
    db.add(LeaveBalanceLedger(employee_id=employee.id, leave_type_id=first.leave_type_id, leave_balance_id=first.id if ledger_linked else None, leave_request_id=legacy.id, year=first.year, transaction_type="request_pending", amount=Decimal("-2"), balance_after=Decimal("1"), created_by=employee.user_id))
    db.commit()
    response = client.put(f"/api/v1/leave/requests/{legacy.id}/approve", headers=superuser_headers, json={"status": "Rejected", "review_remarks": "Restore original debit"})
    assert response.status_code == 200, response.text
    db.refresh(first); db.refresh(second)
    assert first.pending == second.pending == 0
    restored = db.query(LeaveBalanceLedger).filter_by(leave_request_id=legacy.id, transaction_type="request_rejected").all()
    assert len(restored) == 1
    assert restored[0].year == first.year
    assert restored[0].amount == 2
    assert restored[0].balance_after == 3
