"""Execute the real reconciliation handler with disposable DB rows."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from app.api.v1.payroll import reconcile_payroll_attendance_inputs
from app.schemas.payroll import PayrollAttendanceReconcileRequest
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveRequest
from app.models.payroll import PayrollPayGroup, PayrollPeriod, PayrollAttendanceInput


CASES = [(status, unpaid, half, date(2026,5,4), date(2026,5,4))
         for status in ('Approved','Pending','Rejected','Cancelled') for unpaid in (False,True) for half in (False,True)]
CASES += [('Approved', unpaid, False, start, stop) for unpaid in (False, True)
          for start,stop in [(date(2026,4,30),date(2026,5,1)),(date(2026,5,29),date(2026,6,1))]]


@pytest.mark.parametrize('status,unpaid,half,start,stop', CASES)
def test_leave_reconciliation_status_and_boundaries(db, superuser_headers, status, unpaid, half, start, stop, record_property):
    employee = Employee(employee_id='QA-LEAVE', first_name='Synthetic', last_name='Leave', date_of_joining=date(2024,1,1), status='Active')
    group = PayrollPayGroup(code='QA-LEAVE',name='QA Leave')
    leave_type = LeaveType(code='LOP' if unpaid else 'EL', name='Loss of Pay' if unpaid else 'Earned Leave', days_allowed=30)
    db.add_all([employee,group,leave_type]); db.flush()
    period = PayrollPeriod(pay_group_id=group.id,month=5,year=2026,financial_year='2026-27',period_start=date(2026,5,1),period_end=date(2026,5,31),payroll_date=date(2026,5,31),status='Open')
    db.add(period); db.flush()
    db.add(LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=start,to_date=stop,days_count=Decimal('.5') if half else Decimal((stop-start).days+1),is_half_day=half,status=status))
    db.flush()
    from app.models.user import User
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    result = reconcile_payroll_attendance_inputs(PayrollAttendanceReconcileRequest(period_id=period.id,employee_ids=[employee.id],approve_inputs=True), db, actor)
    item = db.query(PayrollAttendanceInput).filter_by(employee_id=employee.id).one()
    # Current reconciliation counts inclusive calendar overlap, including weekends.
    # That policy mismatch with the main engine is reported separately, not silently changed.
    days = Decimal(0) if status != 'Approved' else Decimal('.5') if half else Decimal((min(stop,date(2026,5,31))-max(start,date(2026,5,1))).days+1)
    expected = (days if not unpaid else Decimal(0),days if unpaid else Decimal(0),Decimal(21)-(days if unpaid else Decimal(0)))
    actual = (item.paid_leave_days,item.lop_days,item.payable_days)
    record_property('expected',str(expected)); record_property('actual',str(actual))
    assert result['inputs_created'] == 1
    assert actual == expected


@pytest.mark.parametrize('field,value', [('ctc','-1'),('basic','-1'),('hra','-1'),('wage_rate','-1'),('default_units','-1')])
def test_invalid_salary_api_rejected_without_writing(client, db, superuser_headers, field, value):
    from app.models.payroll import EmployeeSalary
    before = db.query(EmployeeSalary).count()
    payload = dict(employee_id=99999,ctc='360000',effective_from='2026-05-01')
    payload[field] = value
    response = client.post('/api/v1/payroll/salary',json=payload,headers=superuser_headers)
    assert response.status_code == 422, response.text
    assert db.query(EmployeeSalary).count() == before
