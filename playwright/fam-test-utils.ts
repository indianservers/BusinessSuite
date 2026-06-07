import { expect, type Page } from "../frontend/node_modules/playwright/test";

export type FAMRole = "admin" | "fam_admin" | "accountant" | "finance_manager" | "auditor" | "business_owner" | "fam_viewer" | "employee";

const users: Record<FAMRole, { id: number; email: string; role: string; is_superuser: boolean; employee_id: number | null }> = {
  admin: { id: 200, email: "admin@example.com", role: "admin", is_superuser: true, employee_id: null },
  fam_admin: { id: 201, email: "admin@fam.example.com", role: "fam_admin", is_superuser: false, employee_id: null },
  accountant: { id: 202, email: "accountant@fam.example.com", role: "accountant", is_superuser: false, employee_id: null },
  finance_manager: { id: 203, email: "finance@fam.example.com", role: "finance_manager", is_superuser: false, employee_id: null },
  auditor: { id: 204, email: "auditor@fam.example.com", role: "auditor", is_superuser: false, employee_id: null },
  business_owner: { id: 205, email: "owner@fam.example.com", role: "business_owner", is_superuser: false, employee_id: null },
  fam_viewer: { id: 206, email: "viewer@fam.example.com", role: "fam_viewer", is_superuser: false, employee_id: null },
  employee: { id: 207, email: "employee@fam.example.com", role: "employee", is_superuser: false, employee_id: 207 },
};

export const famRoutes = [
  "/fam",
  "/fam/dashboard",
  "/fam/settings",
  "/fam/financial-years",
  "/fam/chart-of-accounts",
  "/fam/ledger-groups",
  "/fam/ledgers",
  "/fam/ledgers/1/entries",
  "/fam/opening-balances",
  "/fam/voucher-types",
  "/fam/vouchers",
  "/fam/vouchers/new",
  "/fam/vouchers/1",
  "/fam/journal",
  "/fam/day-book",
  "/fam/ledger-entries",
  "/fam/cost-centers",
  "/fam/branches",
  "/fam/audit",
  "/fam/parties",
  "/fam/customers",
  "/fam/vendors",
  "/fam/parties/1",
  "/fam/ar",
  "/fam/ar/aging",
  "/fam/ar/outstanding",
  "/fam/ap",
  "/fam/ap/aging",
  "/fam/ap/outstanding",
  "/fam/bill-references",
  "/fam/bill-allocations",
  "/fam/integrations/srm",
  "/fam/posting-jobs",
  "/fam/posting-jobs/1",
  "/fam/posting-rules",
  "/fam/banking",
  "/fam/bank-accounts",
  "/fam/payment-modes",
  "/fam/bank-statements",
  "/fam/bank-statements/1",
  "/fam/bank-reconciliation",
  "/fam/bank-book",
  "/fam/cash-book",
  "/fam/contra",
  "/fam/bank-charges",
  "/fam/purchases",
  "/fam/purchase-bills",
  "/fam/purchase-bills/new",
  "/fam/purchase-bills/1",
  "/fam/expenses",
  "/fam/expenses/new",
  "/fam/tds",
  "/fam/tds/sections",
  "/fam/tds/transactions",
  "/fam/tds/payable",
  "/fam/purchase-register",
  "/fam/expense-register",
  "/fam/vendor-payments",
  "/fam/payables/dashboard",
  "/fam/inventory",
  "/fam/inventory/dashboard",
  "/fam/inventory/items",
  "/fam/inventory/items/1",
  "/fam/inventory/categories",
  "/fam/inventory/stock-groups",
  "/fam/inventory/units",
  "/fam/inventory/warehouses",
  "/fam/inventory/stock-in",
  "/fam/inventory/stock-out",
  "/fam/inventory/stock-transfers",
  "/fam/inventory/stock-adjustments",
  "/fam/inventory/purchase-receipts",
  "/fam/inventory/delivery-notes",
  "/fam/inventory/stock-summary",
  "/fam/inventory/item-ledger/1",
  "/fam/inventory/valuation",
  "/fam/inventory/reorder-alerts",
  "/fam/inventory/reports",
  "/fam/inventory/ai",
];

export async function authenticate(page: Page, role: FAMRole) {
  const user = users[role];
  await installApiStubs(page, user);
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "fam-token",
      refreshToken: "fam-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: {
        accessToken: "fam-token",
        refreshToken: "fam-refresh",
        user: authUser,
        isAuthenticated: true,
      },
      version: 0,
    }));
  }, user);
}

