"""Loopback browser fixture. Always uses a new, in-memory SQLite database."""
import os
import json
from pathlib import Path
import sys

os.environ["APP_ENV"] = "testing"
os.environ["TEST_DATABASE_URI"] = "sqlite:///:memory:"
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tests"))
from test_core import app_with_db
from app.extensions import db
from app.models import CompanySetting, Product, Warehouse, Customer, Sale, PaymentReceived, InventoryLedger, StockTransfer, SalesReturn, CreditNote, Refund, CustomerLedger, SerialNumber, ManufacturingOrder

batch = os.environ.get("QA_WORKFLOW_BATCH", "101-150")
app = app_with_db()
app.jinja_env.auto_reload = True
with app.app_context():
    db.session.add(CompanySetting(company_name=f"Workflow {batch} Test Company"))
    customer = db.session.get(Customer, 1)
    customer.name = "QA Customer A"
    customer.payment_terms = 30
    customer.billing_address = "QA Billing Office"
    customer.shipping_address = "QA Delivery Warehouse"
    product = db.session.get(Product, 1)
    product.name = "QA Product A"
    product.sales_price = 1000
    product.purchase_price = product.average_cost = 600
    db.session.add(Warehouse(name="QA Warehouse B", code="QA-B", branch_id=1))
    db.session.add(Product(sku="QA-SERVICE", name="QA Consulting Service", unit_id=1, tax_id=1,
                           sales_price=800 if batch == "201-250" else 5000, track_inventory=False, current_stock=0, is_active=True))
    if os.environ.get("QA_PRICE_CASE") == "1":
        from datetime import date, timedelta
        from app.models import PriceList, PriceListItem
        for name, amount, start, end, default in [
            ("QA Expired Assigned",750,None,date.today()-timedelta(days=1),False),
            ("QA Valid Default",900,date.today()-timedelta(days=1),date.today()+timedelta(days=30),True),
            ("QA Competing Default",850,None,None,True)]:
            price_list=PriceList(name=name,valid_from=start,valid_to=end,is_default=default,status=True)
            db.session.add(price_list); db.session.flush()
            db.session.add(PriceListItem(price_list_id=price_list.id,product_id=1,sales_price=amount,min_qty=1))
            if not default: customer.price_list_id=price_list.id
    if os.environ.get("QA_MANUFACTURING_CASE") == "1":
        from app.models import Unit, BillOfMaterials, BOMItem
        kg=Unit(name="QA Kilogram",short_name="qkg",decimal_allowed=True)
        db.session.add(kg);db.session.flush();product.unit_id=kg.id
        finished=Product(sku="QA-246-FG",name="QA Fractional Finished Goods",unit_id=1,
                         warehouse_id=1,current_stock=0,average_cost=0,sales_price=1000,is_active=True)
        db.session.add(finished);db.session.flush()
        bom=BillOfMaterials(name="QA quarter-kg BOM",product_id=finished.id,yield_qty=1,is_active=True)
        db.session.add(bom);db.session.flush()
        db.session.add(BOMItem(bom_id=bom.id,component_id=1,quantity=0.25,unit_id=kg.id,waste_pct=0))
    if os.environ.get("QA_SERIAL_CASE") == "1":
        db.session.add(Product(sku="QA-244-SERIAL",barcode="244000001",name="QA Serialized Product",
            unit_id=1,tax_id=1,warehouse_id=1,current_stock=1,purchase_price=600,average_cost=600,
            sales_price=1000,serial_tracking=True,track_inventory=True,is_active=True))
    if os.environ.get("QA_PO_CASE") == "1":
        from datetime import date
        from app.models import PurchaseOrder, PurchaseOrderItem
        destination=Warehouse.query.filter_by(code="QA-B").one()
        destination.address="QA Dock B, 22 Receiving Road, Hyderabad"
        po=PurchaseOrder(po_no="QA-237-DESTINATION",po_date=date.today(),supplier_id=1,warehouse_id=destination.id,
                         subtotal=1200,tax_total=216,grand_total=1416,status="Draft")
        db.session.add(po);db.session.flush()
        db.session.add(PurchaseOrderItem(po_id=po.id,product_id=1,quantity=2,rate=600,tax_rate=18,tax_amount=216,line_total=1416))
        if os.environ.get("QA_PO_AMEND_CASE") == "1":
            from app.models import Supplier
            db.session.add(Supplier(supplier_code="QA-238-B",name="QA Supplier B"))
            po.terms="Supplier A only terms"
            for number in (2,3):
                p=Product(sku=f"QA-239-{number}",name=f"QA Remove Test {number}",unit_id=1,warehouse_id=1,current_stock=0,purchase_price=100,track_inventory=True,is_active=True)
                db.session.add(p);db.session.flush()
                db.session.add(PurchaseOrderItem(po_id=po.id,product_id=p.id,quantity=1,rate=100,discount=0,tax_rate=0,tax_amount=0,line_total=100))
            po.subtotal=1400;po.grand_total=1616
    db.session.commit()


