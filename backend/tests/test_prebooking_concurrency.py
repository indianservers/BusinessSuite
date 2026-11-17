"""Real independent HTTP requests reserve the same shared appointment capacity."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from tests.test_pms_workflow_postgresql import live, race
from tests.srm_test_utils import seed_invoice_parties
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInvoice, SRMReceipt


def test_concurrent_reservations_have_one_winner_and_no_money(live):
    with live.factory() as session:
        seed_invoice_parties(session)
        session.commit()
    service = live.client.post('/api/v1/srm/inventory/items', headers=live.oh, json={
        'sku':'RESERVATION-RACE', 'item_name':'Concurrent service', 'product_type':'service',
        'track_inventory':False, 'sales_rate':100, 'gst_rate':0})
    assert service.status_code == 201, service.text
    provider = live.client.post('/api/v1/srm/industry/resources', headers=live.oh, json={
        'request_id':str(uuid4()), 'title':'Concurrent provider', 'resource_type':'provider',
        'timezone':'UTC', 'opens':'00:00', 'closes':'23:59', 'weekdays':list(range(7))})
    assert provider.status_code == 201, provider.text
    start = (datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    def reserve():
        return live.client.post('/api/v1/srm/industry/appointments', headers=live.oh, json={
            'request_id':str(uuid4()), 'title':'Concurrent reservation', 'customer_id':101,
            'service_id':service.json()['id'], 'resource_ids':[provider.json()['id']],
            'starts_at':start.isoformat(), 'duration_minutes':30})
    responses = race(reserve, reserve)
    assert sorted(response.status_code for response in responses) == [201,409], [response.text for response in responses]
    with live.factory() as session:
        assert session.query(IndustryRecord).filter_by(kind='appointment').count() == 1
        assert session.query(SRMInvoice).count() == session.query(SRMReceipt).count() == 0


def test_concurrent_room_capacity_two_has_exactly_two_winners(live):
    with live.factory() as session:
        seed_invoice_parties(session); session.commit()
    service=live.client.post('/api/v1/srm/inventory/items',headers=live.oh,json={
        'sku':'CAPACITY-RACE','item_name':'Capacity service','product_type':'service','track_inventory':False,'sales_rate':100,'gst_rate':0})
    assert service.status_code==201,service.text
    def resource(kind, title, capacity=1):
        response=live.client.post('/api/v1/srm/industry/resources',headers=live.oh,json={
            'request_id':str(uuid4()),'title':title,'resource_type':kind,'capacity':capacity,
            'timezone':'UTC','opens':'00:00','closes':'23:59','weekdays':list(range(7))})
        assert response.status_code==201,response.text
        return response.json()['id']
    room=resource('room','Capacity race room',2)
    providers=[resource('provider','Capacity race provider '+str(i)) for i in range(3)]
    start=(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    def reserve(provider):
        return live.client.post('/api/v1/srm/industry/appointments',headers=live.oh,json={
            'request_id':str(uuid4()),'title':'Capacity race','customer_id':101,'service_id':service.json()['id'],
            'resource_ids':[provider,room],'starts_at':start.isoformat(),'duration_minutes':30})
    responses=race(*[lambda provider=provider:reserve(provider) for provider in providers])
    assert sorted(response.status_code for response in responses)==[201,201,409],[response.text for response in responses]
