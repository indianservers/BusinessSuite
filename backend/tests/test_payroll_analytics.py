from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollRecord, PayrollRun


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_payroll_analytics_returns_range_totals_trends_and_breakdowns(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal("900000"), effective_from=date(2026, 4, 1), is_active=True))
    april = PayrollRun(month=4, year=2026, status="approved", total_gross=Decimal("100000"), total_net=Decimal("80000"))
    may = PayrollRun(month=5, year=2026, status="approved", total_gross=Decimal("120000"), total_net=Decimal("96000"))
    db.add_all([april, may])
    db.flush()
    db.add_all([
        PayrollRecord(
            payroll_run_id=april.id,
            employee_id=employee.id,
            gross_salary=Decimal("100000"),
            pf_employer=Decimal("12000"),
            esi_employer=Decimal("0"),
            reimbursements=Decimal("5000"),
            bonus=Decimal("10000"),
            total_deductions=Decimal("20000"),
            net_salary=Decimal("80000"),
        ),
        PayrollRecord(
            payroll_run_id=may.id,
            employee_id=employee.id,
            gross_salary=Decimal("120000"),
            pf_employer=Decimal("14400"),
            esi_employer=Decimal("0"),
            reimbursements=Decimal("3000"),
            bonus=Decimal("0"),
            total_deductions=Decimal("24000"),
            net_salary=Decimal("96000"),
        ),
    ])
    db.commit()

    response = client.get(
        "/api/v1/payroll/analytics",
        params={"from_month": 4, "from_year": 2026, "to_month": 5, "to_year": 2026},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["records"] == 2
    assert body["totals"]["headcount"] == 1
    assert _money(body["totals"]["gross_salary"]) == Decimal("220000.00")
    assert _money(body["totals"]["employer_statutory_cost"]) == Decimal("26400.00")
    assert _money(body["totals"]["reimbursement_total"]) == Decimal("8000.00")
    assert _money(body["totals"]["bonus_total"]) == Decimal("10000.00")
    assert _money(body["totals"]["net_payout"]) == Decimal("176000.00")
    assert [row["period"] for row in body["trends"]["payroll_cost"]] == ["2026-04", "2026-05"]
    assert body["breakdowns"]["department_salary_cost"][0]["department_name"]
    assert body["breakdowns"]["cost_center_salary_cost"][0]["cost_center_name"]
    ctc_bands = {row["band"]: row for row in body["breakdowns"]["headcount_cost_by_ctc_band"]}
    assert ctc_bands["5l_to_10l"]["headcount"] == 1
