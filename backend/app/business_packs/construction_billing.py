"""One native certified-measurement invoice command, without a PMS ORM grant."""
from dataclasses import dataclass
from decimal import Decimal
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import exists, inspect, select

_COMMANDS = WeakKeyDictionary()


def deny(message='A certified Construction billing command is required', status=403):
    raise HTTPException(status, message)


@dataclass
class _Command:
    scope: object
    actor: object
    measurement: object
    commercial: object
    snapshot: tuple
    invoice: object = None
    context: object = None


def _snapshot(row):
    return (row.id, row.organization_id, row.branch_id, row.project_id, row.parent_id,
        row.kind, row.status, row.created_by, row.approved_by,
        tuple((key, str(row.data.get(key))) for key in ('quantity', 'unit_rate', 'tax_rate', 'currency')))


def _validate(db, command):
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.service_checkout import _source_scope
    from .construction import project_billing_source
    from .boundary import _current
    scope = db.info.get('business_pack_scope')
    row = command.measurement
    state = inspect(row)
    if (scope is not command.scope or state.session is not db or not state.persistent
            or type(row) is not IndustryRecord or _snapshot(row) != command.snapshot
            or row.kind != 'measurement' or row.status != 'approved'):
        deny()
    _current(scope, db.connection())
    _source_scope(db, scope, scope.company_id, scope.branch_id, IndustryRecord, row.id)
    stored = db.connection().execute(select(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id)).first()
    if stored is None or _snapshot(stored) != command.snapshot:
        deny('Certified Construction source changed')
    if project_billing_source(db, command.actor, row.project_id) != command.commercial:
        deny('Construction commercial identity changed')


def source_reserved(db, source_id):
    """Existence-only reservation, limited to the private command's real source."""
    from app.apps.srm.models import SRMInvoiceLine
    command = _COMMANDS.get(db)
    if command is None or source_id != command.measurement.id:
        deny()
    _validate(db, command)
    table = SRMInvoiceLine.__table__
    return bool(db.connection().scalar(select(exists().where(
        table.c.source_type == 'industry_measurement', table.c.source_id == source_id))))


def project_reference(db, scope, item, parent, pairs):
    from app.apps.project_management.models import PMSProject
    from app.apps.srm.commercial_models import InvoiceContext
    command = _COMMANDS.get(db)
    if (type(item) is not InvoiceContext or parent is not PMSProject.__table__ or len(pairs) != 1
            or pairs[0][0] != 'project_id' or pairs[0][1] is not PMSProject.__table__.c.id):
        return False
    if command is None:
        from app.apps.srm.models import SRMInvoice
        state = inspect(item)
        if not state.persistent or state.session is not db:
            return False
        original = db.connection().execute(select(InvoiceContext.__table__.c.project_id,
            InvoiceContext.__table__.c.invoice_id).where(InvoiceContext.__table__.c.invoice_id == item.invoice_id)).first()
        if original is None or tuple(original) != (item.project_id, item.invoice_id):
            deny('Construction invoice project identity changed')
        invoice = db.get(SRMInvoice, item.invoice_id)
        return invoice is not None and assert_invoice_source(db, invoice)
    if item is not command.context:
        return False
    _validate(db, command)
    invoice, row = command.invoice, command.measurement
    if (scope is not command.scope or invoice is None or inspect(invoice).session is not db
            or item.invoice_id != invoice.id or item.project_id != row.project_id
            or item.seller_id != command.commercial.seller_id or item.origin != 'srm'
            or item.request_id != 'industry:' + str(row.id)
            or invoice.customer_id != command.commercial.customer_id
            or invoice.currency != command.commercial.currency or row.invoice_id != invoice.id):
        deny('Construction invoice parent changed')
    return True


