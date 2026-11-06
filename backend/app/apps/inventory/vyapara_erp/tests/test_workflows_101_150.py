from datetime import date
import pytest
from werkzeug.exceptions import BadRequest
from test_core import app_with_db, invoice_form, login, open_pos_session
from app.extensions import db
from app.models import Product, Customer, Warehouse, Sale, InventoryLedger, POSSession, StockTransfer
from app.services.invoice_service import create_or_update_invoice, issue_invoice, cancel_invoice, record_invoice_payment, line_totals


@pytest.mark.parametrize("mixed", [False, True])
def test_101_102_service_invoice_only_issues_physical_goods(mixed, record_property):
    app = app_with_db()
    with app.app_context():
        service = Product(sku="QA-SVC", name="QA Service", sales_price=3000 if mixed else 5000,
                          unit_id=1, tax_id=1, track_inventory=False, current_stock=0, is_active=True)
        db.session.add(service); db.session.flush()
        specs = [(service.id, 1, 3000 if mixed else 5000)] + ([(1, 2, 1000)] if mixed else [])
        items = [{"product_id": p, "quantity": q, "rate": r, "discount": 0, "tax_rate": 18, **line_totals(q, r, 0, 18)} for p,q,r in specs]
        sale = Sale()
        form = invoice_form(Customer.query.first(), Warehouse.query.first())
        form["invoice_no"] = "QA-101-MIX" if mixed else "QA-101-SVC"
        create_or_update_invoice(sale, form, items, 1)
        issue_invoice(sale, 1)
        record_invoice_payment(sale, 5900, date.today(), "Cash", "QA-101-PAY", "", 1)
        db.session.commit(); db.session.expire_all()
        assert float(sale.grand_total) == 5900
        assert float(sale.balance_amount) == 0
        assert float(service.current_stock) == 0
        assert InventoryLedger.query.filter_by(product_id=service.id).count() == 0
        assert float(db.session.get(Product, 1).current_stock) == (8 if mixed else 10)
        from app.routes.sales_routes import build_picklist
        from flask_login import login_user
        from app.models import User
        with app.test_request_context():
            login_user(db.session.get(User, 1))
            if mixed:
                picklist = build_picklist(sale, "sale")
                db.session.flush()
                assert [(line.product_id, float(line.quantity)) for line in picklist.items] == [(1, 2)]
            else:
                with pytest.raises(ValueError, match="Service-only"):
                    build_picklist(sale, "sale")
        record_property("document_id", sale.invoice_no)
        record_property("expected_vs_actual", f"total=5900/5900; outstanding=0/0; service_movements=0/0; goods_stock={8 if mixed else 10}")


def test_111_customer_terms_calculate_due_date_and_allow_override(record_property):
    app = app_with_db()
    with app.app_context():
        customer = Customer.query.first(); customer.payment_terms = 30
        form = invoice_form(customer, Warehouse.query.first())
        form.update(invoice_no="QA-111-TERMS", invoice_date="2027-01-15", due_date="")
        item = {"product_id": 1, "quantity": 1, "rate": 1000, "discount": 0, "tax_rate": 18, **line_totals(1, 1000, 0, 18)}
        sale = Sale()
        create_or_update_invoice(sale, form, [item], 1)
        db.session.commit(); db.session.expire_all()
        assert sale.due_date == date(2027, 2, 14)
        form["due_date"] = "2027-02-20"
        create_or_update_invoice(sale, form, [item], 1)
        db.session.commit(); db.session.expire_all()
        assert sale.due_date == date(2027, 2, 20)
        record_property("document_id", sale.invoice_no)
        record_property("expected_vs_actual", "default_due=2027-02-14/2027-02-14; override=2027-02-20/2027-02-20")


@pytest.mark.parametrize("quantity", ["0", "-2"])
def test_127_transfer_rejects_invalid_quantities_without_movements(quantity):
    app = app_with_db()
    with app.app_context():
        db.session.add(Warehouse(name="QA B", code="QA-B", branch_id=1)); db.session.commit()
    with app.test_client() as client:
        login(client)
        client.post("/stock/transfers/create", data={"transfer_no":"QA-127-INVALID", "transfer_date":date.today().isoformat(),
            "from_warehouse_id":1,"to_warehouse_id":2,"status":"Sent", "product_id[]":"1","quantity[]":quantity,"rate[]":"600"})
        with app.app_context():
            assert StockTransfer.query.count() == InventoryLedger.query.count() == 0
            assert float(db.session.get(Product, 1).current_stock) == 10


