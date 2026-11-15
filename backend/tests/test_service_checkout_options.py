from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer
from app.apps.srm.service_checkout_options import service_options, provider_options
from app.apps.srm.service_checkout_models import ServiceSpecialistEligibility, ServiceBookingPolicy
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMProduct
from app.models.employee import Employee
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability


def test_real_legacy_options_return_only_policy_and_specialist_metadata(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        result = service_options(db, user, catalog[2][1])
        providers = provider_options(db, user)
    assert result['service_id'] == catalog[2][1]
    assert result['policy']['default_duration_minutes'] == 30
    assert len(result['specialists']) == 1
    row = result['specialists'][0]
    assert set(row) == {'eligibility_id', 'eligibility_revision', 'provider_resource_id', 'employee_id', 'employee_name', 'provider_name', 'timezone'}
    assert row['employee_name'] == 'QA Specialist'
    assert providers['providers'][0]['provider_resource_id'] == row['provider_resource_id']
    assert result['has_more'] is providers['has_more'] is False


def test_no_policy_is_explicit_and_product_validation_remains_native(db, scenario):
    user, branch, catalog, basket = scenario
    db.query(ServiceSpecialistEligibility).delete(); db.query(ServiceBookingPolicy).delete(); db.flush()
    with native_writer(db, user, branch):
        assert service_options(db, user, catalog[2][1]) == {'service_id': catalog[2][1], 'policy': None, 'specialists': [], 'has_more': False}
        with pytest.raises(HTTPException) as error:
            service_options(db, user, catalog[2][0])
        assert error.value.status_code == 404


@pytest.mark.parametrize('case', ['inactive_employee', 'exited_employee', 'inactive_resource', 'invalid_timezone', 'invalid_employee_reference', 'ineligible'])
def test_unavailable_specialists_never_appear(db, scenario, case):
    user, branch, catalog, basket = scenario
    provider = db.query(IndustryRecord).filter_by(kind='resource').one()
    employee = db.get(Employee, provider.data['employee_id'])
    if case == 'inactive_employee': employee.status = 'Terminated'
    elif case == 'exited_employee': employee.date_of_exit = date.today() - timedelta(days=1)
    elif case == 'inactive_resource': provider.status = 'inactive'
    elif case == 'invalid_timezone': provider.data = {**provider.data, 'timezone': 'Invalid/Zone'}
    elif case == 'invalid_employee_reference': provider.data = {**provider.data, 'employee_id': 'invalid'}
    else: db.query(ServiceSpecialistEligibility).one().active = False
    db.flush()
    with native_writer(db, user, branch):
        assert service_options(db, user, catalog[2][1])['specialists'] == []


def test_search_and_explicit_invalid_context_never_fall_back(db, scenario):
    user, branch, catalog, basket = scenario
    with native_writer(db, user, branch):
        assert provider_options(db, user, search='no-match')['providers'] == []
        assert len(provider_options(db, user, search='Specialist')['providers']) == 1
        with pytest.raises(HTTPException) as error:
            provider_options(db, user, selected='invalid')
        assert error.value.status_code == 403


def test_incomplete_installation_fails_closed(db, scenario, monkeypatch):
    user, branch, catalog, basket = scenario
    monkeypatch.setattr('app.apps.srm.service_checkout_options.installation_ready', lambda db: False)
    with native_writer(db, user, branch), pytest.raises(HTTPException) as error:
        service_options(db, user, catalog[2][1])
    assert error.value.status_code == 503


def test_exact_context_anchor_filters_and_role_revocation(db, scenario):
    user, branch, catalog, basket = scenario
    provider = db.query(IndustryRecord).filter_by(kind='resource').one()
    activation = PackActivation(company_id=1, pack_key='hospital', state='active')
    db.add(activation); db.flush()
    context = PackContext(company_id=1, branch_id=branch, activation_id=activation.id, pack_key='hospital', pack_version=1, state='active')
    db.add(context); db.flush()
    grant = PackUserGrant(company_id=1, branch_id=branch, context_id=context.id, user_id=user.id, role='receptionist')
    db.add(grant)
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context.id,
        resource_table=SRMProduct.__tablename__, resource_key=str(catalog[2][1])))
    db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
        resource_table=IndustryRecord.__tablename__, resource_key=str(provider.id)))
    db.flush()
    with native_writer(db, user, branch):
        # The legacy policy and eligibility must never bleed into this context.
        result = service_options(db, user, catalog[2][1], selected=str(context.id))
        assert result['policy'] is None and result['specialists'] == []
        assert len(provider_options(db, user, selected=str(context.id))['providers']) == 1
        grant.role = 'doctor'; db.flush()
        with pytest.raises(HTTPException) as error:
            provider_options(db, user, selected=str(context.id))
        assert error.value.status_code == 403
        grant.role = 'receptionist'; grant.active = False; db.flush()
        with pytest.raises(HTTPException):
            service_options(db, user, catalog[2][1], selected=str(context.id))


