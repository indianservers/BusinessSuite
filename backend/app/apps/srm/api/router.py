from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.apps.fam.models import FAMPostingJob, FAMSRMMapping
from app.apps.business_os.models import BOSLifecycleEvent
from app.apps.business_os.services.module_service import company_id_for as bos_company_id_for, is_module_enabled
from app.apps.srm.access import engagement_query, get_engagement_for_user, get_sales_order_for_user, organization_id_for, sales_order_query
from app.apps.srm.models import (
    SRMAuditLog,
    SRMBillOfMaterial,
    SRMBOMComponent,
    SRMBillingMilestone,
    SRMBillingPlan,
    SRMCollectionReminder,
    SRMContract,
    SRMCustomerAging,
    SRMEngagement,
    SRMEngagementLink,
    SRMGoodsReceipt,
    SRMGoodsReceiptLine,
    SRMInventoryBatch,
    SRMInventoryBalance,
    SRMInventoryMovement,
    SRMInvoice,
    SRMInvoiceDraft,
    SRMInvoiceHistory,
    SRMInvoiceLine,
    SRMProfitabilitySnapshot,
    SRMPOSCashMovement,
    SRMPOSCashierClosing,
    SRMPOSHeldBill,
    SRMPOSReturn,
    SRMPOSReturnLine,
    SRMPOSSession,
    SRMPriceList,
    SRMPriceListLine,
    SRMProductionOrder,
    SRMProduct,
    SRMProductCategory,
    SRMPurchaseOrder,
    SRMPurchaseOrderLine,
    SRMReceipt,
    SRMReceiptAllocation,
    SRMRevenueEvent,
    SRMSalesOrder,
    SRMSalesOrderLine,
    SRMSerialNumber,
    SRMSetting,
    SRMWarehouse,
)
from app.apps.srm.schemas import (
    SRMBillingPlanCreate,
    SRMBillingPlanUpdate,
    SRMBillingMilestoneInput,
    SRMBillOfMaterialCreate,
    SRMContractCreate,
    SRMContractUpdate,
    SRMEngagementCreate,
    SRMEngagementLinkCreate,
    SRMEngagementUpdate,
    SRMGoodsReceiptCreate,
    SRMInventoryBatchCreate,
    SRMInvoiceLineInput,
    SRMManualInvoiceCreate,
    SRMPOSCashMovementCreate,
    SRMPOSCashierClosingCreate,
    SRMPOSHeldBillCreate,
    SRMPOSReturnCreate,
    SRMPOSSessionCreate,
    SRMOpeningStockCreate,
    SRMPriceListCreate,
    SRMPriceLookupRequest,
    SRMProductCategoryCreate,
    SRMProductCreate,
    SRMProductUpdate,
    SRMProductionOrderCreate,
    SRMProductionPostRequest,
    SRMPurchaseOrderCreate,
    SRMInvoicePatch,
    SRMReceiptAllocationRequest,
    SRMReceiptCreate,
    SRMReminderRequest,
    SRMSalesOrderCreate,
    SRMSalesOrderLineInput,
    SRMSalesOrderLineUpdate,
    SRMSalesOrderUpdate,
    SRMSerialNumberCreate,
    SRMSettingUpsert,
    SRMStockAdjustmentCreate,
    SRMStockMovementCreate,
    SRMStockTransferCreate,
    SRMTimeLogInvoiceRequest,
    SRMWarehouseCreate,
    SRMWriteOffRequest,
)
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.approval_os import ApprovalHistory, ApprovalRequest
from app.models.notification import Notification
from app.models.user import User


router = APIRouter(prefix="/srm", tags=["Sales & Inventory Management"])

SALES_ORDER_STATUSES = {"draft", "pending_approval", "approved", "confirmed", "cancelled", "closed"}
CONTRACT_STATUSES = {"draft", "under_review", "active", "expired", "terminated", "renewed"}
ENGAGEMENT_STATUSES = {"created", "project_pending", "project_created", "delivery_in_progress", "billing_in_progress", "completed", "closed"}
BILLING_PLAN_STATUSES = {"draft", "active", "paused", "completed", "cancelled"}
INVOICE_STATUSES = {"draft", "pending_approval", "approved", "sent", "partially_paid", "paid", "overdue", "cancelled"}
RECEIPT_STATUSES = {"draft", "confirmed", "allocated", "partially_allocated", "cancelled"}
COLLECTION_STATUSES = {"not_due", "due", "overdue", "escalated", "collected", "written_off"}

SALES_ORDER_TRANSITIONS = {
    "draft": {"pending_approval", "approved", "cancelled"},
    "pending_approval": {"approved", "cancelled"},
    "approved": {"confirmed", "cancelled"},
    "confirmed": {"closed", "cancelled"},
}
CONTRACT_TRANSITIONS = {
    "draft": {"under_review", "active", "terminated"},
    "under_review": {"active", "terminated"},
    "active": {"expired", "terminated", "renewed"},
    "expired": {"renewed"},
    "renewed": {"active", "terminated"},
}
BILLING_PLAN_TRANSITIONS = {
    "draft": {"active", "cancelled"},
    "active": {"paused", "completed", "cancelled"},
    "paused": {"active", "cancelled"},
}
INVOICE_TRANSITIONS = {
    "draft": {"pending_approval", "approved", "cancelled"},
    "pending_approval": {"approved", "cancelled"},
    "approved": {"sent", "cancelled"},
    "sent": {"partially_paid", "paid", "overdue", "cancelled"},
    "partially_paid": {"paid", "overdue", "cancelled"},
    "overdue": {"partially_paid", "paid", "cancelled"},
}
RECEIPT_TRANSITIONS = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"allocated", "partially_allocated", "cancelled"},
    "partially_allocated": {"allocated", "cancelled"},
}


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _org(user: User) -> int | None:
    return organization_id_for(user)


def _next_number(db: Session, model, prefix: str, column_name: str, org_id: int | None) -> str:
    count = db.query(func.count(model.id)).filter(getattr(model, "organization_id") == org_id).scalar() or 0
    return f"{prefix}-{(count + 1):06d}"


def _audit(db: Session, user: User, entity_type: str, entity_id: int | None, action: str, before=None, after=None) -> None:
    db.add(SRMAuditLog(
        organization_id=_org(user),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=user.id,
        before_json=before,
        after_json=after,
    ))


def _notify(db: Session, user_id: int | None, title: str, message: str, entity_type: str, entity_id: int | None, action_url: str) -> None:
    if not user_id:
        return
    db.add(Notification(
        company_id=None,
        user_id=user_id,
        title=title,
        message=message,
        module="srm",
        event_type="srm.lifecycle",
        related_entity_type=entity_type,
        related_entity_id=entity_id,
        action_url=action_url,
        priority="normal",
    ))


def _serialize(item):
    if item is None:
        return None
    data = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, Decimal):
            value = float(value)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        data[column.name] = value
    return data


def _sum_decimal(db: Session, column, *filters) -> Decimal:
    query = db.query(func.coalesce(func.sum(column), 0))
    for condition in filters:
        query = query.filter(condition)
    return _decimal(query.scalar())


def _count_query(query) -> int:
    return int(query.count() or 0)


def _total_from_lines(lines) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = Decimal("0")
    discount = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    for line in lines:
        line_total = line.line_total if line.line_total is not None else (_decimal(line.quantity) * _decimal(line.unit_price) - _decimal(line.discount_amount) + _decimal(line.tax_amount))
        subtotal += _decimal(line.quantity) * _decimal(line.unit_price)
        discount += _decimal(line.discount_amount)
        tax += _decimal(line.tax_amount)
        total += _decimal(line_total)
    return subtotal, discount, tax, total


def _assert_status(status: str | None, allowed: set[str], label: str) -> None:
    if status and status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {label} status: {status}")


def _transition(current: str | None, target: str, transitions: dict[str, set[str]], label: str) -> None:
    if current == target:
        return
    allowed_targets = transitions.get(current or "", set())
    if target not in allowed_targets:
        raise HTTPException(status_code=400, detail=f"Invalid {label} status transition: {current} -> {target}")


def _recalculate_sales_order(db: Session, order: SRMSalesOrder) -> None:
    db.flush()
    subtotal, discount, tax, total = _total_from_lines(order.lines)
    order.subtotal = subtotal
    order.discount_amount = discount
    order.tax_amount = tax
    order.total_amount = total


def _recalculate_invoice(db: Session, invoice: SRMInvoice) -> None:
    db.flush()
    subtotal = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    for line in invoice.lines:
        line_total = line.line_total if line.line_total is not None else (_decimal(line.quantity) * _decimal(line.unit_price) + _decimal(line.tax_amount))
        subtotal += _decimal(line.quantity) * _decimal(line.unit_price)
        tax += _decimal(line.tax_amount)
        total += _decimal(line_total)
    invoice.subtotal = subtotal
    invoice.tax_amount = tax
    invoice.total_amount = total
    invoice.balance_amount = total - _decimal(invoice.paid_amount)


def _get_invoice(db: Session, invoice_id: int) -> SRMInvoice:
    invoice = db.query(SRMInvoice).filter(SRMInvoice.id == invoice_id, SRMInvoice.deleted_at == None).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def _srm_accounting_status(db: Session | None, organization_id: int | None, source_record_type: str, source_record_id: int) -> dict:
    if db is None:
        return {"status": "unknown", "mappings": []}
    company_id = int(organization_id or 1)
    jobs = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.source_module == "srm", FAMPostingJob.source_record_type == source_record_type, FAMPostingJob.source_record_id == source_record_id).all()
    mappings = db.query(FAMSRMMapping).filter(FAMSRMMapping.company_id == company_id, FAMSRMMapping.srm_record_type == source_record_type, FAMSRMMapping.srm_record_id == source_record_id).all()
    latest = sorted(jobs, key=lambda item: item.id, reverse=True)[0] if jobs else None
    return {
        "status": latest.status if latest else "not_posted",
        "voucher_id": latest.voucher_id if latest else None,
        "job_id": latest.id if latest else None,
        "mappings": [{"fam_record_type": item.fam_record_type, "fam_record_id": item.fam_record_id, "mapping_status": item.mapping_status} for item in mappings],
    }


def _invoice_payload(invoice: SRMInvoice, db: Session | None = None) -> dict:
    payload = _serialize(invoice)
    if invoice.invoice_draft_id:
        draft = getattr(invoice, "_srm_loaded_draft", None)
        payload["source_type"] = getattr(draft, "source_type", None)
        payload["source_id"] = None
    lines = [_serialize(line) for line in invoice.lines]
    if lines:
        payload["source_type"] = payload.get("source_type") or lines[0].get("source_type")
        payload["source_id"] = lines[0].get("source_id")
    return payload | {"lines": lines, "accounting_status": _srm_accounting_status(db, invoice.organization_id, "invoice", invoice.id)}


def _assert_invoice_source_available(db: Session, source_type: str, source_id: int | None) -> None:
    if source_id is None:
        return
    existing = db.query(SRMInvoiceLine).filter(SRMInvoiceLine.source_type == source_type, SRMInvoiceLine.source_id == source_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice already drafted for this source")


def _find_handoff_records(db: Session, deal_id: int) -> dict:
    order = db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal_id, SRMSalesOrder.deleted_at == None).first()
    engagement = db.query(SRMEngagement).filter(SRMEngagement.crm_deal_id == deal_id, SRMEngagement.deleted_at == None).first()
    contract = db.query(SRMContract).filter(SRMContract.sales_order_id == order.id, SRMContract.deleted_at == None).first() if order else None
    billing_plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == engagement.id).first() if engagement else None
    project = None
    if engagement and engagement.pms_project_id:
        try:
            from app.apps.project_management.models import PMSProject

            project = db.query(PMSProject).filter(PMSProject.id == engagement.pms_project_id, PMSProject.deleted_at == None).first()
        except Exception:
            project = None
    return {
        "sales_order": order,
        "engagement": engagement,
        "contract": contract,
        "billing_plan": billing_plan,
        "pms_project": project,
    }


def _handoff_payload(records: dict, idempotent: bool = False) -> dict:
    return {
        "idempotent": idempotent,
        "sales_order": _serialize(records.get("sales_order")),
        "engagement": _serialize(records.get("engagement")),
        "contract": _serialize(records.get("contract")),
        "billing_plan": _serialize(records.get("billing_plan")),
        "pms_project": _serialize(records.get("pms_project")),
    }


def _ensure_billing_plan_from_sales_order(db: Session, user: User, order: SRMSalesOrder, engagement: SRMEngagement, contract: SRMContract | None = None) -> SRMBillingPlan:
    existing = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == engagement.id).first()
    if existing:
        return existing
    plan = SRMBillingPlan(
        organization_id=order.organization_id,
        engagement_id=engagement.id,
        name=f"Billing plan for {order.order_number}",
        billing_type="milestone" if order.lines else "fixed_fee",
        status="draft",
        currency=order.currency,
        total_amount=order.total_amount,
        created_by=user.id,
    )
    db.add(plan)
    db.flush()
    if order.lines:
        for index, line in enumerate(order.lines, start=1):
            db.add(SRMBillingMilestone(
                billing_plan_id=plan.id,
                name=line.description or f"Milestone {index}",
                amount=line.line_total or 0,
                metadata_json={
                    "sales_order_line_id": line.id,
                    "source_quote_line_id": line.source_quote_line_id,
                    "pms_template_key": line.pms_template_key,
                },
            ))
    else:
        db.add(SRMBillingMilestone(billing_plan_id=plan.id, name=order.title, amount=order.total_amount))
    _audit(db, user, "billing_plan", plan.id, "created_from_sales_order", after={"sales_order_id": order.id, "contract_id": contract.id if contract else None})
    return plan


def create_sales_order_from_crm_deal_service(deal_id: int, db: Session, current_user: User) -> dict:
    company_id = bos_company_id_for(current_user)
    if not is_module_enabled(db, "crm", company_id):
        db.add(BOSLifecycleEvent(company_id=company_id, module_key="crm", entity_type="deal", entity_id=str(deal_id), event_name="crm_deal_won_handoff_skipped", status="skipped", message="CRM is not enabled", source_module="crm", target_module="srm", actor_user_id=current_user.id))
        db.commit()
        return {"status": "skipped", "idempotent": True, "message": "CRM is not enabled", "sales_order": None, "engagement": None, "contract": None, "billing_plan": None, "pms_project": None}
    if not is_module_enabled(db, "srm", company_id):
        db.add(BOSLifecycleEvent(company_id=company_id, module_key="crm", entity_type="deal", entity_id=str(deal_id), event_name="crm_deal_won_handoff_skipped", status="skipped", message="SRM not enabled", source_module="crm", target_module="srm", actor_user_id=current_user.id))
        db.commit()
        return {"status": "skipped", "idempotent": True, "message": "SRM not enabled", "sales_order": None, "engagement": None, "contract": None, "billing_plan": None, "pms_project": None}
    existing_records = _find_handoff_records(db, deal_id)
    if existing_records["sales_order"]:
        _audit(db, current_user, "sales_order", existing_records["sales_order"].id, "crm_won_handoff_idempotent", after={"crm_deal_id": deal_id})
        db.commit()
        return _handoff_payload(_find_handoff_records(db, deal_id), idempotent=True)
    try:
        from app.apps.crm.models import CRMDeal, CRMQuotation, CRMQuotationItem
    except Exception as exc:
        raise HTTPException(status_code=400, detail="CRM module is not available") from exc
    deal = db.query(CRMDeal).filter(CRMDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="CRM deal not found")
    quote = db.query(CRMQuotation).filter(CRMQuotation.deal_id == deal.id).order_by(CRMQuotation.id.desc()).first()
    source_total = _decimal(quote.total_amount if quote else deal.amount)
    order = SRMSalesOrder(
        organization_id=getattr(deal, "organization_id", None),
        order_number=_next_number(db, SRMSalesOrder, "SO", "order_number", getattr(deal, "organization_id", None)),
        title=deal.name,
        crm_deal_id=deal.id,
        crm_quote_id=quote.id if quote else None,
        crm_company_id=deal.company_id,
        crm_contact_id=deal.contact_id,
        customer_id=deal.company_id,
        assigned_user_id=deal.owner_user_id or current_user.id,
        created_by=current_user.id,
        currency=quote.currency if quote else deal.currency,
        subtotal=_decimal(quote.subtotal if quote else deal.amount),
        discount_amount=_decimal(quote.discount_amount if quote else deal.discount_amount),
        tax_amount=_decimal(quote.tax_amount if quote else 0),
        total_amount=source_total,
        terms=quote.terms if quote else None,
        metadata_json={"source": "crm_won_handoff", "crm_status": getattr(deal, "status", None)},
    )
    db.add(order)
    db.flush()
    if quote:
        for line in db.query(CRMQuotationItem).filter(CRMQuotationItem.quotation_id == quote.id).all():
            db.add(SRMSalesOrderLine(
                sales_order_id=order.id,
                source_quote_line_id=line.id,
                product_id=line.product_id,
                description=line.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount or 0,
                tax_amount=0,
                line_total=line.total_amount or 0,
                pms_template_key=getattr(line, "sku", None) or None,
            ))
    if not quote:
        db.add(SRMSalesOrderLine(sales_order_id=order.id, description=deal.name, quantity=1, unit_price=source_total, line_total=source_total))
    engagement = SRMEngagement(
        organization_id=order.organization_id,
        engagement_number=_next_number(db, SRMEngagement, "ENG", "engagement_number", order.organization_id),
        sales_order_id=order.id,
        customer_id=order.customer_id,
        crm_deal_id=deal.id,
        crm_quote_id=quote.id if quote else None,
        assigned_user_id=order.assigned_user_id,
        project_manager_user_id=order.assigned_user_id,
        name=order.title,
        status="created",
        budget_amount=order.total_amount,
        currency=order.currency,
        created_by=current_user.id,
    )
    db.add(engagement)
    db.flush()
    contract = SRMContract(
        organization_id=order.organization_id,
        contract_number=_next_number(db, SRMContract, "CTR", "contract_number", order.organization_id),
        sales_order_id=order.id,
        customer_id=order.customer_id,
        title=f"Contract for {order.title}",
        status="draft",
        contract_value=order.total_amount,
        currency=order.currency,
        terms=order.terms,
        created_by=current_user.id,
    )
    db.add(contract)
    db.flush()
    engagement.contract_id = contract.id
    for module, entity_type, entity_id in [
        ("crm", "deal", deal.id),
        ("crm", "quote", quote.id if quote else None),
        ("crm", "company", deal.company_id),
        ("crm", "contact", deal.contact_id),
        ("srm", "sales_order", order.id),
        ("srm", "contract", contract.id),
    ]:
        if entity_id:
            db.add(SRMEngagementLink(engagement_id=engagement.id, linked_module=module, linked_entity_type=entity_type, linked_entity_id=entity_id, label=f"{module}:{entity_type}"))
    billing_plan = _ensure_billing_plan_from_sales_order(db, current_user, order, engagement, contract)
    db.add(SRMRevenueEvent(organization_id=order.organization_id, engagement_id=engagement.id, event_type="crm_won_handoff", amount=order.total_amount, currency=order.currency, recognized_on=date.today(), metadata_json={"crm_deal_id": deal.id}))
    _audit(db, current_user, "sales_order", order.id, "crm_won_handoff", after={"crm_deal_id": deal.id, "engagement_id": engagement.id, "contract_id": contract.id, "billing_plan_id": billing_plan.id})
    _audit(db, current_user, "engagement", engagement.id, "created_from_crm_won", after={"crm_deal_id": deal.id, "sales_order_id": order.id})
    _notify(db, order.assigned_user_id, "SRM sales order created", f"{order.order_number} was created from CRM deal {deal.name}.", "sales_order", order.id, f"/srm/sales-orders/{order.id}")
    _notify(db, engagement.project_manager_user_id, "SRM engagement ready", f"{engagement.engagement_number} is ready for project creation.", "engagement", engagement.id, f"/srm/engagements/{engagement.id}")
    db.commit()
    return _handoff_payload(_find_handoff_records(db, deal_id), idempotent=False)


