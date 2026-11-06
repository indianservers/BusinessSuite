"""Isolated acceptance checks for the second commercial workflow batch."""
from datetime import date
from decimal import Decimal

import pytest

from test_core import app_with_db, login, open_pos_session, invoice_form
from app.extensions import db
from app.models import Customer, Product, Sale, SaleItem, PaymentReceived, POSSession, InventoryLedger, SalesReturn
from app.services.invoice_service import create_or_update_invoice, issue_invoice, line_totals
from app.services.stock_service import apply_purchase_item


def sale_payload(request_id="QA-53"):
    return {"request_id": request_id, "customer_id": 1, "warehouse_id": 1,
        "items": [{"product_id": 1, "qty": 2, "rate": 1000, "tax_rate": 18}],
        "payment_mode": "Cash", "cash_tendered": 2360}


def test_53_retry_without_response_cookie_does_not_repost(record_property):
    app = app_with_db()
    with app.test_client() as client:
        login(client)
        open_pos_session(client)
        old_cookie = client.get_cookie("session").value
        first = client.post("/pos/sale", json=sale_payload())
        assert first.status_code == 200, first.json
        # The server committed, but the response (including Set-Cookie) was lost.
        client.set_cookie("session", old_cookie)
        retry = client.post("/pos/sale", json=sale_payload())
        assert retry.status_code in (200, 409), retry.json
        with app.app_context():
            assert Sale.query.count() == PaymentReceived.query.count() == InventoryLedger.query.count() == 1
            assert float(db.session.get(Product, 1).current_stock) == 8
            assert float(POSSession.query.first().total_sales) == 2360
            record_property("document_id", first.json["invoice_no"])
            record_property("expected_vs_actual", "sales=1/1; receipts=1/1; stock_issues=1/1; stock=8/8; session_sales=2360/2360")


@pytest.mark.parametrize("quantity,rate,discount", [(-1, 1000, 0), (0, 1000, 0), (1, -1, 0), (1, 1000, 101)])
def test_65_normal_invoice_rejects_invalid_values(quantity, rate, discount):
    app = app_with_db()
    with app.app_context():
        from app.models import Warehouse
        sale = Sale()
        item = {"product_id": 1, "quantity": quantity, "rate": rate, "discount": discount, "tax_rate": 18,
                **line_totals(quantity, rate, discount, 18)}
        from werkzeug.exceptions import BadRequest
        with pytest.raises(BadRequest):
            create_or_update_invoice(sale, invoice_form(Customer.query.first(), Warehouse.query.first()), [item], 1)
        db.session.rollback()
        assert Sale.query.count() == InventoryLedger.query.count() == 0


@pytest.mark.parametrize("purchase_qty,restock", [(0, True), (2, True), (0, False)])
def test_56_92_93_fractional_return_uses_original_cost(purchase_qty, restock, record_property):
    app = app_with_db()
    with app.app_context():
        product = db.session.get(Product, 1)
        product.current_stock = Decimal("10.50")
        product.average_cost = product.purchase_price = 600
        product.unit.decimal_allowed = True
        db.session.commit()
    with app.test_client() as client:
        login(client)
        open_pos_session(client)
        payload = sale_payload("QA-FRACTIONAL")
        payload["items"][0]["qty"] = 2.75
        payload["cash_tendered"] = 3245
        response = client.post("/pos/sale", json=payload)
        assert response.status_code == 200, response.json
        sale_id = response.json["sale_id"]
        if purchase_qty:
            with app.app_context():
                apply_purchase_item(1, 1, purchase_qty, 900, 99, "QA-NEW-COST")
                db.session.commit()
        returned = client.post("/sales/returns/create", data={"return_date": date.today().isoformat(),
            "sale_id": sale_id, "customer_id": 1, "warehouse_id": 1, "restock": "on" if restock else "",
            "reason": "QA fractional return", "product_id[]": "1", "quantity[]": "0.50", "rate[]": "1000", "tax_rate[]": "18"})
        assert returned.status_code == 302
        with app.app_context():
            ret = SalesReturn.query.one()
            assert float(ret.grand_total) == 590
            assert float(db.session.get(Product, 1).current_stock) == 7.75 + purchase_qty + (0.5 if restock else 0)
            movements = InventoryLedger.query.filter_by(movement_type="Sales Return").all()
            assert len(movements) == int(restock)
            if restock:
                assert float(movements[0].rate) == 600
                assert float(movements[0].value) == 300
            record_property("document_id", ret.return_no)
            record_property("expected_vs_actual", f"return_credit=590/590; restock={restock}; original_unit_cost=600; remaining_stock={float(db.session.get(Product, 1).current_stock)}")


@pytest.mark.parametrize("rates,expected", [([5, 18], 2230), ([0, 18], 2180)])
def test_59_60_mixed_tax_invoice_persists(rates, expected, record_property):
    app = app_with_db()
    with app.app_context():
        from app.models import Warehouse
        items = [{"product_id": 1, "quantity": 1, "rate": 1000, "discount": 0, "tax_rate": rate,
                  **line_totals(1, 1000, 0, rate)} for rate in rates]
        sale = Sale()
        create_or_update_invoice(sale, invoice_form(Customer.query.first(), Warehouse.query.first()), items, 1)
        issue_invoice(sale, 1)
        db.session.commit()
        db.session.expire_all()
        saved = db.session.get(Sale, sale.id)
        assert float(saved.grand_total) == expected
        assert sorted(float(line.tax_amount) for line in saved.items) == sorted(rate * 10 for rate in rates)
        record_property("document_id", saved.invoice_no)
        record_property("expected_vs_actual", f"invoice_total={expected}/{float(saved.grand_total)}; tax_rates={rates}")


