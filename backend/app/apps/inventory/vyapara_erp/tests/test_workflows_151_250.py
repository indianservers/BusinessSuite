from datetime import date
from decimal import Decimal
from io import BytesIO
import pytest
from openpyxl import load_workbook
from flask import template_rendered
from test_core import app_with_db, login, invoice_form, open_pos_session
from app.extensions import db
from app.models import Product, Customer, Warehouse, Sale, SalesReturn, CreditNote, Refund, InventoryLedger, POSSession
from app.services.invoice_service import create_or_update_invoice, issue_invoice, line_totals, record_invoice_payment
from app.services.stock_service import apply_stock_opening
from app.utils.excel_export import export_to_excel


@pytest.mark.parametrize('value',['=1+1','+SUM(A1)','-QA text','@QA text'])
def test_170_export_preserves_text_type_and_negative_numbers(value):
    output = export_to_excel(['Text','Number'],[[value,Decimal('-12.50')]],'QA')
    sheet = load_workbook(output,data_only=False).active
    assert sheet['A2'].data_type == 's'
    assert sheet['A2'].value == value
    assert sheet['B2'].data_type == 'n' and sheet['B2'].value == -12.5


def create_original(app, quantity=2, discount=0, paid=None):
    with app.app_context():
        product = db.session.get(Product,1)
        product.average_cost=product.purchase_price=600
        sale = Sale()
        form=invoice_form(Customer.query.first(),Warehouse.query.first())
        item={'product_id':1,'quantity':quantity,'rate':1000,'discount':discount,'tax_rate':18,**line_totals(quantity,1000,discount,18)}
        create_or_update_invoice(sale,form,[item],1); issue_invoice(sale,1)
        if paid: record_invoice_payment(sale,paid,date(2026,5,10),'Cash','QA-PAY','',1)
        db.session.commit()
        return sale.id


def return_form(ident,quantity,when='2026-06-01'):
    return {'return_date':when,'sale_id':ident,'customer_id':1,'warehouse_id':1,'restock':'on',
            'product_id[]':'1','quantity[]':str(quantity),'rate[]':'2000','tax_rate[]':'0','reason':'QA eligible original-linked return'}


def test_154_discounted_return_ignores_new_price(record_property):
    app=app_with_db(); ident=create_original(app,discount=10,paid=2124)
    with app.app_context():
        db.session.get(Product,1).sales_price=2000; db.session.commit()
    with app.test_client() as client:
        login(client); client.post('/sales/returns/create',data=return_form(ident,1))
        with app.app_context():
            row=SalesReturn.query.one()
            assert float(row.grand_total)==1062 and float(row.tax_total)==162
            assert row.sale_id==ident
            record_property('document_id',row.return_no)
            record_property('expected_vs_actual','credit=1062/1062; tax=162/162; original_discount_preserved=true')


def test_151_refund_cannot_exceed_collected_cash_or_customer_credit():
    app=app_with_db(); ident=create_original(app,paid=1000)
    with app.test_client() as client:
        login(client); client.post('/sales/returns/create',data=return_form(ident,2))
        with app.app_context():
            note=CreditNote.query.one(); returned=SalesReturn.query.one()
            note_id,return_id=note.id,returned.id
            assert Customer.query.one().outstanding==-1000
        form={'refund_date':'2026-06-01','customer_id':1,'credit_note_id':note_id,'sale_return_id':return_id,'amount':'1001','refund_mode':'Cash'}
        client.post('/sales/refunds',data=form)
        with app.app_context():
            assert Refund.query.count()==0
            assert Customer.query.one().outstanding==-1000
        form['amount']='1000'; client.post('/sales/refunds',data=form)
        client.post('/sales/refunds',data=form)
        with app.app_context():
            assert Refund.query.count()==1
            assert Customer.query.one().outstanding==0
            assert float(db.session.get(Product,1).current_stock)==10


