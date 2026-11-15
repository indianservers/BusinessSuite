"""The registered HRMS route supports assigned staff without Sales access."""
from datetime import timedelta

from app.core.security import create_access_token
from app.branches.migration import backfill
from tests.test_planned_services import plans, START


def test_registered_planned_services_route_intersects_auth_employee_and_assignment(client, plans):
    row = plans.appointment()
    backfill(plans.db.connection(), 1)
    plans.db.commit()
    actor = plans.users['specialist']
    employee = plans.employees['specialist']
    path = f'/api/v1/employees/{employee.id}/planned-services'
    params = {'from_at': (START - timedelta(days=1)).isoformat(),
              'until_at': (START + timedelta(days=1)).isoformat()}
    headers = {'Authorization': 'Bearer ' + create_access_token(actor.id),
               'X-Suite-Organization': '1', 'X-Suite-Branch': str(employee.branch_id)}
    assert client.get(path, params=params).status_code == 403
    response = client.get(path, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert [item['appointment_id'] for item in response.json()['items']] == [row.id]
    assert 'PRIVATE CUSTOMER' not in response.text
    assert 'PRIVATE NOTE' not in response.text
    other = plans.employees['coworker']
    denied = client.get(f'/api/v1/employees/{other.id}/planned-services', params=params, headers=headers)
    assert denied.status_code in {403, 404}


def test_conflicting_pack_selectors_do_not_fall_back_to_legacy(client, plans):
    backfill(plans.db.connection(), 1)
    plans.db.commit()
    actor = plans.users['specialist']
    employee = plans.employees['specialist']
    headers = {'Authorization': 'Bearer ' + create_access_token(actor.id),
               'X-Suite-Organization': '1', 'X-Suite-Branch': str(employee.branch_id),
               'X-Suite-Pack-Context': '7'}
    response = client.get(f'/api/v1/employees/{employee.id}/planned-services', headers=headers,
        params={'from_at': START.isoformat(), 'until_at': (START + timedelta(days=1)).isoformat(),
                'pack_context_id': 8})
    assert response.status_code == 403


def test_global_schedule_route_is_registered_before_employee_id_and_filters_server_side(client, plans):
    own = plans.appointment()
    other = plans.appointment([plans.provider(plans.employees['coworker'])])
    other.data = {**other.data, 'service_id': 99, 'service_name': 'Hidden coworker service'}
    backfill(plans.db.connection(), 1); plans.db.commit()
    actor = plans.users['specialist']
    headers = {'Authorization': 'Bearer ' + create_access_token(actor.id),
               'X-Suite-Organization': '1', 'X-Suite-Branch': str(plans.branches[0].id)}
    params = {'from_at': START.isoformat(), 'until_at': (START + timedelta(days=1)).isoformat(), 'limit': 1}
    path = '/api/v1/employees/planned-services'
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert [row['appointment_id'] for row in response.json()['items']] == [own.id]
    assert 'Hidden coworker' not in response.text
    filtered = client.get(path, headers=headers, params={**params, 'service_id': 99})
    assert filtered.status_code == 200 and not filtered.json()['items']
    assert client.get(path, headers=headers, params={**params, 'employee_id': -1}).status_code == 422