def validate_record(db, row):
    """The original billing source snapshot cannot be rewritten later."""
    from app.apps.srm.industry_models import IndustryRecord
    if type(row) is not IndustryRecord or not inspect(row).persistent:
        return
    table = IndustryRecord.__table__
    original = db.connection().execute(select(table).where(table.c.id == row.id)).first()
    if original is None:
        deny()
    stamp = (original.data or {}).get('_construction_invoice_source')
    if stamp is not None and (row.data.get('_construction_invoice_source') != stamp
            or row.invoice_id != original.invoice_id or _snapshot(row) != _snapshot(original)
            or any(row.data.get(key) != original.data.get(key) for key in ('retention_percent', 'retention_amount'))):
        deny('The original Construction invoice source is immutable')
    if stamp is None and row.data.get('_construction_invoice_source') is not None:
        command = _COMMANDS.get(db)
        if command is None or command.measurement is not row:
            deny()


def assert_invoice_source(db, invoice):
    """Validate one durable private measurement invoice, never a PMS read grant."""
    from app.apps.srm.models import SRMInvoice, SRMInvoiceLine
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.commercial_models import InvoiceContext
    from app.models.user import User
    from .construction import authorize_record_project
    from .models import PackRecordOwnership
    from app.apps.srm.services.commercial import money
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction':
        return False
    state = inspect(invoice, raiseerr=False)
    if (type(invoice) is not SRMInvoice or state is None or not state.persistent
            or state.session is not db or state.identity != (invoice.id,) or invoice in db.deleted):
        deny('Construction invoice requires its actual native identity')
    lines = db.query(SRMInvoiceLine).filter_by(invoice_id=invoice.id).all()
    if not any(line.source_type == 'industry_measurement' for line in lines):
        return False
    if len(lines) != 1 or invoice.sales_order_id is not None or invoice.engagement_id is not None:
        deny('Construction invoice has inconsistent native sources')
    line = lines[0]
    actor = db.get(User, scope.user_id)
    authorize_record_project(db, actor, line.source_id)
    row = db.get(IndustryRecord, line.source_id)
    context = db.get(InvoiceContext, invoice.id)
    stamp = (row.data or {}).get('_construction_invoice_source') if row is not None else None
    if (row is None or context is None or not isinstance(stamp, dict) or stamp.get('version') != 1
            or row.kind != 'measurement' or row.status != 'approved' or row.invoice_id != invoice.id
            or (row.organization_id, row.branch_id, row.project_id) != (scope.company_id, scope.branch_id, context.project_id)
            or stamp.get('invoice_id') != invoice.id or stamp.get('project_id') != row.project_id
            or stamp.get('customer_id') != invoice.customer_id or stamp.get('seller_id') != context.seller_id
            or context.seller_id != scope.company_id or context.request_id != 'industry:' + str(row.id)
            or context.origin != 'srm' or stamp.get('currency') != row.data['currency'] or invoice.currency != row.data['currency']):
        deny('Construction invoice source requires reconciliation', 409)
    for table, identity in ((IndustryRecord.__table__, row.id), (InvoiceContext.__table__, invoice.id)):
        owner = PackRecordOwnership.__table__
        if not db.connection().scalar(select(exists().where(owner.c.resource_table == table.name,
                owner.c.resource_key == str(identity), owner.c.company_id == scope.company_id,
                owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id))):
            deny()
    quantity, rate, tax = (Decimal(row.data[key]) for key in ('quantity', 'unit_rate', 'tax_rate'))
    gross, tax_amount = money(quantity * rate), money(money(quantity * rate) * tax / 100)
    if (tuple(stamp.get(key) for key in ('quantity', 'unit_rate', 'tax_rate')) != tuple(str(row.data[key]) for key in ('quantity', 'unit_rate', 'tax_rate'))
            or line.quantity != quantity or line.unit_price != rate or line.discount_amount != 0
            or line.tax_amount != tax_amount or line.line_total != gross + tax_amount
            or invoice.subtotal != gross or invoice.discount_amount != 0
            or invoice.tax_amount != tax_amount or invoice.total_amount != gross + tax_amount):
        deny('Construction invoice amounts require reconciliation', 409)
    return True


