from tests.security_file_fixtures import uploaded_reference
from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_statutory_rules_profiles_calculation_challan_and_return_file(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    pf = client.post(
        "/api/v1/payroll/statutory/pf-rules",
        json={
            "name": "India PF FY 2026",
            "wage_ceiling": "15000",
            "employee_rate": "12",
            "employer_rate": "12",
            "edli_rate": "0.5",
            "admin_charge_rate": "0.5",
            "effective_from": "2026-04-01",
        },
        headers=headers,
    )
    assert pf.status_code == 201

    esi = client.post(
        "/api/v1/payroll/statutory/esi-rules",
        json={"name": "India ESI FY 2026", "wage_threshold": "21000", "employee_rate": "0.75", "employer_rate": "3.25", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert esi.status_code == 201

    pt = client.post(
        "/api/v1/payroll/statutory/pt-slabs",
        json={"state": "Telangana", "salary_from": "20000", "employee_amount": "200", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert pt.status_code == 201

    lwf = client.post(
        "/api/v1/payroll/statutory/lwf-slabs",
        json={"state": "Telangana", "salary_from": "0", "employee_amount": "10", "employer_amount": "20", "deduction_month": 12, "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert lwf.status_code == 201

    gratuity = client.post(
        "/api/v1/payroll/statutory/gratuity-rules",
        json={"name": "Payment of Gratuity Act", "days_per_year": "15", "wage_days_divisor": "26", "min_service_years": "5", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert gratuity.status_code == 201

    profile = client.post(
        "/api/v1/payroll/statutory/employee-profiles",
        json={
            "employee_id": employee.id,
            "uan": "100200300400",
            "pf_applicable": True,
            "pension_applicable": True,
            "esi_ip_number": "5200123456",
            "esi_applicable": True,
            "pt_state": "Telangana",
            "lwf_applicable": True,
            "nominee_json": {"name": "Nominee", "relation": "Spouse"},
        },
        headers=headers,
    )
    assert profile.status_code == 201

    pay_group = client.post(
        "/api/v1/payroll/setup/pay-groups",
        json={"name": "Statutory Payroll", "code": "STAT-PAY", "state": "Telangana"},
        headers=headers,
    )
    assert pay_group.status_code == 201
    period = client.post(
        "/api/v1/payroll/setup/periods",
        json={
            "pay_group_id": pay_group.json()["id"],
            "month": 12,
            "year": 2026,
            "financial_year": "2026-27",
            "period_start": "2026-12-01",
            "period_end": "2026-12-31",
            "payroll_date": "2026-12-28",
        },
        headers=headers,
    )
    assert period.status_code == 201
    attendance_input = client.post(
        "/api/v1/payroll/inputs/attendance",
        json={
            "period_id": period.json()["id"],
            "employee_id": employee.id,
            "working_days": "26",
            "payable_days": "25",
            "present_days": "24",
            "paid_leave_days": "1",
            "lop_days": "1",
            "source_status": "Approved",
        },
        headers=headers,
    )
    assert attendance_input.status_code == 201
    assert attendance_input.json()["locked_at"] is not None

    calculation = client.post(
        "/api/v1/payroll/statutory/calculate",
        json={
            "employee_id": employee.id,
            "month": 12,
            "year": 2026,
            "gross_salary": "20000",
            "pf_wage": "25000",
            "esi_wage": "20000",
            "gratuity_wage": "26000",
            "service_years": "5",
        },
        headers=headers,
    )
    assert calculation.status_code == 201
    body = calculation.json()
    by_component = {line["component"]: line for line in body["lines"]}
    assert by_component["PF"]["wage_base"] == "15000.00"
    assert by_component["PF"]["employee_amount"] == "1800.00"
    assert by_component["ESI"]["employee_amount"] == "150.00"
    assert by_component["PT"]["employee_amount"] == "200.00"
    assert by_component["LWF"]["employer_amount"] == "20.00"
    assert by_component["GRATUITY"]["employer_amount"] == "1250.00"

    challan = client.post(
        "/api/v1/payroll/statutory/challans/generate",
        json={"challan_type": "PF", "due_date": "2027-01-15"},
        headers=headers,
    )
    assert challan.status_code == 201
    assert challan.json()["amount"] == "3750.00"
    challan_id = challan.json()["id"]

    invalid_return = client.post(
        "/api/v1/payroll/statutory/return-files",
        json={"challan_id": challan_id, "return_type": "PF_ECR", "format_version": "v1"},
        headers=headers,
    )
    assert invalid_return.status_code == 201
    assert invalid_return.json()["validation_status"] == "Failed"

    valid_return = client.post(
        "/api/v1/payroll/statutory/return-files",
        json={"challan_id": challan_id, "return_type": "PF_ECR", "format_version": "v1", "file_url": uploaded_reference('statutory/pf-ecr.csv')},
        headers=headers,
    )
    assert valid_return.status_code == 201
    assert valid_return.json()["validation_status"] == "Validated"
