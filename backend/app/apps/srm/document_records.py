"""Browser document controls over the existing commercial records and audit ledger."""
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from typing import Literal
from uuid import UUID, uuid4
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.apps.crm.models import CRMQuotation, CRMQuotationItem, CRMCompany
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine, SRMContract, SRMPurchaseOrder, SRMPurchaseOrderLine, SRMInvoice, SRMInvoiceLine, SRMInvoiceDraft, SRMAuditLog, SRMGoodsReceipt, SRMInvoiceHistory
from app.apps.srm.services.commercial import require, record, tenant, lock_tenant, invoice_for, money

router = APIRouter()
Kind = Literal['quotations', 'purchase-orders', 'sales-orders', 'contracts', 'invoices']
DEFINITIONS = {
    'quotations': (CRMQuotation, 'quote_number', 'quotation', CRMQuotationItem, 'quotation_id'),
    'purchase-orders': (SRMPurchaseOrder, 'po_number', 'purchase_order', SRMPurchaseOrderLine, 'purchase_order_id'),
    'sales-orders': (SRMSalesOrder, 'order_number', 'sales_order', SRMSalesOrderLine, 'sales_order_id'),
    'contracts': (SRMContract, 'contract_number', 'contract', None, None),
    'invoices': (SRMInvoice, 'invoice_number', 'invoice', SRMInvoiceLine, 'invoice_id'),
}


class DocumentAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=5, max_length=500)
    version: str = Field(min_length=64, max_length=64)
    request_id: UUID
    recipient: str | None = Field(default=None, max_length=254)
    changes: dict = Field(default_factory=dict)
    lines: list[dict] | None = Field(default=None, max_length=200)


def authorize(user, kind, write=False):
    if kind == 'quotations':
        require(user, *(['crm_quotes_manage', 'crm_manage', 'crm_admin'] if write else ['crm_quotes_view', 'crm_view', 'crm_quotes_manage', 'crm_manage', 'crm_admin']))
    elif kind == 'invoices':
        require(user, *(['srm_invoice_create', 'srm_admin'] if write else ['srm_invoice_view', 'srm_invoice_create', 'srm_invoice_approve', 'srm_admin']))
    else:
        require(user, *(['srm_manage', 'srm_admin'] if write else ['srm_view', 'srm_manage', 'srm_admin']))


def load(db, user, kind, ident, write=False):
    authorize(user, kind, write)
    if write:
        lock_tenant(db, user)
    if kind == 'invoices':
        return invoice_for(db, ident, user, lock=write, include_removed=not write)
    if kind == 'quotations':
        from app.apps.crm.api.router import _get_record, _get_resource, _organization_id, _assert_record_visible
        organization = _organization_id(db, user)
        resource = _get_resource('quotations')
        value = _get_record(db, resource, ident, organization)
        _assert_record_visible(db, resource, ident, organization, user)
        return value
    if kind == 'sales-orders':
        from app.apps.srm.api.router import get_sales_order_for_user
        return get_sales_order_for_user(db, ident, user, include_removed=not write)
    return record(db, DEFINITIONS[kind][0], ident, user, include_removed=not write)


def snapshot(db, kind, row):
    # Signed download capabilities rotate on reads; they are not document values.
    result = jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != 'pdf_url'})
    line_model, foreign_key = DEFINITIONS[kind][3:]
    if line_model:
        result['lines'] = [jsonable_encoder({c.name: getattr(line, c.name) for c in line.__table__.columns}) for line in db.query(line_model).filter(getattr(line_model, foreign_key) == row.id).order_by(line_model.id).all()]
    return result


def version(value):
    import json
    # Refreshing a signed PDF link can touch ORM metadata without changing the
    # agreed document. Only substantive values participate in edit concurrency.
    volatile = {'updated_at','pdf_url','pdf_file_name','pdf_status','pdf_generated_at','pdf_generated_by_user_id'}
    content = {key:item for key,item in value.items() if key not in volatile}
    return sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit(db, user, kind, row, action, before, after, data):
    from app.apps.srm.api.router import _audit
    _audit(db, user, DEFINITIONS[kind][2], row.id, action, before=before, after={'record': after, 'reason': data.reason.strip(), 'request_id': str(data.request_id)})


