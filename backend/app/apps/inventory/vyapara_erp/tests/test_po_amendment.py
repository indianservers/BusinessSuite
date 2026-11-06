from datetime import date
from werkzeug.datastructures import MultiDict
from test_core import app_with_db,login
from app.extensions import db
from app.models import PurchaseOrder,PurchaseOrderItem,Supplier,GoodsReceiptNote,InventoryLedger


def test_supplier_change_line_removal_and_receipt_guards():
    app=app_with_db()
    with app.app_context():
        supplier=Supplier(supplier_code='QA-B',name='Supplier B');db.session.add(supplier);db.session.flush()
        po=PurchaseOrder(po_no='QA-238-239',po_date=date.today(),supplier_id=1,warehouse_id=1,status='Draft',terms='A terms',subtotal=300,tax_total=54,grand_total=354)
        db.session.add(po);db.session.flush()
        for n in range(3): db.session.add(PurchaseOrderItem(po_id=po.id,product_id=1,quantity=1,rate=100,discount=0,tax_rate=18,tax_amount=18,line_total=118))
        db.session.commit();pid=po.id;version=str(po.updated_at);sid=supplier.id
        with app.test_client() as client:
            login(client)
            data=MultiDict([('version',version),('supplier_id',str(sid)),('warehouse_id','1'),('terms','B terms'),('amendment_reason','Supplier and line correction')]+[(key,value) for n in range(2) for key,value in [('product_id[]','1'),('quantity[]','1'),('rate[]','100'),('discount[]','0'),('tax_rate[]','18')]])
            result=client.post(f'/purchase-orders/{pid}/edit',data=data,follow_redirects=True)
            assert b'Confirm revised supplier pricing' in result.data
            db.session.expire_all();assert db.session.get(PurchaseOrder,pid).supplier_id==1
            data.add('supplier_revalidated','on')
            result=client.post(f'/purchase-orders/{pid}/edit',data=data,follow_redirects=True)
            assert b'Purchase order amended' in result.data
            db.session.expire_all();po=db.session.get(PurchaseOrder,pid)
            assert po.supplier_id==sid and po.terms=='B terms'
            assert po.items.count()==2 and float(po.grand_total)==236
            assert InventoryLedger.query.count()==0
            assert b'Purchase order changed' in client.post(f'/purchase-orders/{pid}/edit',data=data,follow_redirects=True).data
            item=po.items.first()
            receipt=MultiDict([('grn_no','QA-GRN'),('grn_date',date.today().isoformat()),('supplier_id','1'),('warehouse_id','1'),('product_id[]','1'),('po_item_id[]',str(item.id)),('expected_qty[]','1'),('received_qty[]','1'),('rate[]','100'),('tax_rate[]','18')])
            assert b'Receipt supplier must match' in client.post(f'/purchase-orders/{pid}/grn',data=receipt,follow_redirects=True).data
            assert GoodsReceiptNote.query.count()==0
            receipt['supplier_id']=str(sid)
            client.post(f'/purchase-orders/{pid}/grn',data=receipt)
            assert GoodsReceiptNote.query.one().supplier_id==sid
            assert b'Only draft purchase orders' in client.get(f'/purchase-orders/{pid}/edit',follow_redirects=True).data