def test_146_cash_change_and_closed_session_stays_stable(record_property):
    app = app_with_db()
    with app.test_client() as client:
        login(client); open_pos_session(client)
        response = client.post("/pos/sale", json={"request_id":"QA-146", "customer_id":1,"warehouse_id":1,
            "items":[{"product_id":1,"qty":1,"rate":1000,"tax_rate":18}],"payment_mode":"Cash","cash_tendered":2000})
        assert response.status_code == 200, response.json
        assert response.json["change_due"] == 820
        receipt = client.get(f"/pos/receipt/{response.json['sale_id']}")
        assert b"Change" in receipt.data and b"820.00" in receipt.data
        client.post("/pos/close-session", data={"closing_cash":1280})
        with app.app_context():
            session = POSSession.query.one()
            assert float(session.total_cash) == 1180
            assert float(session.expected_closing_cash) == 1280
            assert float(session.cash_difference) == 0
            assert float(Sale.query.one().pos_change_due) == 820
            record_property("document_id",response.json["invoice_no"])
            record_property("expected_vs_actual","total=1180/1180; change=820/820; retained_cash=1180/1180; closing=1280/1280")


def test_127_129_same_warehouse_rejected_and_staged_transfer_posts_once(record_property):
    app = app_with_db()
    with app.app_context():
        db.session.add(Warehouse(name="QA B", code="QA-B", branch_id=1)); db.session.commit()
    with app.test_client() as client:
        login(client)
        form = {"transfer_no":"QA-129", "transfer_date":date.today().isoformat(),"from_warehouse_id":1,
                "to_warehouse_id":1,"status":"Draft","product_id[]":"1","quantity[]":"5","rate[]":"600"}
        client.post("/stock/transfers/create",data=form)
        with app.app_context():
            assert StockTransfer.query.count() == InventoryLedger.query.count() == 0
        form["to_warehouse_id"] = 2
        client.post("/stock/transfers/create",data=form)
        with app.app_context():
            ident = StockTransfer.query.one().id
        client.post(f"/stock/transfers/{ident}/send")
        client.post(f"/stock/transfers/{ident}/send")
        with app.app_context():
            assert StockTransfer.query.one().status == "Sent"
            assert float(db.session.get(Product, 1).current_stock) == 5
            assert InventoryLedger.query.count() == 1
        client.post(f"/stock/transfers/{ident}/receive")
        client.post(f"/stock/transfers/{ident}/receive")
        with app.app_context():
            assert StockTransfer.query.one().status == "Received"
            assert float(db.session.get(Product, 1).current_stock) == 10
            assert InventoryLedger.query.count() == 2
            assert [(m.warehouse_id, float(m.qty_in), float(m.qty_out)) for m in InventoryLedger.query.order_by(InventoryLedger.id).all()] == [(1, 0, 5), (2, 5, 0)]
            record_property("document_id","QA-129")
            record_property("expected_vs_actual","dispatch_available=5/5; in_transit=5/5; received_company_stock=10/10; movements=2/2")


def test_141_cancelled_manufacturing_order_cannot_post():
    from app.models import BillOfMaterials, BOMItem, ManufacturingOrder
    app = app_with_db()
    with app.app_context():
        finished = Product(sku="QA-141-FG",name="QA FG",warehouse_id=1,current_stock=0)
        db.session.add(finished); db.session.flush()
        bom = BillOfMaterials(product_id=finished.id,name="QA Cancelled BOM",yield_qty=1)
        db.session.add(bom); db.session.flush()
        db.session.add(BOMItem(bom_id=bom.id,component_id=1,quantity=2))
        order = ManufacturingOrder(mo_no="QA-141",bom_id=bom.id,warehouse_id=1,planned_qty=2,status="Cancelled")
        db.session.add(order); db.session.commit()
        ident, product_id = order.id, finished.id
    with app.test_client() as client:
        login(client); client.post(f"/manufacturing/orders/{ident}/complete")
        with app.app_context():
            assert db.session.get(ManufacturingOrder,ident).status == "Cancelled"
            assert float(db.session.get(Product,1).current_stock) == 10
            assert float(db.session.get(Product,product_id).current_stock) == 0
            assert InventoryLedger.query.count() == 0