def previous_action(db, user, kind, row, data, action):
    logs = db.query(SRMAuditLog).filter_by(organization_id=tenant(user), entity_type=DEFINITIONS[kind][2], entity_id=row.id, action=action).order_by(SRMAuditLog.id.desc()).all()
    return next((log for log in logs if (log.after_json or {}).get('request_id') == str(data.request_id)), None)


def check_change(db, kind, row, data):
    if len(data.reason.strip()) < 5:
        raise HTTPException(422, 'Enter a meaningful reason of at least five characters')
    if version(snapshot(db, kind, row)) != data.version:
        raise HTTPException(409, 'This document changed. Refresh before continuing.')


def draft(row):
    return str(row.status or '').lower() in {'draft', 'created', 'planned'}


def detail(db, user, kind, row):
    current = snapshot(db, kind, row)
    logs = db.query(SRMAuditLog).filter_by(organization_id=tenant(user), entity_type=DEFINITIONS[kind][2], entity_id=row.id).order_by(SRMAuditLog.id.desc()).limit(100).all()
    return {'record': current, 'version': version(current), 'number': getattr(row, DEFINITIONS[kind][1]), 'editable': draft(row), 'removed':str(row.status).lower() in {'deleted','archived'}, 'history': [jsonable_encoder({'id': log.id, 'action': log.action, 'actor_id': log.actor_user_id, 'created_at': log.created_at, 'before': log.before_json, 'after': log.after_json, 'reason': (log.after_json or {}).get('reason')}) for log in logs]}


