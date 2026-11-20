from datetime import date
from decimal import Decimal
import pytest
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def report(client, headers, kind="summary", **params):
    response = client.get("/api/v1/fam/inventory/reports", headers=headers, params={"analysis": True, "report": kind, **params})
    assert response.status_code == 200, response.text
    return response.json()


def move(client, headers, item, warehouse, kind, qty_in=0, qty_out=0, suffix="1"):
    payload = {"movement_number": "AUD-"+suffix, "movement_date": "2026-06-07", "movement_type": kind, "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_in": qty_in, "quantity_out": qty_out, "rate": 10}]}
    draft = client.post("/api/v1/fam/inventory/stock-movements", headers=headers, json=payload)
    assert draft.status_code == 201, draft.text
    posted = client.post(f"/api/v1/fam/inventory/stock-movements/{draft.json()['id']}/post", headers=headers, json=payload)
    assert posted.status_code == 200, posted.text
    return posted.json()


@pytest.mark.parametrize("returns,expected", [(False, 120), (True, 115)])
def test_posted_quantities_reconcile_and_ledger_pages_preserve_opening(client, db, returns, expected):
    headers = inventory_headers(client, db, "report-accuracy@example.com")
    item, warehouse = create_stock_item(client, headers, "REPORT-ACCURACY")
    post_opening_stock(client, headers, item, warehouse, quantity=100, rate=10, suffix="AUD")
    move(client, headers, item, warehouse, "purchase_receipt", 50, suffix="PUR")
    move(client, headers, item, warehouse, "delivery_note", qty_out=30, suffix="SALE")
    if returns:
        move(client, headers, item, warehouse, "purchase_return", qty_out=10, suffix="PR")
        move(client, headers, item, warehouse, "sales_return", qty_in=5, suffix="SR")
        cogs = client.get('/api/v1/fam/inventory/reports/cogs', headers=headers)
        assert cogs.status_code == 200, cogs.text
        assert cogs.json()['total_cogs'] == 250
        margin = client.get('/api/v1/fam/inventory/reports/gross-margin', headers=headers)
        assert margin.status_code == 200, margin.text
        assert margin.json()['items'][0]['cogs'] == 250
        assert margin.json()['items'][0]['gross_margin'] is None
    summary = report(client, headers)["items"][0]
    assert Decimal(str(summary["quantity"])) == expected
    assert summary["purchases"] == 50 and summary["sales"] == 30
    assert summary["stock_value"] == expected * 10
    assert summary["opening_quantity"] == 100
    assert summary["opening_quantity"] + summary["purchases"] - summary["purchase_returns"] - summary["sales"] + summary["sales_returns"] + summary["transfers_in"] - summary["transfers_out"] + summary["adjustments_and_other"] == expected
    assert report(client, headers, "reconciliation")["total"] == 0
    ledger = report(client, headers, "ledger", start_date="2026-06-07", per_page=1, page=2)
    assert ledger["items"][0]["opening_quantity"] == 150
    assert ledger["items"][0]["closing_quantity"] == 120
    assert ledger["items"][0]["movement_number"] == "AUD-SALE"


