from decimal import Decimal
from datetime import date

from app.db.init_db import init_db
from app.models.attendance import Attendance, OvertimeRequest
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.payroll import EmployeeSalary, PayrollComponent, PayrollRunEmployee, PayrollCalculationSnapshot, PayrollPeriod
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _period(client, headers):
    pay_group = client.post(
        "/api/v1/payroll/setup/pay-groups",
        json={"name": "Inputs Payroll", "code": "INPUTS-PAY", "state": "Telangana"},
        headers=headers,
    )
    assert pay_group.status_code == 201
    period = client.post(
        "/api/v1/payroll/setup/periods",
        json={
            "pay_group_id": pay_group.json()["id"],
            "month": 5,
            "year": 2026,
            "financial_year": "2026-27",
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "payroll_date": "2026-05-30",
        },
        headers=headers,
    )
    assert period.status_code == 201
    return period.json()["id"]


def test_reconcile_inputs_blocks_approval_until_locked_and_creates_worksheet(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    if not db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active == True).first():
        db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal("600000"), basic=Decimal("20000"), hra=Decimal("10000"), effective_from=date(2026, 4, 1), is_active=True))
        db.commit()
    period_id = _period(client, headers)

    db.add(Attendance(employee_id=employee.id, attendance_date=date(2026, 5, 4), status="Present"))
    db.add(Attendance(employee_id=employee.id, attendance_date=date(2026, 5, 5), status="Present"))
    paid = db.query(LeaveType).filter(LeaveType.code == "EL").first() or LeaveType(name="Earned Leave", code="EL", days_allowed=12)
    unpaid = db.query(LeaveType).filter(LeaveType.code == "LOP").first() or LeaveType(name="Loss of Pay", code="LOP", days_allowed=0)
    db.add_all([paid, unpaid])
    db.flush()
    db.add(LeaveRequest(employee_id=employee.id, leave_type_id=paid.id, from_date=date(2026, 5, 6), to_date=date(2026, 5, 6), days_count=1, status="Approved"))
    db.add(LeaveRequest(employee_id=employee.id, leave_type_id=unpaid.id, from_date=date(2026, 5, 7), to_date=date(2026, 5, 7), days_count=1, status="Approved"))
    db.add(OvertimeRequest(employee_id=employee.id, date=date(2026, 5, 8), hours=Decimal("2.5"), status="Approved"))
    db.commit()

    draft_reconcile = client.post(
        "/api/v1/payroll/inputs/reconcile-attendance",
        json={"period_id": period_id, "employee_ids": [employee.id], "approve_inputs": False},
        headers=headers,
    )
    assert draft_reconcile.status_code == 201
    assert draft_reconcile.json()["inputs_created"] == 1
    inputs = client.get("/api/v1/payroll/inputs/attendance", params={"period_id": period_id}, headers=headers)
    assert inputs.status_code == 200
    assert inputs.json()[0]["source_status"] == "Draft"
    assert Decimal(str(inputs.json()[0]["paid_leave_days"])) == Decimal("1.0")
    assert Decimal(str(inputs.json()[0]["lop_days"])) == Decimal("1.0")
    ensure_payroll_ready(db, 5, 2026)

    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert run.status_code == 201
    blocked = client.put(
        f"/api/v1/payroll/runs/{run.json()['id']}/approve",
        json={"action": "approve", "remarks": "try approval"},
        headers=headers,
    )
    assert blocked.status_code == 400
    assert "attendance inputs" in blocked.json()["detail"]["message"]
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == period_id).first()
    period.status = "Open"
    db.commit()

    locked_reconcile = client.post(
        "/api/v1/payroll/inputs/reconcile-attendance",
        json={"period_id": period_id, "approve_inputs": True},
        headers=headers,
    )
    assert locked_reconcile.status_code == 201
    assert locked_reconcile.json()["overtime_lines_created"] == 0
    approved = client.put(
        f"/api/v1/payroll/runs/{run.json()['id']}/approve",
        json={"action": "approve", "remarks": "inputs checked"},
        headers=headers,
    )
    assert approved.status_code == 200

    worksheet = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/worksheet/process", headers=headers)
    assert worksheet.status_code == 201
    assert worksheet.json()["employees_processed"] >= 1
    assert db.query(PayrollRunEmployee).filter(PayrollRunEmployee.payroll_run_id == run.json()["id"]).count() >= 1
    assert db.query(PayrollCalculationSnapshot).filter(PayrollCalculationSnapshot.payroll_run_id == run.json()["id"]).count() >= 1