@router.get('/documents/{kind}/{ident}')
def document_record(kind: Kind, ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return detail(db, user, kind, load(db, user, kind, ident))


@router.get('/documents/{kind}')
def document_register(kind: Kind, search: str = Query(default='', max_length=200), status: str = Query(default='', max_length=40), include_removed: bool = False, page: int = Query(default=1, ge=1), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.services.commercial import scoped
    authorize(user, kind)
    model, number_key = DEFINITIONS[kind][:2]
    query = db.query(model).filter(scoped(model.organization_id, user))
    if kind == 'invoices':
        from app.apps.srm.services.commercial import invoice_query
        query = invoice_query(db, user, include_removed=include_removed)
    if not include_removed:
        if hasattr(model, 'deleted_at'):
            query = query.filter(model.deleted_at.is_(None))
        query = query.filter(model.status.notin_(['Deleted','archived']))
    if search.strip():
        escaped = search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(getattr(model, number_key).ilike('%'+escaped+'%', escape='\\'))
    if status:
        query = query.filter(model.status == status)
    if kind == 'quotations':
        from app.apps.crm.api.router import _base_query, _get_resource, _organization_id
        visible = _base_query(db, _get_resource('quotations'), _organization_id(db, user))
        query = query.filter(model.id.in_(visible.with_entities(model.id)))
    rows = query.order_by(model.id.desc()).offset((page-1)*50).limit(50).all()
    visible_rows = []
    for row in rows:
        try:
            load(db, user, kind, row.id)
            visible_rows.append(row)
        except HTTPException as exc:
            if exc.status_code not in {403,404}:
                raise
    return {'items':[{'id':r.id, 'number':getattr(r,number_key), 'status':r.status, 'total':getattr(r,'total_amount',getattr(r,'contract_value',None)), 'currency':getattr(r,'currency',None), 'created_at':r.created_at, 'removed':bool(getattr(r,'deleted_at',None)) or str(r.status).lower() in {'deleted','archived'}} for r in visible_rows], 'has_more':len(rows)==50, 'page':page}


def apply_changes(db, kind, row, data):
    allowed = {
        'quotations': {'notes', 'terms', 'terms_and_conditions', 'expiry_date'},
        'purchase-orders': {'notes', 'expected_date'},
        'sales-orders': {'title', 'terms'},
        'contracts': {'title', 'terms', 'effective_date', 'expiry_date'},
        'invoices': {'due_date'},
    }[kind]
    if set(data.changes) - allowed:
        raise HTTPException(422, 'Unsupported document fields')
    for key, value in data.changes.items():
        if key.endswith('_date'):
            try:
                value = date.fromisoformat(str(value)) if value else None
            except ValueError:
                raise HTTPException(422, 'Enter a valid document date')
        elif not isinstance(value, str) or len(value) > 10000:
            raise HTTPException(422, 'Document text is too long or invalid')
        if key == 'title' and not str(value).strip():
            raise HTTPException(422, 'A document title is required')
        if kind == 'quotations' and key == 'expiry_date' and (not value or value < row.issue_date):
            raise HTTPException(422, 'Expiry must be on or after the issue date')
        setattr(row, key, value)
    if kind == 'contracts' and row.effective_date and row.expiry_date and row.expiry_date < row.effective_date:
        raise HTTPException(422, 'End date must follow start date')
    if data.lines is None:
        return
    if not data.lines or kind == 'contracts':
        raise HTTPException(422, 'At least one document line is required')
    if any(type(item.get('id')) is not int for item in data.lines):
        raise HTTPException(422, 'Each document line needs its saved numeric identity')
    model, foreign = DEFINITIONS[kind][3:]
    lines = db.query(model).filter(getattr(model, foreign) == row.id).order_by(model.id).all()
    if len(data.lines) != len(lines) or {line.id for line in lines} != {item.get('id') for item in data.lines}:
        raise HTTPException(409, 'Document lines changed. Refresh before editing.')
    subtotal = discount = tax = total = Decimal('0')
    for line in lines:
        item = next(item for item in data.lines if item['id'] == line.id)
        if set(item) - {'id', 'description', 'quantity', 'unit_price', 'tax_amount', 'discount_amount', 'tax_rate'}:
            raise HTTPException(422, 'Unsupported line fields')
        description = item.get('description', getattr(line, 'name', None) or getattr(line, 'description', ''))
        if not isinstance(description, str) or not description.strip() or len(description) > 2000:
            raise HTTPException(422, 'Enter a line description')
        quantity = money(item.get('quantity', line.quantity))
        price = money(item.get('unit_price', line.unit_price))
        if quantity <= 0 or quantity > 1000000:
            raise HTTPException(422, 'Quantity must be greater than zero and at most one million')
        line.quantity, line.unit_price = quantity, price
        if kind == 'quotations':
            from app.apps.crm.api.router import _apply_quote_line_calculation
            line.name = description
            line.discount_type = 'amount'
            line.discount_value = money(item.get('discount_amount', line.discount_amount or 0))
            line.tax_rate = money(item.get('tax_rate', line.tax_rate or 0))
            _apply_quote_line_calculation(line)
        else:
            line.description = description
            line.tax_amount = money(item.get('tax_amount', line.tax_amount or 0))
            deduction = money(item.get('discount_amount', getattr(line, 'discount_amount', 0) or 0))
            if kind == 'purchase-orders' and deduction:
                raise HTTPException(422, 'Purchase order discounts must be included in the agreed unit price')
            if deduction > quantity * price:
                raise HTTPException(422, 'Discount exceeds the line value')
            if hasattr(line, 'discount_amount'):
                line.discount_amount = deduction
            line.line_total = (quantity * price - deduction + line.tax_amount).quantize(Decimal('.01'))
        subtotal += quantity * price
        discount += Decimal(str(getattr(line, 'discount_amount', 0) or 0))
        total += Decimal(str(line.line_total))
        tax += Decimal(str(line.line_total)) - quantity * price + Decimal(str(getattr(line, 'discount_amount', 0) or 0))
    if kind == 'quotations':
        from app.apps.crm.api.router import _recalculate_quote
        db.flush()
        _recalculate_quote(db, row)
    else:
        for amount in (subtotal,discount,tax,total):
            money(amount)
        row.subtotal, row.tax_amount, row.total_amount = subtotal, tax, total
        if hasattr(row, 'discount_amount'):
            row.discount_amount = discount
        if kind == 'invoices':
            row.balance_amount = total
            invoice_draft = db.get(SRMInvoiceDraft, row.invoice_draft_id)
            if invoice_draft:
                invoice_draft.subtotal, invoice_draft.discount_amount, invoice_draft.tax_amount, invoice_draft.total_amount = subtotal, discount, tax, total


@router.patch('/documents/{kind}/{ident}')
def edit_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident, True)
    if previous_action(db, user, kind, row, data, 'document_modified'):
        return detail(db, user, kind, row)
    check_change(db, kind, row, data)
    if not draft(row):
        raise HTTPException(409, 'Issued documents are retained. Create a revision draft to make changes.')
    if kind == 'sales-orders' and data.lines is not None and db.query(SRMInvoice).filter_by(sales_order_id=row.id).first():
        raise HTTPException(409, 'This order has invoices. Create a revision instead.')
    before = snapshot(db, kind, row)
    apply_changes(db, kind, row, data)
    db.flush()
    audit(db, user, kind, row, 'document_modified', before, snapshot(db, kind, row), data)
    db.commit()
    return detail(db, user, kind, row)


@router.post('/documents/{kind}/{ident}/revise', status_code=201)
def revise_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident, True)
    prior = previous_action(db, user, kind, row, data, 'revision_created')
    if prior:
        target = load(db, user, kind, prior.after_json['record']['id'])
        return detail(db, user, kind, target)
    check_change(db, kind, row, data)
    before = snapshot(db, kind, row)
    if kind == 'invoices':
        from app.apps.srm.api.router import _create_invoice_from_lines
        active_revision = db.query(SRMInvoiceLine).join(SRMInvoice, SRMInvoice.id==SRMInvoiceLine.invoice_id).filter(SRMInvoiceLine.source_type.like('invoice_revision_line%'), SRMInvoiceLine.source_id.in_([line.id for line in row.lines]), SRMInvoice.status.notin_(['archived','cancelled']), SRMInvoice.deleted_at.is_(None)).first()
        if active_revision:
            raise HTTPException(409, 'An active revision already exists. Open that draft or revise the latest issued invoice.')
        lines = [{key: getattr(line, key) for key in ['description', 'quantity', 'unit_price', 'discount_amount', 'tax_amount']} | {'source_type':f'invoice_revision_line:{data.request_id}', 'source_id':line.id} for line in row.lines]
        target = _create_invoice_from_lines(db, user, 'invoice_revision', None, None, None, lines, row.currency)
        target.customer_id = row.customer_id
        target.due_date = row.due_date
        db.get(SRMInvoiceDraft, target.invoice_draft_id).customer_id = row.customer_id
        from app.apps.srm.services.commercial import context
        from app.apps.srm.commercial_models import InvoiceContext
        source_context = db.get(InvoiceContext, row.id)
        target_context = context(db, target, user)
        if source_context:
            target_context.seller_id, target_context.contact_id = source_context.seller_id, source_context.contact_id
    else:
        model, number_key = DEFINITIONS[kind][:2]
        from app.apps.srm.api.router import _next_number
        excluded = {'id', number_key, 'created_at', 'updated_at', 'deleted_at', 'approved_at', 'approved_by', 'approval_request_id', 'signed_by_customer_at', 'signed_by_company_at', 'sent_at', 'accepted_at', 'declined_at', 'pdf_url', 'pdf_file_name', 'pdf_generated_at', 'pdf_generated_by_user_id', 'converted_srm_sales_order_id', 'converted_srm_contract_id', 'converted_srm_engagement_id'}
        values = {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in excluded}
        values['status'] = 'Draft' if kind == 'quotations' else 'draft'
        values[number_key] = f'{row.quote_number[:38]}-R{(row.version_number or 1)+1}-{uuid4().hex[:8]}' if kind == 'quotations' else _next_number(db, model, {'purchase-orders':'PO', 'sales-orders':'SO', 'contracts':'CTR'}[kind], number_key, tenant(user), actor=user)
        if kind == 'quotations':
            values.update(approval_status='not_submitted', version_number=(row.version_number or 1)+1, created_by_user_id=user.id, updated_by_user_id=user.id, pdf_status=None)
            # A revised offer must not silently replace the deal's accepted order.
            values['deal_id'] = None
        else:
            values['created_by'] = user.id
        target = model(**values)
        db.add(target)
        db.flush()
        line_model, foreign = DEFINITIONS[kind][3:]
        if line_model:
            for old_line in db.query(line_model).filter(getattr(line_model, foreign) == row.id).order_by(line_model.id).all():
                values = {c.name: getattr(old_line, c.name) for c in old_line.__table__.columns if c.name not in {'id', foreign, 'quote_id', 'received_quantity'}}
                values[foreign] = target.id
                if kind == 'quotations':
                    values['quote_id'] = target.id
                db.add(line_model(**values))
    db.flush()
    if data.changes:
        apply_changes(db, kind, target, data.model_copy(update={'lines':None}))
    db.flush()
    audit(db, user, kind, row, 'revision_created', before, {'id':target.id, 'number':getattr(target, DEFINITIONS[kind][1])}, data)
    audit(db, user, kind, target, 'revised_from', None, {'source_id':row.id, 'source_number':getattr(row, DEFINITIONS[kind][1]), 'snapshot':before}, data)
    db.commit()
    return detail(db, user, kind, target)


