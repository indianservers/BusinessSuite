from app.extensions import db
from app.models import Product, PurchaseOrder, SalesOrder, ManufacturingOrder, StockTransfer, Batch, SerialNumber, POSSession, Register
from app.services.stock_service import warehouse_quantity


def assert_can_deactivate(warehouse):
    for product in Product.query.all():
        if warehouse_quantity(product, warehouse.id) != 0:
            raise ValueError("Warehouse has remaining stock; transfer or reconcile it before deactivation")
    for model in (PurchaseOrder, SalesOrder, ManufacturingOrder):
        if model.query.filter(model.warehouse_id == warehouse.id,
                model.status.notin_(["Cancelled", "Closed", "Completed", "Received"])).first():
            raise ValueError("Warehouse has open orders; resolve them before deactivation")
    if StockTransfer.query.filter(db.or_(StockTransfer.from_warehouse_id == warehouse.id,
            StockTransfer.to_warehouse_id == warehouse.id), StockTransfer.status.in_(["Draft", "Sent"])).first():
        raise ValueError("Warehouse has an unfinished stock transfer")
    if Batch.query.filter(Batch.warehouse_id == warehouse.id, Batch.quantity != 0).first() or SerialNumber.query.filter_by(warehouse_id=warehouse.id,status="Available").first():
        raise ValueError("Warehouse has available batch or serial stock")
    if POSSession.query.join(Register).filter(Register.warehouse_id == warehouse.id, POSSession.status == "Open").first():
        raise ValueError("Warehouse has an open POS session")
