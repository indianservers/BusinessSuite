"""Appointment checkout over native receipts, allocations and invoice approvals."""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.apps.srm.industry_api import Strict, context, get, fail, revision, save
from app.apps.srm.services.commercial import require, tenant, money as validate_money, lock_tenant, invoice_for
from app.apps.srm.models import SRMReceipt
from app.apps.srm.schemas import SRMReceiptCreate, SRMReceiptAllocationRequest

router = APIRouter(prefix='/appointments')
ACTIVE_RECEIPTS = {'confirmed', 'partially_allocated', 'allocated'}


def money(value):
    return validate_money(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class PaymentInput(Strict):
    request_id: UUID
    expected_revision: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: str = Field(default='cash', min_length=1, max_length=60)
    reference_number: str = Field(default='', max_length=120)


class ApplyInput(Strict):
    expected_revision: int = Field(ge=1)


def appointment_for(db, user, ident, write=False):
    require(user, 'srm_collection_create', 'srm_admin') if write else require(user, 'srm_collection_view', 'srm_collection_create', 'srm_invoice_view', 'srm_invoice_create', 'srm_admin')
    branch = context(db, user, appointments=True)
    if write:
        from app.branches.service import access
        if branch not in access(db, user, tenant(user))[1]:
            fail('Branch write access is required', 403)
        lock_tenant(db, user)
    return get(db, user, branch, ident, 'appointment')


def billing_state(db, user, row):
    records = row.data.get('_payment_requests', {})
    ids = [entry['receipt_id'] for entry in records.values()]
    receipts = db.query(SRMReceipt).filter(SRMReceipt.organization_id == tenant(user), SRMReceipt.customer_id == row.customer_id, SRMReceipt.id.in_(ids)).order_by(SRMReceipt.id).all() if ids else []
    invoice = invoice_for(db, row.invoice_id, user) if row.invoice_id else None
    if invoice and (invoice.customer_id != row.customer_id or invoice.currency != row.data['currency']):
        fail('The linked invoice no longer matches this appointment. Reconcile billing before collecting payments.', 409)
    currency = invoice.currency if invoice else row.data['currency']
    quoted = money(Decimal(row.data['unit_price']) + money(Decimal(row.data['unit_price']) * Decimal(row.data['tax_rate']) / 100))
    total = money(invoice.total_amount) if invoice else quoted
    advances = money(sum((r.unallocated_amount for r in receipts if r.status in ACTIVE_RECEIPTS and r.currency == currency), Decimal(0)))
    paid = money(invoice.paid_amount) if invoice else Decimal(0)
    balance = max(Decimal(0), total - paid - advances)
    return {'appointment_id': row.id, 'revision': row.revision, 'visit_status': row.status, 'currency': currency,
            'total': total, 'paid': paid, 'advance': advances, 'balance': balance,
            'invoice': {'id': invoice.id, 'number': invoice.invoice_number, 'status': invoice.status, 'balance': invoice.balance_amount} if invoice else None,
            'receipts': [{'id': r.id, 'number': r.receipt_number, 'status': r.status, 'amount': r.amount,
                          'unallocated': r.unallocated_amount, 'method': r.payment_method, 'reference': r.reference_number} for r in receipts]}


@router.get('/{ident}/billing')
def billing(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return billing_state(db, user, appointment_for(db, user, ident))


def apply_receipt(db, user, row, receipt, invoice):
    from app.apps.srm.api.router import allocate_receipt_operation
    amount = min(money(receipt.unallocated_amount), money(invoice.balance_amount))
    if amount <= 0:
        return False
    allocation_key = uuid5(NAMESPACE_URL, f'appointment:{row.id}:receipt:{receipt.id}:invoice:{invoice.id}')
    allocate_receipt_operation(receipt.id, SRMReceiptAllocationRequest(invoice_id=invoice.id, amount=amount, request_id=allocation_key), db, user, commit=False)
    return True


@router.post('/{ident}/payments', status_code=201)
def record_payment(ident: int, data: PaymentInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.api.router import create_receipt_operation, confirm_receipt_operation
    row = appointment_for(db, user, ident, True)
    requests = dict(row.data.get('_payment_requests', {}))
    key = str(data.request_id)
    details = {'amount': str(money(data.amount)), 'payment_method': data.payment_method, 'reference_number': data.reference_number}
    if key in requests:
        if requests[key]['details'] != details:
            fail('Payment request was already used with different details', 409)
        return billing_state(db, user, row)
    revision(row, data.expected_revision)
    if row.status in {'cancelled', 'no_show'}:
        fail('Payments cannot be collected for cancelled or missed appointments', 409)
    state = billing_state(db, user, row)
    if state['invoice'] and state['invoice']['status'] == 'cancelled':
        fail('Payments cannot be collected for a cancelled invoice', 409)
    if data.amount > state['balance']:
        fail('Payment exceeds the appointment balance', 422)
    customer_id = row.customer_id
    from app.shared.form_defaults import effective
    local_zone = effective(db, tenant(user), 'srm', row.branch_id)['values']['timezone']
    payload = SRMReceiptCreate(receipt_number=f'APPT-{row.id}-{data.request_id.hex}', customer_id=customer_id,
                               receipt_date=datetime.now(ZoneInfo(local_zone)).date(),
                               amount=data.amount, currency=state['currency'], payment_method=data.payment_method,
                               reference_number=data.reference_number or None)
    receipt_data = create_receipt_operation(payload, db, user, commit=False)
    confirm_receipt_operation(receipt_data['id'], db, user, commit=False)
    receipt = db.get(SRMReceipt, receipt_data['id'])
    requests[key] = {'receipt_id': receipt.id, 'details': details}
    row.data = {**row.data, '_payment_requests': requests}
    if row.invoice_id:
        invoice = invoice_for(db, row.invoice_id, user, lock=True)
        if invoice.status not in {'draft', 'pending_approval', 'cancelled'}:
            apply_receipt(db, user, row, receipt, invoice)
    save(db, user, row, 'payment_recorded')
    return billing_state(db, user, row)


@router.post('/{ident}/apply-advances')
def apply_advances(ident: int, data: ApplyInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = appointment_for(db, user, ident, True)
    revision(row, data.expected_revision)
    if not row.invoice_id:
        fail('Create and approve the invoice before applying advances', 409)
    invoice = invoice_for(db, row.invoice_id, user, lock=True)
    if invoice.status in {'draft', 'pending_approval', 'cancelled'}:
        fail('Approve the invoice before applying advances', 409)
    ids = [entry['receipt_id'] for entry in row.data.get('_payment_requests', {}).values()]
    receipts = db.query(SRMReceipt).filter(SRMReceipt.organization_id == tenant(user), SRMReceipt.customer_id == row.customer_id, SRMReceipt.id.in_(ids), SRMReceipt.status.in_(ACTIVE_RECEIPTS)).order_by(SRMReceipt.id).with_for_update().all()
    changed = False
    for receipt in receipts:
        changed = apply_receipt(db, user, row, receipt, invoice) or changed
    if changed:
        save(db, user, row, 'advances_applied')
    return billing_state(db, user, row)