@router.delete('/documents/{kind}/{ident}')
def remove_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident, True)
    check_change(db, kind, row, data)
    if not draft(row):
        raise HTTPException(409, 'Issued documents cannot be deleted. Retain the record and use cancellation.')
    if kind == 'quotations' and (row.converted_srm_sales_order_id or row.sent_at):
        raise HTTPException(409, 'This quotation has issued or converted history')
    if kind == 'sales-orders':
        from app.apps.srm.models import SRMEngagement
        if any(db.query(model).filter_by(sales_order_id=row.id).first() for model in [SRMInvoice, SRMInvoiceDraft, SRMContract, SRMEngagement]):
            raise HTTPException(409, 'This order has linked commercial records')
    if kind == 'contracts':
        from app.apps.srm.models import SRMEngagement
        if db.query(SRMEngagement).filter_by(contract_id=row.id).first():
            raise HTTPException(409, 'This contract has a linked engagement')
    if kind == 'purchase-orders' and db.query(SRMGoodsReceipt).filter_by(purchase_order_id=row.id).first():
        raise HTTPException(409, 'This purchase order has receipts')
    if kind == 'invoices':
        from app.apps.srm.commercial_models import InvoiceContext
        ctx = db.get(InvoiceContext, row.id)
        if row.approved_at or (ctx and ctx.issued_at) or row.paid_amount:
            raise HTTPException(409, 'This invoice has financial history')
    before = snapshot(db, kind, row)
    audit(db, user, kind, row, 'draft_removed', before, {'retained':True}, data)
    # Soft removal, including quotations that lack a deleted_at column.
    row.status = 'Deleted' if kind == 'quotations' else 'archived'
    if hasattr(row, 'deleted_at'):
        row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return detail(db, user, kind, row)


