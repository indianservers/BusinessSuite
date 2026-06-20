from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class SRMPOSSessionCreate(BaseModel):
    branch: str = "Main Branch"
    register_name: str = "Main POS Register"
    opening_cash: Decimal = Decimal("0")
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMPOSCashMovementCreate(BaseModel):
    session_id: int
    movement_type: str = "cash_in"
    amount: Decimal
    reason: str | None = None


class SRMPOSCashierClosingCreate(BaseModel):
    session_id: int
    counted_cash: Decimal
    notes: str | None = None


class SRMPOSHeldBillCreate(BaseModel):
    session_id: int | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    notes: str | None = None
    cart_json: list[dict[str, Any]]
    amount: Decimal = Decimal("0")
    item_count: int = 0


class SRMPOSReturnLineCreate(BaseModel):
    sales_order_line_id: int | None = None
    product_id: int | None = None
    warehouse_id: int | None = None
    item_code: str | None = None
    description: str | None = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None
    condition: str = "sellable"
    restock: bool = True
    metadata_json: dict[str, Any] | None = None


class SRMPOSReturnCreate(BaseModel):
    sales_order_id: int | None = None
    order_number: str | None = None
    session_id: int | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    refund_method: str = "cash"
    refund_status: str = "refunded"
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None
    lines: list[SRMPOSReturnLineCreate]


class SRMProductCategoryCreate(BaseModel):
    parent_category_id: int | None = None
    category_code: str = Field(..., min_length=1, max_length=80)
    category_name: str = Field(..., min_length=1, max_length=180)
    description: str | None = None
    active: bool = True


class SRMWarehouseCreate(BaseModel):
    warehouse_code: str = Field(..., min_length=1, max_length=80)
    warehouse_name: str = Field(..., min_length=1, max_length=180)
    branch: str | None = None
    address: str | None = None
    active: bool = True


class SRMProductCreate(BaseModel):
    category_id: int | None = None
    default_warehouse_id: int | None = None
    sku: str = Field(..., min_length=1, max_length=80)
    item_name: str = Field(..., min_length=1, max_length=220)
    barcode: str | None = None
    description: str | None = None
    product_type: str = "stock"
    category_name: str | None = None
    unit_code: str = "PCS"
    hsn_code: str | None = None
    gst_rate: Decimal = Decimal("0")
    purchase_rate: Decimal = Decimal("0")
    sales_rate: Decimal = Decimal("0")
    mrp: Decimal = Decimal("0")
    current_quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    max_stock: Decimal = Decimal("0")
    track_inventory: bool = True
    batch_tracking: bool = False
    serial_tracking: bool = False
    expiry_tracking: bool = False
    active: bool = True
    metadata_json: dict[str, Any] | None = None


