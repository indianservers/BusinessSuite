"""Plan fulfillment hooks in the existing sales and receipt transaction."""
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from app.shared.offering_contracts import Plan, offering_kind


def prepare_plan_line(product, metadata, buyer_id, quantity):
    if offering_kind(product) == "bundle":
        raise HTTPException(503, "Bundle checkout requires component inventory, tax and refund allocation support")
    if offering_kind(product) not in {"membership", "subscription"}:
        return metadata
    if not buyer_id:
        raise HTTPException(422, "Choose a registered customer for a membership or subscription")
    if Decimal(str(quantity)) != 1:
        raise HTTPException(422, "Add each customer plan as a separate line with quantity one")
    plan = Plan.model_validate((product.metadata_json or {}).get("plan") or {})
    start = metadata.get("plan_start_date")
    if start:
        try:
            start = date.fromisoformat(start)
        except (ValueError, TypeError):
            raise HTTPException(422, "Plan start date must be an ISO date")
    if plan.activation == "selected_date" and not start:
        raise HTTPException(422, "Select the plan activation date")
    beneficiaries = metadata.get("plan_beneficiaries", [])
    if not isinstance(beneficiaries, list) or len(beneficiaries) > plan.beneficiary_limit or any(type(v) is not int or v <= 0 for v in beneficiaries):
        raise HTTPException(422, "Invalid plan beneficiaries")
    return {**metadata, "offering_kind": offering_kind(product), "plan_snapshot": plan.model_dump(mode="json"),
        "plan_start_date": start.isoformat() if start else None, "plan_beneficiaries": beneficiaries}


def fulfill_paid_invoice(db, user, invoice):
    """Receipt retries use stable order/line keys; approval remains pending."""
    from app.apps.srm.models import SRMSalesOrder, SRMProduct
    from app.shared.plan_engine import issue
    if invoice.status != "paid" or not invoice.sales_order_id:
        return
    order = db.query(SRMSalesOrder).filter_by(id=invoice.sales_order_id, organization_id=invoice.organization_id).first()
    if not order:
        return
    for line in order.lines:
        metadata = line.metadata_json or {}
        if metadata.get("offering_kind") not in {"membership", "subscription"}:
            continue
        if db.info.get("business_pack_scope") is not None:
            raise HTTPException(503, "Plan fulfillment requires native context enrollment")
        product = db.query(SRMProduct).filter_by(id=line.product_id, organization_id=invoice.organization_id).first()
        if not product or offering_kind(product) != metadata["offering_kind"]:
            raise HTTPException(409, "Purchased plan master is unavailable")
        start = date.fromisoformat(metadata["plan_start_date"]) if metadata.get("plan_start_date") else None
        issue(db, user, "srm", product.id, metadata["offering_kind"], order.customer_id,
            f"sales-order:{order.id}:line:{line.id}", start, metadata.get("plan_beneficiaries", []),
            configuration=metadata["plan_snapshot"], price_snapshot={"price": str(line.unit_price), "currency": order.currency,
                "tax": str((metadata.get("tax_snapshot") or {}).get("gst_rate", product.gst_rate)), "source_line_id": line.id})
