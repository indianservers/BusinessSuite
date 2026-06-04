from datetime import date

from app.db.init_db import init_db
from app.models.employee import Employee
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_biometric_adapter_import_dedupes_and_reconciliation_flags_missing_out(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    device = client.post("/api/v1/attendance/biometric/devices", json={
        "name": "Factory Gate 1",
        "vendor": "eSSL",
        "device_code": "ESSL-MARKET-READY",
    }, headers=headers)
    assert device.status_code == 201
    device_id = device.json()["id"]

    csv_text = "\n".join([
        "employee_code,punch_time,punch_type",
        "DEMO-EMP-001,2026-05-03 09:00:00,IN",
        "DEMO-EMP-001,2026-05-03 18:00:00,OUT",
        "DEMO-EMP-001,2026-05-04 09:00:00,IN",
    ])
    imported = client.post("/api/v1/attendance/biometric/import-adapter", json={
        "adapter": "essl",
        "device_id": device_id,
        "source_filename": "essl-market-ready.csv",
        "csv_text": csv_text,
    }, headers=headers)
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported_rows"] == 3
    assert imported.json()["skipped_rows"] == 0

    duplicate = client.post("/api/v1/attendance/biometric/import-adapter", json={
        "adapter": "essl",
        "device_id": device_id,
        "csv_text": csv_text,
    }, headers=headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["imported_rows"] == 0
    assert duplicate.json()["skipped_rows"] == 3

    reconciled = client.post("/api/v1/attendance/biometric/reconcile", json={
        "from_date": date(2026, 5, 3).isoformat(),
        "to_date": date(2026, 5, 4).isoformat(),
        "employee_id": employee.id,
    }, headers=headers)
    assert reconciled.status_code == 200, reconciled.text
    body = reconciled.json()
    assert body["reconciled_days"] == 1
    assert body["missing_punch_count"] == 1
    assert body["payroll_blocking"] is True
    assert body["missing_punches"][0]["missing"] == "OUT"

    report = client.get(
        "/api/v1/attendance/reports/missing-punches",
        params={"from_date": "2026-05-04", "to_date": "2026-05-04", "employee_id": employee.id},
        headers=headers,
    )
    assert report.status_code == 200
    assert report.json()["rows"][0]["employee_code"] == "DEMO-EMP-001"


def test_payroll_export_validation_flags_bank_and_statutory_identifier_gaps(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    ensure_payroll_ready(db, 5, 2026)

    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    employee.account_number = None
    employee.ifsc_code = None
    employee.uan_number = None
    db.commit()

    bank_readiness = client.get(f"/api/v1/payroll/runs/{run_id}/exports/bank_advice/validate", headers=headers)
    assert bank_readiness.status_code == 200
    bank_body = bank_readiness.json()
    assert bank_body["ready"] is False
    assert set(bank_body["scope"]) == {"company_id", "branch_id", "department_id", "pay_group_id", "employee_category"}
    assert any("Bank details missing" in issue["message"] for issue in bank_body["issues"])

    pf_readiness = client.get(f"/api/v1/payroll/runs/{run_id}/exports/pf_ecr/validate", headers=headers)
    assert pf_readiness.status_code == 200
    pf_body = pf_readiness.json()
    assert pf_body["ready"] is False
    assert any("UAN is required" in issue["message"] for issue in pf_body["issues"])

    generated = client.post(f"/api/v1/payroll/runs/{run_id}/exports/bank_advice", headers=headers)
    assert generated.status_code == 201
    assert "readiness issue" in generated.json()["remarks"]