export async function installApiStubs(page: Page, user = users.fam_admin) {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let body: unknown = {};

    if (path.includes("/auth/me")) {
      body = { id: user.id, email: user.email, role: { name: user.role }, is_superuser: user.is_superuser, employee_id: user.employee_id };
    } else if (path.includes("/auth/sso/providers")) {
      body = [];
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (path.startsWith("/fam")) {
      if (isForbiddenFamMutation(user.role, method, path)) {
        await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Forbidden FAM action" }) });
        return;
      }
      body = famResponse(path, method, url);
    } else if (path.startsWith("/reports")) {
      body = {};
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectHealthyFamRoute(page: Page, route: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(route)}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator(".vite-error-overlay, #webpack-dev-server-client-overlay")).toHaveCount(0);
  await expect(page.locator("body")).toContainText(/FAM|Finance|Accounting|Ledger|Opening|Audit|Branch/i, { timeout: 20_000 });
}

export async function expectDenied(page: Page, route: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
}

function isForbiddenFamMutation(role: string, method: string, path: string) {
  if (method === "GET") return false;
  if (role === "admin" || role === "fam_admin") return false;
  if (role === "accountant" || role === "finance_manager") return path.includes("/settings") || path.includes("/audit-logs");
  return true;
}

function famResponse(path: string, method: string, url: URL) {
  if (method !== "GET") {
    if (path === "/fam/settings") return settings();
    if (path === "/fam/financial-years") return { id: 2, name: "FY 2027-28", status: "open", start_date: "2027-04-01", end_date: "2028-03-31" };
    if (path === "/fam/ledger-groups") return { id: 8, group_code: "DEP", group_name: "Deposits", nature: "asset", active: true };
    if (path === "/fam/ledgers") return { id: 20, ledger_code: "BANK-HDFC", ledger_name: "HDFC Bank", nature: "asset", ledger_type: "bank" };
    if (path === "/fam/opening-balances") return { id: 1, financial_year_id: 1, ledger_id: 1, debit_amount: 1000, credit_amount: 0, posted: false };
    if (path === "/fam/opening-balances/post") return { posted: true, count: 2, debitTotal: 1000, creditTotal: 1000 };
    if (path === "/fam/vouchers") return voucher();
    if (path === "/fam/parties") return party();
    if (path === "/fam/bill-references") return billReference();
    if (path === "/fam/bill-allocations") return billAllocation();
    if (path.includes("/fam/integrations/srm/post-invoice/1")) return postingResult("invoice");
    if (path.includes("/fam/integrations/srm/post-receipt/1")) return postingResult("receipt");
    if (path.includes("/fam/integrations/srm/post-allocation/1")) return { status: "posted", allocation: billAllocation(), postingJob: postingJob({ source_record_type: "allocation", posting_type: "allocation" }) };
    if (path.includes("/fam/integrations/srm/reverse/invoice/1")) return { status: "reversed", reversalVoucher: { ...voucher(), id: 4, voucher_number: "ADJ-00001", status: "posted" }, postingJob: postingJob({ posting_type: "reversal", status: "reversed" }) };
    if (path.includes("/fam/posting-jobs/1/retry")) return postingResult("invoice");
    if (path === "/fam/posting-rules") return postingRule();
    if (path === "/fam/bank-accounts") return bankAccount();
    if (path === "/fam/payment-modes") return paymentMode();
    if (path === "/fam/bank-statements/import") return bankStatement();
    if (path.includes("/fam/bank-statements/1/auto-match")) return { statement: bankStatement({ status: "matched" }), suggestions: [{ statement_line_id: 1, voucher_id: 1, confidence_score: 95 }] };
    if (path.includes("/fam/bank-statements/1/match")) return { statement: bankStatement({ status: "matched", lines: [{ ...bankStatementLine(), matched_status: "matched", matched_voucher_id: 1 }] }), match: { id: 1, statement_line_id: 1, voucher_id: 1, match_type: "confirmed" } };
    if (path.includes("/fam/bank-statements/1/ignore-line")) return { statement: bankStatement(), line: { ...bankStatementLine(), matched_status: "ignored" } };
    if (path.includes("/fam/bank-statements/1/reconcile")) return { statement: bankStatement({ status: "reconciled", lines: [{ ...bankStatementLine(), matched_status: "matched", matched_voucher_id: 1 }] }), session: reconciliationSession() };
    if (path === "/fam/bank-charges/post") return { ...voucher(), status: "posted", voucher_number: "PV-00001", source_record_type: "bank_charge" };
    if (path === "/fam/contra/post") return { ...voucher(), status: "posted", voucher_number: "CV-00001", source_record_type: "contra" };
    if (path === "/fam/purchase-bills") return purchaseBill();
    if (path.includes("/fam/purchase-bills/1/post")) return { ...purchaseBill(), status: "posted", voucher_id: 1, voucher: { ...voucher(), status: "posted" } };
    if (path.includes("/fam/purchase-bills/1/cancel")) return { ...purchaseBill(), status: "cancelled" };
    if (path === "/fam/expenses") return expenseClaim();
    if (path.includes("/fam/expenses/1/post")) return { ...expenseClaim(), status: "posted", voucher_id: 1, voucher: { ...voucher(), status: "posted" } };
    if (path === "/fam/tds/sections") return tdsSection();
    if (path === "/fam/tds/rates") return { id: 1, section_id: 1, rate: 10, effective_from: "2026-04-01", active: true };
    if (path === "/fam/tds/calculate") return { section_id: 1, taxable_amount: 1000, tds_rate: 10, threshold_amount: 30000, tds_amount: 0, status: "calculated" };
    if (path === "/fam/vendor-payments/prepare") return { id: 1, run_number: "VPR-001", payment_date: "2026-06-06", total_amount: 900, status: "prepared" };
    if (path === "/fam/vendor-payments/post") return { id: 1, run_number: "VPR-001", payment_date: "2026-06-06", total_amount: 900, status: "posted", voucher: { ...voucher(), status: "posted" } };
    if (path === "/fam/inventory/items") return inventoryItem();
    if (path === "/fam/inventory/stock-groups") return inventoryGroup();
    if (path === "/fam/inventory/units") return inventoryUnit();
    if (path === "/fam/inventory/warehouses") return inventoryWarehouse();
    if (path === "/fam/inventory/opening-stock") return { id: 1, opening_number: "OPEN-001", stock_item_id: 1, warehouse_id: 1, quantity: 10, rate: 100, value: 1000 };
    if (path === "/fam/inventory/stock-movements") return { id: 1, movement_number: "MOV-001", movement_date: "2026-06-06", movement_type: "stock_in", status: "draft" };
    if (path.includes("/fam/inventory/stock-movements/1/post")) return { id: 1, movement_number: "MOV-001", status: "posted" };
    if (path === "/fam/inventory/stock-transfers") return { id: 1, transfer_number: "TRF-001", status: "draft" };
    if (path.includes("/fam/inventory/stock-transfers/1/post")) return { id: 1, transfer_number: "TRF-001", status: "posted" };
    if (path === "/fam/inventory/stock-adjustments") return { id: 1, adjustment_number: "ADJ-001", status: "draft" };
    if (path.includes("/fam/inventory/stock-adjustments/1/post")) return { id: 1, adjustment_number: "ADJ-001", status: "posted", voucher_id: 1 };
    if (path === "/fam/inventory/cogs/post") return { amount: 200, voucher: { ...voucher(), status: "posted" } };
    if (path === "/fam/inventory/ai") return { id: 1, status: "not_configured", response: { message: "Inventory AI provider is not configured. No recommendation was generated." } };
    if (path.includes("/fam/vouchers/1/post")) return { ...voucher(), status: "posted" };
    if (path.includes("/fam/vouchers/1/cancel")) return { ...voucher(), status: "cancelled" };
    if (path.includes("/fam/vouchers/1/reverse")) return { ...voucher(), id: 2, voucher_number: "REV-JV-00001", reversed_voucher_id: 1 };
    if (path.includes("/fam/vouchers/1/clone")) return { ...voucher(), id: 3, voucher_number: "JV-00002" };
    if (path === "/fam/cost-centers") return { id: 1, code: "SALES", name: "Sales Department", active: true };
    if (path === "/fam/branches") return { id: 1, branch_code: "BLR", branch_name: "Bengaluru", active: true };
    return { id: 1, status: "saved" };
  }
  if (path.includes("/module-info")) return { key: "fam", name: "Finance & Accounting Management", shortName: "FAM" };
  if (path.includes("/fam/inventory/source-audit")) return { source_root: "C:\\Indian Servers\\AI Inventory Management Software", source_exists: true, merged_under: "FAM", files: [{ path: "app/services/stock_service.py", exists: true }, { path: "app/models/product.py", exists: true }] };
  if (path.includes("/fam/inventory/dashboard") || path === "/fam/inventory") return { items_count: 1, warehouses_count: 1, total_stock_value: 1000, low_stock_count: 1, recent_movements: [{ id: 1, movement_number: "MOV-001", movement_type: "opening_stock", status: "posted" }] };
  if (path.includes("/fam/inventory/items/1")) return { ...inventoryItem(), ledger: [inventoryLedgerLine()] };
  if (path.includes("/fam/inventory/items")) return { items: [inventoryItem()], total: 1 };
  if (path.includes("/fam/inventory/stock-groups") || path.includes("/fam/inventory/categories")) return { items: [inventoryGroup()], total: 1 };
  if (path.includes("/fam/inventory/units")) return { items: [inventoryUnit()], total: 1 };
  if (path.includes("/fam/inventory/warehouses")) return { items: [inventoryWarehouse()], total: 1 };
  if (path.includes("/fam/inventory/stock-movements")) return { items: [{ id: 1, movement_number: "MOV-001", movement_type: "stock_in", status: "posted" }], total: 1 };
  if (path.includes("/fam/inventory/item-ledger/1")) return { items: [inventoryLedgerLine()], total: 1 };
  if (path.includes("/fam/inventory/stock-summary")) return { items: [inventorySummary()], total: 1, total_stock_value: 1000 };
  if (path.includes("/fam/inventory/valuation")) return { items: [inventorySummary()], total: 1, total_inventory_value: 1000, valuation_method: "weighted_average" };
  if (path.includes("/fam/inventory/reorder-alerts")) return { items: [inventorySummary({ is_low_stock: true })], total: 1 };
  if (path.includes("/fam/inventory/reports")) return { summary: { items: [inventorySummary()], total: 1 }, valuation: { total_inventory_value: 1000, valuation_method: "weighted_average" }, reorder_alerts: { items: [inventorySummary({ is_low_stock: true })], total: 1 } };
  if (path.includes("/dashboard")) {
    return {
      currentFinancialYear: { id: 1, name: "FY 2026-27", status: "open" },
      totalAssets: 50000,
      totalLiabilities: 25000,
      totalIncome: 100000,
      totalExpenses: 30000,
      cashAndBankBalance: 50000,
      receivablesPlaceholder: "Pending SRM/FAM posting integration",
      payablesPlaceholder: "Pending purchase/accounting voucher phase",
      gstCompliancePlaceholder: "Configured later; no fake GST integration",
      booksStatus: "open",
      recentAccountingActivity: [{ id: 1, record_type: "ledger", record_id: 1, action: "CREATE", performed_at: "2026-06-05T00:00:00Z" }],
    };
  }
  if (path.includes("/settings")) return settings();
  if (path.includes("/voucher-audit/1")) return { items: [{ id: 1, voucher_id: 1, action: "CREATE", performed_by: 201, performed_at: "2026-06-06T00:00:00Z" }] };
  if (path.includes("/integrations/srm/accounting-status/invoice/1")) return accountingStatus("invoice");
  if (path.includes("/integrations/srm/status")) return srmIntegrationStatus();
  if (path.includes("/posting-jobs/1")) return { ...postingJob(), accountingStatus: accountingStatus("invoice") };
  if (path.includes("/posting-jobs")) return { items: [postingJob(), postingJob({ id: 2, source_record_type: "receipt", posting_type: "receipt", status: "failed", error_message: "Missing bank ledger" })], total: 2 };
  if (path.includes("/posting-rules")) return { items: [postingRule()], total: 1 };
  if (path.includes("/bank-statements/1")) return bankStatement();
  if (path.includes("/bank-statements")) return { items: [bankStatement()], total: 1 };
  if (path.includes("/bank-reconciliation")) return bankReconciliation();
  if (path.includes("/bank-book")) return bankBook();
  if (path.includes("/cash-book")) return cashBook();
  if (path.includes("/bank-accounts")) return { items: [bankAccount()], total: 1 };
  if (path.includes("/payment-modes")) return { items: [paymentMode()], total: 1 };
  if (path.includes("/purchase-bills/1")) return purchaseBill();
  if (path.includes("/purchase-bills")) return { items: [purchaseBill()], total: 1 };
  if (path.includes("/expenses")) return { items: [expenseClaim()], total: 1 };
  if (path.includes("/tds/sections")) return { items: [tdsSection()], total: 1 };
  if (path.includes("/tds/rates")) return { items: [{ id: 1, section_id: 1, rate: 10, effective_from: "2026-04-01", active: true }], total: 1 };
  if (path.includes("/tds/transactions")) return { items: [tdsTransaction()], total: 1 };
  if (path.includes("/tds/payable")) return { items: [tdsTransaction()], total: 1, tds_payable: 100, total_payable: 100, filing_status: "not_configured" };
  if (path.includes("/purchase-register")) return purchaseRegister();
  if (path.includes("/expense-register")) return expenseRegister();
  if (path.includes("/payables/dashboard")) return payablesDashboard();
  if (path.includes("/parties/1/statement")) return { party: party(), billReferences: billReferences(), allocations: billAllocations(), outstanding: 1250 };
  if (path.includes("/parties/1/outstanding")) return { party_id: 1, outstanding: 1250, openBills: 2, items: billReferences() };
  if (path.includes("/parties/1/bill-references")) return { items: billReferences(), total: billReferences().length };
  if (path.includes("/parties/1")) return party();
  if (path.includes("/parties")) {
    const partyType = url.searchParams.get("party_type");
    return { items: parties(partyType === "vendor" ? "vendor" : partyType === "customer" ? "customer" : undefined), total: partyType ? 1 : 2 };
  }
  if (path.includes("/ar/aging")) return aging("invoice");
  if (path.includes("/ap/aging")) return aging("bill");
  if (path.includes("/ar/outstanding")) return outstanding("invoice");
  if (path.includes("/ap/outstanding")) return outstanding("bill");
  if (path.includes("/bill-references")) return { items: billReferences(), total: billReferences().length };
  if (path.includes("/bill-allocations")) return { items: billAllocations(), total: billAllocations().length };
  if (path.includes("/voucher-types")) return { items: voucherTypes(), total: voucherTypes().length };
  if (path.includes("/vouchers/1")) return voucher();
  if (path.includes("/vouchers")) return { items: [voucher()], total: 1 };
  if (path.includes("/day-book")) return { items: [voucher()], total: 1, debitTotal: 1000, creditTotal: 1000 };
  if (path.includes("/ledger-entries")) return { items: ledgerEntries(), total: 2, debitTotal: 1000, creditTotal: 1000 };
  if (path.includes("/financial-years")) return { items: [{ id: 1, name: "FY 2026-27", start_date: "2026-04-01", end_date: "2027-03-31", status: "open", is_current: true }] };
  if (path.includes("/ledger-groups")) return { items: ledgerGroups() };
  if (path.includes("/ledgers/1/entries")) return { ledger: ledgers()[0], items: ledgerEntries(), openingBalance: 0, debitMovement: 1000, creditMovement: 1000, closingBalance: 0 };
  if (path.includes("/ledgers")) return { items: ledgers() };
  if (path.includes("/opening-balances")) return { items: [{ id: 1, financial_year_id: 1, ledger_id: 1, debit_amount: 1000, credit_amount: 1000, posted: false }], debitTotal: 1000, creditTotal: 1000, difference: 0 };
  if (path.includes("/cost-centers")) return { items: [{ id: 1, code: "SALES", name: "Sales Department", active: true }] };
  if (path.includes("/branches")) return { items: [{ id: 1, branch_code: "BLR", branch_name: "Bengaluru", gstin: "29ABCDE1234F1Z5", active: true }] };
  if (path.includes("/audit-logs")) return { items: [{ id: 1, record_type: "ledger", record_id: 1, action: "CREATE", performed_by: 201, performed_at: "2026-06-05T00:00:00Z" }] };
  if (path.includes("/chart-of-accounts")) return { groups: ledgerGroups(), ledgers: ledgers(), totalGroups: 2, totalLedgers: 2 };
  return {};
}

function voucherTypes() {
  return [
    { id: 1, voucher_type_code: "JV", voucher_type_name: "Journal", category: "journal", numbering_prefix: "JV", numbering_sequence: 2, active: true },
    { id: 2, voucher_type_code: "RV", voucher_type_name: "Receipt", category: "receipt", numbering_prefix: "RV", numbering_sequence: 1, active: true },
  ];
}

function voucher() {
  return {
    id: 1,
    voucher_type_id: 1,
    financial_year_id: 1,
    voucher_number: "JV-00001",
    voucher_date: "2026-06-06",
    reference_number: "REF-1",
    narration: "Balanced journal voucher",
    total_debit: 1000,
    total_credit: 1000,
    status: "draft",
    source_module: "fam",
    lines: [
      { id: 1, ledger_id: 1, debit_amount: 1000, credit_amount: 0, narration: "Cash debit" },
      { id: 2, ledger_id: 2, debit_amount: 0, credit_amount: 1000, narration: "Capital credit" },
    ],
  };
}

function ledgerEntries() {
  return [
    { id: 1, voucher_number: "JV-00001", voucher_date: "2026-06-06", ledger_id: 1, debit_amount: 1000, credit_amount: 0, running_balance: 1000, source_module: "fam" },
    { id: 2, voucher_number: "JV-00001", voucher_date: "2026-06-06", ledger_id: 2, debit_amount: 0, credit_amount: 1000, running_balance: -1000, source_module: "fam" },
    { id: 3, voucher_number: "RV-00001", voucher_date: "2026-06-06", ledger_id: 3, debit_amount: 1000, credit_amount: 0, running_balance: 1000, narration: "Customer receipt REF-1", source_module: "fam" },
  ];
}

function settings() {
  return {
    id: 1,
    legal_name: "Acme India Private Limited",
    trade_name: "Acme India",
    country_code: "IN",
    base_currency: "INR",
    financial_year_start_month: 4,
    books_start_date: "2026-04-01",
    gstin: "29ABCDE1234F1Z5",
    pan: "ABCDE1234F",
    tan: "BLRA12345B",
    cin: "U72900KA2026PTC123456",
    state_code: "29",
    registered_address: "Bengaluru",
    decimal_places: 2,
  };
}

function ledgerGroups() {
  return [
    { id: 1, group_code: "CA", group_name: "Current Assets", nature: "asset", system_group: true, active: true },
    { id: 2, group_code: "CL", group_name: "Current Liabilities", nature: "liability", system_group: true, active: true },
  ];
}

function ledgers() {
  return [
    { id: 1, ledger_code: "CASH", ledger_name: "Cash", ledger_group_id: 1, nature: "asset", ledger_type: "cash", current_balance_dr: 1000, current_balance_cr: 0, active: true },
    { id: 2, ledger_code: "CAPITAL", ledger_name: "Capital", ledger_group_id: 2, nature: "liability", ledger_type: "liability", current_balance_dr: 0, current_balance_cr: 1000, active: true },
    { id: 3, ledger_code: "BANK-HDFC", ledger_name: "HDFC Bank", ledger_group_id: 1, nature: "asset", ledger_type: "bank", current_balance_dr: 1000, current_balance_cr: 0, active: true },
  ];
}

function bankAccount() {
  return { id: 1, company_id: 1, ledger_id: 3, bank_name: "HDFC Bank", branch_name: "Bengaluru", account_number_masked: "XXXX1234", ifsc: "HDFC0001234", account_type: "current", opening_balance: 0, active: true };
}

function paymentMode() {
  return { id: 1, company_id: 1, name: "UPI", type: "upi", default_ledger_id: 3, active: true };
}

function bankStatementLine(overrides: Record<string, unknown> = {}) {
  return { id: 1, statement_id: 1, transaction_date: "2026-06-06", value_date: "2026-06-06", description: "Customer receipt REF-1", reference_number: "REF-1", debit_amount: 0, credit_amount: 1000, balance: 1000, matched_status: "unmatched", matched_voucher_id: null, ...overrides };
}

function bankStatement(overrides: Record<string, unknown> = {}) {
  const lines = (overrides.lines as Record<string, unknown>[] | undefined) || [bankStatementLine()];
  return { id: 1, company_id: 1, bank_account_id: 1, statement_period_start: "2026-06-01", statement_period_end: "2026-06-30", imported_file_name: "hdfc-june.csv", status: "imported", lines, summary: { total_lines: lines.length, matched: lines.filter((line) => line.matched_status === "matched").length, suggested: lines.filter((line) => line.matched_status === "suggested").length, unmatched: lines.filter((line) => line.matched_status === "unmatched").length, ignored: lines.filter((line) => line.matched_status === "ignored").length }, ...overrides };
}

function reconciliationSession() {
  return { id: 1, bank_account_id: 1, statement_id: 1, book_balance: 1000, bank_statement_balance: 1000, unreconciled_count: 0, status: "reconciled", reconciled_at: "2026-06-06T00:00:00Z" };
}

function bankReconciliation() {
  return { statements: [bankStatement()], sessions: [reconciliationSession()], unmatched_count: 1 };
}

function bankBook() {
  return { ledgers: [ledgers()[2]], items: [ledgerEntries()[2]], openingBalance: 0, debitTotal: 1000, creditTotal: 0, closingBalance: 1000 };
}

function cashBook() {
  return { ledgers: [ledgers()[0]], registers: [{ id: 1, ledger_id: 1, register_name: "Main Cash", opening_balance: 0, active: true }], items: [ledgerEntries()[0]], openingBalance: 0, debitTotal: 1000, creditTotal: 0, closingBalance: 1000 };
}

function party(type: "customer" | "vendor" | "both" = "customer") {
  return {
    id: type === "vendor" ? 2 : 1,
    party_type: type,
    party_code: type === "vendor" ? "VEND-001" : "CUST-001",
    legal_name: type === "vendor" ? "Reliable Vendor LLP" : "Acme Customer Private Limited",
    trade_name: type === "vendor" ? "Reliable Vendor" : "Acme Customer",
    ledger_id: type === "vendor" ? 12 : 11,
    gstin: "29ABCDE1234F1Z5",
    pan: "ABCDE1234F",
    state_code: "29",
    payment_terms_days: 30,
    credit_limit: 100000,
    active: true,
    contacts: [{ id: 1, name: "Accounts Contact", email: "accounts@example.com", is_primary: true }],
  };
}

function parties(type?: "customer" | "vendor") {
  if (type === "customer") return [party("customer")];
  if (type === "vendor") return [party("vendor")];
  return [party("customer"), party("vendor")];
}

function billReference(type: "invoice" | "bill" | "advance" = "invoice") {
  return {
    id: type === "bill" ? 2 : type === "advance" ? 3 : 1,
    party_id: type === "bill" ? 2 : 1,
    ledger_id: type === "bill" ? 12 : 11,
    bill_number: type === "bill" ? "BILL-001" : type === "advance" ? "ADV-001" : "INV-001",
    bill_date: "2026-06-01",
    due_date: "2026-07-01",
    bill_type: type,
    original_amount: type === "bill" ? 900 : type === "advance" ? 500 : 1250,
    outstanding_amount: type === "bill" ? 900 : type === "advance" ? 250 : 1000,
    status: "open",
  };
}

function billReferences() {
  return [billReference("invoice"), billReference("bill"), billReference("advance")];
}

function billAllocation() {
  return {
    id: 1,
    allocation_date: "2026-06-06",
    party_id: 1,
    from_bill_reference_id: 3,
    to_bill_reference_id: 1,
    allocated_amount: 250,
    allocation_type: "advance_adjustment",
  };
}

function billAllocations() {
  return [billAllocation()];
}

function postingJob(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    company_id: 1,
    source_module: "srm",
    source_record_type: "invoice",
    source_record_id: 1,
    posting_type: "sales_invoice",
    status: "posted",
    voucher_id: 1,
    retry_count: 0,
    posted_at: "2026-06-06T10:00:00Z",
    ...overrides,
  };
}

