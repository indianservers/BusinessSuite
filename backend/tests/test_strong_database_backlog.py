from tests.security_file_fixtures import uploaded_reference
from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollRecord, PayrollRun


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_helpdesk_sla_escalation_and_knowledge_base(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")

    category = client.post(
        "/api/v1/helpdesk/categories",
        params={"name": "Payroll", "sla_hours": 8, "assigned_team": "HR Ops"},
        headers=admin_headers,
    )
    assert category.status_code == 201
    category_id = category.json()["id"]

    article = client.post(
        "/api/v1/helpdesk/knowledge",
        json={
            "category_id": category_id,
            "title": "How to read payslip",
            "body": "Gross minus deductions equals net pay.",
            "keywords": "payslip,payroll",
            "is_published": True,
        },
        headers=admin_headers,
    )
    assert article.status_code == 201
    assert article.json()["published_at"] is not None

    ticket = client.post(
        "/api/v1/helpdesk/tickets",
        params={
            "subject": "Payslip issue",
            "description": "My deduction is incorrect",
            "category_id": category_id,
            "priority": "High",
        },
        headers=employee_headers,
    )
    assert ticket.status_code == 201
    assert ticket.json()["resolution_due_at"] is not None

    escalated = client.put(
        f"/api/v1/helpdesk/tickets/{ticket.json()['id']}/escalate",
        json={"escalation_reason": "Payroll close is today"},
        headers=admin_headers,
    )
    assert escalated.status_code == 200

    rule = client.post(
        "/api/v1/helpdesk/escalation-rules",
        json={"category_id": category_id, "priority": "High", "escalate_after_hours": 2, "escalation_team": "HR Head"},
        headers=admin_headers,
    )
    assert rule.status_code == 201

    knowledge = client.get("/api/v1/helpdesk/knowledge", headers=employee_headers)
    assert knowledge.status_code == 200
    assert any(item["title"] == "How to read payslip" for item in knowledge.json())


def test_payroll_database_backlog_foundations(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("600000"),
        effective_from=date(2026, 5, 1),
        is_active=True,
    ))
    run = PayrollRun(month=5, year=2026, status="Locked", total_gross=0, total_deductions=0, total_net=0)
    db.add(run)
    db.flush()
    db.add(PayrollRecord(
        payroll_run_id=run.id,
        employee_id=employee.id,
        gross_salary=Decimal("50000"),
        total_deductions=Decimal("5000"),
        net_salary=Decimal("45000"),
        basic=Decimal("20000"),
        hra=Decimal("10000"),
    ))
    db.commit()

    revision = client.post(
        "/api/v1/payroll/salary-revisions",
        json={
            "employee_id": employee.id,
            "proposed_ctc": "720000",
            "effective_from": "2026-06-01",
            "reason": "Annual increment",
        },
        headers=admin_headers,
    )
    assert revision.status_code == 201
    approved_revision = client.put(
        f"/api/v1/payroll/salary-revisions/{revision.json()['id']}/review",
        json={"action": "approve", "remarks": "Finance approved"},
        headers=admin_headers,
    )
    assert approved_revision.status_code == 200
    assert approved_revision.json()["status"] == "Applied"
    audit = client.get(f"/api/v1/payroll/salary-audit?employee_id={employee.id}", headers=admin_headers)
    assert audit.status_code == 200
    assert audit.json()[0]["new_value_masked"].startswith("***")

    unlock = client.post(
        f"/api/v1/payroll/runs/{run.id}/unlock-requests",
        json={"reason": "Manual arrear missed"},
        headers=admin_headers,
    )
    assert unlock.status_code == 201
    reviewed_unlock = client.put(
        f"/api/v1/payroll/unlock-requests/{unlock.json()['id']}/review",
        json={"action": "approve", "remarks": "Allowed once"},
        headers=admin_headers,
    )
    assert reviewed_unlock.status_code == 200
    assert reviewed_unlock.json()["status"] == "Approved"

    check = client.post(
        f"/api/v1/payroll/runs/{run.id}/pre-run-checks",
        json={"check_type": "missing_attendance", "status": "Warning", "severity": "Medium", "message": "1 employee missing"},
        headers=admin_headers,
    )
    assert check.status_code == 201

    manual = client.post(
        f"/api/v1/payroll/runs/{run.id}/manual-inputs",
        json={"employee_id": employee.id, "input_type": "Bonus", "component_name": "Project Bonus", "amount": "5000"},
        headers=admin_headers,
    )
    assert manual.status_code == 201
    manual_review = client.put(
        f"/api/v1/payroll/manual-inputs/{manual.json()['id']}/review",
        json={"action": "approve"},
        headers=admin_headers,
    )
    assert manual_review.status_code == 200
    assert manual_review.json()["status"] == "Approved"

    publish = client.post(
        f"/api/v1/payroll/runs/{run.id}/payslip-publish",
        json={"email_dispatch_status": "Queued"},
        headers=admin_headers,
    )
    assert publish.status_code == 201
    assert publish.json()["published_count"] == 1

    reimbursement = client.post(
        "/api/v1/payroll/reimbursements",
        json={"category": "Travel", "amount": "1200", "date": "2026-05-12", "description": "Client visit"},
        headers=employee_headers,
    )
    assert reimbursement.status_code == 201
    reimbursement_review = client.put(
        f"/api/v1/payroll/reimbursements/{reimbursement.json()['id']}/review",
        json={"action": "approve", "remarks": "Valid bill"},
        headers=admin_headers,
    )
    assert reimbursement_review.status_code == 200
    ledger = client.get(f"/api/v1/payroll/reimbursements/{reimbursement.json()['id']}/ledger", headers=admin_headers)
    assert ledger.status_code == 200
    assert len(ledger.json()) == 2

    loan = client.post(
        "/api/v1/payroll/loans",
        json={
            "employee_id": employee.id,
            "loan_type": "Salary Advance",
            "principal_amount": "60000",
            "interest_rate": "0",
            "emi_amount": "10000",
            "start_month": 6,
            "start_year": 2026,
            "tenure_months": 6,
        },
        headers=admin_headers,
    )
    assert loan.status_code == 201
    installments = client.get(f"/api/v1/payroll/loans/{loan.json()['id']}/installments", headers=admin_headers)
    assert installments.status_code == 200
    assert len(installments.json()) == 6

    settlement = client.post(
        "/api/v1/payroll/settlements",
        json={
            "employee_id": employee.id,
            "settlement_date": "2026-07-31",
            "leave_encashment_amount": "15000",
            "notice_recovery_amount": "5000",
            "gratuity_amount": "20000",
            "loan_recovery_amount": "10000",
            "settlement_letter_url": uploaded_reference('settlements/demo.pdf'),
            "lines": [{"line_type": "Payable", "component_name": "Bonus", "amount": "3000"}],
        },
        headers=admin_headers,
    )
    assert settlement.status_code == 201
    assert Decimal(str(settlement.json()["net_payable"])) == Decimal("23000.00")
