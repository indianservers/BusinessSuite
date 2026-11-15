"""SQLite schema-loss regressions; native migrations are checked separately."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.apps.srm.models import SRMPOSSession
from app.business_packs.restaurant.split_bills import register_cash
from app.business_packs.restaurant.split_models import MODELS
from tests.test_restaurant_split_bills import (settlement, unpaid, scenario, catalog, directory_identity,
    split_sql_guards, body, selected)
from tests.test_restaurant_kitchen import post


@pytest.mark.parametrize('fault', ['missing_receipts', 'missing_columns', 'only_native_aliases_remain'])
def test_known_split_provenance_never_falls_back_to_zero_cash_on_partial_schema(client, db, settlement, fault):
    assert db.bind.dialect.name == 'sqlite'
    case = settlement
    path = f"/tabs/{case['order']['id']}/bills"
    billed = post(client, case['headers'], path, body(case))
    post(client, case['headers'], path+f"/{billed['bill_id']}/payments", {
        'request_key': str(uuid4()), 'expected_revision': billed['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '10'}})
    with selected(db, case):
        register = db.get(SRMPOSSession, case['register'])
        if fault == 'missing_columns':
            db.connection().exec_driver_sql('ALTER TABLE business_restaurant_bill_receipts RENAME COLUMN collection_session_id TO broken_collection_session_id')
        elif fault == 'missing_receipts':
            db.connection().exec_driver_sql('DROP TABLE business_restaurant_bill_receipts')
        else:
            for model in reversed(MODELS):
                db.connection().exec_driver_sql('DROP TABLE '+model.__tablename__)
        with pytest.raises(HTTPException) as error: register_cash(db, register)
        assert error.value.status_code == 503
        db.rollback()


def test_entirely_absent_split_schema_without_actual_split_data_retains_legacy_zero(db):
    assert db.bind.dialect.name == 'sqlite'
    for model in reversed(MODELS):
        db.connection().exec_driver_sql('DROP TABLE '+model.__tablename__)
    db.info['business_pack_scope'] = SimpleNamespace(pack_key='restaurant')
    try:
        assert register_cash(db, SimpleNamespace(id=987654321)) == {
            'cash_received': Decimal(0), 'cash_by_currency': {}, 'receipt_ids': set(), 'collection_count': 0}
    finally:
        db.info.pop('business_pack_scope', None)
        db.rollback()


@pytest.mark.parametrize('route', ['order', 'bills', 'billing', 'registers'])
def test_restaurant_domain_reports_missing_provenance_columns_as_unavailable(client, db, settlement, route):
    assert db.bind.dialect.name == 'sqlite'
    case = settlement
    db.connection().exec_driver_sql('ALTER TABLE business_restaurant_bill_receipts RENAME COLUMN collection_currency TO broken_currency')
    path = {'order': '/orders/'+str(case['order']['id']), 'bills': f"/tabs/{case['order']['id']}/bills",
        'billing': f"/tabs/{case['order']['id']}/billing", 'registers': '/registers'}[route]
    response = client.get('/api/v1/srm/restaurant'+path, headers=case['headers'])
    assert response.status_code == 503, response.text
    db.rollback()
