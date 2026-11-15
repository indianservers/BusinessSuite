"""Source-reserved native invoices for independently approved service periods."""
from dataclasses import dataclass
from weakref import WeakKeyDictionary
from sqlalchemy import select, exists, inspect, event
from app.apps.srm.models import SRMEngagement, SRMInvoiceLine, SRMInvoice, SRMInvoiceDraft
from app.apps.srm.services.commercial import require, lock_tenant, invoice_for
from app.business_packs.common_core import _native_authority
from . import service
from .models import AccountsCommand, AccountsPeriod

_COMMANDS = WeakKeyDictionary()


def assert_invoice_source(db, invoice):
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.commercial_models import InvoiceContext
    from app.models.user import User
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'accounting_firm':
        return False
    state = inspect(invoice, raiseerr=False)
    if type(invoice) is not SRMInvoice or state is None or not state.persistent or state.session is not db:
        service.fail('Accounts billing requires its actual native invoice')
    lines = db.query(SRMInvoiceLine).filter_by(invoice_id=invoice.id).all()
    if not any(line.source_type == 'accounts_period' for line in lines):
        return False
    if len(lines) != 1 or invoice.sales_order_id is not None:
        service.fail('Accounts invoice sources require reconciliation', 409)
    line = lines[0]
    actor = db.get(User, scope.user_id)
    row = service.record(db, actor, scope, line.source_id)
    engagement = db.get(SRMEngagement, row.engagement_id)
    command = service.scoped(db, AccountsCommand, scope).filter_by(period_id=row.id, action='invoice').one_or_none()
    context = db.get(InvoiceContext, invoice.id)
    if (command is None or context is None or command.result.get('invoice_id') != invoice.id
            or command.result.get('period_id') != row.id or command.result.get('approved_work_revision', 0) < 1
            or invoice.engagement_id != row.engagement_id or invoice.customer_id != row.client_id
            or engagement.pms_project_id != command.result.get('project_id')
            or invoice.currency != command.result.get('currency') or str(invoice.total_amount) != command.result.get('total_amount')
            or context.project_id is not None or context.seller_id != scope.company_id or context.origin != 'srm'
            or context.request_id != 'accounts-period:' + str(row.id)
            or line.quantity != 1 or line.unit_price != invoice.total_amount or line.discount_amount != 0
            or line.tax_amount != 0 or line.line_total != invoice.total_amount
            or invoice.subtotal != invoice.total_amount or invoice.discount_amount != 0 or invoice.tax_amount != 0):
        service.fail('Accounts invoice differs from its certified source', 409)
    if engagement.pms_project_id is not None:
        from .pms_sources import project_for_action
        project_for_action(db, actor, engagement.pms_project_id)
    return True


@dataclass
class _Draft:
    actor: object
    scope: object
    period: object
    revision: int
    work_revision: int
    authority: str
    amount: object
    invoice: object = None
    native_draft: object = None
    certificate: object = None


def _capture_native(mapper, connection, row):
    db = inspect(row).session
    command = _COMMANDS.get(db)
    if command is None:
        return
    engagement = db.get(SRMEngagement, command.period.engagement_id)
    if (row.id is not None or row.organization_id != command.scope.company_id or row.created_by != command.actor.id
            or row.engagement_id != engagement.id or row.customer_id != engagement.customer_id
            or row.sales_order_id is not None or row.currency != engagement.currency
            or row.total_amount != command.amount or row.subtotal != command.amount or row.tax_amount != 0
            or row.discount_amount != 0 or row.status not in (None, 'draft')):
        service.fail('Accounts native invoice birth differs from its approved command', 409)
    if type(row) is SRMInvoiceDraft:
        if command.native_draft is not None or row.source_type != 'accounts_period':
            service.fail('Accounts requires exactly one native period invoice draft', 409)
        command.native_draft = row
    else:
        if command.invoice is not None or command.native_draft is None or row.invoice_draft_id != command.native_draft.id:
            service.fail('Accounts requires its actual newly generated native invoice', 409)
        command.invoice = row


event.listen(SRMInvoiceDraft, 'before_insert', _capture_native)
event.listen(SRMInvoice, 'before_insert', _capture_native)


