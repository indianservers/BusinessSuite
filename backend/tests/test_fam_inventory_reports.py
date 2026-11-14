from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_inventory_phase9_reports_render_from_stock_ledgers(client, db):
    headers = inventory_headers(client, db, "phase9-reports@example.com")
    item, warehouse = create_stock_item(client, headers, "P9-REP", reorder_level=20)
    post_opening_stock(client, headers, item, warehouse, quantity=10, rate=100, suffix="P9-REP")

    endpoints = [
        "/api/v1/fam/inventory/reports/stock-summary",
        f"/api/v1/fam/inventory/reports/item-ledger/{item['id']}",
        "/api/v1/fam/inventory/reports/warehouse-stock",
        "/api/v1/fam/inventory/reports/stock-aging",
        "/api/v1/fam/inventory/reports/reorder",
        "/api/v1/fam/inventory/reports/dead-stock",
        "/api/v1/fam/inventory/reports/fast-slow-moving",
        "/api/v1/fam/inventory/reports/valuation",
        "/api/v1/fam/inventory/reports/gross-margin",
        "/api/v1/fam/inventory/reports/purchase-item-register",
        "/api/v1/fam/inventory/reports/sales-item-register",
        "/api/v1/fam/inventory/reports/stock-movement-audit",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200, f"{endpoint}: {response.text}"
        assert "total" in response.json() or "total_inventory_value" in response.json()


def test_inventory_cogs_and_hsn_reports_preserve_currency_cents_and_group_identity(client,db):
    from app.apps.fam.models import FAMCompanyFinancialSettings,FAMStockItem
    from decimal import Decimal
    headers=inventory_headers(client,db,'qa-financial-summaries@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-SUMMARY')
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one()
    settings.base_currency='USD';db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=3.1,rate=5.2,suffix='QA-SUMMARY')
    delivery=client.post('/api/v1/fam/inventory/delivery-notes',headers=headers,json={'movement_date':'2026-06-07','movement_type':'delivery_note','reference_number':'QA-CENTS','lines':[{'stock_item_id':item['id'],'warehouse_id':warehouse['id'],'quantity_out':1.1,'rate':5.2}]})
    assert delivery.status_code==201,delivery.text
    other,_=create_stock_item(client,headers,'QA-HSN-OTHER')
    db.get(FAMStockItem,other['id']).hsn_code='9983';db.commit()
    cogs=client.get('/api/v1/fam/inventory/reports/cogs',headers=headers)
    assert cogs.status_code==200,cogs.text
    assert cogs.json()['currency']=='USD'
    assert Decimal(str(cogs.json()['total_cogs']))==Decimal('5.72')
    assert Decimal(str(cogs.json()['items'][0]['cogs_value']))==Decimal('5.72')
    hsn=client.get('/api/v1/fam/inventory/reports/hsn-summary',headers=headers)
    assert hsn.status_code==200,hsn.text
    assert hsn.json()['currency']=='USD'
    assert hsn.json()['total']==2
    assert len({row['id'] for row in hsn.json()['items']})==2
    row=next(row for row in hsn.json()['items'] if row['hsn_code']=='8471')
    assert Decimal(str(row['stock_value']))==Decimal('10.40')
    assert Decimal(str(row['quantity']))==Decimal('2')


def test_inventory_warehouse_stock_ignores_unposted_and_foreign_header_movements(client,db):
    from datetime import date
    from decimal import Decimal
    from app.apps.fam.models import FAMStockMovement,FAMStockMovementLine,FAMCompanyFinancialSettings
    headers=inventory_headers(client,db,'qa-warehouse-posted@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-WAREHOUSE-POSTED')
    db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one().base_currency='USD';db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=3.1,rate=5.2,suffix='QA-WAREHOUSE-POSTED')
    for index,(status,company) in enumerate([('draft',1),('cancelled',1),('posted',2)]):
        movement=FAMStockMovement(company_id=company,movement_number=f'QA-EXCLUDED-{index}',movement_date=date(2026,6,7),movement_type='stock_in',status=status)
        db.add(movement);db.flush()
        line=FAMStockMovementLine(company_id=1,movement_id=movement.id,stock_item_id=item['id'],warehouse_id=warehouse['id'],quantity_in=100,quantity_out=0,rate=5.2,value=520)
        db.add(line)
        from test_identity_utils import own_workflow_records
        own_workflow_records(db,movement,line)
    db.commit()
    for endpoint in ['/inventory/warehouse-stock','/inventory/reports/warehouse-stock']:
        response=client.get('/api/v1/fam'+endpoint,headers=headers)
        assert response.status_code==200,response.text
        data=response.json();assert data['total']==1
        row=data['items'][0]
        assert Decimal(str(row['quantity']))==Decimal('3.1')
        assert Decimal(str(row['stock_value']))==Decimal('16.12')
        assert data['currency']=='USD'
        assert row['id']==f"warehouse:{warehouse['id']}:item:{item['id']}"
