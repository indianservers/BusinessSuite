from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FAMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CompanyFinancialSettingsPayload(FAMBaseSchema):
    country_code: str = "IN"
    base_currency: str = "INR"
    gst_enabled: bool = False
    gstin: str | None = None
    legal_name: str | None = None
    trade_name: str | None = None
    pan: str | None = None
    tan: str | None = None
    cin: str | None = None
    registered_address: str | None = None
    state_code: str | None = None
    financial_year_start_month: int = Field(default=4, ge=1, le=12)
    books_start_date: date | None = None
    decimal_places: int = Field(default=2, ge=0, le=4)


class FinancialYearPayload(FAMBaseSchema):
    name: str
    start_date: date
    end_date: date
    status: str = "open"
    is_current: bool = False


class LedgerGroupPayload(FAMBaseSchema):
    parent_group_id: int | None = None
    group_name: str
    group_code: str
    nature: str
    system_group: bool = False
    affects_gross_profit: bool = False
    sequence_order: int = 100
    active: bool = True


class LedgerPayload(FAMBaseSchema):
    ledger_code: str
    ledger_name: str
    ledger_group_id: int
    nature: str | None = None
    ledger_type: str = "general"
    gst_applicable: bool = False
    pan: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    billing_address: str | None = None
    opening_balance_dr: Decimal = Decimal("0")
    opening_balance_cr: Decimal = Decimal("0")
    active: bool = True


class OpeningBalancePayload(FAMBaseSchema):
    financial_year_id: int
    ledger_id: int
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    narration: str | None = None


class CostCenterPayload(FAMBaseSchema):
    code: str
    name: str
    parent_id: int | None = None
    active: bool = True


class BranchPayload(FAMBaseSchema):
    branch_code: str
    branch_name: str
    gstin: str | None = None
    state_code: str | None = None
    address: str | None = None
    active: bool = True


class VoucherTypePayload(FAMBaseSchema):
    voucher_type_code: str
    voucher_type_name: str
    category: str
    numbering_prefix: str
    numbering_sequence: int = Field(default=1, ge=1)
    auto_numbering: bool = True
    active: bool = True
    system_type: bool = False


class VoucherLinePayload(FAMBaseSchema):
    ledger_id: int
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    narration: str | None = None
    cost_center_id: int | None = None
    branch_id: int | None = None
    party_id: int | None = None
    tax_component_id: int | None = None


class VoucherPayload(FAMBaseSchema):
    financial_year_id: int | None = None
    accounting_period_id: int | None = None
    branch_id: int | None = None
    voucher_type_id: int
    voucher_number: str | None = None
    voucher_date: date
    reference_number: str | None = None
    reference_date: date | None = None
    narration: str | None = None
    source_module: str = "fam"
    source_record_type: str | None = None
    source_record_id: str | None = None
    lines: list[VoucherLinePayload] = Field(default_factory=list)


class VoucherUpdatePayload(VoucherPayload):
    status: str | None = None


class VoucherCancelPayload(FAMBaseSchema):
    reason: str


class VoucherClonePayload(FAMBaseSchema):
    voucher_date: date | None = None
    narration: str | None = None


class PartyContactPayload(FAMBaseSchema):
    name: str
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    is_primary: bool = False


class PartyPayload(FAMBaseSchema):
    party_type: str
    crm_account_id: int | None = None
    crm_contact_id: int | None = None
    ledger_id: int | None = None
    party_code: str
    legal_name: str
    trade_name: str | None = None
    pan: str | None = None
    gstin: str | None = None
    registration_type: str = "regular"
    state_code: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    payment_terms_days: int = Field(default=30, ge=0)
    credit_limit: Decimal = Decimal("0")
    opening_balance_dr: Decimal = Decimal("0")
    opening_balance_cr: Decimal = Decimal("0")
    active: bool = True
    create_ledger: bool = False
    contacts: list[PartyContactPayload] = Field(default_factory=list)


class BillReferencePayload(FAMBaseSchema):
    party_id: int
    ledger_id: int | None = None
    voucher_id: int | None = None
    voucher_line_id: int | None = None
    bill_number: str
    bill_date: date
    due_date: date | None = None
    bill_type: str
    original_amount: Decimal
    outstanding_amount: Decimal | None = None
    source_module: str = "fam"
    source_record_type: str | None = None
    source_record_id: str | None = None


class BillAllocationPayload(FAMBaseSchema):
    allocation_date: date
    party_id: int
    from_bill_reference_id: int
    to_bill_reference_id: int
    voucher_id: int | None = None
    allocated_amount: Decimal
    allocation_type: str


class PartyCreditTermPayload(FAMBaseSchema):
    party_id: int
    terms_name: str
    days: int = Field(default=30, ge=0)
    discount_percentage: Decimal = Decimal("0")
    active: bool = True


class PostingRulePayload(FAMBaseSchema):
    source_module: str = "srm"
    transaction_type: str
    debit_ledger_rule_json: dict[str, Any] | None = None
    credit_ledger_rule_json: dict[str, Any] | None = None
    tax_ledger_rule_json: dict[str, Any] | None = None
    roundoff_ledger_id: int | None = None
    active: bool = True


