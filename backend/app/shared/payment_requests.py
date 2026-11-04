"""Shared POS/CRM/invoice requests; issuing a request never records a receipt."""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.apps.srm.services.commercial import tenant, require, lock_tenant, invoice_for
from app.shared.payment_models import PaymentRequest
from app.shared.payment_gateway import gateway_for, verified_link, provider_reference

router = APIRouter(prefix="/payment-requests", tags=["Payment requests"])
Source = Literal["crm_deal", "crm_quotation", "srm_order", "srm_invoice"]
ACTIVE = ("awaiting_gateway", "creating_link", "reconciliation_required", "link_ready", "partially_paid")


def source_context(db, user, kind, ident, *, write=False):
    guidance = "Use the issued invoice or linked sales order for collection if this record has been handed over."
    from app.module_registry import is_app_enabled
    module = "crm" if kind.startswith("crm_") else "srm"
    if not is_app_enabled(module):
        raise HTTPException(404, "Payment source module is not installed.")
    grants = getattr(user, "_suite_grants", None)
    if grants is not None and not user.is_superuser and not grants.get(module, {}).get("enabled"):
        raise HTTPException(403, "This payment source application is not enabled for your account.")
    from app.apps.business_os.services.module_service import assert_module_enabled
    assert_module_enabled(db, module, tenant(user))
    if write:
        lock_tenant(db, user)
    if kind == "srm_invoice":
        require(user, "srm_collection_create", "srm_admin")
        row = invoice_for(db, ident, user, lock=write)
        from app.apps.srm.commercial_models import InvoiceContext
        invoice_context = db.get(InvoiceContext, row.id)
        if invoice_context and invoice_context.seller_id != tenant(user):
            raise HTTPException(409, "Switch to the invoice seller's organization to request payment through its gateway.")
        ceiling = Decimal(row.balance_amount or 0)
        reference = row.invoice_number
        payable = row.status not in {"draft", "pending_approval", "cancelled", "paid"}
    elif kind == "srm_order":
        from app.apps.srm.access import get_sales_order_for_user
        require(user, "srm_manage", "srm_admin")
        row = get_sales_order_for_user(db, ident, user)
        ceiling, reference = Decimal(row.total_amount or 0), row.order_number
        payable = str(row.status).lower() not in {"cancelled", "rejected", "closed"}
        metadata = row.metadata_json or {}
        if metadata.get("source") == "pos" and metadata.get("payment_mode") not in {"Credit", "Payment request"}:
            payable = False
            guidance = "This POS order was completed with a payment method. Review Collections before requesting any further payment."
        # An issued invoice becomes the authoritative collection source.
        from app.apps.srm.models import SRMInvoice
        if db.query(SRMInvoice.id).filter(SRMInvoice.sales_order_id == row.id,
            func.coalesce(SRMInvoice.organization_id, 1) == tenant(user), SRMInvoice.deleted_at.is_(None),
            ~SRMInvoice.status.in_(["draft", "pending_approval", "cancelled"])).first():
            payable = False
    else:
        from app.apps.crm import productivity as crm
        entity = "deals" if kind == "crm_deal" else "quotations"
        if not crm.allowed(user, entity, "manage"):
            raise HTTPException(403, "Managing this CRM record is required to request payment.")
        row = crm.rows(db, user, entity, lock=write).filter_by(id=ident).first()
        if not row:
            raise HTTPException(404, "Payment source not found")
        if kind == "crm_deal":
            ceiling, reference = Decimal(row.amount or 0), row.name
        else:
            ceiling, reference = Decimal(row.grand_total or row.total_amount or 0), row.quote_number
        payable = str(getattr(row, "status", "")).lower() not in {"lost", "cancelled", "declined", "rejected", "expired"}
        # Once handed over, request against the linked order/invoice instead.
        from app.apps.srm.models import SRMSalesOrder
        link = SRMSalesOrder.crm_deal_id if kind == "crm_deal" else SRMSalesOrder.crm_quote_id
        if db.query(SRMSalesOrder.id).filter(link == row.id, func.coalesce(SRMSalesOrder.organization_id, 1) == tenant(user),
            SRMSalesOrder.deleted_at.is_(None), ~SRMSalesOrder.status.in_(["cancelled", "rejected"])).first():
            payable = False
    # Carry reservations across CRM -> order -> invoice handover so the same
    # obligation cannot be requested twice through two screens.
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice
    from app.apps.crm.models import CRMQuotation
    quote_id = row.id if kind == "crm_quotation" else getattr(row, "crm_quote_id", None)
    deal_id = row.id if kind == "crm_deal" else getattr(row, "deal_id", None) or getattr(row, "crm_deal_id", None)
    order_id = row.id if kind == "srm_order" else getattr(row, "sales_order_id", None)
    if order_id:
        order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == order_id, func.coalesce(SRMSalesOrder.organization_id, 1) == tenant(user)).first()
        if order:
            deal_id, quote_id = order.crm_deal_id, order.crm_quote_id
    if quote_id and not deal_id:
        quote = db.query(CRMQuotation).filter(CRMQuotation.id == quote_id, func.coalesce(CRMQuotation.organization_id, 1) == tenant(user)).first()
        deal_id = quote.deal_id if quote else None
    quotes = db.query(CRMQuotation.id).filter(func.coalesce(CRMQuotation.organization_id, 1) == tenant(user),
        or_(CRMQuotation.id == quote_id, CRMQuotation.deal_id == deal_id if deal_id else False))
    orders = db.query(SRMSalesOrder.id).filter(func.coalesce(SRMSalesOrder.organization_id, 1) == tenant(user),
        or_(SRMSalesOrder.id == order_id, SRMSalesOrder.crm_deal_id == deal_id if deal_id else False, SRMSalesOrder.crm_quote_id.in_(quotes)))
    invoices = db.query(SRMInvoice.id).filter(func.coalesce(SRMInvoice.organization_id, 1) == tenant(user), SRMInvoice.sales_order_id.in_(orders))
    family = or_(
        (PaymentRequest.source_type == kind) & (PaymentRequest.source_id == ident),
        PaymentRequest.deal_id == deal_id if deal_id else False,
        PaymentRequest.quotation_id.in_(quotes), PaymentRequest.sales_order_id.in_(orders), PaymentRequest.invoice_id.in_(invoices))
    reserved = db.query(func.coalesce(func.sum(PaymentRequest.amount), 0)).filter(
        PaymentRequest.organization_id == tenant(user), family, PaymentRequest.status.in_((*ACTIVE, "gateway_paid"))).scalar()
    return {"reference": str(reference or f"{kind} #{ident}"), "currency": str(row.currency or "INR"), "source_amount": str(ceiling),
        "available_amount": str(max(Decimal(0), ceiling - Decimal(reserved or 0)) if payable else Decimal(0)),
        "payable": payable and ceiling > 0,
        "guidance": guidance}


