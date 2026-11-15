from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.business_packs.models import PackUserGrant
from tests.test_pharma_recalls import request, BASE
from tests.test_pharma_fefo import lots, sale, lot_quantities
from tests.test_pharma_receipts import pharma, command, counts, balance
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_business_pack_http_integration import grant


def test_recall_traces_fractional_sales_with_pagination_and_no_stock_changes(client, db, lots):
    case = lots[0]
    checkouts = []
    for quantity in ('0.25', '0.50'):
        response = client.post('/api/v1/srm/service-checkout', headers=case[0], json=sale(lots, quantity))
        assert response.status_code == 201, response.text
        checkouts.append(response.json())
    response = client.post(BASE, headers=case[0], json=request(lots, 'recall'))
    assert response.status_code == 201, response.text
    ident = response.json()['id']
    before = lot_quantities(db, lots)
    url = f'{BASE}/{ident}'
    first = client.get(url, headers=case[0], params={'include_affected_sales': True, 'limit': 1})
    assert first.status_code == 200, first.text
    first = first.json()['affected_sales']
    assert first['has_more'] and first['next'] == first['items'][0]['allocation_id']
    second = client.get(url, headers=case[0], params={'include_affected_sales': True, 'limit': 1, 'after': first['next']})
    assert second.status_code == 200, second.text
    second = second.json()['affected_sales']
    assert not second['has_more'] and second['next'] is None
    rows = first['items'] + second['items']
    assert [Decimal(row['quantity']) for row in rows] == [Decimal('.25'), Decimal('.50')]
    assert [row['checkout_id'] for row in rows] == [row['id'] for row in checkouts]
    assert all(row['batch_id'] == lots[1][1]['batch_id'] for row in rows)
    assert all(row['invoice_id'] and row['invoice_line_id'] and row['movement_id'] for row in rows)
    assert lot_quantities(db, lots) == before
    assert client.get(f'{BASE}/999999?include_affected_sales=true', headers=case[0]).status_code == 404


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef'), ('construction', 'site_engineer')])
def test_multi_assignment_cannot_trace_or_receive_from_other_pack(client, db, lots, pack, role):
    case = lots[0]
    created = client.post(BASE, headers=case[0], json=request(lots))
    assert created.status_code == 201, created.text
    other, _ = grant(db, case[1], case[2], pack, role)
    headers = {**case[0], 'X-Suite-Pack-Context': str(other.id)}
    denied = client.get(f"{BASE}/{created.json()['id']}?include_affected_sales=true", headers=headers)
    assert denied.status_code == 403, denied.text
    before = counts(db), balance(db, case)
    assert client.post('/api/v1/srm/pharma/batch-receipts', headers=headers, json=command(case)).status_code == 403
    assert (counts(db), balance(db, case)) == before


def test_revocation_blocks_receipt_replay_and_trace(client, db, lots):
    case = lots[0]
    payload = command(case)
    assert client.post('/api/v1/srm/pharma/batch-receipts', headers=case[0], json=payload).status_code == 201
    created = client.post(BASE, headers=case[0], json=request(lots))
    assert created.status_code == 201, created.text
    role = db.query(PackUserGrant).filter_by(context_id=case[3], user_id=case[1].id).one()
    role.active = False
    db.commit()
    before = counts(db), balance(db, case)
    assert client.post('/api/v1/srm/pharma/batch-receipts', headers=case[0], json=payload).status_code == 403
    assert client.get(f"{BASE}/{created.json()['id']}?include_affected_sales=true", headers=case[0]).status_code == 403
    assert (counts(db), balance(db, case)) == before


def test_receipt_rejects_manufacture_after_receipt_without_mutation(client, db, pharma):
    payload = {**command(pharma), 'manufacture_date': (date.today() + timedelta(days=1)).isoformat()}
    before = counts(db), balance(db, pharma)
    response = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=payload)
    assert response.status_code == 422, response.text
    assert (counts(db), balance(db, pharma)) == before


def test_failed_receipt_can_retry_same_key_without_duplicate_stock(client, db, pharma, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm.services import commercial_numbering
    payload = command(pharma)
    before = counts(db), balance(db, pharma)
    original = commercial_numbering.reserve_number
    def unavailable(*args, **kwargs):
        raise HTTPException(409, 'Native numbering temporarily unavailable')
    monkeypatch.setattr(commercial_numbering, 'reserve_number', unavailable)
    url = '/api/v1/srm/pharma/batch-receipts'
    assert client.post(url, headers=pharma[0], json=payload).status_code == 409
    assert (counts(db), balance(db, pharma)) == before
    monkeypatch.setattr(commercial_numbering, 'reserve_number', original)
    success = client.post(url, headers=pharma[0], json=payload)
    assert success.status_code == 201, success.text
    after = counts(db), balance(db, pharma)
    assert balance(db, pharma) == before[1] + Decimal('2.5')
    assert client.post(url, headers=pharma[0], json=payload).json() == success.json()
    assert (counts(db), balance(db, pharma)) == after


def test_checkout_rejects_four_decimal_quantity_without_consuming_lots(client, db, lots):
    before = lot_quantities(db, lots), counts(db), balance(db, lots[0])
    response = client.post('/api/v1/srm/service-checkout', headers=lots[0][0], json=sale(lots, '0.0001'))
    assert response.status_code == 422, response.text
    assert (lot_quantities(db, lots), counts(db), balance(db, lots[0])) == before


def test_native_view_revocation_denies_trace(client, db, lots):
    from app.access.models import AccessPolicy
    case = lots[0]
    created = client.post(BASE, headers=case[0], json=request(lots))
    assert created.status_code == 201, created.text
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case[1].id).one()
    policy.grants = {**policy.grants, 'srm': {**policy.grants['srm'], 'actions': ['create', 'edit', 'approve']}}
    policy.version += 1
    db.commit()
    denied = client.get(f"{BASE}/{created.json()['id']}?include_affected_sales=true", headers=case[0])
    assert denied.status_code == 403, denied.text


def test_trace_is_private_to_company_and_branch_even_with_both_branch_grants(client, db, lots):
    from app.models.company import Branch
    from app.branches.models import BranchGrant, BranchOwnership
    from app.business_packs.models import PackContext
    case = lots[0]
    created = client.post(BASE, headers=case[0], json=request(lots))
    assert created.status_code == 201, created.text
    url = f"{BASE}/{created.json()['id']}?include_affected_sales=true"
    assert client.get(url, headers={**case[0], 'X-Suite-Organization': '999999'}).status_code == 403
    branch = Branch(company_id=1, organization_id=1, name='Other Pharma branch', code='OTHER-'+uuid4().hex[:8], is_active=True)
    db.add(branch)
    db.flush()
    db.add(BranchOwnership(company_id=1, branch_id=branch.id, resource_table='branches', resource_key=str(branch.id), source='test-created'))
    db.add(BranchGrant(company_id=1, branch_id=branch.id, user_id=case[1].id, can_write=True))
    original = db.get(PackContext, case[3])
    other = PackContext(company_id=1, branch_id=branch.id, activation_id=original.activation_id,
                        pack_key='pharma', pack_version=1, state='active')
    db.add(other)
    db.flush()
    db.add(PackUserGrant(company_id=1, branch_id=branch.id, context_id=other.id,
                         user_id=case[1].id, role='pharmacy_manager'))
    db.commit()
    denied = client.get(url, headers={**case[0], 'X-Suite-Branch': str(branch.id), 'X-Suite-Pack-Context': str(other.id)})
    assert denied.status_code == 404, denied.text