class BankAccountPayload(FAMBaseSchema):
    ledger_id: int
    bank_name: str
    branch_name: str | None = None
    account_number_masked: str
    ifsc: str | None = None
    account_type: str = "current"
    opening_balance: Decimal = Decimal("0")
    active: bool = True


class PaymentModePayload(FAMBaseSchema):
    name: str
    type: str
    default_ledger_id: int | None = None
    active: bool = True


class BankStatementLinePayload(FAMBaseSchema):
    transaction_date: date
    value_date: date | None = None
    description: str
    reference_number: str | None = None
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")


class BankStatementImportPayload(FAMBaseSchema):
    bank_account_id: int
    statement_period_start: date
    statement_period_end: date
    imported_file_name: str = "manual-import.csv"
    file_content: str | None = None
    column_map: dict[str, str] | None = None
    lines: list[BankStatementLinePayload] = Field(default_factory=list)


class BankStatementMatchPayload(FAMBaseSchema):
    statement_line_id: int
    voucher_id: int
    ledger_entry_id: int | None = None
    matched_amount: Decimal | None = None
    confirm: bool = True


class BankStatementIgnoreLinePayload(FAMBaseSchema):
    statement_line_id: int
    reason: str | None = None


class BankChargePostPayload(FAMBaseSchema):
    bank_account_id: int
    expense_ledger_id: int
    amount: Decimal
    charge_date: date
    reference_number: str | None = None
    narration: str = "Bank charges"


class ContraPostPayload(FAMBaseSchema):
    from_ledger_id: int
    to_ledger_id: int
    amount: Decimal
    contra_date: date
    reference_number: str | None = None
    narration: str = "Contra entry"


class GSTRegistrationPayload(FAMBaseSchema):
    gstin: str
    legal_name: str
    trade_name: str | None = None
    state_code: str
    registration_type: str = "regular"
    effective_from: date
    active: bool = True


class GSTRatePayload(FAMBaseSchema):
    rate_name: str
    tax_type: str = "goods"
    cgst_rate: Decimal = Decimal("0")
    sgst_rate: Decimal = Decimal("0")
    igst_rate: Decimal = Decimal("0")
    cess_rate: Decimal = Decimal("0")
    effective_from: date
    effective_to: date | None = None
    active: bool = True


class HSNSACPayload(FAMBaseSchema):
    code: str
    description: str
    type: str
    default_gst_rate_id: int | None = None
    active: bool = True


class GSTCalculationPayload(FAMBaseSchema):
    taxable_value: Decimal
    company_state_code: str
    place_of_supply_state: str
    gst_rate_id: int | None = None
    cgst_rate: Decimal | None = None
    sgst_rate: Decimal | None = None
    igst_rate: Decimal | None = None
    cess_rate: Decimal = Decimal("0")
    supply_type: str = "b2b"
    transaction_type: str = "outward"
    reverse_charge: bool = False
    itc_eligible: bool = False
    exempt_type: str | None = None
    hsn_sac_code: str | None = None
    party_id: int | None = None
    gstin: str | None = None
    voucher_id: int | None = None
    voucher_line_id: int | None = None
    persist: bool = False


class GSTReturnPreparePayload(FAMBaseSchema):
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2000)


class EInvoiceSettingsPayload(FAMBaseSchema):
    provider_name: str | None = None
    api_base_url: str | None = None
    credentials_configured: bool = False
    applicable_from: date | None = None
    applicability_json: dict[str, Any] | None = None
    active: bool = False


class EWayBillSettingsPayload(FAMBaseSchema):
    provider_name: str | None = None
    api_base_url: str | None = None
    credentials_configured: bool = False
    threshold_amount: Decimal = Decimal("50000")
    applicability_json: dict[str, Any] | None = None
    active: bool = False


class PurchaseBillLinePayload(FAMBaseSchema):
    expense_ledger_id: int
    item_id: int | None = None
    description: str
    hsn_sac: str | None = None
    quantity: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    taxable_value: Decimal | None = None
    gst_rate_id: int | None = None
    gst_amount: Decimal = Decimal("0")
    tds_section_id: int | None = None
    tds_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None


class PurchaseBillPayload(FAMBaseSchema):
    vendor_id: int
    bill_number: str
    bill_date: date
    due_date: date | None = None
    gstin: str | None = None
    place_of_supply: str | None = None
    discount_total: Decimal = Decimal("0")
    lines: list[PurchaseBillLinePayload] = Field(default_factory=list)


class ExpenseLinePayload(FAMBaseSchema):
    expense_ledger_id: int
    description: str
    hsn_sac: str | None = None
    taxable_value: Decimal
    gst_rate_id: int | None = None
    gst_amount: Decimal = Decimal("0")
    line_total: Decimal | None = None


