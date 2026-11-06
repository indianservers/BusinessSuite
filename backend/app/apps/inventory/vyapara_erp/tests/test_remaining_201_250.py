from datetime import date
import pytest
from test_core import app_with_db,login,open_pos_session
from app.extensions import db
from app.models import Product,Warehouse,PurchaseOrder,ManufacturingOrder,BillOfMaterials,BOMItem,InventoryLedger,SerialNumber,GoodsReceiptNote,AuditLog,Sale


def test_246_248_amend_unposted_order_and_post_exactly_once():
    app=app_with_db()
    with app.app_context():
        db.session.get(Product,1).average_cost=600
        fg=Product(sku='QA-FG',name='Finished',unit_id=1,warehouse_id=1,current_stock=0)
        db.session.add(fg);db.session.flush();fg_id=fg.id
        bom=BillOfMaterials(name='Quarter unit',product_id=fg_id,yield_qty=1,is_active=True)
        db.session.add(bom);db.session.flush();bom_id=bom.id
        db.session.add(BOMItem(bom_id=bom_id,component_id=1,quantity=0.25,waste_pct=0));db.session.commit()
    with app.test_client() as client:
        login(client)
        form=dict(mo_no='QA-248',bom_id=bom_id,warehouse_id=1,planned_qty=10,produced_qty=10,planned_date='2026-11-06',status='Completed')
        client.post('/manufacturing/orders/create',data=form)
        with app.app_context():
            order=ManufacturingOrder.query.one();ident=order.id
            assert order.status=='Draft' and order.produced_qty==0 and InventoryLedger.query.count()==0
        form['planned_qty']=6
        client.post(f'/manufacturing/orders/{ident}/edit',data=form)
        with app.app_context():
            assert ManufacturingOrder.query.one().planned_qty==6 and InventoryLedger.query.count()==0
        client.post(f'/manufacturing/orders/{ident}/complete',data={'produced_qty':7})
        with app.app_context(): assert InventoryLedger.query.count()==0
        client.post(f'/manufacturing/orders/{ident}/complete',data={'produced_qty':6})
        client.post(f'/manufacturing/orders/{ident}/complete',data={'produced_qty':6})
        assert client.post(f'/manufacturing/orders/{ident}/edit',data=form).status_code==409
        with app.app_context():
            assert float(db.session.get(Product,1).current_stock)==8.5
            fg=db.session.get(Product,fg_id)
            assert float(fg.current_stock)==6 and float(fg.average_cost)==150
            assert InventoryLedger.query.count()==2
            assert AuditLog.query.filter_by(module='ManufacturingOrder',action='Edit').one().user_id==1


@pytest.mark.parametrize('path',['/settings/warehouses/1/toggle','/masters/warehouses/1/delete','/settings/warehouses/1/edit'])
def test_241_stock_blocks_all_deactivation_paths(path):
    app=app_with_db()
    with app.test_client() as client:
        login(client)
        if '/masters/' in path: client.get(path)
        else: client.post(path,data={'name':'Main','code':'MAIN','branch_id':1})
        with app.app_context():
            assert db.session.get(Warehouse,1).status is True
            assert float(db.session.get(Product,1).current_stock)==10


def test_241_open_order_and_empty_warehouse_resolution():
    app=app_with_db()
    with app.app_context():
        wh=Warehouse(name='Other',code='OTHER',branch_id=1);db.session.add(wh);db.session.flush();ident=wh.id
        db.session.add(PurchaseOrder(po_no='QA-OPEN',po_date=date.today(),supplier_id=1,warehouse_id=ident,status='Draft'));db.session.commit()
    with app.test_client() as client:
        login(client);client.post(f'/settings/warehouses/{ident}/toggle')
        with app.app_context():
            assert db.session.get(Warehouse,ident).status
            PurchaseOrder.query.one().status='Cancelled';db.session.commit()
        client.post(f'/settings/warehouses/{ident}/toggle')
        with app.app_context(): assert not db.session.get(Warehouse,ident).status


def test_244_normalization_duplicate_receipt_rollback_and_serial_sale():
    app=app_with_db()
    with app.test_client() as client:
        login(client)
        client.post('/stock/serial-numbers',data={'product_id':1,'warehouse_id':1,'serial_no':'  qa-AbC  '})
        response=client.post('/stock/serial-numbers',data={'product_id':1,'warehouse_id':1,'serial_no':'Qa-abc'},follow_redirects=True)
        assert b'Serial number already exists' in response.data
        with app.app_context():
            serial=SerialNumber.query.one();ident=serial.id
            assert serial.serial_no=='QA-ABC'
            db.session.get(Product,1).serial_tracking=True;db.session.commit()
        client.post('/grn/create',data={'grn_no':'QA-DUP','grn_date':'2026-11-06','supplier_id':1,'warehouse_id':1,'product_id[]':'1','po_item_id[]':'','expected_qty[]':'1','received_qty[]':'1','rate[]':'100','tax_rate[]':'18','serial_numbers[]':'qa-abc'})
        with app.app_context():
            assert GoodsReceiptNote.query.count()==0 and InventoryLedger.query.count()==0
            assert float(db.session.get(Product,1).current_stock)==10
        open_pos_session(client)
        payload={'request_id':'QA-SERIAL','customer_id':1,'warehouse_id':1,'items':[{'product_id':1,'qty':1,'rate':150,'tax_rate':18}],'payment_mode':'Cash','cash_tendered':177}
        assert client.post('/pos/sale',json=payload).status_code==400
        payload['items'][0]['serial_id']=ident
        result=client.post('/pos/sale',json=payload)
        assert result.status_code==200,result.json
        assert client.post('/pos/sale',json=payload).status_code==200
        payload['request_id']='QA-REUSE'
        assert client.post('/pos/sale',json=payload).status_code==400
        with app.app_context():
            serial=db.session.get(SerialNumber,ident)
            assert serial.status=='Sold' and serial.sale_id==result.json['sale_id']
            assert Sale.query.count()==1 and float(db.session.get(Product,1).current_stock)==9


def test_237_po_print_and_receipt_use_destination_warehouse():
    app=app_with_db()
    with app.app_context():
        wh=Warehouse(name='Dock B',code='DOCK-B',address='22 Receiving Road',branch_id=1)
        db.session.add(wh);db.session.commit();ident=wh.id
    with app.test_client() as client:
        login(client)
        client.post('/purchase-orders/create',data={'po_no':'QA-237','po_date':'2026-11-06','supplier_id':1,'warehouse_id':ident,'product_id[]':'1','quantity[]':'2','rate[]':'600','discount[]':'0','tax_rate[]':'18'})
        with app.app_context(): po_id=PurchaseOrder.query.one().id;line_id=PurchaseOrder.query.one().items[0].id
        printed=client.get(f'/purchase-orders/{po_id}/print')
        assert b'Deliver to' in printed.data and b'Dock B' in printed.data and b'22 Receiving Road' in printed.data
        client.post(f'/purchase-orders/{po_id}/grn',data={'grn_no':'QA-237-GRN','grn_date':'2026-11-06','warehouse_id':ident,'product_id[]':'1','po_item_id[]':str(line_id),'expected_qty[]':'2','received_qty[]':'2','rate[]':'600','tax_rate[]':'18'})
        with app.app_context():
            assert GoodsReceiptNote.query.one().warehouse_id==ident
            assert InventoryLedger.query.one().warehouse_id==ident
            assert float(InventoryLedger.query.one().qty_in)==2
