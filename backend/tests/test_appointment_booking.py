from datetime import datetime, timedelta, timezone
import re
import os
import pytest
from tests.test_industry_operations import business, stylist, booking, post
from tests.test_contact_directory import directory_identity
from app.apps.srm.industry_models import IndustryRecord

ROOT = '/api/v1/srm/industry/booking-links'


def link(client, h, buyer, service, resource):
    response = client.post(ROOT, headers=h, json={'customer_id': buyer.id, 'service_id': service.id, 'resource_ids': [resource['id']], 'duration_minutes': 30})
    assert response.status_code == 201, response.text
    return response.json()


def test_public_booking_creates_native_appointment_once_and_hides_private_data(client, db, business):
    h, buyer, _, service = business
    provider = stylist(client, h)
    public = link(client, h, buyer, service, provider)
    day = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    page = client.get(public['path'], params={'day': day})
    assert page.status_code == 200, page.text
    assert 'name="slot"' in page.text and buyer.name not in page.text
    assert 'no-store' in page.headers['cache-control']
    slots = re.findall(r'<option value="([^"]+)">\d\d:\d\d</option>', page.text)
    assert slots
    booked = client.post(public['path'] + '/book', data={'slot': slots[0]})
    assert booked.status_code == 200, booked.text
    assert 'confirmed' in booked.text
    rows = db.query(IndustryRecord).filter_by(kind='appointment', customer_id=buyer.id).all()
    assert len(rows) == 1 and rows[0].data['resource_ids'] == [provider['id']]
    assert rows[0].status == 'booked' and rows[0].invoice_id is None
    replay = client.post(public['path'] + '/book', data={'slot': slots[-1]})
    assert replay.status_code == 200, replay.text
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 1
    assert 'confirmed' in client.get(public['path']).text


