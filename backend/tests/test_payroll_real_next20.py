from tests.payroll_test_utils import init_payroll_test_db as init_db
from app.models.employee import Employee


def _login(client, email="admin@aihrms.com", password="Admin@123456"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_payroll_setup_salary_templates_and_tax_projection_work(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    legal_entity = client.post(
        "/api/v1/statutory-compliance/legal-entities",
        json={"legal_name": "AI HRMS Payroll Pvt Ltd", "pan": "ABCDE1234F", "tan": "HYDA12345B", "is_default": True},
        headers=headers,
    )
    assert legal_entity.status_code == 201
    legal_entity_id = legal_entity.json()["id"]

    statutory = client.post(
        "/api/v1/payroll/setup/statutory-profiles",
        json={
            "legal_entity_id": legal_entity_id,
            "pf_establishment_code": "APHYD1234567",
            "esi_employer_code": "52001234560001099",
            "pt_registration_number": "PT-HYD-1",
            "effective_from": "2026-04-01",
        },
        headers=headers,
    )
    assert statutory.status_code == 201

    pay_group = client.post(
        "/api/v1/payroll/setup/pay-groups",
        json={
            "name": "India Monthly Payroll",
            "code": "IN-MONTHLY",
            "legal_entity_id": legal_entity_id,
            "state": "Telangana",
            "pay_cycle_day": 28,
            "attendance_cutoff_day": 25,
            "reimbursement_cutoff_day": 24,
            "default_tax_regime": "NEW",
            "is_default": True,
        },
        headers=headers,
    )
    assert pay_group.status_code == 201
    pay_group_id = pay_group.json()["id"]

    generated = client.post(
        "/api/v1/payroll/setup/periods/generate",
        json={"pay_group_id": pay_group_id, "year": 2026, "financial_year": "2026-27"},
        headers=headers,
    )
    assert generated.status_code == 201
    assert len(generated.json()) == 12
    period_id = generated.json()[0]["id"]
    locked = client.put(f"/api/v1/payroll/setup/periods/{period_id}/lock", headers=headers)
    assert locked.status_code == 200
    assert locked.json()["status"] == "Locked"
    unlocked = client.put(f"/api/v1/payroll/setup/periods/{period_id}/unlock", headers=headers)
    assert unlocked.status_code == 200
    assert unlocked.json()["status"] == "Open"

    category = client.post(
        "/api/v1/payroll/component-categories",
        json={"name": "Core Earnings", "code": "CORE_EARN", "category_type": "Earning"},
        headers=headers,
    )
    assert category.status_code == 201

    component = client.post(
        "/api/v1/payroll/components",
        json={
            "name": "Basic Salary",
            "code": "BASIC_REAL",
            "component_type": "Earning",
            "calculation_type": "Formula",
            "formula_expression": "ctc_monthly * Decimal('0.40')",
            "category_id": category.json()["id"],
            "pf_wage_flag": True,
            "gratuity_wage_flag": True,
        },
        headers=headers,
    )
    assert component.status_code == 201
    component_id = component.json()["id"]

    rule = client.post(
        "/api/v1/payroll/component-formula-rules",
        json={"component_id": component_id, "formula_expression": "ctc_monthly * Decimal('0.50')", "validation_status": "Active"},
        headers=headers,
    )
    assert rule.status_code == 201

    blocked_rule = client.post(
        "/api/v1/payroll/component-formula-rules",
        json={"component_id": component_id, "formula_expression": "__import__('os').system('dir')", "validation_status": "Active"},
        headers=headers,
    )
    assert blocked_rule.status_code == 400

    structure = client.post(
        "/api/v1/payroll/structures",
        json={"name": "Real Structure", "version": "1.0", "components": [{"component_id": component_id, "order_sequence": 1}]},
        headers=headers,
    )
    assert structure.status_code == 201
    preview = client.post(f"/api/v1/payroll/structures/{structure.json()['id']}/preview", json={"ctc": "1200000"}, headers=headers)
    assert preview.status_code == 200
    assert preview.json()["lines"][0]["monthly_amount"] == "50000.00"

    template = client.post(
        "/api/v1/payroll/salary-templates",
        json={
            "name": "Engineer CTC Template",
            "code": "ENG-CTC",
            "pay_group_id": pay_group_id,
            "grade": "G5",
            "components": [{"component_id": component_id, "formula_expression": "ctc_monthly * Decimal('0.50')"}],
        },
        headers=headers,
    )
    assert template.status_code == 201

    assignment = client.post(
        "/api/v1/payroll/salary-template-assignments",
        json={"employee_id": employee.id, "template_id": template.json()["id"], "ctc": "1200000", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert assignment.status_code == 201

    override = client.post(
        "/api/v1/payroll/salary-component-overrides",
        json={"assignment_id": assignment.json()["id"], "component_id": component_id, "override_type": "Amount", "amount": "52000", "reason": "Offer approval"},
        headers=headers,
    )
    assert override.status_code == 201

    regime = client.post(
        "/api/v1/payroll/tax/regimes",
        json={"financial_year": "2026-27", "regime_code": "NEW", "name": "New Tax Regime", "is_default": True, "standard_deduction_amount": "75000"},
        headers=headers,
    )
    assert regime.status_code == 201
    regime_id = regime.json()["id"]
    assert client.post("/api/v1/payroll/tax/slabs", json={"tax_regime_id": regime_id, "min_income": "0", "max_income": "300000", "rate_percent": "0", "sequence": 1}, headers=headers).status_code == 201
    assert client.post("/api/v1/payroll/tax/slabs", json={"tax_regime_id": regime_id, "min_income": "300000", "max_income": "700000", "rate_percent": "5", "sequence": 2}, headers=headers).status_code == 201
    assert client.post("/api/v1/payroll/tax/slabs", json={"tax_regime_id": regime_id, "min_income": "700000", "rate_percent": "10", "sequence": 3}, headers=headers).status_code == 201

    section = client.post("/api/v1/payroll/tax/sections", json={"section_code": "80C", "name": "Section 80C"}, headers=headers)
    assert section.status_code == 201
    limit = client.post(
        "/api/v1/payroll/tax/section-limits",
        json={"tax_section_id": section.json()["id"], "tax_regime_id": regime_id, "financial_year": "2026-27", "limit_amount": "150000"},
        headers=headers,
    )
    assert limit.status_code == 201
    election = client.post(
        "/api/v1/payroll/tax/elections",
        json={"employee_id": employee.id, "financial_year": "2026-27", "tax_regime_id": regime_id, "lock": True},
        headers=headers,
    )
    assert election.status_code == 201

    previous = client.post(
        "/api/v1/payroll/tax/previous-employment",
        json={"employee_id": employee.id, "financial_year": "2026-27", "employer_name": "Old Company", "taxable_income": "200000", "tds_deducted": "5000"},
        headers=headers,
    )
    assert previous.status_code == 201

    worksheet = client.post(
        "/api/v1/payroll/tax/worksheets/project",
        json={
            "employee_id": employee.id,
            "financial_year": "2026-27",
            "tax_regime_id": regime_id,
            "gross_taxable_income": "1200000",
            "deductions": "50000",
            "remaining_months": 10,
        },
        headers=headers,
    )
    assert worksheet.status_code == 201
    body = worksheet.json()
    assert body["previous_employment_income"] == "200000.00"
    assert float(body["monthly_tds"]) > 0
    assert len(body["lines"]) == 2