function postingRule() {
  return {
    id: 1,
    source_module: "srm",
    transaction_type: "sales_invoice",
    debit_ledger_rule_json: { type: "customer_ledger" },
    credit_ledger_rule_json: { ledger_code: "SALES" },
    tax_ledger_rule_json: { cgst: "OUTPUT-CGST", sgst: "OUTPUT-SGST" },
    active: true,
  };
}

function accountingStatus(type: string) {
  return {
    source_record_type: type,
    source_record_id: 1,
    status: "posted",
    mappings: [
      { fam_record_type: "voucher", fam_record_id: 1, mapping_status: "active" },
      { fam_record_type: "bill_reference", fam_record_id: 1, mapping_status: "active" },
    ],
  };
}

function postingResult(type: "invoice" | "receipt") {
  return {
    status: "posted",
    idempotent: false,
    postingJob: postingJob({ source_record_type: type, posting_type: type === "invoice" ? "sales_invoice" : "receipt" }),
    voucher: { ...voucher(), status: "posted", source_module: "srm", source_record_type: type },
    billReference: billReference(type === "invoice" ? "invoice" : "advance"),
    party: party("customer"),
    accountingStatus: accountingStatus(type),
  };
}

function srmIntegrationStatus() {
  return {
    pending_postings: 2,
    failed_postings: 1,
    posted_today: 4,
    unmapped_customers: 1,
    duplicate_prevention_status: "active",
    recent_jobs: [postingJob(), postingJob({ id: 2, source_record_type: "receipt", posting_type: "receipt", status: "failed", error_message: "Missing bank ledger" })],
  };
}