def test_staff_can_revoke_and_public_links_expire(client, db, business):
    from app.shared.models import ServicePolicy
    h, buyer, _, service = business
    provider = stylist(client, h)
    public = link(client, h, buyer, service, provider)
    response = client.post(ROOT + f'/{public["id"]}/revoke', headers=h)
    assert response.status_code == 200, response.text
    assert client.get(public['path']).status_code == 404
    public = link(client, h, buyer, service, provider)
    policy = db.get(ServicePolicy, public['id'])
    policy.values_json = {**policy.values_json, 'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    db.commit()
    assert client.get(public['path']).status_code == 404
    assert client.get(public['path'].replace('/shared/', '/other-workspace/')).status_code == 404


def test_reception_conflicts_and_changed_prices_are_revalidated(client, db, business):
    h, buyer, _, service = business
    provider = stylist(client, h)
    public = link(client, h, buyer, service, provider)
    day = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    page = client.get(public['path'], params={'day': day})
    choices = re.findall(r'<option value="([^"]+)">\d\d:\d\d</option>', page.text)
    assert choices
    data = booking(client, h, buyer, service, provider)
    post(client, h, '/appointments', {**data, 'starts_at': choices[0]})
    rejected = client.post(public['path'] + '/book', data={'slot': choices[0]})
    assert rejected.status_code == 409, rejected.text
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 1
    assert choices[0] not in client.get(public['path'], params={'day': day}).text
    service.sales_rate = 700; db.commit()
    assert client.get(public['path'], params={'day': day}).status_code == 404
    assert client.post(public['path'] + '/book', data={'slot': choices[-1]}).status_code == 404


def test_link_owner_deactivation_and_raw_token_storage(client, db, business):
    from app.shared.models import ServicePolicy
    from app.models.user import User
    from app.models.audit import AuditLog
    h, buyer, project, service = business
    public = link(client, h, buyer, service, stylist(client, h))
    token = public['path'].split('/')[-1]
    policy = db.get(ServicePolicy, public['id'])
    assert token not in str(policy.values_json) and token not in policy.scope_key
    assert client.get(public['path']).status_code == 200
    assert not any(token in (row.endpoint or '') for row in db.query(AuditLog).all())
    owner = db.get(User, policy.values_json['owner_id']); owner.is_active = False; db.commit()
    assert client.get(public['path']).status_code == 404
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 0


def test_booking_links_require_manage_permission(client, db, business):
    from tests.test_settings_hub import actor
    from test_identity_utils import attach_workflow_branch
    h, buyer, _, service = business
    provider = stylist(client, h)
    public = link(client, h, buyer, service, provider)
    reader, user = actor(db, 'public-booking-view-only', permissions=['srm_view'])
    branch = attach_workflow_branch(db, user); db.commit()
    reader = {**reader, 'X-Suite-Branch': str(branch.id)}
    assert client.post(ROOT, headers=reader, json={'customer_id': buyer.id, 'service_id': service.id, 'resource_ids': [provider['id']]}).status_code == 403
    assert client.post(ROOT + f'/{public["id"]}/revoke', headers=reader).status_code == 403


def test_public_booking_rate_limit_is_durable(client, db, business, monkeypatch):
    from app.core import request_limits
    h, buyer, _, service = business
    public = link(client, h, buyer, service, stylist(client, h))
    consume = request_limits.consume
    monkeypatch.setattr(request_limits, 'consume', lambda db, specs: consume(db, [(key, 2, seconds) for key, _, seconds in specs]))
    assert client.get(public['path']).status_code == 200
    assert client.get(public['path']).status_code == 200
    limited = client.get(public['path'])
    assert limited.status_code == 429, limited.text
    assert int(limited.headers['retry-after']) > 0


def test_public_booking_route_selects_verified_tenant_without_a_login(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4
    from app.core.config import settings
    from app.core.middleware import tenant_database
    from app.db.tenant import current_tenant
    marker = str(uuid4())
    calls, messages = [], []
    monkeypatch.setattr(settings, 'TENANT_DATABASES_ENABLED', True)
    def lookup(value):
        calls.append(value)
        return SimpleNamespace(tenant_uuid=marker, workspace_code='CLINIC', company_id=1)
    monkeypatch.setattr(tenant_database, 'lookup_route', lookup)
    async def app(scope, receive, send):
        assert current_tenant.get().tenant_uuid == marker
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})
    async def receive(): return {'type': 'http.request', 'body': b''}
    async def send(value): messages.append(value)
    scope = {'type': 'http', 'method': 'GET', 'path': f'/api/v1/public/appointments/{marker}/opaque-token', 'headers': [], 'query_string': b''}
    previous = current_tenant.get()
    asyncio.run(tenant_database.TenantDatabaseMiddleware(app)(scope, receive, send))
    assert calls == [marker] and messages[0]['status'] == 200
    assert current_tenant.get() is previous


@pytest.mark.skipif(os.environ.get('RUN_APPOINTMENT_BROWSER_QA') != '1', reason='Explicit browser workflow opt-in')
def test_public_appointment_workflow_in_real_browsers(client, db, business):
    from app.models.company import Branch
    from tests.workflow_browser_utils import run_browser
    h, buyer, _, service = business
    provider = post(client, h, '/resources', {'request_id': __import__('uuid').uuid4().hex, 'title': 'Dr Booking Example', 'resource_type': 'provider', 'weekdays': list(range(7))})
    branch = db.query(Branch).filter_by(company_id=1).first()
    configured = client.put('/api/v1/access/settings/business-profile/configuration', headers=h, json={'version': 0, 'values': {'business_type': 'hospital'}})
    assert configured.status_code == 200, configured.text
    run_browser(client, db, 'test-public-appointment-workflow.cjs', {
        'BOOKING_TOKEN': h['Authorization'].split(' ', 1)[1], 'BOOKING_BRANCH': str(branch.id),
        'BOOKING_CUSTOMER': buyer.name, 'BOOKING_SERVICE': service.item_name, 'BOOKING_PROVIDER': provider['title'],
        'BOOKING_DAY': (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat(),
    }, timeout_seconds=240)
    assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 0
