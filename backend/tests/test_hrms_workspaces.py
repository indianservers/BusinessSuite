from datetime import date
from decimal import Decimal
from app.models.employee import Employee
from app.models.user import User
from app.models.asset import Asset, AssetAssignment
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.expense import ExpenseClaim


def people(db):
    manager = db.query(User).filter(User.email == "testadmin@test.com").one()
    lead = Employee(employee_id="WS-MANAGER", first_name="Team", last_name="Manager", date_of_joining=date.today(), user_id=manager.id)
    db.add(lead); db.flush()
    report = Employee(employee_id="WS-REPORT", first_name="Direct", last_name="Report", date_of_joining=date.today(), reporting_manager_id=lead.id)
    other = Employee(employee_id="WS-OTHER", first_name="Other", last_name="Team", date_of_joining=date.today())
    db.add_all([report, other]); db.commit()
    return report, other


def test_manager_decisions_followups_and_outside_team_guard(client, db, superuser_headers):
    report, other = people(db)
    claims = [ExpenseClaim(employee_id=e.id, claim_number=f"TEAM-{e.id}", claim_type="Travel", expense_date=date.today(), amount=100) for e in [report, other]]
    db.add_all(claims); db.commit()
    result = client.get("/api/v1/reports/my-team", headers=superuser_headers)
    assert result.status_code == 200, result.text
    assert [r["id"] for r in result.json()["team"]] == [report.id]
    assert len(result.json()["decisions"]) == 1
    own_id, other_id = [c.id for c in claims]
    assert client.put(f"/api/v1/reports/my-team/decisions/expense/{other_id}", headers=superuser_headers, json={"decision": "approve", "remarks": "Reviewed receipt"}).status_code == 404
    approved = client.put(f"/api/v1/reports/my-team/decisions/expense/{own_id}", headers=superuser_headers, json={"decision": "approve", "remarks": "Reviewed receipt"})
    assert approved.status_code == 200, approved.text
    assert client.put(f"/api/v1/reports/my-team/decisions/expense/{own_id}", headers=superuser_headers, json={"decision": "reject", "remarks": "Changed mind"}).status_code == 409
    follow = client.post("/api/v1/reports/my-team/followups", headers=superuser_headers, json={"employee_id": report.id, "title": "Review travel policy", "due_date": "2026-11-01"})
    assert follow.status_code == 201, follow.text
    assert client.put(f"/api/v1/reports/my-team/followups/{follow.json()['id']}/complete", headers=superuser_headers).status_code == 200
    assert client.get("/api/v1/reports/my-team", headers=superuser_headers).json()["followups"][0]["status"] == "Completed"


def test_bike_assignment_duplicate_return_and_exit_clearance(client, db, superuser_headers):
    report, _ = people(db)
    bike = Asset(asset_tag="BIKE-1", name="Honda company bike", status="Available")
    db.add(bike); db.commit()
    assigned = client.post("/api/v1/assets/assignments", headers=superuser_headers, json={"asset_id": bike.id, "employee_id": report.id, "assigned_date": date.today().isoformat()})
    assert assigned.status_code == 201, assigned.text
    assert client.post("/api/v1/assets/assignments", headers=superuser_headers, json={"asset_id": bike.id, "employee_id": report.id, "assigned_date": date.today().isoformat()}).status_code == 409
    record = ExitRecord(employee_id=report.id, status="In Progress")
    db.add(record); db.flush()
    db.add(ExitChecklistItem(exit_record_id=record.id, task_name="Asset return and condition check", is_completed=True))
    db.commit()
    assert client.put(f"/api/v1/exit/records/{record.id}/complete", headers=superuser_headers).status_code == 409
    assert client.get("/api/v1/assets/exit-clearance", headers=superuser_headers).json()[0]["cleared"] is False
    returned = client.put(f"/api/v1/assets/assignments/{assigned.json()['id']}/return", headers=superuser_headers, params={"condition_at_return": "Damaged"})
    assert returned.status_code == 200, returned.text
    db.refresh(bike); assert bike.status == "Under Repair"
    assert client.get("/api/v1/assets/exit-clearance", headers=superuser_headers).json()[0]["cleared"] is True
    assert client.put(f"/api/v1/exit/records/{record.id}/complete", headers=superuser_headers).status_code == 200
    assert client.put(f"/api/v1/assets/assignments/{assigned.json()['id']}/return", headers=superuser_headers).status_code == 409


