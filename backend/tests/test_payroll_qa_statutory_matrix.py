"""Configured synthetic PF/ESI thresholds; not a legal compliance certification."""
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import pytest
from app.crud.crud_payroll import _calculate_statutory_amounts
from app.models.employee import Employee
from app.models.payroll import PFRule, ESIRule, EmployeeStatutoryProfile


@pytest.mark.parametrize('basic',['14999.99','15000','15000.01'])
@pytest.mark.parametrize('gross',['0','20999.99','21000','21000.01','45500.75'])
def test_configured_statutory_caps_and_eligibility(db,basic,gross,record_property):
    employee=Employee(employee_id='QA-STAT',first_name='Synthetic',last_name='Statutory',date_of_joining=date(2024,1,1))
    db.add(employee);db.flush()
    db.add_all([EmployeeStatutoryProfile(employee_id=employee.id,pf_applicable=True,esi_applicable=True),
        PFRule(name='QA configured PF',wage_ceiling=15000,employee_rate=12,employer_rate=12,effective_from=date(2024,1,1),rounding_rule='Nearest Rupee',is_active=True),
        ESIRule(name='QA configured ESI',wage_threshold=21000,employee_rate=Decimal('.75'),employer_rate=Decimal('3.25'),effective_from=date(2024,1,1),rounding_rule='Nearest Rupee',is_active=True)])
    db.flush()
    actual,_=_calculate_statutory_amounts(db,employee.id,5,date(2026,5,1),Decimal(basic),Decimal(gross))
    round_rupee=lambda value:value.quantize(Decimal('1'),rounding=ROUND_HALF_EVEN).quantize(Decimal('.01'))
    expected_pf=round_rupee(min(Decimal(basic),Decimal(15000))*Decimal('.12'))
    expected_esi=round_rupee(Decimal(gross)*Decimal('.0075')) if Decimal(gross)<=21000 else Decimal(0)
    expected_employer_esi=round_rupee(Decimal(gross)*Decimal('.0325')) if Decimal(gross)<=21000 else Decimal(0)
    record_property('expected',str((expected_pf,expected_esi,expected_employer_esi)))
    record_property('actual',str((actual['pf_employee'],actual['esi_employee'],actual['esi_employer'])))
    assert actual['pf_employee']==expected_pf
    assert actual['pf_employer']==expected_pf
    assert actual['esi_employee']==expected_esi
    assert actual['esi_employer']==expected_employer_esi
