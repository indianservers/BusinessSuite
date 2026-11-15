"""Actual Guided Payroll native computation retains authority and private data boundaries."""
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case
from tests.payroll_review_test_utils import review_candidate


@pytest.mark.parametrize('mode,count',[('own',1),('team',2),('organization',2)])
def test_guided_preserves_native_records_and_actual_readiness_blockers(register_case,mode,count):
    from app.access.models import AccessPolicy
    n=register_case;user=n.user;headers=n.headers
    if mode=='team':
        n.employee.reporting_manager_id=None;n.manager.reporting_manager_id=n.employee.id
    policy=n.db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}};n.db.commit();select_pack(n)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers={**headers,'X-Suite-Pack-Context':'bad'})
    assert response.status_code==200,response.text
    result=response.json();assert len(result['records'])==count
    assert result['blocked'] is True
    assert any(issue['key']=='missing_bank' for issue in result['issues'])
    assert any('attendance input' in message for message in result['blockers'])
    assert not result['can_process'] and not result['can_approve']
    assert not {'account_number','bank_account','ifsc_code','ctc','basic','personal_email'} & set(result)
    assert all(set(record)=={'id','employee_id','employee_name','gross','deductions','net','currency'} for record in result['records'])


def test_guided_missing_native_payroll_permission_is_not_a_pack_grant(core_case):
    n=core_case;select_pack(n)
    response=n.client.get('/api/v1/payroll/runs/1/guided',headers=n.headers)
    assert response.status_code==403,response.text


@pytest.mark.parametrize('attack',['salary-body','salary-amount','contact','bank-line','raw-component','unknown','write'])
def test_guided_private_computation_cannot_escape_fixed_native_projection(register_case,monkeypatch,attack):
    from app.api.v1 import payroll_guided
    from app.models.payroll import EmployeeSalary,PayrollPaymentLine,PayrollRun,PayrollComponent
    from app.models.employee import Employee
    from app.apps.srm.models import SRMInvoice
    n=register_case;select_pack(n)
    def unsafe(run_id,db,user):
        if attack=='salary-body':db.query(EmployeeSalary).all()
        elif attack=='salary-amount':db.query(EmployeeSalary.ctc).all()
        elif attack=='contact':db.query(Employee.personal_email).all()
        elif attack=='bank-line':db.query(PayrollPaymentLine.bank_account).all()
        elif attack=='raw-component':
            from sqlalchemy import select
            db.execute(select(PayrollComponent.__table__.c.record_id)).all()
        elif attack=='unknown':db.query(SRMInvoice).all()
        else:db.query(PayrollRun).delete()
        return {}
    monkeypatch.setattr(payroll_guided,'native_overview',unsafe)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.admin_headers)
    assert response.status_code==403,response.text


@pytest.mark.parametrize('failure',[False,True])
def test_guided_reader_preserves_native_outer_transaction(register_case,monkeypatch,failure):
    from app.api.v1 import payroll_guided
    from app.models.company import Company
    from sqlalchemy import update,select
    n=register_case;select_pack(n);connection=n.db.connection()
    connection.execute(update(Company).where(Company.id==1).values(address='Outer transaction retained'))
    tx=connection.get_transaction();nested=connection.get_nested_transaction()
    if failure:
        def unsupported(run_id,db,user):
            db.commit()
        monkeypatch.setattr(payroll_guided,'native_overview',unsupported)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.admin_headers)
    assert response.status_code==(403 if failure else 200),response.text
    # HTTP failure rolls the request back in the existing API fixture. Success
    # must never be rolled back by the independently closed reader itself.
    if not failure:
        assert connection.get_transaction() is tx and connection.get_nested_transaction() is nested
        assert connection.scalar(select(Company.address).where(Company.id==1))=='Outer transaction retained'


