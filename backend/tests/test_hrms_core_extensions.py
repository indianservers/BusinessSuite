from datetime import date, timedelta
from decimal import Decimal

from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun


def _employee(db, code="CORE001"):
    employee = Employee(
        employee_id=code,
        first_name="Core",
        last_name="Employee",
        date_of_joining=date(2024, 4, 1),
        status="Active",
    )
    db.add(employee)
    db.commit()
    return employee


def test_expense_claim_review_and_reimbursement(client, superuser_headers, db):
    employee = _employee(db, "EXP001")

    created = client.post(
        "/api/v1/expenses/claims",
        headers=superuser_headers,
        json={
            "employee_id": employee.id,
            "claim_type": "travel",
            "expense_date": date.today().isoformat(),
            "amount": "1250.00",
            "description": "Client visit cab fare",
        },
    )
    assert created.status_code == 201, created.text
    claim_id = created.json()["id"]

    manager_review = client.put(
        f"/api/v1/expenses/claims/{claim_id}/manager-review",
        headers=superuser_headers,
        json={"status": "manager_approved", "approved_amount": "1200.00"},
    )
    assert manager_review.status_code == 200, manager_review.text
    assert manager_review.json()["status"] == "manager_approved"

    finance_review = client.put(
        f"/api/v1/expenses/claims/{claim_id}/finance-review",
        headers=superuser_headers,
        json={"status": "finance_approved", "approved_amount": "1200.00"},
    )
    assert finance_review.status_code == 200, finance_review.text
    assert finance_review.json()["status"] == "finance_approved"

    reimbursed = client.put(
        f"/api/v1/expenses/claims/{claim_id}/reimburse",
        headers=superuser_headers,
        json={"reimbursement_reference": "UTR123"},
    )
    assert reimbursed.status_code == 200, reimbursed.text
    assert reimbursed.json()["status"] == "reimbursed"
    assert reimbursed.json()["reimbursement_reference"] == "UTR123"


def test_statutory_calculation_and_benefit_windows(client, superuser_headers, db):
    employee = _employee(db, "BEN001")

    statutory = client.post(
        "/api/v1/statutory-compliance/calculate",
        headers=superuser_headers,
        json={"basic_salary": "20000", "gross_salary": "20000", "state": "Karnataka"},
    )
    assert statutory.status_code == 200, statutory.text
    result = statutory.json()
    assert result["pf"]["employee_contribution"] == 1800
    assert result["esi"]["eligible"] is True
    assert result["professional_tax"]["monthly_amount"] == 0

    plan = client.post(
        "/api/v1/benefits/plans",
        headers=superuser_headers,
        json={"name": "Family Health", "plan_type": "health", "provider_name": "Demo Insurer"},
    )
    assert plan.status_code == 201, plan.text

    window = client.post(
        "/api/v1/benefits/enrollment-windows",
        headers=superuser_headers,
        json={
            "name": "FY Benefits",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "plan_type": "health",
        },
    )
    assert window.status_code == 201, window.text

    dependent = client.post(
        "/api/v1/benefits/dependants",
        headers=superuser_headers,
        json={"employee_id": employee.id, "full_name": "Core Dependant", "relationship": "Spouse"},
    )
    assert dependent.status_code == 201, dependent.text
    assert dependent.json()["relationship"] == "Spouse"


def test_document_generation_form12bb_and_standard_reports(client, superuser_headers, db):
    employee = _employee(db, "DOCGEN001")
    template = client.post(
        "/api/v1/documents/templates",
        headers=superuser_headers,
        json={
            "name": "Appointment Letter",
            "template_type": "appointment_letter",
            "content": "Dear {{ employee_name }}, welcome on {{ date_of_joining }}.",
        },
    )
    assert template.status_code == 201, template.text

    generated = client.post(
        f"/api/v1/documents/templates/{template.json()['id']}/generate",
        headers=superuser_headers,
        json={"employee_id": employee.id},
    )
    assert generated.status_code == 201, generated.text
    assert generated.json()["document_type"] == "appointment_letter"

    categories = client.get("/api/v1/hrms/tax-declaration/categories?financialYear=2026-27", headers=superuser_headers)
    section_80c = next(item for item in categories.json() if item["code"] == "80C")
    declaration = client.post(
        "/api/v1/hrms/tax-declarations",
        headers=superuser_headers,
        json={
            "employeeId": employee.id,
            "financialYear": "2026-27",
            "items": [{"categoryId": section_80c["id"], "declaredAmount": 100000}],
        },
    )
    assert declaration.status_code == 200, declaration.text
    form12bb = client.get(f"/api/v1/hrms/tax-declarations/{declaration.json()['id']}/form12bb", headers=superuser_headers)
    assert form12bb.status_code == 200, form12bb.text
    assert form12bb.json()["form"] == "12BB"

    run = PayrollRun(month=5, year=2026, status="Approved")
    db.add(run)
    db.flush()
    db.add(
        PayrollRecord(
            payroll_run_id=run.id,
            employee_id=employee.id,
            gross_salary=Decimal("50000"),
            total_deductions=Decimal("5000"),
            net_salary=Decimal("45000"),
            status="Approved",
        )
    )
    db.commit()

    salary_register = client.get("/api/v1/reports/salary-register?month=5&year=2026", headers=superuser_headers)
    assert salary_register.status_code == 200, salary_register.text
    assert salary_register.json()[0]["net_salary"] == 45000

    joiners = client.get(
        "/api/v1/reports/new-joiners-exits?from_date=2024-04-01&to_date=2024-04-30",
        headers=superuser_headers,
    )
    assert joiners.status_code == 200, joiners.text
    assert any(item["employee_code"] == "DOCGEN001" for item in joiners.json()["joiners"])
