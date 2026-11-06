from datetime import date
from test_core import app_with_db,login
from app.extensions import db
from app.models import Product,PurchaseOrder,PurchaseOrderItem
from app.routes.stock_routes import _reorder_position


def test_reorder_policy_counts_open_procurement_and_rechecks_stale_submissions():
    app=app_with_db()
    with app.app_context():
        p=db.session.get(Product,1);p.reorder_level=12;p.max_stock=30;p.preferred_supplier_id=1;db.session.commit()
        data={'supplier_id':1,'warehouse_id':1,'product_id[]':1}
        with app.test_client() as client:
            login(client)
            client.post('/stock/reorder-suggestions',data=data)
            po=PurchaseOrder.query.one();assert float(po.items.first().quantity)==20
            client.post('/stock/reorder-suggestions',data=data)
            assert PurchaseOrder.query.count()==1
            db.session.expire_all();p=db.session.get(Product,1)
            p.reorder_level=35;p.max_stock=40;db.session.commit()
            assert tuple(map(float,_reorder_position(p)))==(20,10)
            line=po.items.first();line.received_qty=8;p.current_stock=18;po.status='Partially Received';db.session.commit()
            assert tuple(map(float,_reorder_position(p)))==(12,10)
            line.received_qty=20;p.current_stock=30;po.status='Received';db.session.commit()
            assert tuple(map(float,_reorder_position(p)))==(0,10)
            client.post('/stock/reorder-suggestions',data=data)
            assert PurchaseOrder.query.count()==2
            assert float(PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first().items.first().quantity)==10
            assert tuple(map(float,_reorder_position(p)))==(10,0)
