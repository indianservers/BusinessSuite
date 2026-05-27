from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import (
    EmployeeSalary,
    PayrollCalculationSnapshot,
    PayrollPreRunCheck,
    PayrollRecord,
)


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _prepare_usd_employee(db) -> Employee:
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.salary_currency = "USD"
    db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id).delete(synchronize_session=False)
    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("120000"),
        basic=Decimal("4000"),
        hra=Decimal("2000"),
        effective_from=date(2026, 5, 1),
        is_active=True,
    ))
    db.commit()
    return employee


def test_multi_currency_payroll_blocks_when_exchange_rate_missing(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = _prepare_usd_employee(db)

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=admin_headers)

    assert response.status_code == 400
    assert "Missing exchange rate" in response.json()["detail"]
    check = db.query(PayrollPreRunCheck).filter(
        PayrollPreRunCheck.affected_employee_id == employee.id,
        PayrollPreRunCheck.check_type == "currency_exchange_rate",
    ).first()
    assert check is not None
    assert check.status == "Failed"
    assert "USD->INR" in check.message


def test_multi_currency_payroll_converts_and_exposes_currency_metadata(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = _prepare_usd_employee(db)

    created_rate = client.post(
        "/api/v1/payroll/exchange-rates",
        json={
            "from_currency": "usd",
            "to_currency": "inr",
            "rate": "83.25",
            "effective_date": "2026-05-01",
            "source": "Test",
        },
        headers=admin_headers,
    )
    assert created_rate.status_code == 201

    listed_rates = client.get(
        "/api/v1/payroll/exchange-rates?from_currency=USD&to_currency=INR&date=2026-05-31",
        headers=admin_headers,
    )
    assert listed_rates.status_code == 200
    assert listed_rates.json()[0]["rate"] == 83.25

    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=admin_headers)
    assert run.status_code == 201
    run_id = run.json()["id"]

    record = db.query(PayrollRecord).filter(
        PayrollRecord.payroll_run_id == run_id,
        PayrollRecord.employee_id == employee.id,
    ).first()
    assert record is not None
    assert record.salary_currency == "USD"
    assert record.converted_currency == "INR"
    assert Decimal(str(record.exchange_rate)) == Decimal("83.250000")
    assert record.gross_salary > Decimal("800000")

    snapshot = db.query(PayrollCalculationSnapshot).filter(
        PayrollCalculationSnapshot.payroll_run_id == run_id,
        PayrollCalculationSnapshot.employee_id == employee.id,
        PayrollCalculationSnapshot.snapshot_type == "PayrollRun",
    ).first()
    assert snapshot is not None
    assert snapshot.result_json["salary_currency"] == "USD"
    assert snapshot.result_json["converted_currency"] == "INR"

    payslip = client.get("/api/v1/payroll/payslip?month=5&year=2026", headers=employee_headers)
    assert payslip.status_code == 200
    assert payslip.json()["salary_currency"] == "USD"
    assert payslip.json()["converted_currency"] == "INR"