function aging(type: "invoice" | "bill") {
  const item = billReference(type);
  return {
    buckets: { "Not due": item.outstanding_amount, "0-30": 0, "31-60": 0, "61-90": 0, "91-180": 0, ">180": 0 },
    items: [{ ...item, aging_bucket: "Not due", overdue_days: 0 }],
    totalOutstanding: item.outstanding_amount,
  };
}

function outstanding(type: "invoice" | "bill") {
  const item = billReference(type);
  return { items: [item], totalOutstanding: item.outstanding_amount };
}

function purchaseBill() {
  return {
    id: 1,
    vendor_id: 2,
    bill_number: "PB-001",
    bill_date: "2026-06-06",
    due_date: "2026-07-06",
    gstin: "29ABCDE1234F1Z5",
    place_of_supply: "29",
    subtotal: 1000,
    discount_total: 0,
    gst_total: 180,
    tds_amount: 100,
    grand_total: 1080,
    status: "draft",
    voucher_id: null,
    lines: [{ id: 1, purchase_bill_id: 1, expense_ledger_id: 1, description: "Professional services", hsn_sac: "998314", quantity: 1, rate: 1000, taxable_value: 1000, gst_amount: 180, tds_section_id: 1, tds_amount: 100, line_total: 1080 }],
    audit_logs: [{ id: 1, action: "CREATE", performed_by: 201, performed_at: "2026-06-06T00:00:00Z", remarks: "Purchase bill created" }],
  };
}