def _create_profitability_snapshot(db: Session, engagement: SRMEngagement | None, user: User | None = None) -> SRMProfitabilitySnapshot:
    org_id = engagement.organization_id if engagement else (organization_id_for(user) if user else None)
    engagement_id = engagement.id if engagement else None
    customer_id = engagement.customer_id if engagement else None
    order_amount = Decimal("0")
    contract_amount = Decimal("0")
    billing_amount = Decimal("0")
    invoiced_amount = Decimal("0")
    collected_amount = Decimal("0")
    overdue_amount = Decimal("0")
    cost_amount = Decimal("0")

    if engagement:
        if engagement.sales_order_id:
            order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == engagement.sales_order_id).first()
            order_amount = _decimal(order.total_amount if order else 0)
        if engagement.contract_id:
            contract = db.query(SRMContract).filter(SRMContract.id == engagement.contract_id).first()
            contract_amount = _decimal(contract.contract_value if contract else 0)
        billing_amount = _decimal(db.query(func.coalesce(func.sum(SRMBillingPlan.total_amount), 0)).filter(SRMBillingPlan.engagement_id == engagement.id).scalar())
        invoiced_amount = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.total_amount), 0)).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at == None).scalar())
        collected_amount = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.paid_amount), 0)).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at == None).scalar())
        overdue_amount = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.balance_amount), 0)).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at == None, SRMInvoice.balance_amount > 0, SRMInvoice.due_date < date.today()).scalar())
        try:
            from app.apps.project_management.models import PMSTimeLog

            if engagement.pms_project_id:
                minutes = db.query(func.coalesce(func.sum(PMSTimeLog.duration_minutes), 0)).filter(PMSTimeLog.project_id == engagement.pms_project_id).scalar() or 0
                cost_amount = Decimal(str(minutes)) / Decimal("60") * Decimal("500")
        except Exception:
            cost_amount = Decimal("0")

    outstanding = invoiced_amount - collected_amount
    gross_margin = invoiced_amount - cost_amount
    gross_margin_percent = (gross_margin / invoiced_amount * Decimal("100")) if invoiced_amount else Decimal("0")
    cash_margin = collected_amount - cost_amount
    snapshot = SRMProfitabilitySnapshot(
        organization_id=org_id,
        engagement_id=engagement_id,
        customer_id=customer_id,
        quoted_amount=order_amount,
        order_amount=order_amount,
        contract_amount=contract_amount,
        billing_amount=billing_amount,
        invoiced_amount=invoiced_amount,
        collected_amount=collected_amount,
        outstanding_amount=outstanding,
        overdue_amount=overdue_amount,
        cost_amount=cost_amount,
        gross_margin_amount=gross_margin,
        gross_margin_percent=gross_margin_percent,
        cash_margin_amount=cash_margin,
        status="healthy" if gross_margin >= 0 else "at_risk",
    )
    db.add(snapshot)
    db.flush()
    _audit(db, user, "profitability", engagement_id, "snapshot_created", after={"engagement_id": engagement_id, "gross_margin": float(gross_margin)}) if user else None
    return snapshot


def _profitability_payload(snapshot: SRMProfitabilitySnapshot) -> dict:
    data = _serialize(snapshot)
    invoiced = _decimal(snapshot.invoiced_amount)
    collected = _decimal(snapshot.collected_amount)
    outstanding = _decimal(snapshot.outstanding_amount)
    cost = _decimal(snapshot.cost_amount)
    cash_margin = collected - cost
    data.update({
        "quoted_value": data.get("quoted_amount"),
        "sales_order_value": data.get("order_amount"),
        "contract_value": data.get("contract_amount"),
        "billing_plan_value": data.get("billing_amount"),
        "delivery_budget": data.get("order_amount"),
        "approved_timesheet_cost": data.get("cost_amount"),
        "employee_cost": data.get("cost_amount"),
        "gross_margin": data.get("gross_margin_amount"),
        "cash_margin": float(cash_margin),
        "cash_margin_percent": float((cash_margin / collected * Decimal("100")) if collected else Decimal("0")),
        "collection_status": "collected" if invoiced and outstanding <= 0 else ("overdue" if _decimal(snapshot.overdue_amount) > 0 else ("outstanding" if outstanding > 0 else "not_billed")),
    })
    return data


@router.get("/module-info")
def module_info(current_user: User = Depends(RequirePermission("srm_view", "srm_admin"))):
    return {
        "key": "srm",
        "label": "Sales & Inventory Management",
        "api_prefix": "/api/v1/srm",
        "routes": [
            "/srm/dashboard",
            "/srm/sales-orders",
            "/srm/contracts",
            "/srm/engagements",
            "/srm/billing-plans",
            "/srm/invoice-drafts",
            "/srm/invoices",
            "/srm/collections",
            "/srm/revenue-recognition",
            "/srm/profitability",
            "/srm/customer-360",
            "/srm/reports",
            "/srm/settings",
        ],
    }


@router.get("/sales-orders")
def list_sales_orders(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    return [_serialize(item) | {"lines": [_serialize(line) for line in item.lines]} for item in sales_order_query(db, current_user).order_by(SRMSalesOrder.id.desc()).limit(200).all()]


def _get_pos_session(db: Session, session_id: int, user: User) -> SRMPOSSession:
    item = db.query(SRMPOSSession).filter(
        SRMPOSSession.id == session_id,
        SRMPOSSession.organization_id == _org(user),
        SRMPOSSession.deleted_at == None,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="POS session not found")
    return item


def _pos_session_summary(db: Session, session: SRMPOSSession) -> dict:
    orders = db.query(SRMSalesOrder).filter(
        SRMSalesOrder.organization_id == session.organization_id,
        SRMSalesOrder.deleted_at == None,
    ).all()
    pos_orders = []
    for order in orders:
        metadata = order.metadata_json or {}
        if metadata.get("source") == "pos" and int(metadata.get("pos_session_id") or 0) == session.id:
            pos_orders.append(order)
    cash_sales = sum(_decimal(order.total_amount) for order in pos_orders if (order.metadata_json or {}).get("payment_mode") in {"Cash", "Split"})
    cash_in = _sum_decimal(db, SRMPOSCashMovement.amount, SRMPOSCashMovement.session_id == session.id, SRMPOSCashMovement.movement_type == "cash_in")
    cash_out = _sum_decimal(db, SRMPOSCashMovement.amount, SRMPOSCashMovement.session_id == session.id, SRMPOSCashMovement.movement_type == "cash_out")
    expected_cash = _decimal(session.opening_cash) + cash_sales + cash_in - cash_out
    return {
        "session": _serialize(session),
        "sales_count": len(pos_orders),
        "cash_sales": float(cash_sales),
        "cash_in": float(cash_in),
        "cash_out": float(cash_out),
        "expected_cash": float(expected_cash),
        "movements": [_serialize(item) for item in session.cash_movements],
        "closing": _serialize(session.closings[-1]) if session.closings else None,
    }


def _held_bill_payload(item: SRMPOSHeldBill) -> dict:
    data = _serialize(item)
    data["holdNo"] = item.hold_number
    data["cart"] = item.cart_json or []
    return data


def _product_payload(product: SRMProduct) -> dict:
    data = _serialize(product)
    data["category"] = _serialize(product.category)
    data["default_warehouse"] = _serialize(product.default_warehouse)
    return data


def _product_or_404(db: Session, org_id: int | None, product_id: int) -> SRMProduct:
    product = db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.id == product_id, SRMProduct.deleted_at.is_(None)).first()
    if not product:
        raise HTTPException(status_code=404, detail="SRM product not found")
    return product


def _warehouse_or_404(db: Session, org_id: int | None, warehouse_id: int) -> SRMWarehouse:
    warehouse = db.query(SRMWarehouse).filter(SRMWarehouse.organization_id == org_id, SRMWarehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="SRM warehouse not found")
    return warehouse


def _refresh_product_quantity(db: Session, product: SRMProduct) -> None:
    total = _sum_decimal(
        db,
        SRMInventoryBalance.quantity,
        SRMInventoryBalance.organization_id == product.organization_id,
        SRMInventoryBalance.product_id == product.id,
    )
    product.current_quantity = total


def _balance_for_update(db: Session, org_id: int | None, product: SRMProduct, warehouse_id: int, rate: Decimal = Decimal("0")) -> SRMInventoryBalance:
    balance = db.query(SRMInventoryBalance).filter(
        SRMInventoryBalance.organization_id == org_id,
        SRMInventoryBalance.product_id == product.id,
        SRMInventoryBalance.warehouse_id == warehouse_id,
    ).first()
    if not balance:
        balance = SRMInventoryBalance(organization_id=org_id, product_id=product.id, warehouse_id=warehouse_id, quantity=0, average_cost=rate or product.average_cost)
        db.add(balance)
        db.flush()
    return balance


def _post_stock_movement(
    db: Session,
    org_id: int | None,
    product: SRMProduct,
    warehouse_id: int,
    movement_type: str,
    quantity_in: Decimal,
    quantity_out: Decimal,
    rate: Decimal,
    movement_date: date,
    reference_number: str | None,
    notes: str | None,
    user: User,
) -> SRMInventoryMovement:
    if _decimal(quantity_in) < 0 or _decimal(quantity_out) < 0:
        raise HTTPException(status_code=400, detail="Stock quantities cannot be negative")
    if _decimal(quantity_in) <= 0 and _decimal(quantity_out) <= 0:
        raise HTTPException(status_code=400, detail="Stock movement quantity is required")
    balance = _balance_for_update(db, org_id, product, warehouse_id, rate)
    if _decimal(quantity_out) > 0 and _decimal(balance.quantity) < _decimal(quantity_out):
        raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.item_name}")
    balance.quantity = _decimal(balance.quantity) + _decimal(quantity_in) - _decimal(quantity_out)
    if _decimal(quantity_in) > 0 and _decimal(rate) > 0:
        balance.average_cost = rate
        product.average_cost = rate
    movement = SRMInventoryMovement(
        organization_id=org_id,
        movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", org_id),
        movement_type=movement_type,
        movement_date=movement_date,
        product_id=product.id,
        warehouse_id=warehouse_id,
        quantity_in=quantity_in,
        quantity_out=quantity_out,
        rate=rate,
        value=(_decimal(quantity_in) or _decimal(quantity_out)) * _decimal(rate),
        reference_number=reference_number,
        notes=notes,
        created_by=user.id,
    )
    db.add(movement)
    db.flush()
    _refresh_product_quantity(db, product)
    return movement


def _issue_inventory_for_sales_order(db: Session, order: SRMSalesOrder, user: User) -> list[SRMInventoryMovement]:
    metadata = order.metadata_json or {}
    if metadata.get("inventory_issued_at"):
        return []
    is_pos = metadata.get("source") == "pos"
    if not is_pos and order.status != "confirmed":
        return []
    movements: list[SRMInventoryMovement] = []
    for line in order.lines:
        if line.service_type != "product" or not line.product_id:
            continue
        product = db.query(SRMProduct).filter(
            SRMProduct.organization_id == order.organization_id,
            SRMProduct.id == line.product_id,
            SRMProduct.deleted_at.is_(None),
        ).first()
        if not product or not product.track_inventory:
            continue
        warehouse_id = product.default_warehouse_id
        line_metadata = line.metadata_json or {}
        if line_metadata.get("warehouse_id"):
            warehouse_id = int(line_metadata["warehouse_id"])
        if not warehouse_id:
            raise HTTPException(status_code=400, detail=f"Default warehouse is required for {product.item_name}")
        balance = db.query(SRMInventoryBalance).filter(
            SRMInventoryBalance.organization_id == order.organization_id,
            SRMInventoryBalance.product_id == product.id,
            SRMInventoryBalance.warehouse_id == warehouse_id,
        ).first()
        requested = _decimal(line.quantity)
        available = _decimal(balance.quantity if balance else 0)
        if requested > available:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.item_name}: available {available}, requested {requested}")
        if not balance:
            raise HTTPException(status_code=409, detail=f"No stock balance found for {product.item_name}")
        balance.quantity = available - requested
        movement = SRMInventoryMovement(
            organization_id=order.organization_id,
            movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", order.organization_id),
            movement_type="pos_sale" if is_pos else "sales_order_issue",
            movement_date=date.today(),
            product_id=product.id,
            warehouse_id=warehouse_id,
            quantity_out=requested,
            rate=line.unit_price or product.sales_rate or 0,
            value=requested * _decimal(line.unit_price or product.sales_rate or 0),
            reference_number=order.order_number,
            notes=f"{'POS sale' if is_pos else 'Sales order issue'} {order.order_number}",
            created_by=user.id,
        )
        db.add(movement)
        db.flush()
        _refresh_product_quantity(db, product)
        movements.append(movement)
    if movements:
        order.metadata_json = {**metadata, "inventory_issued_at": datetime.now(timezone.utc).isoformat(), "inventory_issue_movement_ids": [movement.id for movement in movements]}
    return movements


def _validate_pos_stock_available(db: Session, data: SRMSalesOrderCreate, org_id: int | None) -> None:
    if (data.metadata_json or {}).get("source") != "pos":
        return
    for line in data.lines:
        if line.service_type != "product" or not line.product_id:
            continue
        product = db.query(SRMProduct).filter(
            SRMProduct.organization_id == org_id,
            SRMProduct.id == line.product_id,
            SRMProduct.deleted_at.is_(None),
        ).first()
        if not product or not product.track_inventory:
            continue
        warehouse_id = product.default_warehouse_id
        line_metadata = line.metadata_json or {}
        if line_metadata.get("warehouse_id"):
            warehouse_id = int(line_metadata["warehouse_id"])
        if not warehouse_id:
            raise HTTPException(status_code=400, detail=f"Default warehouse is required for {product.item_name}")
        balance = db.query(SRMInventoryBalance).filter(
            SRMInventoryBalance.organization_id == org_id,
            SRMInventoryBalance.product_id == product.id,
            SRMInventoryBalance.warehouse_id == warehouse_id,
        ).first()
        requested = _decimal(line.quantity)
        available = _decimal(balance.quantity if balance else 0)
        if requested > available:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.item_name}: available {available}, requested {requested}")


def _return_payload(item: SRMPOSReturn) -> dict:
    return _serialize(item) | {"lines": [_serialize(line) for line in item.lines]}


def _returned_quantity_for_order_line(db: Session, order_line_id: int) -> Decimal:
    return _sum_decimal(
        db,
        SRMPOSReturnLine.quantity,
        SRMPOSReturnLine.sales_order_line_id == order_line_id,
        SRMPOSReturnLine.restock.is_(True),
    )


def _resolve_return_order(db: Session, data: SRMPOSReturnCreate, org_id: int | None) -> SRMSalesOrder:
    query = db.query(SRMSalesOrder).filter(SRMSalesOrder.organization_id == org_id, SRMSalesOrder.deleted_at.is_(None))
    if data.sales_order_id:
        order = query.filter(SRMSalesOrder.id == data.sales_order_id).first()
    elif data.order_number:
        order = query.filter(SRMSalesOrder.order_number == data.order_number).first()
    else:
        order = None
    if not order:
        raise HTTPException(status_code=404, detail="Original POS sale not found")
    if (order.metadata_json or {}).get("source") != "pos":
        raise HTTPException(status_code=400, detail="Only POS sales can be returned through POS returns")
    return order


def _restock_return_line(db: Session, return_doc: SRMPOSReturn, line: SRMPOSReturnLine, order: SRMSalesOrder, user: User) -> SRMInventoryMovement | None:
    if not line.restock or not line.product_id:
        return None
    product = db.query(SRMProduct).filter(
        SRMProduct.organization_id == order.organization_id,
        SRMProduct.id == line.product_id,
        SRMProduct.deleted_at.is_(None),
    ).first()
    if not product or not product.track_inventory:
        return None
    warehouse_id = line.warehouse_id or product.default_warehouse_id
    if not warehouse_id:
        raise HTTPException(status_code=400, detail=f"Return warehouse is required for {product.item_name}")
    balance = db.query(SRMInventoryBalance).filter(
        SRMInventoryBalance.organization_id == order.organization_id,
        SRMInventoryBalance.product_id == product.id,
        SRMInventoryBalance.warehouse_id == warehouse_id,
    ).first()
    if not balance:
        balance = SRMInventoryBalance(organization_id=order.organization_id, product_id=product.id, warehouse_id=warehouse_id, quantity=0, average_cost=product.average_cost)
        db.add(balance)
        db.flush()
    quantity = _decimal(line.quantity)
    balance.quantity = _decimal(balance.quantity) + quantity
    movement = SRMInventoryMovement(
        organization_id=order.organization_id,
        movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", order.organization_id),
        movement_type="pos_return",
        movement_date=date.today(),
        product_id=product.id,
        warehouse_id=warehouse_id,
        quantity_in=quantity,
        rate=line.unit_price or product.sales_rate or 0,
        value=quantity * _decimal(line.unit_price or product.sales_rate or 0),
        reference_number=return_doc.return_number,
        notes=f"POS return {return_doc.return_number} for {order.order_number}",
        created_by=user.id,
    )
    db.add(movement)
    db.flush()
    _refresh_product_quantity(db, product)
    return movement


def _purchase_order_payload(item: SRMPurchaseOrder) -> dict:
    return _serialize(item) | {"lines": [_serialize(line) for line in item.lines]}


def _goods_receipt_payload(item: SRMGoodsReceipt) -> dict:
    return _serialize(item) | {"lines": [_serialize(line) for line in item.lines]}


def _price_list_line_payload(line: SRMPriceListLine) -> dict:
    data = _serialize(line)
    data["product"] = _product_payload(line.product) if line.product else None
    return data


def _price_list_payload(item: SRMPriceList) -> dict:
    data = _serialize(item)
    data["lines"] = [_price_list_line_payload(line) for line in item.lines]
    return data


def _batch_payload(item: SRMInventoryBatch) -> dict:
    data = _serialize(item)
    data["product"] = _product_payload(item.product) if item.product else None
    data["warehouse"] = _serialize(item.warehouse)
    data["serial_count"] = len(item.serials or [])
    return data


def _serial_payload(item: SRMSerialNumber) -> dict:
    data = _serialize(item)
    data["product"] = _product_payload(item.product) if item.product else None
    data["warehouse"] = _serialize(item.warehouse)
    data["batch"] = _serialize(item.batch)
    return data


def _bom_component_payload(item: SRMBOMComponent) -> dict:
    data = _serialize(item)
    data["component_product"] = _product_payload(item.component_product) if item.component_product else None
    data["warehouse"] = _serialize(item.warehouse)
    return data


def _bom_payload(item: SRMBillOfMaterial) -> dict:
    data = _serialize(item)
    data["finished_product"] = _product_payload(item.finished_product) if item.finished_product else None
    data["components"] = [_bom_component_payload(row) for row in item.components]
    return data


def _production_order_payload(item: SRMProductionOrder) -> dict:
    data = _serialize(item)
    data["bom"] = _bom_payload(item.bom) if item.bom else None
    data["finished_product"] = _product_payload(item.finished_product) if item.finished_product else None
    data["warehouse"] = _serialize(item.warehouse)
    return data


def _matching_price_line(db: Session, org_id: int | None, product_id: int, channel: str | None, customer_type: str | None, price_date: date, quantity: Decimal) -> SRMPriceListLine | None:
    query = (
        db.query(SRMPriceListLine)
        .join(SRMPriceList, SRMPriceList.id == SRMPriceListLine.price_list_id)
        .filter(
            SRMPriceList.organization_id == org_id,
            SRMPriceList.deleted_at.is_(None),
            SRMPriceList.active.is_(True),
            SRMPriceListLine.active.is_(True),
            SRMPriceListLine.product_id == product_id,
            SRMPriceListLine.min_quantity <= quantity,
            (SRMPriceList.effective_from.is_(None)) | (SRMPriceList.effective_from <= price_date),
            (SRMPriceList.effective_to.is_(None)) | (SRMPriceList.effective_to >= price_date),
        )
    )
    if channel:
        query = query.filter((SRMPriceList.channel == channel) | (SRMPriceList.channel == "all"))
    if customer_type:
        query = query.filter((SRMPriceList.customer_type == customer_type) | (SRMPriceList.customer_type == "all"))
    return query.order_by(SRMPriceList.priority.asc(), SRMPriceListLine.min_quantity.desc(), SRMPriceList.id.desc()).first()


