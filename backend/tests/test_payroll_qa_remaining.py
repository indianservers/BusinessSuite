"""Remaining payroll reliability and historical-input regression cases."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
import uuid
import pytest
from sqlalchemy.orm import Session
from app.crud import crud_payroll
from app.models.employee import Employee
from app.models.user import User
from app.models.payroll import PayrollRun, PayrollRecord, Reimbursement, SalaryAdvance, OvertimePayLine, LeaveEncashmentLine
from tests.payroll_test_utils import init_payroll_test_db, ensure_payroll_ready, commit_payroll_fixture
from app.models.leave import LeaveRequest, LeaveType, LeaveBalance
from app.api.v1.payroll import reconcile_payroll_attendance_inputs
from app.schemas.payroll import PayrollAttendanceReconcileRequest


def setup_employee(db, category='QA-REMAINING'):
    init_payroll_test_db(db)
    employee=db.query(Employee).filter_by(employee_id='DEMO-EMP-001').one()
    employee.functional_area=category
    period=ensure_payroll_ready(db,5,2026,[employee])
    actor=db.query(User).filter_by(email='admin@aihrms.com').one()
    commit_payroll_fixture(db)
    return employee,period,actor


@pytest.mark.parametrize('kind',['reimbursement','advance','overtime','encashment'])
def test_reprocessing_preserves_previously_consumed_inputs(db,kind,record_property):
    employee,period,actor=setup_employee(db)
    common=dict(employee_id=employee.id,status='Approved')
    if kind=='reimbursement': line=Reimbursement(**common,category='QA Travel',amount=Decimal('1250'),date=date(2026,5,4))
    elif kind=='advance': line=SalaryAdvance(**common,requested_amount=Decimal('1250'),approved_amount=Decimal('1250'),requested_deduction_month=5,requested_deduction_year=2026)
    elif kind=='overtime': line=OvertimePayLine(**common,period_id=period.id,hours=Decimal(2),hourly_rate=Decimal(625),multiplier=1,amount=Decimal(1250),ot_date=date(2026,5,4))
    else: line=LeaveEncashmentLine(**common,period_id=period.id,days=Decimal(1),amount=Decimal(1250))
    db.add(line);commit_payroll_fixture(db)
    run=crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    first=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    expected=(first.gross_salary,first.total_deductions,first.net_salary)
    # Repeat generation must retain that same one-time input, without doubling it.
    rerun=crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    second=db.query(PayrollRecord).filter_by(payroll_run_id=rerun.id,employee_id=employee.id).one()
    actual=(second.gross_salary,second.total_deductions,second.net_salary)
    record_property('expected',str(expected));record_property('actual',str(actual))
    assert actual==expected
    assert line.payroll_record_id==second.id
    assert db.query(PayrollRecord).filter_by(payroll_run_id=rerun.id,employee_id=employee.id).count()==1


def test_processing_failure_rolls_back_partial_records(db,monkeypatch):
    employee,period,actor=setup_employee(db)
    from app.models.payroll import EmployeeSalary
    second=Employee(employee_id='QA-FAILURE-SECOND',first_name='Synthetic',last_name='Second',date_of_joining=date(2024,1,1),branch_id=employee.branch_id,status='Active',functional_area='QA-REMAINING')
    db.add(second);db.flush()
    db.add(EmployeeSalary(employee_id=second.id,ctc=Decimal(360000),effective_from=date(2024,1,1),is_active=True))
    commit_payroll_fixture(db)
    original=crud_payroll._calculate_statutory_amounts
    calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:
            assert db.query(PayrollRecord).count()==1
            raise RuntimeError('QA injected calculation failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(crud_payroll,'_calculate_statutory_amounts',fail)
    with pytest.raises(RuntimeError,match='QA injected'):
        crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    db.rollback()
    assert db.query(PayrollRun).filter_by(employee_category='QA-REMAINING').count()==0
    assert db.query(PayrollRecord).count()==0
    monkeypatch.setattr(crud_payroll,'_calculate_statutory_amounts',original)


@pytest.mark.parametrize('scenario,expected',[
    ('duplicate_full',Decimal(1)),('duplicate_first_half',Decimal('.5')),
    ('different_halves',Decimal(1)),('full_plus_half',Decimal(1)),
    ('deleted_full',Decimal(0)),('deleted_half',Decimal(0)),
])
def test_reconciliation_deduplicates_unpaid_intervals(db,scenario,expected,record_property):
    employee,period,actor=setup_employee(db)
    period.status='Open'
    leave_type=LeaveType(name='QA Unpaid',code='QA-LOP',days_allowed=30)
    db.add(leave_type);db.flush()
    half=scenario in {'duplicate_first_half','different_halves','deleted_half'}
    def leave(half,part='First Half',deleted=False):
        return LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,5,4),to_date=date(2026,5,4),days_count=Decimal('.5') if half else Decimal(1),is_half_day=half,half_day_period=part,status='Approved',deleted_at=datetime.now(timezone.utc) if deleted else None)
    db.add(leave(half,deleted=scenario.startswith('deleted')))
    if scenario.startswith('duplicate'):db.add(leave(half))
    if scenario=='different_halves':db.add(leave(True,'Second Half'))
    if scenario=='full_plus_half':db.add(leave(True))
    commit_payroll_fixture(db)
    reconcile_payroll_attendance_inputs(PayrollAttendanceReconcileRequest(period_id=period.id,employee_ids=[employee.id],approve_inputs=True),db,actor)
    from app.models.payroll import PayrollAttendanceInput
    actual=db.query(PayrollAttendanceInput).filter_by(employee_id=employee.id,period_id=period.id).one().lop_days
    record_property('expected',str(expected));record_property('actual',str(actual))
    assert actual==expected


def test_locked_run_blocks_reconciliation_even_if_input_period_open(db):
    from fastapi import HTTPException
    employee,period,actor=setup_employee(db)
    run=crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    run.status='locked';period.status='Open';commit_payroll_fixture(db)
    with pytest.raises(HTTPException) as rejected:
        reconcile_payroll_attendance_inputs(PayrollAttendanceReconcileRequest(period_id=period.id,employee_ids=[employee.id]),db,actor)
    assert rejected.value.status_code==400


def test_locked_run_blocks_pending_manual_input_review(db):
    from fastapi import HTTPException
    from app.api.v1.payroll import review_manual_input
    from app.models.payroll import PayrollManualInput
    from app.schemas.payroll import PayrollManualInputReview
    employee,period,actor=setup_employee(db)
    run=crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    item=PayrollManualInput(payroll_run_id=run.id,employee_id=employee.id,input_type='Bonus',component_name='QA pending bonus',amount=500,status='Pending')
    db.add(item);run.status='locked';commit_payroll_fixture(db)
    with pytest.raises(HTTPException) as rejected:review_manual_input(item.id,PayrollManualInputReview(action='approve'),db,actor)
    assert rejected.value.status_code==400
    db.refresh(item);assert item.status=='Pending'


@pytest.mark.parametrize('scenario',['before_join','after_exit','half_multiple_dates','half_disallowed'])
def test_leave_request_respects_employment_and_half_day_configuration(db,scenario):
    from app.crud.crud_leave import create_leave_request
    employee,period,actor=setup_employee(db)
    employee.date_of_joining=date(2026,5,4)
    employee.date_of_exit=date(2026,5,20)
    leave_type=LeaveType(name='QA Controlled',code='QA-CONTROLLED',days_allowed=30,half_day_allowed=scenario!='half_disallowed')
    db.add(leave_type);db.flush()
    db.add(LeaveBalance(employee_id=employee.id,leave_type_id=leave_type.id,year=2026,allocated=10,used=0,pending=0,carried_forward=0))
    commit_payroll_fixture(db)
    start=date(2026,5,1) if scenario=='before_join' else date(2026,5,21) if scenario=='after_exit' else date(2026,5,5)
    stop=date(2026,5,6) if scenario=='half_multiple_dates' else start
    with pytest.raises(ValueError):
        create_leave_request(db,employee.id,dict(leave_type_id=leave_type.id,from_date=start,to_date=stop,is_half_day=scenario.startswith('half_'),reason='QA boundary'))


@pytest.mark.parametrize('year,month',[(2025,2),(2024,2),(2026,4),(2026,5)])
@pytest.mark.parametrize('boundary',['join','exit'])
def test_salary_revision_intersects_employment_before_proration(db,year,month,boundary,record_property):
    import calendar
    from app.models.payroll import EmployeeSalary, PayrollAttendanceInput, PayrollManualInput
    from tests.payroll_expected_calculator import monthly_pay
    employee,_,actor=setup_employee(db)
    length=calendar.monthrange(year,month)[1]
    first,last=date(year,month,1),date(year,month,length)
    employee.date_of_joining=date(year,month,15) if boundary=='join' else date(year-2,1,1)
    employee.date_of_exit=date(year,month,14) if boundary=='exit' else None
    for old in db.query(EmployeeSalary).filter_by(employee_id=employee.id).all():
        old.is_active=False;old.effective_to=date(year-3,12,31)
    db.add_all([EmployeeSalary(employee_id=employee.id,ctc=Decimal(360000),basic=12000,hra=6000,effective_from=first,effective_to=date(year,month,14),is_active=False),EmployeeSalary(employee_id=employee.id,ctc=Decimal(372000),basic=12400,hra=6200,effective_from=date(year,month,15),is_active=True)])
    commit_payroll_fixture(db)
    period=ensure_payroll_ready(db,month,year,[employee])
    start=employee.date_of_joining if boundary=='join' else first
    end=employee.date_of_exit if boundary=='exit' else last
    employed=(end-start).days+1
    work=sum(date.fromordinal(start.toordinal()+offset).weekday()<5 for offset in range(employed))
    db.add(PayrollAttendanceInput(period_id=period.id,employee_id=employee.id,working_days=work,payable_days=Decimal(work)-Decimal('.5'),present_days=Decimal(work)-Decimal('.5'),lop_days=Decimal('.5'),source_status='Approved'))
    commit_payroll_fixture(db)
    run=crud_payroll.run_payroll(db,month,year,actor.id,force_run=True,employee_category='QA-REMAINING',company_id=employee.branch.company_id,branch_id=employee.branch_id)
    db.add_all([PayrollManualInput(payroll_run_id=run.id,employee_id=employee.id,input_type='Bonus',component_name='QA fixed bonus',amount=1000,status='Approved'),PayrollManualInput(payroll_run_id=run.id,employee_id=employee.id,input_type='Deduction',component_name='QA recovery',amount=250,status='Approved')])
    commit_payroll_fixture(db)
    repeated=crud_payroll.run_payroll(db,month,year,actor.id,force_run=True,employee_category='QA-REMAINING',company_id=employee.branch.company_id,branch_id=employee.branch_id)
    assert repeated.id==run.id
    record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    expected,_=monthly_pay('31000' if boundary=='join' else '30000',length,employed,work,Decimal('.5'),earnings=1000)
    record_property('expected',str(expected));record_property('actual',str(record.gross_salary))
    assert record.gross_salary==expected
    assert record.other_deductions>=250


@pytest.mark.parametrize('paid,half,expected',[(False,False,Decimal(1)),(False,True,Decimal(1)),(True,False,Decimal(0)),(True,True,Decimal('.5'))])
def test_lwp_feed_does_not_deduct_approved_leave_and_absence_twice(db,paid,half,expected):
    from app.models.attendance import Attendance
    from app.api.v1.leave_payroll import _calculate_lwp_feed
    employee,period,actor=setup_employee(db)
    leave_type=LeaveType(name='QA Paid' if paid else 'QA Unpaid',code='QA-EL' if paid else 'QA-LOP',days_allowed=30)
    db.add(leave_type);db.flush()
    db.add(LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,5,4),to_date=date(2026,5,4),days_count=Decimal('.5') if half else 1,is_half_day=half,status='Approved'))
    db.add(Attendance(employee_id=employee.id,attendance_date=date(2026,5,4),status='Absent'))
    commit_payroll_fixture(db)
    rows=_calculate_lwp_feed(db,'2026-05',[employee.id])
    actual=Decimal(str(rows[0]['lwpDays'])) if rows else Decimal(0)
    assert actual==expected


def test_lwp_cancellation_clears_previously_synced_deduction(db):
    from app.api.v1.leave_payroll import sync_lwp_feed,LWPSyncPayload
    from app.models.payroll import PayrollAttendanceInput
    employee,period,actor=setup_employee(db);period.status='Open'
    leave_type=LeaveType(name='QA Unpaid',code='QA-LOP',days_allowed=30)
    db.add(leave_type);db.flush()
    leave=LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,5,4),to_date=date(2026,5,4),days_count=1,status='Approved')
    db.add(leave);commit_payroll_fixture(db)
    payload=LWPSyncPayload(month='2026-05',employeeIds=[employee.id])
    sync_lwp_feed(payload,db,actor)
    item=db.query(PayrollAttendanceInput).filter_by(period_id=period.id,employee_id=employee.id).one()
    assert item.lop_days==1
    leave.status='Cancelled';commit_payroll_fixture(db)
    sync_lwp_feed(payload,db,actor)
    db.refresh(item);assert item.lop_days==0


@pytest.mark.parametrize('adjustment,expected',[('-.5','.5'),('-1','0'),('-2','0')])
def test_lwp_correction_cannot_produce_negative_payroll_days(db,adjustment,expected):
    from app.api.v1.leave_payroll import _calculate_lwp_feed
    from app.models.payroll import LOPAdjustment
    employee,period,actor=setup_employee(db)
    leave_type=LeaveType(name='QA Unpaid',code='QA-LOP',days_allowed=30)
    db.add(leave_type);db.flush()
    db.add(LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,5,4),to_date=date(2026,5,4),days_count=1,status='Approved'))
    db.add(LOPAdjustment(period_id=period.id,employee_id=employee.id,adjustment_days=Decimal(adjustment),status='Approved'))
    commit_payroll_fixture(db)
    rows=_calculate_lwp_feed(db,'2026-05',[employee.id],include_zero=True)
    assert Decimal(str(rows[0]['lwpDays']))==Decimal(expected)


@pytest.mark.parametrize('historical,current,expected',[('monthly_fixed','hourly','30000'),('daily','monthly_fixed','21000'),('hourly','monthly_fixed','1000')])
def test_future_pay_mode_does_not_change_historical_payroll(db,historical,current,expected,record_property):
    from app.models.payroll import EmployeeSalary
    employee,period,actor=setup_employee(db)
    for old in db.query(EmployeeSalary).filter_by(employee_id=employee.id).all():
        old.is_active=False;old.effective_to=date(2023,12,31)
    db.add_all([
        EmployeeSalary(employee_id=employee.id,ctc=360000 if historical=='monthly_fixed' else 0,basic=12000,hra=6000,payroll_type=historical,wage_rate=1000 if historical=='daily' else 125,default_units=8,effective_from=date(2026,5,1),effective_to=date(2026,5,31),is_active=False),
        EmployeeSalary(employee_id=employee.id,ctc=600000,payroll_type=current,wage_rate=100,default_units=10,effective_from=date(2026,6,1),is_active=True),
    ])
    commit_payroll_fixture(db)
    run=crud_payroll.run_payroll(db,5,2026,actor.id,force_run=True,employee_category='QA-REMAINING')
    record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    record_property('expected',expected);record_property('actual',str(record.gross_salary))
    assert record.gross_salary==Decimal(expected)


@pytest.mark.parametrize('path',['reconcile','lwp_sync'])
def test_full_period_unpaid_leave_cannot_exceed_payroll_day_denominator(db,path):
    from app.api.v1.leave_payroll import sync_lwp_feed,LWPSyncPayload
    from app.models.payroll import PayrollAttendanceInput
    employee,period,actor=setup_employee(db);period.status='Open'
    leave_type=LeaveType(name='QA Unpaid',code='QA-LOP',days_allowed=31)
    db.add(leave_type);db.flush()
    db.add(LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,5,1),to_date=date(2026,5,31),days_count=31,status='Approved'))
    commit_payroll_fixture(db)
    if path=='reconcile':reconcile_payroll_attendance_inputs(PayrollAttendanceReconcileRequest(period_id=period.id,employee_ids=[employee.id]),db,actor)
    else:sync_lwp_feed(LWPSyncPayload(month='2026-05',employeeIds=[employee.id]),db,actor)
    item=db.query(PayrollAttendanceInput).filter_by(employee_id=employee.id,period_id=period.id).one()
    assert item.working_days==21
    assert item.lop_days==21
    assert item.payable_days==0
