from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def auth_headers_for(client, db, email: str, role_name: str, password: str = "Password@123", permissions: list[str] | None = None):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name, is_system=True)
        db.add(role)
        db.flush()
    if permissions is not None:
        role.permissions = []
        for name in permissions:
            permission = db.query(Permission).filter(Permission.name == name).first()
            if not permission:
                permission = Permission(name=name, description=name, module="fam")
                db.add(permission)
                db.flush()
            role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash(password), is_active=True, is_superuser=False, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password, "module": "fam"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


FAM_ADMIN_PERMISSIONS = [
    "fam_view",
    "fam_manage",
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
    "fam_vendor_payment_manage", "fam_inventory_view", "fam_inventory_manage", "fam_stock_post", "fam_stock_adjust", "fam_stock_transfer", "fam_inventory_valuation_view", "fam_cogs_post", "fam_inventory_reports_view", "fam_inventory_ai_use",
]


def fam_admin_headers(client, db, email: str = "fam-admin@example.com"):
    return auth_headers_for(client, db, email, "fam_admin", permissions=FAM_ADMIN_PERMISSIONS)


def voucher_seed_ids(client, headers):
    client.get("/api/v1/fam/dashboard", headers=headers)
    voucher_types = client.get("/api/v1/fam/voucher-types", headers=headers).json()["items"]
    ledgers = client.get("/api/v1/fam/ledgers", headers=headers).json()["items"]
    return voucher_types[0]["id"], ledgers[0]["id"], ledgers[1]["id"]


def balanced_voucher_payload(client, headers, amount=1000):
    voucher_type_id, debit_ledger_id, credit_ledger_id = voucher_seed_ids(client, headers)
    return {
        "voucher_type_id": voucher_type_id,
        "voucher_date": "2026-06-06",
        "reference_number": "TEST-REF",
        "narration": "Balanced test voucher",
        "source_module": "fam",
        "lines": [
            {"ledger_id": debit_ledger_id, "debit_amount": amount, "credit_amount": 0, "narration": "Debit"},
            {"ledger_id": credit_ledger_id, "debit_amount": 0, "credit_amount": amount, "narration": "Credit"},
        ],
    }


def create_balanced_voucher(client, headers, amount=1000):
    response = client.post("/api/v1/fam/vouchers", headers=headers, json=balanced_voucher_payload(client, headers, amount))
    assert response.status_code == 201, response.text
    return response.json()


def party_payload(party_type="customer", code="CUST-001", name="Acme Customer"):
    return {
        "party_type": party_type,
        "party_code": code,
        "legal_name": name,
        "trade_name": name,
        "registration_type": "regular",
        "state_code": "29",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "billing_address": "Bengaluru",
        "shipping_address": "Bengaluru",
        "email": "accounts@example.com",
        "payment_terms_days": 30,
        "credit_limit": 100000,
        "opening_balance_dr": 0,
        "opening_balance_cr": 0,
        "active": True,
        "create_ledger": True,
        "contacts": [{"name": "Accounts Contact", "email": "accounts@example.com", "is_primary": True}],
    }


def create_party(client, headers, party_type="customer", code="CUST-001", name="Acme Customer"):
    response = client.post("/api/v1/fam/parties", headers=headers, json=party_payload(party_type, code, name))
    assert response.status_code == 201, response.text
    return response.json()


def create_bill(client, headers, party, bill_number="BILL-001", bill_type="invoice", amount=1000):
    response = client.post("/api/v1/fam/bill-references", headers=headers, json={
        "party_id": party["id"],
        "bill_number": bill_number,
        "bill_date": "2026-06-01",
        "bill_type": bill_type,
        "original_amount": amount,
        "source_module": "fam",
    })
    assert response.status_code == 201, response.text
    return response.json()


def ledger_by_type(client, headers, ledger_type: str):
    response = client.get("/api/v1/fam/ledgers", headers=headers)
    assert response.status_code == 200, response.text
    for ledger in response.json()["items"]:
        if ledger["ledger_type"] == ledger_type:
            return ledger
    raise AssertionError(f"Missing {ledger_type} ledger")


def ledger_by_nature(client, headers, nature: str):
    response = client.get("/api/v1/fam/ledgers", headers=headers)
    assert response.status_code == 200, response.text
    for ledger in response.json()["items"]:
        if ledger["nature"] == nature:
            return ledger
    raise AssertionError(f"Missing {nature} ledger")


def create_bank_account(client, headers):
    bank_ledger = ledger_by_type(client, headers, "bank")
    response = client.post("/api/v1/fam/bank-accounts", headers=headers, json={
        "ledger_id": bank_ledger["id"],
        "bank_name": "HDFC Bank",
        "branch_name": "Bengaluru",
        "account_number_masked": "XXXX1234",
        "ifsc": "HDFC0001234",
        "account_type": "current",
        "opening_balance": 0,
    })
    assert response.status_code == 201, response.text
    return response.json()

