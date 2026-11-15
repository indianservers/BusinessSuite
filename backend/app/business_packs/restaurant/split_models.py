"""Immutable links to native invoices/receipts; never a financial ledger."""
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, UniqueConstraint, CheckConstraint, Index, event, inspect, select
from app.db.base_class import Base
from .models import Scope, constraints, parent, immutable


class RestaurantBillGroup(Scope, Base):
    __tablename__ = 'business_restaurant_bill_groups'
    __table_args__ = (*constraints('bill_group'),
        parent('bill_group_order', ['service_order_id'], 'business_restaurant_service_orders'),
        UniqueConstraint('organization_id', 'branch_id', 'pack_context_id', 'request_key', name='uq_rest_bill_request'),
        Index('ix_rest_bill_order', 'service_order_id'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64', name='ck_rest_bill_request'))
    id = Column(Integer, primary_key=True)
    service_order_id = Column(Integer, nullable=False)
    request_key = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)


class RestaurantBillLine(Scope, Base):
    __tablename__ = 'business_restaurant_bill_lines'
    __table_args__ = (*constraints('bill_line'),
        parent('bill_line_group', ['group_id'], 'business_restaurant_bill_groups'),
        parent('bill_line_snapshot', ['snapshot_id'], 'business_restaurant_tab_lines'),
        UniqueConstraint('group_id', 'snapshot_id', name='uq_rest_bill_snapshot'),
        Index('ix_rest_bill_snapshot', 'snapshot_id'),
        CheckConstraint('quantity > 0 AND unit_price >= 0 AND tax_amount >= 0 AND line_total >= 0', name='ck_rest_bill_charge'))
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, nullable=False)
    snapshot_id = Column(Integer, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    tax_amount = Column(Numeric(14, 2), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)


class RestaurantBillIssue(Scope, Base):
    __tablename__ = 'business_restaurant_bill_issues'
    __table_args__ = (*constraints('bill_issue'),
        parent('bill_issue_group', ['group_id'], 'business_restaurant_bill_groups'),
        UniqueConstraint('group_id', name='uq_rest_bill_issued_once'))
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, nullable=False)
    invoice_id = Column(Integer, ForeignKey('srm_invoices.id', ondelete='RESTRICT'), nullable=False, unique=True)


class RestaurantBillReceipt(Scope, Base):
    __tablename__ = 'business_restaurant_bill_receipts'
    __table_args__ = (*constraints('bill_receipt'),
        parent('bill_receipt_issue', ['issue_id'], 'business_restaurant_bill_issues'),
        UniqueConstraint('organization_id', 'branch_id', 'pack_context_id', 'payment_key', name='uq_rest_bill_payment'),
        UniqueConstraint('organization_id', 'branch_id', 'pack_context_id', 'request_key', name='uq_rest_bill_receipt_request'),
        Index('ix_rest_bill_register', 'collection_session_id'),
        CheckConstraint('length(payment_key)=36 AND length(request_key)=36 AND length(request_sha256)=64', name='ck_rest_bill_payment'),
        CheckConstraint('collection_currency IS NULL OR (length(collection_currency)=3 AND collection_currency=upper(collection_currency))', name='ck_rest_bill_collection_currency'))
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, nullable=False)
    receipt_id = Column(Integer, ForeignKey('srm_receipts.id', ondelete='RESTRICT'), nullable=False, unique=True)
    allocation_id = Column(Integer, ForeignKey('srm_receipt_allocations.id', ondelete='RESTRICT'), nullable=False, unique=True)
    collection_session_id = Column(Integer, ForeignKey('srm_pos_sessions.id', ondelete='RESTRICT'), nullable=False)
    collection_cashier_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    collection_currency = Column(String(3))
    payment_key = Column(String(36), nullable=False)
    request_key = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)


MODELS = (RestaurantBillGroup, RestaurantBillLine, RestaurantBillIssue, RestaurantBillReceipt)
for model in MODELS:
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)


@event.listens_for(RestaurantBillIssue, 'before_insert')
def exact_native_issuance(mapper, connection, row):
    from .split_bills import validate_issue_insert
    validate_issue_insert(inspect(row).session, row)


@event.listens_for(RestaurantBillReceipt, 'before_insert')
def exact_native_collection(mapper, connection, row):
    from .split_bills import validate_payment_insert
    validate_payment_insert(inspect(row).session, row)


def pending_source(mapper, connection, row):
    from .split_bills import register_new_source
    if type(row) is RestaurantBillReceipt:
        group_id = connection.scalar(select(RestaurantBillIssue.group_id).where(RestaurantBillIssue.id == row.issue_id))
    else:
        group_id = row.id if type(row) is RestaurantBillGroup else row.group_id
    register_new_source(inspect(row).session, group_id, type(row), row.id)


for model in MODELS:
    event.listen(model, 'after_insert', pending_source)
