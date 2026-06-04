from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollBankExport, PayrollRun
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ensure_salary(db, employee):
    if not db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active == True).first():
        db.add(
            EmployeeSalary(
                employee_id=employee.id,
                ctc=Decimal("600000"),
                basic=Decimal("20000"),
                hra=Decimal("10000"),
                effective_from=date(2026, 4, 1),
                is_active=True,
            )
        )
        db.commit()


def test_bank_advice_preview_generate_and_download(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    employee.bank_name = "HDFC Bank"
    employee.account_number = "1234567890"
    employee.ifsc_code = "HDFC0001234"
    _ensure_salary(db, employee)
    db.commit()
    ensure_payroll_ready(db, 5, 2026)

    run_response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    run.status = "approved"
    db.commit()

    preview = client.get(f"/api/v1/hrms/payroll/{run_id}/bank-advice/preview?bank_name=HDFC", headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["validation_errors"] == []
    assert body["total_employees"] >= 1
    employee_row = next(row for row in body["rows"] if row["employee_id"] == employee.id)
    assert employee_row["account_number_masked"].endswith("7890")
    assert employee_row["account_number_masked"] != "1234567890"

    export_response = client.post(
        f"/api/v1/hrms/payroll/{run_id}/bank-advice/generate",
        json={"export_type": "txt", "bank_name": "HDFC"},
        headers=headers,
    )
    assert export_response.status_code == 201
    export_body = export_response.json()
    assert export_body["export_type"] == "txt"
    assert export_body["total_amount"] != "0.00"
    assert export_body["file_path"].endswith(".txt")

    export = db.query(PayrollBankExport).filter(PayrollBankExport.id == export_body["id"]).first()
    assert export
    assert export.download_count == 0

    download = client.get(f"/api/v1/hrms/payroll/bank-exports/{export_body['id']}/download", headers=headers)
    assert download.status_code == 200
    assert b"1234567890" in download.content
    db.refresh(export)
    assert export.download_count == 1


def test_bank_advice_generation_blocks_invalid_bank_details(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    _ensure_salary(db, employee)
    db.commit()
    ensure_payroll_ready(db, 6, 2026)

    run_response = client.post("/api/v1/payroll/run", json={"month": 6, "year": 2026}, headers=headers)
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    run.status = "approved"
    employee.bank_name = None
    employee.account_number = None
    employee.ifsc_code = None
    db.commit()

    export_response = client.post(
        f"/api/v1/hrms/payroll/{run_id}/bank-advice/generate",
        json={"export_type": "pdf", "bank_name": "HDFC"},
        headers=headers,
    )
    assert export_response.status_code == 400
    detail = export_response.json()["detail"]
    assert detail["message"] == "Bank-specific file validation failed"
    assert any(item["code"] == "MISSING_ACCOUNT" for item in detail["validation"]["errors"])
