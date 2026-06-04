from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun


def _login(client, email="admin@aihrms.com", password="Admin@123456"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_governed_metric_filters_and_drilldowns(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.gender_identity = "Non-binary"
    employee.employment_type = "Full-time"
    employee.date_of_joining = date(2026, 1, 1)
    run = PayrollRun(month=5, year=2026, status="Approved")
    db.add(run)
    db.flush()
    db.add(PayrollRecord(
        payroll_run_id=run.id,
        employee_id=employee.id,
        gross_salary=Decimal("125000"),
        total_deductions=Decimal("10000"),
        net_salary=Decimal("115000"),
    ))
    db.add(Attendance(employee_id=employee.id, attendance_date=date(2026, 5, 5), status="Absent"))
    db.add(Attendance(employee_id=employee.id, attendance_date=date(2026, 5, 6), status="Present"))
    db.commit()

    definitions = client.get("/api/v1/reports/analytics/metric-definitions", headers=headers)
    assert definitions.status_code == 200
    assert {item["code"] for item in definitions.json()} >= {"pay_equity", "span_of_control", "manager_effectiveness", "attrition_trend", "absenteeism", "dei_representation"}

    pay_equity = client.get(
        "/api/v1/reports/analytics/drilldown",
        params={"metric": "pay_equity", "department_id": employee.department_id, "employment_type": "Full-time", "tenure_band": "0-1"},
        headers=headers,
    )
    assert pay_equity.status_code == 200
    assert pay_equity.json()["summary"]["groups"] >= 1
    assert pay_equity.json()["rows"][0]["average_gross_salary"] >= 0

    absenteeism = client.get(
        "/api/v1/reports/analytics/drilldown",
        params={"metric": "absenteeism", "department_id": employee.department_id, "from_date": "2026-05-01", "to_date": "2026-05-31"},
        headers=headers,
    )
    assert absenteeism.status_code == 200
    assert absenteeism.json()["summary"]["attendance_records"] == 2
    assert absenteeism.json()["summary"]["absenteeism_rate"] == 50


def test_report_schedule_creation_and_manual_run(client, db):
    init_db(db)
    headers = _login(client)

    definition = client.post("/api/v1/reports/definitions", json={
        "name": "Active employee export",
        "code": "ACTIVE_EMP_EXPORT",
        "module": "employees",
        "selected_fields_json": ["employee_code", "first_name", "status"],
        "export_format": "csv",
    }, headers=headers)
    assert definition.status_code == 201

    schedule = client.post("/api/v1/reports/schedules", json={
        "report_definition_id": definition.json()["id"],
        "name": "Monthly active employee export",
        "cron_expression": "0 9 1 * *",
        "recipients_json": ["hr@example.com"],
    }, headers=headers)
    assert schedule.status_code == 201
    assert schedule.json()["status"] == "Active"

    run = client.post(f"/api/v1/reports/schedules/{schedule.json()['id']}/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["status"] == "Completed"
    assert run.json()["row_count"] >= 1

    preview = client.get(f"/api/v1/reports/definitions/{definition.json()['id']}/run", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["columns"] == ["employee_code", "first_name", "status"]
    assert preview.json()["row_count"] >= 1


def test_domain_pack_enablement_and_manufacturing_records(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    blocked = client.post("/api/v1/enterprise/domain-packs/manufacturing/safety-incidents", json={
        "employee_id": employee.id,
        "incident_date": "2026-05-12",
        "incident_type": "Near Miss",
    }, headers=headers)
    assert blocked.status_code == 400

    enabled = client.post("/api/v1/enterprise/domain-packs/enable", json={
        "pack_key": "manufacturing",
        "config_json": {"plant_codes": ["PLANT-1"]},
    }, headers=headers)
    assert enabled.status_code == 201
    assert enabled.json()["pack_key"] == "manufacturing"

    incident = client.post("/api/v1/enterprise/domain-packs/manufacturing/safety-incidents", json={
        "employee_id": employee.id,
        "incident_date": "2026-05-12",
        "incident_type": "Near Miss",
        "severity": "Medium",
        "location": "Line 2",
        "lost_time_hours": "0",
    }, headers=headers)
    assert incident.status_code == 201
    assert incident.json()["severity"] == "Medium"

    ppe = client.post("/api/v1/enterprise/domain-packs/manufacturing/ppe-issuances", json={
        "employee_id": employee.id,
        "ppe_item": "Safety Helmet",
        "issued_on": "2026-05-13",
        "quantity": 1,
    }, headers=headers)
    assert ppe.status_code == 201

    fitness = client.post("/api/v1/enterprise/domain-packs/manufacturing/medical-fitness", json={
        "employee_id": employee.id,
        "exam_date": "2026-05-14",
        "fitness_status": "Fit",
        "valid_until": "2027-05-14",
    }, headers=headers)
    assert fitness.status_code == 201

    batch = client.post("/api/v1/enterprise/domain-packs/manufacturing/contract-labor-batches", json={
        "vendor_name": "SafeWorks Contractors",
        "batch_code": "CL-2026-05",
        "start_date": "2026-05-01",
        "headcount": 42,
        "compliance_status": "Verified",
    }, headers=headers)
    assert batch.status_code == 201

    listed = client.get("/api/v1/enterprise/domain-packs/manufacturing/safety-incidents", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
