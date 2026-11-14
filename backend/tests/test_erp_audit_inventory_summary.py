from decimal import Decimal
import pytest
from tests.srm_test_utils import auth_headers_for
from tests.fam_inventory_test_utils import create_stock_item,inventory_headers,post_opening_stock


@pytest.mark.parametrize('report',['stock-summary','reorder'])
def test_sales_summary_and_reorder_use_visible_balances_and_positive_thresholds(client,db,superuser_headers,report):
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog_models import CatalogDetails
    from app.apps.project_management.models import PMSWorkspace
    from test_identity_utils import own_workflow_records
    def post(path,data):
        response=client.post('/api/v1/srm/inventory/'+path,headers=superuser_headers,json=data)
        assert response.status_code==201,response.text
        return response.json()
    warehouses=[post('warehouses',{'warehouse_code':f'QA-SUM-{i}','warehouse_name':f'Summary warehouse {i}'}) for i in range(2)]
    products={}
    for key,level,minimum,quantity in [('LOW',5,1,3.1),('AT',5,0,5),('MIN',0,4,2.5),('HIGH',5,10,6),('UNSET',0,0,0),('EMPTY',2,0,0),('HISTORICAL',2,0,1),('NO-TRACK',0,0,0),('PRIVATE',2,0,0)]:
        item=post('items',{'sku':'QA-SUM-'+key,'item_name':key,'reorder_level':level,'min_stock':minimum,'metadata_json':{'currency':'USD'}});products[key]=item
        if quantity:
            quantities=[1.1,2] if key=='LOW' else [quantity]
            for index,amount in enumerate(quantities):
                post('opening-stock',{'product_id':item['id'],'warehouse_id':warehouses[index]['id'],'quantity':amount,'rate':5.2})
    db.get(SRMProduct,products['LOW']['id']).current_quantity=999
    db.get(SRMProduct,products['LOW']['id']).average_cost=999
    for key in ['HISTORICAL','NO-TRACK']:db.get(SRMProduct,products[key]['id']).track_inventory=False
    workspace=PMSWorkspace(organization_id=1,name='Private summary workspace');db.add(workspace);db.flush()
    details=CatalogDetails(organization_id=1,product_id=products['PRIVATE']['id'],workspace_id=workspace.id);db.add(details);own_workflow_records(db,workspace,details);db.commit()
    viewer=auth_headers_for(client,db,'qa-summary-reader@example.com','srm_viewer',permissions=['srm_view'])
    endpoint='/api/v1/srm/inventory/reports/'+report
    response=client.get(endpoint,headers=viewer)
    assert response.status_code==200,response.text
    data=response.json();rows={r['sku'].removeprefix('QA-SUM-'):r for r in data['items']}
    low={'LOW','AT','MIN','EMPTY','HISTORICAL'}
    assert set(rows)==(low if report=='reorder' else low|{'HIGH','UNSET'})
    assert data['total']==len(rows)
    assert Decimal(str(rows['LOW']['current_quantity']))==Decimal('3.1')
    assert Decimal(str(rows['LOW']['stock_value']))==Decimal('16.12')
    assert rows['LOW']['currency']=='USD'
    assert all(rows[key]['is_low_stock'] for key in low)
    assert rows['EMPTY']['current_quantity']==0
    assert rows['LOW']['reserved_quantity'] is None
    assert rows['LOW']['available_quantity'] is None
    if report=='stock-summary':
        assert not rows['HIGH']['is_low_stock']
        assert not rows['UNSET']['is_low_stock']
    assert data['quantity_basis']=='scoped_sales_warehouse_on_hand'
    assert client.get(endpoint).status_code==403
    denied=auth_headers_for(client,db,'qa-summary-denied@example.com','srm_sales_executive',permissions=['srm_sales_order_view'])
    assert client.get(endpoint,headers=denied).status_code==403


@pytest.mark.parametrize('report',['stock-summary','reorder-alerts'])
def test_finance_summary_and_reorder_report_currency_and_reservation_values(client,db,report):
    from app.apps.fam.models import FAMCompanyFinancialSettings
    headers=inventory_headers(client,db,'qa-summary-finance@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-SUM-FINANCE',reorder_level=5)
    db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one().base_currency='USD';db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=3.1,rate=5.2,suffix='QA-SUM-FINANCE')
    response=client.get('/api/v1/fam/inventory/'+report,headers=headers)
    assert response.status_code==200,response.text
    data=response.json();assert data['currency']=='USD'
    assert data['total']==1
    row=data['items'][0]
    assert row['is_low_stock']
    assert Decimal(str(row['current_quantity']))==Decimal('3.1')
    assert Decimal(str(row['available_quantity']))==Decimal('3.1')
    assert row['reserved_quantity']==0
    assert Decimal(str(row['stock_value']))==Decimal('16.12')
