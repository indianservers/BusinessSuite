"""Cross-employee schedule filters are authorized before paging/descriptors."""
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.access.models import AccessPolicy
from app.branches.service import context
from app.business_packs.access import resolve_context
from app.services.planned_services import scheduled_services
from tests.test_planned_services import plans, START


def read(p, **kwargs):
    actor = p.users['specialist']
    branch = kwargs.pop('branch_ctx', None) or context(p.db, actor, 1, p.branches[0].id)
    return scheduled_services(p.db, actor, branch, kwargs.pop('from_at', START - timedelta(days=1)),
                              kwargs.pop('until_at', START + timedelta(days=2)), **kwargs)


def organization(p, scope='organization'):
    policy = AccessPolicy(company_id=1, user_id=p.users['specialist'].id, status='active',
        grants={'hrms': {'enabled': True, 'permissions': ['timesheet_view'], 'actions': ['view'], 'scope': scope}})
    p.db.add(policy); p.db.commit()
    return policy


def test_own_projection_and_descriptors_exclude_other_workforce_and_private_data(plans):
    p = plans
    own = p.appointment()
    p.appointment([p.provider(p.employees['coworker'])])
    p.appointment([p.provider(p.employees['foreign'])], branch=p.branches[2].id)
    p.db.commit()
    result = read(p)
    assert [row['appointment_id'] for row in result['items']] == [own.id]
    assert result['items'][0]['employee_id'] == p.employees['specialist'].id
    assert [row['id'] for row in result['filter_options']['employees']] == [p.employees['specialist'].id]
    assert result['filter_options']['services'] == [{'id': 17, 'name': 'Scheduled consultation'}]
    assert 'PRIVATE' not in str(result)
    assert not read(p, employee_id=p.employees['coworker'].id)['items']


def test_filters_apply_before_pagination_but_descriptors_cover_authorized_range(plans):
    p = plans
    organization(p)
    p.appointment()
    coworker = p.appointment([p.provider(p.employees['coworker'])])
    coworker.data = {**coworker.data, 'service_id': 29, 'service_name': 'Second service'}
    p.db.commit()
    result = read(p, employee_id=p.employees['coworker'].id, service_id=29, limit=1)
    assert [row['appointment_id'] for row in result['items']] == [coworker.id]
    assert result['next_cursor'] is None
    assert len(result['filter_options']['employees']) == 2
    assert len(result['filter_options']['services']) == 2
    assert not read(p, service_id=999)['items']


def test_shared_appointment_pages_each_employee_once_without_alias_duplicates(plans):
    p = plans
    organization(p)
    alias = p.provider()
    row = p.appointment([p.default_provider, alias, p.provider(p.employees['coworker'])])
    p.db.commit()
    first = read(p, limit=1)
    second = read(p, limit=1, cursor=first['next_cursor'])
    assert [page['items'][0]['appointment_id'] for page in (first, second)] == [row.id, row.id]
    assert {page['items'][0]['employee_id'] for page in (first, second)} == {p.employees['specialist'].id, p.employees['coworker'].id}
    assert second['next_cursor'] is None
    with pytest.raises(HTTPException) as error:
        read(p, limit=1, service_id=17, cursor=first['next_cursor'])
    assert error.value.status_code == 422


def test_team_scope_and_permission_revocation_apply_to_global_view(plans):
    p = plans
    coworker = p.employees['coworker']
    coworker.reporting_manager_id = p.employees['specialist'].id
    p.appointment(); p.appointment([p.provider(coworker)])
    p.appointment([p.provider(p.employees['reception'])])
    policy = organization(p, 'team')
    result = read(p)
    assert {row['employee_id'] for row in result['items']} == {coworker.id, p.employees['specialist'].id}
    policy.grants = {'hrms': {'enabled': True, 'permissions': ['timesheet_view'], 'actions': ['view'], 'scope': 'own'}}
    p.db.commit()
    assert {row['employee_id'] for row in read(p)['items']} == {p.employees['specialist'].id}
    policy.status = 'suspended'; p.db.commit()
    with pytest.raises(HTTPException) as error:
        read(p)
    assert error.value.status_code == 403


def test_pack_ownership_filters_both_rows_and_descriptors(plans):
    p = plans
    hospital, grant = p.pack()
    own = p.appointment(); p.anchor(own, hospital); p.anchor(p.default_provider, hospital)
    restaurant, _ = p.pack('restaurant', 'chef')
    other_provider = p.provider(); p.anchor(other_provider, restaurant)
    other = p.appointment([other_provider]); p.anchor(other, restaurant)
    other.data = {**other.data, 'service_id': 72, 'service_name': 'Private restaurant service'}
    p.db.commit()
    actor = p.users['specialist']
    branch = context(p.db, actor, 1, p.branches[0].id)
    pack = resolve_context(p.db, actor, branch, hospital.id)
    result = read(p, pack_scope=pack)
    assert [row['appointment_id'] for row in result['items']] == [own.id]
    assert result['filter_options']['services'] == [{'id': 17, 'name': 'Scheduled consultation'}]
    assert 'Private restaurant' not in str(result)
    grant.active = False; p.db.commit()
    with pytest.raises(HTTPException):
        read(p, pack_scope=pack)


def test_descriptor_caps_are_explicit_and_not_derived_from_first_page(plans):
    p = plans
    for ident in range(201):
        row = p.appointment()
        row.data = {**row.data, 'service_id': ident + 1, 'service_name': f'Service {ident}'}
    p.db.commit()
    result = read(p, limit=1)
    assert len(result['items']) == 1
    assert len(result['filter_options']['services']) == 200
    assert result['filter_options']['services_complete'] is False
    assert result['filter_options']['employees_complete'] is True


@pytest.mark.parametrize('filters', [{'employee_id': True}, {'service_id': 0}, {'service_id': '17'}, {'limit': 101}, {'statuses': ['bogus']}])
def test_invalid_global_filters_fail_closed(plans, filters):
    with pytest.raises(HTTPException) as error:
        read(plans, **filters)
    assert error.value.status_code == 422


def test_global_schedule_includes_employee_categories_and_room_labels(plans):
    p = plans
    room = p.provider(resource_type='room'); room.title = 'Consultation room'
    p.employees['specialist'].work_categories = ['Consultant']
    p.appointment([p.default_provider, room]);p.db.commit()
    item = read(p)['items'][0]
    assert item['employee_categories'] == ['Consultant']
    assert item['resources'] == [{'id': room.id, 'name': 'Consultation room', 'resource_type': 'room'}]
    assert not any(key in str(item) for key in ['PRIVATE', 'customer_name', 'payment_requests'])
