from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, EmployeeStatutoryProfile, ESIRule, PFRule, PayrollRun, StatutoryExport
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _prepare_employee(db):
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    employee.uan_number = "100200300400"
    employee.esic_number = "ESIC12345"
    if not db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active == True).first():
        db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal("360000"), basic=Decimal("12000"), hra=Decimal("4000"), effective_from=date(2026, 4, 1), is_active=True))
    profile = db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == employee.id).first()
    if not profile:
        db.add(EmployeeStatutoryProfile(employee_id=employee.id, uan="100200300400", pf_applicable=True, pension_applicable=True, esi_ip_number="ESIC12345", esi_applicable=True))
    else:
        profile.uan = "100200300400"
        profile.pf_applicable = True
        profile.pension_applicable = True
        profile.esi_ip_number = "ESIC12345"
        profile.esi_applicable = True
    if not db.query(PFRule).filter(PFRule.name == "PF Test Rule").first():
        db.add(PFRule(name="PF Test Rule", wage_ceiling=Decimal("15000"), employee_rate=Decimal("12"), employer_rate=Decimal("12"), eps_rate=Decimal("8.33"), effective_from=date(2026, 4, 1), is_active=True))
    if not db.query(ESIRule).filter(ESIRule.name == "ESI Test Rule").first():
        db.add(ESIRule(name="ESI Test Rule", wage_threshold=Decimal("50000"), employee_rate=Decimal("0.75"), employer_rate=Decimal("3.25"), effective_from=date(2026, 4, 1), is_active=True))
    db.commit()
    return employee


def test_pf_ecr_and_esi_export_generation(client, db):
    init_db(db)
    headers = _login(client)
    employee = _prepare_employee(db)
    ensure_payroll_ready(db, 7, 2026)

    run_response = client.post("/api/v1/payroll/run", json={"month": 7, "year": 2026}, headers=headers)
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    run.status = "locked"
    db.commit()

    pf_preview = client.get(f"/api/v1/hrms/compliance/pf-ecr/preview?payrollRunId={run_id}", headers=headers)
    assert pf_preview.status_code == 200
    assert pf_preview.json()["validation_errors"] == []
    assert any(row["uan"] == "100200300400" for row in pf_preview.json()["rows"])

    pf_export = client.post("/api/v1/hrms/compliance/pf-ecr/generate", json={"payroll_run_id": run_id}, headers=headers)
    assert pf_export.status_code == 201
    assert pf_export.json()["export_type"] == "pf_ecr"

    esi_preview = client.get(f"/api/v1/hrms/compliance/esi/preview?payrollRunId={run_id}", headers=headers)
    assert esi_preview.status_code == 200
    assert esi_preview.json()["validation_errors"] == []
    assert any(row["esic_number"] == "ESIC12345" for row in esi_preview.json()["rows"])

    esi_export = client.post("/api/v1/hrms/compliance/esi/generate", json={"payroll_run_id": run_id}, headers=headers)
    assert esi_export.status_code == 201
    assert esi_export.json()["export_type"] == "esi_challan"

    download = client.get(f"/api/v1/hrms/compliance/exports/{pf_export.json()['id']}/download", headers=headers)
    assert download.status_code == 200
    assert b"100200300400" in download.content
    stored = db.query(StatutoryExport).filter(StatutoryExport.id == pf_export.json()["id"]).first()
    db.refresh(stored)
    assert stored.download_count == 1


def test_pf_generation_reports_missing_uan(client, db):
    init_db(db)
    headers = _login(client)
    employee = _prepare_employee(db)
    ensure_payroll_ready(db, 8, 2026)
    employee.uan_number = None
    profile = db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == employee.id).first()
    profile.uan = None
    db.commit()

    run_response = client.post("/api/v1/payroll/run", json={"month": 8, "year": 2026}, headers=headers)
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    run.status = "locked"
    db.commit()

    generated = client.post("/api/v1/hrms/compliance/pf-ecr/generate", json={"payroll_run_id": run_id}, headers=headers)
    assert generated.status_code == 400
    assert any("UAN is missing or invalid" in item for item in generated.json()["detail"]["validation_errors"])
