from uuid import uuid4
import pytest
from app.apps.srm.models import SRMReceipt
from app.business_packs.restaurant.models import RestaurantCommand, RestaurantServiceOrder
from tests.test_restaurant_settlement import settlement, unpaid, scenario, catalog, directory_identity, bill_input, post, BASE


def serve(client, case):
    ticket = case['ticket']
    for action in ('prepare', 'ready', 'serve'):
        ticket = post(client, case['headers'], f"/tickets/{ticket['id']}/{action}", {
            'request_key': str(uuid4()), 'expected_revision': ticket['revision']}, status=200)


@pytest.mark.parametrize('serve_first', [True, False])
def test_actual_shared_payment_closes_only_fully_paid_served_tab(client, db, settlement, serve_first):
    case = settlement
    bill = post(client, case['headers'], f"/tabs/{case['order']['id']}/bill", bill_input(case))
    if serve_first:
        serve(client, case)
    root = bill['checkout']
    payload = {'expected_revision': root['revision'], 'pos_session_id': case['register'],
        'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}}
    path = f"/api/v1/srm/service-checkout/{root['id']}/payments"
    response = client.post(path, headers=case['headers'], json=payload)
    assert response.status_code == 201, response.text
    if not serve_first:
        assert client.get(BASE+'/tables', headers=case['headers']).json()['items'][0]['occupied'] is True
        serve(client, case)
    assert client.get(BASE+'/tables', headers=case['headers']).json()['items'][0]['occupied'] is False
    revision = db.get(RestaurantServiceOrder, case['order']['id']).revision
    response = client.post(path, headers=case['headers'], json=payload)
    assert response.status_code == 201, response.text
    db.expire_all()
    assert db.get(RestaurantServiceOrder, case['order']['id']).revision == revision
    assert db.query(SRMReceipt).count() == 1


def test_shared_payment_counterfeit_tab_bill_link_rolls_back_receipt(client, db, settlement):
    case = settlement
    billed = post(client, case['headers'], f"/tabs/{case['order']['id']}/bill", bill_input(case))
    command = db.query(RestaurantCommand).filter_by(action='tab.bill').one()
    db.connection().execute(RestaurantCommand.__table__.update().where(RestaurantCommand.id == command.id).values(
        result={**command.result, 'checkout': {**command.result['checkout'], 'id': 999999}}))
    db.commit()
    response = client.post(f"/api/v1/srm/service-checkout/{billed['checkout']['id']}/payments", headers=case['headers'], json={
        'expected_revision': billed['checkout']['revision'], 'pos_session_id': case['register'],
        'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}})
    assert response.status_code == 409, response.text
    assert db.query(SRMReceipt).count() == 0


@pytest.mark.parametrize('fault', ['transient_root', 'dirty_root', 'foreign_session', 'wrong_epoch'])
def test_callback_rejects_forged_or_changed_native_source(db, client, settlement, fault):
    from fastapi import HTTPException
    from sqlalchemy.orm import Session
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.native_checkout_authority import capture
    from app.business_packs.restaurant.settlement import after_native_payment
    from tests.test_srm_native_transaction_operations import native_writer
    case = settlement
    billed = post(client, case['headers'], f"/tabs/{case['order']['id']}/bill", bill_input(case))
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        foreign = Session(bind=db.bind)
        try:
            root = db.get(POSServiceCheckout, billed['checkout']['id'])
            epoch = capture(db, case['manager'], scope, order=False, billing=False, payments=True, write=True)
            if fault == 'transient_root':
                root = POSServiceCheckout(id=root.id)
            elif fault == 'dirty_root':
                root.currency = 'USD'
            elif fault == 'foreign_session':
                root = foreign.get(POSServiceCheckout, root.id)
                assert root is not None
            else:
                epoch = 'forged'
            with pytest.raises(HTTPException) as denied:
                after_native_payment(db, case['manager'], scope, root, epoch)
            assert denied.value.status_code == 403
        finally:
            foreign.close()
            db.rollback()
            cleanup()