@app.after_request
def capture_persisted_browser_records(response):
    evidence = {
        "fixture": f"Isolated in-memory Workflow {batch} Test Company",
        "invoices": [{"id": sale.id, "number": sale.invoice_no, "status": sale.status,
                      "invoice_date": str(sale.invoice_date), "due_date": str(sale.due_date),
                      "subtotal": float(sale.subtotal), "tax": float(sale.tax_total),
                      "total": float(sale.grand_total), "paid": float(sale.paid_amount),
                      "balance": float(sale.balance_amount)} for sale in Sale.query.all()],
        "products": [{"id": p.id, "sku": p.sku, "stock": float(p.current_stock), "track_inventory":p.track_inventory} for p in Product.query.all()],
        "receipts": [{"id": p.id, "number":p.receipt_no,"sale_id":p.sale_id,"amount":float(p.amount)} for p in PaymentReceived.query.all()],
        "stock_movements": [{"product_id": m.product_id,"warehouse_id":m.warehouse_id,"reference":m.reference_no,
                             "type":m.movement_type,"in":float(m.qty_in),"out":float(m.qty_out),"rate":float(m.rate),"value":float(m.value)} for m in InventoryLedger.query.all()],
        "warehouses": [{"id":w.id,"name":w.name,"active":w.status} for w in Warehouse.query.all()],
        "purchase_orders": [{"id":p.id,"supplier_id":p.supplier_id,"status":p.status,"terms":p.terms,"total":float(p.grand_total),"lines":[{"id":i.id,"product_id":i.product_id,"quantity":float(i.quantity),"received":float(i.received_qty)} for i in p.items]} for p in __import__('app.models',fromlist=['PurchaseOrder']).PurchaseOrder.query.all()],
        "manufacturing": [{"id":m.id,"number":m.mo_no,"planned":float(m.planned_qty),"produced":float(m.produced_qty),"status":m.status} for m in ManufacturingOrder.query.all()],
        "serials": [{"id":s.id,"product_id":s.product_id,"number":s.serial_no,"status":s.status,"sale_id":s.sale_id} for s in SerialNumber.query.all()],
        "returns": [{"id":r.id,"number":r.return_no,"status":r.status,"sale_id":r.sale_id,"date":str(r.return_date),"total":float(r.grand_total)} for r in SalesReturn.query.all()],
        "credits": [{"id":n.id,"number":n.cn_no,"sale_id":n.sale_id,"total":float(n.grand_total)} for n in CreditNote.query.all()],
        "refunds": [{"number":r.refund_no,"amount":float(r.amount),"status":r.approval_status} for r in Refund.query.all()],
        "customer_balances": [{"id":c.id,"outstanding":c.outstanding} for c in Customer.query.all()],
        "customer_ledger": [{"reference":l.reference_no,"debit":float(l.debit),"credit":float(l.credit)} for l in CustomerLedger.query.all()],
        "transfers": [{"id":t.id,"number":t.transfer_no,"status":t.status,"from":t.from_warehouse_id,"to":t.to_warehouse_id} for t in StockTransfer.query.all()],
    }
    (root.parents[4]/"outputs"/f"workflows-{batch}-browser-records.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    return response

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("QA_BROWSER_PORT", "5298")), debug=False, threaded=False)