def document_pdf(db, user, kind, row):
    if kind == 'invoices':
        from app.apps.srm.services.commercial import invoice_document
        return invoice_document(db, row)
    if kind == 'quotations':
        from app.apps.crm.api.router import _generate_quotation_pdf
        path, _, _ = _generate_quotation_pdf(db, row, tenant(user), user.id)
        from pathlib import Path
        return Path(path).read_bytes()
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    value = snapshot(db, kind, row)
    output = BytesIO()
    styles = getSampleStyleSheet()
    parts = [Paragraph(escape(kind.replace('-', ' ').title()), styles['Title']), Paragraph(escape(str(getattr(row, DEFINITIONS[kind][1]))), styles['Heading2'])]
    for key in ['vendor_name', 'title', 'status', 'order_date', 'currency', 'subtotal', 'tax_amount', 'total_amount', 'contract_value', 'notes', 'terms']:
        if value.get(key) is not None:
            parts.append(Paragraph(escape(f'{key.replace("_", " ").title()}: {value[key]}'), styles['Normal']))
    for line in value.get('lines', []):
        parts.extend([Spacer(1,8),Paragraph(escape(f'{line.get("description", "")} | {line.get("quantity")} × {line.get("unit_price")} | Total {line.get("line_total")}'), styles['Normal'])])
    SimpleDocTemplate(output).build(parts)
    return output.getvalue()


@router.get('/documents/{kind}/{ident}/pdf')
def download_document(kind: Kind, ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident)
    body = document_pdf(db, user, kind, row)
    return Response(body, media_type='application/pdf', headers={'Content-Disposition':f'attachment; filename="{kind}-{ident}.pdf"'})


