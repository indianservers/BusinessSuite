from tests.security_file_fixtures import uploaded_reference
from datetime import datetime, timezone

from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_payroll_formula_tax_and_platform_foundations(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")

    basic = client.post("/api/v1/payroll/components", json={
        "name": "Basic", "code": "BASIC", "component_type": "Earning", "calculation_type": "Fixed", "amount": "0",
    }, headers=admin)
    assert basic.status_code == 201
    hra = client.post("/api/v1/payroll/components", json={
        "name": "HRA", "code": "HRA", "component_type": "Earning", "calculation_type": "Formula",
        "formula_expression": "BASIC * Decimal('0.40')", "amount": "0",
    }, headers=admin)
    assert hra.status_code == 201
    structure = client.post("/api/v1/payroll/structures", json={
        "name": "Dependency Structure",
        "components": [
            {"component_id": hra.json()["id"], "order_sequence": 1},
            {"component_id": basic.json()["id"], "amount": "50000", "order_sequence": 2},
        ],
    }, headers=admin)
    assert structure.status_code == 201
    preview = client.post(f"/api/v1/payroll/structures/{structure.json()['id']}/preview", json={"ctc": "1200000"}, headers=admin)
    assert preview.status_code == 200
    assert preview.json()["formula_order"] == ["BASIC", "HRA"]
    assert preview.json()["lines"][1]["monthly_amount"] == "20000.00"

    old = client.post("/api/v1/payroll/tax/regimes", json={
        "financial_year": "2026-27", "regime_code": "OLD", "name": "Old Regime",
        "standard_deduction_amount": "50000", "rebate_rules_json": [{"income_upto": 500000, "rebate_amount": 12500}],
        "surcharge_rules_json": [{"income_above": 5000000, "rate_percent": 10}],
    }, headers=admin)
    new = client.post("/api/v1/payroll/tax/regimes", json={
        "financial_year": "2026-27", "regime_code": "NEW", "name": "New Regime", "is_default": True,
        "standard_deduction_amount": "75000", "rebate_rules_json": [{"income_upto": 700000, "rebate_amount": 25000}],
    }, headers=admin)
    assert old.status_code == 201
    assert new.status_code == 201
    for regime in (old.json(), new.json()):
        for index, row in enumerate([
            ("0", "300000", "0"), ("300000", "600000", "5"), ("600000", "1200000", "10"), ("1200000", None, "20"),
        ], start=1):
            payload = {"tax_regime_id": regime["id"], "sequence": index, "min_income": row[0], "max_income": row[1], "rate_percent": row[2]}
            assert client.post("/api/v1/payroll/tax/slabs", json=payload, headers=admin).status_code == 201
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    compare = client.get(
        f"/api/v1/payroll/tax/compare?employee_id={employee.id}&financial_year=2026-27&gross_taxable_income=1000000&deductions=150000&exemptions=100000",
        headers=admin,
    )
    assert compare.status_code == 200
    assert compare.json()["recommended_regime"]["regime_code"] in {"OLD", "NEW"}

    field = client.post("/api/v1/custom-fields/definitions", json={
        "module": "employees", "field_key": "tshirt_size", "label": "T-Shirt Size", "field_type": "Select",
        "options_json": ["S", "M", "L"],
    }, headers=admin)
    assert field.status_code == 201
    value = client.put("/api/v1/custom-fields/values", json={
        "definition_id": field.json()["id"], "entity_type": "employee", "entity_id": employee.id, "value_text": "M",
    }, headers=admin)
    assert value.status_code == 200

    report = client.post("/api/v1/reports/definitions", json={
        "name": "Employee Master", "code": "EMP_MASTER", "module": "employees",
        "selected_fields_json": ["employee_id", "first_name", "status"],
    }, headers=admin)
    assert report.status_code == 201
    run = client.post(f"/api/v1/reports/definitions/{report.json()['id']}/run", headers=admin)
    assert run.status_code == 201
    assert run.json()["row_count"] >= 1


def test_whatsapp_biometric_and_geo_attendance_foundations(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.phone_number = "9888888888"
    employee.phone_number_country_code = "+91"
    db.commit()

    config = client.post("/api/v1/whatsapp-ess/configs", json={
        "business_phone_number": "9000000000", "business_phone_number_country_code": "+91", "webhook_url": "https://example.com/wa",
        "app_secret_ref": "secret://wa/app", "verify_token_ref": "secret://wa/verify",
    }, headers=admin)
    assert config.status_code == 201
    template = client.post("/api/v1/whatsapp-ess/templates", json={
        "config_id": config.json()["id"], "template_name": "payslip_ready", "intent": "payslip",
        "body_text": "Your payslip is ready.",
    }, headers=admin)
    assert template.status_code == 201
    opt_in = client.post("/api/v1/whatsapp-ess/opt-ins", json={
        "employee_id": employee.id, "phone_number": "9888888888", "phone_number_country_code": "+91", "consent_text": "Employee opted in",
    }, headers=admin)
    assert opt_in.status_code == 201
    outbound = client.post("/api/v1/whatsapp-ess/messages/outbound", json={
        "employee_id": employee.id, "phone_number": "9888888888", "phone_number_country_code": "+91", "template_id": template.json()["id"], "intent": "payslip",
    }, headers=admin)
    assert outbound.status_code == 201
    callback = client.post("/api/v1/whatsapp-ess/delivery-callbacks", json={
        "provider_message_id": outbound.json().get("provider_message_id", ""),
        "status": "Delivered",
    }, headers=admin)
    assert callback.status_code == 201

    device = client.post("/api/v1/attendance/biometric/devices", json={
        "name": "Main Door", "vendor": "eSSL", "device_code": "ESSL-01",
    }, headers=admin)
    assert device.status_code == 201
    imported = client.post("/api/v1/attendance/biometric/import", json={
        "device_id": device.json()["id"], "source_filename": "essl.csv",
        "rows": [{"employee_id": employee.id, "punch_time": datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc).isoformat(), "punch_type": "IN"}],
    }, headers=admin)
    assert imported.status_code == 201
    assert imported.json()["imported_rows"] == 1

    policy = client.post("/api/v1/attendance/geo/policies", json={
        "name": "Hyderabad Office", "latitude": "17.3850440", "longitude": "78.4866710", "radius_meters": 250,
        "require_selfie": True,
    }, headers=admin)
    assert policy.status_code == 201
    proof = client.post("/api/v1/attendance/geo/punch", json={
        "policy_id": policy.json()["id"], "punch_time": datetime(2026, 5, 2, 9, 5, tzinfo=timezone.utc).isoformat(),
        "punch_type": "IN", "latitude": "17.3850440", "longitude": "78.4866710", "selfie_url": uploaded_reference('selfie.jpg'),
    }, headers=employee_headers)
    assert proof.status_code == 201
    assert proof.json()["validation_status"] == "Verified"