function expenseClaim() {
  return { id: 1, claim_number: "EXP-001", employee_id: 201, claimant_name: "Finance User", claim_date: "2026-06-06", subtotal: 1200, gst_total: 0, grand_total: 1200, total_amount: 1200, status: "draft", voucher_id: null };
}

function tdsSection() {
  return { id: 1, section_code: "194J", description: "Professional fees", default_rate: 10, threshold_amount: 30000, effective_from: "2026-04-01", active: true };
}

function tdsTransaction() {
  return { id: 1, voucher_id: 1, vendor_id: 2, section_id: 1, section_code: "194J", taxable_amount: 1000, tds_rate: 10, tds_amount: 100, deduction_date: "2026-06-06", status: "deducted" };
}

function purchaseRegister() {
  const bill = purchaseBill();
  return { items: [bill], total: 1, subtotal: 1000, gst_total: 180, tds_amount: 100, grand_total: 1080, totals: { subtotal: 1000, gst_total: 180, tds_amount: 100, grand_total: 1080 } };
}

function expenseRegister() {
  const claim = expenseClaim();
  return { items: [claim], total: 1, total_amount: 1200, grand_total: 1200, totals: { total_amount: 1200, grand_total: 1200 } };
}

function payablesDashboard() {
  const bill = { ...billReference("bill"), aging_bucket: "Not due", overdue_days: 0 };
  return { items: [bill], buckets: { "Not due": 900, "0-30": 0, "31-60": 0, "61-90": 0, "91-180": 0, ">180": 0 }, totalOutstanding: 900, draftBills: 1, postedBills: 1, paidBills: 0, tdsPayable: 100 };
}