def test_77_inactive_product_cannot_be_sold_by_direct_id():
    app = app_with_db()
    with app.app_context():
        db.session.get(Product, 1).is_active = False
        db.session.commit()
    with app.test_client() as client:
        login(client)
        open_pos_session(client)
        assert client.get("/pos/products/search?q=P1").json["data"] == []
        response = client.post("/pos/sale", json=sale_payload())
        assert response.status_code == 400, response.json
        with app.app_context():
            assert Sale.query.count() == InventoryLedger.query.count() == 0


def test_53_same_key_cannot_change_payment_and_can_recover_after_closing():
    app = app_with_db()
    with app.test_client() as client:
        login(client)
        open_pos_session(client)
        first = client.post("/pos/sale", json=sale_payload())
        changed = sale_payload()
        changed["items"][0]["qty"] = 3
        assert client.post("/pos/sale", json=changed).status_code == 409
        assert client.post("/pos/close-session", data={"closing_cash": 2460}).status_code == 200
        recovered = client.post("/pos/sale", json=sale_payload())
        assert recovered.status_code == 200
        assert recovered.json["sale_id"] == first.json["sale_id"]
        with app.app_context():
            assert Sale.query.count() == PaymentReceived.query.count() == 1
            assert float(db.session.get(Product, 1).current_stock) == 8


def test_56_cumulative_fractional_return_cannot_exceed_sale():
    app = app_with_db()
    with app.test_client() as client:
        login(client)
        open_pos_session(client)
        sold = client.post("/pos/sale", json=sale_payload()).json
        form = {"return_date": date.today().isoformat(), "sale_id": sold["sale_id"], "customer_id": 1,
            "warehouse_id": 1, "restock": "on", "product_id[]": "1", "quantity[]": "0.50", "rate[]": "1", "tax_rate[]": "0"}
        client.post("/sales/returns/create", data=form)
        form["quantity[]"] = "1.75"
        client.post("/sales/returns/create", data=form)
        with app.app_context():
            assert SalesReturn.query.count() == 1
            assert float(SalesReturn.query.one().grand_total) == 590, "Credit must use original pricing and tax"
            assert float(db.session.get(Product, 1).current_stock) == 8.5


def test_65_zero_price_is_permitted_but_not_negative():
    app = app_with_db()
    with app.app_context():
        from app.models import Warehouse
        sale = Sale()
        item = {"product_id": 1, "quantity": 1, "rate": 0, "discount": 0, "tax_rate": 18, **line_totals(1, 0, 0, 18)}
        create_or_update_invoice(sale, invoice_form(Customer.query.first(), Warehouse.query.first()), [item], 1)
        issue_invoice(sale, 1)
        db.session.commit()
        db.session.expire_all()
        assert float(db.session.get(Sale, sale.id).grand_total) == 0
        assert float(db.session.get(Product, 1).current_stock) == 9


def test_51_selected_warehouse_limit_does_not_use_other_locations():
    from app.models import Warehouse
    from app.services.stock_service import apply_stock_transfer, apply_sale_item, warehouse_quantity
    from werkzeug.exceptions import BadRequest
    app=app_with_db()
    with app.app_context():
        db.session.add(Warehouse(name='Other',code='OTHER',branch_id=1)); db.session.commit()
        apply_stock_transfer(1,1,2,5,100,1,'QA-51-TRANSFER'); db.session.commit()
        apply_sale_item(1,1,4,1,'QA-51-FIRST'); db.session.commit()
        with pytest.raises(BadRequest,match='selected warehouse'):
            apply_sale_item(1,1,4,2,'QA-51-SECOND')
        db.session.rollback()
        product=db.session.get(Product,1)
        assert float(product.current_stock)==6
        assert float(warehouse_quantity(product,1))==1
        assert float(warehouse_quantity(product,2))==5
        assert InventoryLedger.query.filter_by(reference_no='QA-51-SECOND').count()==0


def test_54_repeated_issue_does_not_duplicate_stock_or_receivable():
    from app.models import CustomerLedger,Warehouse
    from werkzeug.exceptions import BadRequest
    app=app_with_db()
    with app.app_context():
        sale=Sale()
        line=dict(product_id=1,quantity=2,rate=1000,discount=0,tax_rate=18,**line_totals(2,1000,0,18))
        create_or_update_invoice(sale,invoice_form(Customer.query.first(),Warehouse.query.first()),[line],1)
        db.session.commit(); ident=sale.id
        issue_invoice(sale,1); db.session.commit()
        with pytest.raises(BadRequest,match='Only draft'):
            issue_invoice(sale,1)
        db.session.rollback()
        assert db.session.get(Sale,ident).status=='Issued'
        assert float(db.session.get(Product,1).current_stock)==8
        assert InventoryLedger.query.filter_by(reference_type='Sale',reference_id=ident).count()==1
        assert CustomerLedger.query.filter_by(reference_type='Sale',reference_id=ident).count()==1
        assert Customer.query.one().outstanding==2360
