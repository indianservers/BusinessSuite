from datetime import date
from io import BytesIO
from hashlib import sha256
from openpyxl import load_workbook
from test_core import app_with_db, login, invoice_form
from app.extensions import db
from app.models import (AdjustmentReview, AppSetting, BillOfMaterials, BOMItem, CustomView, InventoryLedger, ManufacturingOrder, ManufacturingSource, Permission, Product, Role, RolePermission, Sale, StockAdjustment, User, Warehouse)
from app.services.invoice_service import create_or_update_invoice, issue_invoice, line_totals


def test_245_evidence_gates_single_post_and_private_download():
    app=app_with_db()
    with app.app_context(),app.test_client() as client:
        login(client)
        client.post('/stock/adjustments/policy',data={'require_evidence':'on'})
        response=client.post('/stock/adjustments',data={'adjustment_no':'QA245','adjustment_date':'2026-11-06','warehouse_id':1,'reason':'Count difference','product_id[]':1,'qty_in[]':2,'qty_out[]':0,'rate[]':100},follow_redirects=True)
        assert b'Pending' in response.data
        review=AdjustmentReview.query.one();aid=review.adjustment_id
        assert float(db.session.get(Product,1).current_stock)==10 and InventoryLedger.query.count()==0
        assert b'Supporting evidence is required' in client.post(f'/stock/adjustments/{aid}/approve',follow_redirects=True).data
        for filename,content in [('bad.exe',b'MZbad'),('oversized.csv',b'a'*(2*1024*1024+1))]:
            response=client.post(f'/stock/adjustments/{aid}/evidence',data={'evidence':(BytesIO(content),filename)},follow_redirects=True)
            assert b'No attachment was saved' in response.data
            db.session.expire_all();assert not db.session.get(AdjustmentReview,aid).evidence
        content=b'Product,Count\nP1,12\n'
        client.post(f'/stock/adjustments/{aid}/evidence',data={'evidence':(BytesIO(content),'count-sheet.csv')})
        db.session.expire_all();assert db.session.get(AdjustmentReview,aid).evidence_sha256==sha256(content).hexdigest()
        assert client.get(f'/stock/adjustments/{aid}/evidence').data==content
        response=client.post(f'/stock/adjustments/{aid}/approve',follow_redirects=True)
        assert b'Posted' in response.data
        assert client.post(f'/stock/adjustments/{aid}/approve').status_code==409
        assert client.post(f'/stock/adjustments/{aid}/evidence',data={'evidence':(BytesIO(content),'new.csv')}).status_code==409
        db.session.expire_all();assert float(db.session.get(Product,1).current_stock)==12 and InventoryLedger.query.count()==1
        assert db.session.get(AdjustmentReview,aid).approved_by==1
        client.get('/logout')
        assert client.get(f'/stock/adjustments/{aid}/evidence').status_code==302


