from __future__ import annotations

from fastapi import HTTPException

from app.models.user import User


FAM_VIEW_PERMISSIONS = {
    "fam_view",
    "fam_admin",
    "fam_settings_manage",
    "fam_chart_view",
    "fam_chart_manage",
    "fam_opening_balance_view",
    "fam_opening_balance_manage",
    "fam_cost_center_manage",
    "fam_branch_manage",
    "fam_audit_view",
    "fam_vouchers_view",
    "fam_vouchers_create",
    "fam_vouchers_post",
    "fam_vouchers_cancel",
    "fam_vouchers_reverse",
    "fam_voucher_types_manage",
    "fam_ledger_entries_view",
    "fam_day_book_view",
    "fam_parties_view",
    "fam_parties_manage",
    "fam_ar_view",
    "fam_ar_manage",
    "fam_ap_view",
    "fam_ap_manage",
    "fam_bill_allocation_manage",
    "fam_party_statement_view",
    "fam_srm_integration_view",
    "fam_srm_posting_manage",
    "fam_posting_rules_manage",
    "fam_posting_jobs_retry",
    "fam_accounting_status_view",
    "fam_banking_view",
    "fam_banking_manage",
    "fam_bank_statement_import",
    "fam_bank_reconcile",
    "fam_cash_book_view",
    "fam_bank_book_view",
    "fam_gst_view",
    "fam_gst_manage",
    "fam_gst_return_prepare",
    "fam_gst_einvoice_manage",
    "fam_gst_ewaybill_manage",
    "fam_gst_reconciliation_view",
    "fam_purchase_view",
    "fam_purchase_manage",
    "fam_expense_view",
    "fam_expense_manage",
    "fam_tds_view",
    "fam_tds_manage",
    "fam_vendor_payment_manage",
    "fam_inventory_view",
    "fam_inventory_manage",
    "fam_stock_post",
    "fam_stock_adjust",
    "fam_stock_transfer",
    "fam_inventory_valuation_view",
    "fam_cogs_post",
    "fam_inventory_reports_view",
    "fam_inventory_ai_use",
}
FAM_ADMIN_PERMISSIONS = {"fam_admin"}
FAM_SETTINGS_PERMISSIONS = {"fam_admin", "fam_settings_manage"}
FAM_CHART_VIEW_PERMISSIONS = {"fam_admin", "fam_chart_view", "fam_chart_manage"}
FAM_CHART_MANAGE_PERMISSIONS = {"fam_admin", "fam_chart_manage"}
FAM_OPENING_VIEW_PERMISSIONS = {"fam_admin", "fam_opening_balance_view", "fam_opening_balance_manage"}
FAM_OPENING_MANAGE_PERMISSIONS = {"fam_admin", "fam_opening_balance_manage"}
FAM_COST_CENTER_PERMISSIONS = {"fam_admin", "fam_cost_center_manage"}
FAM_BRANCH_PERMISSIONS = {"fam_admin", "fam_branch_manage"}
FAM_AUDIT_PERMISSIONS = {"fam_admin", "fam_audit_view"}
FAM_VOUCHER_VIEW_PERMISSIONS = {"fam_admin", "fam_vouchers_view", "fam_vouchers_create", "fam_vouchers_post", "fam_vouchers_cancel", "fam_vouchers_reverse"}
FAM_VOUCHER_CREATE_PERMISSIONS = {"fam_admin", "fam_vouchers_create"}
FAM_VOUCHER_POST_PERMISSIONS = {"fam_admin", "fam_vouchers_post"}
FAM_VOUCHER_CANCEL_PERMISSIONS = {"fam_admin", "fam_vouchers_cancel"}
FAM_VOUCHER_REVERSE_PERMISSIONS = {"fam_admin", "fam_vouchers_reverse"}
FAM_VOUCHER_TYPE_PERMISSIONS = {"fam_admin", "fam_voucher_types_manage"}
FAM_LEDGER_ENTRY_PERMISSIONS = {"fam_admin", "fam_ledger_entries_view"}
FAM_DAY_BOOK_PERMISSIONS = {"fam_admin", "fam_day_book_view"}
FAM_PARTIES_VIEW_PERMISSIONS = {"fam_admin", "fam_parties_view", "fam_parties_manage"}
FAM_PARTIES_MANAGE_PERMISSIONS = {"fam_admin", "fam_parties_manage"}
FAM_AR_VIEW_PERMISSIONS = {"fam_admin", "fam_ar_view", "fam_ar_manage"}
FAM_AR_MANAGE_PERMISSIONS = {"fam_admin", "fam_ar_manage"}
FAM_AP_VIEW_PERMISSIONS = {"fam_admin", "fam_ap_view", "fam_ap_manage"}
FAM_AP_MANAGE_PERMISSIONS = {"fam_admin", "fam_ap_manage"}
FAM_BILL_ALLOCATION_PERMISSIONS = {"fam_admin", "fam_bill_allocation_manage", "fam_ar_manage", "fam_ap_manage"}
FAM_PARTY_STATEMENT_PERMISSIONS = {"fam_admin", "fam_party_statement_view", "fam_parties_view", "fam_ar_view", "fam_ap_view"}
FAM_SRM_INTEGRATION_VIEW_PERMISSIONS = {"fam_admin", "fam_srm_integration_view", "fam_srm_posting_manage", "fam_accounting_status_view"}
FAM_SRM_POSTING_MANAGE_PERMISSIONS = {"fam_admin", "fam_srm_posting_manage"}
FAM_POSTING_RULES_MANAGE_PERMISSIONS = {"fam_admin", "fam_posting_rules_manage"}
FAM_POSTING_JOBS_RETRY_PERMISSIONS = {"fam_admin", "fam_posting_jobs_retry", "fam_srm_posting_manage"}
FAM_ACCOUNTING_STATUS_VIEW_PERMISSIONS = {"fam_admin", "fam_accounting_status_view", "fam_srm_integration_view", "fam_srm_posting_manage"}
FAM_BANKING_VIEW_PERMISSIONS = {"fam_admin", "fam_banking_view", "fam_banking_manage", "fam_bank_statement_import", "fam_bank_reconcile", "fam_bank_book_view", "fam_cash_book_view"}
FAM_BANKING_MANAGE_PERMISSIONS = {"fam_admin", "fam_banking_manage"}
FAM_BANK_STATEMENT_IMPORT_PERMISSIONS = {"fam_admin", "fam_bank_statement_import", "fam_banking_manage"}
FAM_BANK_RECONCILE_PERMISSIONS = {"fam_admin", "fam_bank_reconcile", "fam_banking_manage"}
FAM_BANK_BOOK_VIEW_PERMISSIONS = {"fam_admin", "fam_bank_book_view", "fam_banking_view", "fam_banking_manage"}
FAM_CASH_BOOK_VIEW_PERMISSIONS = {"fam_admin", "fam_cash_book_view", "fam_banking_view", "fam_banking_manage"}
FAM_GST_VIEW_PERMISSIONS = {"fam_admin", "fam_gst_view", "fam_gst_manage", "fam_gst_return_prepare", "fam_gst_einvoice_manage", "fam_gst_ewaybill_manage", "fam_gst_reconciliation_view"}
FAM_GST_MANAGE_PERMISSIONS = {"fam_admin", "fam_gst_manage"}
FAM_GST_RETURN_PREPARE_PERMISSIONS = {"fam_admin", "fam_gst_return_prepare", "fam_gst_manage"}
FAM_GST_EINVOICE_PERMISSIONS = {"fam_admin", "fam_gst_einvoice_manage", "fam_gst_manage"}
FAM_GST_EWAYBILL_PERMISSIONS = {"fam_admin", "fam_gst_ewaybill_manage", "fam_gst_manage"}
FAM_GST_RECONCILIATION_PERMISSIONS = {"fam_admin", "fam_gst_reconciliation_view", "fam_gst_manage"}
FAM_PURCHASE_VIEW_PERMISSIONS = {"fam_admin", "fam_purchase_view", "fam_purchase_manage"}
FAM_PURCHASE_MANAGE_PERMISSIONS = {"fam_admin", "fam_purchase_manage"}
FAM_EXPENSE_VIEW_PERMISSIONS = {"fam_admin", "fam_expense_view", "fam_expense_manage"}
FAM_EXPENSE_MANAGE_PERMISSIONS = {"fam_admin", "fam_expense_manage"}
FAM_TDS_VIEW_PERMISSIONS = {"fam_admin", "fam_tds_view", "fam_tds_manage"}
FAM_TDS_MANAGE_PERMISSIONS = {"fam_admin", "fam_tds_manage"}
FAM_VENDOR_PAYMENT_MANAGE_PERMISSIONS = {"fam_admin", "fam_vendor_payment_manage", "fam_purchase_manage"}
FAM_INVENTORY_VIEW_PERMISSIONS = {"fam_admin", "fam_inventory_view", "fam_inventory_manage", "fam_inventory_reports_view"}
FAM_INVENTORY_MANAGE_PERMISSIONS = {"fam_admin", "fam_inventory_manage"}
FAM_STOCK_POST_PERMISSIONS = {"fam_admin", "fam_stock_post", "fam_inventory_manage"}
FAM_STOCK_ADJUST_PERMISSIONS = {"fam_admin", "fam_stock_adjust", "fam_inventory_manage"}
FAM_STOCK_TRANSFER_PERMISSIONS = {"fam_admin", "fam_stock_transfer", "fam_inventory_manage"}
FAM_INVENTORY_VALUATION_VIEW_PERMISSIONS = {"fam_admin", "fam_inventory_valuation_view", "fam_inventory_view", "fam_inventory_manage"}
FAM_COGS_POST_PERMISSIONS = {"fam_admin", "fam_cogs_post", "fam_inventory_manage"}
FAM_INVENTORY_REPORTS_VIEW_PERMISSIONS = {"fam_admin", "fam_inventory_reports_view", "fam_inventory_view", "fam_inventory_manage"}
FAM_INVENTORY_AI_USE_PERMISSIONS = {"fam_admin", "fam_inventory_ai_use", "fam_inventory_manage"}


def normalize_role(role: str | None) -> str:
    return (role or "").lower().replace(" ", "_")


def user_permission_names(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def has_any_permission(user: User, permissions: set[str]) -> bool:
    names = user_permission_names(user)
    return "*" in names or bool(names.intersection(permissions))


def require_fam_permission(user: User, permissions: set[str]) -> None:
    if not has_any_permission(user, permissions):
        raise HTTPException(status_code=403, detail=f"Required FAM permissions: {', '.join(sorted(permissions))}")


def company_id_for(user: User) -> int:
    return int(getattr(user, "organization_id", None) or 1)