class SRMProductUpdate(BaseModel):
    category_id: int | None = None
    default_warehouse_id: int | None = None
    item_name: str | None = None
    barcode: str | None = None
    description: str | None = None
    product_type: str | None = None
    category_name: str | None = None
    unit_code: str | None = None
    hsn_code: str | None = None
    gst_rate: Decimal | None = None
    purchase_rate: Decimal | None = None
    sales_rate: Decimal | None = None
    mrp: Decimal | None = None
    reorder_level: Decimal | None = None
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None
    track_inventory: bool | None = None
    batch_tracking: bool | None = None
    serial_tracking: bool | None = None
    expiry_tracking: bool | None = None
    active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class SRMOpeningStockCreate(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: Decimal
    rate: Decimal = Decimal("0")
    movement_date: date | None = None
    reference_number: str | None = None
    notes: str | None = None


class SRMStockMovementCreate(BaseModel):
    product_id: int
    warehouse_id: int
    movement_type: str = "stock_in"
    quantity: Decimal
    rate: Decimal = Decimal("0")
    movement_date: date | None = None
    reference_number: str | None = None
    notes: str | None = None


class SRMStockTransferCreate(BaseModel):
    product_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: Decimal
    rate: Decimal = Decimal("0")
    movement_date: date | None = None
    reference_number: str | None = None
    notes: str | None = None


class SRMStockAdjustmentCreate(BaseModel):
    product_id: int
    warehouse_id: int
    quantity_in: Decimal = Decimal("0")
    quantity_out: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    reason: str | None = None
    movement_date: date | None = None
    reference_number: str | None = None
    notes: str | None = None


class SRMPurchaseOrderLineCreate(BaseModel):
    product_id: int | None = None
    warehouse_id: int | None = None
    item_code: str | None = None
    description: str | None = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None
    metadata_json: dict[str, Any] | None = None


class SRMPurchaseOrderCreate(BaseModel):
    po_number: str | None = None
    vendor_id: int | None = None
    vendor_name: str | None = None
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    lines: list[SRMPurchaseOrderLineCreate]


class SRMGoodsReceiptLineCreate(BaseModel):
    purchase_order_line_id: int | None = None
    product_id: int | None = None
    warehouse_id: int | None = None
    item_code: str | None = None
    description: str | None = None
    quantity: Decimal = Decimal("1")
    accepted_quantity: Decimal | None = None
    rejected_quantity: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None
    metadata_json: dict[str, Any] | None = None


class SRMGoodsReceiptCreate(BaseModel):
    grn_number: str | None = None
    purchase_order_id: int | None = None
    vendor_id: int | None = None
    vendor_name: str | None = None
    receipt_date: date | None = None
    reference_number: str | None = None
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    lines: list[SRMGoodsReceiptLineCreate]


class SRMPriceListLineCreate(BaseModel):
    product_id: int
    min_quantity: Decimal = Decimal("1")
    price: Decimal
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    tax_inclusive: bool = False
    active: bool = True
    metadata_json: dict[str, Any] | None = None


class SRMPriceListCreate(BaseModel):
    price_list_code: str | None = None
    price_list_name: str = Field(..., min_length=1, max_length=180)
    channel: str = "retail"
    customer_type: str = "cash"
    currency: str = "INR"
    effective_from: date | None = None
    effective_to: date | None = None
    priority: int = 100
    active: bool = True
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    lines: list[SRMPriceListLineCreate]


class SRMPriceLookupRequest(BaseModel):
    product_ids: list[int]
    channel: str | None = None
    customer_type: str | None = None
    price_date: date | None = None
    quantity: Decimal = Decimal("1")


class SRMInventoryBatchCreate(BaseModel):
    product_id: int
    warehouse_id: int | None = None
    batch_number: str = Field(..., min_length=1, max_length=120)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    received_date: date | None = None
    quantity: Decimal = Decimal("0")
    available_quantity: Decimal | None = None
    unit_cost: Decimal = Decimal("0")
    status: str = "available"
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMSerialNumberCreate(BaseModel):
    product_id: int
    warehouse_id: int | None = None
    batch_id: int | None = None
    serial_number: str = Field(..., min_length=1, max_length=160)
    status: str = "available"
    received_date: date | None = None
    reference_number: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMBOMComponentCreate(BaseModel):
    component_product_id: int
    warehouse_id: int | None = None
    quantity: Decimal = Decimal("1")
    scrap_percent: Decimal = Decimal("0")
    unit_cost: Decimal = Decimal("0")
    line_total: Decimal | None = None
    metadata_json: dict[str, Any] | None = None


class SRMBillOfMaterialCreate(BaseModel):
    bom_number: str | None = None
    bom_name: str = Field(..., min_length=1, max_length=180)
    finished_product_id: int
    output_quantity: Decimal = Decimal("1")
    status: str = "active"
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    components: list[SRMBOMComponentCreate]


class SRMProductionOrderCreate(BaseModel):
    production_number: str | None = None
    bom_id: int
    warehouse_id: int | None = None
    planned_quantity: Decimal = Decimal("1")
    order_date: date | None = None
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None


class SRMProductionPostRequest(BaseModel):
    completed_quantity: Decimal | None = None
    warehouse_id: int | None = None
    completed_at: datetime | None = None


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

    model_config = ConfigDict(from_attributes=True)