def test_247_component_sources_and_atomic_insufficiency():
    app=app_with_db()
    with app.app_context(),app.test_client() as client:
        b=Warehouse(name='Source B',code='B',branch_id=1);dest=Warehouse(name='Finished',code='FG',branch_id=1)
        db.session.add_all([b,dest]);db.session.flush()
        second=Product(sku='B',name='Component B',unit_id=1,warehouse_id=b.id,current_stock=10,average_cost=200,purchase_price=200,track_inventory=True,is_active=True)
        finished=Product(sku='FG',name='Finished goods',unit_id=1,warehouse_id=dest.id,current_stock=0,average_cost=0,track_inventory=True,is_active=True)
        db.session.add_all([second,finished]);db.session.flush()
        bom=BillOfMaterials(name='Two source BOM',product_id=finished.id,yield_qty=1,is_active=True)
        db.session.add(bom);db.session.flush()
        one=BOMItem(bom_id=bom.id,component_id=1,quantity=1,unit_id=1,waste_pct=0);two=BOMItem(bom_id=bom.id,component_id=second.id,quantity=2,unit_id=1,waste_pct=0)
        db.session.add_all([one,two]);db.session.commit();sid=second.id;fid=finished.id
        login(client)
        form={'mo_no':'QA247','bom_id':bom.id,'warehouse_id':dest.id,'planned_qty':2,'planned_date':'2026-11-06',f'source_{one.id}':1,f'source_{two.id}':b.id}
        client.post('/manufacturing/orders/create',data=form)
        order=ManufacturingOrder.query.one();oid=order.id
        assert ManufacturingSource.query.count()==2
        # A bad source must roll back the first component issue as well.
        source=ManufacturingSource.query.filter_by(order_id=oid,bom_item_id=two.id).one();source.warehouse_id=1;db.session.commit()
        client.post(f'/manufacturing/orders/{oid}/complete',data={'produced_qty':2})
        db.session.expire_all();assert InventoryLedger.query.count()==0 and float(db.session.get(Product,1).current_stock)==10
        db.session.get(ManufacturingSource,(oid,two.id)).warehouse_id=b.id;db.session.commit()
        client.post(f'/manufacturing/orders/{oid}/complete',data={'produced_qty':2})
        db.session.expire_all();assert db.session.get(ManufacturingOrder,oid).status=='Completed'
        entries=InventoryLedger.query.order_by(InventoryLedger.id).all()
        assert [(e.product_id,e.warehouse_id,float(e.qty_out),float(e.qty_in)) for e in entries]==[(1,1,2,0),(sid,b.id,4,0),(fid,dest.id,0,2)]
        assert float(db.session.get(Product,fid).average_cost)==500
        client.post(f'/manufacturing/orders/{oid}/complete',data={'produced_qty':2})
        assert InventoryLedger.query.count()==3


def test_249_saved_filter_access_intersection_and_export():
    app=app_with_db()
    with app.app_context(),app.test_client() as client:
        second=Warehouse(name='Restricted',code='R',branch_id=1);db.session.add(second);db.session.flush()
        for warehouse,number in [(1,'VISIBLE'),(second.id,'HIDDEN')]:
            sale=Sale(invoice_no=number,invoice_date=date(2026,11,6),customer_id=1,warehouse_id=warehouse,status='Paid',grand_total=118,paid_amount=118,balance_amount=0)
            db.session.add(sale)
        role=Role(name='Report reader');db.session.add(role);db.session.flush()
        for action in ['view','export']:
            permission=Permission(module='reports',action=action);db.session.add(permission);db.session.flush();db.session.add(RolePermission(role_id=role.id,permission_id=permission.id,granted=True))
        viewer=User(name='Narrow reader',email='qa-reader@example.com',role_id=role.id,is_active=True);viewer.set_password('QA-reader-123');db.session.add(viewer);db.session.commit();uid=viewer.id;wid=second.id
        login(client)
        client.post('/reports/access',data={'user_id':uid,'warehouse_ids':1})
        response=client.post('/reports/sales-summary/views',data={'name':'QA249','date_from':'2026-11-01','date_to':'2026-11-30','warehouse_id':1,'status':'Paid'},follow_redirects=True)
        view=CustomView.query.one();vid=view.id
        assert b'Applied: QA249' in response.data
        client.get('/logout');client.post('/login',data={'email':'qa-reader@example.com','password':'QA-reader-123'})
        response=client.get(f'/reports/sales-summary?view_id={vid}')
        assert response.status_code==200 and b'VISIBLE' in response.data and b'HIDDEN' not in response.data
        exported=client.get(f'/reports/sales-summary?view_id={vid}&export=xlsx')
        book=load_workbook(BytesIO(exported.data),data_only=True)
        assert book.active.max_row==2 and book.active['A2'].value=='VISIBLE'
        assert b'HIDDEN' not in client.get(f'/reports/sales-summary?warehouse_id={wid}').data
        assert client.post('/reports/sales-summary/views',data={'name':'Forbidden'}).status_code==403
        assert client.post('/reports/access',data={'user_id':uid,'warehouse_ids':wid}).status_code==403