def _received_quantity_for_po_line(db: Session, po_line_id: int) -> Decimal:
    return _sum_decimal(
        db,
        SRMGoodsReceiptLine.accepted_quantity,
        SRMGoodsReceiptLine.purchase_order_line_id == po_line_id,
    )


def _update_purchase_order_receipt_status(db: Session, po: SRMPurchaseOrder) -> None:
    any_received = False
    fully_received = bool(po.lines)
    for line in po.lines:
        received = _received_quantity_for_po_line(db, line.id)
        line.received_quantity = received
        if received > 0:
            any_received = True
        if received < _decimal(line.quantity):
            fully_received = False
    po.status = "received" if fully_received else ("partially_received" if any_received else po.status)


def _stock_in_from_grn_line(db: Session, receipt: SRMGoodsReceipt, line: SRMGoodsReceiptLine, user: User) -> SRMInventoryMovement | None:
    if not line.product_id or _decimal(line.accepted_quantity) <= 0:
        return None
    product = db.query(SRMProduct).filter(
        SRMProduct.organization_id == receipt.organization_id,
        SRMProduct.id == line.product_id,
        SRMProduct.deleted_at.is_(None),
    ).first()
    if not product or not product.track_inventory:
        return None
    warehouse_id = line.warehouse_id or product.default_warehouse_id
    if not warehouse_id:
        raise HTTPException(status_code=400, detail=f"Receipt warehouse is required for {product.item_name}")
    balance = db.query(SRMInventoryBalance).filter(
        SRMInventoryBalance.organization_id == receipt.organization_id,
        SRMInventoryBalance.product_id == product.id,
        SRMInventoryBalance.warehouse_id == warehouse_id,
    ).first()
    if not balance:
        balance = SRMInventoryBalance(organization_id=receipt.organization_id, product_id=product.id, warehouse_id=warehouse_id, quantity=0, average_cost=line.unit_price or product.average_cost)
        db.add(balance)
        db.flush()
    quantity = _decimal(line.accepted_quantity)
    balance.quantity = _decimal(balance.quantity) + quantity
    balance.average_cost = line.unit_price or balance.average_cost
    movement = SRMInventoryMovement(
        organization_id=receipt.organization_id,
        movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", receipt.organization_id),
        movement_type="grn_receipt",
        movement_date=receipt.receipt_date,
        product_id=product.id,
        warehouse_id=warehouse_id,
        quantity_in=quantity,
        rate=line.unit_price or product.purchase_rate or 0,
        value=quantity * _decimal(line.unit_price or product.purchase_rate or 0),
        reference_number=receipt.grn_number,
        notes=f"GRN {receipt.grn_number}",
        created_by=user.id,
    )
    db.add(movement)
    db.flush()
    _refresh_product_quantity(db, product)
    if line.unit_price:
        product.average_cost = line.unit_price
    return movement


def _post_production_inventory(db: Session, order: SRMProductionOrder, completed_quantity: Decimal, warehouse_id: int | None, user: User) -> list[SRMInventoryMovement]:
    bom = order.bom
    if not bom or not bom.components:
        raise HTTPException(status_code=400, detail="BOM components are required before posting production")
    if _decimal(completed_quantity) <= 0:
        raise HTTPException(status_code=400, detail="Completed quantity must be greater than zero")
    output_ratio = _decimal(completed_quantity) / _decimal(bom.output_quantity or 1)
    movements: list[SRMInventoryMovement] = []
    component_cost = Decimal("0")
    for component in bom.components:
        product = component.component_product
        if not product:
            raise HTTPException(status_code=400, detail="BOM component product is missing")
        component_warehouse_id = component.warehouse_id or product.default_warehouse_id
        if not component_warehouse_id:
            raise HTTPException(status_code=400, detail=f"Warehouse is required for component {product.item_name}")
        required_quantity = _decimal(component.quantity) * output_ratio
        balance = db.query(SRMInventoryBalance).filter(
            SRMInventoryBalance.organization_id == order.organization_id,
            SRMInventoryBalance.product_id == product.id,
            SRMInventoryBalance.warehouse_id == component_warehouse_id,
        ).first()
        available = _decimal(balance.quantity if balance else 0)
        if available < required_quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient component stock for {product.item_name}")
        rate = _decimal(component.unit_cost or product.average_cost or product.purchase_rate or 0)
        balance.quantity = available - required_quantity
        movement = SRMInventoryMovement(
            organization_id=order.organization_id,
            movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", order.organization_id),
            movement_type="production_consumption",
            movement_date=date.today(),
            product_id=product.id,
            warehouse_id=component_warehouse_id,
            quantity_out=required_quantity,
            rate=rate,
            value=required_quantity * rate,
            reference_number=order.production_number,
            notes=f"Production consumption for {order.production_number}",
            created_by=user.id,
        )
        db.add(movement)
        db.flush()
        movements.append(movement)
        component_cost += required_quantity * rate
        _refresh_product_quantity(db, product)
    finished = order.finished_product
    finished_warehouse_id = warehouse_id or order.warehouse_id or (finished.default_warehouse_id if finished else None)
    if not finished or not finished_warehouse_id:
        raise HTTPException(status_code=400, detail="Finished product warehouse is required")
    finished_balance = db.query(SRMInventoryBalance).filter(
        SRMInventoryBalance.organization_id == order.organization_id,
        SRMInventoryBalance.product_id == finished.id,
        SRMInventoryBalance.warehouse_id == finished_warehouse_id,
    ).first()
    unit_cost = component_cost / _decimal(completed_quantity)
    if not finished_balance:
        finished_balance = SRMInventoryBalance(organization_id=order.organization_id, product_id=finished.id, warehouse_id=finished_warehouse_id, quantity=0, average_cost=unit_cost)
        db.add(finished_balance)
        db.flush()
    finished_balance.quantity = _decimal(finished_balance.quantity) + _decimal(completed_quantity)
    finished_balance.average_cost = unit_cost
    finished_movement = SRMInventoryMovement(
        organization_id=order.organization_id,
        movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", order.organization_id),
        movement_type="production_output",
        movement_date=date.today(),
        product_id=finished.id,
        warehouse_id=finished_warehouse_id,
        quantity_in=completed_quantity,
        rate=unit_cost,
        value=component_cost,
        reference_number=order.production_number,
        notes=f"Production output for {order.production_number}",
        created_by=user.id,
    )
    db.add(finished_movement)
    db.flush()
    movements.append(finished_movement)
    _refresh_product_quantity(db, finished)
    finished.average_cost = unit_cost
    order.completed_quantity = _decimal(order.completed_quantity) + _decimal(completed_quantity)
    order.total_component_cost = _decimal(order.total_component_cost) + component_cost
    order.status = "completed" if _decimal(order.completed_quantity) >= _decimal(order.planned_quantity) else "partially_completed"
    order.completed_at = datetime.now(timezone.utc)
    db.flush()
    return movements


