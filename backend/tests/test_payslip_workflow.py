from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.core.config import settings
from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollRun, PayslipPublishBatch
from tests.payroll_test_utils import init_payroll_test_db, commit_payroll_fixture


@pytest.fixture
def slips(client, db, monkeypatch, tmp_path):
    init_payroll_test_db(db)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", False)
    employee = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").one()
    employee.date_of_birth = date(1990, 1, 2)
    employee.aadhaar_number = None
    run = PayrollRun(month=5, year=2026, status="locked", company_id=employee.branch.company_id)
    db.add(run)
    db.flush()
    record = PayrollRecord(payroll_run_id=run.id, employee_id=employee.id,
                           basic=50000, gross_salary=50000, total_deductions=5000,
                           net_salary=45000, tds=5000, converted_currency="INR")
    db.add(record)
    commit_payroll_fixture(db)

    def login(email, password):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return run, record, login("admin@aihrms.com", "Admin@123456"), login("employee@aihrms.com", "Employee@123456")


def test_publish_prepares_protected_pdf_and_employee_can_download(client, db, slips):
    run, record, admin, employee = slips
    response = client.post(f"/api/v1/payroll/runs/{run.id}/payslip-publish", json={"send_email": False}, headers=admin)
    assert response.status_code == 201, response.text
    assert response.json()["published_count"] == 1
    assert response.json()["email_dispatch_status"] == "Not requested"
    assert response.json()["output_file_url"] is None
    db.refresh(record)
    assert record.payslip_generated_at
    assert record.payslip_pdf_url
    pdf = client.get(f"/api/v1/payroll/payslip/{record.id}/pdf", headers=employee)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["cache-control"] == "private, no-store"
    reader = PdfReader(BytesIO(pdf.content))
    assert reader.is_encrypted
    assert reader.decrypt("02011990")
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "INR 45,000.00" in text
    assert "Total deductions" in text
    assert not list(Path(settings.UPLOAD_DIR).rglob(f"*_run_{run.id}.pdf"))


def test_missing_pdf_is_recovered_only_for_its_owner(client, db, slips):
    run, record, admin, employee = slips
    other = db.query(Employee).filter(Employee.id != record.employee_id).first()
    other_record = PayrollRecord(payroll_run_id=run.id, employee_id=other.id, net_salary=100)
    db.add(other_record)
    commit_payroll_fixture(db)
    denied = client.get(f"/api/v1/payroll/payslip/{other_record.id}/pdf", headers=employee)
    assert denied.status_code == 403
    assert other_record.payslip_pdf_url is None
    for _ in range(2):
        response = client.get(f"/api/v1/payroll/payslip/{record.id}/pdf", headers=employee)
        assert response.status_code == 200, response.text
        db.refresh(record)
        path = Path(settings.UPLOAD_DIR) / record.payslip_pdf_url.removeprefix("/uploads/")
        path.unlink()


@pytest.mark.parametrize("status", ["draft", "calculated", "approved"])
def test_unfinished_payroll_is_hidden_and_cannot_be_published(client, db, slips, status):
    run, record, admin, employee = slips
    run.status = status
    db.commit()
    assert client.get("/api/v1/payroll/payslip?month=5&year=2026", headers=employee).status_code == 404
    assert client.get(f"/api/v1/payroll/payslip/{record.id}/pdf", headers=employee).status_code == 404
    assert client.get("/api/v1/payroll/my-payslips", headers=employee).json() == []
    assert client.post(f"/api/v1/payroll/runs/{run.id}/payslip-publish", json={}, headers=admin).status_code == 409
    assert db.query(PayslipPublishBatch).count() == 0


def test_history_is_personal_and_payload_omits_sensitive_employee_fields(client, db, slips):
    run, record, admin, employee = slips
    response = client.get("/api/v1/payroll/my-payslips", headers=employee)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [record.id]
    data = client.get("/api/v1/payroll/payslip?month=5&year=2026", headers=employee).json()
    assert set(data["employee"]) == {"id", "employee_id", "first_name", "last_name"}
    assert data["payroll_status"] == "locked"
    assert client.get("/api/v1/payroll/payslip?month=13&year=2026", headers=employee).status_code == 422


