from datetime import datetime
from app.extensions import db


class AdjustmentReview(db.Model):
    __tablename__ = "stock_adjustment_reviews"
    adjustment_id = db.Column(db.Integer, db.ForeignKey("stock_adjustments.id", ondelete="CASCADE"), primary_key=True)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    evidence = db.Column(db.LargeBinary)
    evidence_name = db.Column(db.String(255))
    evidence_mime = db.Column(db.String(100))
    evidence_sha256 = db.Column(db.String(64))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    adjustment = db.relationship("StockAdjustment", backref=db.backref("review", uselist=False))


class ManufacturingSource(db.Model):
    __tablename__ = "manufacturing_component_sources"
    order_id = db.Column(db.Integer, db.ForeignKey("manufacturing_orders.id", ondelete="CASCADE"), primary_key=True)
    bom_item_id = db.Column(db.Integer, db.ForeignKey("bom_items.id", ondelete="CASCADE"), primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    order = db.relationship("ManufacturingOrder", backref="component_sources")