class ExpenseClaimPayload(FAMBaseSchema):
    claim_number: str
    claimant_name: str | None = None
    claim_date: date
    payable_ledger_id: int | None = None
    lines: list[ExpenseLinePayload] = Field(default_factory=list)


class TDSSectionPayload(FAMBaseSchema):
    section_code: str
    description: str
    default_rate: Decimal = Decimal("0")
    threshold_amount: Decimal = Decimal("0")
    effective_from: date
    active: bool = True


class TDSRatePayload(FAMBaseSchema):
    section_id: int
    rate: Decimal
    threshold_amount: Decimal = Decimal("0")
    effective_from: date
    effective_to: date | None = None
    active: bool = True


class TDSCalculatePayload(FAMBaseSchema):
    section_id: int
    taxable_amount: Decimal


class VendorPaymentItemPayload(FAMBaseSchema):
    vendor_id: int
    purchase_bill_id: int | None = None
    bill_reference_id: int | None = None
    amount: Decimal


class VendorPaymentPreparePayload(FAMBaseSchema):
    payment_date: date
    bank_ledger_id: int
    items: list[VendorPaymentItemPayload] = Field(default_factory=list)


class InventoryGroupPayload(FAMBaseSchema):
    group_code: str
    group_name: str
    parent_group_id: int | None = None
    description: str | None = None
    active: bool = True


class InventoryUnitPayload(FAMBaseSchema):
    unit_code: str
    unit_name: str
    symbol: str | None = None
    decimal_allowed: bool = True
    active: bool = True


class InventoryWarehousePayload(FAMBaseSchema):
    warehouse_code: str
    warehouse_name: str
    branch_id: int | None = None
    address: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    active: bool = True


class InventoryItemPayload(FAMBaseSchema):
    sku: str
    item_name: str
    stock_group_id: int | None = None
    unit_id: int | None = None
    default_warehouse_id: int | None = None
    inventory_ledger_id: int | None = None
    cogs_ledger_id: int | None = None
    barcode: str | None = None
    description: str | None = None
    hsn_code: str | None = None
    gst_rate_id: int | None = None
    purchase_rate: Decimal = Decimal("0")
    sales_rate: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    max_stock: Decimal = Decimal("0")
    track_inventory: bool = True
    batch_tracking: bool = False
    serial_tracking: bool = False
    expiry_tracking: bool = False
    active: bool = True
    source_app_reference: str | None = None


class InventoryOpeningPayload(FAMBaseSchema):
    opening_number: str | None = None
    opening_date: date
    stock_item_id: int
    warehouse_id: int
    quantity: Decimal
    rate: Decimal = Decimal("0")
    notes: str | None = None


class StockMovementLinePayload(FAMBaseSchema):
    stock_item_id: int
    warehouse_id: int
    quantity_in: Decimal = Decimal("0")
    quantity_out: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    notes: str | None = None


class StockMovementPayload(FAMBaseSchema):
    movement_number: str | None = None
    movement_date: date
    movement_type: str
    reference_number: str | None = None
    narration: str | None = None
    source_module: str = "fam"
    source_record_type: str | None = None
    source_record_id: str | None = None
    lines: list[StockMovementLinePayload] = Field(default_factory=list)


class StockTransferLinePayload(FAMBaseSchema):
    stock_item_id: int
    quantity: Decimal
    rate: Decimal = Decimal("0")
    notes: str | None = None


class StockTransferPayload(FAMBaseSchema):
    transfer_number: str | None = None
    transfer_date: date
    from_warehouse_id: int
    to_warehouse_id: int
    notes: str | None = None
    lines: list[StockTransferLinePayload] = Field(default_factory=list)


class StockAdjustmentLinePayload(FAMBaseSchema):
    stock_item_id: int
    quantity_in: Decimal = Decimal("0")
    quantity_out: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    notes: str | None = None


class StockAdjustmentPayload(FAMBaseSchema):
    adjustment_number: str | None = None
    adjustment_date: date
    warehouse_id: int
    adjustment_type: str = "other"
    reason: str | None = None
    notes: str | None = None
    inventory_ledger_id: int | None = None
    adjustment_ledger_id: int | None = None
    lines: list[StockAdjustmentLinePayload] = Field(default_factory=list)


class COGSPostPayload(FAMBaseSchema):
    stock_item_id: int
    quantity: Decimal
    posting_date: date
    reference_number: str | None = None
    inventory_ledger_id: int | None = None
    cogs_ledger_id: int | None = None


class InventoryAIRequestPayload(FAMBaseSchema):
    prompt: str
    scope: str = "inventory"
    stock_item_id: int | None = None


class FAMResponse(FAMBaseSchema):
    id: int


class FAMListResponse(FAMBaseSchema):
    items: list[dict[str, Any]]
    total: int


class FAMAuditResponse(FAMBaseSchema):
    id: int
    company_id: int
    module_name: str
    record_type: str
    record_id: int | None = None
    action: str
    old_value_json: dict[str, Any] | None = None
    new_value_json: dict[str, Any] | None = None
    performed_by: int | None = None
    performed_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
