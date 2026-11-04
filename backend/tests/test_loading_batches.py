"""Regression coverage for real data calculations and bounded lookup work."""
from datetime import date
from decimal import Decimal
from sqlalchemy import event
from app.models.leave import LeaveRequest,LeaveType
from app.models.payroll import EmployeeSalary
from app.models.attendance import Attendance
from app.api.v1.leave_payroll import _calculate_lwp_feed
from tests.test_hrms_leave_payroll_feeds import _employee
from tests.payroll_test_utils import commit_payroll_fixture


def test_lwp_batch_keeps_overlap_half_day_attendance_and_latest_salary(db):
    employees=[_employee(db,f'BATCH-{i}') for i in range(12)]
    unpaid=LeaveType(name='Unpaid leave',code='UNPAID-BATCH',days_allowed=30,is_active=True)
    paid=LeaveType(name='Annual leave',code='PAID-BATCH',days_allowed=30,is_active=True)
    db.add_all([unpaid,paid]);db.flush()
    for employee in employees:
        db.add_all([
            LeaveRequest(employee_id=employee.id,leave_type_id=unpaid.id,from_date=date(2026,10,30),to_date=date(2026,11,2),days_count=4,status='Approved',reason='Boundary overlap'),
            LeaveRequest(employee_id=employee.id,leave_type_id=unpaid.id,from_date=date(2026,11,3),to_date=date(2026,11,3),days_count=Decimal('0.5'),is_half_day=True,status='Approved',reason='Half day'),
            LeaveRequest(employee_id=employee.id,leave_type_id=paid.id,from_date=date(2026,11,4),to_date=date(2026,11,4),days_count=1,status='Approved',reason='Paid must be excluded'),
            Attendance(employee_id=employee.id,attendance_date=date(2026,11,5),status='Absent'),
            EmployeeSalary(employee_id=employee.id,ctc=624000,basic=26000,effective_from=date(2026,1,1),is_active=True),
        ])
    commit_payroll_fixture(db)
    statements=[]
    def count(*args):statements.append(args[2])
    engine=db.get_bind();event.listen(engine,'before_cursor_execute',count)
    try:
        rows=_calculate_lwp_feed(db,'2026-11')
        batch=[row for row in rows if row['employeeCode'].startswith('BATCH-')]
        assert len(batch)==12
        assert all(row['leaveLwpDays']==2.5 and row['attendanceLwpDays']==1 and row['lwpDays']==3.5 and row['estimatedDeduction']==3500 for row in batch)
        assert len(statements)<=8,'Feed reads must not grow by three queries per employee'
    finally:event.remove(engine,'before_cursor_execute',count)
    without_attendance=_calculate_lwp_feed(db,'2026-11',employee_ids=[employees[0].id],include_attendance=False)
    assert len(without_attendance)==1 and without_attendance[0]['lwpDays']==2.5
