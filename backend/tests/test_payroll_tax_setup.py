from tests.security_file_fixtures import uploaded_reference
from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_payroll_setup_masters(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")

    group = client.post("/api/v1/payroll/setup/pay-groups", json={
        "name": "India Monthly",
        "code": "IN-MONTHLY",
        "description": "Default India payroll group",
        "pay_frequency": "Monthly",
    }, headers=admin_headers)
    assert group.status_code == 201
    group_id = group.json()["id"]

    calendar = client.post("/api/v1/payroll/setup/calendars", json={
        "pay_group_id": group_id,
        "month": 5,
        "year": 2026,
        "period_start": "2026-05-01",
        "period_end": "2026-05-31",
        "payroll_date": "2026-05-31",
        "attendance_cutoff_date": "2026-05-25",
    }, headers=admin_headers)
    assert calendar.status_code == 201
    assert calendar.json()["status"] == "Open"

    rule = client.post("/api/v1/payroll/setup/compliance-rules", json={
        "state": "Telangana",
        "rule_type": "PT",
        "salary_from": "20000",
        "salary_to": "9999999",
        "employee_amount": "200",
        "effective_from": "2026-04-01",
    }, headers=admin_headers)
    assert rule.status_code == 201
    assert rule.json()["employee_amount"] == "200.00"

    bank = client.post("/api/v1/payroll/setup/bank-advice-formats", json={
        "name": "HDFC Netbanking CSV",
        "bank_name": "HDFC Bank",
        "file_format": "CSV",
        "column_order": "employee_id,employee_name,account_number,ifsc,net_salary",
    }, headers=admin_headers)
    assert bank.status_code == 201
    assert bank.json()["bank_name"] == "HDFC Bank"


def test_tax_declaration_proof_and_projection(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("800000"),
        basic=Decimal("30000"),
        hra=Decimal("15000"),
        effective_from=date(2026, 4, 1),
        is_active=True,
    ))
    db.commit()

    cycle = client.post("/api/v1/payroll/tax/cycles", json={
        "name": "FY 2026-27",
        "financial_year": "2026-27",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
        "proof_due_date": "2027-01-31",
    }, headers=admin_headers)
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]

    declaration = client.post("/api/v1/payroll/tax/declarations", json={
        "cycle_id": cycle_id,
        "section": "80C",
        "declared_amount": "150000",
        "description": "ELSS and PF",
    }, headers=employee_headers)
    assert declaration.status_code == 201
    declaration_id = declaration.json()["id"]

    proof = client.post("/api/v1/payroll/tax/proofs", json={
        "declaration_id": declaration_id,
        "file_url": uploaded_reference('tax/elss.pdf'),
        "original_filename": "elss.pdf",
    }, headers=employee_headers)
    assert proof.status_code == 201
    assert proof.json()["status"] == "Submitted"

    verified = client.put(f"/api/v1/payroll/tax/proofs/{proof.json()['id']}/verify", json={
        "status": "Verified",
        "verification_remarks": "Proof matches declaration",
    }, headers=admin_headers)
    assert verified.status_code == 200

    projection = client.get(
        f"/api/v1/payroll/tax/projection?cycle_id={cycle_id}",
        headers=employee_headers,
    )
    assert projection.status_code == 200
    assert projection.json()["approved_amount"] == 150000
    assert projection.json()["projected_taxable_income"] == 650000
