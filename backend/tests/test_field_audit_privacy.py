from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.employee import Employee
from app.models.platform import DataRetentionPolicy, LegalHold
from app.models.payroll import EmployeeSalary


def test_employee_sensitive_field_update_creates_masked_hash_audit(client, db, superuser_headers):
    employee = Employee(
        employee_id="AUD-001",
        first_name="Audit",
        last_name="Subject",
        date_of_joining=datetime(2024, 1, 1).date(),
        account_number="123456789012",
        pan_number="ABCDE1234F",
        department_id=1,
        status="Active",
    )
    db.add(employee)
    db.commit()

    response = client.put(
        f"/api/v1/employees/{employee.id}",
        json={"account_number": "999988887777", "pan_number": "ABCDE9999F", "department_id": 2, "status": "Probation"},
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text

    audit = client.get(f"/api/v1/logs/field-audit?employee_id={employee.id}", headers=superuser_headers)
    assert audit.status_code == 200
    rows = audit.json()
    account_row = next(row for row in rows if row["field_name"] == "account_number")
    assert account_row["old_value_masked"].endswith("9012")
    assert account_row["new_value_masked"].endswith("7777")
    assert account_row["old_value_hash"]
    assert account_row["new_value_hash"]
    assert "123456789012" not in str(rows)
    department_row = next(row for row in rows if row["field_name"] == "department_id")
    assert department_row["old_value_masked"] == "1"
    assert department_row["new_value_masked"] == "2"


def test_salary_assignment_creates_field_audit(client, db, superuser_headers):
    employee = Employee(employee_id="AUD-SAL-001", first_name="Salary", last_name="Audit", date_of_joining=datetime(2024, 1, 1).date())
    db.add(employee)
    db.commit()

    response = client.post(
        "/api/v1/payroll/salary",
        json={"employee_id": employee.id, "ctc": "900000", "basic": "35000", "hra": "15000", "effective_from": "2026-04-01", "is_active": True},
        headers=superuser_headers,
    )
    assert response.status_code == 201, response.text
    audit = client.get(f"/api/v1/logs/field-audit?employee_id={employee.id}&module=payroll", headers=superuser_headers)
    assert audit.status_code == 200
    fields = {row["field_name"]: row for row in audit.json()}
    assert "ctc" in fields
    assert fields["ctc"]["new_value_masked"] == "Restricted"
    assert fields["ctc"]["new_value_hash"]


def test_privacy_export_masks_identifiers_and_delete_is_blocked_by_legal_hold(client, db, superuser_headers):
    employee = Employee(
        employee_id="PRIV-001",
        first_name="Private",
        last_name="Person",
        date_of_joining=datetime(2024, 1, 1).date(),
        account_number="123456789012",
        pan_number="ABCDE1234F",
        aadhaar_number="123456789012",
    )
    db.add(employee)
    db.commit()

    export_req = client.post(
        "/api/v1/enterprise/privacy-requests",
        json={"employee_id": employee.id, "request_type": "export", "requested_by_email": "privacy@example.com"},
        headers=superuser_headers,
    )
    assert export_req.status_code == 201
    processed = client.post(f"/api/v1/enterprise/privacy-requests/{export_req.json()['id']}/process", headers=superuser_headers)
    assert processed.status_code == 200
    package = processed.json()["processing_result_json"]["package"]
    assert package["sensitive_identifiers"]["pan_number"]["masked"].endswith("1234F"[-4:])
    assert "ABCDE1234F" not in str(package)
    assert "123456789012" not in str(package)

    db.add(LegalHold(name="Litigation hold", module="employee", entity_type="employee", entity_id=employee.id, reason="Investigation"))
    db.commit()
    delete_req = client.post(
        "/api/v1/enterprise/privacy-requests",
        json={"employee_id": employee.id, "request_type": "anonymize", "requested_by_email": "privacy@example.com"},
        headers=superuser_headers,
    )
    blocked = client.post(f"/api/v1/enterprise/privacy-requests/{delete_req.json()['id']}/process", headers=superuser_headers)
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "Blocked"
    assert "active_legal_hold" in blocked.json()["processing_result_json"]["blockers"]


def test_retention_policy_marks_and_processes_eligible_employee(client, db, superuser_headers):
    employee = Employee(employee_id="RET-001", first_name="Retention", last_name="Subject", date_of_joining=datetime(2020, 1, 1).date(), pan_number="ABCDE1234F")
    employee.created_at = datetime.now(timezone.utc) - timedelta(days=1000)
    db.add(employee)
    db.add(DataRetentionPolicy(module="employee", record_type="employee", retention_days=30, action="Anonymize", legal_basis="Expired retention"))
    db.commit()

    dry_run = client.post("/api/v1/enterprise/retention-policies/run?dry_run=true", headers=superuser_headers)
    assert dry_run.status_code == 200
    assert dry_run.json()["eligible"] >= 1
    db.refresh(employee)
    assert employee.pan_number == "ABCDE1234F"

    run = client.post("/api/v1/enterprise/retention-policies/run?dry_run=false", headers=superuser_headers)
    assert run.status_code == 200
    db.refresh(employee)
    assert employee.pan_number is None
    assert employee.status == "Anonymized"
