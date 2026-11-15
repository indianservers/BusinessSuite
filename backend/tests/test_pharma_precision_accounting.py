"""Canonical journals and the public refund interface retain native cents."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.models.user import Permission
from app.apps.fam.models import FAMLedger, FAMLedgerEntry, FAMVoucher
from app.apps.srm.models import SRMInventoryBatch
from tests.test_pharma_fefo import lots, sale, lot_quantities
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_retail_return_http import post_original


@pytest.mark.parametrize('quantity', ['0.001', '0.125'])
def test_three_decimal_sale_and_public_refund_use_balanced_canonical_ledgers(client, db, lots, quantity):
    case = lots[0]
    actor = case[1]
    permission = db.query(Permission).filter_by(name='fam_admin').one_or_none()
    if permission is None:
        permission = Permission(name='fam_admin', description='Native Accounting administrator')
        db.add(permission)
        db.flush()
    actor.role.permissions.append(permission)
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'fam': {'enabled': True, 'permissions': ['fam_admin'],
                    'actions': ['view', 'create', 'edit', 'approve'], 'scope': 'organization'}}
    db.commit()
    base = (Decimal(quantity)*100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    total = base+(base*Decimal('.18')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    payload = sale(lots, quantity)
    payload['payments'] = [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': str(total)}]
    response = client.post('/api/v1/srm/service-checkout', headers=case[0], json=payload)
    assert response.status_code == 201, response.text
    checkout = response.json()
    accounting = (case[0], actor, case[2], case[3], checkout, lots[2], case[4], case[5])
    post_original(db, accounting)
    assert db.query(FAMVoucher).count() == 2
    ledger_count = db.query(FAMLedger).count()
    post_original(db, accounting)
    assert db.query(FAMVoucher).count() == 2 and db.query(FAMLedger).count() == ledger_count
    discovery = client.get(f"/api/v1/srm/pharma/returns/sales/{checkout['id']}/lots", headers=case[0])
    assert discovery.status_code == 200, discovery.text
    original = discovery.json()['lots']
    assert len(original) == 1 and Decimal(original[0]['sold_quantity']) == Decimal(quantity)
    before = lot_quantities(db, lots)
    body = {'request_key': str(uuid4()), 'checkout_id': checkout['id'],
            'expected_checkout_revision': checkout['revision'],
            'lots': [{'allocation_id': original[0]['allocation_id'], 'quantity': quantity}],
            'refund': {'method': 'cash', 'session_id': lots[2]}, 'reason': 'Exact original fractional medicine return'}
    returned = client.post('/api/v1/srm/pharma/returns', headers=case[0], json=body)
    assert returned.status_code == 201, returned.text
    result = returned.json()
    assert Decimal(result['refund_amount']) == total
    assert db.query(FAMVoucher).count() == 4 and db.query(FAMLedger).count() == ledger_count
    for voucher in db.query(FAMVoucher).all():
        entries = db.query(FAMLedgerEntry).filter_by(voucher_id=voucher.id).all()
        assert entries
        debit = sum((entry.debit_amount for entry in entries), Decimal(0))
        credit = sum((entry.credit_amount for entry in entries), Decimal(0))
        assert debit == credit == total
        assert all(entry.debit_amount == entry.debit_amount.quantize(Decimal('.01')) and
                   entry.credit_amount == entry.credit_amount.quantize(Decimal('.01')) for entry in entries)
    assert lot_quantities(db, lots) == before
    quarantined = db.query(SRMInventoryBatch).filter_by(status='quarantined').one()
    assert quarantined.available_quantity == 0 and quarantined.quantity == Decimal(quantity)
    replay = client.post('/api/v1/srm/pharma/returns', headers=case[0], json=body)
    assert replay.status_code == 201 and replay.json() == result
    assert db.query(FAMVoucher).count() == 4 and db.query(FAMLedger).count() == ledger_count
