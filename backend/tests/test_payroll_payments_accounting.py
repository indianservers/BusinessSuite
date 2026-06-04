from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollPaymentBatch, PayrollJournalEntry
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ensure_salary(db, employee):
    if not db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active == True).first():
        db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal("600000"), basic=Decimal("20000"), hra=Decimal("10000"), effective_from=date(2026, 4, 1), is_active=True))
        db.commit()


def test_payment_batch_status_import_gl_and_statutory_validation(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    employee.account_number = "1234567890"
    employee.ifsc_code = "HDFC0001234"
    _ensure_salary(db, employee)
    db.commit()
    ensure_payroll_ready(db, 5, 2026)

    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert run.status_code == 201
    run_id = run.json()["id"]

    batch = client.post("/api/v1/payroll/payments/batches", json={"payroll_run_id": run_id, "debit_account": "HDFC Payroll"}, headers=headers)
    assert batch.status_code == 201
    batch_body = batch.json()
    assert batch_body["total_amount"] != "0.00"
    assert batch_body["generated_file_url"].endswith(".csv")
    employee_line = next(line for line in batch_body["lines"] if line["employee_id"] == employee.id)
    assert employee_line["bank_account"] == "1234567890"

    imported = client.put(
        f"/api/v1/payroll/payments/batches/{batch_body['id']}/status-import",
        json={"lines": [{"employee_id": employee.id, "payment_status": "Paid", "utr_number": "UTR123"}]},
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json()["updated"] == 1
    db.refresh(db.query(PayrollPaymentBatch).filter(PayrollPaymentBatch.id == batch_body["id"]).first())

    journal = client.post(f"/api/v1/payroll/runs/{run_id}/accounting-journal", headers=headers)
    assert journal.status_code == 201
    journal_body = journal.json()
    assert Decimal(str(journal_body["total_debit"])) == Decimal(str(journal_body["total_credit"]))
    assert journal_body["status"] == "Generated"
    assert db.query(PayrollJournalEntry).filter(PayrollJournalEntry.payroll_run_id == run_id).count() == 1

    validation = client.post(
        "/api/v1/payroll/statutory/file-validations",
        json={"payroll_run_id": run_id, "file_type": "pf_ecr"},
        headers=headers,
    )
    assert validation.status_code == 201
    assert validation.json()["total_rows"] >= 1
    assert validation.json()["output_file_url"].endswith(".csv")

    template = client.post("/api/v1/payroll/statutory/templates/form_16", headers=headers)
    assert template.status_code == 201
    assert template.json()["file_url"].endswith("form_16_template.csv")
