from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import (
    PayrollPreRunCheck,
    PayrollRecord,
    PayrollRun,
    PayrollRunAuditLog,
    Reimbursement,
    SalaryRevisionRequest,
)
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_payroll_run_blocks_on_readiness_without_force(client, db):
    init_db(db)
    headers = _login(client)

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["message"] == "Payroll readiness checks failed"
    readiness = detail["readiness"]
    assert readiness["critical_issue_count"] > 0
    assert readiness["issues"]["attendance_not_locked"]["severity"] == "Critical"


def test_payroll_force_run_persists_readiness_warnings(client, db):
    init_db(db)
    headers = _login(client)

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "force_run": True}, headers=headers)

    assert response.status_code == 201
    run_id = response.json()["id"]
    checks = db.query(PayrollPreRunCheck).filter(PayrollPreRunCheck.payroll_run_id == run_id).all()
    assert any(check.check_type == "attendance_not_locked" and check.severity == "Critical" for check in checks)
    assert db.query(PayrollRunAuditLog).filter(
        PayrollRunAuditLog.payroll_run_id == run_id,
        PayrollRunAuditLog.action == "payroll_force_run_readiness_warnings",
    ).first()


def test_payroll_readiness_checks_hrms_trust_blockers(client, db):
    init_db(db)
    headers = _login(client)
    ensure_payroll_ready(db, 5, 2026)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    db.add(SalaryRevisionRequest(
        employee_id=employee.id,
        current_ctc=600000,
        proposed_ctc=720000,
        effective_from=employee.date_of_joining,
        reason="Annual revision pending checker approval",
        status="Pending",
    ))
    db.add(Reimbursement(
        employee_id=employee.id,
        category="Travel",
        amount=1250,
        date=employee.date_of_joining,
        status="Pending",
    ))
    prior_run = PayrollRun(month=5, year=2026, status="calculated")
    db.add(prior_run)
    db.flush()
    db.add(PayrollRecord(
        payroll_run_id=prior_run.id,
        employee_id=employee.id,
        gross_salary=1000,
        total_deductions=1500,
        net_salary=-500,
    ))
    db.commit()

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "force_run": True}, headers=headers)

    assert response.status_code == 201
    run_id = response.json()["id"]
    checks = db.query(PayrollPreRunCheck).filter(PayrollPreRunCheck.payroll_run_id == run_id).all()
    check_types = {check.check_type for check in checks}
    assert "pending_salary_revisions" in check_types
    assert "pending_reimbursements" in check_types
    assert "negative_net_salary" in check_types
    assert "tax_declaration_readiness" in check_types
