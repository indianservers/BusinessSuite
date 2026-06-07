from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.apps.fam.access import (
    FAM_AUDIT_PERMISSIONS,
    FAM_BRANCH_PERMISSIONS,
    FAM_ACCOUNTING_STATUS_VIEW_PERMISSIONS,
    FAM_BANK_BOOK_VIEW_PERMISSIONS,
    FAM_BANK_RECONCILE_PERMISSIONS,
    FAM_BANK_STATEMENT_IMPORT_PERMISSIONS,
    FAM_BANKING_MANAGE_PERMISSIONS,
    FAM_BANKING_VIEW_PERMISSIONS,
    FAM_CASH_BOOK_VIEW_PERMISSIONS,
    FAM_CHART_MANAGE_PERMISSIONS,
    FAM_CHART_VIEW_PERMISSIONS,
    FAM_COST_CENTER_PERMISSIONS,
    FAM_DAY_BOOK_PERMISSIONS,
    FAM_GST_EINVOICE_PERMISSIONS,
    FAM_GST_EWAYBILL_PERMISSIONS,
    FAM_GST_MANAGE_PERMISSIONS,
    FAM_GST_RECONCILIATION_PERMISSIONS,
    FAM_GST_RETURN_PREPARE_PERMISSIONS,
    FAM_GST_VIEW_PERMISSIONS,
    FAM_LEDGER_ENTRY_PERMISSIONS,
    FAM_OPENING_MANAGE_PERMISSIONS,
    FAM_OPENING_VIEW_PERMISSIONS,
    FAM_AP_MANAGE_PERMISSIONS,
    FAM_AP_VIEW_PERMISSIONS,
    FAM_AR_MANAGE_PERMISSIONS,
    FAM_AR_VIEW_PERMISSIONS,
    FAM_BILL_ALLOCATION_PERMISSIONS,
    FAM_EXPENSE_MANAGE_PERMISSIONS,
    FAM_EXPENSE_VIEW_PERMISSIONS,
    FAM_PARTIES_MANAGE_PERMISSIONS,
    FAM_PARTIES_VIEW_PERMISSIONS,
    FAM_PARTY_STATEMENT_PERMISSIONS,
    FAM_POSTING_JOBS_RETRY_PERMISSIONS,
    FAM_POSTING_RULES_MANAGE_PERMISSIONS,
    FAM_PURCHASE_MANAGE_PERMISSIONS,
    FAM_PURCHASE_VIEW_PERMISSIONS,
    FAM_SETTINGS_PERMISSIONS,
    FAM_SRM_INTEGRATION_VIEW_PERMISSIONS,
    FAM_SRM_POSTING_MANAGE_PERMISSIONS,
    FAM_VIEW_PERMISSIONS,
    FAM_VOUCHER_CANCEL_PERMISSIONS,
    FAM_VOUCHER_CREATE_PERMISSIONS,
    FAM_VOUCHER_POST_PERMISSIONS,
    FAM_VOUCHER_REVERSE_PERMISSIONS,
    FAM_VOUCHER_TYPE_PERMISSIONS,
    FAM_TDS_MANAGE_PERMISSIONS,
    FAM_TDS_VIEW_PERMISSIONS,
    FAM_VENDOR_PAYMENT_MANAGE_PERMISSIONS,
    FAM_COGS_POST_PERMISSIONS,
    FAM_INVENTORY_AI_USE_PERMISSIONS,
    FAM_INVENTORY_MANAGE_PERMISSIONS,
    FAM_INVENTORY_REPORTS_VIEW_PERMISSIONS,
    FAM_INVENTORY_VALUATION_VIEW_PERMISSIONS,
    FAM_INVENTORY_VIEW_PERMISSIONS,
    FAM_STOCK_ADJUST_PERMISSIONS,
    FAM_STOCK_POST_PERMISSIONS,
    FAM_STOCK_TRANSFER_PERMISSIONS,
    FAM_VOUCHER_VIEW_PERMISSIONS,
    company_id_for,
    require_fam_permission,
)
from app.apps.fam.models import (
    FAMAuditLog,
    FAMAccountingPeriod,
    FAMBranch,
    FAMCompanyFinancialSettings,
    FAMCostCenter,
    FAMFinancialYear,
    FAMLedger,
    FAMLedgerEntry,
    FAMLedgerGroup,
    FAMOpeningBalance,
    FAMBillAllocation,
    FAMBillReference,
    FAMBankAccount,
    FAMBankReconciliationMatch,
    FAMBankReconciliationSession,
    FAMBankStatement,
    FAMBankStatementLine,
    FAMCashRegister,
    FAMParty,
    FAMPartyContact,
    FAMPartyCreditTerm,
    FAMPaymentMode,
    FAMPaymentReference,
    FAMPostingJob,
    FAMPostingRule,
    FAMEInvoiceJob,
    FAMEInvoiceSettings,
    FAMEWayBillJob,
    FAMEWayBillSettings,
    FAMGSTR1Record,
    FAMGSTR3BRecord,
    FAMGSTRate,
    FAMGSTAuditLog,
    FAMGSTReconciliationItem,
    FAMGSTReturnPeriod,
    FAMGSTTransactionLine,
    FAMHSNSACCode,
    FAMExpenseClaim,
    FAMExpenseLine,
    FAMSRMMapping,
    FAMTaxRegistration,
    FAMPurchaseAuditLog,
    FAMPurchaseBill,
    FAMPurchaseBillLine,
    FAMTDSRate,
    FAMTDSSection,
    FAMTDSTransaction,
    FAMVendorPaymentItem,
    FAMVendorPaymentRun,
    FAMInventoryAILog,
    FAMInventoryReport,
    FAMInventoryValuationLayer,
    FAMStockAdjustment,
    FAMStockGroup,
    FAMStockItem,
    FAMStockMovement,
    FAMStockMovementLine,
    FAMStockOpeningBalance,
    FAMStockTransfer,
    FAMUnitOfMeasure,
    FAMWarehouse,
    FAMVoucher,
    FAMVoucherAuditLog,
    FAMVoucherLine,
    FAMVoucherType,
)
from app.apps.fam.schema import ensure_fam_seed_data
from app.apps.fam.schemas import (
    BranchPayload,
    CompanyFinancialSettingsPayload,
    CostCenterPayload,
    FinancialYearPayload,
    LedgerGroupPayload,
    LedgerPayload,
    OpeningBalancePayload,
    BillAllocationPayload,
    BillReferencePayload,
    BankAccountPayload,
    BankChargePostPayload,
    BankStatementIgnoreLinePayload,
    BankStatementImportPayload,
    BankStatementMatchPayload,
    ContraPostPayload,
    EInvoiceSettingsPayload,
    EWayBillSettingsPayload,
    ExpenseClaimPayload,
    GSTCalculationPayload,
    GSTRegistrationPayload,
    GSTReturnPreparePayload,
    GSTRatePayload,
    HSNSACPayload,
    PaymentModePayload,
    PartyCreditTermPayload,
    PartyPayload,
    PostingRulePayload,
    PurchaseBillPayload,
    TDSCalculatePayload,
    TDSRatePayload,
    TDSSectionPayload,
    VendorPaymentPreparePayload,
    COGSPostPayload,
    InventoryAIRequestPayload,
    InventoryGroupPayload,
    InventoryItemPayload,
    InventoryOpeningPayload,
    InventoryUnitPayload,
    InventoryWarehousePayload,
    StockAdjustmentPayload,
    StockMovementPayload,
    StockTransferPayload,
    VoucherCancelPayload,
    VoucherClonePayload,
    VoucherPayload,
    VoucherTypePayload,
    VoucherUpdatePayload,
)
from app.core.deps import RequirePermission, get_db
from app.models.user import User
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation


router = APIRouter(prefix="/fam", tags=["FAM"])

VALID_NATURES = {"asset", "liability", "equity", "income", "expense"}
VALID_LEDGER_TYPES = {"general", "customer", "vendor", "bank", "cash", "tax", "employee", "asset", "liability", "income", "expense"}
VALID_VOUCHER_CATEGORIES = {"journal", "receipt", "payment", "contra", "sales", "purchase", "debit_note", "credit_note", "opening", "adjustment"}
VALID_PARTY_TYPES = {"customer", "vendor", "both"}
VALID_REGISTRATION_TYPES = {"regular", "composition", "unregistered", "consumer", "sez", "export"}
VALID_BILL_TYPES = {"invoice", "bill", "debit_note", "credit_note", "opening", "advance"}
VALID_ALLOCATION_TYPES = {"receipt", "payment", "credit_note", "debit_note", "advance", "advance_adjustment", "writeoff"}
VALID_PAYMENT_MODE_TYPES = {"cash", "cheque", "neft", "rtgs", "upi", "card", "wallet", "other"}
VALID_BANK_STATEMENT_STATUSES = {"imported", "matched", "reconciled"}
VALID_BANK_LINE_STATUSES = {"unmatched", "suggested", "matched", "ignored"}
VALID_GST_TAX_TYPES = {"goods", "services"}
VALID_HSN_SAC_TYPES = {"hsn", "sac"}
VALID_GST_TRANSACTION_TYPES = {"outward", "inward", "rcm", "import", "export"}
VALID_GST_SUPPLY_TYPES = {"b2b", "b2c", "export", "sez", "deemed_export"}
VALID_GST_EXEMPT_TYPES = {None, "exempt", "nil", "zero_rated", "out_of_scope"}


def serialize(record: Any) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for column in record.__table__.columns:
        value = getattr(record, column.name)
        if isinstance(value, Decimal):
            output[column.name] = float(value)
        elif hasattr(value, "isoformat"):
            output[column.name] = value.isoformat()
        else:
            output[column.name] = value
    return output


def audit(db: Session, request: Request, user: User, company_id: int, record_type: str, record_id: int | None, action: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> None:
    db.add(
        FAMAuditLog(
            company_id=company_id,
            module_name="fam",
            record_type=record_type,
            record_id=record_id,
            action=action,
            old_value_json=old,
            new_value_json=new,
            performed_by=user.id,
            performed_at=datetime.now(timezone.utc),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )


def bootstrap(db: Session, user: User) -> int:
    company_id = company_id_for(user)
    ensure_fam_seed_data(db, company_id)
    db.commit()
    return company_id


def assert_nature(value: str) -> None:
    if value not in VALID_NATURES:
        raise HTTPException(status_code=422, detail=f"Invalid nature. Expected one of: {', '.join(sorted(VALID_NATURES))}")


def assert_ledger_type(value: str) -> None:
    if value not in VALID_LEDGER_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid ledger type. Expected one of: {', '.join(sorted(VALID_LEDGER_TYPES))}")


def assert_payment_mode_type(value: str) -> None:
    if value not in VALID_PAYMENT_MODE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid payment mode type. Expected one of: {', '.join(sorted(VALID_PAYMENT_MODE_TYPES))}")


def assert_tax_format_placeholders(payload: Any) -> None:
    patterns = {
        "gstin": r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
        "pan": r"^[A-Z]{5}[0-9]{4}[A-Z]$",
        "tan": r"^[A-Z]{4}[0-9]{5}[A-Z]$",
    }
    for field, pattern in patterns.items():
        value = getattr(payload, field, None)
        if value and not re.match(pattern, str(value).strip().upper()):
            raise HTTPException(status_code=422, detail=f"{field.upper()} validation failed")


def get_current_financial_year(db: Session, company_id: int) -> FAMFinancialYear | None:
    return db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.is_current == True).first()


def voucher_lines(db: Session, voucher_id: int) -> list[FAMVoucherLine]:
    return db.query(FAMVoucherLine).filter(FAMVoucherLine.voucher_id == voucher_id).order_by(FAMVoucherLine.line_number).all()


def serialize_voucher(db: Session, voucher: FAMVoucher) -> dict[str, Any]:
    data = serialize(voucher)
    data["lines"] = [serialize(line) for line in voucher_lines(db, voucher.id)]
    return data


def voucher_audit(db: Session, voucher_id: int, action: str, user: User, old: dict[str, Any] | None, new: dict[str, Any] | None) -> None:
    db.add(FAMVoucherAuditLog(voucher_id=voucher_id, action=action, old_value_json=old, new_value_json=new, performed_by=user.id, performed_at=datetime.now(timezone.utc)))


def find_financial_year_for_date(db: Session, company_id: int, voucher_date) -> FAMFinancialYear:
    fy = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.start_date <= voucher_date, FAMFinancialYear.end_date >= voucher_date).first()
    if not fy:
        raise HTTPException(status_code=422, detail="Voucher date does not belong to a financial year")
    if fy.status in {"closed", "locked"}:
        raise HTTPException(status_code=409, detail="Closed/locked financial year blocks posting")
    return fy


def find_period_for_date(db: Session, fy: FAMFinancialYear, voucher_date) -> FAMAccountingPeriod | None:
    period = db.query(FAMAccountingPeriod).filter(FAMAccountingPeriod.financial_year_id == fy.id, FAMAccountingPeriod.start_date <= voucher_date, FAMAccountingPeriod.end_date >= voucher_date).first()
    if period and period.status in {"closed", "locked"}:
        raise HTTPException(status_code=409, detail="Closed/locked accounting period blocks posting")
    return period


def validate_voucher_type(category: str) -> None:
    if category not in VALID_VOUCHER_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Invalid voucher category. Expected one of: {', '.join(sorted(VALID_VOUCHER_CATEGORIES))}")


def next_voucher_number(voucher_type: FAMVoucherType) -> str:
    return f"{voucher_type.numbering_prefix}-{int(voucher_type.numbering_sequence or 1):05d}"


def validate_voucher_payload(db: Session, company_id: int, payload: VoucherPayload, for_posting: bool = False) -> tuple[FAMFinancialYear, FAMAccountingPeriod | None, FAMVoucherType, Decimal, Decimal]:
    voucher_type = db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id, FAMVoucherType.id == payload.voucher_type_id, FAMVoucherType.active == True).first()
    if not voucher_type:
        raise HTTPException(status_code=404, detail="Voucher type not found")
    fy = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id == payload.financial_year_id).first() if payload.financial_year_id else find_financial_year_for_date(db, company_id, payload.voucher_date)
    if not fy:
        raise HTTPException(status_code=404, detail="Financial year not found")
    if not (fy.start_date <= payload.voucher_date <= fy.end_date):
        raise HTTPException(status_code=422, detail="Voucher date must belong to the selected financial year")
    if fy.status in {"closed", "locked"}:
        raise HTTPException(status_code=409, detail="Closed/locked financial year blocks posting")
    period = db.query(FAMAccountingPeriod).filter(FAMAccountingPeriod.id == payload.accounting_period_id, FAMAccountingPeriod.financial_year_id == fy.id).first() if payload.accounting_period_id else find_period_for_date(db, fy, payload.voucher_date)
    if for_posting and len(payload.lines) < 2:
        raise HTTPException(status_code=422, detail="At least two voucher lines are required")
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for line in payload.lines:
        debit = Decimal(line.debit_amount or 0)
        credit = Decimal(line.credit_amount or 0)
        if debit < 0 or credit < 0:
            raise HTTPException(status_code=422, detail="Debit and credit amounts cannot be negative")
        if debit and credit:
            raise HTTPException(status_code=422, detail="A voucher line cannot have both debit and credit")
        if for_posting and not debit and not credit:
            raise HTTPException(status_code=422, detail="Each posted voucher line must have either debit or credit")
        ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == line.ledger_id, FAMLedger.active == True).first()
        if not ledger:
            raise HTTPException(status_code=404, detail=f"Active ledger not found: {line.ledger_id}")
        debit_total += debit
        credit_total += credit
    if for_posting and debit_total != credit_total:
        raise HTTPException(status_code=409, detail="Voucher debit total must equal credit total")
    return fy, period, voucher_type, debit_total, credit_total


def payload_from_voucher(db: Session, voucher: FAMVoucher) -> VoucherPayload:
    return VoucherPayload(
        financial_year_id=voucher.financial_year_id,
        accounting_period_id=voucher.accounting_period_id,
        branch_id=voucher.branch_id,
        voucher_type_id=voucher.voucher_type_id,
        voucher_number=voucher.voucher_number,
        voucher_date=voucher.voucher_date,
        reference_number=voucher.reference_number,
        reference_date=voucher.reference_date,
        narration=voucher.narration,
        source_module=voucher.source_module,
        source_record_type=voucher.source_record_type,
        source_record_id=voucher.source_record_id,
        lines=[serialize(line) for line in voucher_lines(db, voucher.id)],
    )


def apply_ledger_movement(ledger: FAMLedger, debit: Decimal, credit: Decimal) -> Decimal:
    ledger.current_balance_dr = Decimal(ledger.current_balance_dr or 0) + debit
    ledger.current_balance_cr = Decimal(ledger.current_balance_cr or 0) + credit
    return Decimal(ledger.current_balance_dr or 0) - Decimal(ledger.current_balance_cr or 0)


def assert_party_payload(db: Session, company_id: int, payload: PartyPayload) -> None:
    if payload.party_type not in VALID_PARTY_TYPES:
        raise HTTPException(status_code=422, detail="Invalid party type")
    if payload.registration_type not in VALID_REGISTRATION_TYPES:
        raise HTTPException(status_code=422, detail="Invalid GST registration type")
    if Decimal(payload.opening_balance_dr or 0) and Decimal(payload.opening_balance_cr or 0):
        raise HTTPException(status_code=422, detail="Party opening balance cannot have both debit and credit")
    assert_tax_format_placeholders(payload)
    settings = db.query(FAMCompanyFinancialSettings).filter(FAMCompanyFinancialSettings.company_id == company_id).first()
    if settings and settings.gst_enabled and not payload.state_code:
        raise HTTPException(status_code=422, detail="State code is mandatory for GST-enabled companies")


def party_contacts(db: Session, party_id: int) -> list[dict[str, Any]]:
    return [serialize(item) for item in db.query(FAMPartyContact).filter(FAMPartyContact.party_id == party_id).order_by(FAMPartyContact.is_primary.desc(), FAMPartyContact.id).all()]


def serialize_party(db: Session, party: FAMParty) -> dict[str, Any]:
    data = serialize(party)
    data["contacts"] = party_contacts(db, party.id)
    return data


def group_for_party_type(db: Session, company_id: int, party_type: str) -> FAMLedgerGroup:
    group_code = "ASSET-DEBTORS" if party_type in {"customer", "both"} else "LIAB-CREDITORS"
    group = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.group_code == group_code).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"System ledger group missing: {group_code}")
    return group


def create_party_ledger(db: Session, company_id: int, party: FAMParty) -> FAMLedger:
    if party.ledger_id:
        ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == party.ledger_id).first()
        if ledger:
            return ledger
    group = group_for_party_type(db, company_id, party.party_type)
    ledger = FAMLedger(
        company_id=company_id,
        ledger_code=f"PARTY-{party.party_code}",
        ledger_name=party.legal_name,
        ledger_group_id=group.id,
        nature=group.nature,
        ledger_type="customer" if party.party_type == "customer" else "vendor" if party.party_type == "vendor" else "general",
        pan=party.pan,
        gstin=party.gstin,
        state_code=party.state_code,
        billing_address=party.billing_address,
        opening_balance_dr=party.opening_balance_dr,
        opening_balance_cr=party.opening_balance_cr,
        current_balance_dr=party.opening_balance_dr,
        current_balance_cr=party.opening_balance_cr,
        active=True,
        system_ledger=False,
    )
    db.add(ledger)
    db.flush()
    party.ledger_id = ledger.id
    return ledger


def bill_status(outstanding: Decimal) -> str:
    return "settled" if outstanding <= 0 else "open"


def bucket_for(due_date: date, today: date) -> str:
    days = (today - due_date).days
    if days < 0:
        return "Not due"
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    if days <= 180:
        return "91-180"
    return ">180"