@event.listens_for(AccountsCommand, 'before_insert')
def _certify_billing(mapper, connection, row):
    if row.action != 'invoice':
        return
    db = inspect(row).session
    command = _COMMANDS.get(db)
    if (command is None or command.certificate is not row or command.invoice is None
            or row.id is not None or row.created_at is not None or row.period_id != command.period.id
            or row.created_by != command.actor.id or row.pack_context_id != command.scope.context_id
            or row.organization_id != command.scope.company_id or row.branch_id != command.scope.branch_id
            or row.result.get('invoice_id') != command.invoice.id
            or row.result.get('approved_work_revision') != command.work_revision):
        service.fail('A genuine native Accounts invoice certificate is required', 409)


def linked_engagement_authorized(db, actor, engagement):
    """Finite exception for the exact active approved-period billing source."""
    command = _COMMANDS.get(db)
    if (command is None or command.actor is not actor or command.scope is not db.info.get('business_pack_scope')
            or engagement.id != command.period.engagement_id or inspect(engagement).session is not db
            or engagement.customer_id != command.period.client_id or engagement.pms_project_id is None
            or command.authority != _native_authority(db, actor, command.scope.company_id)):
        service.fail('The linked engagement requires its exact Accounts billing command')
    from .pms_sources import project_for_action
    project = project_for_action(db, actor, engagement.pms_project_id)
    if project.currency != engagement.currency:
        service.fail('Project and engagement currency require reconciliation', 409)
    from app.apps.srm.commercial_models import ProjectCommercial
    table = ProjectCommercial.__table__
    rows = db.connection().execute(select(table.c.project_id, table.c.customer_id, table.c.seller_id, table.c.currency)
        .where((table.c.project_id == project.id) | (table.c.engagement_id == engagement.id))).all()
    if any(tuple(row) != (project.id, engagement.customer_id, command.scope.company_id, engagement.currency) for row in rows):
        service.fail('Native project commercial linkage requires reconciliation', 409)
    return True


def source_reserved(db, ident):
    """Only a genuine in-progress approved-period command can use this source."""
    command = _COMMANDS.get(db)
    if command is None or ident != command.period.id:
        service.fail('An exact Accounts period billing command is required')
    row, scope = command.period, command.scope
    state = inspect(row)
    if (db.info.get('business_pack_scope') is not scope or state.session is not db or not state.persistent
            or db.is_modified(row) or row.state != 'approved' or row.revision != command.revision
            or row.work_revision != command.work_revision or row.approved_work_revision != row.work_revision
            or _native_authority(db, command.actor, scope.company_id) != command.authority):
        service.fail('Accounts billing source or authority changed', 409)
    service.record(db, command.actor, scope, row.id)
    table = AccountsPeriod.__table__
    actual = db.connection().execute(select(table.c.revision, table.c.work_revision,
        table.c.approved_work_revision, table.c.state).where(table.c.id == row.id)).one()
    if tuple(actual) != (row.revision, row.work_revision, row.work_revision, 'approved'):
        service.fail('Accounts billing requires the actual approved source', 409)
    lines = SRMInvoiceLine.__table__
    return bool(db.connection().scalar(select(exists().where(
        lines.c.source_type == 'accounts_period', lines.c.source_id == ident))))