def test_search_finds_employee_beyond_first_page_and_statement_currencies(client, db, superuser_headers):
    report, _ = people(db)
    for i in range(105):
        db.add(Employee(employee_id=f"WS-SEARCH-{i}", first_name=f"A{i:03}", last_name="Search", date_of_joining=date.today()))
    db.add(Employee(employee_id="WS-LAST", first_name="Zebra", last_name="Findable", date_of_joining=date.today()))
    for number, status, currency, amount, approved in [(1, "submitted", "INR", "10.25", "0"), (2, "finance_approved", "INR", "20.75", "19.50"), (3, "reimbursed", "INR", "30", "30"), (4, "finance_approved", "USD", "2.50", "2.50")]:
        db.add(ExpenseClaim(employee_id=report.id, claim_number=f"STMT-{number}", claim_type="Travel", expense_date=date.today(), status=status, currency=currency, amount=Decimal(amount), approved_amount=Decimal(approved)))
    db.commit()
    options = client.get("/api/v1/assets/employees", params={"search": "Zebra"}, headers=superuser_headers)
    assert options.status_code == 200, options.text
    assert options.json()[0]["employee_code"] == "WS-LAST"
    statement = client.get(f"/api/v1/expenses/statements/{report.id}", headers=superuser_headers)
    assert statement.status_code == 200, statement.text
    totals = {r["currency"]: r for r in statement.json()["totals"]}
    assert totals["INR"]["claimed"] == "61.00"
    assert totals["INR"]["approved"] == "49.50"
    assert totals["INR"]["outstanding"] == "19.50"
    assert totals["INR"]["paid"] == "30.00"
    assert totals["USD"]["outstanding"] == "2.50"


def test_guided_payroll_requires_paid_references_and_no_duplicate_batch(client, db, superuser_headers):
    from app.models.payroll import PayrollRun, PayrollRecord, PayrollPaymentBatch, PayrollPaymentLine
    report, _ = people(db)
    run = PayrollRun(month=10, year=2026, status="locked")
    db.add(run); db.flush()
    record = PayrollRecord(payroll_run_id=run.id, employee_id=report.id, gross_salary=100, total_deductions=0, net_salary=100)
    db.add(record); db.flush()
    batch = PayrollPaymentBatch(payroll_run_id=run.id, total_amount=100, status="Generated")
    db.add(batch); db.flush()
    line = PayrollPaymentLine(batch_id=batch.id, payroll_record_id=record.id, employee_id=report.id, net_amount=100, payment_status="Pending")
    db.add(line); db.commit()
    def action(value):
        return client.post(f"/api/v1/payroll/runs/{run.id}/guided", headers=superuser_headers, json={"action": value, "remarks": "Bank results checked"})
    assert action("pay").status_code == 409
    assert action("reconcile").status_code == 409
    line.payment_status = "Paid"; db.commit()
    assert action("reconcile").status_code == 409
    line.utr_number = "BANK-REFERENCE-1"; db.commit()
    closed = action("reconcile")
    assert closed.status_code == 200, closed.text
    db.refresh(run); assert run.status == "paid"


def test_receipts_are_validated_and_duplicates_visible_to_reviewers(client, db, superuser_headers):
    report, _ = people(db)
    claims = [ExpenseClaim(employee_id=report.id, claim_number=f"RECEIPT-{i}", claim_type="Travel", expense_date=date.today(), amount=100) for i in [1, 2]]
    db.add_all(claims); db.commit()
    headers = superuser_headers
    invalid = client.post(f"/api/v1/expenses/claims/{claims[0].id}/receipt", headers=headers, files={"file": ("receipt.pdf", b"<html>not a PDF</html>", "application/pdf")})
    assert invalid.status_code == 422
    content = b"%PDF-1.4\nSynthetic receipt content\n%%EOF"
    first = client.post(f"/api/v1/expenses/claims/{claims[0].id}/receipt", headers=headers, files={"file": ("receipt.pdf", content, "application/pdf")})
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/expenses/claims/{claims[1].id}/receipt", headers=headers, files={"file": ("receipt.pdf", content, "application/pdf")})
    assert second.status_code == 200, second.text
    assert second.json()["duplicate_claim_ids"] == [claims[0].id]
    statement = client.get(f"/api/v1/expenses/statements/{report.id}", headers=headers).json()
    assert all(row["duplicate_receipt_claim_ids"] for row in statement["claims"])
