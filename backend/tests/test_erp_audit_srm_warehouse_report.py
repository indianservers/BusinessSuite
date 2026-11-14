from decimal import Decimal
from datetime import datetime
from tests.srm_test_utils import auth_headers_for


def test_sales_warehouse_report_uses_scoped_balances_and_preserves_cents(client, db, superuser_headers):
    from app.apps.srm.models import SRMProduct, SRMInventoryBalance, SRMWarehouse
    from test_identity_utils import own_workflow_records
    headers=superuser_headers
    product=client.post('/api/v1/srm/inventory/items',headers=headers,json={'sku':'QA-WH-REAL','item_name':'Warehouse stock','metadata_json':{'currency':'USD'}})
    assert product.status_code==201,product.text
    item=product.json()
    warehouses=[]
    for index,(quantity,rate) in enumerate([(3.1,5.2),(2.5,7.3)]):
        response=client.post('/api/v1/srm/inventory/warehouses',headers=headers,json={'warehouse_code':f'QA-WH-{index}','warehouse_name':f'Warehouse {index}'})
        assert response.status_code==201,response.text
        warehouse=response.json();warehouses.append(warehouse)
        opening=client.post('/api/v1/srm/inventory/opening-stock',headers=headers,json={'product_id':item['id'],'warehouse_id':warehouse['id'],'quantity':quantity,'rate':rate})
        assert opening.status_code==201,opening.text
    # Deliberately mismatched cached product totals must not replace per-warehouse balances.
    db.get(SRMProduct,item['id']).current_quantity=999
    db.get(SRMProduct,item['id']).average_cost=999
    for name,attributes in [('FOREIGN',{'organization_id':2}),('DELETED',{'deleted_at':datetime(2026,1,1)}),('SERVICE',{'product_type':'service'}),('BRANCH',{'metadata_json':{'catalog_branches':{'default':False,'overrides':{}}}})]:
        values={'organization_id':1,'sku':'QA-WH-'+name,'item_name':name,'product_type':'stock',**attributes}
        hidden=SRMProduct(**values);db.add(hidden);db.flush()
        balance=SRMInventoryBalance(organization_id=1,product_id=hidden.id,warehouse_id=warehouses[0]['id'],quantity=100,average_cost=100)
        db.add(balance);own_workflow_records(db,balance)
    # A private catalog workspace must remain hidden from an ordinary SRM viewer.
    from app.shared.catalog_models import CatalogDetails
    from app.apps.project_management.models import PMSWorkspace
    workspace=PMSWorkspace(organization_id=1,name='Private stock workspace')
    hidden=SRMProduct(organization_id=1,sku='QA-WH-PRIVATE',item_name='Private stock',product_type='stock')
    db.add_all([workspace,hidden]);db.flush()
    details=CatalogDetails(organization_id=1,product_id=hidden.id,workspace_id=workspace.id)
    balance=SRMInventoryBalance(organization_id=1,product_id=hidden.id,warehouse_id=warehouses[0]['id'],quantity=100,average_cost=100)
    db.add_all([details,balance]);own_workflow_records(db,workspace,details,balance)
    db.commit()
    viewer=auth_headers_for(client,db,'qa-warehouse-reader@example.com','srm_viewer',permissions=['srm_view'])
    response=client.get('/api/v1/srm/inventory/reports/warehouse-stock',headers=viewer)
    assert response.status_code==200,response.text
    data=response.json();assert data['total']==2
    assert len({row['id'] for row in data['items']})==2
    assert {row['sku'] for row in data['items']}=={'QA-WH-REAL'}
    for row,quantity,value in zip(sorted(data['items'],key=lambda row:row['warehouse_name']),['3.1','2.5'],['16.12','18.25']):
        assert Decimal(str(row['quantity']))==Decimal(quantity)
        assert Decimal(str(row['stock_value']))==Decimal(value)
        assert row['currency']=='USD'
        assert row['warehouse_name'].startswith('Warehouse ')
    assert data['valuation_basis']=='warehouse_balance_average_cost'
    assert client.get('/api/v1/srm/inventory/reports/warehouse-stock').status_code==403
    denied=auth_headers_for(client,db,'qa-warehouse-denied@example.com','srm_sales_executive',permissions=['srm_sales_order_view'])
    assert client.get('/api/v1/srm/inventory/reports/warehouse-stock',headers=denied).status_code==403
