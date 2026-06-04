from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import (
    EmployeeStatutoryProfile,
    PayrollRecord,
    PayrollRun,
    PayrollStatutoryContributionLine,
    TDS26ASReconciliation,
)


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _legal_entity(client, headers, **overrides):
    payload = {
        "legal_name": "Portal Ready HRMS Private Limited",
        "pan": "ABCDE1234F",
        "tan": "HYDA12345B",
        "pf_establishment_code": "APHYD1234567",
        "esi_employer_code": "52001234560001099",
        "pt_registration_number": "PT-TG-12345",
        "lwf_registration_number": "LWF-TG-12345",
        "is_default": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/statutory-compliance/legal-entities", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _run_with_employee(db, *, pan="ABCDE1234F", uan="100200300400", tds=Decimal("2500.00")):
    employee = Employee(
        employee_id=f"STAT-{pan or 'NOPAN'}-{uan or 'NOUAN'}",
        first_name="Stat",
        last_name="Employee",
        pan_number=pan,
        uan_number=uan,
        esic_number="ESIC12345",
        date_of_joining=date(2026, 4, 1),
    )
    db.add(employee)
    db.flush()
    db.add(
        EmployeeStatutoryProfile(
            employee_id=employee.id,
            uan=uan,
            pf_applicable=True,
            pension_applicable=True,
            esi_ip_number="ESIC12345",
            esi_applicable=True,
            lwf_applicable=True,
            pt_state="Telangana",
        )
    )
    run = PayrollRun(month=7, year=2026, status="locked", pay_period_start=date(2026, 7, 1), pay_period_end=date(2026, 7, 31))
    db.add(run)
    db.flush()
    record = PayrollRecord(
        payroll_run_id=run.id,
        employee_id=employee.id,
        working_days=31,
        present_days=Decimal("31"),
        paid_days=Decimal("31"),
        basic=Decimal("20000"),
        gross_salary=Decimal("50000"),
        pf_employee=Decimal("1800"),
        pf_employer=Decimal("1800"),
        professional_tax=Decimal("200"),
        tds=tds,
        total_deductions=Decimal("4500"),
        net_salary=Decimal("45500"),
    )
    db.add(record)
    db.flush()
    db.add(
        PayrollStatutoryContributionLine(
            payroll_record_id=record.id,
            employee_id=employee.id,
            component="PF",
            wage_base=Decimal("15000"),
            employee_amount=Decimal("1800"),
            employer_amount=Decimal("1800"),
            rule_type="PF",
        )
    )
    db.commit()
    return run, employee


def test_pf_ecr_portal_ready_export_has_structured_status_and_calendar(client, db):
    init_db(db)
    headers = _login(client)
    _legal_entity(client, headers)
    run, _employee = _run_with_employee(db)

    response = client.post(f"/api/v1/statutory/generate/{run.id}/pf_ecr", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["validation_status"] == "valid"
    assert body["filing_status"] == "ready_for_upload"
    assert body["portal_connector_status"] == "not_configured"
    assert body["digital_signature_status"] == "not_applicable"
    assert body["errors"] == []
    assert body["calendar_event"]["statutory_type"] == "PF_ECR"
    assert body["calendar_event"]["reminder_days_before"] == 7

    download = client.get(body["download_url"], headers=headers)
    assert download.status_code == 200
    assert b"100200300400" in download.content


def test_pf_ecr_reports_missing_uan_with_error_code(client, db):
    init_db(db)
    headers = _login(client)
    _legal_entity(client, headers)
    run, _employee = _run_with_employee(db, uan=None)

    response = client.post(f"/api/v1/statutory/generate/{run.id}/pf_ecr", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["validation_status"] == "invalid"
    assert body["filing_status"] == "generated_with_errors"
    assert any(error["code"] == "UAN_INVALID" for error in body["errors"])


def test_tds_24q_reports_missing_pan_and_invalid_employer_tan(client, db):
    init_db(db)
    headers = _login(client)
    _legal_entity(client, headers, tan="BADTAN")
    run, _employee = _run_with_employee(db, pan=None)

    response = client.post(f"/api/v1/statutory/generate/{run.id}/tds_24q?quarter=2&year=2026", headers=headers)
    assert response.status_code == 200
    codes = {error["code"] for error in response.json()["errors"]}
    assert "PAN_INVALID" in codes
    assert "EMPLOYER_TAN_INVALID" in codes


def test_tds_24q_reports_reconciliation_mismatch(client, db):
    init_db(db)
    headers = _login(client)
    _legal_entity(client, headers)
    run, employee = _run_with_employee(db, tds=Decimal("2500.00"))
    db.add(
        TDS26ASReconciliation(
            employee_id=employee.id,
            financial_year="2026-27",
            company_tds=Decimal("2500.00"),
            reported_26as_tds=Decimal("1000.00"),
            difference=Decimal("1500.00"),
            status="Mismatch",
        )
    )
    db.commit()

    response = client.post(f"/api/v1/statutory/generate/{run.id}/tds_24q?quarter=2&year=2026", headers=headers)
    assert response.status_code == 200
    assert any(error["code"] == "TDS_RECON_MISMATCH" for error in response.json()["errors"])
