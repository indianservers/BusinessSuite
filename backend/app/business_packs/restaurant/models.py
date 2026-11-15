"""Private restaurant fulfillment. Canonical orders and receipts retain money."""
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        ForeignKeyConstraint, Index, Integer, JSON, Numeric,
                        String, UniqueConstraint, event, inspect, func, select)
from app.db.base_class import Base


class Scope:
    organization_id = Column(Integer, nullable=False)
    branch_id = Column(Integer, nullable=False)
    pack_context_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def constraints(name):
    return (ForeignKeyConstraint(['pack_context_id', 'organization_id', 'branch_id'],
        ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'],
        name='fk_restaurant_'+name+'_context', ondelete='RESTRICT'),
        UniqueConstraint('id', 'organization_id', 'branch_id', 'pack_context_id', name='uq_restaurant_'+name+'_source'))


def parent(name, fields, target):
    return ForeignKeyConstraint([*fields, 'organization_id', 'branch_id', 'pack_context_id'],
        [target+'.id', target+'.organization_id', target+'.branch_id', target+'.pack_context_id'],
        name='fk_restaurant_'+name, ondelete='RESTRICT')


class RestaurantTable(Scope, Base):
    __tablename__ = 'business_restaurant_tables'
    __table_args__ = (*constraints('table'),
        UniqueConstraint('organization_id', 'branch_id', 'pack_context_id', 'name', name='uq_restaurant_table_name'),
        CheckConstraint('capacity > 0 AND capacity <= 1000 AND revision > 0', name='ck_restaurant_table_values'))
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    capacity = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    revision = Column(Integer, nullable=False, default=1)


class RestaurantServiceOrder(Scope, Base):
    __tablename__ = 'business_restaurant_service_orders'
    __table_args__ = (*constraints('order'),
        parent('order_table', ['table_id'], 'business_restaurant_tables'),
        ForeignKeyConstraint(['checkout_id', 'organization_id', 'branch_id', 'pack_context_id'],
            ['srm_pos_service_checkouts.id', 'srm_pos_service_checkouts.organization_id',
             'srm_pos_service_checkouts.branch_id', 'srm_pos_service_checkouts.scope_context_key'],
            name='fk_restaurant_order_checkout_scope', ondelete='RESTRICT'),
        CheckConstraint("state IN ('open','served') AND revision > 0", name='ck_restaurant_order_state'),
        CheckConstraint('length(source_sha256)=64', name='ck_restaurant_order_fingerprint'),
        CheckConstraint("(source_kind = 'paid_pos' AND checkout_id IS NOT NULL) OR (source_kind = 'unpaid_tab' AND checkout_id IS NULL)", name='ck_restaurant_order_kind'),
        Index('uq_restaurant_active_table', 'table_id', unique=True,
              postgresql_where=(Column('state') == 'open'), sqlite_where=(Column('state') == 'open')))
    id = Column(Integer, primary_key=True)
    checkout_id = Column(Integer, ForeignKey('srm_pos_service_checkouts.id', ondelete='RESTRICT'), nullable=True, unique=True)
    source_kind = Column(String(20), nullable=False, default='paid_pos', server_default='paid_pos')
    sales_order_id = Column(Integer, ForeignKey('srm_sales_orders.id', ondelete='RESTRICT'), nullable=False, unique=True)
    table_id = Column(Integer)
    source_sha256 = Column(String(64), nullable=False)
    state = Column(String(20), nullable=False, default='open')
    revision = Column(Integer, nullable=False, default=1)


class RestaurantKitchenTicket(Scope, Base):
    __tablename__ = 'business_restaurant_kitchen_tickets'
    __table_args__ = (*constraints('ticket'),
        parent('ticket_order', ['service_order_id'], 'business_restaurant_service_orders'),
        CheckConstraint("state IN ('queued','preparing','ready','served') AND revision > 0", name='ck_restaurant_ticket_state'))
    id = Column(Integer, primary_key=True)
    service_order_id = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False, default='queued')
    revision = Column(Integer, nullable=False, default=1)


