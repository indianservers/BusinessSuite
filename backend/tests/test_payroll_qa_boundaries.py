"""Calendar, wage-mode and malicious-input payroll regressions with explicit oracles."""
import calendar
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.crud.crud_payroll import get_prorated_salary_for_period, _non_monthly_base_pay, _attendance_day_value
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary
from app.schemas.payroll import EmployeeSalaryCreate, PayrollAttendanceInputCreate
from tests.payroll_expected_calculator import salary_segments

PERIODS = [(2025, 2), (2024, 2), (2026, 4), (2026, 5)]
SCENARIOS = ['full', 'default_components', 'middle', 'last', 'exit_first', 'exit_middle', 'prior_version', 'revision', 'outside', 'decimal']


@pytest.mark.parametrize('year,month', PERIODS)
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_calendar_salary_history(db, year, month, scenario, record_property):
    end = calendar.monthrange(year, month)[1]
    first, last = date(year, month, 1), date(year, month, end)
    start, stop = first, last
    if scenario == 'middle': start = date(year, month, 15)
    if scenario == 'last': start = last
    if scenario == 'exit_first': stop = first
    if scenario == 'exit_middle': stop = date(year, month, 15)
    if scenario == 'outside': start, stop = date(year-1, 1, 1), date(year-1, 12, 31)
    versions = [dict(start=start, end=stop, ctc='546009' if scenario == 'decimal' else '360000', basic='12000', hra='6000')]
    if scenario == 'default_components': versions[0].update(basic='0', hra='0')
    if scenario == 'prior_version': versions[0]['start'] = date(year-1, 1, 1)
    if scenario == 'revision':
        versions[0]['end'] = date(year, month, 14)
        versions.append(dict(start=date(year, month, 15), end=last, ctc='372000', basic='12400', hra='6200'))
    employee = Employee(employee_id='QA-CALENDAR', first_name='Synthetic', last_name='Payroll', date_of_joining=date(2020,1,1), status='Active')
    db.add(employee); db.flush()
    for v in versions:
        db.add(EmployeeSalary(employee_id=employee.id, ctc=Decimal(v['ctc']), basic=Decimal(v['basic']), hra=Decimal(v['hra']), effective_from=v['start'], effective_to=v['end'], is_active=v == versions[-1]))
    db.flush()
    expected = salary_segments(year, month, versions)
    actual = get_prorated_salary_for_period(db, employee.id, first, last)
    record_property('inputs', str(versions)); record_property('expected', str(expected)); record_property('actual', str(actual))
    assert actual == expected


@pytest.mark.parametrize('mode,rate,units,paid,expected', [
    ('daily','1000','99','0','0'), ('daily','1000','99','.5','500'), ('daily','1000','99','21','21000'),
    ('hourly','125.25','7.5','0','939.38'), ('per_lecture','1200','10','0','12000'),
    ('per_class','500','1','0','500'), ('per_delivery','55.5','12','0','666'),
    ('per_trip','250','3','0','750'), ('per_shift','800','2','0','1600'),
    ('piece_rate','12.25','25','0','306.25'), ('unit_based','33.33','3','0','99.99'),
    ('commission_based','100','2','0','200'), ('invoice_based','100','2','0','200')])
def test_wage_modes(mode, rate, units, paid, expected, record_property):
    salary = EmployeeSalary(payroll_type=mode, wage_rate=Decimal(rate), default_units=Decimal(units))
    actual = _non_monthly_base_pay(salary, Decimal(paid))[0]
    record_property('expected', expected); record_property('actual', str(actual))
    assert actual == Decimal(expected)


@pytest.mark.parametrize('status,expected', [('Present','1'),('WFH','1'),('Remote','1'),('Work From Home','1'),('Half-day','.5'),('Half day','.5'),('half_day','.5'),('Absent','0'),('On Leave','0'),(None,'0')])
def test_attendance_status_units(status, expected):
    assert _attendance_day_value(status) == Decimal(expected)


@pytest.mark.parametrize('field', ['ctc','basic','hra','wage_rate','default_units','commission_rate_percent','commission_base_amount','invoice_amount'])
def test_salary_rejects_negative_amount(field):
    payload = dict(employee_id=1, ctc='360000', effective_from='2026-05-01')
    payload[field] = '-0.01'
    with pytest.raises(ValidationError): EmployeeSalaryCreate(**payload)


@pytest.mark.parametrize('field', ['working_days','payable_days','present_days','paid_leave_days','unpaid_leave_days','lop_days','holiday_days','weekly_off_days','ot_hours'])
def test_attendance_rejects_negative_units(field):
    payload = dict(period_id=1, employee_id=1, working_days='21')
    payload[field] = '-0.5'
    with pytest.raises(ValidationError): PayrollAttendanceInputCreate(**payload)


@pytest.mark.parametrize('field', ['payable_days','present_days','lop_days'])
def test_attendance_rejects_units_beyond_working_days(field):
    payload = dict(period_id=1, employee_id=1, working_days='21')
    payload[field] = '21.5'
    with pytest.raises(ValidationError): PayrollAttendanceInputCreate(**payload)


def test_salary_rejects_reversed_effective_dates():
    with pytest.raises(ValidationError):
        EmployeeSalaryCreate(employee_id=1, ctc='360000', effective_from='2026-05-15', effective_to='2026-05-01')


@pytest.mark.parametrize('mode,base,percentage,invoice,expected',[
    ('commission_based','100000','2.5','0','2500'),
    ('commission_based','100000','0','0','200'),
    ('invoice_based','0','0','45500.75','45500.75')])
def test_wage_modes_explicit_commission_and_invoice(mode,base,percentage,invoice,expected):
    salary=EmployeeSalary(payroll_type=mode,wage_rate=Decimal(100),default_units=Decimal(2),commission_base_amount=Decimal(base),commission_rate_percent=Decimal(percentage),invoice_amount=Decimal(invoice))
    assert _non_monthly_base_pay(salary,Decimal(0))[0]==Decimal(expected)