def bill_query_for(db: Session, company_id: int, receivable: bool):
    party_types = ["customer", "both"] if receivable else ["vendor", "both"]
    bill_types = ["invoice", "debit_note", "opening"] if receivable else ["bill", "credit_note", "opening"]
    return db.query(FAMBillReference).join(FAMParty, FAMParty.id == FAMBillReference.party_id).filter(
        FAMBillReference.company_id == company_id,
        FAMParty.party_type.in_(party_types),
        FAMBillReference.bill_type.in_(bill_types),
        FAMBillReference.outstanding_amount > 0,
    )


def aging_payload(items: list[FAMBillReference], today: date) -> dict[str, Any]:
    buckets = {name: Decimal("0") for name in ["Not due", "0-30", "31-60", "61-90", "91-180", ">180"]}
    rows = []
    for item in items:
        bucket = bucket_for(item.due_date, today)
        amount = Decimal(item.outstanding_amount or 0)
        buckets[bucket] += amount
        rows.append({**serialize(item), "aging_bucket": bucket, "overdue_days": max((today - item.due_date).days, 0)})
    return {"buckets": {key: float(value) for key, value in buckets.items()}, "items": rows, "totalOutstanding": float(sum(buckets.values(), Decimal("0")))}


def parse_date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() == "":
        raise HTTPException(status_code=422, detail="Statement date is required")
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail=f"Invalid statement date: {text}")


def parse_money(value: Any) -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal("0")
    cleaned = str(value).replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid amount: {value}") from exc


def line_hash(line: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(line.get("transaction_date") or ""),
            str(line.get("value_date") or ""),
            str(line.get("description") or "").strip().lower(),
            str(line.get("reference_number") or "").strip().lower(),
            str(line.get("debit_amount") or "0"),
            str(line.get("credit_amount") or "0"),
            str(line.get("balance") or "0"),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def statement_hash(payload: BankStatementImportPayload, normalized_lines: list[dict[str, Any]]) -> str:
    source = payload.file_content or "|".join(line_hash(line) for line in normalized_lines)
    raw = f"{payload.bank_account_id}|{payload.statement_period_start}|{payload.statement_period_end}|{payload.imported_file_name}|{source}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lines_from_csv(content: str, column_map: dict[str, str] | None) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV statement has no header row")
    mapping = column_map or {
        "transaction_date": "transaction_date",
        "value_date": "value_date",
        "description": "description",
        "reference_number": "reference_number",
        "debit_amount": "debit_amount",
        "credit_amount": "credit_amount",
        "balance": "balance",
    }
    rows: list[dict[str, Any]] = []
    for row in reader:
        rows.append({target: row.get(source, "") for target, source in mapping.items()})
    return rows


def normalize_statement_lines(payload: BankStatementImportPayload) -> list[dict[str, Any]]:
    raw_lines: list[Any] = [line.model_dump() for line in payload.lines]
    if payload.file_content:
        raw_lines.extend(lines_from_csv(payload.file_content, payload.column_map))
    if not raw_lines:
        raise HTTPException(status_code=422, detail="At least one statement line is required")
    normalized: list[dict[str, Any]] = []
    for raw in raw_lines:
        debit = parse_money(raw.get("debit_amount"))
        credit = parse_money(raw.get("credit_amount"))
        if debit < 0 or credit < 0:
            raise HTTPException(status_code=422, detail="Statement debit/credit amounts cannot be negative")
        if debit and credit:
            raise HTTPException(status_code=422, detail="Statement line cannot have both debit and credit amount")
        if not debit and not credit:
            raise HTTPException(status_code=422, detail="Statement line requires debit or credit amount")
        line = {
            "transaction_date": parse_date_value(raw.get("transaction_date")),
            "value_date": parse_date_value(raw.get("value_date")) if raw.get("value_date") else None,
            "description": str(raw.get("description") or "").strip(),
            "reference_number": str(raw.get("reference_number") or "").strip() or None,
            "debit_amount": debit,
            "credit_amount": credit,
            "balance": parse_money(raw.get("balance")),
        }
        if not line["description"]:
            raise HTTPException(status_code=422, detail="Statement line description is required")
        line["line_hash"] = line_hash(line)
        normalized.append(line)
    return normalized


def statement_lines(db: Session, statement_id: int) -> list[FAMBankStatementLine]:
    return db.query(FAMBankStatementLine).filter(FAMBankStatementLine.statement_id == statement_id).order_by(FAMBankStatementLine.transaction_date, FAMBankStatementLine.id).all()


def serialize_statement(db: Session, statement: FAMBankStatement) -> dict[str, Any]:
    lines = statement_lines(db, statement.id)
    data = serialize(statement)
    data["lines"] = [serialize(line) for line in lines]
    data["summary"] = {
        "total_lines": len(lines),
        "matched": len([line for line in lines if line.matched_status == "matched"]),
        "suggested": len([line for line in lines if line.matched_status == "suggested"]),
        "unmatched": len([line for line in lines if line.matched_status == "unmatched"]),
        "ignored": len([line for line in lines if line.matched_status == "ignored"]),
    }
    return data


def ledger_book_payload(db: Session, company_id: int, ledger_types: set[str], ledger_id: int | None = None) -> dict[str, Any]:
    ledger_query = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_type.in_(ledger_types))
    if ledger_id:
        ledger_query = ledger_query.filter(FAMLedger.id == ledger_id)
    ledgers = ledger_query.order_by(FAMLedger.ledger_name).all()
    ledger_ids = [item.id for item in ledgers]
    entries = db.query(FAMLedgerEntry).filter(FAMLedgerEntry.company_id == company_id, FAMLedgerEntry.ledger_id.in_(ledger_ids)).order_by(FAMLedgerEntry.voucher_date, FAMLedgerEntry.id).all() if ledger_ids else []
    opening = sum((Decimal(item.opening_balance_dr or 0) - Decimal(item.opening_balance_cr or 0)) for item in ledgers)
    debit = sum(Decimal(item.debit_amount or 0) for item in entries)
    credit = sum(Decimal(item.credit_amount or 0) for item in entries)
    return {
        "ledgers": [serialize(item) for item in ledgers],
        "items": [serialize(item) for item in entries],
        "openingBalance": float(opening),
        "debitTotal": float(debit),
        "creditTotal": float(credit),
        "closingBalance": float(opening + debit - credit),
    }


def best_match_for_line(db: Session, company_id: int, bank_ledger_id: int, line: FAMBankStatementLine) -> tuple[FAMLedgerEntry | None, Decimal]:
    amount = Decimal(line.credit_amount or 0) or Decimal(line.debit_amount or 0)
    start_date = line.transaction_date - timedelta(days=3)
    end_date = line.transaction_date + timedelta(days=3)
    candidates = db.query(FAMLedgerEntry).filter(
        FAMLedgerEntry.company_id == company_id,
        FAMLedgerEntry.ledger_id == bank_ledger_id,
        FAMLedgerEntry.voucher_date >= start_date,
        FAMLedgerEntry.voucher_date <= end_date,
        or_(FAMLedgerEntry.debit_amount == amount, FAMLedgerEntry.credit_amount == amount),
    ).all()
    if not candidates:
        return None, Decimal("0")
    scored: list[tuple[Decimal, FAMLedgerEntry]] = []
    ref = (line.reference_number or "").lower()
    desc = (line.description or "").lower()
    for candidate in candidates:
        score = Decimal("70")
        if ref and ref in (candidate.narration or "").lower():
            score += Decimal("20")
        if desc and desc[:12] in (candidate.narration or "").lower():
            score += Decimal("10")
        scored.append((min(score, Decimal("99")), candidate))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1], scored[0][0]


def ledger_by_code(db: Session, company_id: int, code: str) -> FAMLedger:
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_code == code).first()
    if not ledger:
        raise HTTPException(status_code=422, detail=f"Required FAM ledger missing: {code}")
    return ledger


def voucher_type_by_code(db: Session, company_id: int, code: str) -> FAMVoucherType:
    voucher_type = db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id, FAMVoucherType.voucher_type_code == code, FAMVoucherType.active == True).first()
    if not voucher_type:
        raise HTTPException(status_code=422, detail=f"Required FAM voucher type missing: {code}")
    return voucher_type


def mapping_for(db: Session, company_id: int, srm_record_type: str, srm_record_id: int, fam_record_type: str) -> FAMSRMMapping | None:
    return db.query(FAMSRMMapping).filter(
        FAMSRMMapping.company_id == company_id,
        FAMSRMMapping.srm_record_type == srm_record_type,
        FAMSRMMapping.srm_record_id == srm_record_id,
        FAMSRMMapping.fam_record_type == fam_record_type,
    ).first()


def add_mapping(db: Session, company_id: int, srm_record_type: str, srm_record_id: int, fam_record_type: str, fam_record_id: int, status_value: str = "active") -> FAMSRMMapping:
    existing = mapping_for(db, company_id, srm_record_type, srm_record_id, fam_record_type)
    if existing:
        return existing
    item = FAMSRMMapping(company_id=company_id, srm_record_type=srm_record_type, srm_record_id=srm_record_id, fam_record_type=fam_record_type, fam_record_id=fam_record_id, mapping_status=status_value)
    db.add(item)
    db.flush()
    return item


def posting_job(db: Session, company_id: int, source_record_type: str, source_record_id: int, posting_type: str) -> FAMPostingJob:
    job = db.query(FAMPostingJob).filter(
        FAMPostingJob.company_id == company_id,
        FAMPostingJob.source_module == "srm",
        FAMPostingJob.source_record_type == source_record_type,
        FAMPostingJob.source_record_id == source_record_id,
        FAMPostingJob.posting_type == posting_type,
    ).first()
    if job:
        return job
    job = FAMPostingJob(company_id=company_id, source_module="srm", source_record_type=source_record_type, source_record_id=source_record_id, posting_type=posting_type, status="pending", retry_count=0)
    db.add(job)
    db.flush()
    return job


def source_status(db: Session, company_id: int, source_record_type: str, source_record_id: int) -> dict[str, Any]:
    jobs = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.source_module == "srm", FAMPostingJob.source_record_type == source_record_type, FAMPostingJob.source_record_id == source_record_id).all()
    mappings = db.query(FAMSRMMapping).filter(FAMSRMMapping.company_id == company_id, FAMSRMMapping.srm_record_type == source_record_type, FAMSRMMapping.srm_record_id == source_record_id).all()
    latest = sorted(jobs, key=lambda item: item.id, reverse=True)[0] if jobs else None
    return {
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "status": latest.status if latest else "not_posted",
        "posting_jobs": [serialize(item) for item in jobs],
        "mappings": [serialize(item) for item in mappings],
    }


def ensure_srm_customer_party(db: Session, company_id: int, customer_id: int | None, source_record_type: str, source_record_id: int) -> FAMParty:
    mapping_id = customer_id if customer_id is not None else source_record_id
    mapped = mapping_for(db, company_id, "customer", mapping_id, "party")
    if mapped:
        party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == mapped.fam_record_id).first()
        if party:
            return party
    party_code = f"SRM-CUST-{customer_id}" if customer_id is not None else f"SRM-{source_record_type.upper()}-{source_record_id}"
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.party_code == party_code).first()
    if not party:
        party = FAMParty(
            company_id=company_id,
            party_type="customer",
            party_code=party_code,
            legal_name=f"SRM Customer {customer_id or source_record_id}",
            trade_name=f"SRM Customer {customer_id or source_record_id}",
            registration_type="unregistered",
            payment_terms_days=30,
            active=True,
        )
        db.add(party)
        db.flush()
    create_party_ledger(db, company_id, party)
    add_mapping(db, company_id, "customer", mapping_id, "party", party.id)
    return party


def create_and_post_voucher(
    db: Session,
    request: Request,
    user: User,
    company_id: int,
    voucher_type_code: str,
    voucher_date: date,
    reference_number: str,
    narration: str,
    source_record_type: str,
    source_record_id: int,
    lines: list[dict[str, Any]],
    source_module: str = "srm",
) -> FAMVoucher:
    voucher_type = voucher_type_by_code(db, company_id, voucher_type_code)
    fy = find_financial_year_for_date(db, company_id, voucher_date)
    period = find_period_for_date(db, fy, voucher_date)
    debit_total = sum(Decimal(str(line.get("debit_amount") or 0)) for line in lines)
    credit_total = sum(Decimal(str(line.get("credit_amount") or 0)) for line in lines)
    if debit_total <= 0 or debit_total != credit_total:
        raise HTTPException(status_code=409, detail="FAM posting voucher must be balanced")
    voucher = FAMVoucher(
        company_id=company_id,
        financial_year_id=fy.id,
        accounting_period_id=period.id if period else None,
        voucher_type_id=voucher_type.id,
        voucher_number=next_voucher_number(voucher_type),
        voucher_date=voucher_date,
        reference_number=reference_number,
        narration=narration,
        total_debit=debit_total,
        total_credit=credit_total,
        status="posted",
        source_module=source_module,
        source_record_type=source_record_type,
        source_record_id=str(source_record_id),
        posted_by=user.id,
        posted_at=datetime.now(timezone.utc),
    )
    db.add(voucher)
    db.flush()
    for index, line in enumerate(lines, start=1):
        voucher_line = FAMVoucherLine(voucher_id=voucher.id, line_number=index, **line)
        db.add(voucher_line)
        db.flush()
        ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == voucher_line.ledger_id).first()
        running = apply_ledger_movement(ledger, Decimal(voucher_line.debit_amount or 0), Decimal(voucher_line.credit_amount or 0))
        db.add(
            FAMLedgerEntry(
                company_id=company_id,
                financial_year_id=fy.id,
                accounting_period_id=period.id if period else None,
                voucher_id=voucher.id,
                voucher_line_id=voucher_line.id,
                voucher_number=voucher.voucher_number,
                voucher_date=voucher.voucher_date,
                ledger_id=voucher_line.ledger_id,
                debit_amount=voucher_line.debit_amount,
                credit_amount=voucher_line.credit_amount,
                running_balance=running,
                narration=voucher_line.narration or narration,
                source_module=source_module,
                source_record_type=source_record_type,
                source_record_id=str(source_record_id),
                posted_at=voucher.posted_at,
            )
        )
    voucher_type.numbering_sequence = int(voucher_type.numbering_sequence or 1) + 1
    voucher_audit(db, voucher.id, f"CREATE_POSTED_FROM_{source_module.upper()}", user, None, serialize_voucher(db, voucher))
    audit(db, request, user, company_id, "voucher", voucher.id, f"POST_FROM_{source_module.upper()}", None, serialize(voucher))
    return voucher


def create_or_get_bill_reference(
    db: Session,
    company_id: int,
    party: FAMParty,
    ledger_id: int,
    voucher_id: int,
    bill_number: str,
    bill_date: date,
    due_date: date,
    bill_type: str,
    original_amount: Decimal,
    outstanding_amount: Decimal,
    source_record_type: str,
    source_record_id: int,
) -> FAMBillReference:
    mapped = mapping_for(db, company_id, source_record_type, source_record_id, "bill_reference")
    if mapped:
        existing = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.id == mapped.fam_record_id).first()
        if existing:
            return existing
    existing = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.party_id == party.id, FAMBillReference.bill_number == bill_number).first()
    if existing:
        add_mapping(db, company_id, source_record_type, source_record_id, "bill_reference", existing.id)
        return existing
    item = FAMBillReference(
        company_id=company_id,
        party_id=party.id,
        ledger_id=ledger_id,
        voucher_id=voucher_id,
        bill_number=bill_number,
        bill_date=bill_date,
        due_date=due_date,
        bill_type=bill_type,
        original_amount=original_amount,
        outstanding_amount=outstanding_amount,
        status=bill_status(outstanding_amount),
        source_module="srm",
        source_record_type=source_record_type,
        source_record_id=str(source_record_id),
    )
    db.add(item)
    db.flush()
    add_mapping(db, company_id, source_record_type, source_record_id, "bill_reference", item.id)
    return item


def post_srm_invoice_to_fam(db: Session, request: Request, user: User, company_id: int, invoice_id: int) -> dict[str, Any]:
    invoice = db.query(SRMInvoice).filter(SRMInvoice.id == invoice_id, SRMInvoice.deleted_at == None).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="SRM invoice not found")
    if invoice.status in {"draft", "pending_approval", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only approved/sent/payable SRM invoices can be posted")
    job = posting_job(db, company_id, "invoice", invoice.id, "sales_invoice")
    mapped = mapping_for(db, company_id, "invoice", invoice.id, "voucher")
    if mapped and job.status == "posted":
        voucher = db.query(FAMVoucher).filter(FAMVoucher.id == mapped.fam_record_id).first()
        return {"status": "posted", "idempotent": True, "postingJob": serialize(job), "voucher": serialize(voucher), "accountingStatus": source_status(db, company_id, "invoice", invoice.id)}
    party = ensure_srm_customer_party(db, company_id, invoice.customer_id, "invoice", invoice.id)
    sales = Decimal(invoice.subtotal or 0) or (Decimal(invoice.total_amount or 0) - Decimal(invoice.tax_amount or 0))
    tax = Decimal(invoice.tax_amount or 0)
    total = Decimal(invoice.total_amount or 0)
    invoice_date = invoice.issue_date or date.today()
    lines = [
        {"ledger_id": party.ledger_id, "debit_amount": total, "credit_amount": Decimal("0"), "narration": f"SRM invoice {invoice.invoice_number}", "party_id": party.id},
        {"ledger_id": ledger_by_code(db, company_id, "SALES").id, "debit_amount": Decimal("0"), "credit_amount": sales, "narration": f"SRM invoice {invoice.invoice_number} sales"},
    ]
    if tax > 0:
        half_tax = (tax / Decimal("2")).quantize(Decimal("0.01"))
        lines.append({"ledger_id": ledger_by_code(db, company_id, "OUTPUT-CGST").id, "debit_amount": Decimal("0"), "credit_amount": half_tax, "narration": "Output CGST"})
        lines.append({"ledger_id": ledger_by_code(db, company_id, "OUTPUT-SGST").id, "debit_amount": Decimal("0"), "credit_amount": tax - half_tax, "narration": "Output SGST"})
    voucher = create_and_post_voucher(db, request, user, company_id, "SV", invoice_date, invoice.invoice_number, f"SRM sales invoice {invoice.invoice_number}", "invoice", invoice.id, lines)
    add_mapping(db, company_id, "invoice", invoice.id, "voucher", voucher.id)
    bill = create_or_get_bill_reference(db, company_id, party, party.ledger_id, voucher.id, invoice.invoice_number, invoice_date, invoice.due_date or invoice_date + timedelta(days=party.payment_terms_days or 0), "invoice", total, Decimal(invoice.balance_amount if invoice.balance_amount is not None else total), "invoice", invoice.id)
    job.status = "posted"
    job.voucher_id = voucher.id
    job.error_message = None
    job.posted_at = datetime.now(timezone.utc)
    audit(db, request, user, company_id, "srm_posting_job", job.id, "POST_INVOICE", None, {"invoice_id": invoice.id, "voucher_id": voucher.id, "bill_reference_id": bill.id})
    db.commit()
    return {"status": "posted", "idempotent": False, "postingJob": serialize(job), "voucher": serialize(voucher), "billReference": serialize(bill), "party": serialize_party(db, party), "accountingStatus": source_status(db, company_id, "invoice", invoice.id)}


def ensure_receipt_advance_reference(db: Session, company_id: int, receipt: SRMReceipt, party: FAMParty, voucher_id: int | None = None) -> FAMBillReference:
    existing = mapping_for(db, company_id, "receipt", receipt.id, "bill_reference")
    if existing:
        bill = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.id == existing.fam_record_id).first()
        if bill:
            return bill
    receipt_date = receipt.receipt_date or date.today()
    return create_or_get_bill_reference(db, company_id, party, party.ledger_id, voucher_id or 0, receipt.receipt_number, receipt_date, receipt_date, "advance", Decimal(receipt.amount or 0), Decimal(receipt.amount or 0), "receipt", receipt.id)