@router.get("/inventory/categories")
def list_srm_product_categories(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    rows = db.query(SRMProductCategory).filter(SRMProductCategory.organization_id == org_id).order_by(SRMProductCategory.category_name).all()
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.post("/inventory/categories", status_code=201)
def create_srm_product_category(data: SRMProductCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if db.query(SRMProductCategory).filter(SRMProductCategory.organization_id == org_id, SRMProductCategory.category_code == data.category_code).first():
        raise HTTPException(status_code=409, detail="SRM category code already exists")
    row = SRMProductCategory(organization_id=org_id, created_by=current_user.id, **data.model_dump())
    db.add(row)
    db.flush()
    _audit(db, current_user, "product_category", row.id, "CREATE", None, _serialize(row))
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/inventory/warehouses")
def list_srm_warehouses(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    rows = db.query(SRMWarehouse).filter(SRMWarehouse.organization_id == org_id).order_by(SRMWarehouse.warehouse_name).all()
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.post("/inventory/warehouses", status_code=201)
def create_srm_warehouse(data: SRMWarehouseCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if db.query(SRMWarehouse).filter(SRMWarehouse.organization_id == org_id, SRMWarehouse.warehouse_code == data.warehouse_code).first():
        raise HTTPException(status_code=409, detail="SRM warehouse code already exists")
    row = SRMWarehouse(organization_id=org_id, created_by=current_user.id, **data.model_dump())
    db.add(row)
    db.flush()
    _audit(db, current_user, "warehouse", row.id, "CREATE", None, _serialize(row))
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/inventory/items")
def list_srm_products(search: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    query = db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.deleted_at.is_(None))
    if search:
        normalized = f"%{search.lower()}%"
        query = query.filter(
            func.lower(SRMProduct.sku).like(normalized)
            | func.lower(SRMProduct.item_name).like(normalized)
            | func.lower(SRMProduct.category_name).like(normalized)
            | func.lower(SRMProduct.barcode).like(normalized)
        )
    rows = query.order_by(SRMProduct.item_name).all()
    return {"items": [_product_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/items", status_code=201)
def create_srm_product(data: SRMProductCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.sku == data.sku, SRMProduct.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="SRM product SKU already exists")
    if data.barcode and db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.barcode == data.barcode, SRMProduct.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="SRM product barcode already exists")
    row = SRMProduct(organization_id=org_id, created_by=current_user.id, **data.model_dump())
    if not row.mrp:
        row.mrp = row.sales_rate
    db.add(row)
    db.flush()
    _audit(db, current_user, "product", row.id, "CREATE", None, _product_payload(row))
    db.commit()
    db.refresh(row)
    return _product_payload(row)


@router.get("/inventory/items/{product_id}")
def get_srm_product(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    product = _product_or_404(db, org_id, product_id)
    movements = db.query(SRMInventoryMovement).filter(SRMInventoryMovement.organization_id == org_id, SRMInventoryMovement.product_id == product.id).order_by(SRMInventoryMovement.id.desc()).limit(25).all()
    balances = db.query(SRMInventoryBalance).filter(SRMInventoryBalance.organization_id == org_id, SRMInventoryBalance.product_id == product.id).all()
    return {**_product_payload(product), "ledger": [_serialize(row) for row in movements], "balances": [_serialize(row) for row in balances]}


@router.put("/inventory/items/{product_id}")
def update_srm_product(product_id: int, data: SRMProductUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    product = _product_or_404(db, org_id, product_id)
    before = _product_payload(product)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    if not product.mrp:
        product.mrp = product.sales_rate
    _audit(db, current_user, "product", product.id, "UPDATE", before, _product_payload(product))
    db.commit()
    db.refresh(product)
    return _product_payload(product)


@router.post("/inventory/opening-stock", status_code=201)
def create_srm_opening_stock(data: SRMOpeningStockCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    product = _product_or_404(db, org_id, data.product_id)
    warehouse = _warehouse_or_404(db, org_id, data.warehouse_id)
    movement = SRMInventoryMovement(
        organization_id=org_id,
        movement_number=_next_number(db, SRMInventoryMovement, "INV", "movement_number", org_id),
        movement_type="opening_stock",
        movement_date=data.movement_date or date.today(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity_in=data.quantity,
        rate=data.rate,
        value=_decimal(data.quantity) * _decimal(data.rate),
        reference_number=data.reference_number,
        notes=data.notes,
        created_by=current_user.id,
    )
    balance = db.query(SRMInventoryBalance).filter(SRMInventoryBalance.organization_id == org_id, SRMInventoryBalance.product_id == product.id, SRMInventoryBalance.warehouse_id == warehouse.id).first()
    if not balance:
        balance = SRMInventoryBalance(organization_id=org_id, product_id=product.id, warehouse_id=warehouse.id, quantity=0, average_cost=data.rate)
        db.add(balance)
        db.flush()
    balance.quantity = _decimal(balance.quantity) + _decimal(data.quantity)
    balance.average_cost = data.rate
    db.add(movement)
    db.flush()
    _refresh_product_quantity(db, product)
    if data.rate:
        product.average_cost = data.rate
    _audit(db, current_user, "inventory_movement", movement.id, "OPENING_STOCK", None, _serialize(movement))
    db.commit()
    db.refresh(movement)
    db.refresh(product)
    return {"movement": _serialize(movement), "product": _product_payload(product), "balance": _serialize(balance)}


@router.post("/inventory/stock-movements", status_code=201)
def create_srm_stock_movement(data: SRMStockMovementCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    movement_type = data.movement_type or "stock_in"
    if movement_type not in {"stock_in", "stock_out", "purchase_receipt", "delivery_note"}:
        raise HTTPException(status_code=400, detail="Unsupported stock movement type")
    product = _product_or_404(db, org_id, data.product_id)
    warehouse = _warehouse_or_404(db, org_id, data.warehouse_id)
    quantity_in = data.quantity if movement_type in {"stock_in", "purchase_receipt"} else Decimal("0")
    quantity_out = data.quantity if movement_type in {"stock_out", "delivery_note"} else Decimal("0")
    movement = _post_stock_movement(
        db,
        org_id,
        product,
        warehouse.id,
        movement_type,
        quantity_in,
        quantity_out,
        data.rate,
        data.movement_date or date.today(),
        data.reference_number,
        data.notes,
        current_user,
    )
    _audit(db, current_user, "inventory_movement", movement.id, movement_type.upper(), None, _serialize(movement))
    db.commit()
    db.refresh(product)
    return {"movement": _serialize(movement), "product": _product_payload(product)}


@router.post("/inventory/stock-transfers", status_code=201)
def create_srm_stock_transfer(data: SRMStockTransferCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(status_code=400, detail="Transfer warehouses must be different")
    product = _product_or_404(db, org_id, data.product_id)
    from_warehouse = _warehouse_or_404(db, org_id, data.from_warehouse_id)
    to_warehouse = _warehouse_or_404(db, org_id, data.to_warehouse_id)
    movement_date = data.movement_date or date.today()
    ref = data.reference_number or _next_number(db, SRMInventoryMovement, "TRF", "movement_number", org_id)
    out_movement = _post_stock_movement(db, org_id, product, from_warehouse.id, "stock_transfer_out", Decimal("0"), data.quantity, data.rate, movement_date, ref, data.notes, current_user)
    in_movement = _post_stock_movement(db, org_id, product, to_warehouse.id, "stock_transfer_in", data.quantity, Decimal("0"), data.rate, movement_date, ref, data.notes, current_user)
    _audit(db, current_user, "inventory_transfer", out_movement.id, "TRANSFER_OUT", None, _serialize(out_movement))
    _audit(db, current_user, "inventory_transfer", in_movement.id, "TRANSFER_IN", None, _serialize(in_movement))
    db.commit()
    db.refresh(product)
    return {"reference_number": ref, "movements": [_serialize(out_movement), _serialize(in_movement)], "product": _product_payload(product)}


@router.post("/inventory/stock-adjustments", status_code=201)
def create_srm_stock_adjustment(data: SRMStockAdjustmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if _decimal(data.quantity_in) > 0 and _decimal(data.quantity_out) > 0:
        raise HTTPException(status_code=400, detail="Use either quantity_in or quantity_out for one adjustment")
    product = _product_or_404(db, org_id, data.product_id)
    warehouse = _warehouse_or_404(db, org_id, data.warehouse_id)
    movement_type = "stock_adjustment_in" if _decimal(data.quantity_in) > 0 else "stock_adjustment_out"
    movement = _post_stock_movement(
        db,
        org_id,
        product,
        warehouse.id,
        movement_type,
        data.quantity_in,
        data.quantity_out,
        data.rate,
        data.movement_date or date.today(),
        data.reference_number,
        data.notes or data.reason,
        current_user,
    )
    _audit(db, current_user, "inventory_adjustment", movement.id, movement_type.upper(), None, _serialize(movement))
    db.commit()
    db.refresh(product)
    return {"movement": _serialize(movement), "product": _product_payload(product)}


@router.get("/inventory/batches")
def list_inventory_batches(product_id: int | None = None, status: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    query = db.query(SRMInventoryBatch).filter(SRMInventoryBatch.organization_id == org_id)
    if product_id:
        query = query.filter(SRMInventoryBatch.product_id == product_id)
    if status:
        query = query.filter(SRMInventoryBatch.status == status)
    rows = query.order_by(SRMInventoryBatch.expiry_date.asc().nullslast(), SRMInventoryBatch.id.desc()).limit(200).all()
    return {"items": [_batch_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/batches", status_code=201)
def create_inventory_batch(data: SRMInventoryBatchCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    product = _product_or_404(db, org_id, data.product_id)
    warehouse_id = data.warehouse_id or product.default_warehouse_id
    warehouse = _warehouse_or_404(db, org_id, warehouse_id) if warehouse_id else None
    if data.expiry_date and data.manufacture_date and data.expiry_date < data.manufacture_date:
        raise HTTPException(status_code=400, detail="Expiry date cannot be before manufacture date")
    if _decimal(data.quantity) < 0:
        raise HTTPException(status_code=400, detail="Batch quantity cannot be negative")
    if db.query(SRMInventoryBatch).filter(SRMInventoryBatch.organization_id == org_id, SRMInventoryBatch.product_id == product.id, SRMInventoryBatch.batch_number == data.batch_number).first():
        raise HTTPException(status_code=409, detail="Batch number already exists for this product")
    available = data.available_quantity if data.available_quantity is not None else data.quantity
    if _decimal(available) < 0 or _decimal(available) > _decimal(data.quantity):
        raise HTTPException(status_code=400, detail="Available quantity must be between zero and batch quantity")
    batch = SRMInventoryBatch(
        organization_id=org_id,
        product_id=product.id,
        warehouse_id=warehouse.id if warehouse else None,
        batch_number=data.batch_number,
        manufacture_date=data.manufacture_date,
        expiry_date=data.expiry_date,
        received_date=data.received_date or date.today(),
        quantity=data.quantity,
        available_quantity=available,
        unit_cost=data.unit_cost,
        status=data.status,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    product.batch_tracking = True
    if data.expiry_date:
        product.expiry_tracking = True
    db.add(batch)
    db.flush()
    _audit(db, current_user, "inventory_batch", batch.id, "created", None, _batch_payload(batch))
    db.commit()
    db.refresh(batch)
    return _batch_payload(batch)


@router.get("/inventory/batches/{batch_id}")
def get_inventory_batch(batch_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    batch = db.query(SRMInventoryBatch).filter(SRMInventoryBatch.organization_id == _org(current_user), SRMInventoryBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return _batch_payload(batch) | {"serials": [_serial_payload(row) for row in batch.serials]}


@router.get("/inventory/serial-numbers")
def list_serial_numbers(product_id: int | None = None, status: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    query = db.query(SRMSerialNumber).filter(SRMSerialNumber.organization_id == org_id)
    if product_id:
        query = query.filter(SRMSerialNumber.product_id == product_id)
    if status:
        query = query.filter(SRMSerialNumber.status == status)
    rows = query.order_by(SRMSerialNumber.id.desc()).limit(300).all()
    return {"items": [_serial_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/serial-numbers", status_code=201)
def create_serial_number(data: SRMSerialNumberCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    product = _product_or_404(db, org_id, data.product_id)
    batch = None
    if data.batch_id:
        batch = db.query(SRMInventoryBatch).filter(SRMInventoryBatch.organization_id == org_id, SRMInventoryBatch.id == data.batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch.product_id != product.id:
            raise HTTPException(status_code=400, detail="Serial batch must belong to the same product")
    warehouse_id = data.warehouse_id or (batch.warehouse_id if batch else None) or product.default_warehouse_id
    warehouse = _warehouse_or_404(db, org_id, warehouse_id) if warehouse_id else None
    if db.query(SRMSerialNumber).filter(SRMSerialNumber.organization_id == org_id, SRMSerialNumber.serial_number == data.serial_number).first():
        raise HTTPException(status_code=409, detail="Serial number already exists")
    serial = SRMSerialNumber(
        organization_id=org_id,
        product_id=product.id,
        warehouse_id=warehouse.id if warehouse else None,
        batch_id=batch.id if batch else None,
        serial_number=data.serial_number,
        status=data.status,
        received_date=data.received_date or date.today(),
        reference_number=data.reference_number,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    product.serial_tracking = True
    db.add(serial)
    db.flush()
    _audit(db, current_user, "serial_number", serial.id, "created", None, _serial_payload(serial))
    db.commit()
    db.refresh(serial)
    return _serial_payload(serial)


@router.get("/inventory/manufacturing/bom")
def list_boms(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMBillOfMaterial).filter(SRMBillOfMaterial.organization_id == _org(current_user), SRMBillOfMaterial.deleted_at.is_(None)).order_by(SRMBillOfMaterial.id.desc()).limit(100).all()
    return {"items": [_bom_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/manufacturing/bom", status_code=201)
def create_bom(data: SRMBillOfMaterialCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.components:
        raise HTTPException(status_code=400, detail="BOM components are required")
    if _decimal(data.output_quantity) <= 0:
        raise HTTPException(status_code=400, detail="BOM output quantity must be greater than zero")
    finished = _product_or_404(db, org_id, data.finished_product_id)
    bom_number = data.bom_number or _next_number(db, SRMBillOfMaterial, "BOM", "bom_number", org_id)
    if db.query(SRMBillOfMaterial).filter(SRMBillOfMaterial.organization_id == org_id, SRMBillOfMaterial.bom_number == bom_number, SRMBillOfMaterial.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="BOM number already exists")
    bom = SRMBillOfMaterial(
        organization_id=org_id,
        bom_number=bom_number,
        bom_name=data.bom_name,
        finished_product_id=finished.id,
        output_quantity=data.output_quantity,
        status=data.status,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(bom)
    db.flush()
    for component_data in data.components:
        component_product = _product_or_404(db, org_id, component_data.component_product_id)
        if component_product.id == finished.id:
            raise HTTPException(status_code=400, detail="Finished product cannot also be a component")
        if _decimal(component_data.quantity) <= 0:
            raise HTTPException(status_code=400, detail="Component quantity must be greater than zero")
        warehouse_id = component_data.warehouse_id or component_product.default_warehouse_id
        line_total = component_data.line_total if component_data.line_total is not None else _decimal(component_data.quantity) * _decimal(component_data.unit_cost or component_product.average_cost or component_product.purchase_rate or 0)
        component = SRMBOMComponent(
            bom_id=bom.id,
            component_product_id=component_product.id,
            warehouse_id=warehouse_id,
            quantity=component_data.quantity,
            scrap_percent=component_data.scrap_percent,
            unit_cost=component_data.unit_cost or component_product.average_cost or component_product.purchase_rate or 0,
            line_total=line_total,
            metadata_json=component_data.metadata_json,
        )
        db.add(component)
    db.flush()
    _audit(db, current_user, "bill_of_material", bom.id, "created", None, _bom_payload(bom))
    db.commit()
    db.refresh(bom)
    return _bom_payload(bom)


@router.get("/inventory/manufacturing/bom/{bom_id}")
def get_bom(bom_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    bom = db.query(SRMBillOfMaterial).filter(SRMBillOfMaterial.organization_id == _org(current_user), SRMBillOfMaterial.id == bom_id, SRMBillOfMaterial.deleted_at.is_(None)).first()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    return _bom_payload(bom)


@router.get("/inventory/manufacturing/orders")
def list_production_orders(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMProductionOrder).filter(SRMProductionOrder.organization_id == _org(current_user)).order_by(SRMProductionOrder.id.desc()).limit(100).all()
    return {"items": [_production_order_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/manufacturing/orders", status_code=201)
def create_production_order(data: SRMProductionOrderCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    bom = db.query(SRMBillOfMaterial).filter(SRMBillOfMaterial.organization_id == org_id, SRMBillOfMaterial.id == data.bom_id, SRMBillOfMaterial.deleted_at.is_(None)).first()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    if _decimal(data.planned_quantity) <= 0:
        raise HTTPException(status_code=400, detail="Planned quantity must be greater than zero")
    production_number = data.production_number or _next_number(db, SRMProductionOrder, "MFG", "production_number", org_id)
    if db.query(SRMProductionOrder).filter(SRMProductionOrder.organization_id == org_id, SRMProductionOrder.production_number == production_number).first():
        raise HTTPException(status_code=409, detail="Production order number already exists")
    order = SRMProductionOrder(
        organization_id=org_id,
        production_number=production_number,
        bom_id=bom.id,
        finished_product_id=bom.finished_product_id,
        warehouse_id=data.warehouse_id or bom.finished_product.default_warehouse_id,
        planned_quantity=data.planned_quantity,
        order_date=data.order_date or date.today(),
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(order)
    db.flush()
    _audit(db, current_user, "production_order", order.id, "created", None, _production_order_payload(order))
    db.commit()
    db.refresh(order)
    return _production_order_payload(order)


@router.post("/inventory/manufacturing/orders/{order_id}/post")
def post_production_order(order_id: int, data: SRMProductionPostRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    order = db.query(SRMProductionOrder).filter(SRMProductionOrder.organization_id == _org(current_user), SRMProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Production order not found")
    if order.status == "completed":
        raise HTTPException(status_code=409, detail="Production order is already completed")
    completed_quantity = data.completed_quantity or (_decimal(order.planned_quantity) - _decimal(order.completed_quantity))
    movements = _post_production_inventory(db, order, completed_quantity, data.warehouse_id, current_user)
    _audit(db, current_user, "production_order", order.id, "posted", None, _production_order_payload(order))
    for movement in movements:
        _audit(db, current_user, "inventory_movement", movement.id, movement.movement_type.upper(), None, _serialize(movement))
    db.commit()
    db.refresh(order)
    return {"production_order": _production_order_payload(order), "movements": [_serialize(row) for row in movements]}


@router.get("/procurement/purchase-orders")
def list_purchase_orders(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMPurchaseOrder).filter(SRMPurchaseOrder.organization_id == _org(current_user), SRMPurchaseOrder.deleted_at.is_(None)).order_by(SRMPurchaseOrder.id.desc()).limit(100).all()
    return {"items": [_purchase_order_payload(row) for row in rows], "total": len(rows)}


@router.post("/procurement/purchase-orders", status_code=201)
def create_purchase_order(data: SRMPurchaseOrderCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.lines:
        raise HTTPException(status_code=400, detail="Purchase order lines are required")
    if data.po_number and db.query(SRMPurchaseOrder).filter(SRMPurchaseOrder.organization_id == org_id, SRMPurchaseOrder.po_number == data.po_number, SRMPurchaseOrder.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="Purchase order number already exists")
    po = SRMPurchaseOrder(
        organization_id=org_id,
        po_number=data.po_number or _next_number(db, SRMPurchaseOrder, "PO", "po_number", org_id),
        vendor_id=data.vendor_id,
        vendor_name=data.vendor_name,
        status="ordered",
        order_date=data.order_date or date.today(),
        expected_date=data.expected_date,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()
    subtotal = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    for line_data in data.lines:
        if _decimal(line_data.quantity) <= 0:
            raise HTTPException(status_code=400, detail="Purchase order quantity must be greater than zero")
        product = db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.id == line_data.product_id, SRMProduct.deleted_at.is_(None)).first() if line_data.product_id else None
        warehouse_id = line_data.warehouse_id or (product.default_warehouse_id if product else None)
        line_total = line_data.line_total if line_data.line_total is not None else _decimal(line_data.quantity) * _decimal(line_data.unit_price) + _decimal(line_data.tax_amount)
        line = SRMPurchaseOrderLine(
            purchase_order_id=po.id,
            product_id=line_data.product_id,
            warehouse_id=warehouse_id,
            item_code=line_data.item_code or (product.sku if product else None),
            description=line_data.description or (product.item_name if product else None),
            quantity=line_data.quantity,
            unit_price=line_data.unit_price,
            tax_amount=line_data.tax_amount,
            line_total=line_total,
            metadata_json=line_data.metadata_json,
        )
        db.add(line)
        subtotal += _decimal(line.quantity) * _decimal(line.unit_price)
        tax += _decimal(line.tax_amount)
        total += _decimal(line.line_total)
    po.subtotal = subtotal
    po.tax_amount = tax
    po.total_amount = total
    db.flush()
    _audit(db, current_user, "purchase_order", po.id, "created", None, _purchase_order_payload(po))
    db.commit()
    db.refresh(po)
    return _purchase_order_payload(po)


@router.get("/procurement/purchase-orders/{po_id}")
def get_purchase_order(po_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    po = db.query(SRMPurchaseOrder).filter(SRMPurchaseOrder.organization_id == _org(current_user), SRMPurchaseOrder.id == po_id, SRMPurchaseOrder.deleted_at.is_(None)).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return _purchase_order_payload(po)


@router.get("/procurement/grn")
def list_goods_receipts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMGoodsReceipt).filter(SRMGoodsReceipt.organization_id == _org(current_user)).order_by(SRMGoodsReceipt.id.desc()).limit(100).all()
    return {"items": [_goods_receipt_payload(row) for row in rows], "total": len(rows)}


@router.post("/procurement/grn", status_code=201)
def create_goods_receipt(data: SRMGoodsReceiptCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.lines:
        raise HTTPException(status_code=400, detail="GRN lines are required")
    po = db.query(SRMPurchaseOrder).filter(SRMPurchaseOrder.organization_id == org_id, SRMPurchaseOrder.id == data.purchase_order_id, SRMPurchaseOrder.deleted_at.is_(None)).first() if data.purchase_order_id else None
    po_lines = {line.id: line for line in po.lines} if po else {}
    receipt = SRMGoodsReceipt(
        organization_id=org_id,
        grn_number=data.grn_number or _next_number(db, SRMGoodsReceipt, "GRN", "grn_number", org_id),
        purchase_order_id=po.id if po else None,
        vendor_id=data.vendor_id or (po.vendor_id if po else None),
        vendor_name=data.vendor_name or (po.vendor_name if po else None),
        receipt_date=data.receipt_date or date.today(),
        reference_number=data.reference_number,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(receipt)
    db.flush()
    subtotal = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    movements: list[SRMInventoryMovement] = []
    for line_data in data.lines:
        po_line = po_lines.get(line_data.purchase_order_line_id or 0)
        product_id = line_data.product_id or (po_line.product_id if po_line else None)
        product = db.query(SRMProduct).filter(SRMProduct.organization_id == org_id, SRMProduct.id == product_id, SRMProduct.deleted_at.is_(None)).first() if product_id else None
        accepted = line_data.accepted_quantity if line_data.accepted_quantity is not None else line_data.quantity
        if _decimal(accepted) < 0 or _decimal(line_data.rejected_quantity) < 0:
            raise HTTPException(status_code=400, detail="GRN quantities cannot be negative")
        if po_line:
            already_received = _received_quantity_for_po_line(db, po_line.id)
            if already_received + _decimal(accepted) > _decimal(po_line.quantity):
                raise HTTPException(status_code=409, detail=f"Received quantity exceeds ordered quantity for {po_line.description}")
        warehouse_id = line_data.warehouse_id or (po_line.warehouse_id if po_line else None) or (product.default_warehouse_id if product else None)
        line_total = line_data.line_total if line_data.line_total is not None else _decimal(accepted) * _decimal(line_data.unit_price or (po_line.unit_price if po_line else 0)) + _decimal(line_data.tax_amount)
        line = SRMGoodsReceiptLine(
            goods_receipt_id=receipt.id,
            purchase_order_line_id=po_line.id if po_line else None,
            product_id=product_id,
            warehouse_id=warehouse_id,
            item_code=line_data.item_code or (po_line.item_code if po_line else None) or (product.sku if product else None),
            description=line_data.description or (po_line.description if po_line else None) or (product.item_name if product else None),
            quantity=line_data.quantity,
            accepted_quantity=accepted,
            rejected_quantity=line_data.rejected_quantity,
            unit_price=line_data.unit_price or (po_line.unit_price if po_line else 0),
            tax_amount=line_data.tax_amount,
            line_total=line_total,
            metadata_json=line_data.metadata_json,
        )
        db.add(line)
        db.flush()
        movement = _stock_in_from_grn_line(db, receipt, line, current_user)
        if movement:
            movements.append(movement)
        subtotal += _decimal(line.accepted_quantity) * _decimal(line.unit_price)
        tax += _decimal(line.tax_amount)
        total += _decimal(line.line_total)
    receipt.subtotal = subtotal
    receipt.tax_amount = tax
    receipt.total_amount = total
    if po:
        _update_purchase_order_receipt_status(db, po)
    _audit(db, current_user, "goods_receipt", receipt.id, "posted", None, _goods_receipt_payload(receipt))
    for movement in movements:
        _audit(db, current_user, "inventory_movement", movement.id, "GRN_RECEIPT", None, _serialize(movement))
    db.commit()
    db.refresh(receipt)
    return _goods_receipt_payload(receipt)


@router.get("/procurement/grn/{grn_id}")
def get_goods_receipt(grn_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    receipt = db.query(SRMGoodsReceipt).filter(SRMGoodsReceipt.organization_id == _org(current_user), SRMGoodsReceipt.id == grn_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="GRN not found")
    return _goods_receipt_payload(receipt)


@router.get("/pricing/price-lists")
def list_price_lists(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMPriceList).filter(SRMPriceList.organization_id == _org(current_user), SRMPriceList.deleted_at.is_(None)).order_by(SRMPriceList.priority.asc(), SRMPriceList.id.desc()).limit(100).all()
    return {"items": [_price_list_payload(row) for row in rows], "total": len(rows)}


@router.post("/pricing/price-lists", status_code=201)
def create_price_list(data: SRMPriceListCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.lines:
        raise HTTPException(status_code=400, detail="Price list lines are required")
    code = data.price_list_code or _next_number(db, SRMPriceList, "PL", "price_list_code", org_id)
    if db.query(SRMPriceList).filter(SRMPriceList.organization_id == org_id, SRMPriceList.price_list_code == code, SRMPriceList.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="Price list code already exists")
    if data.effective_from and data.effective_to and data.effective_to < data.effective_from:
        raise HTTPException(status_code=400, detail="Effective-to date cannot be before effective-from date")
    price_list = SRMPriceList(
        organization_id=org_id,
        price_list_code=code,
        price_list_name=data.price_list_name,
        channel=data.channel,
        customer_type=data.customer_type,
        currency=data.currency,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        priority=data.priority,
        active=data.active,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(price_list)
    db.flush()
    for line_data in data.lines:
        product = _product_or_404(db, org_id, line_data.product_id)
        if _decimal(line_data.min_quantity) <= 0:
            raise HTTPException(status_code=400, detail="Minimum quantity must be greater than zero")
        if _decimal(line_data.price) < 0:
            raise HTTPException(status_code=400, detail="Price cannot be negative")
        line = SRMPriceListLine(
            price_list_id=price_list.id,
            product_id=product.id,
            sku=product.sku,
            item_name=product.item_name,
            min_quantity=line_data.min_quantity,
            price=line_data.price,
            discount_percent=line_data.discount_percent,
            discount_amount=line_data.discount_amount,
            tax_inclusive=line_data.tax_inclusive,
            active=line_data.active,
            metadata_json=line_data.metadata_json,
        )
        db.add(line)
    db.flush()
    _audit(db, current_user, "price_list", price_list.id, "created", None, _price_list_payload(price_list))
    db.commit()
    db.refresh(price_list)
    return _price_list_payload(price_list)


@router.get("/pricing/price-lists/{price_list_id}")
def get_price_list(price_list_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    row = db.query(SRMPriceList).filter(SRMPriceList.organization_id == _org(current_user), SRMPriceList.id == price_list_id, SRMPriceList.deleted_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Price list not found")
    return _price_list_payload(row)


@router.post("/pricing/lookup")
def lookup_prices(data: SRMPriceLookupRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    price_date = data.price_date or date.today()
    quantity = _decimal(data.quantity or 1)
    rows = []
    for product_id in data.product_ids:
        product = _product_or_404(db, org_id, product_id)
        line = _matching_price_line(db, org_id, product.id, data.channel, data.customer_type, price_date, quantity)
        list_row = line.price_list if line else None
        price = _decimal(line.price if line else product.sales_rate)
        discount_amount = _decimal(line.discount_amount if line else 0)
        discount_percent = _decimal(line.discount_percent if line else 0)
        net_price = price - discount_amount
        if discount_percent:
            net_price = net_price - (net_price * discount_percent / Decimal("100"))
        rows.append({
            "product_id": product.id,
            "sku": product.sku,
            "item_name": product.item_name,
            "base_price": float(price),
            "net_price": float(net_price),
            "discount_percent": float(discount_percent),
            "discount_amount": float(discount_amount),
            "currency": list_row.currency if list_row else "INR",
            "price_list_id": list_row.id if list_row else None,
            "price_list_code": list_row.price_list_code if list_row else None,
            "price_list_name": list_row.price_list_name if list_row else "Default product sales rate",
            "tax_inclusive": bool(line.tax_inclusive) if line else False,
        })
    return {"items": rows, "total": len(rows), "price_date": price_date.isoformat()}


@router.get("/pos/sessions")
def list_pos_sessions(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    sessions = db.query(SRMPOSSession).filter(SRMPOSSession.organization_id == _org(current_user), SRMPOSSession.deleted_at == None).order_by(SRMPOSSession.id.desc()).limit(100).all()
    return [_pos_session_summary(db, item) for item in sessions]


@router.post("/pos/sessions", status_code=201)
def open_pos_session(data: SRMPOSSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    open_session = db.query(SRMPOSSession).filter(SRMPOSSession.organization_id == org_id, SRMPOSSession.cashier_user_id == current_user.id, SRMPOSSession.status == "open", SRMPOSSession.deleted_at == None).first()
    if open_session:
        return _pos_session_summary(db, open_session)
    item = SRMPOSSession(
        organization_id=org_id,
        session_number=_next_number(db, SRMPOSSession, "POS", "session_number", org_id),
        branch=data.branch,
        register_name=data.register_name,
        cashier_user_id=current_user.id,
        opening_cash=data.opening_cash,
        expected_cash=data.opening_cash,
        notes=data.notes,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    _audit(db, current_user, "pos_session", item.id, "opened", after=_serialize(item))
    db.commit()
    db.refresh(item)
    return _pos_session_summary(db, item)


@router.get("/pos/sessions/active")
def active_pos_session(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = db.query(SRMPOSSession).filter(SRMPOSSession.organization_id == _org(current_user), SRMPOSSession.cashier_user_id == current_user.id, SRMPOSSession.status == "open", SRMPOSSession.deleted_at == None).order_by(SRMPOSSession.id.desc()).first()
    if not item:
        return {"session": None, "sales_count": 0, "cash_sales": 0, "cash_in": 0, "cash_out": 0, "expected_cash": 0, "movements": [], "closing": None}
    return _pos_session_summary(db, item)


@router.post("/pos/cash-movements", status_code=201)
def create_pos_cash_movement(data: SRMPOSCashMovementCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    session = _get_pos_session(db, data.session_id, current_user)
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Cannot add cash movement to a closed session")
    movement_type = data.movement_type if data.movement_type in {"cash_in", "cash_out"} else "cash_in"
    item = SRMPOSCashMovement(
        organization_id=_org(current_user),
        session_id=session.id,
        movement_type=movement_type,
        amount=data.amount,
        reason=data.reason,
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    summary = _pos_session_summary(db, session)
    session.expected_cash = summary["expected_cash"]
    _audit(db, current_user, "pos_cash_movement", item.id, "created", after=_serialize(item))
    db.commit()
    db.refresh(session)
    return _pos_session_summary(db, session)


@router.post("/pos/cashier-closing", status_code=201)
def close_pos_session(data: SRMPOSCashierClosingCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    session = _get_pos_session(db, data.session_id, current_user)
    if session.status == "closed":
        return _pos_session_summary(db, session)
    summary = _pos_session_summary(db, session)
    expected_cash = _decimal(summary["expected_cash"])
    variance = _decimal(data.counted_cash) - expected_cash
    closing = SRMPOSCashierClosing(
        organization_id=_org(current_user),
        session_id=session.id,
        opening_cash=session.opening_cash,
        cash_sales=summary["cash_sales"],
        cash_in=summary["cash_in"],
        cash_out=summary["cash_out"],
        expected_cash=expected_cash,
        counted_cash=data.counted_cash,
        variance=variance,
        notes=data.notes,
        closed_by=current_user.id,
    )
    session.status = "closed"
    session.expected_cash = expected_cash
    session.counted_cash = data.counted_cash
    session.cash_variance = variance
    session.closed_at = datetime.now(timezone.utc)
    db.add(closing)
    db.flush()
    _audit(db, current_user, "pos_session", session.id, "closed", after=_serialize(session))
    db.commit()
    db.refresh(session)
    return _pos_session_summary(db, session)


@router.get("/pos/held-bills")
def list_pos_held_bills(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMPOSHeldBill).filter(
        SRMPOSHeldBill.organization_id == _org(current_user),
        SRMPOSHeldBill.status == "held",
        SRMPOSHeldBill.deleted_at.is_(None),
    ).order_by(SRMPOSHeldBill.id.desc()).limit(100).all()
    return {"items": [_held_bill_payload(row) for row in rows], "total": len(rows)}


@router.post("/pos/held-bills", status_code=201)
def create_pos_held_bill(data: SRMPOSHeldBillCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.cart_json:
        raise HTTPException(status_code=400, detail="Held bill cart cannot be empty")
    if data.session_id:
        _get_pos_session(db, data.session_id, current_user)
    row = SRMPOSHeldBill(
        organization_id=org_id,
        session_id=data.session_id,
        hold_number=_next_number(db, SRMPOSHeldBill, "HOLD", "hold_number", org_id),
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        notes=data.notes,
        cart_json=data.cart_json,
        amount=data.amount,
        item_count=data.item_count or len(data.cart_json),
        created_by=current_user.id,
    )
    db.add(row)
    db.flush()
    _audit(db, current_user, "pos_held_bill", row.id, "held", None, _held_bill_payload(row))
    db.commit()
    db.refresh(row)
    return _held_bill_payload(row)


@router.post("/pos/held-bills/{held_bill_id}/recall")
def recall_pos_held_bill(held_bill_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    row = db.query(SRMPOSHeldBill).filter(
        SRMPOSHeldBill.organization_id == _org(current_user),
        SRMPOSHeldBill.id == held_bill_id,
        SRMPOSHeldBill.status == "held",
        SRMPOSHeldBill.deleted_at.is_(None),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Held bill not found")
    before = _held_bill_payload(row)
    row.status = "recalled"
    row.recalled_by = current_user.id
    row.recalled_at = datetime.now(timezone.utc)
    _audit(db, current_user, "pos_held_bill", row.id, "recalled", before, _held_bill_payload(row))
    db.commit()
    db.refresh(row)
    return _held_bill_payload(row)


@router.delete("/pos/held-bills/{held_bill_id}")
def delete_pos_held_bill(held_bill_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    row = db.query(SRMPOSHeldBill).filter(
        SRMPOSHeldBill.organization_id == _org(current_user),
        SRMPOSHeldBill.id == held_bill_id,
        SRMPOSHeldBill.status == "held",
        SRMPOSHeldBill.deleted_at.is_(None),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Held bill not found")
    before = _held_bill_payload(row)
    row.status = "cancelled"
    row.deleted_at = datetime.now(timezone.utc)
    _audit(db, current_user, "pos_held_bill", row.id, "cancelled", before, _held_bill_payload(row))
    db.commit()
    return {"status": "cancelled", "id": held_bill_id}


@router.get("/pos/returns")
def list_pos_returns(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    rows = db.query(SRMPOSReturn).filter(SRMPOSReturn.organization_id == _org(current_user)).order_by(SRMPOSReturn.id.desc()).limit(100).all()
    return {"items": [_return_payload(row) for row in rows], "total": len(rows)}


@router.post("/pos/returns", status_code=201)
def create_pos_return(data: SRMPOSReturnCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if not data.lines:
        raise HTTPException(status_code=400, detail="Return lines are required")
    order = _resolve_return_order(db, data, org_id)
    order_lines_by_id = {line.id: line for line in order.lines}
    order_lines_by_product = {line.product_id: line for line in order.lines if line.product_id}
    return_doc = SRMPOSReturn(
        organization_id=org_id,
        return_number=_next_number(db, SRMPOSReturn, "RET", "return_number", org_id),
        sales_order_id=order.id,
        session_id=data.session_id,
        customer_id=data.customer_id or order.customer_id,
        customer_name=data.customer_name,
        refund_method=data.refund_method,
        refund_status=data.refund_status,
        reason=data.reason,
        metadata_json=data.metadata_json,
        created_by=current_user.id,
    )
    db.add(return_doc)
    db.flush()
    subtotal = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    movements: list[SRMInventoryMovement] = []
    for line_data in data.lines:
        source_line = order_lines_by_id.get(line_data.sales_order_line_id or 0)
        if not source_line and line_data.product_id:
            source_line = order_lines_by_product.get(line_data.product_id)
        if not source_line:
            raise HTTPException(status_code=400, detail="Return line does not match original sale")
        already_returned = _returned_quantity_for_order_line(db, source_line.id)
        requested = _decimal(line_data.quantity)
        if requested <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if already_returned + requested > _decimal(source_line.quantity):
            raise HTTPException(status_code=409, detail=f"Return quantity exceeds sold quantity for {source_line.description}")
        line_total = line_data.line_total if line_data.line_total is not None else requested * _decimal(line_data.unit_price or source_line.unit_price) + _decimal(line_data.tax_amount)
        line = SRMPOSReturnLine(
            return_id=return_doc.id,
            sales_order_line_id=source_line.id,
            product_id=line_data.product_id or source_line.product_id,
            warehouse_id=line_data.warehouse_id or ((source_line.metadata_json or {}).get("warehouse_id") if source_line.metadata_json else None),
            item_code=line_data.item_code or source_line.item_code,
            description=line_data.description or source_line.description,
            quantity=requested,
            unit_price=line_data.unit_price or source_line.unit_price,
            tax_amount=line_data.tax_amount,
            line_total=line_total,
            condition=line_data.condition,
            restock=line_data.restock,
            metadata_json=line_data.metadata_json,
        )
        db.add(line)
        db.flush()
        movement = _restock_return_line(db, return_doc, line, order, current_user)
        if movement:
            movements.append(movement)
        subtotal += requested * _decimal(line.unit_price)
        tax += _decimal(line.tax_amount)
        total += _decimal(line.line_total)
    return_doc.subtotal = subtotal
    return_doc.tax_amount = tax
    return_doc.refund_amount = total
    _audit(db, current_user, "pos_return", return_doc.id, "created", None, _return_payload(return_doc))
    for movement in movements:
        _audit(db, current_user, "inventory_movement", movement.id, "POS_RETURN", None, _serialize(movement))
    db.commit()
    db.refresh(return_doc)
    return _return_payload(return_doc)


@router.get("/pos/returns/{return_id}")
def get_pos_return(return_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    row = db.query(SRMPOSReturn).filter(SRMPOSReturn.organization_id == _org(current_user), SRMPOSReturn.id == return_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="POS return not found")
    return _return_payload(row)


@router.post("/sales-orders", status_code=201)
def create_sales_order(data: SRMSalesOrderCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if data.order_number:
        existing = db.query(SRMSalesOrder).filter(SRMSalesOrder.organization_id == org_id, SRMSalesOrder.order_number == data.order_number, SRMSalesOrder.deleted_at == None).first()
        if existing:
            raise HTTPException(status_code=409, detail="Sales order number already exists")
    _validate_pos_stock_available(db, data, org_id)
    item = SRMSalesOrder(
        organization_id=org_id,
        order_number=data.order_number or _next_number(db, SRMSalesOrder, "SO", "order_number", org_id),
        title=data.title,
        crm_deal_id=data.crm_deal_id,
        crm_quote_id=data.crm_quote_id,
        crm_company_id=data.crm_company_id,
        crm_contact_id=data.crm_contact_id,
        customer_id=data.customer_id or data.crm_company_id,
        assigned_user_id=data.assigned_user_id or current_user.id,
        created_by=current_user.id,
        currency=data.currency,
        subtotal=data.subtotal,
        discount_amount=data.discount_amount,
        tax_amount=data.tax_amount,
        total_amount=data.total_amount or (data.subtotal - data.discount_amount + data.tax_amount),
        expected_start_date=data.expected_start_date,
        expected_end_date=data.expected_end_date,
        terms=data.terms,
        metadata_json=data.metadata_json,
    )
    db.add(item)
    db.flush()
    for line_data in data.lines:
        line_total = line_data.line_total if line_data.line_total is not None else (_decimal(line_data.quantity) * _decimal(line_data.unit_price) - _decimal(line_data.discount_amount) + _decimal(line_data.tax_amount))
        db.add(SRMSalesOrderLine(sales_order_id=item.id, line_total=line_total, **line_data.model_dump(exclude={"line_total"})))
    if data.lines:
        db.flush()
        subtotal, discount, tax, total = _total_from_lines(item.lines)
        item.subtotal = subtotal
        item.discount_amount = discount
        item.tax_amount = tax
        item.total_amount = total
    issued_movements = _issue_inventory_for_sales_order(db, item, current_user)
    _audit(db, current_user, "sales_order", item.id, "created", after=_serialize(item))
    for movement in issued_movements:
        _audit(db, current_user, "inventory_movement", movement.id, movement.movement_type.upper(), None, _serialize(movement))
    db.commit()
    db.refresh(item)
    return _serialize(item) | {"lines": [_serialize(line) for line in item.lines]}


@router.get("/sales-orders/{sales_order_id}")
def get_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    contract = db.query(SRMContract).filter(SRMContract.sales_order_id == item.id, SRMContract.deleted_at == None).first()
    engagement = db.query(SRMEngagement).filter(SRMEngagement.sales_order_id == item.id, SRMEngagement.deleted_at == None).first()
    billing_plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == engagement.id).first() if engagement else None
    project = None
    if engagement and engagement.pms_project_id:
        try:
            from app.apps.project_management.models import PMSProject

            project = db.query(PMSProject).filter(PMSProject.id == engagement.pms_project_id, PMSProject.deleted_at == None).first()
        except Exception:
            project = None
    audits = db.query(SRMAuditLog).filter(
        ((SRMAuditLog.entity_type == "sales_order") & (SRMAuditLog.entity_id == item.id))
        | ((SRMAuditLog.entity_type == "sales_order_line") & (SRMAuditLog.entity_id.in_([line.id for line in item.lines] or [0])))
    ).order_by(SRMAuditLog.created_at.desc()).limit(30).all()
    return _serialize(item) | {
        "lines": [_serialize(line) for line in item.lines],
        "contract": _serialize(contract),
        "engagement": _serialize(engagement),
        "billing_plan": _serialize(billing_plan),
        "pms_project": _serialize(project),
        "audit": [_serialize(audit) for audit in audits],
    }


@router.patch("/sales-orders/{sales_order_id}")
def update_sales_order(sales_order_id: int, data: SRMSalesOrderUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    before = _serialize(item)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "status":
            _assert_status(value, SALES_ORDER_STATUSES, "sales order")
            _transition(item.status, value, SALES_ORDER_TRANSITIONS, "sales order")
        setattr(item, key, value)
    _audit(db, current_user, "sales_order", item.id, "updated", before=before, after=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/sales-orders/{sales_order_id}/lines", status_code=201)
def add_sales_order_line(sales_order_id: int, data: SRMSalesOrderLineInput, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    order = get_sales_order_for_user(db, sales_order_id, current_user)
    if order.status not in {"draft", "pending_approval"}:
        raise HTTPException(status_code=400, detail="Sales order lines can only be changed before confirmation")
    line_total = data.line_total if data.line_total is not None else (_decimal(data.quantity) * _decimal(data.unit_price) - _decimal(data.discount_amount) + _decimal(data.tax_amount))
    line = SRMSalesOrderLine(sales_order_id=order.id, line_total=line_total, **data.model_dump(exclude={"line_total"}))
    db.add(line)
    _recalculate_sales_order(db, order)
    _audit(db, current_user, "sales_order_line", line.id, "created", after=_serialize(line))
    db.commit()
    db.refresh(line)
    return _serialize(line)


@router.patch("/sales-orders/{sales_order_id}/lines/{line_id}")
def update_sales_order_line(sales_order_id: int, line_id: int, data: SRMSalesOrderLineUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    order = get_sales_order_for_user(db, sales_order_id, current_user)
    if order.status not in {"draft", "pending_approval"}:
        raise HTTPException(status_code=400, detail="Sales order lines can only be changed before confirmation")
    line = db.query(SRMSalesOrderLine).filter(SRMSalesOrderLine.id == line_id, SRMSalesOrderLine.sales_order_id == order.id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Sales order line not found")
    before = _serialize(line)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(line, key, value)
    if data.line_total is None:
        line.line_total = _decimal(line.quantity) * _decimal(line.unit_price) - _decimal(line.discount_amount) + _decimal(line.tax_amount)
    _recalculate_sales_order(db, order)
    _audit(db, current_user, "sales_order_line", line.id, "updated", before=before, after=_serialize(line))
    db.commit()
    db.refresh(line)
    return _serialize(line)


@router.delete("/sales-orders/{sales_order_id}/lines/{line_id}")
def delete_sales_order_line(sales_order_id: int, line_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    order = get_sales_order_for_user(db, sales_order_id, current_user)
    if order.status not in {"draft", "pending_approval"}:
        raise HTTPException(status_code=400, detail="Sales order lines can only be changed before confirmation")
    line = db.query(SRMSalesOrderLine).filter(SRMSalesOrderLine.id == line_id, SRMSalesOrderLine.sales_order_id == order.id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Sales order line not found")
    before = _serialize(line)
    db.delete(line)
    _recalculate_sales_order(db, order)
    _audit(db, current_user, "sales_order_line", line_id, "deleted", before=before)
    db.commit()
    return {"deleted": True, "id": line_id}


@router.post("/sales-orders/{sales_order_id}/submit")
def submit_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    if item.status not in {"draft", "pending_approval"}:
        raise HTTPException(status_code=400, detail="Only draft sales orders can be submitted")
    threshold_setting = db.query(SRMSetting).filter(SRMSetting.organization_id == item.organization_id, SRMSetting.key == "sales_order_approval_threshold").first()
    threshold = _decimal((threshold_setting.value_json or {}).get("amount")) if threshold_setting and isinstance(threshold_setting.value_json, dict) else Decimal("1000000")
    before = item.status
    if _decimal(item.total_amount) >= threshold:
        approval = ApprovalRequest(
            source_module="srm",
            approval_type="sales_order",
            entity_type="srm_sales_order",
            entity_id=item.id,
            title=f"Approve sales order {item.order_number}",
            description=f"{item.title} requires approval for {item.currency} {item.total_amount}",
            requester_user_id=current_user.id,
            assigned_role="srm_finance_manager",
            priority="High",
            status="Pending",
            sla_due_at=datetime.now(timezone.utc) + timedelta(days=2),
            context_json={"sales_order_id": item.id, "total_amount": float(_decimal(item.total_amount))},
        )
        db.add(approval)
        db.flush()
        db.add(ApprovalHistory(request_id=approval.id, event_type="created", actor_user_id=current_user.id, after_status="Pending"))
        item.approval_request_id = approval.id
        item.status = "pending_approval"
    else:
        item.status = "approved"
        item.approved_by = current_user.id
    _audit(db, current_user, "sales_order", item.id, "submitted", before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/sales-orders/{sales_order_id}/approve")
def approve_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_approve", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    if item.status not in {"pending_approval", "approved"}:
        raise HTTPException(status_code=400, detail="Only pending sales orders can be approved")
    before = item.status
    item.status = "approved"
    item.approved_by = current_user.id
    if item.approval_request_id:
        approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == item.approval_request_id).first()
        if approval:
            approval.status = "Approved"
            approval.decided_by = current_user.id
            approval.decided_at = datetime.now(timezone.utc)
            db.add(ApprovalHistory(request_id=approval.id, event_type="approved", actor_user_id=current_user.id, before_status="Pending", after_status="Approved"))
    _audit(db, current_user, "sales_order", item.id, "approved", before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/sales-orders/{sales_order_id}/confirm")
def confirm_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    if item.status not in {"approved", "confirmed"}:
        raise HTTPException(status_code=400, detail="Only approved sales orders can be confirmed")
    item.status = "confirmed"
    issued_movements = _issue_inventory_for_sales_order(db, item, current_user)
    engagement = db.query(SRMEngagement).filter(SRMEngagement.sales_order_id == item.id).first()
    if not engagement:
        engagement = SRMEngagement(
            organization_id=item.organization_id,
            engagement_number=_next_number(db, SRMEngagement, "ENG", "engagement_number", item.organization_id),
            sales_order_id=item.id,
            customer_id=item.customer_id,
            crm_deal_id=item.crm_deal_id,
            crm_quote_id=item.crm_quote_id,
            assigned_user_id=item.assigned_user_id,
            name=item.title,
            status="project_pending",
            budget_amount=item.total_amount,
            currency=item.currency,
            created_by=current_user.id,
        )
        db.add(engagement)
        db.flush()
        for module, entity_type, entity_id in [
            ("crm", "deal", item.crm_deal_id),
            ("crm", "quote", item.crm_quote_id),
            ("srm", "sales_order", item.id),
        ]:
            if entity_id:
                db.add(SRMEngagementLink(engagement_id=engagement.id, linked_module=module, linked_entity_type=entity_type, linked_entity_id=entity_id, label=f"{module}:{entity_type}"))
    contract = db.query(SRMContract).filter(SRMContract.sales_order_id == item.id, SRMContract.deleted_at == None).first()
    billing_plan = _ensure_billing_plan_from_sales_order(db, current_user, item, engagement, contract)
    _audit(db, current_user, "sales_order", item.id, "confirmed", after={"engagement_id": engagement.id, "billing_plan_id": billing_plan.id})
    for movement in issued_movements:
        _audit(db, current_user, "inventory_movement", movement.id, movement.movement_type.upper(), None, _serialize(movement))
    db.commit()
    return _serialize(item) | {"engagement": _serialize(engagement), "billing_plan": _serialize(billing_plan)}


@router.post("/sales-orders/{sales_order_id}/cancel")
def cancel_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    _transition(item.status, "cancelled", SALES_ORDER_TRANSITIONS, "sales order")
    before = item.status
    item.status = "cancelled"
    _audit(db, current_user, "sales_order", item.id, "cancelled", before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/sales-orders/{sales_order_id}/close")
def close_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_sales_order_for_user(db, sales_order_id, current_user)
    _transition(item.status, "closed", SALES_ORDER_TRANSITIONS, "sales order")
    before = item.status
    item.status = "closed"
    _audit(db, current_user, "sales_order", item.id, "closed", before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/handoff/crm-won/{deal_id}", status_code=201)
def handoff_crm_won(deal_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return create_sales_order_from_crm_deal_service(deal_id, db, current_user)


@router.post("/from-crm/deals/{deal_id}/create-sales-order", status_code=201)
def create_sales_order_from_crm_deal(deal_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return create_sales_order_from_crm_deal_service(deal_id, db, current_user)


@router.get("/by-crm-deal/{deal_id}")
def get_by_crm_deal(deal_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    records = _find_handoff_records(db, deal_id)
    if not records["sales_order"] and not records["engagement"]:
        raise HTTPException(status_code=404, detail="SRM handoff not found for CRM deal")
    return _handoff_payload(records, idempotent=True)


@router.get("/contracts")
def list_contracts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    return [_serialize(item) for item in db.query(SRMContract).filter(SRMContract.deleted_at == None).order_by(SRMContract.id.desc()).limit(200).all()]


@router.post("/contracts", status_code=201)
def create_contract(data: SRMContractCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    if data.contract_number:
        existing = db.query(SRMContract).filter(SRMContract.organization_id == org_id, SRMContract.contract_number == data.contract_number, SRMContract.deleted_at == None).first()
        if existing:
            raise HTTPException(status_code=409, detail="Contract number already exists")
    item = SRMContract(organization_id=org_id, contract_number=data.contract_number or _next_number(db, SRMContract, "CTR", "contract_number", org_id), created_by=current_user.id, **data.model_dump(exclude={"contract_number"}))
    db.add(item)
    db.flush()
    _audit(db, current_user, "contract", item.id, "created", after=_serialize(item))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = db.query(SRMContract).filter(SRMContract.id == contract_id, SRMContract.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Contract not found")
    sales_order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == item.sales_order_id, SRMSalesOrder.deleted_at == None).first() if item.sales_order_id else None
    engagement = db.query(SRMEngagement).filter(SRMEngagement.contract_id == item.id, SRMEngagement.deleted_at == None).first()
    billing_plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == engagement.id).first() if engagement else None
    invoices = db.query(SRMInvoice).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at == None).order_by(SRMInvoice.id.desc()).limit(20).all() if engagement else []
    audits = db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "contract", SRMAuditLog.entity_id == item.id).order_by(SRMAuditLog.created_at.desc()).limit(30).all()
    return _serialize(item) | {
        "sales_order": _serialize(sales_order),
        "engagement": _serialize(engagement),
        "billing_plan": _serialize(billing_plan),
        "invoices": [_serialize(invoice) for invoice in invoices],
        "audit": [_serialize(audit) for audit in audits],
    }


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: int, data: SRMContractUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = db.query(SRMContract).filter(SRMContract.id == contract_id, SRMContract.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Contract not found")
    before = _serialize(item)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _audit(db, current_user, "contract", item.id, "updated", before=before, after=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(item)
    return _serialize(item)


def _contract_status(contract_id: int, target_status: str, action: str, db: Session, current_user: User):
    item = db.query(SRMContract).filter(SRMContract.id == contract_id, SRMContract.deleted_at == None).first()
    if not item:
        raise HTTPException(status_code=404, detail="Contract not found")
    _transition(item.status, target_status, CONTRACT_TRANSITIONS, "contract")
    before = item.status
    item.status = target_status
    if target_status == "active":
        item.approved_by = current_user.id
    _audit(db, current_user, "contract", item.id, action, before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/contracts/{contract_id}/activate")
def activate_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _contract_status(contract_id, "active", "activated", db, current_user)


@router.post("/contracts/{contract_id}/expire")
def expire_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _contract_status(contract_id, "expired", "expired", db, current_user)


@router.post("/contracts/{contract_id}/terminate")
def terminate_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _contract_status(contract_id, "terminated", "terminated", db, current_user)


@router.post("/contracts/{contract_id}/renew")
def renew_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _contract_status(contract_id, "renewed", "renewed", db, current_user)


@router.get("/engagements")
def list_engagements(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    return [_serialize(item) for item in engagement_query(db, current_user).order_by(SRMEngagement.id.desc()).limit(200).all()]


@router.post("/engagements", status_code=201)
def create_engagement(data: SRMEngagementCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    org_id = _org(current_user)
    item = SRMEngagement(organization_id=org_id, engagement_number=data.engagement_number or _next_number(db, SRMEngagement, "ENG", "engagement_number", org_id), created_by=current_user.id, **data.model_dump(exclude={"engagement_number"}))
    db.add(item)
    db.flush()
    _audit(db, current_user, "engagement", item.id, "created", after=_serialize(item))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = get_engagement_for_user(db, engagement_id, current_user)
    links = db.query(SRMEngagementLink).filter(SRMEngagementLink.engagement_id == item.id).all()
    return _serialize(item) | {"links": [_serialize(link) for link in links]}


@router.patch("/engagements/{engagement_id}")
def update_engagement(engagement_id: int, data: SRMEngagementUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_engagement_for_user(db, engagement_id, current_user)
    before = _serialize(item)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "status":
            _assert_status(value, ENGAGEMENT_STATUSES, "engagement")
        setattr(item, key, value)
    _audit(db, current_user, "engagement", item.id, "updated", before=before, after=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/engagements/{engagement_id}/links", status_code=201)
def link_engagement(engagement_id: int, data: SRMEngagementLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = get_engagement_for_user(db, engagement_id, current_user)
    existing = db.query(SRMEngagementLink).filter(
        SRMEngagementLink.engagement_id == item.id,
        SRMEngagementLink.linked_module == data.linked_module,
        SRMEngagementLink.linked_entity_type == data.linked_entity_type,
        SRMEngagementLink.linked_entity_id == data.linked_entity_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Engagement link already exists")
    link = SRMEngagementLink(engagement_id=item.id, **data.model_dump())
    db.add(link)
    db.flush()
    _audit(db, current_user, "engagement_link", link.id, "created", after=_serialize(link))
    db.commit()
    db.refresh(link)
    return _serialize(link)


@router.post("/engagements/{engagement_id}/status/{target_status}")
def update_engagement_status(engagement_id: int, target_status: str, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    _assert_status(target_status, ENGAGEMENT_STATUSES, "engagement")
    item = get_engagement_for_user(db, engagement_id, current_user)
    before = item.status
    item.status = target_status
    _audit(db, current_user, "engagement", item.id, "status_changed", before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/engagements/{engagement_id}/timeline")
def engagement_timeline(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = get_engagement_for_user(db, engagement_id, current_user)
    audits = db.query(SRMAuditLog).filter(
        ((SRMAuditLog.entity_type == "engagement") & (SRMAuditLog.entity_id == item.id))
        | ((SRMAuditLog.entity_type == "sales_order") & (SRMAuditLog.entity_id == item.sales_order_id))
    ).order_by(SRMAuditLog.created_at.asc()).all()
    links = db.query(SRMEngagementLink).filter(SRMEngagementLink.engagement_id == item.id).all()
    return {"engagement": _serialize(item), "links": [_serialize(link) for link in links], "audit": [_serialize(audit) for audit in audits]}


@router.get("/engagements/{engagement_id}/lifecycle")
def engagement_lifecycle(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = get_engagement_for_user(db, engagement_id, current_user)
    sales_order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == item.sales_order_id, SRMSalesOrder.deleted_at == None).first() if item.sales_order_id else None
    contract = db.query(SRMContract).filter(SRMContract.id == item.contract_id, SRMContract.deleted_at == None).first() if item.contract_id else None
    billing_plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == item.id).first()
    invoices = db.query(SRMInvoice).filter(SRMInvoice.engagement_id == item.id, SRMInvoice.deleted_at == None).order_by(SRMInvoice.id.desc()).all()
    links = db.query(SRMEngagementLink).filter(SRMEngagementLink.engagement_id == item.id).all()
    audits = db.query(SRMAuditLog).filter(
        ((SRMAuditLog.entity_type == "engagement") & (SRMAuditLog.entity_id == item.id))
        | ((SRMAuditLog.entity_type == "sales_order") & (SRMAuditLog.entity_id == item.sales_order_id))
        | ((SRMAuditLog.entity_type == "billing_plan") & (SRMAuditLog.entity_id == (billing_plan.id if billing_plan else 0)))
    ).order_by(SRMAuditLog.created_at.asc()).all()
    project = None
    if item.pms_project_id:
        try:
            from app.apps.project_management.models import PMSProject

            project = db.query(PMSProject).filter(PMSProject.id == item.pms_project_id, PMSProject.deleted_at == None).first()
        except Exception:
            project = None
    return {
        "engagement": _serialize(item),
        "sales_order": _serialize(sales_order),
        "contract": _serialize(contract),
        "billing_plan": _serialize(billing_plan),
        "invoices": [_serialize(invoice) for invoice in invoices],
        "pms_project": _serialize(project),
        "links": [_serialize(link) for link in links],
        "audit": [_serialize(audit) for audit in audits],
    }


@router.post("/engagements/{engagement_id}/create-pms-project")
def create_pms_project(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    company_id = bos_company_id_for(current_user)
    if not is_module_enabled(db, "project_management", company_id):
        db.add(BOSLifecycleEvent(company_id=company_id, module_key="srm", entity_type="engagement", entity_id=str(engagement_id), event_name="srm_pms_handoff_skipped", status="skipped", message="PMS is not enabled", source_module="srm", target_module="project_management", actor_user_id=current_user.id))
        db.commit()
        return {"status": "skipped", "idempotent": True, "message": "PMS is not enabled", "engagement": None, "project": None}
    engagement = get_engagement_for_user(db, engagement_id, current_user)
    if engagement.pms_project_id:
        try:
            from app.apps.project_management.models import PMSProject

            existing_project = db.query(PMSProject).filter(PMSProject.id == engagement.pms_project_id, PMSProject.deleted_at == None).first()
        except Exception:
            existing_project = None
        _audit(db, current_user, "engagement", engagement.id, "pms_project_idempotent", after={"pms_project_id": engagement.pms_project_id})
        db.commit()
        return {"idempotent": True, "engagement": _serialize(engagement), "project": _serialize(existing_project)}
    order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == engagement.sales_order_id, SRMSalesOrder.deleted_at == None).first() if engagement.sales_order_id else None
    if not order or order.status != "confirmed":
        raise HTTPException(status_code=400, detail="PMS project can only be created after the SRM sales order is confirmed")
    try:
        from app.apps.project_management.models import PMSMilestone, PMSProject, PMSProjectMember, PMSTask
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PMS module is not available") from exc
    project_key = f"SRM{engagement.id}"
    project = PMSProject(
        organization_id=engagement.organization_id,
        manager_user_id=engagement.project_manager_user_id or current_user.id,
        owner_user_id=engagement.assigned_user_id or current_user.id,
        name=engagement.name,
        project_key=project_key,
        category="SRM Engagement",
        description=f"Created from SRM engagement {engagement.engagement_number}",
        status="Active",
        budget_amount=engagement.budget_amount,
        billing_status="Unbilled",
        is_client_visible=True,
    )
    db.add(project)
    db.flush()
    db.add(PMSProjectMember(project_id=project.id, user_id=project.manager_user_id, role="Project Manager", allocation_percent=100))
    kickoff = PMSMilestone(project_id=project.id, owner_user_id=project.manager_user_id, name="Kickoff", status="Not Started", progress_percent=0)
    db.add(kickoff)
    db.flush()
    lines = db.query(SRMSalesOrderLine).filter(SRMSalesOrderLine.sales_order_id == order.id).order_by(SRMSalesOrderLine.id.asc()).all()
    for index, line in enumerate(lines, start=1):
        milestone = PMSMilestone(
            project_id=project.id,
            owner_user_id=project.manager_user_id,
            name=line.description or f"Commercial line {index}",
            status="Not Started",
            progress_percent=0,
        )
        db.add(milestone)
        db.flush()
        db.add(PMSTask(
            project_id=project.id,
            milestone_id=milestone.id,
            assignee_user_id=project.manager_user_id,
            reporter_user_id=current_user.id,
            title=line.description or f"Deliver service line {index}",
            description=f"Created from SRM sales order line {line.id}",
            task_key=f"{project.project_key}-{index}",
            status="To Do",
            priority="Medium",
            estimated_hours=8,
            is_client_visible=True,
        ))
    engagement.pms_project_id = project.id
    engagement.status = "project_created"
    db.add(SRMEngagementLink(engagement_id=engagement.id, linked_module="project_management", linked_entity_type="project", linked_entity_id=project.id, label=project.project_key))
    _audit(db, current_user, "engagement", engagement.id, "pms_project_created", after={"pms_project_id": project.id})
    _notify(db, project.manager_user_id, "PMS project created", f"{project.project_key} was created from SRM engagement {engagement.engagement_number}.", "project", project.id, f"/pms/projects/{project.id}")
    _notify(db, engagement.assigned_user_id, "SRM engagement linked to PMS", f"{engagement.engagement_number} is linked to PMS project {project.project_key}.", "engagement", engagement.id, f"/srm/engagements/{engagement.id}")
    db.commit()
    return {"idempotent": False, "engagement": _serialize(engagement), "project": _serialize(project)}


@router.get("/billing-plans")
def list_billing_plans(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    return [_serialize(item) for item in db.query(SRMBillingPlan).order_by(SRMBillingPlan.id.desc()).limit(200).all()]


@router.post("/sales-orders/{sales_order_id}/billing-plan", status_code=201)
def create_billing_plan_from_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    order = get_sales_order_for_user(db, sales_order_id, current_user)
    engagement = db.query(SRMEngagement).filter(SRMEngagement.sales_order_id == order.id, SRMEngagement.deleted_at == None).first()
    if not engagement:
        raise HTTPException(status_code=400, detail="Sales order must have an SRM engagement before billing plan creation")
    contract = db.query(SRMContract).filter(SRMContract.sales_order_id == order.id, SRMContract.deleted_at == None).first()
    plan = _ensure_billing_plan_from_sales_order(db, current_user, order, engagement, contract)
    db.commit()
    db.refresh(plan)
    milestones = db.query(SRMBillingMilestone).filter(SRMBillingMilestone.billing_plan_id == plan.id).all()
    return _serialize(plan) | {"milestones": [_serialize(milestone) for milestone in milestones]}


@router.post("/billing-plans", status_code=201)
def create_billing_plan(data: SRMBillingPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    engagement = get_engagement_for_user(db, data.engagement_id, current_user)
    if data.billing_type not in {"fixed_fee", "milestone", "t&m", "time_and_material", "recurring", "hybrid"}:
        raise HTTPException(status_code=400, detail="Invalid billing plan type")
    item = SRMBillingPlan(organization_id=engagement.organization_id, created_by=current_user.id, **data.model_dump(exclude={"milestones"}))
    db.add(item)
    db.flush()
    for milestone in data.milestones:
        db.add(SRMBillingMilestone(billing_plan_id=item.id, **milestone.model_dump()))
    _audit(db, current_user, "billing_plan", item.id, "created", after=_serialize(item))
    db.commit()
    db.refresh(item)
    milestones = db.query(SRMBillingMilestone).filter(SRMBillingMilestone.billing_plan_id == item.id).all()
    return _serialize(item) | {"milestones": [_serialize(milestone) for milestone in milestones]}


@router.get("/billing-plans/{billing_plan_id}")
def get_billing_plan(billing_plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_manage", "srm_admin"))):
    item = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == billing_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    engagement = get_engagement_for_user(db, item.engagement_id, current_user)
    sales_order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == engagement.sales_order_id, SRMSalesOrder.deleted_at == None).first() if engagement.sales_order_id else None
    contract = db.query(SRMContract).filter(SRMContract.id == engagement.contract_id, SRMContract.deleted_at == None).first() if engagement.contract_id else None
    milestones = db.query(SRMBillingMilestone).filter(SRMBillingMilestone.billing_plan_id == item.id).all()
    invoices = db.query(SRMInvoice).filter(SRMInvoice.engagement_id == engagement.id, SRMInvoice.deleted_at == None).order_by(SRMInvoice.id.desc()).limit(20).all()
    invoiced_value = sum(_decimal(invoice.total_amount) for invoice in invoices)
    audits = db.query(SRMAuditLog).filter(
        ((SRMAuditLog.entity_type == "billing_plan") & (SRMAuditLog.entity_id == item.id))
        | ((SRMAuditLog.entity_type == "billing_milestone") & (SRMAuditLog.entity_id.in_([milestone.id for milestone in milestones] or [0])))
    ).order_by(SRMAuditLog.created_at.desc()).limit(30).all()
    return _serialize(item) | {
        "sales_order": _serialize(sales_order),
        "engagement": _serialize(engagement),
        "contract": _serialize(contract),
        "milestones": [_serialize(milestone) for milestone in milestones],
        "invoices": [_serialize(invoice) for invoice in invoices],
        "invoiced_value": float(invoiced_value),
        "balance_value": float(_decimal(item.total_amount) - invoiced_value),
        "audit": [_serialize(audit) for audit in audits],
    }


@router.patch("/billing-plans/{billing_plan_id}")
def update_billing_plan(billing_plan_id: int, data: SRMBillingPlanUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == billing_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    get_engagement_for_user(db, item.engagement_id, current_user)
    before = _serialize(item)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _audit(db, current_user, "billing_plan", item.id, "updated", before=before, after=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/billing-plans/{billing_plan_id}/milestones", status_code=201)
def add_billing_milestone(billing_plan_id: int, data: SRMBillingMilestoneInput, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    item = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == billing_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    get_engagement_for_user(db, item.engagement_id, current_user)
    milestone = SRMBillingMilestone(billing_plan_id=item.id, **data.model_dump())
    db.add(milestone)
    item.total_amount = _decimal(item.total_amount) + _decimal(data.amount)
    db.flush()
    _audit(db, current_user, "billing_milestone", milestone.id, "created", after=_serialize(milestone))
    db.commit()
    db.refresh(milestone)
    return _serialize(milestone)


def _billing_plan_status(billing_plan_id: int, target_status: str, action: str, db: Session, current_user: User):
    item = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == billing_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    get_engagement_for_user(db, item.engagement_id, current_user)
    _transition(item.status, target_status, BILLING_PLAN_TRANSITIONS, "billing plan")
    before = item.status
    item.status = target_status
    _audit(db, current_user, "billing_plan", item.id, action, before={"status": before}, after={"status": item.status})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/billing-plans/{billing_plan_id}/activate")
def activate_billing_plan(billing_plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _billing_plan_status(billing_plan_id, "active", "activated", db, current_user)


@router.post("/billing-plans/{billing_plan_id}/pause")
def pause_billing_plan(billing_plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _billing_plan_status(billing_plan_id, "paused", "paused", db, current_user)


@router.post("/billing-plans/{billing_plan_id}/complete")
def complete_billing_plan(billing_plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _billing_plan_status(billing_plan_id, "completed", "completed", db, current_user)


@router.post("/billing-plans/{billing_plan_id}/cancel")
def cancel_billing_plan(billing_plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_manage", "srm_admin"))):
    return _billing_plan_status(billing_plan_id, "cancelled", "cancelled", db, current_user)


def _create_invoice_from_lines(
    db: Session,
    user: User,
    source_type: str,
    source_id: int | None,
    engagement: SRMEngagement | None,
    sales_order: SRMSalesOrder | None,
    lines: list[dict],
    currency: str,
    billing_plan_id: int | None = None,
) -> SRMInvoice:
    _assert_invoice_source_available(db, source_type, source_id)
    if not lines:
        raise HTTPException(status_code=400, detail="At least one invoice line is required")
    for line in lines:
        line_source_type = line.get("source_type") or source_type
        line_source_id = line.get("source_id") if line.get("source_id") is not None else source_id
        _assert_invoice_source_available(db, line_source_type, line_source_id)
    subtotal = sum((_decimal(line.get("quantity", 1)) * _decimal(line.get("unit_price", 0))) for line in lines)
    tax = sum(_decimal(line.get("tax_amount", 0)) for line in lines)
    total = sum(_decimal(line.get("line_total")) if line.get("line_total") is not None else (_decimal(line.get("quantity", 1)) * _decimal(line.get("unit_price", 0)) + _decimal(line.get("tax_amount", 0))) for line in lines)
    org_id = (engagement.organization_id if engagement else None) or (sales_order.organization_id if sales_order else _org(user))
    draft = SRMInvoiceDraft(
        organization_id=org_id,
        sales_order_id=sales_order.id if sales_order else None,
        engagement_id=engagement.id if engagement else None,
        billing_plan_id=billing_plan_id,
        customer_id=(engagement.customer_id if engagement else None) or (sales_order.customer_id if sales_order else None),
        source_type=source_type,
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=total,
        created_by=user.id,
    )
    db.add(draft)
    db.flush()
    invoice = SRMInvoice(
        organization_id=org_id,
        invoice_number=_next_number(db, SRMInvoice, "INV", "invoice_number", org_id),
        invoice_draft_id=draft.id,
        sales_order_id=draft.sales_order_id,
        engagement_id=draft.engagement_id,
        customer_id=draft.customer_id,
        status="draft",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=total,
        balance_amount=total,
        created_by=user.id,
    )
    db.add(invoice)
    db.flush()
    for line in lines:
        db.add(SRMInvoiceLine(
            invoice_id=invoice.id,
            source_type=line.get("source_type") or source_type,
            source_id=line.get("source_id") if line.get("source_id") is not None else source_id,
            description=line["description"],
            quantity=line.get("quantity", 1),
            unit_price=line.get("unit_price", 0),
            tax_amount=line.get("tax_amount", 0),
            line_total=line.get("line_total"),
        ))
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, to_status="draft", actor_user_id=user.id, notes="Invoice draft created"))
    _audit(db, user, "invoice", invoice.id, "draft_created", after={"source_type": source_type, "source_id": source_id})
    _notify(db, user.id, "Invoice draft created", f"{invoice.invoice_number} is ready for review.", "invoice", invoice.id, f"/srm/invoices/{invoice.id}")
    return invoice


def _create_invoice_from_amount(db: Session, user: User, source_type: str, source_id: int, engagement: SRMEngagement | None, sales_order: SRMSalesOrder | None, amount: Decimal, description: str, currency: str, billing_plan_id: int | None = None) -> SRMInvoice:
    return _create_invoice_from_lines(
        db,
        user,
        source_type,
        source_id,
        engagement,
        sales_order,
        [{"description": description, "quantity": 1, "unit_price": amount, "line_total": amount}],
        currency,
        billing_plan_id=billing_plan_id,
    )


@router.post("/invoices/draft-from-sales-order/{sales_order_id}", status_code=201)
def draft_from_sales_order(sales_order_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    order = get_sales_order_for_user(db, sales_order_id, current_user)
    invoice = _create_invoice_from_amount(db, current_user, "sales_order", order.id, None, order, _decimal(order.total_amount), order.title, order.currency)
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice)


@router.post("/invoices/draft-from-engagement/{engagement_id}", status_code=201)
def draft_from_engagement(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    engagement = get_engagement_for_user(db, engagement_id, current_user)
    invoice = _create_invoice_from_amount(db, current_user, "engagement", engagement.id, engagement, None, _decimal(engagement.budget_amount), engagement.name, engagement.currency)
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice)


@router.post("/invoices/draft-from-billing-milestone/{milestone_id}", status_code=201)
def draft_from_billing_milestone(milestone_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    milestone = db.query(SRMBillingMilestone).filter(SRMBillingMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Billing milestone not found")
    if milestone.invoice_draft_id:
        raise HTTPException(status_code=409, detail="Billing milestone is already invoiced")
    plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.id == milestone.billing_plan_id).first()
    engagement = get_engagement_for_user(db, plan.engagement_id, current_user) if plan else None
    order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == engagement.sales_order_id).first() if engagement and engagement.sales_order_id else None
    if milestone.status not in {"approved", "ready", "completed"}:
        raise HTTPException(status_code=400, detail="Billing milestone must be approved or completed before invoicing")
    invoice = _create_invoice_from_amount(db, current_user, "billing_milestone", milestone.id, engagement, order, _decimal(milestone.amount), milestone.name, plan.currency if plan else "INR", billing_plan_id=plan.id if plan else None)
    db.flush()
    milestone.invoice_draft_id = invoice.invoice_draft_id
    milestone.status = "invoiced"
    _audit(db, current_user, "billing_milestone", milestone.id, "invoiced", after={"invoice_id": invoice.id, "invoice_draft_id": invoice.invoice_draft_id})
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice)


@router.post("/invoices/draft-from-pms-milestone/{pms_milestone_id}", status_code=201)
def draft_from_pms_milestone(pms_milestone_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    try:
        from app.apps.project_management.models import PMSMilestone
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PMS milestones are not available") from exc
    milestone = db.query(PMSMilestone).filter(PMSMilestone.id == pms_milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="PMS milestone not found")
    if str(milestone.client_approval_status or "").lower() not in {"approved", "client approved", "accepted"} and not milestone.client_approved_at:
        raise HTTPException(status_code=400, detail="PMS milestone must be client-approved before invoicing")
    engagement = db.query(SRMEngagement).filter(SRMEngagement.pms_project_id == milestone.project_id, SRMEngagement.deleted_at == None).first()
    if not engagement:
        raise HTTPException(status_code=404, detail="No SRM engagement is linked to this PMS project")
    get_engagement_for_user(db, engagement.id, current_user)
    order = db.query(SRMSalesOrder).filter(SRMSalesOrder.id == engagement.sales_order_id).first() if engagement.sales_order_id else None
    amount = _decimal(db.query(func.coalesce(func.sum(SRMBillingMilestone.amount), 0)).join(SRMBillingPlan, SRMBillingPlan.id == SRMBillingMilestone.billing_plan_id).filter(SRMBillingPlan.engagement_id == engagement.id, SRMBillingMilestone.name == milestone.name).scalar())
    if amount <= 0:
        amount = _decimal(engagement.budget_amount)
    invoice = _create_invoice_from_amount(db, current_user, "pms_milestone", milestone.id, engagement, order, amount, milestone.name, engagement.currency)
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice)


@router.post("/invoices/draft-from-timesheets", status_code=201)
def draft_from_timesheets(data: SRMTimeLogInvoiceRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    try:
        from app.apps.project_management.models import PMSTimeLog
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PMS time logs are not available") from exc
    logs = db.query(PMSTimeLog).filter(PMSTimeLog.id.in_(data.time_log_ids), PMSTimeLog.is_billable == True, PMSTimeLog.approval_status.in_(["Approved", "approved"])).all() if data.time_log_ids else []
    if len(logs) != len(set(data.time_log_ids)):
        raise HTTPException(status_code=400, detail="All selected time logs must be approved and billable")
    minutes = sum(log.duration_minutes for log in logs)
    if not minutes:
        raise HTTPException(status_code=400, detail="No billable time logs selected")
    engagement = db.query(SRMEngagement).filter(SRMEngagement.id == data.engagement_id).first() if data.engagement_id else None
    amount = Decimal(str(minutes)) / Decimal("60") * data.hourly_rate
    for time_log_id in data.time_log_ids:
        _assert_invoice_source_available(db, "pms_time_log", time_log_id)
    invoice = _create_invoice_from_lines(
        db,
        current_user,
        "timesheet",
        abs(hash(tuple(sorted(data.time_log_ids)))) % 100000000,
        engagement,
        None,
        [{
            "source_type": "pms_time_log",
            "source_id": log.id,
            "description": log.description or f"Billable time log {log.id}",
            "quantity": Decimal(str(log.duration_minutes)) / Decimal("60"),
            "unit_price": data.hourly_rate,
            "line_total": Decimal(str(log.duration_minutes)) / Decimal("60") * data.hourly_rate,
        } for log in logs],
        data.currency,
    )
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice) | {"time_log_ids": data.time_log_ids}


@router.post("/invoices/manual", status_code=201)
def manual_invoice(data: SRMManualInvoiceCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    engagement = get_engagement_for_user(db, data.engagement_id, current_user) if data.engagement_id else None
    order = get_sales_order_for_user(db, data.sales_order_id, current_user) if data.sales_order_id else None
    lines = []
    for line in data.lines:
        payload = line.model_dump()
        payload["source_type"] = payload.get("source_type") or "manual"
        lines.append(payload)
    invoice = _create_invoice_from_lines(db, current_user, "manual", None, engagement, order, lines, data.currency)
    invoice.customer_id = data.customer_id or invoice.customer_id
    if data.issue_date:
        invoice.issue_date = data.issue_date
    if data.due_date:
        invoice.due_date = data.due_date
    db.commit()
    db.refresh(invoice)
    return _invoice_payload(invoice)


@router.get("/invoice-drafts")
def list_invoice_drafts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_view", "srm_invoice_create", "srm_admin"))):
    return [_serialize(item) for item in db.query(SRMInvoiceDraft).order_by(SRMInvoiceDraft.id.desc()).limit(200).all()]


@router.get("/invoices")
def list_invoices(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_view", "srm_invoice_create", "srm_admin"))):
    return [_invoice_payload(item, db) for item in db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None).order_by(SRMInvoice.id.desc()).limit(200).all()]


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_view", "srm_invoice_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    return _invoice_payload(invoice, db)


@router.patch("/invoices/{invoice_id}")
def patch_invoice(invoice_id: int, data: SRMInvoicePatch, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    before = _serialize(invoice)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "status":
            _assert_status(value, INVOICE_STATUSES, "invoice")
            _transition(invoice.status, value, INVOICE_TRANSITIONS, "invoice")
        setattr(invoice, key, value)
    if data.total_amount is not None:
        invoice.balance_amount = _decimal(invoice.total_amount) - _decimal(invoice.paid_amount)
    _audit(db, current_user, "invoice", invoice.id, "updated", before=before, after=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(invoice)
    return _serialize(invoice)


@router.post("/invoices/{invoice_id}/lines", status_code=201)
def add_invoice_line(invoice_id: int, data: SRMInvoiceLineInput, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    if invoice.status not in {"draft", "pending_approval"}:
        raise HTTPException(status_code=400, detail="Invoice lines can only be changed before approval")
    if data.source_type and data.source_id:
        existing = db.query(SRMInvoiceLine).filter(SRMInvoiceLine.source_type == data.source_type, SRMInvoiceLine.source_id == data.source_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Invoice line source already billed")
    line_total = data.line_total if data.line_total is not None else (_decimal(data.quantity) * _decimal(data.unit_price) + _decimal(data.tax_amount))
    line = SRMInvoiceLine(invoice_id=invoice.id, line_total=line_total, **data.model_dump(exclude={"line_total"}))
    db.add(line)
    _recalculate_invoice(db, invoice)
    _audit(db, current_user, "invoice_line", line.id, "created", after=_serialize(line))
    db.commit()
    db.refresh(line)
    return _serialize(line)


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_approve", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    if invoice.status not in {"draft", "pending_approval", "approved"}:
        raise HTTPException(status_code=400, detail="Only draft or pending invoices can be approved")
    before = invoice.status
    invoice.status = "approved"
    invoice.approved_by = current_user.id
    invoice.approved_at = datetime.now(timezone.utc)
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, from_status=before, to_status="approved", actor_user_id=current_user.id))
    _audit(db, current_user, "invoice", invoice.id, "approved", before={"status": before}, after={"status": invoice.status})
    db.commit()
    db.refresh(invoice)
    return _serialize(invoice)


@router.post("/invoices/{invoice_id}/send")
def send_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    if invoice.status not in {"approved", "sent"}:
        raise HTTPException(status_code=400, detail="Only approved invoices can be sent")
    before = invoice.status
    invoice.status = "sent"
    invoice.sent_at = datetime.now(timezone.utc)
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, from_status=before, to_status="sent", actor_user_id=current_user.id))
    db.add(SRMRevenueEvent(organization_id=invoice.organization_id, engagement_id=invoice.engagement_id, invoice_id=invoice.id, event_type="invoice_sent", amount=invoice.total_amount, currency=invoice.currency, recognized_on=date.today()))
    _audit(db, current_user, "invoice", invoice.id, "sent", before={"status": before}, after={"status": invoice.status})
    db.commit()
    db.refresh(invoice)
    return _serialize(invoice)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_invoice_view", "srm_invoice_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    body = f"%PDF-1.4\n1 0 obj<<>>stream\nSRM Invoice {invoice.invoice_number} Amount {invoice.currency} {invoice.total_amount}\nendstream\nendobj\n%%EOF"
    return Response(content=body.encode("utf-8"), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'})


@router.post("/receipts", status_code=201)
def create_receipt(data: SRMReceiptCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    org_id = _org(current_user)
    item = SRMReceipt(organization_id=org_id, receipt_number=data.receipt_number or _next_number(db, SRMReceipt, "RCT", "receipt_number", org_id), created_by=current_user.id, unallocated_amount=data.amount, **data.model_dump(exclude={"receipt_number"}))
    db.add(item)
    db.flush()
    _audit(db, current_user, "receipt", item.id, "created", after=_serialize(item))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/receipts")
def list_receipts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_view", "srm_collection_create", "srm_admin"))):
    return [_serialize(item) | {"accounting_status": _srm_accounting_status(db, item.organization_id, "receipt", item.id)} for item in db.query(SRMReceipt).order_by(SRMReceipt.id.desc()).limit(200).all()]


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_view", "srm_collection_create", "srm_admin"))):
    item = db.query(SRMReceipt).filter(SRMReceipt.id == receipt_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Receipt not found")
    allocations = db.query(SRMReceiptAllocation).filter(SRMReceiptAllocation.receipt_id == item.id).all()
    return _serialize(item) | {"allocations": [_serialize(allocation) | {"accounting_status": _srm_accounting_status(db, item.organization_id, "allocation", allocation.id)} for allocation in allocations], "accounting_status": _srm_accounting_status(db, item.organization_id, "receipt", item.id)}


@router.post("/receipts/{receipt_id}/confirm")
def confirm_receipt(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    receipt = db.query(SRMReceipt).filter(SRMReceipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    _transition(receipt.status, "confirmed", RECEIPT_TRANSITIONS, "receipt")
    before = receipt.status
    receipt.status = "confirmed"
    _audit(db, current_user, "receipt", receipt.id, "confirmed", before={"status": before}, after={"status": receipt.status})
    db.commit()
    db.refresh(receipt)
    return _serialize(receipt)


@router.post("/receipts/{receipt_id}/allocate")
def allocate_receipt(receipt_id: int, data: SRMReceiptAllocationRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    receipt = db.query(SRMReceipt).filter(SRMReceipt.id == receipt_id).first()
    invoice = db.query(SRMInvoice).filter(SRMInvoice.id == data.invoice_id, SRMInvoice.deleted_at == None).first()
    if not receipt or not invoice:
        raise HTTPException(status_code=404, detail="Receipt or invoice not found")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Allocation amount must be positive")
    if _decimal(receipt.unallocated_amount) < data.amount:
        raise HTTPException(status_code=400, detail="Receipt does not have enough unallocated amount")
    if _decimal(invoice.balance_amount) < data.amount:
        raise HTTPException(status_code=400, detail="Allocation amount exceeds invoice balance")
    if receipt.status == "draft":
        receipt.status = "confirmed"
    allocation = SRMReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id, amount=data.amount, allocated_by=current_user.id)
    db.add(allocation)
    receipt.unallocated_amount = _decimal(receipt.unallocated_amount) - data.amount
    receipt.status = "allocated" if receipt.unallocated_amount <= 0 else "partially_allocated"
    invoice.paid_amount = _decimal(invoice.paid_amount) + data.amount
    invoice.balance_amount = _decimal(invoice.total_amount) - _decimal(invoice.paid_amount)
    invoice.status = "paid" if invoice.balance_amount <= 0 else "partially_paid"
    db.add(SRMRevenueEvent(organization_id=invoice.organization_id, engagement_id=invoice.engagement_id, invoice_id=invoice.id, event_type="cash_collected", amount=data.amount, currency=invoice.currency, recognized_on=date.today()))
    engagement = db.query(SRMEngagement).filter(SRMEngagement.id == invoice.engagement_id).first() if invoice.engagement_id else None
    if engagement:
        _create_profitability_snapshot(db, engagement, current_user)
    _audit(db, current_user, "receipt", receipt.id, "allocated", after={"invoice_id": invoice.id, "amount": float(data.amount)})
    db.commit()
    return {"receipt": _serialize(receipt), "invoice": _serialize(invoice), "allocation": _serialize(allocation)}


def _mark_invoice_collection_status(invoice: SRMInvoice, status_value: str) -> None:
    if invoice.status in {"paid", "cancelled"}:
        return
    if status_value == "escalated":
        invoice.status = "overdue"
    elif status_value == "written_off":
        invoice.status = "cancelled"


@router.post("/collections/{invoice_id}/escalate")
def escalate_collection(invoice_id: int, data: SRMReminderRequest | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    if invoice.balance_amount <= 0:
        raise HTTPException(status_code=400, detail="Paid invoices cannot be escalated")
    before = invoice.status
    _mark_invoice_collection_status(invoice, "escalated")
    reminder = SRMCollectionReminder(
        organization_id=invoice.organization_id,
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        status="sent",
        reminder_type="escalation",
        scheduled_at=datetime.now(timezone.utc),
        sent_at=datetime.now(timezone.utc),
        message=(data.message if data else None) or "Collection escalation raised",
        created_by=current_user.id,
    )
    db.add(reminder)
    db.flush()
    _audit(db, current_user, "invoice", invoice.id, "collection_escalated", before={"status": before}, after={"status": invoice.status, "reminder_id": reminder.id})
    _notify(db, invoice.created_by, "Collection escalated", f"{invoice.invoice_number} has been escalated for collection.", "invoice", invoice.id, f"/srm/invoices/{invoice.id}")
    db.commit()
    return {"invoice": _serialize(invoice), "escalation": _serialize(reminder)}


@router.post("/collections/{invoice_id}/write-off-request")
def write_off_request(invoice_id: int, data: SRMWriteOffRequest | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    invoice = _get_invoice(db, invoice_id)
    if invoice.balance_amount <= 0:
        raise HTTPException(status_code=400, detail="Paid invoices cannot be written off")
    amount = data.amount if data and data.amount is not None else _decimal(invoice.balance_amount)
    if amount <= 0 or amount > _decimal(invoice.balance_amount):
        raise HTTPException(status_code=400, detail="Write-off amount must be within invoice balance")
    reminder = SRMCollectionReminder(
        organization_id=invoice.organization_id,
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        status="queued",
        reminder_type="write_off_request",
        scheduled_at=datetime.now(timezone.utc),
        message=(data.reason if data else None) or "Write-off approval requested",
        created_by=current_user.id,
    )
    db.add(reminder)
    db.flush()
    _audit(db, current_user, "invoice", invoice.id, "write_off_requested", after={"amount": float(amount), "reason": data.reason if data else None, "request_id": reminder.id})
    _notify(db, invoice.created_by, "Write-off requested", f"{invoice.invoice_number} has a write-off request.", "invoice", invoice.id, f"/srm/invoices/{invoice.id}")
    db.commit()
    return {"invoice": _serialize(invoice), "write_off_request": _serialize(reminder)}


@router.get("/collections/aging")
def collections_aging(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_view", "srm_collection_create", "srm_admin"))):
    today = date.today()
    invoices = db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None, SRMInvoice.balance_amount > 0).all()
    buckets: dict[int, dict] = {}
    for invoice in invoices:
        customer_id = invoice.customer_id or 0
        bucket = buckets.setdefault(customer_id, {"customer_id": customer_id, "current_amount": 0, "days_1_30": 0, "days_31_60": 0, "days_61_90": 0, "days_90_plus": 0, "total_outstanding": 0})
        overdue_days = (today - invoice.due_date).days if invoice.due_date else 0
        amount = float(_decimal(invoice.balance_amount))
        if overdue_days <= 0:
            bucket["current_amount"] += amount
        elif overdue_days <= 30:
            bucket["days_1_30"] += amount
        elif overdue_days <= 60:
            bucket["days_31_60"] += amount
        elif overdue_days <= 90:
            bucket["days_61_90"] += amount
        else:
            bucket["days_90_plus"] += amount
        bucket["total_outstanding"] += amount
    for customer_id, bucket in buckets.items():
        aging = db.query(SRMCustomerAging).filter(SRMCustomerAging.organization_id == _org(current_user), SRMCustomerAging.customer_id == customer_id).first()
        if not aging:
            aging = SRMCustomerAging(organization_id=_org(current_user), customer_id=customer_id)
            db.add(aging)
        for key in ["current_amount", "days_1_30", "days_31_60", "days_61_90", "days_90_plus", "total_outstanding"]:
            setattr(aging, key, bucket[key])
    db.commit()
    return list(buckets.values())


@router.get("/collections/customer/{customer_id}")
def customer_collections(customer_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_view", "srm_collection_create", "srm_admin"))):
    invoices = db.query(SRMInvoice).filter(SRMInvoice.customer_id == customer_id, SRMInvoice.deleted_at == None).all()
    receipts = db.query(SRMReceipt).filter(SRMReceipt.customer_id == customer_id).all()
    reminders = db.query(SRMCollectionReminder).filter(SRMCollectionReminder.customer_id == customer_id).all()
    return {"invoices": [_serialize(item) for item in invoices], "receipts": [_serialize(item) for item in receipts], "reminders": [_serialize(item) for item in reminders]}


@router.post("/collections/reminders/send")
def send_collection_reminder(data: SRMReminderRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_collection_create", "srm_admin"))):
    invoice = db.query(SRMInvoice).filter(SRMInvoice.id == data.invoice_id).first() if data.invoice_id else None
    item = SRMCollectionReminder(
        organization_id=_org(current_user),
        customer_id=data.customer_id or (invoice.customer_id if invoice else None),
        invoice_id=invoice.id if invoice else None,
        status="sent",
        reminder_type="email",
        scheduled_at=datetime.now(timezone.utc),
        sent_at=datetime.now(timezone.utc),
        message=data.message or "Payment reminder",
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    _audit(db, current_user, "collection_reminder", item.id, "sent", after=_serialize(item))
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/profitability")
def profitability(
    engagement_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    crm_deal_id: int | None = Query(default=None),
    sales_order_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("srm_profitability_view", "srm_admin")),
):
    query = engagement_query(db, current_user)
    if engagement_id or project_id or customer_id or crm_deal_id or sales_order_id:
        if engagement_id:
            query = query.filter(SRMEngagement.id == engagement_id)
        if project_id:
            query = query.filter(SRMEngagement.pms_project_id == project_id)
        if customer_id:
            query = query.filter(SRMEngagement.customer_id == customer_id)
        if crm_deal_id:
            query = query.filter(SRMEngagement.crm_deal_id == crm_deal_id)
        if sales_order_id:
            query = query.filter(SRMEngagement.sales_order_id == sales_order_id)
        engagements = query.all()
        if not engagements:
            raise HTTPException(status_code=404, detail="No profitability records found for the requested scope")
        if len(engagements) == 1:
            snapshot = _create_profitability_snapshot(db, engagements[0], current_user)
            db.commit()
            db.refresh(snapshot)
            return _profitability_payload(snapshot)
        snapshots = [_create_profitability_snapshot(db, engagement, current_user) for engagement in engagements]
        db.commit()
        return [_profitability_payload(snapshot) for snapshot in snapshots]
    latest = db.query(SRMProfitabilitySnapshot).order_by(SRMProfitabilitySnapshot.snapshot_at.desc()).limit(100).all()
    return [_profitability_payload(item) for item in latest]


@router.get("/reports")
def reports(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_profitability_view", "srm_admin"))):
    aging = collections_aging(db, current_user)
    invoice_total = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.total_amount), 0)).filter(SRMInvoice.deleted_at == None).scalar())
    collected_total = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.paid_amount), 0)).filter(SRMInvoice.deleted_at == None).scalar())
    outstanding_total = _decimal(db.query(func.coalesce(func.sum(SRMInvoice.balance_amount), 0)).filter(SRMInvoice.deleted_at == None).scalar())
    snapshots = [_profitability_payload(item) for item in db.query(SRMProfitabilitySnapshot).order_by(SRMProfitabilitySnapshot.snapshot_at.desc()).limit(50).all()]
    return {
        "sales_order_report": {"count": db.query(SRMSalesOrder).filter(SRMSalesOrder.deleted_at == None).count()},
        "contract_report": {"count": db.query(SRMContract).filter(SRMContract.deleted_at == None).count()},
        "invoice_register": {"count": db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None).count(), "total": float(invoice_total)},
        "invoice_aging": aging,
        "collection_aging": aging,
        "customer_outstanding": {"total_outstanding": float(outstanding_total), "customers": aging},
        "engagement_profitability": snapshots,
        "project_profitability": [item for item in snapshots if item.get("engagement_id")],
        "customer_profitability": snapshots,
        "lead_to_cash_report": lead_to_cash_report(db, current_user),
        "sales_to_delivery_margin": {"gross_margin_total": sum(float(item.get("gross_margin") or 0) for item in snapshots)},
        "cash_margin_report": {"collected_total": float(collected_total), "cash_margin_total": sum(float(item.get("cash_margin") or 0) for item in snapshots)},
    }


def _dashboard_payload(db: Session, current_user: User) -> dict:
    org_id = _org(current_user)
    today = date.today()
    sales_orders = sales_order_query(db, current_user)
    engagements = engagement_query(db, current_user)
    sales_order_ids = [item.id for item in sales_orders.with_entities(SRMSalesOrder.id).all()]
    engagement_ids = [item.id for item in engagements.with_entities(SRMEngagement.id).all()]

    invoice_query = db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None)
    invoice_draft_query = db.query(SRMInvoiceDraft)
    contract_query = db.query(SRMContract).filter(SRMContract.deleted_at == None)
    billing_plan_query = db.query(SRMBillingPlan)
    revenue_query = db.query(SRMRevenueEvent)
    snapshot_query = db.query(SRMProfitabilitySnapshot)
    if not current_user.is_superuser:
        invoice_query = invoice_query.filter(SRMInvoice.organization_id == org_id)
        invoice_draft_query = invoice_draft_query.filter(SRMInvoiceDraft.organization_id == org_id)
        contract_query = contract_query.filter(SRMContract.organization_id == org_id)
        billing_plan_query = billing_plan_query.filter(SRMBillingPlan.organization_id == org_id)
        revenue_query = revenue_query.filter(SRMRevenueEvent.organization_id == org_id)
        snapshot_query = snapshot_query.filter(SRMProfitabilitySnapshot.organization_id == org_id)
    if engagement_ids:
        billing_plan_query = billing_plan_query.filter(SRMBillingPlan.engagement_id.in_(engagement_ids))
        snapshot_query = snapshot_query.filter((SRMProfitabilitySnapshot.engagement_id.in_(engagement_ids)) | (SRMProfitabilitySnapshot.engagement_id == None))
    elif not current_user.is_superuser:
        billing_plan_query = billing_plan_query.filter(SRMBillingPlan.engagement_id == None)

    total_invoiced = _decimal(invoice_query.with_entities(func.coalesce(func.sum(SRMInvoice.total_amount), 0)).scalar())
    total_collected = _decimal(invoice_query.with_entities(func.coalesce(func.sum(SRMInvoice.paid_amount), 0)).scalar())
    outstanding = _decimal(invoice_query.with_entities(func.coalesce(func.sum(SRMInvoice.balance_amount), 0)).scalar())
    overdue = _decimal(invoice_query.filter(SRMInvoice.balance_amount > 0, SRMInvoice.due_date < today).with_entities(func.coalesce(func.sum(SRMInvoice.balance_amount), 0)).scalar())
    gross_margin = _decimal(snapshot_query.with_entities(func.coalesce(func.sum(SRMProfitabilitySnapshot.gross_margin_amount), 0)).scalar())
    cash_margin = _decimal(snapshot_query.with_entities(func.coalesce(func.sum(SRMProfitabilitySnapshot.cash_margin_amount), 0)).scalar())

    recent_orders = sales_order_query(db, current_user).order_by(SRMSalesOrder.created_at.desc()).limit(5).all()
    recent_invoices = invoice_query.order_by(SRMInvoice.created_at.desc()).limit(5).all()
    overdue_invoices = invoice_query.filter(SRMInvoice.balance_amount > 0, SRMInvoice.due_date < today).order_by(SRMInvoice.due_date.asc()).limit(5).all()

    revenue_rows = revenue_query.order_by(SRMRevenueEvent.recognized_on.desc(), SRMRevenueEvent.created_at.desc()).limit(12).all()
    revenue_trend = [
        {
            "date": item.recognized_on.isoformat() if item.recognized_on else None,
            "event_type": item.event_type,
            "amount": float(_decimal(item.amount)),
            "currency": item.currency,
        }
        for item in reversed(revenue_rows)
    ]
    collection_alerts = [
        _serialize(item) | {"overdue_days": (today - item.due_date).days if item.due_date else None}
        for item in overdue_invoices
    ]
    linked_crm_orders = sales_order_query(db, current_user).filter(SRMSalesOrder.crm_deal_id != None).count()
    linked_pms_engagements = engagement_query(db, current_user).filter(SRMEngagement.pms_project_id != None).count()

    payload = {
        "total_sales_orders": _count_query(sales_orders),
        "pending_approvals": sales_order_query(db, current_user).filter(SRMSalesOrder.status == "pending_approval").count(),
        "confirmed_sales_orders": sales_order_query(db, current_user).filter(SRMSalesOrder.status == "confirmed").count(),
        "active_contracts": contract_query.filter(SRMContract.status == "active").count(),
        "active_engagements": engagement_query(db, current_user).filter(SRMEngagement.status.in_(["created", "project_pending", "project_created", "delivery_in_progress", "billing_in_progress"])).count(),
        "active_billing_plans": billing_plan_query.filter(SRMBillingPlan.status == "active").count(),
        "invoice_drafts_pending": invoice_draft_query.filter(SRMInvoiceDraft.status.in_(["draft", "pending_approval"])).count(),
        "approved_invoices": invoice_query.filter(SRMInvoice.status == "approved").count(),
        "sent_invoices": invoice_query.filter(SRMInvoice.status.in_(["sent", "partially_paid", "paid", "overdue"])).count(),
        "total_invoiced_value": float(total_invoiced),
        "total_collected_value": float(total_collected),
        "outstanding_value": float(outstanding),
        "overdue_value": float(overdue),
        "collection_risk": "high" if overdue > 0 else ("watch" if outstanding > 0 else "normal"),
        "gross_margin": float(gross_margin),
        "cash_margin": float(cash_margin),
        "recent_sales_orders": [_serialize(item) for item in recent_orders],
        "recent_invoices": [_invoice_payload(item) for item in recent_invoices],
        "collection_alerts": collection_alerts,
        "revenue_trend": revenue_trend,
        "profitability_summary": {
            "gross_margin": float(gross_margin),
            "cash_margin": float(cash_margin),
            "margin_status": "at_risk" if gross_margin < 0 or overdue > 0 else "healthy",
        },
        "linked_activity_summary": {
            "crm_linked_sales_orders": linked_crm_orders,
            "pms_linked_engagements": linked_pms_engagements,
            "sales_order_ids": sales_order_ids[:20],
            "engagement_ids": engagement_ids[:20],
        },
        "crm_pms_activity_summary": {
            "crm_linked_sales_orders": linked_crm_orders,
            "pms_linked_engagements": linked_pms_engagements,
        },
    }
    payload.update({
        "sales_order_count": payload["total_sales_orders"],
        "engagement_count": _count_query(engagements),
        "invoice_total": payload["total_invoiced_value"],
        "collected_total": payload["total_collected_value"],
        "outstanding_total": payload["outstanding_value"],
    })
    return payload


def _find_customer_id_for_360(
    db: Session,
    current_user: User,
    customer_id: int | None = None,
    crm_deal_id: int | None = None,
    sales_order_id: int | None = None,
    engagement_id: int | None = None,
    q: str | None = None,
) -> int | None:
    if customer_id is not None:
        return customer_id
    order = None
    engagement = None
    if sales_order_id is not None:
        order = sales_order_query(db, current_user).filter(SRMSalesOrder.id == sales_order_id).first()
    if engagement_id is not None:
        engagement = engagement_query(db, current_user).filter(SRMEngagement.id == engagement_id).first()
    if crm_deal_id is not None:
        order = sales_order_query(db, current_user).filter(SRMSalesOrder.crm_deal_id == crm_deal_id).first()
        engagement = engagement or engagement_query(db, current_user).filter(SRMEngagement.crm_deal_id == crm_deal_id).first()
    if q:
        value = q.strip()
        if value.isdigit():
            numeric = int(value)
            order = order or sales_order_query(db, current_user).filter((SRMSalesOrder.id == numeric) | (SRMSalesOrder.customer_id == numeric) | (SRMSalesOrder.crm_deal_id == numeric)).first()
            engagement = engagement or engagement_query(db, current_user).filter((SRMEngagement.id == numeric) | (SRMEngagement.customer_id == numeric) | (SRMEngagement.crm_deal_id == numeric)).first()
            if order and order.customer_id:
                return order.customer_id
            if engagement and engagement.customer_id:
                return engagement.customer_id
            return numeric
        like = f"%{value}%"
        order = order or sales_order_query(db, current_user).filter((SRMSalesOrder.order_number.ilike(like)) | (SRMSalesOrder.title.ilike(like))).first()
        engagement = engagement or engagement_query(db, current_user).filter((SRMEngagement.engagement_number.ilike(like)) | (SRMEngagement.name.ilike(like))).first()
        contract = db.query(SRMContract).filter(SRMContract.deleted_at == None, (SRMContract.contract_number.ilike(like)) | (SRMContract.title.ilike(like))).first()
        invoice = db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None, SRMInvoice.invoice_number.ilike(like)).first()
        for item in (order, engagement, contract, invoice):
            if item and getattr(item, "customer_id", None) is not None:
                return item.customer_id
    if order and order.customer_id:
        return order.customer_id
    if engagement and engagement.customer_id:
        return engagement.customer_id
    return None


def _customer_360_payload(db: Session, current_user: User, customer_id: int | None, filters: dict) -> dict:
    if customer_id is None:
        return {
            "matched": False,
            "filters": filters,
            "customer_id": None,
            "message": "No matching SRM customer record found.",
            "crm_references": {},
            "sales_orders": [],
            "contracts": [],
            "engagements": [],
            "billing_plans": [],
            "invoices": [],
            "receipts": [],
            "outstanding_amount": 0,
            "aging": None,
            "collection_reminders": [],
            "profitability": [],
            "pms_projects": [],
            "timeline": [],
            "audit_trail": [],
        }

    orders = sales_order_query(db, current_user).filter(SRMSalesOrder.customer_id == customer_id).all()
    engagements = engagement_query(db, current_user).filter(SRMEngagement.customer_id == customer_id).all()
    engagement_ids = [item.id for item in engagements]
    order_ids = [item.id for item in orders]
    contracts = db.query(SRMContract).filter(SRMContract.customer_id == customer_id, SRMContract.deleted_at == None).all()
    billing_plans = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id.in_(engagement_ids)).all() if engagement_ids else []
    invoices = db.query(SRMInvoice).filter(SRMInvoice.customer_id == customer_id, SRMInvoice.deleted_at == None).all()
    receipts = db.query(SRMReceipt).filter(SRMReceipt.customer_id == customer_id).all()
    reminders = db.query(SRMCollectionReminder).filter(SRMCollectionReminder.customer_id == customer_id).order_by(SRMCollectionReminder.created_at.desc()).limit(20).all()
    aging = db.query(SRMCustomerAging).filter(SRMCustomerAging.organization_id == _org(current_user), SRMCustomerAging.customer_id == customer_id).first()
    profitability_rows = db.query(SRMProfitabilitySnapshot).filter(SRMProfitabilitySnapshot.customer_id == customer_id).order_by(SRMProfitabilitySnapshot.snapshot_at.desc()).limit(20).all()
    audits = []
    if order_ids:
        audits.extend(db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "sales_order", SRMAuditLog.entity_id.in_(order_ids)).order_by(SRMAuditLog.created_at.desc()).limit(20).all())
    if engagement_ids:
        audits.extend(db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "engagement", SRMAuditLog.entity_id.in_(engagement_ids)).order_by(SRMAuditLog.created_at.desc()).limit(20).all())
    pms_projects = []
    project_ids = [item.pms_project_id for item in engagements if item.pms_project_id]
    if project_ids:
        try:
            from app.apps.project_management.models import PMSProject

            pms_projects = db.query(PMSProject).filter(PMSProject.id.in_(project_ids), PMSProject.deleted_at == None).all()
        except Exception:
            pms_projects = []

    outstanding = sum(_decimal(item.balance_amount) for item in invoices)
    crm_references = {
        "crm_deal_ids": sorted({item.crm_deal_id for item in [*orders, *engagements] if item.crm_deal_id}),
        "crm_quote_ids": sorted({item.crm_quote_id for item in [*orders, *engagements] if item.crm_quote_id}),
        "crm_company_ids": sorted({item.crm_company_id for item in orders if item.crm_company_id}),
        "crm_contact_ids": sorted({item.crm_contact_id for item in orders if item.crm_contact_id}),
    }
    timeline = sorted(
        [_serialize(item) | {"type": "audit"} for item in audits]
        + [_serialize(item) | {"type": "sales_order"} for item in orders]
        + [_serialize(item) | {"type": "invoice"} for item in invoices],
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )[:30]
    return {
        "matched": bool(orders or engagements or contracts or invoices or receipts),
        "filters": filters,
        "customer_id": customer_id,
        "crm_references": crm_references,
        "sales_orders": [_serialize(item) for item in orders],
        "contracts": [_serialize(item) for item in contracts],
        "engagements": [_serialize(item) for item in engagements],
        "billing_plans": [_serialize(item) for item in billing_plans],
        "invoices": [_invoice_payload(item) for item in invoices],
        "receipts": [_serialize(item) for item in receipts],
        "outstanding_amount": float(outstanding),
        "aging": _serialize(aging),
        "collection_reminders": [_serialize(item) for item in reminders],
        "profitability": [_profitability_payload(item) for item in profitability_rows],
        "pms_projects": [_serialize(item) for item in pms_projects],
        "timeline": timeline,
        "audit_trail": [_serialize(item) for item in audits],
    }


@router.get("/dashboard")
def srm_dashboard(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_profitability_view", "srm_invoice_view", "srm_collection_view", "srm_admin"))):
    return _dashboard_payload(db, current_user)


@router.get("/customer-360")
def customer_360_search(
    customer_id: int | None = Query(default=None),
    crm_deal_id: int | None = Query(default=None),
    sales_order_id: int | None = Query(default=None),
    engagement_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("srm_view", "srm_invoice_view", "srm_collection_view", "srm_profitability_view", "srm_admin")),
):
    filters = {"customer_id": customer_id, "crm_deal_id": crm_deal_id, "sales_order_id": sales_order_id, "engagement_id": engagement_id, "q": q}
    resolved_customer_id = _find_customer_id_for_360(db, current_user, customer_id, crm_deal_id, sales_order_id, engagement_id, q)
    return _customer_360_payload(db, current_user, resolved_customer_id, filters)


@router.get("/customer-360/{customer_id}")
def customer_360(customer_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_invoice_view", "srm_collection_view", "srm_admin"))):
    return _customer_360_payload(db, current_user, customer_id, {"customer_id": customer_id})


@router.get("/reports/dashboard")
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_profitability_view", "srm_admin"))):
    return _dashboard_payload(db, current_user)


@router.get("/reports/lead-to-cash")
def lead_to_cash_report(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_profitability_view", "srm_admin"))):
    orders = db.query(SRMSalesOrder).filter(SRMSalesOrder.deleted_at == None).count()
    engagements = db.query(SRMEngagement).filter(SRMEngagement.deleted_at == None).count()
    invoices = db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None).count()
    receipts = db.query(SRMReceipt).count()
    return {"crm_won_to_sales_order": orders, "sales_order_to_engagement": engagements, "engagement_to_invoice": invoices, "invoice_to_collection": receipts}


@router.get("/settings")
def list_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_view", "srm_settings_manage", "srm_admin"))):
    return [_serialize(item) for item in db.query(SRMSetting).order_by(SRMSetting.key).all()]


@router.put("/settings/{key}")
def upsert_setting(key: str, data: SRMSettingUpsert, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("srm_settings_manage", "srm_admin"))):
    org_id = _org(current_user)
    item = db.query(SRMSetting).filter(SRMSetting.organization_id == org_id, SRMSetting.key == key).first()
    if not item:
        item = SRMSetting(organization_id=org_id, key=key)
        db.add(item)
    item.value_json = data.value_json
    item.updated_by = current_user.id
    _audit(db, current_user, "setting", item.id, "upserted", after={"key": key})
    db.commit()
    db.refresh(item)
    return _serialize(item)
