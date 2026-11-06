from datetime import date
from test_core import app_with_db,login
from test_workflows_151_250 import create_original
from app.extensions import db
from app.models import CreditNote,Customer,InventoryLedger,PaymentReceived,Product,Sale,SalesReturn


def test_214_copy_then_205_financial_credit_preserve_physical_and_settlement_history():
    app=app_with_db();source_id=create_original(app,quantity=1,paid=1180)
    with app.app_context(),app.test_client() as client:
        source=db.session.get(Sale,source_id);source.irn='QA-OLD-IRN';source.razorpay_payment_id='QA-OLD-PAYMENT';db.session.commit()
        login(client)
        response=client.post(f'/invoices/{source_id}/copy',follow_redirects=True)
        assert b'New unpaid draft created' in response.data
        copied=Sale.query.order_by(Sale.id.desc()).first();cid=copied.id
        assert copied.status=='Draft' and float(copied.paid_amount)==0 and float(copied.balance_amount)==1180
        assert copied.issued_at is None and copied.irn is None and copied.razorpay_payment_id is None
        assert copied.invoice_no != source.invoice_no and copied.items.count()==1
        assert PaymentReceived.query.count()==1 and InventoryLedger.query.count()==1
        client.post(f'/invoices/{cid}/issue')
        db.session.expire_all();assert float(db.session.get(Product,1).current_stock)==8
        response=client.post('/credit-notes/create',data={'cn_date':date.today().isoformat(),'customer_id':1,'sale_id':cid,'adjustment_type':'Price','reason':'Authorized concession; goods retained','product_id[]':1,'quantity[]':1,'rate[]':100,'tax_rate[]':18},follow_redirects=True)
        assert b'Credit note issued' in response.data
        note=CreditNote.query.one();nid=note.id
        assert float(note.grand_total)==118 and float(note.tax_total)==18
        other=Customer(customer_code='OTHER',name='Other customer');db.session.add(other);db.session.flush()
        wrong=Sale(invoice_no='WRONG-CUSTOMER',invoice_date=date.today(),customer_id=other.id,warehouse_id=1,status='Issued',grand_total=1000,balance_amount=1000,paid_amount=0)
        db.session.add(wrong);db.session.commit()
        assert b'same customer' in client.post(f'/credit-notes/{nid}/apply',data={'sale_id':wrong.id,'amount':118},follow_redirects=True).data
        assert b'cannot exceed' in client.post(f'/credit-notes/{nid}/apply',data={'sale_id':cid,'amount':119},follow_redirects=True).data
        client.post(f'/credit-notes/{nid}/apply',data={'sale_id':cid,'amount':118})
        db.session.expire_all();assert float(db.session.get(Sale,cid).balance_amount)==1062
        assert float(db.session.get(Product,1).current_stock)==8 and InventoryLedger.query.count()==2 and SalesReturn.query.count()==0
        assert Customer.query.get(1).outstanding==1062
        client.post(f'/invoices/{cid}/payments',data={'payment_date':date.today().isoformat(),'amount':1062,'payment_mode':'Cash','reference_no':'QA-214-NEW-RECEIPT'})
        db.session.expire_all();assert db.session.get(Sale,cid).status=='Paid'
        assert [float(p.amount) for p in PaymentReceived.query.order_by(PaymentReceived.id)]==[1180,1062]
        assert Customer.query.get(1).outstanding==0


def test_201_shipping_only_credit_and_refund_leave_goods_and_reference_intact():
    from app.models import CustomerLedger,Refund
    app=app_with_db()
    with app.app_context(),app.test_client() as client:
        shipping=Product(sku='SHIP',name='Shipping service',unit_id=1,tax_id=1,track_inventory=False,current_stock=0,sales_price=100,is_active=True)
        db.session.add(shipping);db.session.commit();pid=shipping.id
        from app.services.invoice_service import create_or_update_invoice,issue_invoice,line_totals,record_invoice_payment
        from test_core import invoice_form
        sale=Sale();form=invoice_form(Customer.query.first(),__import__('app.models',fromlist=['Warehouse']).Warehouse.query.first())
        lines=[dict(product_id=product,quantity=1,rate=rate,discount=0,tax_rate=18,**line_totals(1,rate,0,18)) for product,rate in [(1,1000),(pid,100)]]
        create_or_update_invoice(sale,form,lines,1);issue_invoice(sale,1);record_invoice_payment(sale,1298,date.today(),'Card','QA201','',1);db.session.commit();sid=sale.id
        login(client)
        client.post('/credit-notes/create',data={'cn_date':date.today().isoformat(),'customer_id':1,'sale_id':sid,'adjustment_type':'Other','reason':'Shipping charge refund only','product_id[]':pid,'quantity[]':1,'rate[]':100,'tax_rate[]':18})
        note=CreditNote.query.one();nid=note.id
        assert float(note.tax_total)==18 and float(note.grand_total)==118
        assert b'cannot exceed' in client.post(f'/credit-notes/{nid}/refund',data={'amount':119},follow_redirects=True).data
        client.post(f'/credit-notes/{nid}/refund',data={'amount':118,'refund_mode':'Bank'})
        assert b'cannot exceed' in client.post(f'/credit-notes/{nid}/refund',data={'amount':118},follow_redirects=True).data
        db.session.expire_all();refund=Refund.query.one()
        assert float(refund.amount)==118 and float(db.session.get(Product,1).current_stock)==9
        assert InventoryLedger.query.count()==1 and SalesReturn.query.count()==0
        ledger=CustomerLedger.query.filter_by(reference_type='Refund').one()
        assert ledger.reference_id==refund.id and float(ledger.balance)==0 and Customer.query.get(1).outstanding==0
        repeated=client.post('/credit-notes/create',data={'cn_date':date.today().isoformat(),'customer_id':1,'sale_id':sid,'adjustment_type':'Other','reason':'Repeated shipping credit','product_id[]':pid,'quantity[]':1,'rate[]':100,'tax_rate[]':0},follow_redirects=True)
        assert b'Cumulative credits cannot exceed' in repeated.data
        assert CreditNote.query.count()==1 and Refund.query.count()==1
