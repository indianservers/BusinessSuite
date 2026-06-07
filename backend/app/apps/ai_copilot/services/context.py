from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.apps.crm.models import CRMAccount, CRMCompany, CRMContact, CRMCustomField, CRMCustomFieldValue, CRMDeal, CRMLead, CRMQuotation
from app.apps.srm.access import engagement_query, sales_order_query
from app.apps.srm.models import SRMBillingPlan, SRMCollectionReminder, SRMEngagement, SRMInvoice, SRMSalesOrder
from app.models.user import User


SENSITIVE_FIELD_PARTS = {
    "password",
    "secret",
    "token",
    "api_key",
    "key_reference",
    "metadata",
    "notes",
    "address",
    "bank",
    "salary",
    "pan",
    "aadhaar",
    "ssn",
    "tax_registration",
}

ALLOW_FIELDS: dict[str, set[str]] = {
    "lead": {"id", "full_name", "company_name", "source", "status", "rating", "lead_score", "lead_score_label", "industry", "city", "estimated_value", "expected_close_date", "next_follow_up_at", "owner_user_id"},
    "contact": {"id", "full_name", "job_title", "department", "lifecycle_stage", "source", "company_name", "industry", "city", "status", "next_follow_up_at", "owner_user_id"},
    "account": {"id", "account_name", "legal_name", "industry", "country", "account_status", "owner_id"},
    "company": {"id", "name", "industry", "city", "country", "account_type", "status", "annual_revenue", "owner_user_id"},
    "deal": {"id", "name", "description", "amount", "currency", "probability", "expected_revenue", "expected_close_date", "status", "lead_source", "source", "next_follow_up_at", "owner_user_id", "company_id", "contact_id"},
    "quote": {"id", "quote_number", "status", "issue_date", "expiry_date", "subtotal", "discount_amount", "tax_amount", "total_amount", "deal_id", "company_id", "contact_id"},
    "quotation": {"id", "quote_number", "status", "issue_date", "expiry_date", "subtotal", "discount_amount", "tax_amount", "total_amount", "deal_id", "company_id", "contact_id"},
    "sales_order": {"id", "order_number", "status", "crm_deal_id", "crm_quote_id", "customer_id", "title", "currency", "subtotal", "discount_amount", "tax_amount", "total_amount", "assigned_user_id"},
    "engagement": {"id", "engagement_number", "sales_order_id", "contract_id", "customer_id", "crm_deal_id", "crm_quote_id", "pms_project_id", "name", "status", "billing_type", "budget_amount", "currency", "assigned_user_id", "project_manager_user_id"},
    "billing_plan": {"id", "engagement_id", "name", "billing_type", "status", "currency", "total_amount"},
    "invoice": {"id", "invoice_number", "sales_order_id", "engagement_id", "customer_id", "status", "issue_date", "due_date", "currency", "total_amount", "paid_amount", "balance_amount"},
    "collection": {"id", "customer_id", "invoice_id", "status", "reminder_type", "scheduled_at", "sent_at", "message"},
}

MODEL_BY_RECORD_TYPE = {
    "lead": CRMLead,
    "leads": CRMLead,
    "contact": CRMContact,
    "contacts": CRMContact,
    "account": CRMCompany,
    "accounts": CRMCompany,
    "company": CRMCompany,
    "companies": CRMCompany,
    "crm_account": CRMAccount,
    "deal": CRMDeal,
    "deals": CRMDeal,
    "quote": CRMQuotation,
    "quotation": CRMQuotation,
    "quotations": CRMQuotation,
    "sales_order": SRMSalesOrder,
    "sales-orders": SRMSalesOrder,
    "engagement": SRMEngagement,
    "engagements": SRMEngagement,
    "billing_plan": SRMBillingPlan,
    "billing-plans": SRMBillingPlan,
    "invoice": SRMInvoice,
    "invoices": SRMInvoice,
    "collection": SRMCollectionReminder,
    "collections": SRMCollectionReminder,
}


