from datetime import date, datetime, timezone
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun, SalaryComponent, SalaryStructure, SalaryStructureComponent
from app.models.timesheet import Project, Timesheet


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_payroll_pdf_exports_and_formula_preview(client, db):
    init_db(db)
    headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    run = PayrollRun(month=5, year=2026, status="Completed", total_gross=Decimal("50000"), total_deductions=Decimal("5000"), total_net=Decimal("45000"))
    db.add(run)
    db.flush()
    record = PayrollRecord(payroll_run_id=run.id, employee_id=employee.id, gross_salary=Decimal("50000"), total_deductions=Decimal("5000"), net_salary=Decimal("45000"), basic=Decimal("20000"), hra=Decimal("10000"))
    db.add(record)
    formula_component = SalaryComponent(name="Special Allowance", code="SPL_FORMULA", component_type="Earning", calculation_type="Formula", formula_expression="ctc_monthly * Decimal('0.10')")
    structure = SalaryStructure(name="Formula Structure", version="1.0")
    db.add_all([formula_component, structure])
    db.flush()
    db.add(SalaryStructureComponent(structure_id=structure.id, component_id=formula_component.id, order_sequence=1))
    db.commit()

    pdf = client.post(f"/api/v1/payroll/payslip/{record.id}/pdf", headers=headers)
    assert pdf.status_code == 200
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(pdf.json()["payslip_pdf_url"]).endswith(".pdf")

    export = client.post(f"/api/v1/payroll/runs/{run.id}/exports/pay_register", headers=headers)
    assert export.status_code == 201
    assert normalize_upload_references(export.json()["output_file_url"]).endswith("pay_register.csv")

    preview = client.post(f"/api/v1/payroll/structures/{structure.id}/preview", json={"ctc": "1200000"}, headers=headers)
    assert preview.status_code == 200
    assert Decimal(str(preview.json()["lines"][0]["monthly_amount"])) == Decimal("10000.00")


def test_attendance_workflow_recruitment_lms_engagement_and_utilization(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    punch = client.post(
        "/api/v1/attendance/punches",
        json={"punch_time": datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc).isoformat(), "punch_type": "IN", "source": "Mobile"},
        headers=employee_headers,
    )
    assert punch.status_code == 201
    lock = client.post("/api/v1/attendance/locks", json={"month": 5, "year": 2026, "reason": "Payroll cutoff"}, headers=admin)
    assert lock.status_code == 201

    definition = client.post(
        "/api/v1/workflow-engine/definitions",
        json={"name": "Payroll Approval", "module": "payroll", "trigger_event": "submitted", "steps": [{"step_order": 1, "approver_type": "Role", "approver_value": "super_admin"}]},
        headers=admin,
    )
    assert definition.status_code == 201
    instance = client.post(
        "/api/v1/workflow-engine/instances",
        json={"workflow_id": definition.json()["id"], "module": "payroll", "entity_type": "payroll_run", "entity_id": 1},
        headers=admin,
    )
    assert instance.status_code == 201
    tasks = client.get("/api/v1/workflow-engine/tasks", headers=admin)
    assert tasks.status_code == 200
    assert len(tasks.json()) >= 1

    req = client.post("/api/v1/recruitment/requisitions", json={"title": "HR Executive", "openings": 1}, headers=admin)
    assert req.status_code == 201
    approved = client.put(f"/api/v1/recruitment/requisitions/{req.json()['id']}/review", json={"action": "approve"}, headers=admin)
    assert approved.status_code == 200
    job_id = approved.json()["job_id"]
    cand = client.post("/api/v1/recruitment/candidates", json={"job_id": job_id, "first_name": "New", "last_name": "Hire", "email": "new.hire@example.com"}, headers=admin)
    assert cand.status_code == 201
    converted = client.post(f"/api/v1/recruitment/candidates/{cand.json()['id']}/convert", json={"employee_id": "NEW-HIRE-001", "date_of_joining": "2026-06-01"}, headers=admin)
    assert converted.status_code == 201

    course = client.post("/api/v1/lms/courses", json={"code": "HR101", "title": "HR Basics"}, headers=admin)
    assert course.status_code == 201
    assignment = client.post("/api/v1/lms/assignments", json={"course_id": course.json()["id"], "employee_id": employee.id}, headers=admin)
    assert assignment.status_code == 201
    recognition = client.post("/api/v1/engagement/recognitions", json={"to_employee_id": employee.id, "title": "Great work"}, headers=employee_headers)
    assert recognition.status_code == 201

    project = Project(code="UTIL", name="Utilization", client_name="Client")
    db.add(project)
    db.flush()
    db.add(Timesheet(employee_id=employee.id, project_id=project.id, period_start=date(2026, 5, 1), period_end=date(2026, 5, 7), status="Approved", total_hours=Decimal("40"), billable_hours=Decimal("32"), non_billable_hours=Decimal("8")))
    db.commit()
    report = client.get("/api/v1/reports/project-utilization?from_date=2026-05-01&to_date=2026-05-31", headers=admin)
    assert report.status_code == 200
    assert any(item["project_code"] == "UTIL" and item["billable_utilization_percent"] == 80 for item in report.json())
    csv_report = client.get("/api/v1/reports/project-utilization?from_date=2026-05-01&to_date=2026-05-31&export=csv", headers=admin)
    assert csv_report.status_code == 200
    assert "project_code" in csv_report.text
    assert "UTIL" in csv_report.text
