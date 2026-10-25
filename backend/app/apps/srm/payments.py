"""Atomic, idempotent collection actions against the existing SRM receipt ledger."""
from app.access.catalog import permission_objects
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMInvoiceHistory, SRMRevenueEvent
from app.apps.srm.commercial_models import InvoiceContext, ReceiptContext
from app.apps.srm.services.commercial import require, invoice_for, invoice_query, tenant, seller, money

router = APIRouter()


def summary(db, invoice):
    ctx = db.get(InvoiceContext, invoice.id)
    return {"id": invoice.id, "invoice_number": invoice.invoice_number, "customer_id": invoice.customer_id,
        "seller_id": ctx.seller_id if ctx else (invoice.organization_id or 1), "currency": invoice.currency,
        "total_amount": invoice.total_amount, "paid_amount": invoice.paid_amount, "balance_amount": invoice.balance_amount,
        "document_status": "cancelled" if invoice.status == "cancelled" else "draft" if invoice.status in {"draft", "pending_approval"} else "issued",
        "payment_status": "not_payable" if invoice.status == "cancelled" else "paid" if invoice.balance_amount == 0 else "partially_paid" if invoice.paid_amount else "unpaid",
        "delivery_status": "sent" if invoice.sent_at else "not_sent", "project_id": ctx.project_id if ctx else None}


@router.get("/business/collection-invoices")
def collection_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require(user, "srm_collection_view", "srm_collection_create", "srm_admin")
    names = {p.name for p in (permission_objects(user))}
    rows = invoice_query(db, user).order_by(SRMInvoice.id.desc()).limit(200).all()
    return {"items": [summary(db, r) for r in rows], "can_record": user.is_superuser or bool(names.intersection({"srm_collection_create", "srm_admin"}))}


class PaymentInput(BaseModel):
    request_id: UUID
    amount: Decimal
    reference: str = Field("", max_length=120)
    payment_method: str = Field("bank_transfer", max_length=60)
    receipt_date: date | None = None


@router.post("/business/invoices/{invoice_id}/payments", status_code=201)
def record_payment(invoice_id: int, data: PaymentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.srm.api.router import _next_number, _audit
    require(user, "srm_collection_create", "srm_admin")
    invoice = invoice_for(db, invoice_id, user, lock=True)
    previous = db.query(ReceiptContext).filter_by(invoice_id=invoice_id, request_id=str(data.request_id)).first()
    if previous:
        return {"receipt_id": previous.receipt_id, "invoice": summary(db, invoice), "reversed": bool(previous.reversed_at)}
    amount = money(data.amount).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    if amount <= 0 or amount > Decimal(invoice.balance_amount or 0) or invoice.status in {"draft", "pending_approval", "cancelled"}:
        raise HTTPException(422, "Apply a positive amount within the issued invoice's outstanding balance")
    ctx = db.get(InvoiceContext, invoice.id)
    seller_id = ctx.seller_id if ctx else (invoice.organization_id or 1)
    seller(db, seller_id, user)
    receipt = SRMReceipt(organization_id=tenant(user), receipt_number=_next_number(db, SRMReceipt, "RCT", "receipt_number", tenant(user)), customer_id=invoice.customer_id,
        status="allocated", receipt_date=data.receipt_date or date.today(), payment_method=data.payment_method,
        reference_number=data.reference, currency=invoice.currency, amount=amount, unallocated_amount=0, created_by=user.id)
    db.add(receipt); db.flush()
    db.add(SRMReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id, amount=amount, allocated_by=user.id))
    db.add(ReceiptContext(receipt_id=receipt.id, seller_id=seller_id, invoice_id=invoice.id, request_id=str(data.request_id)))
    invoice.paid_amount = Decimal(invoice.paid_amount or 0) + amount
    invoice.balance_amount = Decimal(invoice.total_amount) - invoice.paid_amount
    invoice.status = "paid" if invoice.balance_amount == 0 else "partially_paid"
    db.add(SRMRevenueEvent(organization_id=invoice.organization_id, engagement_id=invoice.engagement_id, invoice_id=invoice.id, event_type="cash_collected", amount=amount, currency=invoice.currency, recognized_on=date.today()))
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, to_status=invoice.status, actor_user_id=user.id, notes=f"Receipt {receipt.id} applied; correlation {data.request_id}"))
    _audit(db, user, "receipt", receipt.id, "payment_applied", after={"invoice_id": invoice.id, "correlation_id": str(data.request_id), "amount": str(amount)})
    db.commit()
    return {"receipt_id": receipt.id, "invoice": summary(db, invoice), "reversed": False}


class ReversePaymentInput(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/business/payments/{receipt_id}/reverse")
def reverse_payment(receipt_id: int, data: ReversePaymentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.fam.models import FAMSRMMapping
    from app.apps.srm.api.router import _audit
    require(user, "srm_invoice_approve", "srm_admin")
    ctx = db.get(ReceiptContext, receipt_id)
    if not ctx or not ctx.invoice_id:
        raise HTTPException(409, "Legacy or multi-invoice receipts require finance reconciliation")
    invoice = invoice_for(db, ctx.invoice_id, user, lock=True)
    db.refresh(ctx)
    receipt = db.get(SRMReceipt, receipt_id)
    if ctx.reversed_at:
        return {"receipt_id": receipt_id, "invoice": summary(db, invoice), "reversed": True}
    allocations = db.query(SRMReceiptAllocation).filter_by(receipt_id=receipt_id).all()
    mapped = db.query(FAMSRMMapping).filter(FAMSRMMapping.company_id == tenant(user), ((FAMSRMMapping.srm_record_type == "receipt") & (FAMSRMMapping.srm_record_id == receipt_id)) | ((FAMSRMMapping.srm_record_type == "allocation") & FAMSRMMapping.srm_record_id.in_([a.id for a in allocations]))).all()
    if any(m.srm_record_type == "allocation" for m in mapped) or (any(m.fam_record_type == "voucher" for m in mapped) and not any(m.fam_record_type == "reversal_voucher" for m in mapped)):
        raise HTTPException(409, "Reverse/reconcile the posted FAM payment and bill allocation through Accounting first")
    ctx.reversed_at, ctx.reversal_reason = datetime.now(timezone.utc), data.reason
    receipt.status, receipt.unallocated_amount = "cancelled", Decimal("0")
    invoice.paid_amount -= Decimal(receipt.amount)
    invoice.balance_amount = Decimal(invoice.total_amount) - invoice.paid_amount
    invoice.status = "partially_paid" if invoice.paid_amount > 0 else "sent" if invoice.sent_at else "approved"
    db.add(SRMRevenueEvent(organization_id=invoice.organization_id, engagement_id=invoice.engagement_id, invoice_id=invoice.id, event_type="cash_reversed", amount=-Decimal(receipt.amount), currency=invoice.currency, recognized_on=date.today()))
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, to_status=invoice.status, actor_user_id=user.id, notes=f"Receipt {receipt_id} reversed: {data.reason}"))
    _audit(db, user, "receipt", receipt_id, "payment_reversed", after={"invoice_id": invoice.id, "reason": data.reason, "correlation_id": ctx.request_id})
    db.commit()
    return {"receipt_id": receipt_id, "invoice": summary(db, invoice), "reversed": True}