@router.post('/documents/{kind}/{ident}/send')
def resend_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident, True)
    prior = previous_action(db, user, kind, row, data, 'document_delivery')
    if prior:
        return {**prior.after_json['record'], 'document':detail(db, user, kind, row)}
    check_change(db, kind, row, data)
    if draft(row) or str(row.status).lower() in {'cancelled', 'deleted', 'archived', 'rejected', 'declined'}:
        raise HTTPException(409, 'Issue or approve the document before sending')
    if kind == 'quotations':
        require(user, 'crm_quotes_send', 'crm_manage', 'crm_admin')
        if str(row.status).lower() not in {'approved','sent','accepted'}:
            raise HTTPException(409, 'Approve the quotation before sending')
    if kind == 'invoices':
        from app.apps.srm.services.commercial import send
        from app.apps.srm.commercial_models import InvoiceDelivery
        uncertain = db.query(InvoiceDelivery).filter(InvoiceDelivery.invoice_id == row.id, InvoiceDelivery.status.in_(['sending','unknown'])).first()
        if uncertain:
            raise HTTPException(409, 'Review the outstanding delivery attempt before resending')
        result = jsonable_encoder(send(db, row, user, str(data.request_id), data.recipient))
        audit(db, user, kind, row, 'document_delivery', None, result, data)
        db.commit()
        return {**result, 'document':detail(db, user, kind, row)}
    from app.apps.communication.models import CommunicationEmailMessage
    from app.apps.communication.services.delivery import deliver_email, validate_email
    attempts = db.query(SRMAuditLog).filter_by(organization_id=tenant(user), entity_type=DEFINITIONS[kind][2], entity_id=row.id, action='document_delivery').all()
    if any((entry.after_json or {}).get('record',{}).get('status') in {'sending','unknown'} for entry in attempts):
        raise HTTPException(409, 'Review the outstanding delivery attempt before resending')
    recipient = (data.recipient or '').strip()
    if not recipient:
        party = db.get(CRMCompany, getattr(row, 'company_id', None) or getattr(row, 'vendor_id', None) or getattr(row, 'customer_id', None))
        recipient = party.email if party and party.organization_id == tenant(user) else ''
    validate_email(recipient)
    body = document_pdf(db, user, kind, row)
    message = CommunicationEmailMessage(related_record_type=DEFINITIONS[kind][2], related_record_id=row.id, to_email=recipient, subject=f'{kind.replace("-", " ").title()} {getattr(row, DEFINITIONS[kind][1])}', body='Please find the requested document attached.', sent_by=user.id, status='queued')
    db.add(message)
    db.flush()
    # Persist an attempt before delivery; retries of the same request never send twice.
    result = {'status':'sending', 'recipient':recipient, 'message_id':message.id, 'document_sha256':sha256(body).hexdigest()}
    audit(db, user, kind, row, 'document_delivery', None, result, data)
    db.commit()
    log = previous_action(db, user, kind, row, data, 'document_delivery')
    try:
        deliver_email(db, message, user, attachments=[(f'{kind}-{ident}.pdf',body,'application/pdf')])
        result['status'] = message.status
        result['error'] = message.error_message
        if kind == 'quotations' and message.status == 'sent':
            row.sent_at = row.sent_at or datetime.now(timezone.utc)
            if str(row.status).lower() == 'approved':
                row.status = 'Sent'
    except Exception:
        result['status'] = 'unknown'
        result['error'] = 'Delivery outcome is uncertain. Review the provider before resending.'
    log.after_json = {**log.after_json, 'record':result}
    db.commit()
    return {**result, 'document':detail(db, user, kind, row)}


@router.post('/documents/{kind}/{ident}/issue')
def issue_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if kind != 'purchase-orders':
        raise HTTPException(409, 'Use the established approval workflow for this document')
    row = load(db, user, kind, ident, True)
    if previous_action(db, user, kind, row, data, 'document_issued'):
        return detail(db, user, kind, row)
    check_change(db, kind, row, data)
    if not draft(row) or not row.lines:
        raise HTTPException(409, 'Only a purchase order draft with lines can be issued')
    before = snapshot(db, kind, row)
    row.status = 'ordered'
    audit(db, user, kind, row, 'document_issued', before, snapshot(db, kind, row), data)
    db.commit()
    return detail(db, user, kind, row)


