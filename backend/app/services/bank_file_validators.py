from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


@dataclass(frozen=True)
class BankValidationRule:
    account_min: int
    account_max: int
    allowed_modes: set[str]
    max_amount_by_mode: dict[str, Decimal | None]
    min_amount_by_mode: dict[str, Decimal]
    name_max_length: int = 80


DEFAULT_RULE = BankValidationRule(
    account_min=9,
    account_max=18,
    allowed_modes={"NEFT", "RTGS", "IMPS"},
    max_amount_by_mode={"NEFT": Decimal("4999999.99"), "RTGS": None, "IMPS": Decimal("500000.00")},
    min_amount_by_mode={"NEFT": Decimal("1.00"), "RTGS": Decimal("200000.00"), "IMPS": Decimal("1.00")},
)


BANK_RULES: dict[str, BankValidationRule] = {
    "HDFC": BankValidationRule(
        account_min=9,
        account_max=18,
        allowed_modes={"NEFT", "RTGS", "IMPS"},
        max_amount_by_mode={"NEFT": Decimal("4999999.99"), "RTGS": None, "IMPS": Decimal("500000.00")},
        min_amount_by_mode={"NEFT": Decimal("1.00"), "RTGS": Decimal("200000.00"), "IMPS": Decimal("1.00")},
    ),
    "ICICI": BankValidationRule(
        account_min=12,
        account_max=16,
        allowed_modes={"NEFT", "RTGS", "IMPS"},
        max_amount_by_mode={"NEFT": Decimal("4999999.99"), "RTGS": None, "IMPS": Decimal("500000.00")},
        min_amount_by_mode={"NEFT": Decimal("1.00"), "RTGS": Decimal("200000.00"), "IMPS": Decimal("1.00")},
    ),
    "SBI": BankValidationRule(
        account_min=11,
        account_max=17,
        allowed_modes={"NEFT", "RTGS"},
        max_amount_by_mode={"NEFT": Decimal("4999999.99"), "RTGS": None},
        min_amount_by_mode={"NEFT": Decimal("1.00"), "RTGS": Decimal("200000.00")},
    ),
    "AXIS": BankValidationRule(
        account_min=9,
        account_max=15,
        allowed_modes={"NEFT", "RTGS", "IMPS"},
        max_amount_by_mode={"NEFT": Decimal("4999999.99"), "RTGS": None, "IMPS": Decimal("500000.00")},
        min_amount_by_mode={"NEFT": Decimal("1.00"), "RTGS": Decimal("200000.00"), "IMPS": Decimal("1.00")},
    ),
}


def normalize_bank_name(bank_name: str | None) -> str:
    value = (bank_name or "").strip().upper()
    if "HDFC" in value:
        return "HDFC"
    if "ICICI" in value:
        return "ICICI"
    if value in {"SBI", "STATE BANK OF INDIA"} or "STATE BANK" in value:
        return "SBI"
    if "AXIS" in value:
        return "AXIS"
    return value or "GENERIC"


def _amount(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def validate_bank_file_rows(
    rows: list[dict[str, Any]],
    bank_name: str,
    payment_mode: str | None = None,
) -> dict[str, Any]:
    bank_code = normalize_bank_name(bank_name)
    rule = BANK_RULES.get(bank_code, DEFAULT_RULE)
    mode = (payment_mode or "NEFT").strip().upper()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_accounts: dict[str, Any] = {}

    if mode not in rule.allowed_modes:
        errors.append({
            "code": "UNSUPPORTED_PAYMENT_MODE",
            "message": f"{bank_code} does not allow {mode}. Allowed modes: {', '.join(sorted(rule.allowed_modes))}",
            "payment_mode": mode,
        })

    for index, row in enumerate(rows, start=1):
        employee_id = _row_value(row, "employee_id")
        employee_code = _row_value(row, "employee_code")
        row_ref = {"row": index, "employee_id": employee_id, "employee_code": employee_code}
        name = str(_row_value(row, "account_holder_name", "employee_name") or "").strip()
        account = re.sub(r"\s+", "", str(_row_value(row, "account_number") or ""))
        ifsc = str(_row_value(row, "ifsc") or "").strip().upper()
        amount = _amount(_row_value(row, "net_payable", "net_salary", "amount"))

        if not name:
            errors.append({**row_ref, "code": "MISSING_BENEFICIARY_NAME", "message": "Beneficiary name is mandatory"})
        elif len(name) > rule.name_max_length:
            warnings.append({**row_ref, "code": "BENEFICIARY_NAME_LONG", "message": f"Beneficiary name exceeds {rule.name_max_length} characters"})
        if not account:
            errors.append({**row_ref, "code": "MISSING_ACCOUNT", "message": "Account number is mandatory"})
        elif not account.isdigit() or not (rule.account_min <= len(account) <= rule.account_max):
            errors.append({**row_ref, "code": "INVALID_ACCOUNT", "message": f"{bank_code} account number must be {rule.account_min}-{rule.account_max} digits"})
        elif account in seen_accounts:
            errors.append({**row_ref, "code": "DUPLICATE_ACCOUNT", "message": f"Duplicate account also used by employee {seen_accounts[account]}"})
        else:
            seen_accounts[account] = employee_id or employee_code or index

        if not ifsc:
            errors.append({**row_ref, "code": "MISSING_IFSC", "message": "IFSC is mandatory"})
        elif not IFSC_RE.fullmatch(ifsc):
            errors.append({**row_ref, "code": "INVALID_IFSC", "message": "IFSC must match Indian IFSC format"})

        if amount <= 0:
            errors.append({**row_ref, "code": "INVALID_AMOUNT", "message": "Amount must be greater than zero"})
        min_amount = rule.min_amount_by_mode.get(mode)
        max_amount = rule.max_amount_by_mode.get(mode)
        if min_amount and amount > 0 and amount < min_amount:
            errors.append({**row_ref, "code": "AMOUNT_BELOW_MODE_MINIMUM", "message": f"{mode} amount must be at least {min_amount}"})
        if max_amount and amount > max_amount:
            errors.append({**row_ref, "code": "AMOUNT_ABOVE_MODE_MAXIMUM", "message": f"{mode} amount cannot exceed {max_amount}"})

    if bank_code == "GENERIC":
        warnings.append({"code": "GENERIC_BANK_RULES", "message": "Bank-specific rules not configured; applied generic NEFT/RTGS/IMPS checks"})

    return {
        "bank_name": bank_name,
        "bank_code": bank_code,
        "payment_mode": mode,
        "checked_rows": len(rows),
        "status": "Failed" if errors else "Passed",
        "errors": errors,
        "warnings": warnings,
    }
