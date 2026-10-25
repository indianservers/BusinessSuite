from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import PayrollRun, PayrollRecord


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_payroll_record(db, employee_id: int, month: int, year: int, gross: Decimal, net: Decimal):
    run = PayrollRun(month=month, year=year, status="Completed", total_gross=gross, total_net=net)
    db.add(run)
    db.flush()
    record = PayrollRecord(
        payroll_run_id=run.id,
        employee_id=employee_id,
        working_days=22,
        present_days=Decimal("22"),
        lop_days=Decimal("0"),
        paid_days=Decimal("22"),
        basic=gross * Decimal("0.4"),
        hra=gross * Decimal("0.2"),
        gross_salary=gross,
        total_deductions=gross - net,
        net_salary=net,
    )
    db.add(record)
    db.commit()
    db.refresh(run)
    db.refresh(record)
    return run, record


def test_payroll_variance_and_export_batches(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    _seed_payroll_record(db, employee.id, 4, 2026, Decimal("50000"), Decimal("45000"))
    current_run, _ = _seed_payroll_record(db, employee.id, 5, 2026, Decimal("65000"), Decimal("58000"))

    variance = client.get(f"/api/v1/payroll/runs/{current_run.id}/variance", headers=admin_headers)
    assert variance.status_code == 200
    items = variance.json()
    assert len(items) == 1
    assert items[0]["severity"] == "High"
    assert float(items[0]["gross_delta_percent"]) == 30.0

    exported = client.post(
        f"/api/v1/payroll/runs/{current_run.id}/exports/pf_ecr",
        headers=admin_headers,
    )
    assert exported.status_code == 201
    data = exported.json()
    assert data["export_type"] == "pf_ecr"
    assert data["status"] == "Generated"
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(data["output_file_url"]).endswith("/pf_ecr.csv")
    assert data["total_records"] == 1

    audit = client.get(f"/api/v1/payroll/runs/{current_run.id}/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert any(row["action"] == "export_generated" for row in audit.json())


def test_payroll_lock_blocks_sensitive_mutations(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    locked_run = PayrollRun(month=5, year=2026, status="Locked")
    db.add(locked_run)
    db.commit()

    salary = client.post(
        "/api/v1/payroll/salary",
        json={
            "employee_id": employee.id,
            "ctc": "600000",
            "basic": "20000",
            "hra": "10000",
            "effective_from": "2026-05-01",
        },
        headers=admin_headers,
    )
    assert salary.status_code == 400
    assert "locked" in salary.json()["detail"].lower()

    component = client.post(
        "/api/v1/payroll/components",
        json={
            "name": "Special Allowance",
            "code": "SPALL",
            "component_type": "Earning",
            "calculation_type": "Fixed",
            "amount": "1000",
        },
        headers=admin_headers,
    )
    assert component.status_code == 400

    reimbursement = client.post(
        "/api/v1/payroll/reimbursements",
        json={
            "category": "Travel",
            "amount": "1200",
            "date": "2026-05-10",
            "description": "Client visit",
        },
        headers=employee_headers,
    )
    assert reimbursement.status_code == 400, reimbursement.json()


def test_employee_cannot_view_other_employee_payslip(client, db):
    init_db(db)
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    manager = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()
    _seed_payroll_record(db, manager.id, 6, 2026, Decimal("80000"), Decimal("72000"))

    response = client.get(
        f"/api/v1/payroll/payslip?month=6&year=2026&employee_id={manager.id}",
        headers=employee_headers,
    )
    assert response.status_code == 403
