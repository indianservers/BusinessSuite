from datetime import date,timedelta
from decimal import Decimal
import pytest
from tests.fam_inventory_test_utils import create_stock_item,inventory_headers,post_opening_stock


@pytest.mark.parametrize('report',['stock-aging','fast-slow-moving'])
def test_inventory_activity_reports_ignore_unposted_and_non_sale_issues(client,db,report):
    from app.apps.fam.models import FAMStockMovement,FAMStockMovementLine
    from test_identity_utils import own_workflow_records
    headers=inventory_headers(client,db,'qa-stock-activity@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-ACTIVITY')
    post_opening_stock(client,headers,item,warehouse,quantity=10,rate=5.2,suffix='QA-ACTIVITY')
    today=date.today()
    seeds=[('draft','delivery_note',1,0,100),('cancelled','delivery_note',1,0,100),('posted','delivery_note',2,0,100),('posted','delivery_note',1,21,2),('posted','stock_transfer',1,14,100)]
    for index,(status,kind,company,days,quantity) in enumerate(seeds):
        movement=FAMStockMovement(company_id=company,movement_number=f'QA-ACTIVITY-{index}',movement_date=today-timedelta(days=days),movement_type=kind,status=status)
        db.add(movement);db.flush()
        line=FAMStockMovementLine(company_id=1,movement_id=movement.id,stock_item_id=item['id'],warehouse_id=warehouse['id'],quantity_out=quantity,rate=5.2,value=Decimal(str(quantity))*Decimal('5.2'))
        db.add(line);own_workflow_records(db,movement,line)
    db.commit()
    response=client.get('/api/v1/fam/inventory/reports/'+report,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['total']==1
    row=response.json()['items'][0]
    if report=='stock-aging':
        assert row['last_movement_date']==(today-timedelta(days=14)).isoformat()
        assert row['age_days']==14
    else:
        assert Decimal(str(row['quantity_out']))==Decimal('2')
        assert row['movement_class']=='slow'


def test_inventory_dead_stock_rejects_invalid_day_threshold_without_generating_report(client,db):
    from app.apps.fam.models import FAMInventoryReport
    headers=inventory_headers(client,db,'qa-dead-stock-threshold@example.com')
    before=db.query(FAMInventoryReport).count()
    for days in ['0','-1','36501','invalid']:
        response=client.get('/api/v1/fam/inventory/reports/dead-stock?days='+days,headers=headers)
        assert response.status_code==422,response.text
        assert any(error['loc'][-1]=='days' for error in response.json()['detail'])
    assert db.query(FAMInventoryReport).count()==before