def draft(db, actor, row, data):
    from app.apps.srm.api.router import _create_invoice_from_lines, _invoice_payload
    from app.apps.srm.commercial_models import InvoiceContext
    from app.apps.srm.industry_api import save
    from app.apps.srm.services.commercial import customer, seller, money
    from .construction import project_billing_source
    from app.apps.srm.industry_models import IndustryRecord
    state = inspect(row, raiseerr=False)
    if (type(row) is not IndustryRecord or state is None or not state.persistent
            or state.session is not db or db.is_modified(row, include_collections=True)
            or row.invoice_id is not None or row.kind != 'measurement' or row.status != 'approved'):
        deny('Construction billing requires the unchanged certified source')
    scope = db.info.get('business_pack_scope')
    commercial = project_billing_source(db, actor, row.project_id)
    if commercial is None:
        deny('Link the shared customer and seller in PMS Project Billing first', 422)
    customer(db, commercial.customer_id, actor)
    seller(db, commercial.seller_id, actor)
    if row.data['currency'] != commercial.currency:
        deny('Project currency changed; reconcile approved scope before billing', 409)
    if db in _COMMANDS:
        deny('Construction billing commands cannot nest')
    command = _Command(scope, actor, row, commercial, _snapshot(row))
    _COMMANDS[db] = command
    try:
        _validate(db, command)
        quantity, rate, tax = (Decimal(row.data[key]) for key in ('quantity', 'unit_rate', 'tax_rate'))
        gross = money(quantity * rate)
        invoice = _create_invoice_from_lines(db, actor, 'industry_measurement', row.id, None, None,
            [{'description': row.title, 'quantity': quantity, 'unit_price': rate,
              'tax_amount': money(gross * tax / 100)}], commercial.currency)
        command.invoice = invoice
        invoice.customer_id = commercial.customer_id
        context = InvoiceContext(invoice_id=invoice.id, project_id=row.project_id,
            seller_id=commercial.seller_id, request_id='industry:' + str(row.id), origin='srm')
        command.context = context
        db.add(context)
        row.invoice_id = invoice.id
        row.data = {**row.data, 'retention_percent': str(data.retention_percent),
            'retention_amount': str(money(gross * data.retention_percent / 100)),
            '_construction_invoice_source': {'version': 1, 'invoice_id': invoice.id,
                'project_id': row.project_id, 'customer_id': commercial.customer_id,
                'seller_id': commercial.seller_id, 'currency': commercial.currency,
                **{key: str(row.data[key]) for key in ('quantity', 'unit_rate', 'tax_rate')}}}
        save(db, actor, row, 'invoice_drafted')
        return _invoice_payload(invoice, db)
    finally:
        _COMMANDS.pop(db, None)


def payment(db, actor, ident, data):
    """Collect only against the actual issued invoice for this private measurement."""
    from .access import PackScope
    from app.apps.srm.services.commercial import lock_tenant
    from app.apps.srm.industry_api import get
    from app.apps.srm.payments import record_payment_operation
    scope = db.info.get('business_pack_scope')
    if (not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or scope.user_id != actor.id or not scope.writable or 'construction.payments.record' not in scope.capabilities):
        deny('An authorized Construction collection context is required')
    epoch = collection_authority(db, actor, scope)
    lock_tenant(db, actor)
    if collection_authority(db, actor, scope) != epoch:
        deny('Native Construction collection authority changed while waiting')
    row = get(db, actor, scope.branch_id, ident, 'measurement')
    if row.status != 'approved' or row.invoice_id is None:
        deny('Issue the certified measurement invoice before collecting payment', 409)
    result = record_payment_operation(row.invoice_id, data, db, actor, commit=False)
    db.commit()
    return result


def collection_authority(db, actor, scope):
    """Retain native collection create permission and financial approve action."""
    from .native_checkout_authority import capture
    from .catalog_management import _module_grant
    epoch = capture(db, actor, scope, order=False, billing=False, payments=True, write=True)
    if not actor.is_superuser and 'approve' not in _module_grant(db, actor, scope, 'srm').get('actions', ()):
        deny('Native collection approval action is required')
    return epoch
