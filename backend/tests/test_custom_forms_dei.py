from tests.rich_text_test_utils import organization_context
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun


def _login(client, email="admin@aihrms.com", password="Admin@123456"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dynamic_custom_forms_submit_values_and_review(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    field = client.post(
        "/api/v1/custom-fields/definitions",
        json={
            "module": "employees",
            "section": "DEI",
            "field_key": "preferred_pronouns",
            "label": "Preferred pronouns",
            "field_type": "Select",
            "options_json": ["She/Her", "He/Him", "They/Them"],
            "is_required": True,
        },
        headers=headers,
    )
    assert field.status_code == 201

    form = client.post(
        "/api/v1/custom-fields/forms",
        json={
            "name": "Employee DEI Self Identification",
            "code": "EMP_DEI_SELF_ID",
            "module": "employees",
            "entity_type": "employee",
            "workflow_required": True,
            "fields": [{"field_definition_id": field.json()["id"], "display_order": 1}],
        },
        headers=headers,
    )
    assert form.status_code == 201
    assert form.json()["fields"][0]["field_definition_id"] == field.json()["id"]

    submission = client.post(
        f"/api/v1/custom-fields/forms/{form.json()['id']}/submissions",
        json={
            "form_id": form.json()["id"],
            "entity_type": "employee",
            "entity_id": employee.id,
            "values_json": {"preferred_pronouns": "They/Them"},
        },
        headers=headers,
    )
    assert submission.status_code == 201
    assert submission.json()["values_json"]["preferred_pronouns"] == "They/Them"

    values = client.get(
        "/api/v1/custom-fields/values",
        params={"entity_type": "employee", "entity_id": employee.id},
        headers=headers,
    )
    assert values.status_code == 200
    assert values.json()[0]["value_text"] == "They/Them"

    reviewed = client.put(
        f"/api/v1/custom-fields/forms/submissions/{submission.json()['id']}/review",
        json={"status": "Approved", "review_remarks": "Captured"},
        headers=headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"


def test_dei_analytics_representation_and_pay_equity(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.gender_identity = "Non-binary"
    employee.disability_status = "No disability disclosed"
    employee.veteran_status = "Not a veteran"
    run = PayrollRun(month=5, year=2026, status="Approved")
    db.add(run)
    db.flush()
    db.add(PayrollRecord(
        payroll_run_id=run.id,
        employee_id=employee.id,
        gross_salary=Decimal("100000"),
        total_deductions=Decimal("10000"),
        net_salary=Decimal("90000"),
    ))
    db.commit()

    response = client.get("/api/v1/reports/dei-analytics", params={"include_pay_equity": True}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_active_headcount"] >= 1
    assert any(item["gender_identity"] == "Non-binary" for item in data["gender_identity"])
    assert data["pay_equity"]["average_gross_by_gender_identity"][0]["average_gross_salary"] >= 0
