from datetime import datetime, timezone, timedelta
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, BASE, send_items
from tests.test_restaurant_kitchen import post, staff


def test_daily_summary_counts_real_orders_and_tickets_without_financial_payload(client, db, unpaid):
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    send_items(client, case, order)
    today = datetime.now(timezone.utc).date()
    response = client.get(BASE + '/daily-summary', params={'day': str(today), 'timezone_name': 'UTC'}, headers=case['headers'])
    assert response.status_code == 200, response.text
    assert response.json() == {'day': str(today), 'timezone': 'UTC', 'orders_opened': 1, 'orders': {'open': 1},
        'tickets_created': 1, 'tickets': {'queued': 1}, 'reservations_starting': 0, 'reservations': {}}
    yesterday = client.get(BASE + '/daily-summary', params={'day': str(today - timedelta(days=1)), 'timezone_name': 'UTC'}, headers=case['headers'])
    assert yesterday.status_code == 200 and yesterday.json()['orders_opened'] == 0
    assert client.get(BASE + '/daily-summary', params={'day': str(today), 'timezone_name': 'invalid/zone'}, headers=case['headers']).status_code == 422


def test_chef_and_server_cannot_read_manager_summary(client, db, unpaid):
    from tests.test_business_pack_http_integration import grant
    context = None
    for role in ('chef', 'server'):
        headers, actor = staff(db, unpaid, role)
        context, _ = grant(db, actor, unpaid['branch'], 'hospital', 'doctor', context)
        response = client.get(BASE + '/daily-summary', params={'day': '2026-11-15'}, headers=headers)
        assert response.status_code == 403, response.text
        for kind in ('appointment', 'site_diary'):
            denied = client.get('/api/v1/srm/industry/records', params={'kind': kind}, headers=headers)
            assert denied.status_code == 403, denied.text


def test_summary_does_not_count_another_pack_appointments_for_same_user(client, db, unpaid):
    from app.apps.srm.industry_models import IndustryRecord
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from tests.test_business_pack_http_integration import grant
    from tests.test_srm_native_transaction_operations import native_writer
    context, _ = grant(db, unpaid['manager'], unpaid['branch'], 'hospital', 'hospital_manager')
    with native_writer(db, unpaid['manager'], unpaid['branch']):
        scope = resolve_context(db, unpaid['manager'], db.info['branch_context'], context.id)
        cleanup = install(db, scope, policy=native_srm_policy('hospital').policy)
        try:
            starts = datetime.now(timezone.utc)
            row = IndustryRecord(organization_id=1, branch_id=unpaid['branch'], kind='appointment', title='Private hospital record',
                status='booked', request_id='00000000-0000-4000-8000-000000000001', starts_at=starts, ends_at=starts + timedelta(minutes=30),
                data={}, created_by=unpaid['manager'].id)
            db.add(row)
            db.commit()
        finally:
            cleanup()
    response = client.get(BASE + '/daily-summary', params={'day': str(starts.date()), 'timezone_name': 'UTC'}, headers=unpaid['headers'])
    assert response.status_code == 200, response.text
    assert response.json()['reservations_starting'] == 0 and response.json()['reservations'] == {}
    assert 'Private hospital record' not in response.text
