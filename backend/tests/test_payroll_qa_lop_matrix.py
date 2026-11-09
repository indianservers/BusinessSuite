import calendar
from datetime import date
from decimal import Decimal
import pytest
from app.crud.crud_payroll import run_payroll
from app.models.employee import Employee
from app.models.user import User
from app.models.payroll import EmployeeSalary, PayrollAttendanceInput, PayrollRecord
from tests.payroll_test_utils import init_payroll_test_db, ensure_payroll_ready, commit_payroll_fixture
from tests.payroll_expected_calculator import monthly_pay


@pytest.mark.parametrize('year,month', [(2025,2),(2024,2),(2026,4),(2026,5)])
@pytest.mark.parametrize('lop', ['0','.5','1','1.5','all'])
def test_real_engine_lop_with_independent_oracle(db,year,month,lop,record_property):
    init_payroll_test_db(db)
    employee=db.query(Employee).filter_by(employee_id='DEMO-EMP-001').one()
    employee.functional_area='QA-LOP-ONLY'
    # Close the demo salary before assigning this case's controlled salary.
    for old in db.query(EmployeeSalary).filter_by(employee_id=employee.id).all():
        old.is_active=False
        old.effective_to=date(year-2,12,31)
    salary='45500.75' if month==4 else '31000' if month==5 else '30000'
    db.add(EmployeeSalary(employee_id=employee.id,ctc=Decimal(salary)*12,basic=Decimal('12000'),hra=Decimal('6000'),effective_from=date(year-1,1,1),is_active=True))
    commit_payroll_fixture(db)
    period=ensure_payroll_ready(db,month,year,[employee])
    length=calendar.monthrange(year,month)[1]
    work=sum(date(year,month,day).weekday()<5 for day in range(1,length+1))
    loss=Decimal(work) if lop=='all' else Decimal(lop)
    db.add(PayrollAttendanceInput(period_id=period.id,employee_id=employee.id,working_days=work,payable_days=Decimal(work)-loss,present_days=Decimal(work)-loss,lop_days=loss,source_status='Approved'))
    commit_payroll_fixture(db)
    actor=db.query(User).filter_by(email='admin@aihrms.com').one()
    result=run_payroll(db,month,year,run_by_user_id=actor.id,force_run=True,employee_category='QA-LOP-ONLY')
    record=db.query(PayrollRecord).filter_by(payroll_run_id=result.id,employee_id=employee.id).one()
    expected,_=monthly_pay(salary,length,length,work,loss)
    record_property('inputs',f'monthly={salary};working_days={work};LOP={loss};calendar_days={length}')
    record_property('expected',str(expected));record_property('actual',str(record.gross_salary))
    assert record.gross_salary==expected
    assert record.net_salary==record.gross_salary-record.total_deductions
    from app.schemas.payroll import PayrollRunSchema
    assert PayrollRunSchema.model_validate(result).total_employees==1


@pytest.mark.parametrize('status,included',[('Active',True),('Probation',True),('Resigned',True),('Inactive',False),('Terminated',False)])
def test_employee_lifecycle_payroll_eligibility(db,status,included):
    init_payroll_test_db(db)
    employee=db.query(Employee).filter_by(employee_id='DEMO-EMP-001').one()
    employee.status=status
    # Historical eligibility follows employment dates, including former employees.
    if not included: employee.date_of_exit=date(2026,4,30)
    employee.functional_area='QA-LIFECYCLE-ONLY'
    ensure_payroll_ready(db,5,2026,[employee])
    commit_payroll_fixture(db)
    actor=db.query(User).filter_by(email='admin@aihrms.com').one()
    result=run_payroll(db,5,2026,run_by_user_id=actor.id,force_run=True,employee_category='QA-LIFECYCLE-ONLY')
    assert db.query(PayrollRecord).filter_by(payroll_run_id=result.id,employee_id=employee.id).count()==int(included)
