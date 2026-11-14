from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from tests.srm_test_utils import auth_headers_for
from test_identity_utils import own_workflow_records


@pytest.mark.parametrize('report',['stock-aging','dead-stock','fast-slow-moving'])
def test_sales_activity_reports_use_visible_movements_not_catalog_totals(client, db, superuser_headers, report):
    from app.apps.srm.models import SRMProduct, SRMInventoryMovement
    from app.shared.catalog_models import CatalogDetails
    from app.apps.project_management.models import PMSWorkspace
    headers=superuser_headers
    today=date.today()
    def post(path,payload):
        response=client.post('/api/v1/srm/inventory/'+path,headers=headers,json=payload)
        assert response.status_code==201,response.text
        return response.json()
    warehouses=[post('warehouses',{'warehouse_code':f'QA-ACT-{i}','warehouse_name':f'Activity warehouse {i}'}) for i in range(2)]
    products={key:post('items',{'sku':'QA-ACT-'+key,'item_name':key}) for key in ['NORMAL','FAST','OLD','NONE']}
    def day(days):return (today-timedelta(days=days)).isoformat()
    for key,quantity,age in [('NORMAL',25,45),('FAST',50,45),('OLD',5,120)]:
        post('opening-stock',{'product_id':products[key]['id'],'warehouse_id':warehouses[0]['id'],'quantity':quantity,'rate':5.2,'movement_date':day(age)})
    for key,quantity,age in [('NORMAL',2,21),('FAST',10,7)]:
        post('stock-movements',{'product_id':products[key]['id'],'warehouse_id':warehouses[0]['id'],'quantity':quantity,'movement_type':'stock_out','rate':5.2,'movement_date':day(age)})
    post('stock-transfers',{'product_id':products['NORMAL']['id'],'from_warehouse_id':warehouses[0]['id'],'to_warehouse_id':warehouses[1]['id'],'quantity':1,'rate':5.2,'movement_date':day(14)})
    for index,(kind,quantity,org,age) in enumerate([('pos_sale',Decimal('0.75'),1,21),('sales_order_issue',Decimal('1.25'),1,21),('production_consumption',100,1,30),('delivery_note',999,2,0)]):
        row=SRMInventoryMovement(organization_id=org,movement_number=f'QA-ACT-SOURCE-{index}',movement_type=kind,movement_date=today-timedelta(days=age),product_id=products['NORMAL']['id'],warehouse_id=warehouses[0]['id'],quantity_out=quantity)
        db.add(row);own_workflow_records(db,row)
    # Catalog-wide cached quantity cannot be substituted for movement history.
    db.get(SRMProduct,products['NORMAL']['id']).current_quantity=999
    for label,attributes in [('FOREIGN',{'organization_id':2}),('DELETED',{'deleted_at':datetime(2026,1,1)}),('SERVICE',{'product_type':'service'}),('BRANCH',{'metadata_json':{'catalog_branches':{'default':False,'overrides':{}}}}),('PRIVATE',{})]:
        item=SRMProduct(**{'organization_id':1,'sku':'QA-ACT-'+label,'item_name':label,'product_type':'stock',**attributes})
        db.add(item);db.flush()
        movement=SRMInventoryMovement(organization_id=1,movement_number='QA-HIDDEN-'+label,movement_type='stock_out',movement_date=today,product_id=item.id,warehouse_id=warehouses[0]['id'],quantity_out=100)
        db.add(movement);own_workflow_records(db,movement)
        if label=='PRIVATE':
            workspace=PMSWorkspace(organization_id=1,name='Private activity');db.add(workspace);db.flush()
            details=CatalogDetails(organization_id=1,product_id=item.id,workspace_id=workspace.id);db.add(details);own_workflow_records(db,workspace,details)
    db.commit()
    viewer=auth_headers_for(client,db,'qa-activity-viewer@example.com','srm_viewer',permissions=['srm_view'])
    endpoint='/api/v1/srm/inventory/reports/'+report
    response=client.get(endpoint,headers=viewer)
    assert response.status_code==200,response.text
    data=response.json();rows={row['sku']:row for row in data['items']}
    assert data['as_of']==today.isoformat()
    if report=='dead-stock':
        assert data['threshold_days']==90
        assert set(rows)=={'QA-ACT-OLD','QA-ACT-NONE'}
        assert rows['QA-ACT-OLD']['age_days']==120
        assert rows['QA-ACT-NONE']['age_days'] is None
        assert client.get(endpoint+'?days=7',headers=viewer).json()['total']==4
        for value in ['0','-1','36501','wrong']:
            assert client.get(endpoint+'?days='+value,headers=viewer).status_code==422
    else:
        assert set(rows)=={'QA-ACT-NORMAL','QA-ACT-FAST','QA-ACT-OLD','QA-ACT-NONE'}
        if report=='stock-aging':
            assert rows['QA-ACT-NORMAL']['last_movement_date']==day(14)
            assert rows['QA-ACT-NORMAL']['age_days']==14
            assert rows['QA-ACT-NONE']['last_movement_date'] is None
            assert rows['QA-ACT-NONE']['age_days'] is None
        else:
            assert Decimal(str(rows['QA-ACT-NORMAL']['quantity_out']))==Decimal('4')
            assert rows['QA-ACT-NORMAL']['movement_class']=='slow'
            assert Decimal(str(rows['QA-ACT-FAST']['quantity_out']))==10
            assert rows['QA-ACT-FAST']['movement_class']=='fast'
            assert rows['QA-ACT-NONE']['quantity_out']==0
            assert rows['QA-ACT-NONE']['movement_class']=='non_moving'
            assert data['items'][0]['sku']=='QA-ACT-FAST'
            assert data['fast_threshold']==10
    assert data['total']==len(rows)
    assert client.get(endpoint).status_code==403
    denied=auth_headers_for(client,db,'qa-activity-denied@example.com','srm_sales_executive',permissions=['srm_sales_order_view'])
    assert client.get(endpoint,headers=denied).status_code==403