def test_147_held_bill_stays_with_original_open_session(record_property):
    app = app_with_db()
    with app.test_client() as client:
        login(client); open_pos_session(client)
        held = client.post("/pos/hold",json={"customer_id":1,"items":[{"product_id":1,"qty":1,"rate":1000}]}).json
        client.post("/pos/close-session",data={"closing_cash":100})
        open_pos_session(client)
        assert client.get(f"/pos/held/{held['id']}/json").status_code == 403
        with app.app_context():
            assert Sale.query.count() == InventoryLedger.query.count() == 0
            sessions = POSSession.query.order_by(POSSession.id).all()
            assert sessions[0].status == "Closed"
            assert float(sessions[0].total_sales) == 0
            record_property("document_id",held["hold_no"])
            record_property("expected_vs_actual","cross_session_recall=403/403; closed_sales=0/0; stock_movements=0/0")


def test_149_cashier_cannot_reuse_another_cashiers_open_session(record_property):
    from app.models import User
    app = app_with_db()
    with app.app_context():
        second = User(name="QA Cashier B",email="cashier-b@example.com",role_id=1,is_active=True)
        second.set_password("admin123")
        db.session.add(second); db.session.commit()
    first, second = app.test_client(), app.test_client()
    login(first); open_pos_session(first)
    with first.session_transaction() as state:
        original_session = state["pos_session_id"]
    second.post("/login",data={"email":"cashier-b@example.com","password":"admin123"})
    # A stale session cookie must not grant access to the previous cashier's drawer.
    with second.session_transaction() as state:
        state["pos_session_id"] = original_session
    response = second.post("/pos/sale",json={"customer_id":1,"warehouse_id":1,
        "items":[{"product_id":1,"qty":1,"rate":1000,"tax_rate":18}],"payment_mode":"Cash","cash_tendered":1180})
    assert response.status_code == 400, response.json
    with app.app_context():
        assert Sale.query.count() == InventoryLedger.query.count() == 0
        assert float(db.session.get(POSSession,original_session).total_sales) == 0
        record_property("document_id",db.session.get(POSSession,original_session).session_no)
        record_property("expected_vs_actual","foreign_drawer_sale=400/400; sales=0/0; inventory_movements=0/0; original_drawer_total=0/0")

def test_101_service_fulfillment_actions_blocked_and_cancellation_does_not_restock():
    from app.models import Picklist, DeliveryBill
    app = app_with_db()
    with app.app_context():
        service = Product(sku="QA-SERVICE-CANCEL",name="QA Service",sales_price=5000,
                          unit_id=1,tax_id=1,track_inventory=False,current_stock=0,is_active=True)
        db.session.add(service); db.session.flush()
        item = {"product_id":service.id,"quantity":1,"rate":5000,"discount":0,"tax_rate":18,**line_totals(1,5000,0,18)}
        sale = Sale()
        create_or_update_invoice(sale,invoice_form(Customer.query.first(),Warehouse.query.first()),[item],1)
        issue_invoice(sale,1); db.session.commit()
        ident, product_id = sale.id, service.id
    with app.test_client() as client:
        login(client)
        assert client.post(f"/sales/{ident}/delivery-bill").status_code == 400
        client.post("/sales/picklists/create",data={"sale_id":ident})
        details = client.get(f"/invoices/{ident}")
        assert b"Create Delivery Bill" not in details.data
        assert b"Generate Picklist" not in details.data
        with app.app_context():
            assert Picklist.query.count() == DeliveryBill.query.count() == 0
            cancel_invoice(db.session.get(Sale,ident),"QA cancellation",1)
            db.session.commit(); db.session.expire_all()
            assert float(db.session.get(Product,product_id).current_stock) == 0
            assert InventoryLedger.query.count() == 0
