from tests.payroll_test_utils import init_payroll_test_db as init_db
from app.models.employee import Employee
from app.models.payroll import (
    PayrollPreRunCheck,
    PayrollRecord,
    PayrollRun,
    PayrollRunAuditLog,
    Reimbursement,
    SalaryRevisionRequest,
)
from tests.payroll_test_utils import ensure_payroll_ready, commit_payroll_fixture


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
    commit_payroll_fixture(db)

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "force_run": True}, headers=headers)

    assert response.status_code == 201
    run_id = response.json()["id"]
    checks = db.query(PayrollPreRunCheck).filter(PayrollPreRunCheck.payroll_run_id == run_id).all()
    check_types = {check.check_type for check in checks}
    assert "pending_salary_revisions" in check_types
    assert "pending_reimbursements" in check_types
    assert "negative_net_salary" in check_types
    assert "tax_declaration_readiness" in check_types


def test_default_branch_rerun_reuses_run_and_replaces_checks(client, db):
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    init_db(db)
    headers = _login(client)
    ensure_payroll_ready(db, 5, 2026)
    payload = {"month": 5, "year": 2026, "force_run": True}
    first = client.post("/api/v1/payroll/run", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    run_id = first.json()["id"]
    branch_id = first.json()["branch_id"]
    assert branch_id is not None
    record_count = db.query(PayrollRecord).filter_by(payroll_run_id=run_id).count()
    assert record_count > 0
    first_count = db.query(PayrollPreRunCheck).filter_by(payroll_run_id=run_id).count()
    repeated = client.post("/api/v1/payroll/run", headers=headers, json=payload)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == run_id
    assert db.query(PayrollRecord).filter_by(payroll_run_id=run_id).count() == record_count
    checks = db.query(PayrollPreRunCheck).filter_by(payroll_run_id=run_id).all()
    assert len(checks) == first_count
    stamps = db.query(BranchOwnership).filter_by(resource_table=PayrollPreRunCheck.__tablename__).all()
    assert {stamp.resource_key for stamp in stamps} == {str(check.id) for check in checks}
    assert all(stamp.branch_id == branch_id for stamp in stamps)

    sibling = Branch(company_id=first.json()["company_id"], name="Payroll sibling", code="PAY-SIB")
    db.add(sibling)
    commit_payroll_fixture(db)
    sibling_run = client.post("/api/v1/payroll/run", headers={**headers, "X-Suite-Branch": str(sibling.id)}, json=payload)
    assert sibling_run.status_code == 201, sibling_run.text
    assert sibling_run.json()["id"] != run_id
    assert sibling_run.json()["branch_id"] == sibling.id
    assert db.query(PayrollPreRunCheck).filter_by(payroll_run_id=run_id).count() == first_count
    forbidden = client.post("/api/v1/payroll/run", headers={**headers, "X-Suite-Branch": str(branch_id)},
                            json={**payload, "branch_id": sibling.id})
    assert forbidden.status_code == 403, forbidden.text
    assert db.get(PayrollRun, run_id) is not None
    assert db.get(PayrollRun, sibling_run.json()["id"]) is not None
    assert db.query(PayrollRecord).filter_by(payroll_run_id=run_id).count() == record_count
