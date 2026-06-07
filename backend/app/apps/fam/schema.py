from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.apps.fam.models import FAMCompanyFinancialSettings, FAMFinancialYear, FAMLedger, FAMLedgerGroup, FAMVoucherType


SYSTEM_LEDGER_GROUPS = [
    ("Current Assets", "ASSET-CURRENT", "asset", None, 10),
    ("Cash-in-Hand", "ASSET-CASH", "asset", "ASSET-CURRENT", 11),
    ("Bank Accounts", "ASSET-BANK", "asset", "ASSET-CURRENT", 12),
    ("Sundry Debtors", "ASSET-DEBTORS", "asset", "ASSET-CURRENT", 13),
    ("Loans and Advances", "ASSET-LOANS-ADV", "asset", "ASSET-CURRENT", 14),
    ("Fixed Assets", "ASSET-FIXED", "asset", None, 20),
    ("Current Liabilities", "LIAB-CURRENT", "liability", None, 30),
    ("Sundry Creditors", "LIAB-CREDITORS", "liability", "LIAB-CURRENT", 31),
    ("Duties and Taxes", "LIAB-DUTIES-TAXES", "liability", "LIAB-CURRENT", 32),
    ("Loans", "LIAB-LOANS", "liability", None, 40),
    ("Provisions", "LIAB-PROVISIONS", "liability", None, 41),
    ("Capital Account", "EQ-CAPITAL", "equity", None, 50),
    ("Reserves and Surplus", "EQ-RESERVES", "equity", None, 51),
    ("Direct Income", "INC-DIRECT", "income", None, 60),
    ("Indirect Income", "INC-INDIRECT", "income", None, 61),
    ("Sales Accounts", "INC-SALES", "income", "INC-DIRECT", 62),
    ("Direct Expenses", "EXP-DIRECT", "expense", None, 70),
    ("Indirect Expenses", "EXP-INDIRECT", "expense", None, 71),
    ("Purchase Accounts", "EXP-PURCHASE", "expense", "EXP-DIRECT", 72),
]

DEFAULT_LEDGERS = [
    ("CASH", "Cash", "ASSET-CASH", "asset", "cash"),
    ("BANK-DEFAULT", "Bank - Default", "ASSET-BANK", "asset", "bank"),
    ("SALES", "Sales", "INC-SALES", "income", "income"),
    ("PURCHASE", "Purchase", "EXP-PURCHASE", "expense", "expense"),
    ("INVENTORY", "Inventory Stock", "ASSET-CURRENT", "asset", "asset"),
    ("COGS", "Cost of Goods Sold", "EXP-DIRECT", "expense", "expense"),
    ("OUTPUT-CGST", "Output CGST", "LIAB-DUTIES-TAXES", "liability", "tax"),
    ("OUTPUT-SGST", "Output SGST", "LIAB-DUTIES-TAXES", "liability", "tax"),
    ("OUTPUT-IGST", "Output IGST", "LIAB-DUTIES-TAXES", "liability", "tax"),
    ("INPUT-CGST", "Input CGST", "ASSET-CURRENT", "asset", "tax"),
    ("INPUT-SGST", "Input SGST", "ASSET-CURRENT", "asset", "tax"),
    ("INPUT-IGST", "Input IGST", "ASSET-CURRENT", "asset", "tax"),
    ("TDS-RECEIVABLE", "TDS Receivable", "ASSET-CURRENT", "asset", "tax"),
    ("TDS-PAYABLE", "TDS Payable", "LIAB-DUTIES-TAXES", "liability", "tax"),
    ("ROUND-OFF", "Round Off", "EXP-INDIRECT", "expense", "general"),
    ("BAD-DEBTS", "Bad Debts / Write-off", "EXP-INDIRECT", "expense", "expense"),
    ("PROFIT-LOSS", "Profit & Loss Account", "EQ-RESERVES", "equity", "equity"),
    ("OPENING-DIFF", "Opening Balance Difference", "EQ-CAPITAL", "equity", "general"),
]

SYSTEM_VOUCHER_TYPES = [
    ("JV", "Journal", "journal", "JV"),
    ("RV", "Receipt", "receipt", "RV"),
    ("PV", "Payment", "payment", "PV"),
    ("CV", "Contra", "contra", "CV"),
    ("SV", "Sales", "sales", "SV"),
    ("PUR", "Purchase", "purchase", "PUR"),
    ("DN", "Debit Note", "debit_note", "DN"),
    ("CN", "Credit Note", "credit_note", "CN"),
    ("OB", "Opening Balance", "opening", "OB"),
    ("ADJ", "Adjustment", "adjustment", "ADJ"),
]


def ensure_fam_schema(db: Session) -> None:
    ensure_fam_seed_data(db, company_id=1)


def ensure_fam_seed_data(db: Session, company_id: int = 1) -> None:
    settings = db.query(FAMCompanyFinancialSettings).filter(FAMCompanyFinancialSettings.company_id == company_id).first()
    if not settings:
        db.add(FAMCompanyFinancialSettings(company_id=company_id, country_code="IN", base_currency="INR", gst_enabled=False, financial_year_start_month=4, decimal_places=2))
        db.flush()

    fy = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id, FAMFinancialYear.is_current == True).first()
    if not fy:
        db.add(FAMFinancialYear(company_id=company_id, name="FY 2026-27", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), status="open", is_current=True))
        db.flush()

    groups_by_code: dict[str, FAMLedgerGroup] = {}
    for name, code, nature, parent_code, sequence in SYSTEM_LEDGER_GROUPS:
        group = db.query(FAMLedgerGroup).filter(FAMLedgerGroup.company_id == company_id, FAMLedgerGroup.group_code == code).first()
        if not group:
            group = FAMLedgerGroup(company_id=company_id, group_name=name, group_code=code, nature=nature, system_group=True, sequence_order=sequence, active=True)
            db.add(group)
            db.flush()
        groups_by_code[code] = group
    for _name, code, _nature, parent_code, _sequence in SYSTEM_LEDGER_GROUPS:
        if parent_code and groups_by_code[code].parent_group_id != groups_by_code[parent_code].id:
            groups_by_code[code].parent_group_id = groups_by_code[parent_code].id

    for code, name, group_code, nature, ledger_type in DEFAULT_LEDGERS:
        ledger = db.query(FAMLedger).filter(FAMLedger.company_id == company_id, FAMLedger.ledger_code == code).first()
        if not ledger:
            db.add(
                FAMLedger(
                    company_id=company_id,
                    ledger_code=code,
                    ledger_name=name,
                    ledger_group_id=groups_by_code[group_code].id,
                    nature=nature,
                    ledger_type=ledger_type,
                    gst_applicable="GST" in name,
                    opening_balance_dr=Decimal("0"),
                    opening_balance_cr=Decimal("0"),
                    current_balance_dr=Decimal("0"),
                    current_balance_cr=Decimal("0"),
                    active=True,
                    system_ledger=True,
                )
            )
    for code, name, category, prefix in SYSTEM_VOUCHER_TYPES:
        voucher_type = db.query(FAMVoucherType).filter(FAMVoucherType.company_id == company_id, FAMVoucherType.voucher_type_code == code).first()
        if not voucher_type:
            db.add(
                FAMVoucherType(
                    company_id=company_id,
                    voucher_type_code=code,
                    voucher_type_name=name,
                    category=category,
                    numbering_prefix=prefix,
                    numbering_sequence=1,
                    auto_numbering=True,
                    active=True,
                    system_type=True,
                )
            )
    db.flush()