def test_202_multiple_partial_returns_keep_original_dates_and_limit(record_property):
    app=app_with_db(); ident=create_original(app,quantity=10,paid=11800)
    with app.test_client() as client:
        login(client)
        for quantity,when in [(2,'2026-06-01'),(3,'2026-06-02'),(1,'2026-06-03')]:
            client.post('/sales/returns/create',data=return_form(ident,quantity,when))
        client.post('/sales/returns/create',data=return_form(ident,5,'2026-06-04'))
        with app.app_context():
            rows=SalesReturn.query.order_by(SalesReturn.id).all()
            assert len(rows)==3 and all(r.sale_id==ident for r in rows)
            assert sum(float(r.grand_total) for r in rows)==7080
            assert [str(r.return_date) for r in rows]==['2026-06-01','2026-06-02','2026-06-03']
            assert float(db.session.get(Product,1).current_stock)==6
            record_property('document_ids',','.join(r.return_no for r in rows))
            record_property('expected_vs_actual','returned=6/6; remaining=4/4; credit=7080/7080; excessive_return=rejected')


def test_184_stock_and_valuation_exports_use_warehouse_movements():
    app=app_with_db()
    with app.app_context():
        db.session.add(Warehouse(name='QA B',code='QA-B',branch_id=1)); db.session.flush()
        db.session.get(Product,1).current_stock=0
        apply_stock_opening(1,1,5,600,1,'QA-A')
        apply_stock_opening(1,2,8,600,2,'QA-B')
        db.session.commit()
    with app.test_client() as client:
        login(client)
        for warehouse,quantity in [(1,5),(2,8)]:
            response=client.get(f'/reports/stock?warehouse_id={warehouse}&export=xlsx')
            stock=load_workbook(BytesIO(response.data),data_only=True).active
            assert stock['C2'].value==quantity
            response=client.get(f'/reports/valuation?warehouse_id={warehouse}&export=xlsx')
            valuation=load_workbook(BytesIO(response.data),data_only=True).active
            assert valuation['D2'].value==quantity
            assert valuation['F2'].value==quantity*600
            html=client.get(f'/reports/valuation?warehouse_id={warehouse}').data
            assert f'warehouse_id={warehouse}'.encode() in html


def test_182_zero_revenue_has_cost_and_no_numeric_margin():
    app=app_with_db()
    with app.test_client() as client:
        login(client); open_pos_session(client)
        response=client.post('/pos/sale',json={'customer_id':1,'warehouse_id':1,'payment_mode':'Cash',
            'items':[{'product_id':1,'qty':1,'rate':0,'tax_rate':0}],'cash_tendered':0})
        assert response.status_code==200,response.json
        contexts=[]
        def capture(sender,template,context,**extra): contexts.append(context)
        template_rendered.connect(capture,app)
        try: assert client.get('/reports/profit-loss').status_code==200
        finally: template_rendered.disconnect(capture,app)
        assert float(contexts[-1]['profit'])==-100
        assert contexts[-1]['gross_margin'] is None


def test_221_fractional_service_and_234_noncash_closing(record_property):
    app=app_with_db()
    with app.app_context():
        service=Product(sku='QA-HOURS',name='QA hourly service',sales_price=800,track_inventory=False,current_stock=0,is_active=True)
        db.session.add(service); db.session.commit(); service_id=service.id
    with app.test_client() as client:
        login(client); client.post('/pos/open-session',data={'register_id':1,'opening_cash':1000})
        response=client.post('/pos/sale',json={'customer_id':1,'warehouse_id':1,'payment_mode':'Card','card_amount':1180,
            'items':[{'product_id':service_id,'qty':1.25,'rate':800,'tax_rate':18}]})
        assert response.status_code==200,response.json
        client.post('/pos/close-session',data={'closing_cash':1000})
        with app.app_context():
            sale=Sale.query.one(); drawer=POSSession.query.one()
            assert float(sale.subtotal)==1000 and float(sale.tax_total)==180 and float(sale.grand_total)==1180
            assert InventoryLedger.query.count()==0
            assert float(drawer.expected_closing_cash)==1000 and float(drawer.cash_difference)==0
            assert float(drawer.total_card)==1180
            record_property('document_id',sale.invoice_no)
            record_property('expected_vs_actual','service_base=1000/1000; tax=180/180; total=1180/1180; drawer=1000/1000; stock_movements=0/0')