def post_srm_receipt_to_fam(db: Session, request: Request, user: User, company_id: int, receipt_id: int) -> dict[str, Any]:
    receipt = db.query(SRMReceipt).filter(SRMReceipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="SRM receipt not found")
    if receipt.status == "draft":
        raise HTTPException(status_code=409, detail="Only confirmed/allocated SRM receipts can be posted")
    job = posting_job(db, company_id, "receipt", receipt.id, "receipt")
    mapped = mapping_for(db, company_id, "receipt", receipt.id, "voucher")
    if mapped and job.status == "posted":
        voucher = db.query(FAMVoucher).filter(FAMVoucher.id == mapped.fam_record_id).first()
        return {"status": "posted", "idempotent": True, "postingJob": serialize(job), "voucher": serialize(voucher), "accountingStatus": source_status(db, company_id, "receipt", receipt.id)}
    party = ensure_srm_customer_party(db, company_id, receipt.customer_id, "receipt", receipt.id)
    amount = Decimal(receipt.amount or 0)
    receipt_date = receipt.receipt_date or date.today()
    voucher = create_and_post_voucher(
        db,
        request,
        user,
        company_id,
        "RV",
        receipt_date,
        receipt.receipt_number,
        f"SRM receipt {receipt.receipt_number}",
        "receipt",
        receipt.id,
        [
            {"ledger_id": ledger_by_code(db, company_id, "BANK-DEFAULT").id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": f"SRM receipt {receipt.receipt_number}"},
            {"ledger_id": party.ledger_id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": f"SRM receipt {receipt.receipt_number}", "party_id": party.id},
        ],
    )
    add_mapping(db, company_id, "receipt", receipt.id, "voucher", voucher.id)
    bill = ensure_receipt_advance_reference(db, company_id, receipt, party, voucher.id)
    job.status = "posted"
    job.voucher_id = voucher.id
    job.error_message = None
    job.posted_at = datetime.now(timezone.utc)
    audit(db, request, user, company_id, "srm_posting_job", job.id, "POST_RECEIPT", None, {"receipt_id": receipt.id, "voucher_id": voucher.id, "advance_bill_reference_id": bill.id})
    db.commit()
    return {"status": "posted", "idempotent": False, "postingJob": serialize(job), "voucher": serialize(voucher), "billReference": serialize(bill), "party": serialize_party(db, party), "accountingStatus": source_status(db, company_id, "receipt", receipt.id)}


def post_srm_allocation_to_fam(db: Session, request: Request, user: User, company_id: int, allocation_id: int) -> dict[str, Any]:
    allocation = db.query(SRMReceiptAllocation).filter(SRMReceiptAllocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="SRM receipt allocation not found")
    job = posting_job(db, company_id, "allocation", allocation.id, "allocation")
    mapped = mapping_for(db, company_id, "allocation", allocation.id, "allocation")
    if mapped and job.status == "posted":
        fam_allocation = db.query(FAMBillAllocation).filter(FAMBillAllocation.id == mapped.fam_record_id).first()
        return {"status": "posted", "idempotent": True, "postingJob": serialize(job), "allocation": serialize(fam_allocation), "accountingStatus": source_status(db, company_id, "allocation", allocation.id)}
    receipt = db.query(SRMReceipt).filter(SRMReceipt.id == allocation.receipt_id).first()
    invoice = db.query(SRMInvoice).filter(SRMInvoice.id == allocation.invoice_id, SRMInvoice.deleted_at == None).first()
    if not receipt or not invoice:
        raise HTTPException(status_code=404, detail="SRM receipt/invoice not found")
    invoice_result = post_srm_invoice_to_fam(db, request, user, company_id, invoice.id)
    receipt_result = post_srm_receipt_to_fam(db, request, user, company_id, receipt.id)
    party = ensure_srm_customer_party(db, company_id, invoice.customer_id or receipt.customer_id, "allocation", allocation.id)
    invoice_bill = db.query(FAMBillReference).filter(FAMBillReference.id == invoice_result["billReference"]["id"]).first() if "billReference" in invoice_result else db.query(FAMBillReference).filter(FAMBillReference.id == mapping_for(db, company_id, "invoice", invoice.id, "bill_reference").fam_record_id).first()
    receipt_bill = db.query(FAMBillReference).filter(FAMBillReference.id == receipt_result["billReference"]["id"]).first() if "billReference" in receipt_result else db.query(FAMBillReference).filter(FAMBillReference.id == mapping_for(db, company_id, "receipt", receipt.id, "bill_reference").fam_record_id).first()
    amount = Decimal(allocation.amount or 0)
    if amount > Decimal(invoice_bill.outstanding_amount or 0):
        raise HTTPException(status_code=409, detail="Allocation exceeds FAM invoice outstanding")
    invoice_bill.outstanding_amount = Decimal(invoice_bill.outstanding_amount or 0) - amount
    invoice_bill.status = bill_status(Decimal(invoice_bill.outstanding_amount or 0))
    receipt_bill.outstanding_amount = max(Decimal(receipt_bill.outstanding_amount or 0) - amount, Decimal("0"))
    receipt_bill.status = bill_status(Decimal(receipt_bill.outstanding_amount or 0))
    fam_allocation = FAMBillAllocation(
        company_id=company_id,
        allocation_date=allocation.allocated_at.date() if allocation.allocated_at else date.today(),
        party_id=party.id,
        from_bill_reference_id=receipt_bill.id,
        to_bill_reference_id=invoice_bill.id,
        allocated_amount=amount,
        allocation_type="receipt",
        created_by=user.id,
    )
    db.add(fam_allocation)
    db.flush()
    add_mapping(db, company_id, "allocation", allocation.id, "allocation", fam_allocation.id)
    job.status = "posted"
    job.error_message = None
    job.posted_at = datetime.now(timezone.utc)
    audit(db, request, user, company_id, "srm_posting_job", job.id, "POST_ALLOCATION", None, {"allocation_id": allocation.id, "fam_allocation_id": fam_allocation.id})
    db.commit()
    return {"status": "posted", "idempotent": False, "postingJob": serialize(job), "allocation": serialize(fam_allocation), "accountingStatus": source_status(db, company_id, "allocation", allocation.id)}


def reverse_srm_posting(db: Session, request: Request, user: User, company_id: int, source_record_type: str, source_record_id: int) -> dict[str, Any]:
    mapped = mapping_for(db, company_id, source_record_type, source_record_id, "voucher")
    if not mapped:
        raise HTTPException(status_code=404, detail="Posted FAM voucher mapping not found")
    original = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == mapped.fam_record_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Original FAM voucher not found")
    existing_reversal = mapping_for(db, company_id, source_record_type, source_record_id, "reversal_voucher")
    job = posting_job(db, company_id, source_record_type, source_record_id, "reversal")
    if existing_reversal:
        reversal = db.query(FAMVoucher).filter(FAMVoucher.id == existing_reversal.fam_record_id).first()
        return {"status": "reversed", "idempotent": True, "postingJob": serialize(job), "reversalVoucher": serialize(reversal), "accountingStatus": source_status(db, company_id, source_record_type, source_record_id)}
    lines = []
    for line in voucher_lines(db, original.id):
        lines.append({"ledger_id": line.ledger_id, "debit_amount": Decimal(line.credit_amount or 0), "credit_amount": Decimal(line.debit_amount or 0), "narration": f"Reversal of {original.voucher_number}", "party_id": line.party_id})
    reversal = create_and_post_voucher(db, request, user, company_id, "ADJ", date.today(), f"REV-{original.voucher_number}", f"Reversal of SRM {source_record_type} {source_record_id}", source_record_type, source_record_id, lines)
    original.reversed_voucher_id = reversal.id
    add_mapping(db, company_id, source_record_type, source_record_id, "reversal_voucher", reversal.id, "reversed")
    job.status = "reversed"
    job.voucher_id = reversal.id
    job.posted_at = datetime.now(timezone.utc)
    audit(db, request, user, company_id, "srm_posting_job", job.id, "REVERSE", None, {"source_record_type": source_record_type, "source_record_id": source_record_id, "reversal_voucher_id": reversal.id})
    db.commit()
    return {"status": "reversed", "idempotent": False, "postingJob": serialize(job), "reversalVoucher": serialize(reversal), "accountingStatus": source_status(db, company_id, source_record_type, source_record_id)}


@router.get("/module-info")
def module_info(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return {"key": "fam", "name": "Finance & Accounting Management", "shortName": "FAM", "companyId": company_id}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    current_fy = get_current_financial_year(db, company_id)
    def total_for(nature: str, side: str) -> float:
        column = FAMLedger.current_balance_dr if side == "dr" else FAMLedger.current_balance_cr
        return float(db.query(func.coalesce(func.sum(column), 0)).filter(FAMLedger.company_id == company_id, FAMLedger.nature == nature, FAMLedger.active == True).scalar() or 0)

    cash_bank = db.query(func.coalesce(func.sum(FAMLedger.current_balance_dr - FAMLedger.current_balance_cr), 0)).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_type.in_(["cash", "bank"]), FAMLedger.active == True).scalar() or 0
    recent = db.query(FAMAuditLog).filter(FAMAuditLog.company_id == company_id).order_by(FAMAuditLog.performed_at.desc(), FAMAuditLog.id.desc()).limit(8).all()
    return {
        "currentFinancialYear": serialize(current_fy) if current_fy else None,
        "totalAssets": total_for("asset", "dr"),
        "totalLiabilities": total_for("liability", "cr"),
        "totalIncome": total_for("income", "cr"),
        "totalExpenses": total_for("expense", "dr"),
        "cashAndBankBalance": float(cash_bank),
        "receivablesPlaceholder": "Pending SRM/FAM posting integration",
        "payablesPlaceholder": "Pending purchase/accounting voucher phase",
        "gstCompliancePlaceholder": "Configured later; no fake GST integration",
        "booksStatus": current_fy.status if current_fy else "open",
        "recentAccountingActivity": [serialize(item) for item in recent],
    }


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMCompanyFinancialSettings).filter(FAMCompanyFinancialSettings.company_id == company_id).first()
    return serialize(item)


@router.put("/settings")
def update_settings(payload: CompanyFinancialSettingsPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_tax_format_placeholders(payload)
    item = db.query(FAMCompanyFinancialSettings).filter(FAMCompanyFinancialSettings.company_id == company_id).first()
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "settings", item.id, "UPDATE", old, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/financial-years")
def list_financial_years(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id).order_by(FAMFinancialYear.start_date.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/financial-years", status_code=status.HTTP_201_CREATED)
def create_financial_year(payload: FinancialYearPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.end_date <= payload.start_date:
        raise HTTPException(status_code=422, detail="Financial year end date must be after start date")
    overlap = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.start_date <= payload.end_date, FAMFinancialYear.end_date >= payload.start_date).first()
    if overlap:
        raise HTTPException(status_code=409, detail="Financial year dates cannot overlap")
    if payload.is_current:
        db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id).update({"is_current": False})
    item = FAMFinancialYear(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "financial_year", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.put("/financial-years/{year_id}")
def update_financial_year(year_id: int, payload: FinancialYearPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id == year_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Financial year not found")
    overlap = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id != year_id, FAMFinancialYear.start_date <= payload.end_date, FAMFinancialYear.end_date >= payload.start_date).first()
    if overlap:
        raise HTTPException(status_code=409, detail="Financial year dates cannot overlap")
    old = serialize(item)
    if payload.is_current:
        db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id != year_id).update({"is_current": False})
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "financial_year", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.post("/financial-years/{year_id}/close")
def close_financial_year(year_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    return set_financial_year_status(year_id, "closed", request, db, current_user)


@router.post("/financial-years/{year_id}/lock")
def lock_financial_year(year_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    return set_financial_year_status(year_id, "locked", request, db, current_user)


def set_financial_year_status(year_id: int, status_value: str, request: Request, db: Session, user: User):
    company_id = bootstrap(db, user)
    item = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id == year_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Financial year not found")
    old = serialize(item)
    item.status = status_value
    audit(db, request, user, company_id, "financial_year", item.id, status_value.upper(), old, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/ledger-groups")
def list_ledger_groups(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id).order_by(FAMLedgerGroup.sequence_order, FAMLedgerGroup.group_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/ledger-groups", status_code=status.HTTP_201_CREATED)
def create_ledger_group(payload: LedgerGroupPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_nature(payload.nature)
    if db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.group_code == payload.group_code).first():
        raise HTTPException(status_code=409, detail="Ledger group code already exists")
    item = FAMLedgerGroup(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "ledger_group", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.put("/ledger-groups/{group_id}")
def update_ledger_group(group_id: int, payload: LedgerGroupPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.id == group_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ledger group not found")
    assert_nature(payload.nature)
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "ledger_group", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.delete("/ledger-groups/{group_id}")
def delete_ledger_group(group_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.id == group_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ledger group not found")
    if item.system_group:
        raise HTTPException(status_code=409, detail="System groups cannot be deleted")
    if db.query(FAMLedger).filter(FAMLedger.ledger_group_id == item.id).first():
        raise HTTPException(status_code=409, detail="Ledger group has ledgers")
    old = serialize(item)
    db.delete(item)
    audit(db, request, current_user, company_id, "ledger_group", group_id, "DELETE", old, None)
    db.commit()
    return {"deleted": True}


@router.get("/ledgers")
def list_ledgers(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMLedger).filter(FAMLedger.company_id == company_id).order_by(FAMLedger.ledger_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/ledgers", status_code=status.HTTP_201_CREATED)
def create_ledger(payload: LedgerPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_tax_format_placeholders(payload)
    assert_ledger_type(payload.ledger_type)
    group = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.id == payload.ledger_group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Ledger group not found")
    nature = payload.nature or group.nature
    assert_nature(nature)
    if db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_code == payload.ledger_code).first():
        raise HTTPException(status_code=409, detail="Ledger code must be unique")
    if db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_name == payload.ledger_name).first():
        raise HTTPException(status_code=409, detail="Ledger name must be unique within company")
    data = payload.model_dump()
    data["nature"] = nature
    item = FAMLedger(company_id=company_id, current_balance_dr=data["opening_balance_dr"], current_balance_cr=data["opening_balance_cr"], **data)
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "ledger", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.put("/ledgers/{ledger_id}")
def update_ledger(ledger_id: int, payload: LedgerPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == ledger_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ledger not found")
    duplicate_code = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id != ledger_id, FAMLedger.ledger_code == payload.ledger_code).first()
    duplicate_name = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id != ledger_id, FAMLedger.ledger_name == payload.ledger_name).first()
    if duplicate_code:
        raise HTTPException(status_code=409, detail="Ledger code must be unique")
    if duplicate_name:
        raise HTTPException(status_code=409, detail="Ledger name must be unique within company")
    old = serialize(item)
    data = payload.model_dump()
    if not data.get("nature"):
        group = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.id == payload.ledger_group_id, FAMLedgerGroup.company_id == company_id).first()
        data["nature"] = group.nature if group else item.nature
    for key, value in data.items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "ledger", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.delete("/ledgers/{ledger_id}")
def delete_ledger(ledger_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == ledger_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ledger not found")
    if db.query(FAMOpeningBalance).filter(FAMOpeningBalance.ledger_id == ledger_id, FAMOpeningBalance.posted == True).first():
        raise HTTPException(status_code=409, detail="Ledgers with transactions cannot be deleted")
    old = serialize(item)
    db.delete(item)
    audit(db, request, current_user, company_id, "ledger", ledger_id, "DELETE", old, None)
    db.commit()
    return {"deleted": True}


@router.get("/opening-balances")
def list_opening_balances(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_OPENING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMOpeningBalance).filter(FAMOpeningBalance.company_id == company_id).order_by(FAMOpeningBalance.id).all()
    debit = sum(Decimal(item.debit_amount or 0) for item in items)
    credit = sum(Decimal(item.credit_amount or 0) for item in items)
    return {"items": [serialize(item) for item in items], "total": len(items), "debitTotal": float(debit), "creditTotal": float(credit), "difference": float(debit - credit)}


@router.post("/opening-balances", status_code=status.HTTP_201_CREATED)
def create_opening_balance(payload: OpeningBalancePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_OPENING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    fy = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.id == payload.financial_year_id).first()
    if not fy:
        raise HTTPException(status_code=404, detail="Financial year not found")
    if fy.status in {"closed", "locked"}:
        raise HTTPException(status_code=409, detail="Closed/locked periods cannot accept postings")
    if Decimal(payload.debit_amount or 0) and Decimal(payload.credit_amount or 0):
        raise HTTPException(status_code=422, detail="Opening balance cannot have both debit and credit")
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.ledger_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")
    item = FAMOpeningBalance(company_id=company_id, created_by=current_user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "opening_balance", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.post("/opening-balances/post")
def post_opening_balances(request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_OPENING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMOpeningBalance).filter(FAMOpeningBalance.company_id == company_id, FAMOpeningBalance.posted == False).all()
    debit = sum(Decimal(item.debit_amount or 0) for item in items)
    credit = sum(Decimal(item.credit_amount or 0) for item in items)
    if debit != credit:
        raise HTTPException(status_code=409, detail="Opening balances must balance before posting")
    for item in items:
        item.posted = True
        ledger = db.query(FAMLedger).filter(FAMLedger.id == item.ledger_id, FAMLedger.company_id == company_id).first()
        if ledger:
            ledger.opening_balance_dr = item.debit_amount
            ledger.opening_balance_cr = item.credit_amount
            ledger.current_balance_dr = item.debit_amount
            ledger.current_balance_cr = item.credit_amount
    audit(db, request, current_user, company_id, "opening_balance", None, "POST", None, {"count": len(items), "debit": float(debit), "credit": float(credit)})
    db.commit()
    return {"posted": True, "count": len(items), "debitTotal": float(debit), "creditTotal": float(credit)}


@router.get("/cost-centers")
def list_cost_centers(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMCostCenter).filter(FAMCostCenter.company_id == company_id).order_by(FAMCostCenter.code).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/cost-centers", status_code=status.HTTP_201_CREATED)
def create_cost_center(payload: CostCenterPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_COST_CENTER_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = FAMCostCenter(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "cost_center", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/branches")
def list_branches(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBranch).filter(FAMBranch.company_id == company_id).order_by(FAMBranch.branch_code).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(payload: BranchPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BRANCH_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_tax_format_placeholders(payload)
    item = FAMBranch(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "branch", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/audit-logs")
def audit_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AUDIT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMAuditLog).filter(FAMAuditLog.company_id == company_id).order_by(FAMAuditLog.performed_at.desc(), FAMAuditLog.id.desc()).limit(100).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/chart-of-accounts")
def chart_of_accounts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CHART_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    groups = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id).order_by(FAMLedgerGroup.sequence_order, FAMLedgerGroup.group_name).all()
    ledgers = db.query(FAMLedger).filter(FAMLedger.company_id == company_id).order_by(FAMLedger.ledger_name).all()
    return {
        "groups": [serialize(item) for item in groups],
        "ledgers": [serialize(item) for item in ledgers],
        "totalGroups": len(groups),
        "totalLedgers": len(ledgers),
    }


@router.get("/voucher-types")
def list_voucher_types(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id).order_by(FAMVoucherType.id).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/voucher-types", status_code=status.HTTP_201_CREATED)
def create_voucher_type(payload: VoucherTypePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_TYPE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    validate_voucher_type(payload.category)
    if db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id, FAMVoucherType.voucher_type_code == payload.voucher_type_code).first():
        raise HTTPException(status_code=409, detail="Voucher type code already exists")
    item = FAMVoucherType(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "voucher_type", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.put("/voucher-types/{id}")
def update_voucher_type(id: int, payload: VoucherTypePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_TYPE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id, FAMVoucherType.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Voucher type not found")
    validate_voucher_type(payload.category)
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "voucher_type", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/vouchers")
def list_vouchers(status_filter: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    query = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id)
    if status_filter:
        query = query.filter(FAMVoucher.status == status_filter)
    items = query.order_by(FAMVoucher.voucher_date.desc(), FAMVoucher.id.desc()).limit(200).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/vouchers", status_code=status.HTTP_201_CREATED)
def create_voucher(payload: VoucherPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_CREATE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    fy, period, voucher_type, debit, credit = validate_voucher_payload(db, company_id, payload, for_posting=False)
    voucher_number = payload.voucher_number or next_voucher_number(voucher_type)
    if db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.voucher_number == voucher_number).first():
        raise HTTPException(status_code=409, detail="Voucher number already exists")
    voucher = FAMVoucher(
        company_id=company_id,
        financial_year_id=fy.id,
        accounting_period_id=period.id if period else None,
        branch_id=payload.branch_id,
        voucher_type_id=voucher_type.id,
        voucher_number=voucher_number,
        voucher_date=payload.voucher_date,
        reference_number=payload.reference_number,
        reference_date=payload.reference_date,
        narration=payload.narration,
        total_debit=debit,
        total_credit=credit,
        status="draft",
        source_module=payload.source_module,
        source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id,
    )
    db.add(voucher)
    db.flush()
    for index, line in enumerate(payload.lines, start=1):
        db.add(FAMVoucherLine(voucher_id=voucher.id, line_number=index, **line.model_dump()))
    if voucher_type.auto_numbering and not payload.voucher_number:
        voucher_type.numbering_sequence = int(voucher_type.numbering_sequence or 1) + 1
    voucher_audit(db, voucher.id, "CREATE", current_user, None, serialize_voucher(db, voucher))
    audit(db, request, current_user, company_id, "voucher", voucher.id, "CREATE", None, serialize(voucher))
    db.commit()
    return serialize_voucher(db, voucher)


@router.get("/vouchers/{id}")
def get_voucher(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    return serialize_voucher(db, voucher)


@router.put("/vouchers/{id}")
def update_voucher(id: int, payload: VoucherUpdatePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_CREATE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != "draft":
        raise HTTPException(status_code=409, detail="Posted/cancelled/reversed vouchers cannot be silently edited")
    old = serialize_voucher(db, voucher)
    fy, period, voucher_type, debit, credit = validate_voucher_payload(db, company_id, payload, for_posting=False)
    voucher.financial_year_id = fy.id
    voucher.accounting_period_id = period.id if period else None
    voucher.branch_id = payload.branch_id
    voucher.voucher_type_id = voucher_type.id
    voucher.voucher_date = payload.voucher_date
    voucher.reference_number = payload.reference_number
    voucher.reference_date = payload.reference_date
    voucher.narration = payload.narration
    voucher.total_debit = debit
    voucher.total_credit = credit
    voucher.source_module = payload.source_module
    voucher.source_record_type = payload.source_record_type
    voucher.source_record_id = payload.source_record_id
    db.query(FAMVoucherLine).filter(FAMVoucherLine.voucher_id == voucher.id).delete()
    db.flush()
    for index, line in enumerate(payload.lines, start=1):
        db.add(FAMVoucherLine(voucher_id=voucher.id, line_number=index, **line.model_dump()))
    voucher_audit(db, voucher.id, "UPDATE", current_user, old, serialize_voucher(db, voucher))
    audit(db, request, current_user, company_id, "voucher", voucher.id, "UPDATE", old, serialize(voucher))
    db.commit()
    return serialize_voucher(db, voucher)


@router.post("/vouchers/{id}/post")
def post_voucher(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_POST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft vouchers can be posted")
    payload = payload_from_voucher(db, voucher)
    fy, period, _voucher_type, debit, credit = validate_voucher_payload(db, company_id, payload, for_posting=True)
    old = serialize_voucher(db, voucher)
    posted_at = datetime.now(timezone.utc)
    voucher.financial_year_id = fy.id
    voucher.accounting_period_id = period.id if period else None
    voucher.total_debit = debit
    voucher.total_credit = credit
    voucher.status = "posted"
    voucher.posted_by = current_user.id
    voucher.posted_at = posted_at
    for line in voucher_lines(db, voucher.id):
        ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == line.ledger_id).first()
        running = apply_ledger_movement(ledger, Decimal(line.debit_amount or 0), Decimal(line.credit_amount or 0))
        db.add(
            FAMLedgerEntry(
                company_id=company_id,
                financial_year_id=fy.id,
                accounting_period_id=period.id if period else None,
                voucher_id=voucher.id,
                voucher_line_id=line.id,
                voucher_number=voucher.voucher_number,
                voucher_date=voucher.voucher_date,
                ledger_id=line.ledger_id,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                running_balance=running,
                narration=line.narration or voucher.narration,
                source_module=voucher.source_module,
                source_record_type=voucher.source_record_type,
                source_record_id=voucher.source_record_id,
                posted_at=posted_at,
            )
        )
    voucher_audit(db, voucher.id, "POST", current_user, old, serialize_voucher(db, voucher))
    audit(db, request, current_user, company_id, "voucher", voucher.id, "POST", old, serialize(voucher))
    db.commit()
    return serialize_voucher(db, voucher)


@router.post("/vouchers/{id}/cancel")
def cancel_voucher(id: int, payload: VoucherCancelPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_CANCEL_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status not in {"draft", "posted"}:
        raise HTTPException(status_code=409, detail="Only draft or posted vouchers can be cancelled")
    old = serialize_voucher(db, voucher)
    voucher.status = "cancelled"
    voucher.cancelled_by = current_user.id
    voucher.cancelled_at = datetime.now(timezone.utc)
    voucher.cancellation_reason = payload.reason
    voucher_audit(db, voucher.id, "CANCEL", current_user, old, serialize_voucher(db, voucher))
    audit(db, request, current_user, company_id, "voucher", voucher.id, "CANCEL", old, serialize(voucher))
    db.commit()
    return serialize_voucher(db, voucher)


@router.post("/vouchers/{id}/reverse", status_code=status.HTTP_201_CREATED)
def reverse_voucher(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_REVERSE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted vouchers can be reversed")
    existing = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.reversed_voucher_id == voucher.id).first()
    if existing:
        return serialize_voucher(db, existing)
    old = serialize_voucher(db, voucher)
    reverse_number = f"REV-{voucher.voucher_number}"
    reverse = FAMVoucher(
        company_id=company_id,
        financial_year_id=voucher.financial_year_id,
        accounting_period_id=voucher.accounting_period_id,
        branch_id=voucher.branch_id,
        voucher_type_id=voucher.voucher_type_id,
        voucher_number=reverse_number,
        voucher_date=voucher.voucher_date,
        reference_number=voucher.voucher_number,
        reference_date=voucher.voucher_date,
        narration=f"Reversal of {voucher.voucher_number}",
        total_debit=voucher.total_credit,
        total_credit=voucher.total_debit,
        status="draft",
        source_module=voucher.source_module,
        source_record_type=voucher.source_record_type,
        source_record_id=voucher.source_record_id,
        reversed_voucher_id=voucher.id,
    )
    db.add(reverse)
    db.flush()
    for index, line in enumerate(voucher_lines(db, voucher.id), start=1):
        db.add(
            FAMVoucherLine(
                voucher_id=reverse.id,
                line_number=index,
                ledger_id=line.ledger_id,
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                narration=f"Reverse: {line.narration or voucher.narration or ''}".strip(),
                cost_center_id=line.cost_center_id,
                branch_id=line.branch_id,
                party_id=line.party_id,
                tax_component_id=line.tax_component_id,
            )
        )
    voucher.status = "reversed"
    voucher.reversed_voucher_id = reverse.id
    voucher_audit(db, voucher.id, "REVERSE", current_user, old, serialize_voucher(db, voucher))
    voucher_audit(db, reverse.id, "CREATE_REVERSAL", current_user, None, serialize_voucher(db, reverse))
    audit(db, request, current_user, company_id, "voucher", voucher.id, "REVERSE", old, serialize(voucher))
    db.commit()
    return serialize_voucher(db, reverse)


@router.post("/vouchers/{id}/clone", status_code=status.HTTP_201_CREATED)
def clone_voucher(id: int, payload: VoucherClonePayload | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VOUCHER_CREATE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    voucher_type = db.query(FAMVoucherType).filter(FAMVoucherType.id == voucher.voucher_type_id, FAMVoucherType.company_id == company_id).first()
    clone_date = payload.voucher_date if payload and payload.voucher_date else voucher.voucher_date
    fy = find_financial_year_for_date(db, company_id, clone_date)
    period = find_period_for_date(db, fy, clone_date)
    clone = FAMVoucher(company_id=company_id, financial_year_id=fy.id, accounting_period_id=period.id if period else None, branch_id=voucher.branch_id, voucher_type_id=voucher.voucher_type_id, voucher_number=next_voucher_number(voucher_type), voucher_date=clone_date, narration=(payload.narration if payload and payload.narration else f"Clone of {voucher.voucher_number}"), total_debit=voucher.total_debit, total_credit=voucher.total_credit, status="draft", source_module="fam", source_record_type="voucher_clone", source_record_id=str(voucher.id))
    db.add(clone)
    db.flush()
    voucher_type.numbering_sequence = int(voucher_type.numbering_sequence or 1) + 1
    for index, line in enumerate(voucher_lines(db, voucher.id), start=1):
        db.add(FAMVoucherLine(voucher_id=clone.id, line_number=index, ledger_id=line.ledger_id, debit_amount=line.debit_amount, credit_amount=line.credit_amount, narration=line.narration, cost_center_id=line.cost_center_id, branch_id=line.branch_id, party_id=line.party_id, tax_component_id=line.tax_component_id))
    voucher_audit(db, clone.id, "CLONE", current_user, None, serialize_voucher(db, clone))
    db.commit()
    return serialize_voucher(db, clone)


@router.get("/ledger-entries")
def ledger_entries(ledger_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_LEDGER_ENTRY_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    query = db.query(FAMLedgerEntry).filter(FAMLedgerEntry.company_id == company_id)
    if ledger_id:
        query = query.filter(FAMLedgerEntry.ledger_id == ledger_id)
    items = query.order_by(FAMLedgerEntry.voucher_date.desc(), FAMLedgerEntry.id.desc()).limit(500).all()
    debit = sum(Decimal(item.debit_amount or 0) for item in items)
    credit = sum(Decimal(item.credit_amount or 0) for item in items)
    return {"items": [serialize(item) for item in items], "total": len(items), "debitTotal": float(debit), "creditTotal": float(credit)}


@router.get("/ledgers/{id}/entries")
def ledger_entries_for_ledger(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_LEDGER_ENTRY_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")
    entries = db.query(FAMLedgerEntry).filter(FAMLedgerEntry.company_id == company_id, FAMLedgerEntry.ledger_id == id).order_by(FAMLedgerEntry.voucher_date, FAMLedgerEntry.id).all()
    debit = sum(Decimal(item.debit_amount or 0) for item in entries)
    credit = sum(Decimal(item.credit_amount or 0) for item in entries)
    opening = Decimal(ledger.opening_balance_dr or 0) - Decimal(ledger.opening_balance_cr or 0)
    return {"ledger": serialize(ledger), "items": [serialize(item) for item in entries], "openingBalance": float(opening), "debitMovement": float(debit), "creditMovement": float(credit), "closingBalance": float(opening + debit - credit)}


@router.get("/day-book")
def day_book(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_DAY_BOOK_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id).order_by(FAMVoucher.voucher_date.desc(), FAMVoucher.id.desc()).limit(300).all()
    debit = sum(Decimal(item.total_debit or 0) for item in items)
    credit = sum(Decimal(item.total_credit or 0) for item in items)
    return {"items": [serialize(item) for item in items], "total": len(items), "debitTotal": float(debit), "creditTotal": float(credit)}


@router.get("/voucher-audit/{id}")
def voucher_audit_logs(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AUDIT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    items = db.query(FAMVoucherAuditLog).filter(FAMVoucherAuditLog.voucher_id == id).order_by(FAMVoucherAuditLog.performed_at.desc(), FAMVoucherAuditLog.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/parties")
def list_parties(party_type: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    query = db.query(FAMParty).filter(FAMParty.company_id == company_id)
    if party_type:
        query = query.filter(or_(FAMParty.party_type == party_type, FAMParty.party_type == "both"))
    items = query.order_by(FAMParty.legal_name).all()
    return {"items": [serialize_party(db, item) for item in items], "total": len(items)}


@router.post("/parties", status_code=status.HTTP_201_CREATED)
def create_party(payload: PartyPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_party_payload(db, company_id, payload)
    if db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.party_code == payload.party_code).first():
        raise HTTPException(status_code=409, detail="Party code already exists")
    data = payload.model_dump(exclude={"contacts", "create_ledger"})
    party = FAMParty(company_id=company_id, **data)
    db.add(party)
    db.flush()
    if payload.create_ledger:
        create_party_ledger(db, company_id, party)
    for contact in payload.contacts:
        db.add(FAMPartyContact(party_id=party.id, **contact.model_dump()))
    audit(db, request, current_user, company_id, "party", party.id, "CREATE", None, serialize_party(db, party))
    db.commit()
    return serialize_party(db, party)


@router.get("/parties/{id}")
def get_party(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    return serialize_party(db, party)


@router.put("/parties/{id}")
def update_party(id: int, payload: PartyPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    assert_party_payload(db, company_id, payload)
    old = serialize_party(db, party)
    for key, value in payload.model_dump(exclude={"contacts", "create_ledger"}).items():
        setattr(party, key, value)
    db.query(FAMPartyContact).filter(FAMPartyContact.party_id == party.id).delete()
    for contact in payload.contacts:
        db.add(FAMPartyContact(party_id=party.id, **contact.model_dump()))
    audit(db, request, current_user, company_id, "party", party.id, "UPDATE", old, serialize_party(db, party))
    db.commit()
    return serialize_party(db, party)


@router.post("/parties/{id}/create-ledger")
def create_ledger_for_party(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    old = serialize_party(db, party)
    ledger = create_party_ledger(db, company_id, party)
    audit(db, request, current_user, company_id, "party", party.id, "CREATE_LEDGER", old, serialize_party(db, party))
    db.commit()
    return {"party": serialize_party(db, party), "ledger": serialize(ledger)}


@router.get("/parties/{id}/bill-references")
def party_bill_references(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTY_STATEMENT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.party_id == id).order_by(FAMBillReference.due_date).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/parties/{id}/outstanding")
def party_outstanding(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTY_STATEMENT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.party_id == id, FAMBillReference.outstanding_amount > 0).all()
    total = sum(Decimal(item.outstanding_amount or 0) for item in items)
    return {"party_id": id, "outstanding": float(total), "openBills": len(items), "items": [serialize(item) for item in items]}


@router.get("/parties/{id}/statement")
def party_statement(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTY_STATEMENT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    bills = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.party_id == id).order_by(FAMBillReference.bill_date).all()
    allocations = db.query(FAMBillAllocation).filter(FAMBillAllocation.company_id == company_id, FAMBillAllocation.party_id == id).order_by(FAMBillAllocation.allocation_date).all()
    return {"party": serialize_party(db, party), "billReferences": [serialize(item) for item in bills], "allocations": [serialize(item) for item in allocations], "outstanding": float(sum(Decimal(item.outstanding_amount or 0) for item in bills))}


@router.post("/bill-references", status_code=status.HTTP_201_CREATED)
def create_bill_reference(payload: BillReferencePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AR_MANAGE_PERMISSIONS, *FAM_AP_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.bill_type not in VALID_BILL_TYPES:
        raise HTTPException(status_code=422, detail="Invalid bill type")
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == payload.party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.party_id == payload.party_id, FAMBillReference.bill_number == payload.bill_number).first():
        raise HTTPException(status_code=409, detail="Bill reference already exists for this party")
    ledger_id = payload.ledger_id or party.ledger_id
    if not ledger_id:
        raise HTTPException(status_code=422, detail="Party ledger is required")
    if payload.original_amount <= 0:
        raise HTTPException(status_code=422, detail="Bill amount must be positive")
    due_date = payload.due_date or (payload.bill_date + timedelta(days=int(party.payment_terms_days or 0)))
    outstanding = payload.outstanding_amount if payload.outstanding_amount is not None else payload.original_amount
    item = FAMBillReference(company_id=company_id, ledger_id=ledger_id, due_date=due_date, outstanding_amount=outstanding, status=bill_status(Decimal(outstanding)), **payload.model_dump(exclude={"ledger_id", "due_date", "outstanding_amount"}))
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "bill_reference", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/bill-references")
def list_bill_references(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTY_STATEMENT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id).order_by(FAMBillReference.due_date, FAMBillReference.id).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/bill-allocations", status_code=status.HTTP_201_CREATED)
def create_bill_allocation(payload: BillAllocationPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BILL_ALLOCATION_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.allocation_type not in VALID_ALLOCATION_TYPES:
        raise HTTPException(status_code=422, detail="Invalid allocation type")
    amount = Decimal(payload.allocated_amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Allocation amount must be positive")
    from_bill = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.id == payload.from_bill_reference_id, FAMBillReference.party_id == payload.party_id).first()
    to_bill = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.id == payload.to_bill_reference_id, FAMBillReference.party_id == payload.party_id).first()
    if not from_bill or not to_bill:
        raise HTTPException(status_code=404, detail="Bill reference not found")
    if amount > Decimal(to_bill.outstanding_amount or 0):
        raise HTTPException(status_code=409, detail="Allocation exceeds target outstanding")
    to_bill.outstanding_amount = Decimal(to_bill.outstanding_amount or 0) - amount
    to_bill.status = bill_status(Decimal(to_bill.outstanding_amount or 0))
    from_bill.outstanding_amount = max(Decimal(from_bill.outstanding_amount or 0) - amount, Decimal("0"))
    from_bill.status = bill_status(Decimal(from_bill.outstanding_amount or 0))
    item = FAMBillAllocation(company_id=company_id, created_by=current_user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "bill_allocation", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/bill-allocations")
def list_bill_allocations(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTY_STATEMENT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBillAllocation).filter(FAMBillAllocation.company_id == company_id).order_by(FAMBillAllocation.allocation_date.desc(), FAMBillAllocation.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/party-credit-terms")
def list_party_credit_terms(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPartyCreditTerm).join(FAMParty, FAMParty.id == FAMPartyCreditTerm.party_id).filter(FAMParty.company_id == company_id).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/party-credit-terms", status_code=status.HTTP_201_CREATED)
def create_party_credit_term(payload: PartyCreditTermPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PARTIES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    party = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == payload.party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    item = FAMPartyCreditTerm(**payload.model_dump())
    db.add(item)
    db.commit()
    return serialize(item)


@router.get("/ar/aging")
def ar_aging(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AR_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return aging_payload(bill_query_for(db, company_id, True).all(), date.today())


@router.get("/ap/aging")
def ap_aging(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AP_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return aging_payload(bill_query_for(db, company_id, False).all(), date.today())


@router.get("/ar/outstanding")
def ar_outstanding(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AR_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = bill_query_for(db, company_id, True).order_by(FAMBillReference.due_date).all()
    return {"items": [serialize(item) for item in items], "totalOutstanding": float(sum(Decimal(item.outstanding_amount or 0) for item in items))}


@router.get("/ap/outstanding")
def ap_outstanding(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AP_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = bill_query_for(db, company_id, False).order_by(FAMBillReference.due_date).all()
    return {"items": [serialize(item) for item in items], "totalOutstanding": float(sum(Decimal(item.outstanding_amount or 0) for item in items))}


@router.get("/integrations/srm/status")
def srm_integration_status(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_INTEGRATION_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    today = date.today()
    pending = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.status == "pending").count()
    failed = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.status == "failed").count()
    posted_today = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.status.in_(["posted", "reversed"]), FAMPostingJob.posted_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc)).count()
    mapped_customers = db.query(FAMSRMMapping).filter(FAMSRMMapping.company_id == company_id, FAMSRMMapping.srm_record_type == "customer", FAMSRMMapping.fam_record_type == "party").count()
    invoice_count = db.query(SRMInvoice).filter(SRMInvoice.deleted_at == None).count()
    return {
        "pending_postings": pending,
        "failed_postings": failed,
        "posted_today": posted_today,
        "unmapped_customers": max(invoice_count - mapped_customers, 0),
        "duplicate_prevention_status": "active",
        "recent_jobs": [serialize(item) for item in db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id).order_by(FAMPostingJob.id.desc()).limit(10).all()],
    }


@router.get("/integrations/srm/accounting-status/{source_record_type}/{source_record_id}")
def srm_accounting_status(source_record_type: str, source_record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_ACCOUNTING_STATUS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return source_status(db, company_id, source_record_type, source_record_id)


@router.post("/integrations/srm/post-invoice/{invoice_id}")
def post_srm_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_POSTING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return post_srm_invoice_to_fam(db, request, current_user, company_id, invoice_id)


@router.post("/integrations/srm/post-receipt/{receipt_id}")
def post_srm_receipt(receipt_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_POSTING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return post_srm_receipt_to_fam(db, request, current_user, company_id, receipt_id)


@router.post("/integrations/srm/post-allocation/{allocation_id}")
def post_srm_allocation(allocation_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_POSTING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return post_srm_allocation_to_fam(db, request, current_user, company_id, allocation_id)


@router.post("/integrations/srm/reverse/{source_record_type}/{source_record_id}")
def reverse_srm_accounting(source_record_type: str, source_record_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_POSTING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return reverse_srm_posting(db, request, current_user, company_id, source_record_type, source_record_id)


@router.get("/posting-jobs")
def list_posting_jobs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_INTEGRATION_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id).order_by(FAMPostingJob.id.desc()).limit(200).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/posting-jobs/{id}")
def get_posting_job(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_INTEGRATION_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Posting job not found")
    return serialize(item) | {"accountingStatus": source_status(db, company_id, item.source_record_type, item.source_record_id)}


@router.post("/posting-jobs/{id}/retry")
def retry_posting_job(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_POSTING_JOBS_RETRY_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMPostingJob).filter(FAMPostingJob.company_id == company_id, FAMPostingJob.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Posting job not found")
    item.retry_count = int(item.retry_count or 0) + 1
    item.status = "pending"
    db.flush()
    if item.posting_type == "sales_invoice":
        return post_srm_invoice_to_fam(db, request, current_user, company_id, item.source_record_id)
    if item.posting_type == "receipt":
        return post_srm_receipt_to_fam(db, request, current_user, company_id, item.source_record_id)
    if item.posting_type == "allocation":
        return post_srm_allocation_to_fam(db, request, current_user, company_id, item.source_record_id)
    if item.posting_type == "reversal":
        return reverse_srm_posting(db, request, current_user, company_id, item.source_record_type, item.source_record_id)
    raise HTTPException(status_code=422, detail="Unsupported posting job type")


@router.get("/posting-rules")
def list_posting_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_SRM_INTEGRATION_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPostingRule).filter(FAMPostingRule.company_id == company_id).order_by(FAMPostingRule.transaction_type).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/posting-rules", status_code=status.HTTP_201_CREATED)
def create_posting_rule(payload: PostingRulePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_POSTING_RULES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if db.query(FAMPostingRule).filter(FAMPostingRule.company_id == company_id, FAMPostingRule.source_module == payload.source_module, FAMPostingRule.transaction_type == payload.transaction_type).first():
        raise HTTPException(status_code=409, detail="Posting rule already exists")
    item = FAMPostingRule(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "posting_rule", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.put("/posting-rules/{id}")
def update_posting_rule(id: int, payload: PostingRulePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_POSTING_RULES_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMPostingRule).filter(FAMPostingRule.company_id == company_id, FAMPostingRule.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Posting rule not found")
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "posting_rule", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/bank-accounts")
def list_bank_accounts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id).order_by(FAMBankAccount.bank_name, FAMBankAccount.id).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED)
def create_bank_account(payload: BankAccountPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.ledger_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Bank ledger not found")
    if ledger.ledger_type != "bank":
        raise HTTPException(status_code=422, detail="Bank account must be linked to a bank ledger")
    if db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.ledger_id == payload.ledger_id).first():
        raise HTTPException(status_code=409, detail="Bank account already exists for this ledger")
    item = FAMBankAccount(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "bank_account", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/bank-accounts/{id}")
def get_bank_account(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return serialize(item)


@router.put("/bank-accounts/{id}")
def update_bank_account(id: int, payload: BankAccountPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.ledger_id).first()
    if not ledger or ledger.ledger_type != "bank":
        raise HTTPException(status_code=422, detail="Bank account must be linked to a bank ledger")
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, request, current_user, company_id, "bank_account", item.id, "UPDATE", old, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/payment-modes")
def list_payment_modes(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPaymentMode).filter(FAMPaymentMode.company_id == company_id).order_by(FAMPaymentMode.name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/payment-modes", status_code=status.HTTP_201_CREATED)
def create_payment_mode(payload: PaymentModePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    assert_payment_mode_type(payload.type)
    if payload.default_ledger_id and not db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.default_ledger_id).first():
        raise HTTPException(status_code=404, detail="Default ledger not found")
    if db.query(FAMPaymentMode).filter(FAMPaymentMode.company_id == company_id, FAMPaymentMode.name == payload.name).first():
        raise HTTPException(status_code=409, detail="Payment mode already exists")
    item = FAMPaymentMode(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, request, current_user, company_id, "payment_mode", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/bank-book")
def bank_book(ledger_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_BOOK_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    return ledger_book_payload(db, company_id, {"bank"}, ledger_id)


@router.get("/cash-book")
def cash_book(ledger_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_CASH_BOOK_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    registers = db.query(FAMCashRegister).filter(FAMCashRegister.company_id == company_id).all()
    payload = ledger_book_payload(db, company_id, {"cash"}, ledger_id)
    payload["registers"] = [serialize(item) for item in registers]
    return payload


@router.post("/bank-statements/import", status_code=status.HTTP_201_CREATED)
def import_bank_statement(payload: BankStatementImportPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_STATEMENT_IMPORT_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    account = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == payload.bank_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    if payload.statement_period_end < payload.statement_period_start:
        raise HTTPException(status_code=422, detail="Statement end date must be after start date")
    normalized_lines = normalize_statement_lines(payload)
    file_hash = statement_hash(payload, normalized_lines)
    if db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.bank_account_id == account.id, FAMBankStatement.imported_file_hash == file_hash).first():
        raise HTTPException(status_code=409, detail="Duplicate bank statement import detected")
    statement = FAMBankStatement(company_id=company_id, bank_account_id=account.id, statement_period_start=payload.statement_period_start, statement_period_end=payload.statement_period_end, imported_file_name=payload.imported_file_name, imported_file_hash=file_hash, status="imported", imported_by=current_user.id)
    db.add(statement)
    db.flush()
    seen: set[str] = set()
    for line in normalized_lines:
        if line["line_hash"] in seen:
            raise HTTPException(status_code=409, detail="Duplicate statement line detected in import")
        seen.add(line["line_hash"])
        db.add(FAMBankStatementLine(statement_id=statement.id, **line))
    audit(db, request, current_user, company_id, "bank_statement", statement.id, "IMPORT", None, {"file": payload.imported_file_name, "line_count": len(normalized_lines)})
    db.commit()
    db.refresh(statement)
    return serialize_statement(db, statement)


@router.get("/bank-statements")
def list_bank_statements(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id).order_by(FAMBankStatement.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/bank-statements/{id}")
def get_bank_statement(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statement = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.id == id).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    return serialize_statement(db, statement)


@router.post("/bank-statements/{id}/auto-match")
def auto_match_bank_statement(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_RECONCILE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statement = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.id == id).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    account = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == statement.bank_account_id).first()
    suggestions = []
    for line in statement_lines(db, statement.id):
        if line.matched_status in {"matched", "ignored"}:
            continue
        candidate, score = best_match_for_line(db, company_id, account.ledger_id, line)
        if candidate:
            match = db.query(FAMBankReconciliationMatch).filter(FAMBankReconciliationMatch.statement_line_id == line.id, FAMBankReconciliationMatch.voucher_id == candidate.voucher_id).first()
            if not match:
                match = FAMBankReconciliationMatch(statement_line_id=line.id, voucher_id=candidate.voucher_id, ledger_entry_id=candidate.id, match_type="auto_suggested", confidence_score=score, matched_amount=Decimal(line.credit_amount or 0) or Decimal(line.debit_amount or 0))
                db.add(match)
            line.matched_status = "suggested"
            line.matched_voucher_id = candidate.voucher_id
            suggestions.append({"statement_line_id": line.id, "voucher_id": candidate.voucher_id, "ledger_entry_id": candidate.id, "confidence_score": float(score)})
    statement.status = "matched" if suggestions else statement.status
    audit(db, request, current_user, company_id, "bank_statement", statement.id, "AUTO_MATCH", None, {"suggestions": suggestions})
    db.commit()
    return {"statement": serialize_statement(db, statement), "suggestions": suggestions}


@router.post("/bank-statements/{id}/match")
def match_bank_statement_line(id: int, payload: BankStatementMatchPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_RECONCILE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statement = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.id == id).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    line = db.query(FAMBankStatementLine).filter(FAMBankStatementLine.statement_id == statement.id, FAMBankStatementLine.id == payload.statement_line_id).first()
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == payload.voucher_id, FAMVoucher.status == "posted").first()
    if not line or not voucher:
        raise HTTPException(status_code=404, detail="Statement line or posted voucher not found")
    amount = payload.matched_amount or (Decimal(line.credit_amount or 0) or Decimal(line.debit_amount or 0))
    match = db.query(FAMBankReconciliationMatch).filter(FAMBankReconciliationMatch.statement_line_id == line.id, FAMBankReconciliationMatch.voucher_id == voucher.id).first()
    if not match:
        match = FAMBankReconciliationMatch(statement_line_id=line.id, voucher_id=voucher.id, ledger_entry_id=payload.ledger_entry_id, match_type="manual", confidence_score=Decimal("100"), matched_amount=amount)
        db.add(match)
    match.match_type = "confirmed" if payload.confirm else "manual"
    match.confidence_score = Decimal("100")
    match.matched_amount = amount
    match.matched_by = current_user.id
    match.matched_at = datetime.now(timezone.utc)
    line.matched_status = "matched" if payload.confirm else "suggested"
    line.matched_voucher_id = voucher.id
    statement.status = "matched"
    audit(db, request, current_user, company_id, "bank_statement_line", line.id, "MATCH", None, serialize(match))
    db.commit()
    return {"statement": serialize_statement(db, statement), "match": serialize(match)}


@router.post("/bank-statements/{id}/ignore-line")
def ignore_bank_statement_line(id: int, payload: BankStatementIgnoreLinePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_RECONCILE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statement = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.id == id).first()
    line = db.query(FAMBankStatementLine).filter(FAMBankStatementLine.statement_id == id, FAMBankStatementLine.id == payload.statement_line_id).first() if statement else None
    if not statement or not line:
        raise HTTPException(status_code=404, detail="Statement line not found")
    old = serialize(line)
    line.matched_status = "ignored"
    audit(db, request, current_user, company_id, "bank_statement_line", line.id, "IGNORE", old, {"reason": payload.reason, **serialize(line)})
    db.commit()
    return {"statement": serialize_statement(db, statement), "line": serialize(line)}


@router.post("/bank-statements/{id}/reconcile")
def reconcile_bank_statement(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANK_RECONCILE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statement = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id, FAMBankStatement.id == id).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    lines = statement_lines(db, statement.id)
    if [line for line in lines if line.matched_status not in {"matched", "ignored"}]:
        raise HTTPException(status_code=409, detail="Cannot reconcile while statement has unmatched lines")
    account = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == statement.bank_account_id).first()
    book = ledger_book_payload(db, company_id, {"bank"}, account.ledger_id)
    bank_balance = Decimal(lines[-1].balance or 0) if lines else Decimal("0")
    session = FAMBankReconciliationSession(company_id=company_id, bank_account_id=account.id, statement_id=statement.id, book_balance=Decimal(str(book["closingBalance"])), bank_statement_balance=bank_balance, unreconciled_count=0, status="reconciled", reconciled_by=current_user.id, reconciled_at=datetime.now(timezone.utc))
    db.add(session)
    statement.status = "reconciled"
    audit(db, request, current_user, company_id, "bank_statement", statement.id, "RECONCILE", None, serialize(session))
    db.commit()
    db.refresh(session)
    return {"statement": serialize_statement(db, statement), "session": serialize(session)}


@router.get("/bank-reconciliation")
def bank_reconciliation(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    statements = db.query(FAMBankStatement).filter(FAMBankStatement.company_id == company_id).order_by(FAMBankStatement.id.desc()).all()
    sessions = db.query(FAMBankReconciliationSession).filter(FAMBankReconciliationSession.company_id == company_id).order_by(FAMBankReconciliationSession.id.desc()).all()
    unmatched = sum(db.query(FAMBankStatementLine).filter(FAMBankStatementLine.statement_id == statement.id, FAMBankStatementLine.matched_status == "unmatched").count() for statement in statements)
    return {"statements": [serialize(item) for item in statements], "sessions": [serialize(item) for item in sessions], "unmatched_count": unmatched}


@router.post("/bank-charges/post", status_code=status.HTTP_201_CREATED)
def post_bank_charges(payload: BankChargePostPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    account = db.query(FAMBankAccount).filter(FAMBankAccount.company_id == company_id, FAMBankAccount.id == payload.bank_account_id).first()
    expense = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.expense_ledger_id).first()
    if not account or not expense:
        raise HTTPException(status_code=404, detail="Bank account or expense ledger not found")
    amount = Decimal(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Bank charge amount must be positive")
    voucher = create_and_post_voucher(db, request, current_user, company_id, "PV", payload.charge_date, payload.reference_number or f"BANK-CHARGE-{payload.bank_account_id}", payload.narration, "bank_charge", account.id, [{"ledger_id": expense.id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": payload.narration}, {"ledger_id": account.ledger_id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": payload.narration}], source_module="fam")
    db.commit()
    return serialize_voucher(db, voucher)


@router.post("/contra/post", status_code=status.HTTP_201_CREATED)
def post_contra(payload: ContraPostPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    from_ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.from_ledger_id).first()
    to_ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == payload.to_ledger_id).first()
    if not from_ledger or not to_ledger:
        raise HTTPException(status_code=404, detail="Contra ledger not found")
    if from_ledger.ledger_type not in {"bank", "cash"} or to_ledger.ledger_type not in {"bank", "cash"}:
        raise HTTPException(status_code=422, detail="Contra entries must move money between bank/cash ledgers")
    amount = Decimal(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Contra amount must be positive")
    voucher = create_and_post_voucher(db, request, current_user, company_id, "CV", payload.contra_date, payload.reference_number or f"CONTRA-{from_ledger.id}-{to_ledger.id}", payload.narration, "contra", from_ledger.id, [{"ledger_id": to_ledger.id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": payload.narration}, {"ledger_id": from_ledger.id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": payload.narration}], source_module="fam")
    db.commit()
    return serialize_voucher(db, voucher)


def gst_audit(db: Session, user: User, company_id: int, record_type: str, record_id: int | None, action: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> None:
    db.add(FAMGSTAuditLog(company_id=company_id, record_type=record_type, record_id=record_id, action=action, old_value_json=old, new_value_json=new, performed_by=user.id, performed_at=datetime.now(timezone.utc)))


def gst_rate_values(db: Session, company_id: int, payload: GSTCalculationPayload) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if payload.gst_rate_id:
        rate = db.query(FAMGSTRate).filter(FAMGSTRate.company_id == company_id, FAMGSTRate.id == payload.gst_rate_id, FAMGSTRate.active == True).first()
        if not rate:
            raise HTTPException(status_code=404, detail="GST rate not found")
        return Decimal(rate.cgst_rate or 0), Decimal(rate.sgst_rate or 0), Decimal(rate.igst_rate or 0), Decimal(rate.cess_rate or 0)
    return Decimal(payload.cgst_rate or 0), Decimal(payload.sgst_rate or 0), Decimal(payload.igst_rate or 0), Decimal(payload.cess_rate or 0)


def calculate_gst_amounts(db: Session, company_id: int, payload: GSTCalculationPayload) -> dict[str, Any]:
    if payload.supply_type not in VALID_GST_SUPPLY_TYPES or payload.transaction_type not in VALID_GST_TRANSACTION_TYPES or payload.exempt_type not in VALID_GST_EXEMPT_TYPES:
        raise HTTPException(status_code=422, detail="Invalid GST classification")
    taxable = Decimal(payload.taxable_value)
    if taxable < 0:
        raise HTTPException(status_code=422, detail="Taxable value cannot be negative")
    cgst_rate, sgst_rate, igst_rate, cess_rate = gst_rate_values(db, company_id, payload)
    zero_tax = payload.exempt_type in {"exempt", "nil", "zero_rated", "out_of_scope"} or payload.supply_type in {"export", "sez"}
    interstate = payload.company_state_code != payload.place_of_supply_state or payload.supply_type in {"export", "sez"}
    if zero_tax:
        cgst = sgst = igst = cess = Decimal("0")
    elif interstate:
        cgst = sgst = Decimal("0")
        igst = (taxable * igst_rate / Decimal("100")).quantize(Decimal("0.01"))
        cess = (taxable * cess_rate / Decimal("100")).quantize(Decimal("0.01"))
    else:
        cgst = (taxable * cgst_rate / Decimal("100")).quantize(Decimal("0.01"))
        sgst = (taxable * sgst_rate / Decimal("100")).quantize(Decimal("0.01"))
        igst = Decimal("0")
        cess = (taxable * cess_rate / Decimal("100")).quantize(Decimal("0.01"))
    total_tax = cgst + sgst + igst + cess
    return {
        "taxable_value": float(taxable),
        "company_state_code": payload.company_state_code,
        "place_of_supply_state": payload.place_of_supply_state,
        "intra_state": not interstate and not zero_tax,
        "inter_state": interstate and not zero_tax,
        "supply_type": payload.supply_type,
        "transaction_type": payload.transaction_type,
        "reverse_charge": payload.reverse_charge,
        "itc_eligible": payload.itc_eligible,
        "exempt_type": payload.exempt_type,
        "cgst_amount": float(cgst),
        "sgst_amount": float(sgst),
        "igst_amount": float(igst),
        "cess_amount": float(cess),
        "total_tax": float(total_tax),
        "gross_amount": float(taxable + total_tax),
        "ledger_posting_required": not zero_tax,
        "roundoff_difference": 0,
    }


def gst_register(db: Session, company_id: int, transaction_types: set[str]) -> dict[str, Any]:
    items = db.query(FAMGSTTransactionLine).filter(FAMGSTTransactionLine.company_id == company_id, FAMGSTTransactionLine.transaction_type.in_(transaction_types)).order_by(FAMGSTTransactionLine.id.desc()).all()
    totals = {"taxable_value": Decimal("0"), "cgst_amount": Decimal("0"), "sgst_amount": Decimal("0"), "igst_amount": Decimal("0"), "cess_amount": Decimal("0")}
    for item in items:
        for key in totals:
            totals[key] += Decimal(getattr(item, key) or 0)
    return {"items": [serialize(item) for item in items], "total": len(items), "totals": {key: float(value) for key, value in totals.items()}}


def get_or_create_return_period(db: Session, company_id: int, payload: GSTReturnPreparePayload, return_type: str, user: User) -> FAMGSTReturnPeriod:
    period = db.query(FAMGSTReturnPeriod).filter(FAMGSTReturnPeriod.company_id == company_id, FAMGSTReturnPeriod.period_month == payload.period_month, FAMGSTReturnPeriod.period_year == payload.period_year, FAMGSTReturnPeriod.return_type == return_type).first()
    if not period:
        period = FAMGSTReturnPeriod(company_id=company_id, period_month=payload.period_month, period_year=payload.period_year, return_type=return_type)
        db.add(period)
        db.flush()
    period.status = "prepared"
    period.prepared_by = user.id
    period.prepared_at = datetime.now(timezone.utc)
    return period


@router.get("/gst/registrations")
def list_gst_registrations(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMTaxRegistration).filter(FAMTaxRegistration.company_id == company_id).order_by(FAMTaxRegistration.state_code, FAMTaxRegistration.id).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/gst/registrations", status_code=status.HTTP_201_CREATED)
def create_gst_registration(payload: GSTRegistrationPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if db.query(FAMTaxRegistration).filter(FAMTaxRegistration.company_id == company_id, FAMTaxRegistration.gstin == payload.gstin).first():
        raise HTTPException(status_code=409, detail="GSTIN already registered")
    item = FAMTaxRegistration(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    gst_audit(db, current_user, company_id, "tax_registration", item.id, "CREATE", None, serialize(item))
    audit(db, request, current_user, company_id, "gst_registration", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/gst/rates")
def list_gst_rates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMGSTRate).filter(FAMGSTRate.company_id == company_id).order_by(FAMGSTRate.effective_from.desc(), FAMGSTRate.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/gst/rates", status_code=status.HTTP_201_CREATED)
def create_gst_rate(payload: GSTRatePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.tax_type not in VALID_GST_TAX_TYPES:
        raise HTTPException(status_code=422, detail="Invalid GST tax type")
    item = FAMGSTRate(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    gst_audit(db, current_user, company_id, "gst_rate", item.id, "CREATE", None, serialize(item))
    audit(db, request, current_user, company_id, "gst_rate", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/gst/hsn-sac")
def list_hsn_sac(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMHSNSACCode).filter(FAMHSNSACCode.company_id == company_id).order_by(FAMHSNSACCode.code).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/gst/hsn-sac", status_code=status.HTTP_201_CREATED)
def create_hsn_sac(payload: HSNSACPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.type not in VALID_HSN_SAC_TYPES:
        raise HTTPException(status_code=422, detail="Invalid HSN/SAC type")
    if payload.default_gst_rate_id and not db.query(FAMGSTRate).filter(FAMGSTRate.company_id == company_id, FAMGSTRate.id == payload.default_gst_rate_id).first():
        raise HTTPException(status_code=404, detail="Default GST rate not found")
    if db.query(FAMHSNSACCode).filter(FAMHSNSACCode.company_id == company_id, FAMHSNSACCode.code == payload.code).first():
        raise HTTPException(status_code=409, detail="HSN/SAC code already exists")
    item = FAMHSNSACCode(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    gst_audit(db, current_user, company_id, "hsn_sac", item.id, "CREATE", None, serialize(item))
    audit(db, request, current_user, company_id, "hsn_sac", item.id, "CREATE", None, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/gst/calculate")
def calculate_gst(payload: GSTCalculationPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    result = calculate_gst_amounts(db, company_id, payload)
    if payload.persist:
        line = FAMGSTTransactionLine(company_id=company_id, voucher_id=payload.voucher_id, voucher_line_id=payload.voucher_line_id, transaction_type=payload.transaction_type, party_id=payload.party_id, gstin=payload.gstin, place_of_supply_state=payload.place_of_supply_state, supply_type=payload.supply_type, hsn_sac_code=payload.hsn_sac_code, taxable_value=Decimal(str(result["taxable_value"])), cgst_amount=Decimal(str(result["cgst_amount"])), sgst_amount=Decimal(str(result["sgst_amount"])), igst_amount=Decimal(str(result["igst_amount"])), cess_amount=Decimal(str(result["cess_amount"])), itc_eligible=payload.itc_eligible, reverse_charge=payload.reverse_charge, exempt_type=payload.exempt_type)
        db.add(line)
        db.flush()
        result["transaction_line"] = serialize(line)
        gst_audit(db, current_user, company_id, "gst_transaction_line", line.id, "CALCULATE", None, result)
        audit(db, request, current_user, company_id, "gst_transaction_line", line.id, "CALCULATE", None, result)
        db.commit()
    return result


@router.get("/gst/sales-register")
def gst_sales_register(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return gst_register(db, bootstrap(db, current_user), {"outward", "export"})


@router.get("/gst/purchase-register")
def gst_purchase_register(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return gst_register(db, bootstrap(db, current_user), {"inward", "rcm", "import"})


@router.get("/gst/gstr1")
def get_gstr1(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    records = db.query(FAMGSTR1Record).filter(FAMGSTR1Record.company_id == company_id).order_by(FAMGSTR1Record.id.desc()).all()
    return {"items": [serialize(item) for item in records], "total": len(records), "portal_status": "not_configured"}


@router.post("/gst/gstr1/prepare")
def prepare_gstr1(payload: GSTReturnPreparePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_RETURN_PREPARE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    period = get_or_create_return_period(db, company_id, payload, "gstr1", current_user)
    db.query(FAMGSTR1Record).filter(FAMGSTR1Record.return_period_id == period.id).delete()
    register = gst_register(db, company_id, {"outward", "export"})
    totals = register["totals"]
    record = FAMGSTR1Record(company_id=company_id, return_period_id=period.id, section="summary", taxable_value=totals["taxable_value"], cgst_amount=totals["cgst_amount"], sgst_amount=totals["sgst_amount"], igst_amount=totals["igst_amount"], cess_amount=totals["cess_amount"], record_count=register["total"], source_json={"note": "Prepared from GST transaction lines; portal filing not integrated."})
    db.add(record)
    db.flush()
    gst_audit(db, current_user, company_id, "gstr1", period.id, "PREPARE", None, serialize(record))
    audit(db, request, current_user, company_id, "gstr1", period.id, "PREPARE", None, serialize(record))
    db.commit()
    return {"period": serialize(period), "records": [serialize(record)], "portal_status": "not_configured"}


@router.get("/gst/gstr3b")
def get_gstr3b(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    records = db.query(FAMGSTR3BRecord).filter(FAMGSTR3BRecord.company_id == company_id).order_by(FAMGSTR3BRecord.id.desc()).all()
    return {"items": [serialize(item) for item in records], "total": len(records), "portal_status": "not_configured"}


@router.post("/gst/gstr3b/prepare")
def prepare_gstr3b(payload: GSTReturnPreparePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_RETURN_PREPARE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    period = get_or_create_return_period(db, company_id, payload, "gstr3b", current_user)
    db.query(FAMGSTR3BRecord).filter(FAMGSTR3BRecord.return_period_id == period.id).delete()
    outward = gst_register(db, company_id, {"outward", "export"})
    inward = gst_register(db, company_id, {"inward", "rcm", "import"})
    records = []
    for section, register in [("outward_tax", outward), ("eligible_itc", inward)]:
        totals = register["totals"]
        record = FAMGSTR3BRecord(company_id=company_id, return_period_id=period.id, section=section, taxable_value=totals["taxable_value"], cgst_amount=totals["cgst_amount"], sgst_amount=totals["sgst_amount"], igst_amount=totals["igst_amount"], cess_amount=totals["cess_amount"], source_json={"note": "Prepared from GST transaction lines; portal filing not integrated."})
        db.add(record)
        db.flush()
        records.append(record)
    gst_audit(db, current_user, company_id, "gstr3b", period.id, "PREPARE", None, {"records": [serialize(item) for item in records]})
    audit(db, request, current_user, company_id, "gstr3b", period.id, "PREPARE", None, {"records": [serialize(item) for item in records]})
    db.commit()
    return {"period": serialize(period), "records": [serialize(item) for item in records], "portal_status": "not_configured"}


@router.get("/gst/reconciliation")
def gst_reconciliation(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_RECONCILIATION_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMGSTReconciliationItem).filter(FAMGSTReconciliationItem.company_id == company_id).order_by(FAMGSTReconciliationItem.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items), "status": "ready", "external_portal_reconciliation": "not_configured"}


@router.get("/gst/einvoice-settings")
def get_einvoice_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMEInvoiceSettings).filter(FAMEInvoiceSettings.company_id == company_id).first()
    return serialize(item) if item else {"company_id": company_id, "provider_name": None, "credentials_configured": False, "active": False, "status": "not_configured"}


@router.put("/gst/einvoice-settings")
def put_einvoice_settings(payload: EInvoiceSettingsPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EINVOICE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMEInvoiceSettings).filter(FAMEInvoiceSettings.company_id == company_id).first()
    if not item:
        item = FAMEInvoiceSettings(company_id=company_id)
        db.add(item)
        db.flush()
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    gst_audit(db, current_user, company_id, "einvoice_settings", item.id, "UPDATE", old, serialize(item))
    audit(db, request, current_user, company_id, "einvoice_settings", item.id, "UPDATE", old, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/gst/einvoice/generate/{voucher_id}")
def generate_einvoice(voucher_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EINVOICE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    settings = db.query(FAMEInvoiceSettings).filter(FAMEInvoiceSettings.company_id == company_id).first()
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    configured = bool(settings and settings.active and settings.credentials_configured)
    job = FAMEInvoiceJob(company_id=company_id, voucher_id=voucher_id, action="generate", status="queued" if configured else "not_configured", error_message=None if configured else "E-invoice provider not configured", created_by=current_user.id)
    db.add(job)
    db.flush()
    gst_audit(db, current_user, company_id, "einvoice_job", job.id, "GENERATE", None, serialize(job))
    audit(db, request, current_user, company_id, "einvoice_job", job.id, "GENERATE", None, serialize(job))
    db.commit()
    return {**serialize(job), "message": "E-invoice provider not configured" if not configured else "E-invoice generation queued"}


@router.post("/gst/einvoice/cancel/{voucher_id}")
def cancel_einvoice(voucher_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EINVOICE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    configured = bool(db.query(FAMEInvoiceSettings).filter(FAMEInvoiceSettings.company_id == company_id, FAMEInvoiceSettings.active == True, FAMEInvoiceSettings.credentials_configured == True).first())
    job = FAMEInvoiceJob(company_id=company_id, voucher_id=voucher_id, action="cancel", status="queued" if configured else "not_configured", error_message=None if configured else "E-invoice provider not configured", created_by=current_user.id)
    db.add(job)
    db.flush()
    gst_audit(db, current_user, company_id, "einvoice_job", job.id, "CANCEL", None, serialize(job))
    audit(db, request, current_user, company_id, "einvoice_job", job.id, "CANCEL", None, serialize(job))
    db.commit()
    return {**serialize(job), "message": "E-invoice provider not configured" if not configured else "E-invoice cancellation queued"}


@router.get("/gst/ewaybill-settings")
def get_ewaybill_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMEWayBillSettings).filter(FAMEWayBillSettings.company_id == company_id).first()
    return serialize(item) if item else {"company_id": company_id, "provider_name": None, "credentials_configured": False, "active": False, "threshold_amount": 50000, "status": "not_configured"}


@router.put("/gst/ewaybill-settings")
def put_ewaybill_settings(payload: EWayBillSettingsPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EWAYBILL_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = db.query(FAMEWayBillSettings).filter(FAMEWayBillSettings.company_id == company_id).first()
    if not item:
        item = FAMEWayBillSettings(company_id=company_id)
        db.add(item)
        db.flush()
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    gst_audit(db, current_user, company_id, "ewaybill_settings", item.id, "UPDATE", old, serialize(item))
    audit(db, request, current_user, company_id, "ewaybill_settings", item.id, "UPDATE", old, serialize(item))
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/gst/ewaybill/generate/{voucher_id}")
def generate_ewaybill(voucher_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EWAYBILL_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    settings = db.query(FAMEWayBillSettings).filter(FAMEWayBillSettings.company_id == company_id).first()
    voucher = db.query(FAMVoucher).filter(FAMVoucher.company_id == company_id, FAMVoucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    configured = bool(settings and settings.active and settings.credentials_configured)
    job = FAMEWayBillJob(company_id=company_id, voucher_id=voucher_id, action="generate", status="queued" if configured else "not_configured", error_message=None if configured else "E-way bill provider not configured", created_by=current_user.id)
    db.add(job)
    db.flush()
    gst_audit(db, current_user, company_id, "ewaybill_job", job.id, "GENERATE", None, serialize(job))
    audit(db, request, current_user, company_id, "ewaybill_job", job.id, "GENERATE", None, serialize(job))
    db.commit()
    return {**serialize(job), "message": "E-way bill provider not configured" if not configured else "E-way bill generation queued"}


@router.post("/gst/ewaybill/cancel/{voucher_id}")
def cancel_ewaybill(voucher_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_GST_EWAYBILL_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    configured = bool(db.query(FAMEWayBillSettings).filter(FAMEWayBillSettings.company_id == company_id, FAMEWayBillSettings.active == True, FAMEWayBillSettings.credentials_configured == True).first())
    job = FAMEWayBillJob(company_id=company_id, voucher_id=voucher_id, action="cancel", status="queued" if configured else "not_configured", error_message=None if configured else "E-way bill provider not configured", created_by=current_user.id)
    db.add(job)
    db.flush()
    gst_audit(db, current_user, company_id, "ewaybill_job", job.id, "CANCEL", None, serialize(job))
    audit(db, request, current_user, company_id, "ewaybill_job", job.id, "CANCEL", None, serialize(job))
    db.commit()
    return {**serialize(job), "message": "E-way bill provider not configured" if not configured else "E-way bill cancellation queued"}


def purchase_audit(db: Session, user: User, company_id: int, record_type: str, record_id: int | None, action: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> None:
    db.add(FAMPurchaseAuditLog(company_id=company_id, record_type=record_type, record_id=record_id, action=action, old_value_json=old, new_value_json=new, performed_by=user.id, performed_at=datetime.now(timezone.utc)))


def ledger_or_404(db: Session, company_id: int, ledger_id: int, detail: str = "Ledger not found") -> FAMLedger:
    ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.id == ledger_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail=detail)
    return ledger


def first_ledger_by(db: Session, company_id: int, *, ledger_type: str | None = None, nature: str | None = None) -> FAMLedger:
    query = db.query(FAMLedger).filter(FAMLedger.company_id == company_id)
    if ledger_type:
        query = query.filter(FAMLedger.ledger_type == ledger_type)
    if nature:
        query = query.filter(FAMLedger.nature == nature)
    ledger = query.order_by(FAMLedger.id).first()
    if not ledger:
        raise HTTPException(status_code=422, detail=f"Required {ledger_type or nature} ledger not configured")
    return ledger


def tax_ledger_by_keyword(db: Session, company_id: int, keyword: str) -> FAMLedger:
    normalized = f"%{keyword.lower()}%"
    ledger = (
        db.query(FAMLedger)
        .filter(FAMLedger.company_id == company_id, FAMLedger.ledger_type == "tax")
        .filter(or_(func.lower(FAMLedger.ledger_code).like(normalized), func.lower(FAMLedger.ledger_name).like(normalized)))
        .order_by(FAMLedger.id)
        .first()
    )
    if ledger:
        return ledger
    return first_ledger_by(db, company_id, ledger_type="tax")


def calculate_purchase_lines(payload: PurchaseBillPayload) -> tuple[list[dict[str, Any]], Decimal, Decimal, Decimal, Decimal]:
    lines: list[dict[str, Any]] = []
    subtotal = gst_total = tds_total = Decimal("0")
    for raw in payload.lines:
        taxable = Decimal(raw.taxable_value if raw.taxable_value is not None else Decimal(raw.quantity) * Decimal(raw.rate))
        gst = Decimal(raw.gst_amount or 0)
        tds = Decimal(raw.tds_amount or 0)
        line_total = Decimal(raw.line_total if raw.line_total is not None else taxable + gst - tds)
        subtotal += taxable
        gst_total += gst
        tds_total += tds
        lines.append({**raw.model_dump(), "taxable_value": taxable, "gst_amount": gst, "tds_amount": tds, "line_total": line_total})
    grand_total = subtotal - Decimal(payload.discount_total or 0) + gst_total - tds_total
    return lines, subtotal, gst_total, tds_total, grand_total


@router.get("/purchase-bills")
def list_purchase_bills(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id).order_by(FAMPurchaseBill.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/purchase-bills", status_code=status.HTTP_201_CREATED)
def create_purchase_bill(payload: PurchaseBillPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    vendor = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == payload.vendor_id, FAMParty.party_type.in_(["vendor", "both"])).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    create_party_ledger(db, company_id, vendor)
    if db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.vendor_id == vendor.id, FAMPurchaseBill.bill_number == payload.bill_number).first():
        raise HTTPException(status_code=409, detail="Vendor bill already exists")
    lines, subtotal, gst_total, tds_total, grand_total = calculate_purchase_lines(payload)
    bill = FAMPurchaseBill(company_id=company_id, vendor_id=vendor.id, bill_number=payload.bill_number, bill_date=payload.bill_date, due_date=payload.due_date or payload.bill_date + timedelta(days=int(vendor.payment_terms_days or 30)), gstin=payload.gstin or vendor.gstin, place_of_supply=payload.place_of_supply or vendor.state_code, subtotal=subtotal, discount_total=payload.discount_total, gst_total=gst_total, tds_amount=tds_total, grand_total=grand_total, status="draft")
    db.add(bill)
    db.flush()
    for line in lines:
        ledger_or_404(db, company_id, int(line["expense_ledger_id"]), "Expense ledger not found")
        db.add(FAMPurchaseBillLine(purchase_bill_id=bill.id, **line))
    purchase_audit(db, current_user, company_id, "purchase_bill", bill.id, "CREATE", None, serialize(bill))
    audit(db, request, current_user, company_id, "purchase_bill", bill.id, "CREATE", None, serialize(bill))
    db.commit()
    db.refresh(bill)
    return serialize(bill)


@router.get("/purchase-bills/{id}")
def get_purchase_bill(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bill = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    lines = db.query(FAMPurchaseBillLine).filter(FAMPurchaseBillLine.purchase_bill_id == bill.id).all()
    audit_logs = db.query(FAMPurchaseAuditLog).filter(FAMPurchaseAuditLog.company_id == company_id, FAMPurchaseAuditLog.record_type == "purchase_bill", FAMPurchaseAuditLog.record_id == bill.id).order_by(FAMPurchaseAuditLog.performed_at.desc()).all()
    tds_transactions = db.query(FAMTDSTransaction).filter(FAMTDSTransaction.company_id == company_id, FAMTDSTransaction.vendor_id == bill.vendor_id, FAMTDSTransaction.voucher_id == bill.voucher_id).all() if bill.voucher_id else []
    return {**serialize(bill), "lines": [serialize(line) for line in lines], "audit_logs": [serialize(item) for item in audit_logs], "tds_transactions": [serialize(item) for item in tds_transactions]}


@router.put("/purchase-bills/{id}")
def update_purchase_bill(id: int, payload: PurchaseBillPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bill = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    if bill.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft purchase bills can be edited")
    old = get_purchase_bill(id, db, current_user)
    db.query(FAMPurchaseBillLine).filter(FAMPurchaseBillLine.purchase_bill_id == bill.id).delete()
    lines, subtotal, gst_total, tds_total, grand_total = calculate_purchase_lines(payload)
    for key, value in payload.model_dump(exclude={"lines"}).items():
        setattr(bill, key, value)
    bill.subtotal = subtotal
    bill.gst_total = gst_total
    bill.tds_amount = tds_total
    bill.grand_total = grand_total
    for line in lines:
        db.add(FAMPurchaseBillLine(purchase_bill_id=bill.id, **line))
    purchase_audit(db, current_user, company_id, "purchase_bill", bill.id, "UPDATE", old, serialize(bill))
    audit(db, request, current_user, company_id, "purchase_bill", bill.id, "UPDATE", old, serialize(bill))
    db.commit()
    return get_purchase_bill(id, db, current_user)


@router.post("/purchase-bills/{id}/post")
def post_purchase_bill(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bill = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    if bill.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft purchase bills can be posted")
    vendor = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == bill.vendor_id).first()
    create_party_ledger(db, company_id, vendor)
    input_gst_ledger = tax_ledger_by_keyword(db, company_id, "input")
    tds_ledger = tax_ledger_by_keyword(db, company_id, "tds")
    lines = db.query(FAMPurchaseBillLine).filter(FAMPurchaseBillLine.purchase_bill_id == bill.id).all()
    voucher_lines: list[dict[str, Any]] = []
    for line in lines:
        voucher_lines.append({"ledger_id": line.expense_ledger_id, "debit_amount": Decimal(line.taxable_value or 0), "credit_amount": Decimal("0"), "narration": line.description})
    if Decimal(bill.gst_total or 0) > 0:
        voucher_lines.append({"ledger_id": input_gst_ledger.id, "debit_amount": Decimal(bill.gst_total or 0), "credit_amount": Decimal("0"), "narration": "Input GST"})
    if Decimal(bill.grand_total or 0) > 0:
        voucher_lines.append({"ledger_id": vendor.ledger_id, "debit_amount": Decimal("0"), "credit_amount": Decimal(bill.grand_total or 0), "narration": f"Vendor payable {bill.bill_number}"})
    if Decimal(bill.tds_amount or 0) > 0:
        voucher_lines.append({"ledger_id": tds_ledger.id, "debit_amount": Decimal("0"), "credit_amount": Decimal(bill.tds_amount or 0), "narration": "TDS payable"})
    voucher = create_and_post_voucher(db, request, current_user, company_id, "PV", bill.bill_date, bill.bill_number, f"Purchase bill {bill.bill_number}", "purchase_bill", bill.id, voucher_lines, source_module="fam")
    bill.voucher_id = voucher.id
    bill.status = "posted"
    for line in lines:
        if line.tds_section_id and Decimal(line.tds_amount or 0) > 0:
            section = db.query(FAMTDSSection).filter(FAMTDSSection.company_id == company_id, FAMTDSSection.id == line.tds_section_id).first()
            db.add(FAMTDSTransaction(company_id=company_id, voucher_id=voucher.id, vendor_id=vendor.id, section_id=line.tds_section_id, taxable_amount=line.taxable_value, tds_rate=section.default_rate if section else 0, tds_amount=line.tds_amount, deduction_date=bill.bill_date, status="deducted"))
    db.add(FAMBillReference(company_id=company_id, party_id=vendor.id, ledger_id=vendor.ledger_id, voucher_id=voucher.id, bill_number=bill.bill_number, bill_date=bill.bill_date, due_date=bill.due_date or bill.bill_date, bill_type="bill", original_amount=bill.grand_total, outstanding_amount=bill.grand_total, status=bill_status(Decimal(bill.grand_total or 0)), source_module="fam", source_record_type="purchase_bill", source_record_id=str(bill.id)))
    purchase_audit(db, current_user, company_id, "purchase_bill", bill.id, "POST", None, serialize(bill))
    db.commit()
    return {**serialize(bill), "voucher": serialize_voucher(db, voucher)}


@router.post("/purchase-bills/{id}/cancel")
def cancel_purchase_bill(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bill = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    if bill.status == "paid":
        raise HTTPException(status_code=409, detail="Paid purchase bill cannot be cancelled")
    old = serialize(bill)
    bill.status = "cancelled"
    purchase_audit(db, current_user, company_id, "purchase_bill", bill.id, "CANCEL", old, serialize(bill))
    audit(db, request, current_user, company_id, "purchase_bill", bill.id, "CANCEL", old, serialize(bill))
    db.commit()
    return serialize(bill)


@router.get("/expenses")
def list_expenses(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_EXPENSE_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMExpenseClaim).filter(FAMExpenseClaim.company_id == company_id).order_by(FAMExpenseClaim.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseClaimPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_EXPENSE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    subtotal = sum(Decimal(line.taxable_value or 0) for line in payload.lines)
    gst_total = sum(Decimal(line.gst_amount or 0) for line in payload.lines)
    claim = FAMExpenseClaim(company_id=company_id, claim_number=payload.claim_number, claimant_name=payload.claimant_name, claim_date=payload.claim_date, payable_ledger_id=payload.payable_ledger_id, subtotal=subtotal, gst_total=gst_total, grand_total=subtotal + gst_total, status="draft")
    db.add(claim)
    db.flush()
    for raw in payload.lines:
        line_total = Decimal(raw.line_total if raw.line_total is not None else raw.taxable_value + raw.gst_amount)
        db.add(FAMExpenseLine(expense_claim_id=claim.id, **{**raw.model_dump(), "line_total": line_total}))
    purchase_audit(db, current_user, company_id, "expense_claim", claim.id, "CREATE", None, serialize(claim))
    audit(db, request, current_user, company_id, "expense_claim", claim.id, "CREATE", None, serialize(claim))
    db.commit()
    return serialize(claim)


@router.post("/expenses/{id}/post")
def post_expense(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_EXPENSE_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    claim = db.query(FAMExpenseClaim).filter(FAMExpenseClaim.company_id == company_id, FAMExpenseClaim.id == id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense not found")
    if claim.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft expenses can be posted")
    payable = ledger_or_404(db, company_id, claim.payable_ledger_id or first_ledger_by(db, company_id, nature="liability").id, "Payable ledger not found")
    input_gst = tax_ledger_by_keyword(db, company_id, "input")
    lines = db.query(FAMExpenseLine).filter(FAMExpenseLine.expense_claim_id == claim.id).all()
    voucher_lines = [{"ledger_id": line.expense_ledger_id, "debit_amount": Decimal(line.taxable_value or 0), "credit_amount": Decimal("0"), "narration": line.description} for line in lines]
    if Decimal(claim.gst_total or 0) > 0:
        voucher_lines.append({"ledger_id": input_gst.id, "debit_amount": Decimal(claim.gst_total or 0), "credit_amount": Decimal("0"), "narration": "Input GST"})
    voucher_lines.append({"ledger_id": payable.id, "debit_amount": Decimal("0"), "credit_amount": Decimal(claim.grand_total or 0), "narration": f"Expense payable {claim.claim_number}"})
    voucher = create_and_post_voucher(db, request, current_user, company_id, "PV", claim.claim_date, claim.claim_number, f"Expense {claim.claim_number}", "expense_claim", claim.id, voucher_lines, source_module="fam")
    claim.voucher_id = voucher.id
    claim.status = "posted"
    purchase_audit(db, current_user, company_id, "expense_claim", claim.id, "POST", None, serialize(claim))
    db.commit()
    return {**serialize(claim), "voucher": serialize_voucher(db, voucher)}


@router.get("/tds/sections")
def list_tds_sections(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMTDSSection).filter(FAMTDSSection.company_id == company_id).order_by(FAMTDSSection.section_code).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/tds/sections", status_code=status.HTTP_201_CREATED)
def create_tds_section(payload: TDSSectionPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = FAMTDSSection(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    purchase_audit(db, current_user, company_id, "tds_section", item.id, "CREATE", None, serialize(item))
    audit(db, request, current_user, company_id, "tds_section", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/tds/rates")
def list_tds_rates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMTDSRate).filter(FAMTDSRate.company_id == company_id).order_by(FAMTDSRate.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/tds/rates", status_code=status.HTTP_201_CREATED)
def create_tds_rate(payload: TDSRatePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if not db.query(FAMTDSSection).filter(FAMTDSSection.company_id == company_id, FAMTDSSection.id == payload.section_id).first():
        raise HTTPException(status_code=404, detail="TDS section not found")
    item = FAMTDSRate(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    purchase_audit(db, current_user, company_id, "tds_rate", item.id, "CREATE", None, serialize(item))
    audit(db, request, current_user, company_id, "tds_rate", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.post("/tds/calculate")
def calculate_tds(payload: TDSCalculatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    section = db.query(FAMTDSSection).filter(FAMTDSSection.company_id == company_id, FAMTDSSection.id == payload.section_id, FAMTDSSection.active == True).first()
    if not section:
        raise HTTPException(status_code=404, detail="TDS section not found")
    taxable = Decimal(payload.taxable_amount)
    rate = Decimal(section.default_rate or 0)
    threshold = Decimal(section.threshold_amount or 0)
    amount = Decimal("0") if threshold and taxable < threshold else (taxable * rate / Decimal("100")).quantize(Decimal("0.01"))
    return {"section_id": section.id, "taxable_amount": float(taxable), "tds_rate": float(rate), "threshold_amount": float(threshold), "tds_amount": float(amount), "status": "calculated"}


@router.get("/tds/transactions")
def list_tds_transactions(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMTDSTransaction).filter(FAMTDSTransaction.company_id == company_id).order_by(FAMTDSTransaction.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/tds/payable")
def tds_payable(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_TDS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMTDSTransaction).filter(FAMTDSTransaction.company_id == company_id, FAMTDSTransaction.status == "deducted").all()
    total = sum(Decimal(item.tds_amount or 0) for item in items)
    return {"items": [serialize(item) for item in items], "total": len(items), "tds_payable": float(total), "total_payable": float(total), "filing_status": "not_configured"}


@router.get("/purchase-register")
def purchase_register(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_PURCHASE_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id).order_by(FAMPurchaseBill.bill_date.desc()).all()
    totals = {"subtotal": float(sum(Decimal(item.subtotal or 0) for item in items)), "gst_total": float(sum(Decimal(item.gst_total or 0) for item in items)), "tds_amount": float(sum(Decimal(item.tds_amount or 0) for item in items)), "grand_total": float(sum(Decimal(item.grand_total or 0) for item in items))}
    return {"items": [serialize(item) for item in items], "total": len(items), "totals": totals, **totals}


@router.get("/expense-register")
def expense_register(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_EXPENSE_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMExpenseClaim).filter(FAMExpenseClaim.company_id == company_id).order_by(FAMExpenseClaim.claim_date.desc()).all()
    total = float(sum(Decimal(item.grand_total or 0) for item in items))
    return {"items": [serialize(item) for item in items], "total": len(items), "grand_total": total, "total_amount": total, "totals": {"total_amount": total, "grand_total": total}}


@router.get("/payables/dashboard")
def payables_dashboard(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_AP_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = bill_query_for(db, company_id, False).order_by(FAMBillReference.due_date).all()
    ap = {"items": [serialize(item) for item in items], "totalOutstanding": float(sum(Decimal(item.outstanding_amount or 0) for item in items))}
    aging = aging_payload(items, date.today())
    tds = tds_payable(db, current_user=current_user)
    bill_status_counts = {
        "draftBills": db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.status == "draft").count(),
        "postedBills": db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.status == "posted").count(),
        "paidBills": db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.status == "paid").count(),
    }
    return {"apOutstanding": ap, "apAging": aging, "tdsPayable": tds["tds_payable"], "items": aging["items"], "buckets": aging["buckets"], "totalOutstanding": ap["totalOutstanding"], **bill_status_counts}


@router.post("/vendor-payments/prepare", status_code=status.HTTP_201_CREATED)
def prepare_vendor_payment(payload: VendorPaymentPreparePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VENDOR_PAYMENT_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bank = ledger_or_404(db, company_id, payload.bank_ledger_id, "Bank ledger not found")
    if bank.ledger_type not in {"bank", "cash"}:
        raise HTTPException(status_code=422, detail="Payment ledger must be bank or cash")
    total = sum(Decimal(item.amount or 0) for item in payload.items)
    run = FAMVendorPaymentRun(company_id=company_id, run_number=f"VPR-{int(datetime.now(timezone.utc).timestamp())}", payment_date=payload.payment_date, bank_ledger_id=bank.id, total_amount=total, status="prepared")
    db.add(run)
    db.flush()
    for item in payload.items:
        db.add(FAMVendorPaymentItem(payment_run_id=run.id, **item.model_dump()))
    purchase_audit(db, current_user, company_id, "vendor_payment_run", run.id, "PREPARE", None, serialize(run))
    audit(db, request, current_user, company_id, "vendor_payment_run", run.id, "PREPARE", None, serialize(run))
    db.commit()
    return serialize(run)


@router.post("/vendor-payments/post")
def post_vendor_payment(payload: VendorPaymentPreparePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_VENDOR_PAYMENT_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    bank = ledger_or_404(db, company_id, payload.bank_ledger_id, "Bank ledger not found")
    voucher_lines = []
    for item in payload.items:
        vendor = db.query(FAMParty).filter(FAMParty.company_id == company_id, FAMParty.id == item.vendor_id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        create_party_ledger(db, company_id, vendor)
        amount = Decimal(item.amount or 0)
        voucher_lines.append({"ledger_id": vendor.ledger_id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": "Vendor payment"})
    total = sum(Decimal(line["debit_amount"]) for line in voucher_lines)
    voucher_lines.append({"ledger_id": bank.id, "debit_amount": Decimal("0"), "credit_amount": total, "narration": "Vendor payment"})
    voucher = create_and_post_voucher(db, request, current_user, company_id, "PV", payload.payment_date, f"VENDOR-PAY-{int(datetime.now(timezone.utc).timestamp())}", "Vendor payment run", "vendor_payment", 0, voucher_lines, source_module="fam")
    run = FAMVendorPaymentRun(company_id=company_id, run_number=voucher.reference_number, payment_date=payload.payment_date, bank_ledger_id=bank.id, total_amount=total, status="posted", voucher_id=voucher.id)
    db.add(run)
    db.flush()
    for item in payload.items:
        payment_item = FAMVendorPaymentItem(payment_run_id=run.id, **item.model_dump(), status="posted")
        db.add(payment_item)
        if item.purchase_bill_id:
            bill = db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == company_id, FAMPurchaseBill.id == item.purchase_bill_id).first()
            if bill:
                bill.status = "paid"
        if item.bill_reference_id:
            ref = db.query(FAMBillReference).filter(FAMBillReference.company_id == company_id, FAMBillReference.id == item.bill_reference_id).first()
            if ref:
                ref.outstanding_amount = max(Decimal("0"), Decimal(ref.outstanding_amount or 0) - Decimal(item.amount or 0))
                ref.status = bill_status(Decimal(ref.outstanding_amount or 0))
    purchase_audit(db, current_user, company_id, "vendor_payment_run", run.id, "POST", None, serialize(run))
    db.commit()
    return {**serialize(run), "voucher": serialize_voucher(db, voucher)}


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def generated_number(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


def inventory_item_or_404(db: Session, company_id: int, item_id: int) -> FAMStockItem:
    item = db.query(FAMStockItem).filter(FAMStockItem.company_id == company_id, FAMStockItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Stock item not found")
    return item


def warehouse_or_404(db: Session, company_id: int, warehouse_id: int) -> FAMWarehouse:
    warehouse = db.query(FAMWarehouse).filter(FAMWarehouse.company_id == company_id, FAMWarehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


def inventory_audit(db: Session, request: Request, user: User, company_id: int, record_type: str, record_id: int | None, action: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> None:
    audit(db, request, user, company_id, f"inventory_{record_type}", record_id, action, old, new)


def ensure_inventory_ledgers(db: Session, company_id: int) -> tuple[FAMLedger, FAMLedger]:
    inventory = (
        db.query(FAMLedger)
        .filter(FAMLedger.company_id == company_id)
        .filter(or_(func.lower(FAMLedger.ledger_code).like("%inventory%"), func.lower(FAMLedger.ledger_name).like("%inventory%")))
        .first()
    ) or first_ledger_by(db, company_id, nature="asset")
    cogs = (
        db.query(FAMLedger)
        .filter(FAMLedger.company_id == company_id)
        .filter(or_(func.lower(FAMLedger.ledger_code).like("%cogs%"), func.lower(FAMLedger.ledger_name).like("%cost of goods%")))
        .first()
    ) or first_ledger_by(db, company_id, nature="expense")
    return inventory, cogs


def apply_stock_line(db: Session, company_id: int, movement: FAMStockMovement, raw_line: dict[str, Any], line_number: int) -> FAMStockMovementLine:
    item = inventory_item_or_404(db, company_id, int(raw_line["stock_item_id"]))
    warehouse_or_404(db, company_id, int(raw_line["warehouse_id"]))
    qty_in = decimal_value(raw_line.get("quantity_in"))
    qty_out = decimal_value(raw_line.get("quantity_out"))
    if qty_in < 0 or qty_out < 0 or (qty_in == 0 and qty_out == 0):
        raise HTTPException(status_code=422, detail="Stock line must have positive quantity_in or quantity_out")
    if qty_in > 0 and qty_out > 0:
        raise HTTPException(status_code=422, detail="Stock line cannot have both inward and outward quantity")
    rate = decimal_value(raw_line.get("rate")) or decimal_value(item.average_cost) or decimal_value(item.purchase_rate)
    old_qty = decimal_value(item.current_quantity)
    old_value = old_qty * decimal_value(item.average_cost)
    if qty_out > old_qty:
        raise HTTPException(status_code=409, detail=f"Insufficient stock for {item.item_name}")
    if qty_in > 0:
        new_qty = old_qty + qty_in
        new_value = old_value + (qty_in * rate)
        item.average_cost = (new_value / new_qty).quantize(Decimal("0.0001")) if new_qty else rate
    else:
        new_qty = old_qty - qty_out
        new_value = new_qty * decimal_value(item.average_cost)
    item.current_quantity = new_qty
    item.purchase_rate = rate if qty_in > 0 else item.purchase_rate
    value = ((qty_in or qty_out) * rate).quantize(Decimal("0.01"))
    line = FAMStockMovementLine(
        movement_id=movement.id,
        company_id=company_id,
        stock_item_id=item.id,
        warehouse_id=int(raw_line["warehouse_id"]),
        quantity_in=qty_in,
        quantity_out=qty_out,
        rate=rate,
        value=value,
        balance_quantity=new_qty,
        balance_value=(new_qty * decimal_value(item.average_cost)).quantize(Decimal("0.01")),
        line_number=line_number,
        notes=raw_line.get("notes"),
    )
    db.add(line)
    db.flush()
    if qty_in > 0:
        db.add(FAMInventoryValuationLayer(company_id=company_id, stock_item_id=item.id, warehouse_id=line.warehouse_id, movement_id=movement.id, movement_line_id=line.id, quantity=qty_in, unit_cost=rate, layer_value=value, remaining_quantity=qty_in, remaining_value=value))
    return line


def post_stock_movement_record(db: Session, request: Request, user: User, company_id: int, movement: FAMStockMovement, lines: list[dict[str, Any]]) -> FAMStockMovement:
    if movement.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft stock movements can be posted")
    if not lines:
        raise HTTPException(status_code=422, detail="At least one stock movement line is required")
    for index, line in enumerate(lines, start=1):
        apply_stock_line(db, company_id, movement, line, index)
    movement.status = "posted"
    movement.posted_by = user.id
    movement.posted_at = datetime.now(timezone.utc)
    inventory_audit(db, request, user, company_id, "movement", movement.id, "POST", None, serialize(movement))
    return movement


def inventory_summary_rows(db: Session, company_id: int) -> list[dict[str, Any]]:
    rows = []
    items = db.query(FAMStockItem).filter(FAMStockItem.company_id == company_id).order_by(FAMStockItem.item_name).all()
    for item in items:
        qty = decimal_value(item.current_quantity)
        avg = decimal_value(item.average_cost)
        rows.append({**serialize(item), "stock_value": float((qty * avg).quantize(Decimal("0.01"))), "is_low_stock": bool((decimal_value(item.reorder_level) or decimal_value(item.min_stock)) and qty <= (decimal_value(item.reorder_level) or decimal_value(item.min_stock)))})
    return rows


@router.get("/inventory/source-audit")
def inventory_source_audit(current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    source_root = r"C:\Indian Servers\AI Inventory Management Software"
    expected = ["app/models/stock.py", "app/models/product.py", "app/services/stock_service.py", "app/routes/stock_routes.py", "app/templates/stock/current.html"]
    files = [{"path": path, "exists": os.path.exists(os.path.join(source_root, *path.split("/")))} for path in expected]
    return {"source_root": source_root, "source_exists": os.path.isdir(source_root), "source_stack": "Flask + SQLAlchemy + MySQL/SQLite", "merged_under": "FAM", "files": files}


@router.get("/inventory/dashboard")
@router.get("/inventory")
def inventory_dashboard(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    rows = inventory_summary_rows(db, company_id)
    total_value = sum(decimal_value(row.get("stock_value")) for row in rows)
    low_stock = [row for row in rows if row.get("is_low_stock")]
    movements = db.query(FAMStockMovement).filter(FAMStockMovement.company_id == company_id).order_by(FAMStockMovement.id.desc()).limit(8).all()
    return {"items_count": len(rows), "warehouses_count": db.query(FAMWarehouse).filter(FAMWarehouse.company_id == company_id).count(), "total_stock_value": float(total_value), "low_stock_count": len(low_stock), "recent_movements": [serialize(item) for item in movements], "source_merge": "AI Inventory Management Software stock masters, ledger, valuation and reports merged into FAM"}


@router.get("/inventory/categories")
@router.get("/inventory/stock-groups")
def list_stock_groups(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMStockGroup).filter(FAMStockGroup.company_id == company_id).order_by(FAMStockGroup.group_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/categories", status_code=status.HTTP_201_CREATED)
@router.post("/inventory/stock-groups", status_code=status.HTTP_201_CREATED)
def create_stock_group(payload: InventoryGroupPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = FAMStockGroup(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "stock_group", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/inventory/units")
def list_inventory_units(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMUnitOfMeasure).filter(FAMUnitOfMeasure.company_id == company_id).order_by(FAMUnitOfMeasure.unit_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/units", status_code=status.HTTP_201_CREATED)
def create_inventory_unit(payload: InventoryUnitPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = FAMUnitOfMeasure(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "unit", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/inventory/warehouses")
def list_warehouses(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMWarehouse).filter(FAMWarehouse.company_id == company_id).order_by(FAMWarehouse.warehouse_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/warehouses", status_code=status.HTTP_201_CREATED)
def create_warehouse(payload: InventoryWarehousePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = FAMWarehouse(company_id=company_id, **payload.model_dump())
    db.add(item)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "warehouse", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/inventory/items")
def list_inventory_items(search: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    query = db.query(FAMStockItem).filter(FAMStockItem.company_id == company_id)
    if search:
        normalized = f"%{search.lower()}%"
        query = query.filter(or_(func.lower(FAMStockItem.sku).like(normalized), func.lower(FAMStockItem.item_name).like(normalized), func.lower(FAMStockItem.hsn_code).like(normalized)))
    items = query.order_by(FAMStockItem.item_name).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/items", status_code=status.HTTP_201_CREATED)
def create_inventory_item(payload: InventoryItemPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if db.query(FAMStockItem).filter(FAMStockItem.company_id == company_id, FAMStockItem.sku == payload.sku).first():
        raise HTTPException(status_code=409, detail="Stock item SKU already exists")
    inventory, cogs = ensure_inventory_ledgers(db, company_id)
    item = FAMStockItem(company_id=company_id, created_by=current_user.id, inventory_ledger_id=payload.inventory_ledger_id or inventory.id, cogs_ledger_id=payload.cogs_ledger_id or cogs.id, **payload.model_dump(exclude={"inventory_ledger_id", "cogs_ledger_id"}))
    db.add(item)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "item", item.id, "CREATE", None, serialize(item))
    db.commit()
    return serialize(item)


@router.get("/inventory/items/{id}")
def get_inventory_item(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = inventory_item_or_404(db, company_id, id)
    lines = db.query(FAMStockMovementLine).filter(FAMStockMovementLine.company_id == company_id, FAMStockMovementLine.stock_item_id == item.id).order_by(FAMStockMovementLine.id.desc()).limit(25).all()
    return {**serialize(item), "stock_value": float((decimal_value(item.current_quantity) * decimal_value(item.average_cost)).quantize(Decimal("0.01"))), "ledger": [serialize(line) for line in lines]}


@router.put("/inventory/items/{id}")
def update_inventory_item(id: int, payload: InventoryItemPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_MANAGE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = inventory_item_or_404(db, company_id, id)
    old = serialize(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    inventory_audit(db, request, current_user, company_id, "item", item.id, "UPDATE", old, serialize(item))
    db.commit()
    return serialize(item)


@router.post("/inventory/opening-stock", status_code=status.HTTP_201_CREATED)
def create_opening_stock(payload: InventoryOpeningPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = inventory_item_or_404(db, company_id, payload.stock_item_id)
    warehouse_or_404(db, company_id, payload.warehouse_id)
    opening = FAMStockOpeningBalance(company_id=company_id, opening_number=payload.opening_number or generated_number("OPEN"), created_by=current_user.id, value=(payload.quantity * payload.rate).quantize(Decimal("0.01")), **payload.model_dump(exclude={"opening_number"}))
    db.add(opening)
    db.flush()
    movement = FAMStockMovement(company_id=company_id, movement_number=f"MOV-{opening.opening_number}", movement_date=payload.opening_date, movement_type="opening_stock", reference_number=opening.opening_number, source_module="fam", source_record_type="stock_opening", source_record_id=str(opening.id), narration=payload.notes, created_by=current_user.id)
    db.add(movement)
    db.flush()
    post_stock_movement_record(db, request, current_user, company_id, movement, [{"stock_item_id": item.id, "warehouse_id": payload.warehouse_id, "quantity_in": payload.quantity, "rate": payload.rate, "notes": payload.notes}])
    inventory_audit(db, request, current_user, company_id, "opening_stock", opening.id, "CREATE", None, serialize(opening))
    db.commit()
    return {**serialize(opening), "movement": serialize(movement)}


@router.get("/inventory/stock-movements")
def list_stock_movements(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMStockMovement).filter(FAMStockMovement.company_id == company_id).order_by(FAMStockMovement.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


def list_stock_movements_by_type(movement_type: str, db: Session, current_user: User) -> dict[str, Any]:
    company_id = bootstrap(db, current_user)
    items = db.query(FAMStockMovement).filter(FAMStockMovement.company_id == company_id, FAMStockMovement.movement_type == movement_type).order_by(FAMStockMovement.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


def create_posted_stock_document(movement_type: str, payload: StockMovementPayload, request: Request, db: Session, current_user: User) -> dict[str, Any]:
    company_id = bootstrap(db, current_user)
    movement = FAMStockMovement(company_id=company_id, movement_number=payload.movement_number or generated_number("MOV"), movement_date=payload.movement_date, movement_type=movement_type, reference_number=payload.reference_number, narration=payload.narration, source_module=payload.source_module or "fam", source_record_type=payload.source_record_type or movement_type, source_record_id=payload.source_record_id, created_by=current_user.id)
    db.add(movement)
    db.flush()
    post_stock_movement_record(db, request, current_user, company_id, movement, [line.model_dump() for line in payload.lines])
    inventory_audit(db, request, current_user, company_id, "movement", movement.id, "CREATE_POST", None, serialize(movement))
    db.commit()
    return serialize(movement)


@router.post("/inventory/stock-movements", status_code=status.HTTP_201_CREATED)
def create_stock_movement(payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    movement = FAMStockMovement(company_id=company_id, movement_number=payload.movement_number or generated_number("MOV"), movement_date=payload.movement_date, movement_type=payload.movement_type, reference_number=payload.reference_number, narration=payload.narration, source_module=payload.source_module, source_record_type=payload.source_record_type, source_record_id=payload.source_record_id, created_by=current_user.id)
    db.add(movement)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "movement", movement.id, "CREATE", None, serialize(movement))
    db.commit()
    return serialize(movement)


@router.get("/inventory/stock-in")
def list_stock_in(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    return list_stock_movements_by_type("stock_in", db, current_user)


@router.post("/inventory/stock-in", status_code=status.HTTP_201_CREATED)
def create_stock_in(payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    return create_posted_stock_document("stock_in", payload, request, db, current_user)


@router.get("/inventory/stock-out")
def list_stock_out(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    return list_stock_movements_by_type("stock_out", db, current_user)


@router.post("/inventory/stock-out", status_code=status.HTTP_201_CREATED)
def create_stock_out(payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    return create_posted_stock_document("stock_out", payload, request, db, current_user)


@router.get("/inventory/purchase-receipts")
def list_purchase_receipts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    return list_stock_movements_by_type("purchase_receipt", db, current_user)


@router.post("/inventory/purchase-receipts", status_code=status.HTTP_201_CREATED)
def create_purchase_receipt(payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    return create_posted_stock_document("purchase_receipt", payload, request, db, current_user)


@router.get("/inventory/delivery-notes")
def list_delivery_notes(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    return list_stock_movements_by_type("delivery_note", db, current_user)


@router.post("/inventory/delivery-notes", status_code=status.HTTP_201_CREATED)
def create_delivery_note(payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    return create_posted_stock_document("delivery_note", payload, request, db, current_user)


@router.post("/inventory/stock-movements/{id}/post")
def post_stock_movement(id: int, payload: StockMovementPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_POST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    movement = db.query(FAMStockMovement).filter(FAMStockMovement.company_id == company_id, FAMStockMovement.id == id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Stock movement not found")
    movement = post_stock_movement_record(db, request, current_user, company_id, movement, [line.model_dump() for line in payload.lines])
    db.commit()
    return serialize(movement)


@router.get("/inventory/stock-summary")
def stock_summary(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    rows = inventory_summary_rows(db, company_id)
    return {"items": rows, "total": len(rows), "total_stock_value": float(sum(decimal_value(row.get("stock_value")) for row in rows))}


@router.get("/inventory/item-ledger/{id}")
def item_ledger(id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    inventory_item_or_404(db, company_id, id)
    lines = db.query(FAMStockMovementLine).filter(FAMStockMovementLine.company_id == company_id, FAMStockMovementLine.stock_item_id == id).order_by(FAMStockMovementLine.id).all()
    return {"items": [serialize(line) for line in lines], "total": len(lines)}


@router.post("/inventory/stock-transfers", status_code=status.HTTP_201_CREATED)
def create_stock_transfer(payload: StockTransferPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_TRANSFER_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise HTTPException(status_code=422, detail="Transfer warehouses must be different")
    warehouse_or_404(db, company_id, payload.from_warehouse_id)
    warehouse_or_404(db, company_id, payload.to_warehouse_id)
    transfer = FAMStockTransfer(company_id=company_id, transfer_number=payload.transfer_number or generated_number("TRF"), transfer_date=payload.transfer_date, from_warehouse_id=payload.from_warehouse_id, to_warehouse_id=payload.to_warehouse_id, notes=payload.notes, lines_json=[line.model_dump(mode="json") for line in payload.lines], created_by=current_user.id)
    db.add(transfer)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "transfer", transfer.id, "CREATE", None, serialize(transfer))
    db.commit()
    return serialize(transfer)


@router.get("/inventory/stock-transfers")
def list_stock_transfers(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMStockTransfer).filter(FAMStockTransfer.company_id == company_id).order_by(FAMStockTransfer.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/stock-transfers/{id}/post")
def post_stock_transfer(id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_TRANSFER_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    transfer = db.query(FAMStockTransfer).filter(FAMStockTransfer.company_id == company_id, FAMStockTransfer.id == id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    if transfer.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft transfers can be posted")
    movement = FAMStockMovement(company_id=company_id, movement_number=f"MOV-{transfer.transfer_number}", movement_date=transfer.transfer_date, movement_type="stock_transfer", reference_number=transfer.transfer_number, source_module="fam", source_record_type="stock_transfer", source_record_id=str(transfer.id), narration=transfer.notes, created_by=current_user.id)
    db.add(movement)
    db.flush()
    lines: list[dict[str, Any]] = []
    for raw in transfer.lines_json or []:
        qty = decimal_value(raw.get("quantity"))
        rate = decimal_value(raw.get("rate"))
        lines.append({"stock_item_id": raw["stock_item_id"], "warehouse_id": transfer.from_warehouse_id, "quantity_out": qty, "rate": rate, "notes": raw.get("notes")})
        lines.append({"stock_item_id": raw["stock_item_id"], "warehouse_id": transfer.to_warehouse_id, "quantity_in": qty, "rate": rate, "notes": raw.get("notes")})
    post_stock_movement_record(db, request, current_user, company_id, movement, lines)
    transfer.status = "posted"
    transfer.movement_id = movement.id
    transfer.posted_by = current_user.id
    transfer.posted_at = datetime.now(timezone.utc)
    inventory_audit(db, request, current_user, company_id, "transfer", transfer.id, "POST", None, serialize(transfer))
    db.commit()
    return {**serialize(transfer), "movement": serialize(movement)}


@router.post("/inventory/stock-adjustments", status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(payload: StockAdjustmentPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_ADJUST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    warehouse_or_404(db, company_id, payload.warehouse_id)
    adjustment = FAMStockAdjustment(company_id=company_id, adjustment_number=payload.adjustment_number or generated_number("ADJ"), adjustment_date=payload.adjustment_date, warehouse_id=payload.warehouse_id, adjustment_type=payload.adjustment_type, reason=payload.reason, notes=payload.notes, lines_json=[line.model_dump(mode="json") for line in payload.lines], created_by=current_user.id)
    db.add(adjustment)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "adjustment", adjustment.id, "CREATE", None, serialize(adjustment))
    db.commit()
    return serialize(adjustment)


@router.get("/inventory/stock-adjustments")
def list_stock_adjustments(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    items = db.query(FAMStockAdjustment).filter(FAMStockAdjustment.company_id == company_id).order_by(FAMStockAdjustment.id.desc()).all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/inventory/stock-adjustments/{id}/post")
def post_stock_adjustment(id: int, payload: StockAdjustmentPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_STOCK_ADJUST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    adjustment = db.query(FAMStockAdjustment).filter(FAMStockAdjustment.company_id == company_id, FAMStockAdjustment.id == id).first()
    if not adjustment:
        raise HTTPException(status_code=404, detail="Stock adjustment not found")
    if adjustment.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft adjustments can be posted")
    movement = FAMStockMovement(company_id=company_id, movement_number=f"MOV-{adjustment.adjustment_number}", movement_date=adjustment.adjustment_date, movement_type="stock_adjustment", reference_number=adjustment.adjustment_number, source_module="fam", source_record_type="stock_adjustment", source_record_id=str(adjustment.id), narration=adjustment.reason or adjustment.notes, created_by=current_user.id)
    db.add(movement)
    db.flush()
    lines = [{**raw, "warehouse_id": adjustment.warehouse_id} for raw in adjustment.lines_json or []]
    post_stock_movement_record(db, request, current_user, company_id, movement, lines)
    value_in = sum(decimal_value(raw.get("quantity_in")) * decimal_value(raw.get("rate")) for raw in adjustment.lines_json or [])
    value_out = sum(decimal_value(raw.get("quantity_out")) * decimal_value(raw.get("rate")) for raw in adjustment.lines_json or [])
    adjustment_value = (value_in - value_out).quantize(Decimal("0.01"))
    if adjustment_value != 0:
        inventory_ledger, expense_ledger = ensure_inventory_ledgers(db, company_id)
        inventory_ledger_id = payload.inventory_ledger_id or inventory_ledger.id
        adjustment_ledger_id = payload.adjustment_ledger_id or expense_ledger.id
        amount = abs(adjustment_value)
        if adjustment_value > 0:
            voucher_lines = [{"ledger_id": inventory_ledger_id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": "Inventory adjustment in"}, {"ledger_id": adjustment_ledger_id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": "Inventory adjustment gain"}]
        else:
            voucher_lines = [{"ledger_id": adjustment_ledger_id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": "Inventory adjustment loss"}, {"ledger_id": inventory_ledger_id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": "Inventory adjustment out"}]
        voucher = create_and_post_voucher(db, request, current_user, company_id, "ADJ", adjustment.adjustment_date, adjustment.adjustment_number, "Inventory stock adjustment", "stock_adjustment", adjustment.id, voucher_lines, source_module="fam")
        adjustment.voucher_id = voucher.id
    adjustment.status = "posted"
    adjustment.movement_id = movement.id
    adjustment.posted_by = current_user.id
    adjustment.posted_at = datetime.now(timezone.utc)
    inventory_audit(db, request, current_user, company_id, "adjustment", adjustment.id, "POST", None, serialize(adjustment))
    db.commit()
    return serialize(adjustment)


@router.get("/inventory/valuation")
def inventory_valuation(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VALUATION_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    rows = inventory_summary_rows(db, company_id)
    return {"items": rows, "total": len(rows), "valuation_method": "weighted_average", "total_inventory_value": float(sum(decimal_value(row.get("stock_value")) for row in rows))}


@router.get("/inventory/reorder-alerts")
def reorder_alerts(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    rows = [row for row in inventory_summary_rows(db, company_id) if row.get("is_low_stock")]
    return {"items": rows, "total": len(rows)}


@router.post("/inventory/cogs/post")
def post_cogs(payload: COGSPostPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_COGS_POST_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    item = inventory_item_or_404(db, company_id, payload.stock_item_id)
    quantity = decimal_value(payload.quantity)
    amount = (quantity * decimal_value(item.average_cost)).quantize(Decimal("0.01"))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="COGS amount must be positive")
    inventory, cogs = ensure_inventory_ledgers(db, company_id)
    voucher = create_and_post_voucher(db, request, current_user, company_id, "JV", payload.posting_date, payload.reference_number or generated_number("COGS"), f"COGS for {item.sku}", "inventory_cogs", item.id, [{"ledger_id": payload.cogs_ledger_id or item.cogs_ledger_id or cogs.id, "debit_amount": amount, "credit_amount": Decimal("0"), "narration": "Cost of goods sold"}, {"ledger_id": payload.inventory_ledger_id or item.inventory_ledger_id or inventory.id, "debit_amount": Decimal("0"), "credit_amount": amount, "narration": "Inventory reduction for COGS"}], source_module="fam")
    inventory_audit(db, request, current_user, company_id, "cogs", item.id, "POST", None, {"voucher_id": voucher.id, "amount": float(amount)})
    db.commit()
    return {"voucher": serialize_voucher(db, voucher), "amount": float(amount)}


@router.get("/inventory/reports")
def inventory_reports(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_REPORTS_VIEW_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    summary = stock_summary(db, current_user=current_user)
    valuation = inventory_valuation(db, current_user=current_user)
    result = {"summary": summary, "valuation": {"total_inventory_value": valuation["total_inventory_value"], "valuation_method": valuation["valuation_method"]}, "reorder_alerts": reorder_alerts(db, current_user=current_user)}
    report = FAMInventoryReport(company_id=company_id, report_type="inventory_overview", result_json=result, generated_by=current_user.id)
    db.add(report)
    db.commit()
    return result


@router.post("/inventory/ai")
def inventory_ai(payload: InventoryAIRequestPayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission(*FAM_INVENTORY_AI_USE_PERMISSIONS))):
    company_id = bootstrap(db, current_user)
    context = {"scope": payload.scope, "stock_item_id": payload.stock_item_id}
    has_provider = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY"))
    if has_provider:
        response = {"message": "AI provider is configured, but Phase 8 keeps generation disabled until a Business Suite AI gateway is connected.", "recommended_actions": []}
        status_value = "gateway_not_connected"
        confidence = Decimal("0.250")
    else:
        response = {"message": "Inventory AI provider is not configured. No recommendation was generated.", "recommended_actions": []}
        status_value = "not_configured"
        confidence = Decimal("0")
    log = FAMInventoryAILog(company_id=company_id, prompt=payload.prompt, context_json=context, response_json=response, confidence=confidence, evidence_json={"source": "FAM inventory records", "mode": status_value}, provider="env" if has_provider else None, status=status_value, created_by=current_user.id)
    db.add(log)
    db.flush()
    inventory_audit(db, request, current_user, company_id, "ai", log.id, "REQUEST", None, {"status": status_value})
    db.commit()
    return {**serialize(log), "response": response}
