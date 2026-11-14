from decimal import Decimal
from tests.srm_test_utils import auth_headers_for
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_sales_valuation_uses_warehouse_values_and_never_combines_currencies(client,db,superuser_headers):
    from app.apps.srm.models import SRMProduct,SRMInventoryBalance
    from app.shared.catalog_models import CatalogDetails
    from app.apps.project_management.models import PMSWorkspace
    from test_identity_utils import own_workflow_records
    def post(path,payload):
        response=client.post('/api/v1/srm/inventory/'+path,headers=superuser_headers,json=payload)
        assert response.status_code==201,response.text
        return response.json()
    warehouses=[post('warehouses',{'warehouse_code':f'QA-VAL-{i}','warehouse_name':f'Valuation warehouse {i}'}) for i in range(2)]
    products={key:post('items',{'sku':'QA-VAL-'+key,'item_name':key,'metadata_json':{'currency':currency}}) for key,currency in [('USD','USD'),('INR','INR'),('UNKNOWN',{'invalid':True})]}
    for key,index,quantity,rate in [('USD',0,3.1,5.2),('USD',1,2.5,7.3),('INR',0,2,10.125),('UNKNOWN',0,1,3.125)]:
        post('opening-stock',{'product_id':products[key]['id'],'warehouse_id':warehouses[index]['id'],'quantity':quantity,'rate':rate})
    db.get(SRMProduct,products['USD']['id']).current_quantity=999
    db.get(SRMProduct,products['USD']['id']).average_cost=999
    private=SRMProduct(organization_id=1,sku='QA-VAL-PRIVATE',item_name='Private valuation')
    workspace=PMSWorkspace(organization_id=1,name='Private valuation workspace')
    db.add_all([private,workspace]);db.flush()
    details=CatalogDetails(organization_id=1,product_id=private.id,workspace_id=workspace.id)
    balance=SRMInventoryBalance(organization_id=1,product_id=private.id,warehouse_id=warehouses[0]['id'],quantity=100,average_cost=100)
    db.add_all([details,balance]);own_workflow_records(db,workspace,details,balance);db.commit()
    viewer=auth_headers_for(client,db,'qa-valuation-viewer@example.com','srm_viewer',permissions=['srm_view'])
    endpoint='/api/v1/srm/inventory/reports/valuation'
    response=client.get(endpoint,headers=viewer)
    assert response.status_code==200,response.text
    data=response.json();rows={r['sku']:r for r in data['items']}
    assert data['total']==3
    assert set(rows)=={'QA-VAL-USD','QA-VAL-INR','QA-VAL-UNKNOWN'}
    assert Decimal(str(rows['QA-VAL-USD']['current_quantity']))==Decimal('5.6')
    assert Decimal(str(rows['QA-VAL-USD']['stock_value']))==Decimal('34.37')
    assert rows['QA-VAL-USD']['currency']=='USD'
    assert rows['QA-VAL-UNKNOWN']['currency'] is None
    assert Decimal(str(rows['QA-VAL-UNKNOWN']['stock_value']))==Decimal('3.13')
    assert data['unpriced_currency_items']==1
    totals={r['currency']:Decimal(str(r['total_inventory_value'])) for r in data['totals_by_currency']}
    assert totals=={'USD':Decimal('34.37'),'INR':Decimal('20.25')}
    assert data['currency'] is None and data['total_inventory_value'] is None
    assert data['valuation_basis']=='warehouse_balance_average_cost'
    assert client.get(endpoint).status_code==403
    denied=auth_headers_for(client,db,'qa-valuation-denied@example.com','srm_sales_executive',permissions=['srm_sales_order_view'])
    assert client.get(endpoint,headers=denied).status_code==403


def test_finance_valuation_returns_company_currency_and_exact_cents(client,db):
    from app.apps.fam.models import FAMCompanyFinancialSettings
    headers=inventory_headers(client,db,'qa-valuation-finance@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-VAL-FINANCE')
    db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one().base_currency='USD';db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=3.1,rate=5.2,suffix='QA-VAL-FINANCE')
    for endpoint in ['/inventory/valuation','/inventory/reports/valuation']:
        response=client.get('/api/v1/fam'+endpoint,headers=headers)
        assert response.status_code==200,response.text
        data=response.json()
        assert data['currency']=='USD'
        assert Decimal(str(data['total_inventory_value']))==Decimal('16.12')
        assert Decimal(str(data['items'][0]['stock_value']))==Decimal('16.12')
        assert data['valuation_basis']=='stock_item_current_average_cost'
