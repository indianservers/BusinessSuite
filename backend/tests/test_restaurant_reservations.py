from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, BASE
from tests.test_restaurant_kitchen import post, staff


def setup(client, case):
    table = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Reserve', 'capacity': 4})
    body = {'request_key': str(uuid4()), 'table_id': table['id'], 'expected_table_revision': table['revision'],
        'party_size': 3, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), 'duration_minutes': 60}
    return table, body


def test_reservation_native_source_overlap_retry_cancel_and_rebook(client, db, unpaid):
    from app.apps.srm.industry_models import IndustryRecord
    table, body = setup(client, unpaid)
    row = post(client, unpaid['headers'], '/reservations', body)
    assert row['party_size'] == 3 and row['table_id'] == table['id'] and row['state'] == 'booked'
    assert post(client, unpaid['headers'], '/reservations', body) == row
    native = db.get(IndustryRecord, row['id'])
    assert native.kind == 'restaurant_reservation' and native.invoice_id is None and native.project_id is None
    assert not {'service_id', 'provider_id', 'currency', 'unit_price'} & native.data.keys()
    post(client, unpaid['headers'], '/reservations', {**body, 'request_key': str(uuid4())}, 409)
    cancel = {'request_key': str(uuid4()), 'expected_revision': row['revision'], 'status': 'cancelled', 'reason': 'Changed plans'}
    changed = post(client, unpaid['headers'], f"/reservations/{row['id']}/transition", cancel, 200)
    assert changed['state'] == 'cancelled'
    assert post(client, unpaid['headers'], f"/reservations/{row['id']}/transition", cancel, 200) == changed
    post(client, unpaid['headers'], '/reservations', {**body, 'request_key': str(uuid4())})
    denied = client.post('/api/v1/srm/industry/records/'+str(row['id'])+'/transition', headers=unpaid['headers'], json={'expected_revision': changed['revision'], 'status': 'in_service'})
    assert denied.status_code == 403, denied.text
    invoice = client.post('/api/v1/srm/industry/records/'+str(row['id'])+'/invoice', headers=unpaid['headers'], json={'expected_revision': changed['revision']})
    assert invoice.status_code == 409, invoice.text
    assert db.get(IndustryRecord, row['id']).invoice_id is None


@pytest.mark.parametrize('fault', ['capacity', 'revision', 'inactive', 'past', 'chef', 'server'])
def test_invalid_reservations_fail_before_new_operational_records(client, db, unpaid, fault):
    from app.business_packs.restaurant.models import RestaurantTable
    from app.apps.srm.industry_models import IndustryRecord
    table, body = setup(client, unpaid)
    headers = unpaid['headers']
    if fault == 'capacity': body['party_size'] = 5
    if fault == 'revision': body['expected_table_revision'] += 1
    if fault == 'inactive':
        db.get(RestaurantTable, table['id']).active = False
        db.commit()
    if fault == 'past': body['starts_at'] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    if fault in ('chef', 'server'): headers, _ = staff(db, unpaid, fault)
    before = db.query(IndustryRecord).count()
    post(client, headers, '/reservations', body, 403 if fault in ('chef', 'server') else 409)
    assert db.query(IndustryRecord).count() == before


def test_reschedule_revision_retry_seating_and_elapsed_no_show(client, db, unpaid, monkeypatch):
    from app.business_packs.restaurant import reservations
    table, payload = setup(client, unpaid)
    row = post(client, unpaid['headers'], '/reservations', payload)
    changed = {**payload, 'request_key': str(uuid4()), 'expected_revision': row['revision'], 'starts_at': (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()}
    response = client.put(BASE + f"/reservations/{row['id']}", headers=unpaid['headers'], json=changed)
    assert response.status_code == 200, response.text
    assert client.put(BASE + f"/reservations/{row['id']}", headers=unpaid['headers'], json=changed).json() == response.json()
    post(client, unpaid['headers'], f"/reservations/{row['id']}/transition", {'request_key': str(uuid4()), 'expected_revision': row['revision'], 'status': 'no_show'}, 409)
    row = response.json()
    post(client, unpaid['headers'], f"/reservations/{row['id']}/transition", {'request_key': str(uuid4()), 'expected_revision': row['revision'], 'status': 'no_show'}, 409)
    class Later(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.now(timezone.utc) + timedelta(days=4)
    monkeypatch.setattr(reservations, 'datetime', Later)
    absent = post(client, unpaid['headers'], f"/reservations/{row['id']}/transition", {'request_key': str(uuid4()), 'expected_revision': row['revision'], 'status': 'no_show'}, 200)
    assert absent['state'] == 'no_show'
    monkeypatch.undo()
    replacement = post(client, unpaid['headers'], '/reservations', {**payload, 'request_key': str(uuid4())})
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, table_id=table['id'], expected_table_revision=table['revision']))
    seated = post(client, unpaid['headers'], f"/reservations/{replacement['id']}/transition", {'request_key': str(uuid4()), 'expected_revision': replacement['revision'], 'status': 'seated', 'order_id': order['id']}, 200)
    assert seated['state'] == 'seated' and seated['order_id'] == order['id']
