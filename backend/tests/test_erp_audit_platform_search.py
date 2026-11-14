"""Literal searches must not widen platform owner record selection."""
import pytest
from app.platform_owner.models import PlatformSignupRequest as Signup, PlatformTenant, PlatformEvent
from tests.test_public_signup import platform_store, platform_headers


def signup(store, number, **values):
    row = Signup(applicant_type='company', name='Ordinary applicant',
                 company_name='Ordinary company', email=f'ordinary-{number}@example.test',
                 phone=str(9000000000 + number), phone_country_code='+91', **values)
    store.add(row)
    store.flush()
    return row


@pytest.mark.parametrize('literal', ['%', '_', '\\', '/'])
@pytest.mark.parametrize('field', ['name', 'company_name', 'email', 'phone', 'campaign'])
def test_signup_search_is_literal(client, platform_store, platform_headers, literal, field):
    target = signup(platform_store, 1)
    other = signup(platform_store, 2)
    needle = 'Audit' + literal + 'Needle'
    setattr(target, field, needle)
    setattr(other, field, 'AuditXNeedle')
    platform_store.commit()
    response = client.get('/api/v1/platform/signups', headers=platform_headers,
                          params={'search': needle.swapcase(), 'status': 'all'})
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert [r['id'] for r in response.json()['items']] == [target.id]
    if field in ['name', 'company_name', 'email']:
        response = client.get('/api/v1/auth/signup-requests', headers=platform_headers,
                              params={'search': needle.swapcase(), 'status': 'all'})
        assert response.status_code == 200, response.text
        assert response.json()['total'] == 1
        assert [r['id'] for r in response.json()['items']] == [target.id]
        response = client.get('/api/v1/platform/search', headers=platform_headers,
                              params={'q': needle.swapcase()})
        assert response.status_code == 200, response.text
        assert [r['id'] for r in response.json()['signups']] == [target.id]


@pytest.mark.parametrize('literal', ['%', '_', '\\', '/'])
@pytest.mark.parametrize('field', ['name', 'admin_email'])
def test_customer_search_is_literal(client, platform_store, platform_headers, literal, field):
    rows = []
    needle = 'Audit' + literal + 'Needle'
    for number in [1, 2]:
        source = signup(platform_store, number)
        row = PlatformTenant(signup_id=source.id, company_id=number, name='Ordinary tenant',
                             admin_email=f'ordinary-{number}@example.test')
        setattr(row, field, needle if number == 1 else 'AuditXNeedle')
        rows.append(row)
        platform_store.add(row)
    platform_store.commit()
    response = client.get('/api/v1/platform/customers', headers=platform_headers,
                          params={'search': needle.swapcase()})
    assert response.status_code == 200, response.text
    assert [r['id'] for r in response.json()] == [rows[0].id]
    if field == 'name':
        response = client.get('/api/v1/platform/search', headers=platform_headers,
                              params={'q': needle.swapcase()})
        assert response.status_code == 200, response.text
        assert [r['id'] for r in response.json()['customers']] == [rows[0].id]


@pytest.mark.parametrize('literal', ['%', '_', '\\', '/'])
def test_event_search_is_literal(client, platform_store, platform_headers, literal):
    needle = 'audit' + literal + 'event'
    row = PlatformEvent(action=needle, entity='test')
    platform_store.add_all([row, PlatformEvent(action='auditXevent', entity='test')])
    platform_store.commit()
    response = client.get('/api/v1/platform/events', headers=platform_headers,
                          params={'search': needle.upper()})
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert [r['id'] for r in response.json()['items']] == [row.id]


@pytest.mark.parametrize('literal', ['%', '_', '\\', '/'])
def test_literal_search_keeps_assigned_only_scope(client, platform_store, literal):
    from tests.test_platform_portal import staff_login
    actor, headers = staff_login(client, platform_store, 'sales', True)
    needle = 'Scoped' + literal + 'Needle'
    allowed = signup(platform_store, 1, assigned_to=actor.id)
    hidden = signup(platform_store, 2)
    for number, row in enumerate([allowed, hidden], 1):
        row.name = needle
        platform_store.add(PlatformTenant(signup_id=row.id, company_id=number,
            name=needle, admin_email=row.email,
            assigned_to=actor.id if number == 1 else None))
    platform_store.commit()
    for path in ['/api/v1/platform/signups', '/api/v1/auth/signup-requests']:
        response = client.get(path, headers=headers, params={'search': needle, 'status': 'all'})
        assert response.status_code == 200, response.text
        assert response.json()['total'] == 1
        assert [r['id'] for r in response.json()['items']] == [allowed.id]
    response = client.get('/api/v1/platform/search', headers=headers, params={'q': needle})
    assert response.status_code == 200, response.text
    assert [r['id'] for r in response.json()['signups']] == [allowed.id]
    expected = platform_store.query(PlatformTenant).filter_by(signup_id=allowed.id).one().id
    assert [r['id'] for r in response.json()['customers']] == [expected]
    response = client.get('/api/v1/platform/customers', headers=headers, params={'search': needle})
    assert response.status_code == 200, response.text
    assert [r['id'] for r in response.json()] == [expected]
    assert client.get('/api/v1/platform/events', headers=headers, params={'search': needle}).status_code == 403