def test_payroll_input_lines_and_arrear_off_cycle_foundation(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    if not db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active == True).first():
        db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal("600000"), basic=Decimal("20000"), hra=Decimal("10000"), effective_from=date(2026, 4, 1), is_active=True))
        db.commit()
    period_id = _period(client, headers)

    lop = client.post(
        "/api/v1/payroll/inputs/lop-adjustments",
        json={"period_id": period_id, "employee_id": employee.id, "adjustment_days": "0.5", "reason": "Late approved unpaid day", "status": "Approved"},
        headers=headers,
    )
    assert lop.status_code == 201
    assert lop.json()["approved_by"] is not None

    ot_policy = client.post(
        "/api/v1/payroll/inputs/overtime-policies",
        json={"name": "Standard OT", "regular_multiplier": "1.5", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert ot_policy.status_code == 201
    ot_line = client.post(
        "/api/v1/payroll/inputs/overtime-lines",
        json={"period_id": period_id, "employee_id": employee.id, "policy_id": ot_policy.json()["id"], "hours": "3", "hourly_rate": "100", "multiplier": "1.5", "status": "Approved"},
        headers=headers,
    )
    assert ot_line.status_code == 201
    assert Decimal(str(ot_line.json()["amount"])) == Decimal("450.00")

    leave_type = db.query(LeaveType).filter(LeaveType.code == "EL").first() or LeaveType(name="Earned Leave", code="EL", days_allowed=12, encashable=True)
    db.add(leave_type)
    db.commit()
    encash_policy = client.post(
        "/api/v1/payroll/inputs/leave-encashment-policies",
        json={"name": "EL Encashment", "leave_type_id": leave_type.id, "max_days": "10", "effective_from": "2026-04-01"},
        headers=headers,
    )
    assert encash_policy.status_code == 201
    encash_line = client.post(
        "/api/v1/payroll/inputs/leave-encashment-lines",
        json={"period_id": period_id, "employee_id": employee.id, "policy_id": encash_policy.json()["id"], "leave_type_id": leave_type.id, "days": "2", "rate_per_day": "500", "status": "Approved"},
        headers=headers,
    )
    assert encash_line.status_code == 201
    assert Decimal(str(encash_line.json()["amount"])) == Decimal("1000.00")

    attendance_input = client.post(
        "/api/v1/payroll/inputs/attendance",
        json={"period_id": period_id, "employee_id": employee.id, "working_days": "21", "payable_days": "20.5", "present_days": "20", "lop_days": "0.5", "ot_hours": "3", "source_status": "Approved"},
        headers=headers,
    )
    assert attendance_input.status_code == 201
    ensure_payroll_ready(db, 5, 2026)
    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert run.status_code == 201
    components = db.query(PayrollComponent).join(PayrollComponent.record).filter(PayrollComponent.component_name.in_(["Overtime Pay", "Leave Encashment"])).all()
    assert {component.component_name for component in components} == {"Overtime Pay", "Leave Encashment"}
    assert all(component.source_type == "payroll_engine" for component in components)

    arrear = client.post(
        "/api/v1/payroll/arrear-runs",
        json={"payroll_run_id": run.json()["id"], "name": "May corrections", "lines": [{"employee_id": employee.id, "component_name": "Basic Arrear", "amount": "2500"}]},
        headers=headers,
    )
    assert arrear.status_code == 201
    assert arrear.json()["lines"][0]["component_name"] == "Basic Arrear"

    off_cycle = client.post(
        "/api/v1/payroll/off-cycle-runs",
        json={"month": 5, "year": 2026, "run_type": "Bonus", "reason": "Spot bonus", "total_amount": "5000"},
        headers=headers,
    )
    assert off_cycle.status_code == 201
    assert off_cycle.json()["run_type"] == "Bonus"