def test_203_return_preserves_each_original_line_tax():
    app = app_with_db()
    with app.app_context():
        second = Product(sku="QA-203", name="Reduced tax goods", unit_id=1, tax_id=1,
                         warehouse_id=1, current_stock=10, purchase_price=50, sales_price=500)
        db.session.add(second); db.session.flush()
        second_id = second.id
        sale = Sale()
        form = invoice_form(Customer.query.first(), Warehouse.query.first())
        lines = [dict(product_id=1, quantity=1, rate=1000, discount=0, tax_rate=18,
                      **line_totals(1,1000,0,18)),
                 dict(product_id=second_id, quantity=1, rate=500, discount=0, tax_rate=5,
                      **line_totals(1,500,0,5))]
        create_or_update_invoice(sale, form, lines, 1); issue_invoice(sale,1)
        db.session.commit(); sale_id = sale.id
    with app.test_client() as client:
        login(client)
        form = return_form(sale_id,1)
        for field,values in {'product_id[]':['1',str(second_id)], 'quantity[]':['1','1'],
                             'rate[]':['9999','9999'], 'tax_rate[]':['0','0']}.items():
            form[field] = values
        client.post('/sales/returns/create',data=form)
        with app.app_context():
            returned = SalesReturn.query.one()
            assert float(returned.grand_total) == 1705
            assert sorted(float(line.tax_rate) for line in returned.items) == [5,18]
            assert sorted(float(line.tax_amount) for line in returned.items) == [25,180]


def test_218_override_and_236_later_master_change_preserve_invoice():
    app=app_with_db(); ident=create_original(app)
    with app.app_context():
        product=db.session.get(Product,1)
        assert float(product.sales_price)==150  # 1000 invoice override did not update master.
        product.sales_price=2500; product.tax_id=None; db.session.commit()
        sale=db.session.get(Sale,ident)
        line=sale.items[0]
        assert float(line.rate)==1000 and float(line.tax_rate)==18
        assert float(sale.grand_total)==2360 and float(sale.tax_total)==360


def test_206_pending_return_and_rejection_have_no_financial_effect():
    from app.models import AuditLog, CustomerLedger, Role, User
    app=app_with_db()
    with app.test_client() as client:
        login(client)
        form=return_form('',1); form['return_no']='QA-206-PENDING'
        client.post('/sales/returns/create',data=form)
        with app.app_context():
            returned=SalesReturn.query.one(); ident=returned.id
            assert returned.status=='Pending Approval'
            assert CustomerLedger.query.count()==CreditNote.query.count()==InventoryLedger.query.count()==0
            assert Customer.query.one().outstanding==0
            assert float(db.session.get(Product,1).current_stock)==10
        client.post(f'/sales/returns/{ident}/reject',data={'rejection_reason':''})
        with app.app_context():
            assert db.session.get(SalesReturn,ident).status=='Pending Approval'
        client.post(f'/sales/returns/{ident}/reject',data={'rejection_reason':'Outside policy'})
        assert client.post(f'/sales/returns/{ident}/reject',data={'rejection_reason':'Again'}).status_code==409
        with app.app_context():
            returned=db.session.get(SalesReturn,ident)
            assert returned.status=='Rejected' and 'Outside policy' in returned.notes
            assert CustomerLedger.query.count()==CreditNote.query.count()==InventoryLedger.query.count()==0
            audit=AuditLog.query.filter_by(action='Reject',module='SalesReturn').one()
            assert audit.user_id==1 and audit.new_data['reason']=='Outside policy'
            role=Role(name='QA reader'); db.session.add(role); db.session.flush()
            db.session.get(User,1).role_id=role.id; db.session.commit()
        assert client.post(f'/sales/returns/{ident}/reject',data={'rejection_reason':'Forbidden'}).status_code==403