class RestaurantKitchenLine(Scope, Base):
    __tablename__ = 'business_restaurant_kitchen_lines'
    __table_args__ = (*constraints('line'),
        parent('line_ticket', ['ticket_id'], 'business_restaurant_kitchen_tickets'),
        UniqueConstraint('ticket_id', 'sales_order_line_id', name='uq_restaurant_ticket_line'),
        CheckConstraint('quantity > 0', name='ck_restaurant_line_quantity'))
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, nullable=False)
    sales_order_line_id = Column(Integer, ForeignKey('srm_sales_order_lines.id', ondelete='RESTRICT'), nullable=False)
    item = Column(String(500), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    instruction = Column(String(1000), nullable=False, default='')


class RestaurantCommand(Scope, Base):
    """Append-only replay/event result: server-produced primitive DTO only."""
    __tablename__ = 'business_restaurant_commands'
    __table_args__ = (*constraints('command'),
        parent('command_table', ['table_id'], 'business_restaurant_tables'),
        parent('command_order', ['service_order_id'], 'business_restaurant_service_orders'),
        parent('command_ticket', ['ticket_id'], 'business_restaurant_kitchen_tickets'),
        UniqueConstraint('organization_id', 'branch_id', 'pack_context_id', 'request_key', name='uq_restaurant_command_key'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64', name='ck_restaurant_command_key'))
    id = Column(Integer, primary_key=True)
    request_key = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)
    action = Column(String(40), nullable=False)
    table_id = Column(Integer)
    service_order_id = Column(Integer)
    ticket_id = Column(Integer)
    result = Column(JSON, nullable=False)


class RestaurantTabLine(Scope, Base):
    """Immutable provenance of actual appended native SO charges, not a ledger."""
    __tablename__ = 'business_restaurant_tab_lines'
    __table_args__ = (*constraints('tab_line'),
        parent('tab_line_order', ['service_order_id'], 'business_restaurant_service_orders'),
        UniqueConstraint('sales_order_line_id', name='uq_restaurant_tab_native_line'),
        CheckConstraint('original_sales_order_line_id > 0 AND (sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id)', name='ck_restaurant_tab_original_identity'),
        CheckConstraint('quantity > 0 AND unit_price >= 0 AND tax_amount >= 0 AND line_total >= 0', name='ck_restaurant_tab_charge'))
    id = Column(Integer, primary_key=True)
    service_order_id = Column(Integer, nullable=False)
    original_sales_order_line_id = Column(Integer, nullable=False)
    sales_order_line_id = Column(Integer, ForeignKey('srm_sales_order_lines.id', ondelete='SET NULL'), nullable=True)
    product_id = Column(Integer, ForeignKey('srm_products.id', ondelete='RESTRICT'), nullable=False)
    warehouse_id = Column(Integer, ForeignKey('srm_warehouses.id', ondelete='RESTRICT'))
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    tax_amount = Column(Numeric(14, 2), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)
    item = Column(String(500), nullable=False)
    catalog_tax_snapshot = Column(JSON, nullable=False)


class RestaurantKitchenIssue(Scope, Base):
    __tablename__ = 'business_restaurant_kitchen_issues'
    __table_args__ = (*constraints('kitchen_issue'),
        parent('issue_line', ['kitchen_line_id'], 'business_restaurant_kitchen_lines'),
        UniqueConstraint('kitchen_line_id', name='uq_restaurant_kitchen_stock_once'),
        UniqueConstraint('movement_id', name='uq_restaurant_kitchen_native_movement'))
    id = Column(Integer, primary_key=True)
    kitchen_line_id = Column(Integer, nullable=False)
    movement_id = Column(Integer, ForeignKey('srm_inventory_movements.id', ondelete='RESTRICT'), nullable=False)


def immutable(mapper, connection, row):
    raise ValueError('Restaurant fulfillment provenance is immutable')


for model in (RestaurantCommand, RestaurantKitchenLine, RestaurantKitchenIssue):
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)


event.listen(RestaurantTabLine, 'before_delete', immutable)


@event.listens_for(RestaurantTabLine, 'before_update')
def cancel_snapshot_reference(mapper, connection, row):
    from .removals import snapshot_transition
    if not snapshot_transition(row):
        immutable(mapper, connection, row)


@event.listens_for(RestaurantServiceOrder, 'before_update')
def immutable_order_source(mapper, connection, row):
    if any(inspect(row).attrs[name].history.has_changes() for name in ('checkout_id', 'source_kind', 'sales_order_id', 'source_sha256', 'created_by')):
        immutable(mapper, connection, row)


@event.listens_for(RestaurantKitchenTicket, 'before_update')
def immutable_ticket_source(mapper, connection, row):
    if any(inspect(row).attrs[name].history.has_changes() for name in ('service_order_id', 'created_by')):
        immutable(mapper, connection, row)


@event.listens_for(RestaurantKitchenLine, 'before_insert')
def line_parent_source(mapper, connection, row):
    from app.apps.srm.models import SRMSalesOrderLine
    ticket, order, source, issued = (model.__table__ for model in
        (RestaurantKitchenTicket, RestaurantServiceOrder, SRMSalesOrderLine, RestaurantKitchenLine))
    actual = connection.execute(select(order.c.sales_order_id, order.c.organization_id, order.c.branch_id,
        order.c.pack_context_id).select_from(ticket.join(order, ticket.c.service_order_id == order.c.id)).where(ticket.c.id == row.ticket_id)).first()
    native = connection.execute(select(source.c.sales_order_id, source.c.quantity).where(source.c.id == row.sales_order_line_id)).first()
    if (actual is None or native is None or actual.sales_order_id != native.sales_order_id
            or (actual.organization_id, actual.branch_id, actual.pack_context_id) != (row.organization_id, row.branch_id, row.pack_context_id)):
        raise ValueError('Kitchen item must belong to its canonical source order')
    sent = connection.scalar(select(func.coalesce(func.sum(issued.c.quantity), 0)).select_from(
        issued.join(ticket, issued.c.ticket_id == ticket.c.id).join(order, ticket.c.service_order_id == order.c.id)).where(
        order.c.sales_order_id == native.sales_order_id, issued.c.sales_order_line_id == row.sales_order_line_id))
    if row.quantity <= 0 or row.quantity + sent > native.quantity:
        raise ValueError('Kitchen quantity exceeds its canonical source line')


@event.listens_for(RestaurantTabLine, 'before_insert')
def native_charge_snapshot(mapper, connection, row):
    from app.apps.srm.models import SRMSalesOrderLine
    order, line = RestaurantServiceOrder.__table__, SRMSalesOrderLine.__table__
    root = connection.execute(select(order.c.sales_order_id, order.c.organization_id, order.c.branch_id,
        order.c.pack_context_id, order.c.source_kind).where(order.c.id == row.service_order_id)).first()
    actual = connection.execute(select(line).where(line.c.id == row.sales_order_line_id)).mappings().first()
    if (row.original_sales_order_line_id != row.sales_order_line_id or root is None or actual is None or root.source_kind != 'unpaid_tab' or root.sales_order_id != actual['sales_order_id']
            or (root.organization_id, root.branch_id, root.pack_context_id) != (row.organization_id, row.branch_id, row.pack_context_id)
            or (actual['product_id'], actual['description'], actual['quantity'], actual['unit_price'], actual['tax_amount'],
                actual['line_total'], actual['discount_amount'], (actual['metadata_json'] or {}).get('warehouse_id'),
                (actual['metadata_json'] or {}).get('tax_snapshot', {})) !=
               (row.product_id, row.item, row.quantity, row.unit_price, row.tax_amount, row.line_total, 0, row.warehouse_id, row.catalog_tax_snapshot)):
        raise ValueError('Restaurant charge provenance must match its actual native order line')


@event.listens_for(RestaurantKitchenIssue, 'before_insert')
def kitchen_movement_source(mapper, connection, row):
    from decimal import Decimal, ROUND_HALF_UP
    from app.apps.srm.models import SRMSalesOrder, SRMInventoryMovement
    line, ticket, order, charge, native, movement = (model.__table__ for model in
        (RestaurantKitchenLine, RestaurantKitchenTicket, RestaurantServiceOrder, RestaurantTabLine, SRMSalesOrder, SRMInventoryMovement))
    actual = connection.execute(select(line.c.quantity, line.c.created_by, line.c.organization_id, line.c.branch_id,
        line.c.pack_context_id, charge.c.product_id, charge.c.warehouse_id, charge.c.unit_price, native.c.order_number,
        order.c.source_kind).select_from(line.join(ticket, line.c.ticket_id == ticket.c.id).join(order,
            ticket.c.service_order_id == order.c.id).join(charge, (charge.c.sales_order_line_id == line.c.sales_order_line_id)
            & (charge.c.service_order_id == order.c.id)).join(native, native.c.id == order.c.sales_order_id)).where(line.c.id == row.kitchen_line_id)).first()
    issued = connection.execute(select(movement).where(movement.c.id == row.movement_id)).mappings().first()
    if (actual is None or issued is None or actual.source_kind != 'unpaid_tab'
            or (actual.organization_id, actual.branch_id, actual.pack_context_id, actual.created_by) !=
               (row.organization_id, row.branch_id, row.pack_context_id, row.created_by)
            or (issued['organization_id'], issued['created_by'], issued['product_id'], issued['warehouse_id'],
                issued['quantity_in'], issued['quantity_out'], issued['rate'], issued['value'], issued['reference_number'], issued['movement_type']) !=
               (row.organization_id, row.created_by, actual.product_id, actual.warehouse_id, 0, actual.quantity,
                actual.unit_price, (actual.quantity*actual.unit_price).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), actual.order_number, 'restaurant_kitchen')):
        raise ValueError('Kitchen movement must match its actual persisted private item')


from .split_models import MODELS as SPLIT_MODELS

MODELS = (RestaurantTable, RestaurantServiceOrder, RestaurantKitchenTicket, RestaurantKitchenLine, RestaurantCommand,
          RestaurantTabLine, RestaurantKitchenIssue, *SPLIT_MODELS)
RECORD_TABLES = frozenset(model.__tablename__ for model in MODELS)