def draft(ident, data, db, actor, *, commit=True):
    scope = service.authority(db, actor, 'billing.prepare', write=True)
    require(actor, 'srm_invoice_create', 'srm_admin')
    epoch = _native_authority(db, actor, scope.company_id)
    lock_tenant(db, actor)
    service.authority(db, actor, 'billing.prepare', write=True)
    if epoch != _native_authority(db, actor, scope.company_id):
        service.fail('Native billing authority changed while waiting')
    row = service.record(db, actor, scope, ident)
    old = service.replay(db, actor, scope, 'invoice', ident, data)
    if old is not None:
        invoice_for(db, old['invoice_id'], actor)
        return old
    service.source(db, actor, scope, row.engagement_id, row.client_id, require_open=True)
    if (row.revision != data.expected_revision or row.work_revision != data.expected_work_revision
            or row.state != 'approved' or row.approved_work_revision != row.work_revision):
        service.fail('Bill only the current independently approved work revision', 409)
    if service.scoped(db, AccountsCommand, scope).filter_by(period_id=ident, action='invoice').first():
        service.fail('This service period already has a native invoice', 409)
    engagement = db.get(SRMEngagement, row.engagement_id)
    # The shared project-commercial adapter remains a separate integration gate.
    if engagement.pms_project_id is not None:
        from .pms_sources import project_for_action
        project_for_action(db, actor, engagement.pms_project_id)
    from app.apps.srm.api.router import _create_invoice_from_amount
    from app.apps.srm.commercial_models import InvoiceContext
    if db in _COMMANDS:
        service.fail('Accounts billing commands cannot nest')
    with db.begin_nested():
        _COMMANDS[db] = _Draft(actor, scope, row, row.revision, row.work_revision, epoch, data.amount)
        try:
            invoice = _create_invoice_from_amount(db, actor, 'accounts_period', row.id,
                engagement, None, data.amount, row.title, engagement.currency)
            if _COMMANDS[db].invoice is not invoice or not inspect(invoice).persistent or inspect(invoice).session is not db:
                service.fail('Accounts cannot adopt an existing invoice as a new billing command', 409)
            db.add(InvoiceContext(invoice_id=invoice.id, seller_id=scope.company_id,
                request_id='accounts-period:' + str(row.id), origin='srm'))
            dto = {'period_id': row.id, 'invoice_id': invoice.id,
                'approved_work_revision': row.work_revision, 'currency': invoice.currency,
                'total_amount': str(invoice.total_amount), 'project_id': engagement.pms_project_id}
            certificate = AccountsCommand(**service.fields(scope, actor), period_id=row.id,
                request_key=str(data.request_key), request_sha256=service.fingerprint('invoice', ident, data),
                action='invoice', reason='', result=dto)
            _COMMANDS[db].certificate = certificate
            db.add(certificate)
            db.flush()
            if (invoice.total_amount != data.amount or invoice.balance_amount != data.amount
                    or invoice.paid_amount != 0 or not assert_invoice_source(db, invoice)):
                service.fail('Native invoice differs from the approved period fee', 409)
        finally:
            _COMMANDS.pop(db, None)
    if commit:
        db.commit()
    return dto


def outstanding(ident, db, actor):
    scope = service.read_authority(db, actor, ('billing.view','billing.prepare','payments.record'))
    require(actor, 'srm_invoice_view', 'srm_invoice_create', 'srm_invoice_approve', 'srm_admin')
    row = service.record(db, actor, scope, ident)
    command = service.scoped(db, AccountsCommand, scope).filter_by(period_id=row.id, action='invoice').one_or_none()
    if command is None:
        return {'period_id': row.id, 'invoice': None}
    invoice = invoice_for(db, command.result['invoice_id'], actor)
    if invoice.engagement_id != row.engagement_id or invoice.customer_id != row.client_id:
        service.fail('Accounts native invoice source requires reconciliation', 409)
    return {'period_id': row.id, 'invoice': {'id': invoice.id, 'number': invoice.invoice_number,
        'status': invoice.status, 'currency': invoice.currency, 'total_amount': str(invoice.total_amount),
        'paid_amount': str(invoice.paid_amount), 'balance_amount': str(invoice.balance_amount)}}


def collect(ident, data, db, actor):
    from app.apps.srm.payments import can_record, record_payment_operation
    scope = service.authority(db, actor, 'payments.record', write=True)
    epoch = _native_authority(db, actor, scope.company_id)
    lock_tenant(db, actor)
    service.authority(db, actor, 'payments.record', write=True)
    if epoch != _native_authority(db, actor, scope.company_id) or not can_record(db, actor):
        service.fail('Fresh native collection permissions are required')
    row = service.record(db, actor, scope, ident)
    command = service.scoped(db, AccountsCommand, scope).filter_by(period_id=row.id, action='invoice').one_or_none()
    if command is None:
        service.fail('Issue a native invoice before collecting payment', 409)
    invoice = invoice_for(db, command.result['invoice_id'], actor)
    if not assert_invoice_source(db, invoice):
        service.fail('The period requires its certified native invoice', 409)
    with db.begin_nested():
        result = record_payment_operation(invoice.id, data, db, actor, commit=False)
    db.commit()
    return result