def public(row):
    return {key: getattr(row, key) for key in ("id", "request_id", "source_type", "source_id", "reference", "amount", "currency", "instructions", "status", "provider", "payment_url", "amount_paid", "receipt_id", "created_at")}


def authorized_request(db, user, ident, *, write=False):
    # Lock in one order (tenant, source, request) across creation and transitions.
    if write:
        lock_tenant(db, user)
    row = db.query(PaymentRequest).filter_by(id=ident, organization_id=tenant(user)).first()
    if not row:
        raise HTTPException(404, "Payment request not found")
    source_context(db, user, row.source_type, row.source_id)
    if write:
        db.refresh(row, with_for_update=True)
    return row


@router.get("/context")
def context(source_type: Source, source_id: int = Query(gt=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = source_context(db, user, source_type, source_id)
    gateway = gateway_for(tenant(user))
    from app.access.catalog import permission_names
    can_match = user.is_superuser or bool(permission_names(user).intersection({"srm_collection_create", "srm_admin"}))
    return {**result, "can_match_receipt": can_match, "gateway": {"connected": bool(gateway), "provider": gateway.name if gateway else None,
        "test_mode": gateway.test_mode if gateway else False, "planned_provider": "razorpay"}}


@router.get("")
def listing(source_type: Source, source_id: int = Query(gt=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    source_context(db, user, source_type, source_id)
    rows = db.query(PaymentRequest).filter_by(organization_id=tenant(user), source_type=source_type, source_id=source_id).order_by(PaymentRequest.id.desc()).limit(100).all()
    return {"items": [public(row) for row in rows]}


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    source_type: Source
    source_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, le=999999999999, max_digits=14, decimal_places=2, allow_inf_nan=False)
    instructions: str = Field(default="", max_length=2000)


@router.post("", status_code=201)
def create(data: CreateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ctx = source_context(db, user, data.source_type, data.source_id, write=True)
    old = db.query(PaymentRequest).filter_by(organization_id=tenant(user), request_id=str(data.request_id)).first()
    if old:
        if (old.source_type, old.source_id, old.amount, old.instructions) != (data.source_type, data.source_id, data.amount, data.instructions):
            raise HTTPException(409, "This payment request reference was already used for different details.")
        return public(old)
    if not ctx["payable"] or data.amount > Decimal(ctx["available_amount"]):
        raise HTTPException(422, "Request a positive amount within the available balance. Existing payment requests already reserve their amounts.")
    row = PaymentRequest(organization_id=tenant(user), request_id=str(data.request_id), source_type=data.source_type,
        source_id=data.source_id, reference=ctx["reference"][:180], amount=data.amount, currency=ctx["currency"],
        instructions=data.instructions, created_by=user.id, status="awaiting_gateway")
    setattr(row, {"crm_deal":"deal_id", "crm_quotation":"quotation_id", "srm_order":"sales_order_id", "srm_invoice":"invoice_id"}[data.source_type], data.source_id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This payment reference is already reserved. Refresh requests before retrying.") from None
    db.refresh(row)
    return public(row)


def bound_gateway(row):
    gateway = gateway_for(row.organization_id)
    if not gateway:
        raise HTTPException(409, "No payment gateway is connected for this organization. The request is saved; connect Razorpay to generate an online payment link.")
    if row.provider_account and row.provider_account != gateway.account:
        raise HTTPException(409, "This request belongs to a different payment account. Restore that account before reconciliation.")
    return gateway


@router.post("/{ident}/link")
def create_link(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = authorized_request(db, user, ident, write=True)
    if row.status in {"cancelled", "expired", "gateway_paid", "receipt_recorded"}:
        raise HTTPException(409, "This payment request cannot create another link.")
    gateway = bound_gateway(row)
    if row.payment_url:
        return public(row)
    if row.currency not in getattr(gateway, "currencies", {"INR"}):
        raise HTTPException(422, "This payment gateway connection currently supports INR requests only.")
    ctx = source_context(db, user, row.source_type, row.source_id)
    if not ctx["payable"] or row.amount > Decimal(ctx["source_amount"]) or row.currency != ctx["currency"]:
        raise HTTPException(409, "The source amount, currency or payable status changed. Cancel this request and use the current invoice or order.")
    if row.status in {"creating_link", "reconciliation_required"}:
        data = gateway.find(provider_reference(row))
        if not data:
            raise HTTPException(409, "The original provider outcome is unresolved. Reconcile this reference in Razorpay before issuing another request.")
    else:
        row.status, row.provider, row.provider_account = "creating_link", gateway.name, gateway.account
        db.commit()  # Reserve before external I/O; retries must reconcile, never blindly re-send.
        try:
            data = gateway.create(row)
        except HTTPException:
            row.status = "reconciliation_required"; db.commit()
            raise
    try:
        verified_link(row, data)
    except HTTPException:
        row.status = "reconciliation_required"; db.commit()
        raise
    db.commit(); db.refresh(row)
    return public(row)


@router.post("/{ident}/refresh")
def refresh(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = authorized_request(db, user, ident, write=True)
    if row.receipt_id:
        return public(row)
    gateway = bound_gateway(row)
    data = gateway.fetch(row.provider_id) if row.provider_id else gateway.find(provider_reference(row))
    if not data:
        raise HTTPException(409, "No matching provider link was found. This request remains unresolved.")
    verified_link(row, data)
    db.commit(); db.refresh(row)
    # Provider payment evidence is intentionally distinct from an allocated receipt.
    return public(row)


@router.post("/{ident}/cancel")
def cancel(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = authorized_request(db, user, ident, write=True)
    if row.status == "cancelled":
        return public(row)
    if row.amount_paid or row.receipt_id or row.status == "gateway_paid":
        raise HTTPException(409, "Received payments require financial reconciliation, not request cancellation.")
    if row.status in {"creating_link", "reconciliation_required"} and not row.provider_id:
        raise HTTPException(409, "Reconcile the original provider outcome before cancelling.")
    if row.provider_id:
        data = bound_gateway(row).cancel(row.provider_id)
        verified_link(row, data)
        if row.status != "cancelled":
            db.commit()
            raise HTTPException(409, "The provider has not confirmed cancellation.")
    else:
        row.status = "cancelled"
    db.commit(); db.refresh(row)
    return public(row)


@router.post("/{ident}/reconcile-receipt")
def reconcile_receipt(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Match actual ledger evidence; a message or browser callback is not evidence."""
    from app.apps.srm.models import SRMReceipt, SRMReceiptAllocation, SRMInvoice, SRMSalesOrder
    from app.apps.srm.commercial_models import ReceiptContext
    require(user, "srm_collection_create", "srm_admin")
    row = authorized_request(db, user, ident, write=True)
    if row.receipt_id:
        return public(row)
    references = [row.request_id] + ([row.provider_id] if row.provider_id else [])
    query = db.query(SRMReceipt, SRMInvoice).join(ReceiptContext, ReceiptContext.receipt_id == SRMReceipt.id).join(
        SRMReceiptAllocation, SRMReceiptAllocation.receipt_id == SRMReceipt.id).join(SRMInvoice, SRMInvoice.id == SRMReceiptAllocation.invoice_id).filter(
        func.coalesce(SRMReceipt.organization_id, 1) == tenant(user),
        func.coalesce(SRMInvoice.organization_id, 1) == tenant(user), ReceiptContext.reversed_at.is_(None),
        SRMReceipt.status == "allocated",
        SRMReceipt.reference_number.in_(references), SRMReceipt.currency == row.currency,
        SRMReceipt.amount == row.amount, SRMReceiptAllocation.amount == row.amount)
    if row.source_type == "srm_invoice":
        query = query.filter(SRMInvoice.id == row.source_id)
    else:
        query = query.join(SRMSalesOrder, SRMSalesOrder.id == SRMInvoice.sales_order_id)
        column = {"srm_order":SRMSalesOrder.id, "crm_deal":SRMSalesOrder.crm_deal_id, "crm_quotation":SRMSalesOrder.crm_quote_id}[row.source_type]
        query = query.filter(column == row.source_id, func.coalesce(SRMSalesOrder.organization_id, 1) == tenant(user))
    matches = query.limit(2).all()
    if len(matches) != 1:
        raise HTTPException(409, "Record a receipt in Collections for the exact request amount and currency, using this payment request reference (or its gateway link ID). A unique matching allocated receipt is required.")
    receipt, invoice = matches[0]
    invoice_for(db, invoice.id, user)
    if db.query(PaymentRequest.id).filter(PaymentRequest.receipt_id == receipt.id, PaymentRequest.id != row.id).first():
        raise HTTPException(409, "This receipt is already matched to another payment request.")
    if row.provider_id:
        gateway = bound_gateway(row)
        verified_link(row, gateway.fetch(row.provider_id))
        if row.status not in {"gateway_paid", "cancelled", "expired"}:
            verified_link(row, gateway.cancel(row.provider_id))
            if row.status != "cancelled":
                db.commit()
                raise HTTPException(409, "Cancel the outstanding online link before matching a separately received payment.")
    elif row.status in {"creating_link", "reconciliation_required"}:
        raise HTTPException(409, "Resolve the provider link outcome before receipt reconciliation.")
    row.receipt_id, row.status, row.amount_paid = receipt.id, "receipt_recorded", row.amount
    db.commit(); db.refresh(row)
    return public(row)