def user_permissions(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def has_any(user: User, *permissions: str) -> bool:
    names = user_permissions(user)
    return "*" in names or bool(names.intersection(permissions))


def _record_type(value: str | None) -> str:
    return (value or "record").strip().lower().replace(" ", "_")


def _module_for(record_type: str, explicit: str | None) -> str:
    if explicit:
        return explicit.strip().lower()
    if record_type in {"lead", "leads", "contact", "contacts", "account", "accounts", "company", "companies", "crm_account", "deal", "deals", "quote", "quotation", "quotations"}:
        return "crm"
    if record_type in {"sales_order", "sales-orders", "engagement", "engagements", "billing_plan", "billing-plans", "invoice", "invoices", "collection", "collections"}:
        return "srm"
    return "analytics"


def _assert_module_permission(user: User, module_name: str, record_type: str) -> None:
    if module_name == "crm" and not has_any(user, "crm_view", "crm_manage", "crm_admin"):
        raise HTTPException(status_code=403, detail="AI cannot access CRM records without CRM permission")
    if module_name == "srm":
        if record_type in {"invoice", "invoices"} and not has_any(user, "srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_admin"):
            raise HTTPException(status_code=403, detail="AI cannot access SRM invoice records without invoice permission")
        if record_type in {"collection", "collections"} and not has_any(user, "srm_collection_view", "srm_collection_create", "srm_admin"):
            raise HTTPException(status_code=403, detail="AI cannot access collection records without collection permission")
        if not has_any(user, "srm_view", "srm_manage", "srm_admin", "srm_invoice_view", "srm_collection_view", "srm_profitability_view"):
            raise HTTPException(status_code=403, detail="AI cannot access SRM records without SRM permission")
    if module_name == "analytics" and not has_any(user, "analytics_view", "analytics_report_builder", "analytics_manage", "analytics_admin"):
        raise HTTPException(status_code=403, detail="AI cannot access analytics without analytics permission")


def _is_sensitive(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(part in lowered for part in SENSITIVE_FIELD_PARTS)


def _safe_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return "[redacted-structured-value]"
    return value


def _safe_fields(record: Any, record_type: str) -> dict[str, Any]:
    allowed = ALLOW_FIELDS.get(record_type.replace("s", ""), ALLOW_FIELDS.get(record_type, set()))
    fields = {}
    for column in sa_inspect(record.__class__).columns:
        name = column.key
        if allowed and name not in allowed:
            continue
        if _is_sensitive(name):
            continue
        value = getattr(record, name)
        if value is not None:
            fields[name] = _safe_value(value)
    return fields


def _label(fields: dict[str, Any], record_type: str, record_id: int | None) -> str:
    for key in ("full_name", "name", "title", "quote_number", "order_number", "engagement_number", "invoice_number", "account_name"):
        if fields.get(key):
            return str(fields[key])
    return f"{record_type} #{record_id or '-'}"


def _crm_record_query(db: Session, user: User, model: type):
    query = db.query(model)
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at == None)
    if user.is_superuser or has_any(user, "crm_admin"):
        return query
    owner_field = "owner_user_id" if hasattr(model, "owner_user_id") else ("owner_id" if hasattr(model, "owner_id") else None)
    if has_any(user, "crm_manage") and owner_field:
        return query.filter(getattr(model, owner_field) == user.id)
    if has_any(user, "crm_view"):
        return query
    return query.filter(False)


def _load_record(db: Session, user: User, record_type: str, record_id: int | None):
    model = MODEL_BY_RECORD_TYPE.get(record_type)
    if not model or record_id is None:
        return None
    if model is SRMSalesOrder:
        return sales_order_query(db, user).filter(SRMSalesOrder.id == record_id).first()
    if model is SRMEngagement:
        return engagement_query(db, user).filter(SRMEngagement.id == record_id).first()
    return _crm_record_query(db, user, model).filter(model.id == record_id).first()


def _custom_field_context(db: Session, record_type: str, record_id: int | None) -> dict[str, Any]:
    if not record_id or record_type not in {"lead", "leads", "contact", "contacts", "company", "companies", "account", "accounts", "deal", "deals", "quotation", "quotations"}:
        return {}
    entity = {"lead": "leads", "contact": "contacts", "company": "companies", "account": "companies", "deal": "deals", "quotation": "quotations"}.get(record_type.replace("s", ""), record_type)
    rows = (
        db.query(CRMCustomField, CRMCustomFieldValue)
        .join(CRMCustomFieldValue, CRMCustomFieldValue.custom_field_id == CRMCustomField.id)
        .filter(CRMCustomField.entity == entity, CRMCustomFieldValue.record_id == record_id, CRMCustomField.is_active == True, CRMCustomField.is_visible == True)
        .all()
    )
    output = {}
    for field, value in rows:
        key = field.field_key or field.label
        if _is_sensitive(key):
            continue
        output[key] = _safe_value(value.value_text or value.value_number or value.value_date or value.value_datetime or value.value_boolean)
    return output


def build_secure_context(db: Session, user: User, *, record_type: str | None, record_id: int | None, module_name: str | None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_type = _record_type(record_type)
    module = _module_for(normalized_type, module_name)
    _assert_module_permission(user, module, normalized_type)
    record = _load_record(db, user, normalized_type, record_id)
    if record_id is not None and not record:
        raise HTTPException(status_code=404, detail="AI context record not found or not accessible")
    fields = _safe_fields(record, normalized_type) if record else {}
    custom_fields = _custom_field_context(db, normalized_type, record_id)
    sanitized_data = {}
    for key, value in (data or {}).items():
        if not _is_sensitive(key):
            sanitized_data[key] = _safe_value(value)
    return {
        "module_name": module,
        "record_type": normalized_type,
        "record_id": record_id,
        "label": _label(fields, normalized_type, record_id),
        "fields": fields,
        "custom_fields": custom_fields,
        "input_data": sanitized_data,
        "source_summary": {"field_count": len(fields), "custom_field_count": len(custom_fields), "data_keys": sorted(sanitized_data)},
    }