def cancel_unused_order_delivery(db, user, order, data):
    """Retain and close confirmation scaffolding; never unwind actual delivery."""
    from app.apps.srm.models import SRMEngagement, SRMEngagementLink, SRMBillingPlan, SRMBillingMilestone, SRMRevenueEvent, SRMInventoryMovement
    from app.apps.srm.api.router import _audit
    from app.shared.follow_ups import cancel_for_order
    blocked = 'Review linked delivery and invoicing before cancelling this order'
    if db.query(SRMInvoice.id).filter(SRMInvoice.sales_order_id == order.id, SRMInvoice.deleted_at.is_(None), SRMInvoice.status != 'cancelled').first():
        raise HTTPException(409, blocked)
    if db.query(SRMInvoiceDraft.id).filter(SRMInvoiceDraft.sales_order_id == order.id, SRMInvoiceDraft.status.notin_(['cancelled', 'archived', 'converted', 'invoiced'])).first():
        raise HTTPException(409, blocked)
    if db.query(SRMContract.id).filter(SRMContract.sales_order_id == order.id, SRMContract.deleted_at.is_(None), SRMContract.status.notin_(['cancelled', 'archived'])).first():
        raise HTTPException(409, blocked)
    if (order.metadata_json or {}).get('inventory_issued_at') or db.query(SRMInventoryMovement.id).filter_by(organization_id=order.organization_id, reference_number=order.order_number).first():
        raise HTTPException(409, 'Review issued inventory and returns before cancelling this order')
    engagements = db.query(SRMEngagement).filter_by(sales_order_id=order.id).with_for_update().all()
    pending = []
    # Validate every dependency before changing any of them.
    for engagement in engagements:
        if engagement.organization_id != order.organization_id or engagement.pms_project_id or engagement.status not in {'created', 'project_pending', 'cancelled'}:
            raise HTTPException(409, blocked)
        if db.query(SRMEngagementLink.id).filter(SRMEngagementLink.engagement_id == engagement.id, SRMEngagementLink.linked_module.notin_(['crm', 'srm'])).first() or db.query(SRMRevenueEvent.id).filter_by(engagement_id=engagement.id).first():
            raise HTTPException(409, blocked)
        if db.query(SRMInvoice.id).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at.is_(None), SRMInvoice.status != 'cancelled').first() or db.query(SRMInvoiceDraft.id).filter(SRMInvoiceDraft.engagement_id == engagement.id, SRMInvoiceDraft.status.notin_(['cancelled', 'archived', 'converted', 'invoiced'])).first():
            raise HTTPException(409, blocked)
        plans = db.query(SRMBillingPlan).filter_by(engagement_id=engagement.id).with_for_update().all()
        for plan in plans:
            if plan.organization_id != order.organization_id or plan.status not in {'draft', 'cancelled'} or plan.recurrence_rule:
                raise HTTPException(409, blocked)
            milestones = db.query(SRMBillingMilestone).filter_by(billing_plan_id=plan.id).with_for_update().all()
            if any(row.invoice_draft_id or row.status not in {'draft', 'pending', 'planned', 'cancelled'} for row in milestones):
                raise HTTPException(409, blocked)
            pending.append(('billing_plan', plan, milestones))
        pending.append(('engagement', engagement, []))
    for entity, row, milestones in pending:
        for milestone in milestones:
            before = {'status': milestone.status}
            milestone.status = 'cancelled'
            _audit(db, user, 'billing_milestone', milestone.id, 'cancelled_with_order', before=before, after={'status': 'cancelled', 'reason': data.reason, 'sales_order_id': order.id})
        before = {'status': row.status}
        row.status = 'cancelled'
        _audit(db, user, entity, row.id, 'cancelled_with_order', before=before, after={'status': 'cancelled', 'reason': data.reason, 'sales_order_id': order.id})
    cancel_for_order(db, order.id, user)


@router.post('/documents/{kind}/{ident}/cancel')
def cancel_document(kind: Kind, ident: int, data: DocumentAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = load(db, user, kind, ident, True)
    if previous_action(db, user, kind, row, data, 'document_cancelled'):
        return detail(db, user, kind, row)
    check_change(db, kind, row, data)
    before = snapshot(db, kind, row)
    if kind == 'invoices':
        from app.apps.srm.commercial_api import cancel_invoice, CancelInvoiceInput
        cancel_invoice(row.id, CancelInvoiceInput(reason=data.reason.strip()), db, user)
    elif kind == 'purchase-orders':
        if db.query(SRMGoodsReceipt).filter_by(purchase_order_id=row.id).first():
            raise HTTPException(409, 'This purchase order has receipts. Review supplier returns first.')
        row.status = 'cancelled'
    elif kind == 'quotations':
        if row.converted_srm_sales_order_id:
            raise HTTPException(409, 'This quote has a linked order. Review that commercial commitment first.')
        row.status = 'Cancelled'
    else:
        from app.apps.srm.models import SRMEngagement
        if kind == 'sales-orders':
            cancel_unused_order_delivery(db, user, row, data)
        elif db.query(SRMEngagement).filter_by(contract_id=row.id).first():
            raise HTTPException(409, 'Review the linked engagement before cancelling this contract')
        row.status = 'cancelled'
    audit(db, user, kind, row, 'document_cancelled', before, snapshot(db, kind, row), data)
    db.commit()
    return detail(db, user, kind, row)
