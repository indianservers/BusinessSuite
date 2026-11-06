from datetime import date
from werkzeug.datastructures import MultiDict
from test_core import app_with_db,login
from app.extensions import db
from app.models import Product,PurchaseOrder,PurchaseOrderItem,Batch,GoodsReceiptNote,InventoryLedger


def test_split_batch_receipt_reconciles_and_rolls_back_overreceipt():
    app=app_with_db()
    with app.app_context():
        product=db.session.get(Product,1);product.batch_tracking=True
        po=PurchaseOrder(po_no='QA-240',po_date=date.today(),supplier_id=1,warehouse_id=1,status='Draft')
        db.session.add(po);db.session.flush()
        item=PurchaseOrderItem(po_id=po.id,product_id=1,quantity=20,rate=100,tax_rate=18,line_total=2360)
        db.session.add(item);db.session.commit();pid=po.id;iid=item.id
        with app.test_client() as client:
            login(client)
            def payload(second):
                fields=[('grn_no','QA-240-RECEIPT'),('grn_date',date.today().isoformat()),('supplier_id','1'),('warehouse_id','1')]
                for q,b,e in [('12','QA-SHARED','2027-01-01'),(str(second),'QA-B','2027-02-01')]:
                    fields += [('product_id[]','1'),('po_item_id[]',str(iid)),('expected_qty[]','20'),('received_qty[]',q),('rate[]','100'),('tax_rate[]','18'),('batch_no[]',b),('manufacture_date[]','2026-01-01'),('expiry_date[]',e)]
                return MultiDict(fields)
            assert b'exceeds the remaining' in client.post(f'/purchase-orders/{pid}/grn',data=payload(9),follow_redirects=True).data
            db.session.expire_all();assert GoodsReceiptNote.query.count()==0 and Batch.query.count()==0 and InventoryLedger.query.count()==0
            response=client.post(f'/purchase-orders/{pid}/grn',data=payload(8),follow_redirects=True)
            assert b'stock updated' in response.data
            db.session.expire_all();assert float(db.session.get(PurchaseOrderItem,iid).received_qty)==20
            assert db.session.get(PurchaseOrder,pid).status=='Received'
            assert [(b.batch_no,float(b.quantity),b.expiry_date.isoformat()) for b in Batch.query.order_by(Batch.id)]==[('QA-SHARED',12,'2027-01-01'),('QA-B',8,'2027-02-01')]
            assert sum(float(m.value) for m in InventoryLedger.query.all())==2000
            p2=Product(sku='QA243',name='Second batch product',unit_id=1,warehouse_id=1,current_stock=0,average_cost=100,batch_tracking=True,is_active=True)
            db.session.add(p2);db.session.commit();p2id=p2.id
            data=payload(8);data['grn_no']='QA-243';data.setlist('product_id[]',[str(p2id)]);data.setlist('po_item_id[]',['']);data.setlist('received_qty[]',['12'])
            response=client.post('/grn/create',data=data,follow_redirects=True)
            assert b'stock updated' in response.data
            assert Batch.query.filter_by(batch_no='QA-SHARED').count()==2
            assert float(Batch.query.filter_by(product_id=1,batch_no='QA-SHARED').one().quantity)==12


def test_pos_batch_scope_quantity_and_atomic_depletion():
    from app.models import Sale,POSSession,AuditLog
    app=app_with_db()
    with app.app_context():
        p=db.session.get(Product,1);p.batch_tracking=True
        b=Batch(product_id=1,warehouse_id=1,batch_no='QA-SHARED',quantity=2,cost=100,expiry_date=date(2099,1,1))
        db.session.add(b);db.session.add(POSSession(session_no='QA-BATCH',opened_by=1,register_id=1,status='Open'));db.session.commit();bid=b.id
        with app.test_client() as client:
            login(client)
            payload={'request_id':'QA-BATCH-SALE','customer_id':1,'warehouse_id':1,'items':[{'product_id':1,'qty':1,'rate':150,'tax_rate':18}],'payment_mode':'Card','card_amount':177}
            assert client.post('/pos/sale',json=payload).status_code==400
            payload['items'][0]['batch_id']=bid
            payload['warehouse_id']=2
            assert client.post('/pos/sale',json=payload).status_code==400
            payload['warehouse_id']=1;payload['items']*=3;payload['card_amount']=531
            assert client.post('/pos/sale',json=payload).status_code==400
            db.session.expire_all();assert float(db.session.get(Batch,bid).quantity)==2 and Sale.query.count()==0
            payload['items']=payload['items'][:1];payload['card_amount']=177
            result=client.post('/pos/sale',json=payload);assert result.status_code==200,result.data
            db.session.expire_all();assert float(db.session.get(Batch,bid).quantity)==1
            assert client.post('/pos/sale',json=payload).status_code==200
            db.session.expire_all();assert float(db.session.get(Batch,bid).quantity)==1 and Sale.query.count()==1
            assert AuditLog.query.filter_by(action='Batch Sold',record_id=result.json['sale_id']).count()==1
