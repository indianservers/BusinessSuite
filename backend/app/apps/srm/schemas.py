from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class SRMSalesOrderLineInput(BaseModel):
    source_quote_line_id: int | None = None
    product_id: int | None = None
    item_code: str | None = None
    description: str | None = None
    service_type: str = "service"
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None
    pms_template_key: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMSalesOrderCreate(BaseModel):
    order_number: str | None = None
    title: str = Field(..., min_length=1, max_length=220)
    crm_deal_id: int | None = None
    crm_quote_id: int | None = None
    crm_company_id: int | None = None
    crm_contact_id: int | None = None
    customer_id: int | None = None
    assigned_user_id: int | None = None
    currency: str = "INR"
    subtotal: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal | None = None
    expected_start_date: date | None = None
    expected_end_date: date | None = None
    terms: str | None = None
    metadata_json: dict[str, Any] | None = None
    lines: list[SRMSalesOrderLineInput] = []


class SRMSalesOrderUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    assigned_user_id: int | None = None
    subtotal: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    terms: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMSalesOrderLineUpdate(BaseModel):
    source_quote_line_id: int | None = None
    product_id: int | None = None
    item_code: str | None = None
    description: str | None = None
    service_type: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    line_total: Decimal | None = None
    pms_template_key: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMContractCreate(BaseModel):
    contract_number: str | None = None
    sales_order_id: int | None = None
    customer_id: int | None = None
    title: str
    contract_type: str = "services"
    effective_date: date | None = None
    expiry_date: date | None = None
    contract_value: Decimal = Decimal("0")
    currency: str = "INR"
    terms: str | None = None


class SRMContractUpdate(BaseModel):
    sales_order_id: int | None = None
    customer_id: int | None = None
    title: str | None = None
    contract_type: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    contract_value: Decimal | None = None
    currency: str | None = None
    terms: str | None = None


class SRMEngagementCreate(BaseModel):
    engagement_number: str | None = None
    sales_order_id: int | None = None
    contract_id: int | None = None
    customer_id: int | None = None
    crm_deal_id: int | None = None
    crm_quote_id: int | None = None
    assigned_user_id: int | None = None
    project_manager_user_id: int | None = None
    name: str
    billing_type: str = "fixed_fee"
    budget_amount: Decimal = Decimal("0")
    currency: str = "INR"
    planned_start_date: date | None = None
    planned_end_date: date | None = None


class SRMEngagementUpdate(BaseModel):
    sales_order_id: int | None = None
    contract_id: int | None = None
    customer_id: int | None = None
    crm_deal_id: int | None = None
    crm_quote_id: int | None = None
    pms_project_id: int | None = None
    assigned_user_id: int | None = None
    project_manager_user_id: int | None = None
    name: str | None = None
    status: str | None = None
    billing_type: str | None = None
    budget_amount: Decimal | None = None
    currency: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None


class SRMEngagementLinkCreate(BaseModel):
    linked_module: str
    linked_entity_type: str
    linked_entity_id: int
    label: str | None = None


class SRMBillingMilestoneInput(BaseModel):
    name: str
    due_date: date | None = None
    amount: Decimal = Decimal("0")
    metadata_json: dict[str, Any] | None = None


class SRMBillingPlanCreate(BaseModel):
    engagement_id: int
    name: str
    billing_type: str = "fixed_fee"
    currency: str = "INR"
    total_amount: Decimal = Decimal("0")
    recurrence_rule: str | None = None
    milestones: list[SRMBillingMilestoneInput] = []


class SRMBillingPlanUpdate(BaseModel):
    name: str | None = None
    billing_type: str | None = None
    currency: str | None = None
    total_amount: Decimal | None = None
    recurrence_rule: str | None = None


class SRMInvoiceLineInput(BaseModel):
    source_type: str | None = None
    source_id: int | None = None
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None


class SRMInvoicePatch(BaseModel):
    status: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    subtotal: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None


class SRMTimeLogInvoiceRequest(BaseModel):
    project_id: int | None = None
    engagement_id: int | None = None
    time_log_ids: list[int] = []
    hourly_rate: Decimal = Decimal("1000")
    currency: str = "INR"


class SRMManualInvoiceCreate(BaseModel):
    sales_order_id: int | None = None
    engagement_id: int | None = None
    customer_id: int | None = None
    currency: str = "INR"
    issue_date: date | None = None
    due_date: date | None = None
    lines: list[SRMInvoiceLineInput] = []


class SRMReceiptCreate(BaseModel):
    receipt_number: str | None = None
    customer_id: int | None = None
    receipt_date: date | None = None
    payment_method: str = "bank_transfer"
    reference_number: str | None = None
    currency: str = "INR"
    amount: Decimal = Decimal("0")


class SRMReceiptAllocationRequest(BaseModel):
    invoice_id: int
    amount: Decimal


class SRMReminderRequest(BaseModel):
    customer_id: int | None = None
    invoice_id: int | None = None
    message: str | None = None


class SRMWriteOffRequest(BaseModel):
    reason: str | None = None
    amount: Decimal | None = None


class SRMSettingUpsert(BaseModel):
    key: str
    value_json: dict[str, Any] | list[Any] | str | int | float | bool | None


class SRMResponse(BaseModel):
    id: int

    class Config:
        from_attributes = True