def test_provider_limit_truthfully_reports_more(db, scenario):
    user, branch, catalog, basket = scenario
    provider = db.query(IndustryRecord).filter_by(kind='resource').one()
    for index in range(101):
        db.add(IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title=f'Provider {index:03}',
            request_id=f'options-limit-{index}', created_by=user.id, status='active', data=dict(provider.data)))
    db.flush()
    with native_writer(db, user, branch):
        result = provider_options(db, user)
        assert len(result['providers']) == 100 and result['has_more'] is True


def test_specialist_search_finds_eligible_match_beyond_first_hundred(db, scenario):
    user, branch, catalog, basket = scenario
    provider = db.query(IndustryRecord).filter_by(kind='resource').one()
    policy = db.query(ServiceBookingPolicy).one()
    target_id = None
    for index in range(102):
        row = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title=f'ZZ Provider {index:03}',
            request_id=f'options-search-{index}', created_by=user.id, status='active', data=dict(provider.data))
        db.add(row); db.flush()
        db.add(ServiceSpecialistEligibility(organization_id=1, branch_id=branch, booking_policy_id=policy.id,
            service_product_id=policy.service_product_id, provider_resource_id=row.id))
        target_id = row.id
    db.flush()
    with native_writer(db, user, branch):
        first_page = service_options(db, user, catalog[2][1])
        assert len(first_page['specialists']) == 100 and first_page['has_more'] is True
        assert target_id not in {row['provider_resource_id'] for row in first_page['specialists']}
        result = service_options(db, user, catalog[2][1], search='ZZ Provider 101')
        assert [row['provider_resource_id'] for row in result['specialists']] == [target_id]
        assert result['has_more'] is False
        with pytest.raises(HTTPException) as error:
            service_options(db, user, catalog[2][1], search='x' * 101)
        assert error.value.status_code == 422


def test_static_options_api_passes_explicit_header_and_returns_metadata(db, scenario):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_db, get_current_user
    from app.apps.srm.service_checkout_options_api import router
    user, branch, catalog, basket = scenario
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_db] = lambda: db
    application.dependency_overrides[get_current_user] = lambda: user
    with native_writer(db, user, branch), TestClient(application) as client:
        response = client.get('/srm/service-checkout/options', params={'service_id': catalog[2][1]})
        assert response.status_code == 200, response.text
        assert response.json()['specialists'][0]['eligibility_revision'] == 1
        response = client.get('/srm/service-checkout/options', params={'service_id': catalog[2][1], 'search': 'no-matching-provider'})
        assert response.status_code == 200 and response.json()['specialists'] == []
        assert client.get('/srm/service-checkout/options', params={'service_id': catalog[2][1], 'search': 'x' * 101}).status_code == 422
        response = client.get('/srm/service-checkout/options/providers', headers={'X-Suite-Pack-Context': 'invalid'})
        assert response.status_code == 403
