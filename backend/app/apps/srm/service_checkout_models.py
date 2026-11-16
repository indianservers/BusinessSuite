"""Typed service checkout sources; native SRM remains the money/stock ledger.

These definitions register no API or runtime behavior. Services must authorize
the actor and native sources before use. Nullable pack context is reserved for
legacy common service checkout. Stored scope keys make its composite source
identity null-safe; they never grant pack authority.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Computed, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, JSON, Numeric, String,
    UniqueConstraint, event, inspect, select, text,
)
from sqlalchemy.orm import object_session, validates, declared_attr
from sqlalchemy.sql import func
from app.db.base_class import Base


class ServiceCheckoutIdentityError(ValueError):
    """A checkout identity, native source or issued charge was retagged."""


class ServiceCheckoutRevisionError(ValueError):
    """An explicit optimistic revision did not advance exactly once."""


def _scope_constraints(prefix):
    return (
        ForeignKeyConstraint(['pack_context_id', 'organization_id', 'branch_id'],
            ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'],
            name=f'fk_{prefix}_pack_context', ondelete='RESTRICT'),
        CheckConstraint('pack_context_id IS NULL OR pack_context_id > 0', name=f'ck_{prefix}_pack_context'),
    )


def _partial_indexes(prefix, *columns):
    return (
        Index(f'uq_{prefix}_legacy', 'organization_id', 'branch_id', *columns,
              unique=True, sqlite_where=text('pack_context_id IS NULL'),
              postgresql_where=text('pack_context_id IS NULL')),
        Index(f'uq_{prefix}_pack', 'organization_id', 'branch_id', 'pack_context_id', *columns,
              unique=True, sqlite_where=text('pack_context_id IS NOT NULL'),
              postgresql_where=text('pack_context_id IS NOT NULL')),
    )


class _Revisioned:
    @declared_attr
    def __mapper_args__(cls):
        return {'version_id_col': cls.revision}

    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    @validates('revision', 'policy_revision', 'eligibility_revision')
    def _revision(self, name, value):
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
        return value

    @validates('request_id', 'client_line_key', 'occurrence_key', 'payment_key')
    def _uuid(self, name, value):
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f'{name} must be a UUID') from None

    @validates('request_sha256')
    def _digest(self, name, value):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('request_sha256 must be a lowercase SHA-256 digest')
        return value

    @validates('starts_at', 'ends_at', 'effective_from', 'effective_until', 'committed_at')
    def _aware(self, name, value):
        if value is not None:
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ValueError(f'{name} requires an aware timestamp')
            return value.astimezone(timezone.utc)
        return None


class _Scoped:
    organization_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    pack_context_id = Column(Integer, nullable=True)
    scope_context_key = Column(Integer, Computed('coalesce(pack_context_id, 0)', persisted=True), nullable=False)


class _InheritedScope:
    # These are FK-verified copies of the checkout root, not independently
    # selected context/authority. They let SQL constrain cross-source links.
    organization_id = Column(Integer, nullable=False)
    branch_id = Column(Integer, nullable=False)
    scope_context_key = Column(Integer, nullable=False)


class ServiceBookingPolicy(_Scoped, _Revisioned, Base):
    __tablename__ = 'srm_service_booking_policies'
    __table_args__ = (
        *_scope_constraints('service_policy'),
        *_partial_indexes('service_policy', 'service_product_id'),
        UniqueConstraint('id', 'organization_id', 'branch_id', 'scope_context_key', 'service_product_id', name='uq_service_policy_source'),
        CheckConstraint('min_duration_minutes >= 5 AND max_duration_minutes <= 720 AND min_duration_minutes <= default_duration_minutes AND default_duration_minutes <= max_duration_minutes', name='ck_service_policy_duration'),
        CheckConstraint('revision > 0', name='ck_service_policy_revision'),
    )
    id = Column(Integer, primary_key=True)
    employee_categories = Column(JSON, nullable=False, default=list, server_default='[]')
    service_product_id = Column(Integer, ForeignKey('srm_products.id', ondelete='RESTRICT'), nullable=False)
    booking_required = Column(Boolean(create_constraint=True, name='ck_service_policy_required'), nullable=False, default=True, server_default='true')
    default_duration_minutes = Column(Integer, nullable=False)
    min_duration_minutes = Column(Integer, nullable=False)
    max_duration_minutes = Column(Integer, nullable=False)
    allow_duration_override = Column(Boolean(create_constraint=True, name='ck_service_policy_override'), nullable=False, default=False, server_default='false')
    active = Column(Boolean(create_constraint=True, name='ck_service_policy_active'), nullable=False, default=True, server_default='true')


class ServiceSpecialistEligibility(_Scoped, _Revisioned, Base):
    __tablename__ = 'srm_service_specialist_eligibility'
    __table_args__ = (
        *_scope_constraints('service_eligibility'),
        *_partial_indexes('service_eligibility', 'service_product_id', 'provider_resource_id'),
        ForeignKeyConstraint(['booking_policy_id', 'organization_id', 'branch_id', 'scope_context_key', 'service_product_id'],
            ['srm_service_booking_policies.id', 'srm_service_booking_policies.organization_id', 'srm_service_booking_policies.branch_id', 'srm_service_booking_policies.scope_context_key', 'srm_service_booking_policies.service_product_id'],
            name='fk_service_eligibility_policy', ondelete='RESTRICT'),
        UniqueConstraint('id', 'booking_policy_id', 'organization_id', 'branch_id', 'scope_context_key', 'service_product_id', 'provider_resource_id', name='uq_service_eligibility_source'),
        CheckConstraint('effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from', name='ck_service_eligibility_interval'),
        CheckConstraint('revision > 0', name='ck_service_eligibility_revision'),
    )
    id = Column(Integer, primary_key=True)
    booking_policy_id = Column(Integer, nullable=False)
    service_product_id = Column(Integer, ForeignKey('srm_products.id', ondelete='RESTRICT'), nullable=False)
    provider_resource_id = Column(Integer, ForeignKey('srm_industry_records.id', ondelete='RESTRICT'), nullable=False)
    effective_from = Column(DateTime(timezone=True))
    effective_until = Column(DateTime(timezone=True))
    active = Column(Boolean(create_constraint=True, name='ck_service_eligibility_active'), nullable=False, default=True, server_default='true')


class POSServiceCheckout(_Scoped, _Revisioned, Base):
    __tablename__ = 'srm_pos_service_checkouts'
    __table_args__ = (
        *_scope_constraints('service_checkout'),
        *_partial_indexes('service_checkout_request', 'request_id'),
        UniqueConstraint('id', 'organization_id', 'branch_id', 'scope_context_key', name='uq_service_checkout_source'),
        CheckConstraint("state IN ('draft','committed','cancelled')", name='ck_service_checkout_state'),
        CheckConstraint("billing_mode IN ('invoice_at_checkout','advance_then_invoice')", name='ck_service_checkout_billing_mode'),
        CheckConstraint("state != 'committed' OR (sales_order_id IS NOT NULL AND committed_at IS NOT NULL AND (billing_mode != 'invoice_at_checkout' OR invoice_id IS NOT NULL))", name='ck_service_checkout_commit_sources'),
        CheckConstraint('length(request_id) = 36 AND length(request_sha256) = 64', name='ck_service_checkout_request'),
        CheckConstraint('length(currency) = 3 AND currency = upper(currency)', name='ck_service_checkout_currency'),
        CheckConstraint('revision > 0', name='ck_service_checkout_revision'),
    )
    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    customer_id = Column(Integer, ForeignKey('crm_companies.id', ondelete='RESTRICT'), nullable=False)
    currency = Column(String(3), nullable=False)
    pos_session_id = Column(Integer, ForeignKey('srm_pos_sessions.id', ondelete='RESTRICT'), nullable=False)
    sales_order_id = Column(Integer, ForeignKey('srm_sales_orders.id', ondelete='RESTRICT'), unique=True)
    invoice_id = Column(Integer, ForeignKey('srm_invoices.id', ondelete='RESTRICT'), unique=True)
    state = Column(String(20), nullable=False, default='draft', server_default='draft')
    billing_mode = Column(String(30), nullable=False)
    committed_at = Column(DateTime(timezone=True))


class POSCheckoutLine(_InheritedScope, _Revisioned, Base):
    __tablename__ = 'srm_pos_checkout_lines'
    __table_args__ = (
        ForeignKeyConstraint(['checkout_id', 'organization_id', 'branch_id', 'scope_context_key'],
            ['srm_pos_service_checkouts.id', 'srm_pos_service_checkouts.organization_id', 'srm_pos_service_checkouts.branch_id', 'srm_pos_service_checkouts.scope_context_key'],
            name='fk_checkout_line_checkout', ondelete='RESTRICT'),
        UniqueConstraint('checkout_id', 'client_line_key', name='uq_checkout_line_client_key'),
        UniqueConstraint('id', 'checkout_id', 'organization_id', 'branch_id', 'scope_context_key', 'product_id', name='uq_checkout_line_source'),
        CheckConstraint("line_kind IN ('product','unscheduled_service','booked_service')", name='ck_checkout_line_kind'),
        CheckConstraint("quantity > 0 AND quantity <= 1000000000 AND (line_kind != 'booked_service' OR quantity = 1)", name='ck_checkout_line_quantity'),
        CheckConstraint('unit_price >= 0 AND discount_amount >= 0 AND tax_amount >= 0 AND line_total >= 0 AND discount_amount <= quantity * unit_price', name='ck_checkout_line_money'),
        CheckConstraint('length(client_line_key) = 36 AND revision > 0', name='ck_checkout_line_identity'),
    )
    id = Column(Integer, primary_key=True)
    checkout_id = Column(Integer, nullable=False)
    client_line_key = Column(String(36), nullable=False)
    line_kind = Column(String(30), nullable=False)
    product_id = Column(Integer, ForeignKey('srm_products.id', ondelete='RESTRICT'), nullable=False)
    sales_order_line_id = Column(Integer, ForeignKey('srm_sales_order_lines.id', ondelete='RESTRICT'), nullable=False, unique=True)
    invoice_line_id = Column(Integer, ForeignKey('srm_invoice_lines.id', ondelete='RESTRICT'), unique=True)
    quantity = Column(Numeric(24, 10), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    discount_amount = Column(Numeric(14, 2), nullable=False)
    tax_amount = Column(Numeric(14, 2), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)
    catalog_tax_snapshot = Column(JSON, nullable=False, default=dict)


class POSServiceOccurrence(_InheritedScope, _Revisioned, Base):
    __tablename__ = 'srm_pos_service_occurrences'
    __table_args__ = (
        ForeignKeyConstraint(['checkout_line_id', 'checkout_id', 'organization_id', 'branch_id', 'scope_context_key', 'service_product_id'],
            ['srm_pos_checkout_lines.id', 'srm_pos_checkout_lines.checkout_id', 'srm_pos_checkout_lines.organization_id', 'srm_pos_checkout_lines.branch_id', 'srm_pos_checkout_lines.scope_context_key', 'srm_pos_checkout_lines.product_id'],
            name='fk_service_occurrence_line', ondelete='RESTRICT'),
        ForeignKeyConstraint(['eligibility_id', 'booking_policy_id', 'organization_id', 'branch_id', 'scope_context_key', 'service_product_id', 'provider_resource_id'],
            ['srm_service_specialist_eligibility.id', 'srm_service_specialist_eligibility.booking_policy_id', 'srm_service_specialist_eligibility.organization_id', 'srm_service_specialist_eligibility.branch_id', 'srm_service_specialist_eligibility.scope_context_key', 'srm_service_specialist_eligibility.service_product_id', 'srm_service_specialist_eligibility.provider_resource_id'],
            name='fk_service_occurrence_eligibility', ondelete='RESTRICT'),
        UniqueConstraint('checkout_id', 'occurrence_key', name='uq_service_occurrence_key'),
        CheckConstraint('ends_at > starts_at AND duration_minutes >= 5 AND duration_minutes <= 720', name='ck_service_occurrence_duration'),
        CheckConstraint('policy_revision > 0 AND eligibility_revision > 0 AND revision > 0 AND length(occurrence_key) = 36', name='ck_service_occurrence_revision'),
    )
    id = Column(Integer, primary_key=True)
    checkout_line_id = Column(Integer, nullable=False, unique=True)
    checkout_id = Column(Integer, nullable=False)
    occurrence_key = Column(String(36), nullable=False)
    appointment_id = Column(Integer, ForeignKey('srm_industry_records.id', ondelete='RESTRICT'), nullable=False, unique=True)
    service_product_id = Column(Integer, ForeignKey('srm_products.id', ondelete='RESTRICT'), nullable=False)
    provider_resource_id = Column(Integer, ForeignKey('srm_industry_records.id', ondelete='RESTRICT'), nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id', ondelete='RESTRICT'), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    booking_policy_id = Column(Integer, nullable=False)
    policy_revision = Column(Integer, nullable=False)
    eligibility_id = Column(Integer, nullable=False)
    eligibility_revision = Column(Integer, nullable=False)


class POSCheckoutPayment(_InheritedScope, _Revisioned, Base):
    __tablename__ = 'srm_pos_checkout_payments'
    __table_args__ = (
        ForeignKeyConstraint(['checkout_id', 'organization_id', 'branch_id', 'scope_context_key'],
            ['srm_pos_service_checkouts.id', 'srm_pos_service_checkouts.organization_id', 'srm_pos_service_checkouts.branch_id', 'srm_pos_service_checkouts.scope_context_key'],
            name='fk_checkout_payment_checkout', ondelete='RESTRICT'),
        UniqueConstraint('checkout_id', 'payment_key', name='uq_checkout_payment_key'),
        CheckConstraint('length(payment_key) = 36 AND length(request_sha256) = 64 AND revision > 0', name='ck_checkout_payment_identity'),
    )
    id = Column(Integer, primary_key=True)
    checkout_id = Column(Integer, nullable=False)
    payment_key = Column(String(36), nullable=False)
    receipt_id = Column(Integer, ForeignKey('srm_receipts.id', ondelete='RESTRICT'), nullable=False, unique=True)
    collection_session_id = Column(Integer, ForeignKey('srm_pos_sessions.id', name='fk_checkout_payment_collection_session', ondelete='RESTRICT'), nullable=True)
    request_sha256 = Column(String(64), nullable=False)


MODELS = (ServiceBookingPolicy, ServiceSpecialistEligibility, POSServiceCheckout,
          POSCheckoutLine, POSServiceOccurrence, POSCheckoutPayment)


def _native(connection, name, ident):
    table = Base.metadata.tables.get(name)
    if table is None:
        raise ServiceCheckoutIdentityError('Native source model is not registered')
    row = connection.execute(select(table).where(table.c.id == ident)).mappings().first()
    if row is None:
        raise ServiceCheckoutIdentityError('Native service checkout source is unavailable')
    return row


def _same_company(row, company):
    return (row.get('organization_id') or 1) == company


def _inherit(target, parent):
    for key in ('organization_id', 'branch_id', 'scope_context_key'):
        value = getattr(target, key)
        if value is None:
            setattr(target, key, parent[key])
        elif value != parent[key]:
            raise ServiceCheckoutIdentityError('Checkout child source scope does not match its parent')


def _validate_sources(mapper, connection, target):
    if isinstance(target, (ServiceBookingPolicy, ServiceSpecialistEligibility, POSServiceCheckout)):
        branch = _native(connection, 'branches', target.branch_id)
        if branch['company_id'] != target.organization_id:
            raise ServiceCheckoutIdentityError('Native branch belongs to another company')
    if isinstance(target, ServiceBookingPolicy):
        product = _native(connection, 'srm_products', target.service_product_id)
        if not _same_company(product, target.organization_id) or product['product_type'].lower() not in {'service', 'services'}:
            raise ServiceCheckoutIdentityError('Booking policy requires a native service in the same company')
    elif isinstance(target, ServiceSpecialistEligibility):
        provider = _native(connection, 'srm_industry_records', target.provider_resource_id)
        if not _same_company(provider, target.organization_id) or provider['branch_id'] != target.branch_id or provider['kind'] != 'resource':
            raise ServiceCheckoutIdentityError('Specialist requires a resource in the same native branch')
    elif isinstance(target, POSServiceCheckout):
        buyer = _native(connection, 'crm_companies', target.customer_id)
        session = _native(connection, 'srm_pos_sessions', target.pos_session_id)
        if not _same_company(buyer, target.organization_id) or not _same_company(session, target.organization_id):
            raise ServiceCheckoutIdentityError('Checkout customer and register must belong to this company')
        if target.sales_order_id is not None:
            order = _native(connection, 'srm_sales_orders', target.sales_order_id)
            if not _same_company(order, target.organization_id) or order['customer_id'] != target.customer_id or order['currency'] != target.currency:
                raise ServiceCheckoutIdentityError('Native sales order does not match checkout identity')
        if target.invoice_id is not None:
            invoice = _native(connection, 'srm_invoices', target.invoice_id)
            if (not _same_company(invoice, target.organization_id) or invoice['customer_id'] != target.customer_id
                    or invoice['currency'] != target.currency or invoice['sales_order_id'] != target.sales_order_id):
                raise ServiceCheckoutIdentityError('Native invoice does not match checkout identity')
    elif isinstance(target, (POSCheckoutLine, POSServiceOccurrence, POSCheckoutPayment)):
        checkout = _native(connection, 'srm_pos_service_checkouts', target.checkout_id)
        _inherit(target, checkout)
        if isinstance(target, POSCheckoutLine):
            line = _native(connection, 'srm_sales_order_lines', target.sales_order_line_id)
            if line['sales_order_id'] != checkout['sales_order_id'] or line['product_id'] != target.product_id:
                raise ServiceCheckoutIdentityError('Native order line does not match checkout charge')
            for key in ('quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total'):
                try:
                    value = Decimal(str(getattr(target, key)))
                except (InvalidOperation, TypeError):
                    raise ServiceCheckoutIdentityError('Invalid native charge snapshot') from None
                if not value.is_finite() or value != Decimal(str(line[key])):
                    raise ServiceCheckoutIdentityError('Charge snapshot differs from the native order line')
            if target.invoice_line_id is not None:
                billed = _native(connection, 'srm_invoice_lines', target.invoice_line_id)
                if (billed['invoice_id'] != checkout['invoice_id'] or billed['source_type'] != 'sales_order_line'
                        or billed['source_id'] != target.sales_order_line_id
                        or any(Decimal(str(billed[key])) != Decimal(str(getattr(target, key))) for key in ('quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total'))):
                    raise ServiceCheckoutIdentityError('Invoice line differs from the native checkout charge')
        elif isinstance(target, POSServiceOccurrence):
            line = _native(connection, 'srm_pos_checkout_lines', target.checkout_line_id)
            if line['line_kind'] != 'booked_service' or line['checkout_id'] != target.checkout_id or line['product_id'] != target.service_product_id:
                raise ServiceCheckoutIdentityError('Occurrence requires its booked-service checkout line')
            provider = _native(connection, 'srm_industry_records', target.provider_resource_id)
            employee = _native(connection, 'employees', target.employee_id)
            appointment = _native(connection, 'srm_industry_records', target.appointment_id)
            employee_branch = _native(connection, 'branches', employee['branch_id'])
            if (provider['kind'] != 'resource' or not _same_company(provider, target.organization_id)
                    or provider['branch_id'] != target.branch_id or (provider.get('data') or {}).get('employee_id') != target.employee_id
                    or employee_branch['company_id'] != target.organization_id
                    or appointment['kind'] != 'appointment' or not _same_company(appointment, target.organization_id)
                    or appointment['branch_id'] != target.branch_id or appointment['customer_id'] != checkout['customer_id']):
                raise ServiceCheckoutIdentityError('Occurrence native employee/provider/appointment identity does not match')
            target_state = inspect(target)
            if target_state.pending or any(target_state.attrs[key].history.has_changes() for key in _SCHEDULE):
                policy = _native(connection, 'srm_service_booking_policies', target.booking_policy_id)
                eligibility = _native(connection, 'srm_service_specialist_eligibility', target.eligibility_id)
                if (not policy['active'] or not eligibility['active']
                        or target.policy_revision != policy['revision']
                        or target.eligibility_revision != eligibility['revision']
                        or not policy['min_duration_minutes'] <= target.duration_minutes <= policy['max_duration_minutes']
                        or (not policy['allow_duration_override'] and target.duration_minutes != policy['default_duration_minutes'])):
                    raise ServiceCheckoutIdentityError('Occurrence must snapshot current eligible service policy')
                for key, bound in (('effective_from', 'lower'), ('effective_until', 'upper')):
                    value = eligibility[key]
                    if value is not None:
                        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
                        start = target.starts_at.replace(tzinfo=timezone.utc) if target.starts_at.tzinfo is None else target.starts_at
                        end = target.ends_at.replace(tzinfo=timezone.utc) if target.ends_at.tzinfo is None else target.ends_at
                        if (bound == 'lower' and start < value) or (bound == 'upper' and end > value):
                            raise ServiceCheckoutIdentityError('Occurrence lies outside specialist eligibility')
            # SQLite does not preserve tzinfo on loaded DateTime columns; compare
            # normalized instants while requiring aware values at assignment.
            start = target.starts_at.replace(tzinfo=timezone.utc) if target.starts_at.tzinfo is None else target.starts_at
            end = target.ends_at.replace(tzinfo=timezone.utc) if target.ends_at.tzinfo is None else target.ends_at
            if (end - start).total_seconds() != target.duration_minutes * 60:
                raise ServiceCheckoutIdentityError('Occurrence interval must equal its planned duration')
        else:
            receipt = _native(connection, 'srm_receipts', target.receipt_id)
            if not _same_company(receipt, target.organization_id) or receipt['customer_id'] != checkout['customer_id'] or receipt['currency'] != checkout['currency']:
                raise ServiceCheckoutIdentityError('Native receipt does not match checkout identity')
            if target.collection_session_id is not None:
                session = _native(connection, 'srm_pos_sessions', target.collection_session_id)
                if session.get('organization_id') != target.organization_id:
                    raise ServiceCheckoutIdentityError('Collection register belongs to another company')
                ownership = Base.metadata.tables.get('suite_branch_ownership')
                if ownership is not None and inspect(connection).has_table(ownership.name):
                    proof = connection.execute(select(ownership).where(ownership.c.resource_table == 'srm_pos_sessions',
                        ownership.c.resource_key == str(target.collection_session_id))).mappings().first()
                    if not proof or (proof['company_id'], proof['branch_id']) != (target.organization_id, target.branch_id):
                        raise ServiceCheckoutIdentityError('Collection register lacks exact native branch ownership')
                elif session.get('branch_id') != target.branch_id:
                    raise ServiceCheckoutIdentityError('Collection register branch cannot be verified')


_IDENTITY = {
    ServiceBookingPolicy: ('organization_id', 'branch_id', 'pack_context_id', 'service_product_id'),
    ServiceSpecialistEligibility: ('organization_id', 'branch_id', 'pack_context_id', 'booking_policy_id', 'service_product_id', 'provider_resource_id'),
    POSServiceCheckout: ('organization_id', 'branch_id', 'pack_context_id', 'request_id', 'request_sha256', 'created_by', 'customer_id', 'currency', 'pos_session_id', 'billing_mode'),
    POSCheckoutLine: ('organization_id', 'branch_id', 'scope_context_key', 'checkout_id', 'client_line_key', 'line_kind', 'product_id', 'sales_order_line_id', 'quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total', 'catalog_tax_snapshot'),
    POSServiceOccurrence: ('organization_id', 'branch_id', 'scope_context_key', 'checkout_line_id', 'checkout_id', 'occurrence_key', 'appointment_id', 'service_product_id'),
    POSCheckoutPayment: ('organization_id', 'branch_id', 'scope_context_key', 'checkout_id', 'payment_key', 'receipt_id', 'request_sha256'),
}
_SCHEDULE = frozenset({'provider_resource_id', 'employee_id', 'starts_at', 'ends_at', 'duration_minutes',
                       'booking_policy_id', 'policy_revision', 'eligibility_id', 'eligibility_revision'})


@contextmanager
def occurrence_reschedule_scope(db, occurrence_id):
    """Internal marker only; the caller must first authorize native rescheduling."""
    if type(occurrence_id) is not int or occurrence_id < 1:
        raise ServiceCheckoutIdentityError('A persisted occurrence is required')
    previous = db.info.get('service_checkout_reschedule')
    db.info['service_checkout_reschedule'] = frozenset(previous or ()) | {occurrence_id}
    try:
        yield
    finally:
        if previous is None: db.info.pop('service_checkout_reschedule', None)
        else: db.info['service_checkout_reschedule'] = previous


def _immutable_update(mapper, connection, target):
    state = inspect(target)
    table = target.__table__
    original = connection.execute(select(table).where(table.c.id == state.identity[0])).mappings().one_or_none()
    if original is None or target.id != original['id'] or any(getattr(target, key) != original[key] for key in _IDENTITY[type(target)]):
        raise ServiceCheckoutIdentityError('Checkout identity and native charge snapshots are immutable')
    if state.attrs.revision.history.has_changes() and target.revision != original['revision'] + 1:
        raise ServiceCheckoutRevisionError('Checkout revision must advance exactly once')
    if isinstance(target, POSServiceCheckout):
        for key in ('sales_order_id', 'invoice_id', 'committed_at'):
            before, after = original[key], getattr(target, key)
            if key == 'committed_at' and before is not None and after is not None:
                before = before.replace(tzinfo=timezone.utc) if before.tzinfo is None else before
                after = after.replace(tzinfo=timezone.utc) if after.tzinfo is None else after
            if before is not None and after != before:
                raise ServiceCheckoutIdentityError('A bound native checkout source cannot be replaced')
        transitions = {'draft': {'draft', 'committed', 'cancelled'}, 'committed': {'committed', 'cancelled'}, 'cancelled': {'cancelled'}}
        if target.state not in transitions[original['state']]:
            raise ServiceCheckoutIdentityError('Invalid checkout lifecycle transition')
    elif isinstance(target, POSCheckoutLine) and original['invoice_line_id'] is not None and target.invoice_line_id != original['invoice_line_id']:
        raise ServiceCheckoutIdentityError('An issued native invoice line cannot be replaced')
    elif isinstance(target, POSCheckoutPayment) and original['collection_session_id'] is not None and target.collection_session_id != original['collection_session_id']:
        raise ServiceCheckoutIdentityError('A bound collection register cannot be replaced')
    elif isinstance(target, POSServiceOccurrence):
        changed = any(state.attrs[key].history.has_changes() for key in _SCHEDULE)
        if changed:
            if target.id not in (object_session(target).info.get('service_checkout_reschedule') or ()):
                raise ServiceCheckoutIdentityError('Use the authorized occurrence reschedule operation')
            before = original['starts_at']
            before = before.replace(tzinfo=timezone.utc) if before.tzinfo is None else before
            after = target.starts_at
            after = after.replace(tzinfo=timezone.utc) if after.tzinfo is None else after
            if min(before, after) <= datetime.now(timezone.utc):
                raise ServiceCheckoutIdentityError('Only future service occurrences can be rescheduled')
    _validate_sources(mapper, connection, target)


def _no_delete(mapper, connection, target):
    raise ServiceCheckoutIdentityError('Service checkout source history must be retained')


for _model in MODELS:
    event.listen(_model, 'before_insert', _validate_sources)
    event.listen(_model, 'before_update', _immutable_update)
    event.listen(_model, 'before_delete', _no_delete)