def test_reservations_and_detected_mismatch_do_not_rewrite_stock(client, db):
    from app.apps.fam.models import FAMStockItem
    headers = inventory_headers(client, db, "report-reservations@example.com")
    item, warehouse = create_stock_item(client, headers, "REPORT-RESERVE")
    post_opening_stock(client, headers, item, warehouse, quantity=100, rate=10, suffix="RES")
    reserved = client.post("/api/v1/fam/inventory/reserve-stock", headers=headers, json={"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 20, "source_module": "srm", "source_record_type": "sales_order", "source_record_id": "audit-1"})
    assert reserved.status_code == 201, reserved.text
    row = report(client, headers)["items"][0]
    assert (row["quantity"], row["reserved_quantity"], row["available_quantity"]) == (100, 20, 80)
    stored = db.get(FAMStockItem, item["id"])
    stored.current_quantity = 99
    db.commit()
    issue = report(client, headers, "reconciliation")["items"][0]
    assert issue["quantity_difference"] == -1
    assert db.get(FAMStockItem, item["id"]).current_quantity == 99


def test_all_analysis_views_are_paginated_and_dates_are_validated(client, db):
    from app.shared.inventory_reporting import REPORTS
    headers = inventory_headers(client, db, "report-all-views@example.com")
    item, warehouse = create_stock_item(client, headers, "REPORT-ALL")
    post_opening_stock(client, headers, item, warehouse, quantity=100, rate=10, suffix="ALL")
    for name in REPORTS:
        data = report(client, headers, name, per_page=1)
        assert len(data["items"]) <= 1
    response = client.get("/api/v1/fam/inventory/reports?analysis=true&start_date=2026-07-01&end_date=2026-06-01", headers=headers)
    assert response.status_code == 422


def test_transfer_moves_exact_quantity_once_without_revaluing_stock(client, db):
    headers = inventory_headers(client, db, "report-transfer@example.com")
    item, warehouse = create_stock_item(client, headers, "REPORT-TRANSFER")
    post_opening_stock(client, headers, item, warehouse, quantity=100, rate=10, suffix="TRANSFER")
    destination = client.post('/api/v1/fam/inventory/warehouses', headers=headers, json={'warehouse_code':'AUD-DEST','warehouse_name':'Audit destination'}).json()
    draft = client.post('/api/v1/fam/inventory/stock-transfers', headers=headers, json={'transfer_number':'OPEN-TRANSFER','transfer_date':'2026-06-07','from_warehouse_id':warehouse['id'],'to_warehouse_id':destination['id'],'lines':[{'stock_item_id':item['id'],'quantity':20,'rate':999}]})
    assert draft.status_code == 201, draft.text
    path=f"/api/v1/fam/inventory/stock-transfers/{draft.json()['id']}/post"
    assert client.post(path,headers=headers).status_code == 200
    assert client.post(path,headers=headers).status_code == 409
    rows=report(client,headers)['items']
    assert {row['warehouse_id']:row['quantity'] for row in rows} == {warehouse['id']:80,destination['id']:20}
    assert sum(row['stock_value'] for row in rows) == 1000
    assert report(client,headers,'reconciliation')['total'] == 0


def test_outgoing_cost_uses_inventory_cost_and_negative_stock_is_explicit(client,db):
    from app.apps.fam.models import FAMInventoryControlSetting
    headers=inventory_headers(client,db,'report-cost-negative@example.com')
    item,warehouse=create_stock_item(client,headers,'REPORT-COST')
    post_opening_stock(client,headers,item,warehouse,quantity=100,rate=10,suffix='COST')
    payload={'movement_date':'2026-06-07','movement_type':'stock_out','lines':[{'stock_item_id':item['id'],'warehouse_id':warehouse['id'],'quantity_out':120,'rate':999}]}
    rejected=client.post('/api/v1/fam/inventory/stock-out',headers=headers,json=payload)
    assert rejected.status_code==409,rejected.text
    control=FAMInventoryControlSetting(company_id=1,setting_key='allow_negative_stock',setting_value_json={'value':True})
    db.add(control);db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,control);db.commit()
    accepted=client.post('/api/v1/fam/inventory/stock-out',headers=headers,json=payload)
    assert accepted.status_code==201,accepted.text
    row=report(client,headers)['items'][0]
    assert row['quantity']==-20 and row['stock_value']==-200
    assert report(client,headers,'reconciliation')['items'][0]['issue_type']=='Negative stock'


def test_exports_include_matching_rows_and_preserve_cost_values(client,db):
    from io import BytesIO
    from openpyxl import load_workbook
    headers=inventory_headers(client,db,'report-exports@example.com')
    item,warehouse=create_stock_item(client,headers,'REPORT-EXPORT')
    post_opening_stock(client,headers,item,warehouse,quantity=100,rate=10,suffix='EXPORT')
    params={'analysis':True,'report':'summary','export_format':'xlsx','product_id':item['id']}
    response=client.get('/api/v1/fam/inventory/reports',headers=headers,params=params)
    assert response.status_code==200,response.text
    values=list(load_workbook(BytesIO(response.content),data_only=True).active.values)
    assert any('SKU-REPORT-EXPORT' in row for row in values)
    pdf=client.get('/api/v1/fam/inventory/reports',headers=headers,params={**params,'export_format':'pdf'})
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')


def test_sales_reports_use_scoped_warehouse_ledger_not_product_cache(client,db,superuser_headers):
    def post(path,payload):
        response=client.post('/api/v1/srm/inventory/'+path,headers=superuser_headers,json=payload)
        assert response.status_code==201,response.text
        return response.json()
    warehouse=post('warehouses',{'warehouse_code':'AUD-SALES','warehouse_name':'Sales audit'})
    item=post('items',{'sku':'AUD-SALES','item_name':'Sales audit item'})
    post('opening-stock',{'product_id':item['id'],'warehouse_id':warehouse['id'],'quantity':100,'rate':10})
    from app.shared.inventory_reporting import REPORTS
    for name in REPORTS:
        response=client.get('/api/v1/srm/inventory/reports',headers=superuser_headers,params={'report':name})
        assert response.status_code==200,response.text
        if name=='summary':
            assert response.json()['items'], response.text
            assert response.json()['items'][0]['quantity']==100
            assert response.json()['items'][0]['stock_value']==1000


def test_report_indexes_migrate_without_changing_transactions(db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    path=Path(__file__).parents[1]/'alembic/versions/20261119_089_inventory_report_indexes.py'
    spec=importlib.util.spec_from_file_location('inventory_indexes',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(db.connection())):
        module.upgrade()
        for name,table,_ in module.INDEXES:
            assert name in {index['name'] for index in inspect(db.connection()).get_indexes(table)}
        module.downgrade()


@pytest.mark.parametrize('method,cost,remaining', [('weighted_average',Decimal('1600'),Decimal('1600')),('fifo',Decimal('1700'),Decimal('1700'))])
def test_configured_costing_and_remaining_receipt_layers(client,db,method,cost,remaining):
    from app.apps.fam.models import FAMStockItem,FAMInventoryValuationLayer
    headers=inventory_headers(client,db,'report-layer-cost@example.com')
    item,warehouse=create_stock_item(client,headers,'REPORT-LAYER')
    db.get(FAMStockItem,item['id']).valuation_method=method;db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=100,rate=10,suffix='LAYER')
    receipt={'movement_date':'2026-06-07','movement_type':'stock_in','lines':[{'stock_item_id':item['id'],'warehouse_id':warehouse['id'],'quantity_in':50,'rate':20}]}
    response=client.post('/api/v1/fam/inventory/stock-in',headers=headers,json=receipt);assert response.status_code==201,response.text
    move(client,headers,item,warehouse,'delivery_note',qty_out=30,suffix='LAYER-ISSUE')
    layers=db.query(FAMInventoryValuationLayer).filter_by(stock_item_id=item['id']).all()
    assert sum(row.remaining_quantity for row in layers)==120
    assert sum(row.remaining_value for row in layers)==remaining
    row=report(client,headers,'valuation')['items'][0]
    assert Decimal(str(row['stock_value']))==cost
    assert row['valuation_method']==method


def test_offsetting_sales_warehouse_errors_are_both_reported(client,db,superuser_headers):
    from app.apps.srm.models import SRMInventoryBalance
    def post(path,payload):
        response=client.post('/api/v1/srm/inventory/'+path,headers=superuser_headers,json=payload)
        assert response.status_code==201,response.text
        return response.json()
    item=post('items',{'sku':'AUD-OFFSET','item_name':'Offsetting warehouse audit'})
    for i in range(2):
        warehouse=post('warehouses',{'warehouse_code':f'AUD-OFFSET-{i}','warehouse_name':f'Audit {i}'})
        post('opening-stock',{'product_id':item['id'],'warehouse_id':warehouse['id'],'quantity':100,'rate':10})
    balances=db.query(SRMInventoryBalance).filter_by(product_id=item['id']).order_by(SRMInventoryBalance.id).all()
    balances[0].quantity=120;balances[1].quantity=80;db.commit()
    response=client.get('/api/v1/srm/inventory/reports?report=reconciliation',headers=superuser_headers)
    assert response.status_code==200,response.text
    assert response.json()['total']==2
    assert {row['quantity_difference'] for row in response.json()['items']}=={-20,20}


def test_legacy_layer_variance_is_reported_without_silent_repair(client,db):
    from app.apps.fam.models import FAMInventoryValuationLayer
    headers=inventory_headers(client,db,'report-no-repair@example.com')
    item,warehouse=create_stock_item(client,headers,'REPORT-NO-REPAIR')
    post_opening_stock(client,headers,item,warehouse,quantity=100,rate=10,suffix='NO-REPAIR')
    layer=db.query(FAMInventoryValuationLayer).filter_by(stock_item_id=item['id']).one()
    layer.remaining_value=2000;db.commit()
    move(client,headers,item,warehouse,'stock_in',qty_in=10,suffix='NO-REPAIR-NEW')
    db.refresh(layer)
    assert layer.remaining_value==2000
    issues=report(client,headers,'reconciliation')['items']
    assert any(row['issue_type']=='Receipt layer/balance mismatch' and row['value_difference']==1000 for row in issues)


def test_large_quantity_cogs_uses_recorded_cents_not_rounded_unit_rate(client,db):
    from app.apps.fam.models import FAMStockMovementLine,FAMStockMovement,FAMInventoryValuationLayer,FAMVoucherLine
    headers=inventory_headers(client,db,'report-large-precision@example.com')
    item,warehouse=create_stock_item(client,headers,'REPORT-LARGE')
    post_opening_stock(client,headers,item,warehouse,quantity=100000,rate=10,suffix='LARGE')
    payload={'movement_date':'2026-06-07','movement_type':'stock_in','lines':[{'stock_item_id':item['id'],'warehouse_id':warehouse['id'],'quantity_in':50000,'rate':20}]}
    receipt=client.post('/api/v1/fam/inventory/stock-in',headers=headers,json=payload)
    assert receipt.status_code==201,receipt.text
    issue=client.post('/api/v1/fam/inventory/stock-out',headers=headers,json={'movement_date':'2026-06-07','movement_type':'stock_out','lines':[{'stock_item_id':item['id'],'warehouse_id':warehouse['id'],'quantity_out':30000,'rate':999}]})
    assert issue.status_code==201,issue.text
    movement=db.get(FAMStockMovement,issue.json()['id'])
    line=db.query(FAMStockMovementLine).filter_by(movement_id=movement.id).one()
    assert line.value==Decimal('400000')
    assert sum(row.debit_amount for row in db.query(FAMVoucherLine).filter_by(voucher_id=movement.voucher_id).all())==Decimal('400000')
    assert sum(row.remaining_value for row in db.query(FAMInventoryValuationLayer).filter_by(stock_item_id=item['id']).all())==Decimal('1600000')
    assert report(client,headers,'valuation')['items'][0]['stock_value']==1600000
