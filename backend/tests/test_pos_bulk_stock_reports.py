"""Volume acceptance: real HTTP receipts/checkouts and independent reconciliation."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

from app.apps.srm.models import SRMProduct, SRMInventoryBalance, SRMInvoice, SRMReceipt
from app.business_packs.models import PackMasterAvailability
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity


def test_55_customers_60_sales_45_products_stock_and_reports(client, db, retail_setup):
    headers, actor, branch, context, register, _, warehouse = retail_setup
    products = []
    customers = []
    from app.apps.crm.models import CRMCompany
    from test_identity_utils import own_workflow_records
    for index in range(55):
        customer = CRMCompany(organization_id=1, branch_id=branch, account_type='Customer',
            name=f'Volume QA Customer {index:02d}', address='Synthetic QA address')
        db.add(customer)
        own_workflow_records(db, customer)
        customers.append(customer.id)
    for index in range(45):
        product = SRMProduct(organization_id=1, sku=f'VOLUME-{index:03d}',
            item_name=f'Volume product {index:03d}', product_type='stock', track_inventory=True,
            default_warehouse_id=warehouse, sales_rate=100 + index, gst_rate=18, active=True)
        db.add(product)
        own_workflow_records(db, product)
        products.append(product.id)
    db.commit()
    for table, ids in [('crm_companies', customers), ('srm_products', products)]:
        for ident in ids:
            db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
                resource_table=table, resource_key=str(ident), active=True))
    db.commit()
    for pid in products:
        response = client.post('/api/v1/srm/retail/stock-receipts', headers=headers, json={
            'request_key': str(uuid4()), 'product_id': pid, 'warehouse_id': warehouse,
            'quantity': '100', 'unit_cost': '40', 'received_date': date.today().isoformat()})
        assert response.status_code == 201, response.text
    sold = defaultdict(Decimal)
    gross = tax = Decimal(0)
    collections = defaultdict(Decimal)
    for index in range(60):
        indices = [index % 45, (index + 7) % 45]
        quantities = [Decimal(1 + index % 3), Decimal('0.50') if index % 2 else Decimal('2')]
        subtotal = sum((Decimal(100 + p) * q for p, q in zip(indices, quantities)), Decimal(0))
        line_tax = sum(((Decimal(100 + p) * q * Decimal('.18')).quantize(Decimal('.01'))
                        for p, q in zip(indices, quantities)), Decimal(0))
        total = subtotal + line_tax
        method = 'cash' if index % 2 == 0 else 'card'
        command = {'request_id': str(uuid4()), 'customer_id': customers[index % 55],
            'pos_session_id': register,
            'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product',
                       'product_id': products[p], 'quantity': str(q)} for p, q in zip(indices, quantities)],
            'payments': [{'payment_key': str(uuid4()), 'method': method, 'amount': str(total)}]}
        response = client.post('/api/v1/srm/service-checkout', headers=headers, json=command)
        assert response.status_code == 201, (index, response.text)
        result = response.json()
        assert Decimal(result['invoice']['total']) == total
        assert Decimal(result['invoice']['paid']) == total
        assert Decimal(result['invoice']['balance']) == 0
        if index % 10 == 0:
            replay = client.post('/api/v1/srm/service-checkout', headers=headers, json=command)
            assert replay.status_code == 201 and replay.json() == result
        for p, q in zip(indices, quantities):
            sold[products[p]] += q
            db.expire_all()
            assert db.get(SRMProduct, products[p]).current_quantity == 100 - sold[products[p]]
            assert db.query(SRMInventoryBalance).filter_by(product_id=products[p], warehouse_id=warehouse).one().quantity == 100 - sold[products[p]]
        gross += total
        tax += line_tax
        collections[method] += total
    stock = client.get('/api/v1/srm/retail/stock', headers=headers, params={'limit': 100})
    assert stock.status_code == 200, stock.text
    projected = {row['product_id']: row for row in stock.json()['items']}
    rows = []
    for pid in products:
        expected = 100 - sold[pid]
        actual = Decimal(projected[pid]['stock']['available_quantity'])
        assert actual == expected
        rows.append({'product_id': pid, 'received': 100, 'sold': str(sold[pid]), 'expected': str(expected), 'actual': str(actual)})
    report = client.get('/api/v1/srm/retail/reports/daily', headers=headers,
                        params={'day': date.today().isoformat()})
    output = Path(__file__).resolve().parents[1] / 'outputs' / 'pos-bulk-stock-reports.json'
    output.parent.mkdir(exist_ok=True)
    evidence = {'environment': 'isolated SQLite API integration; seeded customers/products; not deployed browser',
        'customers': 55, 'products': 45, 'transactions': 60, 'duplicate_retries': 6,
        'gross': str(gross), 'tax': str(tax), 'collections': {k: str(v) for k, v in collections.items()},
        'stock': rows, 'daily_report_status': report.status_code, 'daily_report': report.json()}
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    assert report.status_code == 200, report.text
    daily = report.json()
    assert daily['sales'] == [{'currency': 'INR', 'count': 60, 'gross': str(gross), 'tax': str(tax)}]
    assert {r['method']: Decimal(r['amount']) for r in daily['collections']} == dict(collections)
    movements = daily['stock_movements']
    assert sum(Decimal(r['quantity_in']) for r in movements) == 4500
    assert sum(Decimal(r['quantity_out']) for r in movements) == sum(sold.values())
    assert db.query(SRMInvoice).count() == 60
    assert db.query(SRMReceipt).count() == 60