def test_generation_failure_does_not_publish_a_batch(client, db, slips, monkeypatch):
    from app.api.v1 import payroll
    from fastapi import HTTPException
    run, record, admin, employee = slips

    def fail(*args):
        raise HTTPException(503, "PDF storage unavailable")

    monkeypatch.setattr(payroll, "_generate_payslip_pdf", fail)
    response = client.post(f"/api/v1/payroll/runs/{run.id}/payslip-publish", json={}, headers=admin)
    assert response.status_code == 503
    assert db.query(PayslipPublishBatch).count() == 0


def test_encryption_failure_does_not_leave_an_unprotected_document(client, db, slips, monkeypatch):
    from pypdf import PdfWriter
    run, record, admin, employee = slips

    def fail(*args, **kwargs):
        raise RuntimeError("Encryption unavailable")

    monkeypatch.setattr(PdfWriter, "encrypt", fail)
    response = client.post(f"/api/v1/payroll/runs/{run.id}/payslip-publish", json={}, headers=admin)
    assert response.status_code == 503
    assert db.query(PayslipPublishBatch).count() == 0
    assert not list(Path(settings.UPLOAD_DIR).rglob("*.pdf"))


def test_draft_run_does_not_shadow_finalized_payslip_or_inflate_ytd(client, db, slips):
    run, record, admin, employee = slips
    draft = PayrollRun(month=5, year=2026, status="calculated", company_id=run.company_id)
    db.add(draft)
    db.flush()
    db.add(PayrollRecord(payroll_run_id=draft.id, employee_id=record.employee_id,
                         gross_salary=90000, net_salary=90000, total_deductions=0))
    commit_payroll_fixture(db)
    response = client.get("/api/v1/payroll/payslip?month=5&year=2026", headers=employee)
    assert response.status_code == 200
    assert response.json()["id"] == record.id
    assert response.json()["ytd"]["net_salary"] == 45000


def test_employee_can_submit_a_query_for_their_own_payslip(client, slips):
    run, record, admin, employee = slips
    response = client.post("/api/v1/payroll/payslip-queries", json={
        "payroll_record_id": record.id, "subject": "Tax deduction", "description": "Please explain this amount.", "priority": "Medium",
    }, headers=employee)
    assert response.status_code == 201, response.text


def test_email_preference_is_honored_and_republishing_deduplicates_notifications(client, db, slips, monkeypatch):
    from app.models.email_outbox import EmailOutbox
    run, record, admin, employee = slips
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True)
    endpoint = f"/api/v1/payroll/runs/{run.id}/payslip-publish"
    assert client.post(endpoint, json={"send_email": False}, headers=admin).status_code == 201
    event_key = f"payslip-published:{run.id}:{record.employee_id}"
    assert db.query(EmailOutbox).filter_by(event_key=event_key).count() == 0
    for _ in range(2):
        response = client.post(endpoint, json={"send_email": True}, headers=admin)
        assert response.status_code == 201, response.text
    queued = db.query(EmailOutbox).filter_by(event_key=event_key).all()
    assert len(queued) == 1
    assert "/hrms/my-payslips" in queued[0].body


def test_ess_channels_hide_unfinished_salary(client, db, slips):
    from app.api.v1.whatsapp_ess import _response_for
    run, record, admin, employee = slips
    run.status = "calculated"
    db.commit()
    summary = client.get("/api/v1/reports/ess-summary", headers=employee)
    assert summary.status_code == 200, summary.text
    assert summary.json()["payslips"] == []
    assert "No payslip" in _response_for(db, record.employee, "payslip")


def test_pdf_layout_paginates_long_component_lists(tmp_path):
    from app.services.payslip_pdf import render_payslip
    path = tmp_path / "long-payslip.pdf"
    render_payslip(str(path), {"month": 5, "year": 2026, "currency": "USD",
                             "earnings": [{"component_name": f"Allowance {i} with a long description " * 2, "amount": 1.25} for i in range(80)],
                             "gross_salary": 100, "net_salary": 100})
    reader = PdfReader(path)
    assert len(reader.pages) > 1
    assert "USD 100.00" in reader.pages[-1].extract_text()