function inventoryGroup() {
  return { id: 1, group_code: "FIN", group_name: "Finished Goods", active: true };
}

function inventoryUnit() {
  return { id: 1, unit_code: "PCS", unit_name: "Pieces", symbol: "pcs", decimal_allowed: true, active: true };
}

function inventoryWarehouse() {
  return { id: 1, warehouse_code: "MAIN", warehouse_name: "Main Warehouse", active: true };
}

function inventoryItem() {
  return { id: 1, sku: "SKU-001", item_name: "Finished Good", hsn_code: "8471", current_quantity: 10, average_cost: 100, reorder_level: 12, active: true, stock_value: 1000 };
}

function inventoryLedgerLine() {
  return { id: 1, movement_id: 1, warehouse_id: 1, quantity_in: 10, quantity_out: 0, rate: 100, value: 1000, balance_quantity: 10 };
}

function inventorySummary(overrides: Record<string, unknown> = {}) {
  return { ...inventoryItem(), is_low_stock: false, ...overrides };
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function gstRegistration() {
  return { id: 1, gstin: "29ABCDE1234F1Z5", legal_name: "Business Suite Pvt Ltd", trade_name: "Business Suite", state_code: "29", registration_type: "regular", effective_from: "2026-04-01", active: true };
}
function gstRate() {
  return { id: 1, rate_name: "GST 18%", tax_type: "goods", cgst_rate: 9, sgst_rate: 9, igst_rate: 18, cess_rate: 0, effective_from: "2026-04-01", active: true };
}
function hsnSac() {
  return { id: 1, code: "998314", description: "IT consulting services", type: "sac", default_gst_rate_id: 1, active: true };
}
function gstCalculation() {
  return { taxable_value: 1000, intra_state: true, cgst_amount: 90, sgst_amount: 90, igst_amount: 0, cess_amount: 0, total_tax: 180, gross_amount: 1180, ledger_posting_required: true };
}
function gstRegister(type: string) {
  const item = { id: 1, transaction_type: type, supply_type: "b2b", gstin: "29ABCDE1234F1Z5", place_of_supply_state: "29", hsn_sac_code: "998314", taxable_value: 1000, cgst_amount: 90, sgst_amount: 90, igst_amount: 0, itc_eligible: type === "inward", reverse_charge: false };
  return { items: [item], total: 1, totals: { taxable_value: 1000, cgst_amount: 90, sgst_amount: 90, igst_amount: 0, cess_amount: 0 } };
}
function gstrRecord(section: string) {
  return { id: 1, section, taxable_value: 1000, cgst_amount: 90, sgst_amount: 90, igst_amount: 0, cess_amount: 0, record_count: 1 };
}
function providerSettings(kind: string) {
  return { id: 1, provider_name: null, api_base_url: null, credentials_configured: false, active: false, threshold_amount: kind === "ewaybill" ? 50000 : undefined, status: "not_configured" };
}
