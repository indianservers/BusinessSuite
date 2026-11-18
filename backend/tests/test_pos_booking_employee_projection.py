"""POS booking can read its closed employee projection without HRMS profile access."""
import pytest
from fastapi import HTTPException
from sqlalchemy import event, false
from sqlalchemy.orm import with_loader_criteria
from types import SimpleNamespace
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer
from app.models.employee import Employee
from app.apps.srm.industry_api import provider_employee
from app.apps.srm.service_checkout import _assert_employee_category
from app.apps.srm.service_checkout_models import ServiceBookingPolicy


def test_booking_projection_does_not_open_hrms_profile_access(db, scenario):
    user, branch, _, basket = scenario
    ident = basket(False).lines[1].booking.employee_id
    employee = db.get(Employee, ident)
    employee.work_categories = ['DEMO Technical Services > Computer Repair']
    db.commit()
    policy = db.query(ServiceBookingPolicy).one()
    policy.employee_categories = ['DEMO Technical Services']
    db.commit()

    def deny_profile_reads(state):
        if state.is_select:
            state.statement = state.statement.options(with_loader_criteria(Employee, false(), include_aliases=True))
    event.listen(db, 'do_orm_execute', deny_profile_reads)
    try:
        with native_writer(db, user, branch):
            assert db.query(Employee).filter_by(id=ident).first() is None
            result = provider_employee(db, user, branch, ident)
            assert set(vars(result)) == {'id', 'user_id', 'date_of_exit', 'work_categories'}
            assert result.id == ident
            _assert_employee_category(db, ident, policy)
            assert db.query(Employee).filter_by(id=ident).first() is None
            with pytest.raises(HTTPException) as wrong_branch:
                provider_employee(db, user, branch + 9999, ident)
            assert wrong_branch.value.status_code == 403
            with pytest.raises(HTTPException) as wrong_company:
                _assert_employee_category(db, ident, SimpleNamespace(employee_categories=['DEMO Technical Services'],
                    branch_id=branch, organization_id=999999))
            assert wrong_company.value.status_code == 409
            with pytest.raises(HTTPException) as wrong_category:
                _assert_employee_category(db, ident, SimpleNamespace(employee_categories=['DEMO Consulting'],
                    branch_id=branch, organization_id=1))
            assert wrong_category.value.status_code == 409
    finally:
        event.remove(db, 'do_orm_execute', deny_profile_reads)


@pytest.mark.parametrize('field,value', [('status','Inactive'), ('deleted_at',__import__('datetime').datetime.now())])
def test_booking_projection_rejects_inactive_or_deleted_employee(db, scenario, field, value):
    user, branch, _, basket = scenario
    ident = basket(False).lines[1].booking.employee_id
    employee = db.get(Employee, ident)
    setattr(employee, field, value)
    db.commit()
    with native_writer(db, user, branch):
        with pytest.raises(HTTPException) as denied:
            provider_employee(db, user, branch, ident)
        assert denied.value.status_code == 422
