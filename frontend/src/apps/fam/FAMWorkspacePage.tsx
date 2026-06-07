import { cloneElement, isValidElement, useMemo, useState, type ElementType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, BadgeIndianRupee, BarChart3, BookOpen, Building2, CalendarDays, Copy, FileText, GitBranch, Landmark, Layers3, LockKeyhole, Package, Plus, RefreshCw, RotateCcw, Save, ScrollText, Settings, ShieldCheck, Sparkles, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { famApi } from "./api";
import type { FAMRecord, FAMViewKind } from "./types";

type ViewMeta = { title: string; description: string; icon: ElementType };

const viewMeta: Record<FAMViewKind, ViewMeta> = {
  dashboard: { title: "FAM Dashboard", description: "India-first accounting foundation, books status, balances, and audit activity.", icon: BarChart3 },
  settings: { title: "Company Financial Settings", description: "Country, currency, GST, PAN, TAN, books start, and India statutory identifiers.", icon: Settings },
  financialYears: { title: "Financial Years", description: "Open, close, lock, and select financial years for statutory books.", icon: CalendarDays },
  chartOfAccounts: { title: "Chart of Accounts", description: "Tree view of ledger groups and ledgers by accounting nature.", icon: GitBranch },
  ledgerGroups: { title: "Ledger Groups", description: "Maintain group hierarchy, system groups, gross-profit behavior, and active status.", icon: Layers3 },
  ledgers: { title: "Ledgers", description: "General, customer, vendor, bank, cash, tax, employee, income, expense, and asset ledgers.", icon: FileText },
  openingBalances: { title: "Opening Balances", description: "Enter debit and credit balances and post only when books are balanced.", icon: BadgeIndianRupee },
  voucherTypes: { title: "Voucher Types", description: "Journal, receipt, payment, contra, sales, purchase, debit note, credit note, opening, and adjustment numbering.", icon: ScrollText },
  vouchers: { title: "Vouchers", description: "Draft, post, cancel, reverse, and clone balanced double-entry accounting vouchers.", icon: BookOpen },
  voucherNew: { title: "New Voucher", description: "Create a balanced voucher draft with debit and credit ledger lines.", icon: Plus },
  voucherDetail: { title: "Voucher Detail", description: "Review voucher lines, immutable entries, lifecycle actions, and voucher audit trail.", icon: BookOpen },
  journal: { title: "Journal Voucher", description: "Fast journal entry screen using the double-entry voucher engine.", icon: FileText },
  dayBook: { title: "Day Book", description: "Date-wise posted and draft voucher register with debit and credit totals.", icon: CalendarDays },
  ledgerEntries: { title: "Ledger Entries", description: "Immutable ledger postings created from posted vouchers.", icon: ScrollText },
  ledgerDetailEntries: { title: "Ledger Drill-Down", description: "Opening balance, debit/credit movement, closing balance, and voucher postings by ledger.", icon: ScrollText },
  parties: { title: "Parties", description: "Customer and vendor accounting masters linked to real FAM ledgers.", icon: Users },
  customers: { title: "Customers", description: "Customer ledgers, credit limits, receivables, statements, and bill-wise tracking.", icon: Users },
  vendors: { title: "Vendors", description: "Vendor ledgers, payables, statements, payment terms, and bill-wise tracking.", icon: Users },
  partyDetail: { title: "Party Detail", description: "Master data, ledger link, GST/PAN, outstanding, statements, bills, and allocations.", icon: Users },
  ar: { title: "Accounts Receivable", description: "Customer outstanding, aging, credit terms, and bill-wise receivables.", icon: BadgeIndianRupee },
  arAging: { title: "AR Aging", description: "Not due, 0-30, 31-60, 61-90, 91-180, and >180 receivable buckets.", icon: BadgeIndianRupee },
  arOutstanding: { title: "AR Outstanding", description: "Party-wise and bill-wise receivables driven by FAM bill references.", icon: BadgeIndianRupee },
  ap: { title: "Accounts Payable", description: "Vendor outstanding, aging, payment terms, and bill-wise payables.", icon: Landmark },
  apAging: { title: "AP Aging", description: "Not due, 0-30, 31-60, 61-90, 91-180, and >180 payable buckets.", icon: Landmark },
  apOutstanding: { title: "AP Outstanding", description: "Party-wise and bill-wise payables driven by FAM bill references.", icon: Landmark },
  billReferences: { title: "Bill References", description: "Invoice, bill, debit note, credit note, opening, and advance references.", icon: FileText },
  billAllocations: { title: "Bill Allocations", description: "Receipt/payment/credit/debit note/advance/write-off allocation foundation.", icon: ScrollText },
  srmIntegration: { title: "SRM Accounting Integration", description: "Post SRM invoices, receipts, allocations, collections, and reversals into FAM statutory books.", icon: Copy },
  postingJobs: { title: "Posting Jobs", description: "SRM to FAM posting queue, status, linked vouchers, retry state, and errors.", icon: RotateCcw },
  postingJobDetail: { title: "Posting Job Detail", description: "Source SRM record, FAM mappings, retry state, voucher link, and accounting status.", icon: RotateCcw },
  postingRules: { title: "Posting Rules", description: "Configure source transaction ledger rules for SRM accounting postings.", icon: Settings },
  banking: { title: "Banking", description: "Ledger-driven bank accounts, statements, matching, reconciliation, bank book, cash book, charges, and contra.", icon: Landmark },
  bankAccounts: { title: "Bank Accounts", description: "Bank masters linked to FAM bank ledgers with masked account numbers and IFSC.", icon: Landmark },
  paymentModes: { title: "Payment Modes", description: "Cash, cheque, NEFT, RTGS, UPI, card, wallet, and other payment modes linked to ledgers.", icon: BadgeIndianRupee },
  bankStatements: { title: "Bank Statements", description: "Manual CSV/imported bank statements with duplicate prevention and no automatic posting.", icon: FileText },
  bankStatementDetail: { title: "Bank Statement Detail", description: "Review statement lines, auto-match suggestions, manual matching, ignored lines, and reconciliation readiness.", icon: FileText },
  bankReconciliation: { title: "Bank Reconciliation", description: "Book balance, statement balance, unreconciled items, sessions, and reconciliation status.", icon: ShieldCheck },
  bankBook: { title: "Bank Book", description: "Ledger-driven bank book with opening, debit, credit, closing, and voucher drill-down rows.", icon: BookOpen },
  cashBook: { title: "Cash Book", description: "Ledger-driven cash book and cash register balances.", icon: BookOpen },
  contra: { title: "Contra", description: "Post bank-to-cash, cash-to-bank, or bank-to-bank transfers through FAM contra vouchers.", icon: RotateCcw },
  bankCharges: { title: "Bank Charges", description: "Post bank fees as payment vouchers against bank and expense ledgers.", icon: BadgeIndianRupee },
  gst: { title: "India GST", description: "GST registrations, rates, HSN/SAC, registers, returns, e-invoice, e-way bill, and reconciliation readiness.", icon: ShieldCheck },
  gstSettings: { title: "GST Settings", description: "GST compliance settings are configurable; portal providers remain clearly not configured until credentials exist.", icon: Settings },
  gstRegistrations: { title: "GST Registrations", description: "Company GSTIN, state, legal name, trade name, registration type, and effective date.", icon: Landmark },
  gstRates: { title: "GST Rates", description: "Versioned CGST, SGST, IGST, and cess rates with effective dates.", icon: BadgeIndianRupee },
  gstHsnSac: { title: "HSN/SAC Master", description: "India HSN/SAC codes linked to configurable GST rates.", icon: FileText },
  gstSalesRegister: { title: "GST Sales Register", description: "Outward GST transaction lines reconciled to FAM voucher/accounting data.", icon: ScrollText },
  gstPurchaseRegister: { title: "GST Purchase Register", description: "Inward, import, and reverse-charge GST transaction lines with ITC flags.", icon: ScrollText },
  gstr1: { title: "GSTR-1 Framework", description: "Prepare working GSTR-1 records from GST sales register data; no fake portal filing.", icon: FileText },
  gstr3b: { title: "GSTR-3B Framework", description: "Prepare working GSTR-3B summary from outward tax and eligible ITC data.", icon: FileText },
  gstReconciliation: { title: "GST Reconciliation", description: "Foundation for books-to-return and portal reconciliation exceptions.", icon: ShieldCheck },
  einvoice: { title: "E-Invoice Readiness", description: "Provider settings and IRN job placeholders; actions show not configured without credentials.", icon: FileText },
  ewaybill: { title: "E-Way Bill Readiness", description: "Threshold, transporter, vehicle, and job placeholders; no fake EWB generation.", icon: FileText },
  purchases: { title: "Purchases", description: "Vendor bills, expense vouchers, TDS deductions, purchase register, and AP readiness for India.", icon: Landmark },
  purchaseBills: { title: "Vendor Purchase Bills", description: "Create, review, post, cancel, and track vendor bills with GST input and TDS deductions.", icon: FileText },
  purchaseBillNew: { title: "New Purchase Bill", description: "Capture vendor bill lines, GST input tax, TDS section, due date, and payable amount.", icon: Plus },
  purchaseBillDetail: { title: "Purchase Bill Detail", description: "Review bill totals, accounting voucher link, TDS transactions, audit trail, and posting actions.", icon: FileText },
  expenses: { title: "Expenses", description: "Employee and operational expense claims posted through the FAM voucher engine.", icon: BadgeIndianRupee },
  expenseNew: { title: "New Expense Claim", description: "Capture expense lines and post approved expenses into statutory books.", icon: Plus },
  tds: { title: "TDS", description: "Configurable India TDS sections, rates, deductions, payable position, and transaction register.", icon: ShieldCheck },
  tdsSections: { title: "TDS Sections", description: "Maintain section codes, default rates, thresholds, effective dates, and active flags.", icon: Settings },
  tdsTransactions: { title: "TDS Transactions", description: "Deducted, paid, and reversed TDS entries linked to vouchers and vendors.", icon: ScrollText },
  tdsPayable: { title: "TDS Payable", description: "TDS payable by section and vendor without pretending return filing is integrated.", icon: BadgeIndianRupee },
  purchaseRegister: { title: "Purchase Register", description: "Posted and draft vendor bills with GST input and TDS tracked separately.", icon: BookOpen },
  expenseRegister: { title: "Expense Register", description: "Expense claims and posted vouchers by employee, claim date, and status.", icon: BookOpen },
  vendorPayments: { title: "Vendor Payments", description: "Prepare and post vendor payment runs against AP bills through bank or cash ledgers.", icon: Landmark },
  payablesDashboard: { title: "Payables Dashboard", description: "Vendor outstanding, AP aging buckets, draft bills, posted bills, and paid bills.", icon: BarChart3 },
  inventory: { title: "Inventory", description: "Merged AI Inventory Management Software capabilities inside FAM statutory books.", icon: Package },
  inventoryDashboard: { title: "Inventory Dashboard", description: "Stock value, low-stock alerts, warehouses, and recent stock movements.", icon: Package },
  inventoryItems: { title: "Stock Items", description: "GST-ready item master with HSN, units, stock groups, reorder levels, rates, and valuation ledgers.", icon: Package },
  inventoryItemDetail: { title: "Stock Item Detail", description: "Item master, stock quantity, valuation, and latest item ledger entries.", icon: Package },
  inventoryCategories: { title: "Inventory Categories", description: "Category view mapped to FAM stock groups from the source inventory app.", icon: Layers3 },
  inventoryStockGroups: { title: "Stock Groups", description: "Hierarchical inventory groups for item classification.", icon: Layers3 },
  inventoryUnits: { title: "Units of Measure", description: "Units, symbols, and decimal settings for stock items.", icon: FileText },
  inventoryWarehouses: { title: "Warehouses", description: "Warehouse masters linked to FAM branches and stock movements.", icon: Building2 },
  inventoryStockIn: { title: "Stock In", description: "Post inward stock movements using the FAM inventory ledger.", icon: Plus },
  inventoryStockOut: { title: "Stock Out", description: "Post outward stock movements with stock availability validation.", icon: RotateCcw },
  inventoryStockTransfers: { title: "Stock Transfers", description: "Move stock between warehouses with idempotent posted movement records.", icon: RotateCcw },
  inventoryStockAdjustments: { title: "Stock Adjustments", description: "Post stock gains/losses and optional accounting vouchers.", icon: ShieldCheck },
  inventoryPurchaseReceipts: { title: "Purchase Receipts", description: "Receive purchased items into inventory without duplicating purchase bill accounting.", icon: Landmark },
  inventoryDeliveryNotes: { title: "Delivery Notes", description: "Issue stock for delivery and keep inventory movement evidence.", icon: FileText },
  inventoryStockSummary: { title: "Stock Summary", description: "Item-wise quantity, average cost, stock value, and low-stock flags.", icon: BookOpen },
  inventoryItemLedger: { title: "Item Ledger", description: "Movement lines, balances, rates, and values for a stock item.", icon: ScrollText },
  inventoryValuation: { title: "Inventory Valuation", description: "Weighted-average valuation layers and total inventory value.", icon: BarChart3 },
  inventoryReorderAlerts: { title: "Reorder Alerts", description: "Items at or below reorder/minimum stock thresholds.", icon: AlertTriangle },
  inventoryReports: { title: "Inventory Reports", description: "Stock summary, valuation, reorder alerts, and generated report audit evidence.", icon: BarChart3 },
  inventoryAI: { title: "Inventory AI", description: "Audited AI insight requests with honest provider readiness status.", icon: Sparkles },
  costCenters: { title: "Cost Centers", description: "Track accounting dimensions by department, project, branch, or operating unit.", icon: Building2 },
  branches: { title: "Branches", description: "GST/location-aware branches for India-first books setup.", icon: Landmark },
  audit: { title: "Accounting Audit", description: "Trace FAM setup, chart, ledger, opening balance, and settings changes.", icon: ScrollText },
};

function money(value: unknown) {
  return Number(value || 0).toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
}

function text(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString("en-IN");
  if (typeof value === "object") return "Linked";
  return String(value).replace(/_/g, " ");
}

function listItems(data: unknown): FAMRecord[] {
  if (data && typeof data === "object" && "items" in data) return ((data as { items?: FAMRecord[] }).items || []);
  return [];
}

function statusTone(value: unknown) {
  const status = String(value || "").toLowerCase();
  if (["open", "active", "posted"].includes(status)) return "default";
  if (["locked", "closed", "inactive"].includes(status)) return "secondary";
  return "outline";
}

function PageHeader({ meta, isFetching, onRefresh }: { meta: ViewMeta; isFetching?: boolean; onRefresh?: () => void }) {
  const Icon = meta.icon;
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{meta.title}</h1>
          <p className="text-sm text-muted-foreground">{meta.description}</p>
        </div>
      </div>
      {onRefresh ? <Button variant="outline" onClick={onRefresh} disabled={isFetching}><RefreshCw className="h-4 w-4" />Refresh</Button> : null}
    </div>
  );
}

function State({ label, isLoading, isError }: { label: string; isLoading?: boolean; isError?: boolean }) {
  if (isLoading) return <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">Loading {label}...</div>;
  if (isError) return <div className="rounded-lg border border-destructive/40 p-6 text-sm text-destructive"><AlertTriangle className="mr-2 inline h-4 w-4" />Unable to load {label}.</div>;
  return null;
}

function DashboardView() {
  const query = useQuery({ queryKey: ["fam", "dashboard"], queryFn: famApi.dashboard });
  const data = (query.data || {}) as FAMRecord;
  const kpis: Array<[string, React.ReactNode]> = [
    ["Current FY", text((data.currentFinancialYear as FAMRecord | undefined)?.name)],
    ["Total assets", money(data.totalAssets)],
    ["Total liabilities", money(data.totalLiabilities)],
    ["Total income", money(data.totalIncome)],
    ["Total expenses", money(data.totalExpenses)],
    ["Cash and bank", money(data.cashAndBankBalance)],
    ["Receivables", text(data.receivablesPlaceholder)],
    ["Payables", text(data.payablesPlaceholder)],
  ];
  return (
    <div className="space-y-5">
      <State label="FAM dashboard" isLoading={query.isLoading} isError={query.isError} />
      <div className="grid gap-3 md:grid-cols-4">
        {kpis.map(([label, value]) => (
          <Card key={label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></CardContent></Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader><CardTitle className="text-base">Recent accounting activity</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {listItems({ items: data.recentAccountingActivity as FAMRecord[] || [] }).map((item) => <AuditRow key={String(item.id)} item={item} />)}
            {!(data.recentAccountingActivity as FAMRecord[] | undefined)?.length ? <p className="text-sm text-muted-foreground">No accounting activity yet.</p> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Books status</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Badge variant={statusTone(data.booksStatus)}>{text(data.booksStatus)}</Badge>
            <p className="text-muted-foreground">GST compliance placeholder is visible but not connected to fake filings.</p>
            <p>{text(data.gstCompliancePlaceholder)}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SettingsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "settings"], queryFn: famApi.settings });
  const settings = (query.data || {}) as FAMRecord;
  const [draft, setDraft] = useState<FAMRecord>({});
  const effective = { ...settings, ...draft };
  const mutation = useMutation({
    mutationFn: () => famApi.updateSettings(effective),
    onSuccess: () => { toast({ title: "FAM settings saved" }); setDraft({}); queryClient.invalidateQueries({ queryKey: ["fam"] }); },
  });
  const patch = (key: string, value: unknown) => setDraft((current) => ({ ...current, [key]: value }));
  return (
    <Card>
      <CardContent className="grid gap-4 p-5 md:grid-cols-3">
        <State label="settings" isLoading={query.isLoading} isError={query.isError} />
        {[
          ["legal_name", "Legal Name"], ["trade_name", "Trade Name"], ["gstin", "GSTIN"], ["pan", "PAN"], ["tan", "TAN"], ["cin", "CIN"], ["state_code", "State Code"], ["base_currency", "Base Currency"], ["country_code", "Country"]
        ].map(([key, label]) => <Field key={key} label={label}><Input value={String(effective[key] || "")} onChange={(event) => patch(key, event.target.value)} /></Field>)}
        <Field label="Financial Year Start Month"><Input type="number" min={1} max={12} value={String(effective.financial_year_start_month || 4)} onChange={(event) => patch("financial_year_start_month", Number(event.target.value))} /></Field>
        <Field label="Books Start Date"><Input type="date" value={String(effective.books_start_date || "")} onChange={(event) => patch("books_start_date", event.target.value)} /></Field>
        <Field label="Decimal Places"><Input type="number" value={String(effective.decimal_places || 2)} onChange={(event) => patch("decimal_places", Number(event.target.value))} /></Field>
        <div className="md:col-span-3">
          <Field label="Registered Address"><textarea className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={String(effective.registered_address || "")} onChange={(event) => patch("registered_address", event.target.value)} /></Field>
        </div>
        <div className="md:col-span-3 flex justify-end"><Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>Save settings</Button></div>
      </CardContent>
    </Card>
  );
}

function DataTable({ rows, columns }: { rows: FAMRecord[]; columns: string[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full min-w-[780px] text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground"><tr>{columns.map((column) => <th key={column} className="px-3 py-2">{column.replace(/_/g, " ")}</th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr key={String(row.id)} className="border-t">{columns.map((column) => <td key={column} className="px-3 py-2">{column.includes("status") || column === "nature" ? <Badge variant={statusTone(row[column])}>{text(row[column])}</Badge> : text(row[column])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function ChartView() {
  const query = useQuery({ queryKey: ["fam", "chart"], queryFn: famApi.chartOfAccounts });
  const data = (query.data || {}) as { groups?: FAMRecord[]; ledgers?: FAMRecord[] };
  const ledgersByGroup = useMemo(() => new Map((data.groups || []).map((group) => [Number(group.id), (data.ledgers || []).filter((ledger) => Number(ledger.ledger_group_id) === Number(group.id))])), [data.groups, data.ledgers]);
  return (
    <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
      <Card><CardHeader><CardTitle className="text-base">Ledger group tree</CardTitle></CardHeader><CardContent className="space-y-2">
        <State label="chart of accounts" isLoading={query.isLoading} isError={query.isError} />
        {(data.groups || []).map((group) => <div key={String(group.id)} className="rounded-md border p-3"><div className="flex items-center justify-between gap-2"><span className="font-medium">{text(group.group_name)}</span><Badge variant="outline">{text(group.nature)}</Badge></div><p className="text-xs text-muted-foreground">{ledgersByGroup.get(Number(group.id))?.length || 0} ledgers {group.system_group ? "System group" : ""}</p></div>)}
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Ledgers</CardTitle></CardHeader><CardContent><DataTable rows={data.ledgers || []} columns={["ledger_code", "ledger_name", "nature", "ledger_type", "active"]} /></CardContent></Card>
    </div>
  );
}

function ListCreateView({ kind }: { kind: FAMViewKind }) {
  const queryClient = useQueryClient();
  const config = getListConfig(kind);
  const query = useQuery({ queryKey: ["fam", kind], queryFn: config.query });
  const rows = listItems(query.data);
  const [draft, setDraft] = useState<FAMRecord>(config.initial);
  const mutation = useMutation({
    mutationFn: () => config.create(draft),
    onSuccess: () => { toast({ title: `${config.label} created` }); setDraft(config.initial); queryClient.invalidateQueries({ queryKey: ["fam"] }); },
  });
  return (
    <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
      <Card><CardHeader><CardTitle className="text-base">Create {config.label}</CardTitle></CardHeader><CardContent className="space-y-3">
        {config.fields.map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}
        <Button className="w-full" onClick={() => mutation.mutate()} disabled={mutation.isPending}><Plus className="h-4 w-4" />Create</Button>
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">{config.label} list</CardTitle></CardHeader><CardContent><State label={config.label} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={config.columns} /></CardContent></Card>
    </div>
  );
}

function OpeningBalancesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "openingBalances"], queryFn: famApi.openingBalances });
  const data = (query.data || {}) as FAMRecord;
  const rows = listItems(data);
  const [draft, setDraft] = useState<FAMRecord>({ financial_year_id: 1, ledger_id: 1, debit_amount: 0, credit_amount: 0, narration: "" });
  const createMutation = useMutation({ mutationFn: () => famApi.createOpeningBalance(draft), onSuccess: () => { toast({ title: "Opening balance saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const postMutation = useMutation({ mutationFn: famApi.postOpeningBalances, onSuccess: () => { toast({ title: "Opening balances posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const difference = Number(data.difference || 0);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Debit</p><p className="text-lg font-semibold">{money(data.debitTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Credit</p><p className="text-lg font-semibold">{money(data.creditTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Difference</p><p className={difference ? "text-lg font-semibold text-destructive" : "text-lg font-semibold text-emerald-700"}>{money(difference)}</p></CardContent></Card>
        <Button className="h-full min-h-20" onClick={() => postMutation.mutate()} disabled={Boolean(difference) || postMutation.isPending}><LockKeyhole className="h-4 w-4" />Post balanced opening</Button>
      </div>
      <ListCreateInline fields={["financial_year_id", "ledger_id", "debit_amount", "credit_amount", "narration"]} draft={draft} setDraft={setDraft} onCreate={() => createMutation.mutate()} />
      <Card><CardHeader><CardTitle className="text-base">Ledger-wise opening balances</CardTitle></CardHeader><CardContent><State label="opening balances" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["financial_year_id", "ledger_id", "debit_amount", "credit_amount", "posted", "narration"]} /></CardContent></Card>
    </div>
  );
}

const defaultVoucherLine = { ledger_id: 1, debit_amount: 0, credit_amount: 0, narration: "" };

function voucherDraft(kind: FAMViewKind): FAMRecord {
  const isJournal = kind === "journal";
  return {
    voucher_type_id: 1,
    voucher_date: "2026-06-06",
    reference_number: "",
    narration: isJournal ? "Journal adjustment" : "",
    source_module: "fam",
    lines: [
      { ...defaultVoucherLine, debit_amount: 1000, narration: "Debit line" },
      { ...defaultVoucherLine, ledger_id: 2, credit_amount: 1000, narration: "Credit line" },
    ],
  };
}

function VoucherEntryView({ mode }: { mode: "new" | "journal" | "detail" }) {
  const params = useParams();
  const queryClient = useQueryClient();
  const voucherQuery = useQuery({ queryKey: ["fam", "voucher", params.id], queryFn: () => famApi.getVoucher(params.id || ""), enabled: mode === "detail" && Boolean(params.id) });
  const typesQuery = useQuery({ queryKey: ["fam", "voucherTypes"], queryFn: famApi.voucherTypes });
  const ledgersQuery = useQuery({ queryKey: ["fam", "ledgers"], queryFn: famApi.ledgers });
  const [draft, setDraft] = useState<FAMRecord>(voucherDraft(mode === "journal" ? "journal" : "voucherNew"));
  const effective = (mode === "detail" && voucherQuery.data ? voucherQuery.data : draft) as FAMRecord;
  const lines = ((effective.lines as FAMRecord[] | undefined) || []) as FAMRecord[];
  const debitTotal = lines.reduce((sum, line) => sum + Number(line.debit_amount || 0), 0);
  const creditTotal = lines.reduce((sum, line) => sum + Number(line.credit_amount || 0), 0);
  const difference = debitTotal - creditTotal;
  const voucherId = String(effective.id || params.id || "");
  const saveMutation = useMutation({
    mutationFn: () => (mode === "detail" && voucherId ? famApi.updateVoucher(voucherId, { ...effective, total_debit: debitTotal, total_credit: creditTotal }) : famApi.createVoucher({ ...effective, total_debit: debitTotal, total_credit: creditTotal })),
    onSuccess: () => { toast({ title: "Voucher draft saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); },
  });
  const postMutation = useMutation({ mutationFn: () => famApi.postVoucher(voucherId), onSuccess: () => { toast({ title: "Voucher posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const cancelMutation = useMutation({ mutationFn: () => famApi.cancelVoucher(voucherId), onSuccess: () => { toast({ title: "Voucher cancelled" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const reverseMutation = useMutation({ mutationFn: () => famApi.reverseVoucher(voucherId), onSuccess: () => { toast({ title: "Reversal voucher created" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const cloneMutation = useMutation({ mutationFn: () => famApi.cloneVoucher(voucherId), onSuccess: () => { toast({ title: "Voucher cloned" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const patch = (key: string, value: unknown) => setDraft((current) => ({ ...effective, ...current, [key]: value }));
  const patchLine = (index: number, key: string, value: unknown) => {
    const next = lines.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: numericFields.has(key) ? Number(value) : value } : line);
    patch("lines", next);
  };
  const addLine = () => patch("lines", [...lines, { ...defaultVoucherLine }]);
  const canEdit = String(effective.status || "draft") === "draft";
  return (
    <div className="space-y-4">
      <State label="voucher" isLoading={voucherQuery.isLoading || typesQuery.isLoading || ledgersQuery.isLoading} isError={voucherQuery.isError || typesQuery.isError || ledgersQuery.isError} />
      <div className="grid gap-3 md:grid-cols-4">
        <Field label="Voucher Type">
          <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={String(effective.voucher_type_id || 1)} onChange={(event) => patch("voucher_type_id", Number(event.target.value))} disabled={!canEdit}>
            {listItems(typesQuery.data).map((type) => <option key={String(type.id)} value={String(type.id)}>{text(type.voucher_type_name)}</option>)}
          </select>
        </Field>
        <Field label="Voucher Date"><Input type="date" value={String(effective.voucher_date || "")} onChange={(event) => patch("voucher_date", event.target.value)} disabled={!canEdit} /></Field>
        <Field label="Reference Number"><Input value={String(effective.reference_number || "")} onChange={(event) => patch("reference_number", event.target.value)} disabled={!canEdit} /></Field>
        <Field label="Narration"><Input value={String(effective.narration || "")} onChange={(event) => patch("narration", event.target.value)} disabled={!canEdit} /></Field>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Debit / Credit lines</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground"><tr><th className="px-3 py-2">Ledger</th><th className="px-3 py-2">Debit</th><th className="px-3 py-2">Credit</th><th className="px-3 py-2">Cost Center</th><th className="px-3 py-2">Narration</th></tr></thead>
              <tbody>
                {lines.map((line, index) => (
                  <tr key={index} className="border-t">
                    <td className="px-3 py-2"><select className="h-9 w-full rounded-md border bg-background px-2" value={String(line.ledger_id || 1)} onChange={(event) => patchLine(index, "ledger_id", event.target.value)} disabled={!canEdit}>{listItems(ledgersQuery.data).map((ledger) => <option key={String(ledger.id)} value={String(ledger.id)}>{text(ledger.ledger_name)}</option>)}</select></td>
                    <td className="px-3 py-2"><Input type="number" value={String(line.debit_amount || 0)} onChange={(event) => patchLine(index, "debit_amount", event.target.value)} disabled={!canEdit} /></td>
                    <td className="px-3 py-2"><Input type="number" value={String(line.credit_amount || 0)} onChange={(event) => patchLine(index, "credit_amount", event.target.value)} disabled={!canEdit} /></td>
                    <td className="px-3 py-2"><Input value={String(line.cost_center_id || "")} onChange={(event) => patchLine(index, "cost_center_id", event.target.value)} disabled={!canEdit} /></td>
                    <td className="px-3 py-2"><Input value={String(line.narration || "")} onChange={(event) => patchLine(index, "narration", event.target.value)} disabled={!canEdit} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {canEdit ? <Button variant="outline" onClick={addLine}><Plus className="h-4 w-4" />Add line</Button> : null}
        </CardContent>
      </Card>
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total debit</p><p className="text-lg font-semibold">{money(debitTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total credit</p><p className="text-lg font-semibold">{money(creditTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Difference</p><p className={difference ? "text-lg font-semibold text-destructive" : "text-lg font-semibold text-emerald-700"}>{money(difference)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Status</p><Badge variant={statusTone(effective.status || "draft")}>{text(effective.status || "draft")}</Badge></CardContent></Card>
      </div>
      <div className="flex flex-wrap gap-2">
        {canEdit ? <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}><Save className="h-4 w-4" />Save draft</Button> : null}
        {voucherId && canEdit ? <Button onClick={() => postMutation.mutate()} disabled={Boolean(difference) || postMutation.isPending}><LockKeyhole className="h-4 w-4" />Post voucher</Button> : null}
        {voucherId ? <Button variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>Cancel voucher</Button> : null}
        {voucherId ? <Button variant="outline" onClick={() => reverseMutation.mutate()} disabled={reverseMutation.isPending}><RotateCcw className="h-4 w-4" />Reverse voucher</Button> : null}
        {voucherId ? <Button variant="outline" onClick={() => cloneMutation.mutate()} disabled={cloneMutation.isPending}><Copy className="h-4 w-4" />Clone voucher</Button> : null}
      </div>
    </div>
  );
}

function VouchersView() {
  const query = useQuery({ queryKey: ["fam", "vouchers"], queryFn: famApi.vouchers });
  const rows = listItems(query.data);
  return <Card><CardHeader><CardTitle className="text-base">Voucher register</CardTitle></CardHeader><CardContent><div className="mb-3"><Button asChild><Link to="/fam/vouchers/new"><Plus className="h-4 w-4" />New voucher</Link></Button></div><State label="vouchers" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["voucher_number", "voucher_date", "status", "total_debit", "total_credit", "source_module"]} /></CardContent></Card>;
}

function DayBookView() {
  const query = useQuery({ queryKey: ["fam", "dayBook"], queryFn: famApi.dayBook });
  const data = (query.data || {}) as FAMRecord;
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-3"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Vouchers</p><p className="text-lg font-semibold">{text(data.total)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Debit total</p><p className="text-lg font-semibold">{money(data.debitTotal)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Credit total</p><p className="text-lg font-semibold">{money(data.creditTotal)}</p></CardContent></Card></div><Card><CardContent className="p-5"><State label="day book" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(data)} columns={["voucher_date", "voucher_number", "status", "reference_number", "total_debit", "total_credit"]} /></CardContent></Card></div>;
}

function LedgerEntriesView({ detail }: { detail?: boolean }) {
  const params = useParams();
  const query = useQuery({ queryKey: ["fam", "ledgerEntries", detail ? params.id : "all"], queryFn: () => detail && params.id ? famApi.ledgerEntriesForLedger(params.id) : famApi.ledgerEntries() });
  const data = (query.data || {}) as FAMRecord;
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Opening</p><p className="text-lg font-semibold">{money(data.openingBalance)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Debit movement</p><p className="text-lg font-semibold">{money(data.debitMovement || data.debitTotal)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Credit movement</p><p className="text-lg font-semibold">{money(data.creditMovement || data.creditTotal)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Closing</p><p className="text-lg font-semibold">{money(data.closingBalance)}</p></CardContent></Card></div><Card><CardContent className="p-5"><State label="ledger entries" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(data)} columns={["voucher_date", "voucher_number", "ledger_id", "debit_amount", "credit_amount", "running_balance", "source_module"]} /></CardContent></Card></div>;
}

function PartiesView({ partyType }: { partyType?: "customer" | "vendor" }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "parties", partyType || "all"], queryFn: () => famApi.parties(partyType) });
  const rows = listItems(query.data);
  const [draft, setDraft] = useState<FAMRecord>({ party_type: partyType || "customer", party_code: "", legal_name: "", registration_type: "regular", state_code: "29", payment_terms_days: 30, credit_limit: 0, create_ledger: true });
  const mutation = useMutation({ mutationFn: () => famApi.createParty(draft), onSuccess: () => { toast({ title: "Party saved" }); setDraft({ ...draft, party_code: "", legal_name: "" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const title = partyType === "customer" ? "customer" : partyType === "vendor" ? "vendor" : "party";
  return (
    <div className="grid gap-4 lg:grid-cols-[24rem_1fr]">
      <Card><CardHeader><CardTitle className="text-base">Create {title}</CardTitle></CardHeader><CardContent className="space-y-3">
        {["party_type", "party_code", "legal_name", "gstin", "pan", "state_code", "payment_terms_days", "credit_limit"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}
        <Button className="w-full" onClick={() => mutation.mutate()} disabled={mutation.isPending}><Plus className="h-4 w-4" />Create with ledger</Button>
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">{title} masters</CardTitle></CardHeader><CardContent><State label="parties" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["party_code", "legal_name", "party_type", "ledger_id", "payment_terms_days", "credit_limit", "active"]} /></CardContent></Card>
    </div>
  );
}

function PartyDetailView() {
  const params = useParams();
  const id = params.id || "1";
  const party = useQuery({ queryKey: ["fam", "party", id], queryFn: () => famApi.getParty(id) });
  const outstanding = useQuery({ queryKey: ["fam", "partyOutstanding", id], queryFn: () => famApi.partyOutstanding(id) });
  const statement = useQuery({ queryKey: ["fam", "partyStatement", id], queryFn: () => famApi.partyStatement(id) });
  const data = (party.data || {}) as FAMRecord;
  const statementData = (statement.data || {}) as FAMRecord;
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Party</p><p className="text-lg font-semibold">{text(data.legal_name)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Ledger</p><p className="text-lg font-semibold">{text(data.ledger_id)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Credit limit</p><p className="text-lg font-semibold">{money(data.credit_limit)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Outstanding</p><p className="text-lg font-semibold">{money((outstanding.data as FAMRecord | undefined)?.outstanding)}</p></CardContent></Card></div><Card><CardHeader><CardTitle className="text-base">Statement and bill references</CardTitle></CardHeader><CardContent><State label="party detail" isLoading={party.isLoading || statement.isLoading} isError={party.isError || statement.isError} /><DataTable rows={(statementData.billReferences as FAMRecord[] | undefined) || []} columns={["bill_number", "bill_date", "due_date", "bill_type", "original_amount", "outstanding_amount", "status"]} /></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Allocations</CardTitle></CardHeader><CardContent><DataTable rows={(statementData.allocations as FAMRecord[] | undefined) || []} columns={["allocation_date", "allocation_type", "allocated_amount", "from_bill_reference_id", "to_bill_reference_id"]} /></CardContent></Card></div>;
}

function AgingView({ kind }: { kind: "ar" | "ap" }) {
  const query = useQuery({ queryKey: ["fam", kind, "aging"], queryFn: kind === "ar" ? famApi.arAging : famApi.apAging });
  const data = (query.data || {}) as FAMRecord;
  const buckets = data.buckets as Record<string, number> | undefined;
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-6">{["Not due", "0-30", "31-60", "61-90", "91-180", ">180"].map((bucket) => <Card key={bucket}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{bucket}</p><p className="text-lg font-semibold">{money(buckets?.[bucket])}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">{kind.toUpperCase()} aging details</CardTitle></CardHeader><CardContent><State label={`${kind} aging`} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.items as FAMRecord[] | undefined) || []} columns={["bill_number", "party_id", "due_date", "aging_bucket", "overdue_days", "outstanding_amount", "status"]} /></CardContent></Card></div>;
}

function OutstandingView({ kind }: { kind: "ar" | "ap" }) {
  const query = useQuery({ queryKey: ["fam", kind, "outstanding"], queryFn: kind === "ar" ? famApi.arOutstanding : famApi.apOutstanding });
  const data = (query.data || {}) as FAMRecord;
  return <div className="space-y-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">{kind.toUpperCase()} total outstanding</p><p className="text-2xl font-semibold">{money(data.totalOutstanding)}</p></CardContent></Card><Card><CardContent className="p-5"><State label={`${kind} outstanding`} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(data)} columns={["bill_number", "party_id", "bill_date", "due_date", "bill_type", "outstanding_amount", "status"]} /></CardContent></Card><p className="text-xs text-muted-foreground">Export placeholder: backend export endpoint is not implemented in this phase.</p></div>;
}

function BillReferencesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "billReferences"], queryFn: famApi.billReferences });
  const [draft, setDraft] = useState<FAMRecord>({ party_id: 1, bill_number: "", bill_date: "2026-06-06", bill_type: "invoice", original_amount: 1000 });
  const mutation = useMutation({ mutationFn: () => famApi.createBillReference(draft), onSuccess: () => { toast({ title: "Bill reference saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create bill reference</CardTitle></CardHeader><CardContent className="space-y-3">{["party_id", "bill_number", "bill_date", "bill_type", "original_amount"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Create bill</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Bill-wise tracking</CardTitle></CardHeader><CardContent><State label="bill references" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["bill_number", "party_id", "bill_date", "due_date", "bill_type", "original_amount", "outstanding_amount", "status"]} /></CardContent></Card></div>;
}

function BillAllocationsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "billAllocations"], queryFn: famApi.billAllocations });
  const [draft, setDraft] = useState<FAMRecord>({ allocation_date: "2026-06-06", party_id: 1, from_bill_reference_id: 1, to_bill_reference_id: 1, allocated_amount: 100, allocation_type: "receipt" });
  const mutation = useMutation({ mutationFn: () => famApi.createBillAllocation(draft), onSuccess: () => { toast({ title: "Bill allocation saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Allocate bill</CardTitle></CardHeader><CardContent className="space-y-3">{["allocation_date", "party_id", "from_bill_reference_id", "to_bill_reference_id", "allocated_amount", "allocation_type"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Allocate</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Allocations</CardTitle></CardHeader><CardContent><State label="bill allocations" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["allocation_date", "party_id", "allocation_type", "allocated_amount", "from_bill_reference_id", "to_bill_reference_id"]} /></CardContent></Card></div>;
}

function SRMIntegrationView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "srmIntegration"], queryFn: famApi.srmIntegrationStatus });
  const data = (query.data || {}) as FAMRecord;
  const [draft, setDraft] = useState<FAMRecord>({ invoice_id: 1, receipt_id: 1, allocation_id: 1, reverse_type: "invoice", reverse_id: 1 });
  const action = useMutation({ mutationFn: (run: () => Promise<FAMRecord>) => run(), onSuccess: () => { toast({ title: "Accounting integration updated" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const kpis: Array<[string, unknown]> = [["Pending postings", data.pending_postings], ["Failed postings", data.failed_postings], ["Posted today", data.posted_today], ["Unmapped customers", data.unmapped_customers], ["Duplicate prevention", data.duplicate_prevention_status]];
  return (
    <div className="space-y-4">
      <State label="SRM accounting integration" isLoading={query.isLoading} isError={query.isError} />
      <div className="grid gap-3 md:grid-cols-5">{kpis.map(([label, value]) => <Card key={label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-lg font-semibold">{text(value)}</p></CardContent></Card>)}</div>
      <Card><CardHeader><CardTitle className="text-base">Manual posting controls</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-4">
        <Field label="invoice id"><Input value={String(draft.invoice_id || "")} onChange={(event) => setDraft((current) => ({ ...current, invoice_id: Number(event.target.value) }))} /></Field>
        <Field label="receipt id"><Input value={String(draft.receipt_id || "")} onChange={(event) => setDraft((current) => ({ ...current, receipt_id: Number(event.target.value) }))} /></Field>
        <Field label="allocation id"><Input value={String(draft.allocation_id || "")} onChange={(event) => setDraft((current) => ({ ...current, allocation_id: Number(event.target.value) }))} /></Field>
        <Field label="reverse source id"><Input value={String(draft.reverse_id || "")} onChange={(event) => setDraft((current) => ({ ...current, reverse_id: Number(event.target.value) }))} /></Field>
        <Button onClick={() => action.mutate(() => famApi.postSrmInvoice(String(draft.invoice_id || 1)))}>Post SRM invoice</Button>
        <Button variant="outline" onClick={() => action.mutate(() => famApi.postSrmReceipt(String(draft.receipt_id || 1)))}>Post SRM receipt</Button>
        <Button variant="outline" onClick={() => action.mutate(() => famApi.postSrmAllocation(String(draft.allocation_id || 1)))}>Post allocation</Button>
        <Button variant="outline" onClick={() => action.mutate(() => famApi.reverseSrmPosting(String(draft.reverse_type || "invoice"), String(draft.reverse_id || 1)))}>Reverse posting</Button>
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Recent posting jobs</CardTitle></CardHeader><CardContent><DataTable rows={(data.recent_jobs as FAMRecord[] | undefined) || []} columns={["id", "source_record_type", "source_record_id", "posting_type", "status", "voucher_id", "retry_count"]} /></CardContent></Card>
    </div>
  );
}

function PostingJobsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "postingJobs"], queryFn: famApi.postingJobs });
  const retry = useMutation({ mutationFn: (id: number | string) => famApi.retryPostingJob(id), onSuccess: () => { toast({ title: "Posting job retried" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <Card><CardHeader><CardTitle className="text-base">SRM posting queue</CardTitle></CardHeader><CardContent className="space-y-3"><State label="posting jobs" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["id", "source_module", "source_record_type", "source_record_id", "posting_type", "status", "voucher_id", "retry_count", "error_message"]} />{listItems(query.data).slice(0, 3).map((item) => <div key={String(item.id)} className="flex items-center justify-between rounded-md border p-3 text-sm"><Link className="text-primary underline-offset-4 hover:underline" to={`/fam/posting-jobs/${item.id}`}>Posting job #{text(item.id)}</Link><Button size="sm" variant="outline" onClick={() => retry.mutate(String(item.id))}>Retry</Button></div>)}</CardContent></Card>;
}

function PostingJobDetailView() {
  const params = useParams();
  const id = params.id || "1";
  const query = useQuery({ queryKey: ["fam", "postingJob", id], queryFn: () => famApi.postingJob(id) });
  const data = (query.data || {}) as FAMRecord;
  const status = (data.accountingStatus || {}) as FAMRecord;
  return <div className="space-y-4"><State label="posting job detail" isLoading={query.isLoading} isError={query.isError} /><div className="grid gap-3 md:grid-cols-4">{["status", "posting_type", "source_record_type", "voucher_id"].map((field) => <Card key={field}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{field.replace(/_/g, " ")}</p><p className="text-lg font-semibold">{text(data[field])}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">Accounting mappings</CardTitle></CardHeader><CardContent><DataTable rows={(status.mappings as FAMRecord[] | undefined) || []} columns={["fam_record_type", "fam_record_id", "mapping_status"]} /></CardContent></Card></div>;
}

function PostingRulesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "postingRules"], queryFn: famApi.postingRules });
  const [draft, setDraft] = useState<FAMRecord>({ source_module: "srm", transaction_type: "sales_invoice", debit_ledger_rule_json: '{"type":"customer_ledger"}', credit_ledger_rule_json: '{"ledger_code":"SALES"}', tax_ledger_rule_json: '{"cgst":"OUTPUT-CGST","sgst":"OUTPUT-SGST"}', active: true });
  const mutation = useMutation({ mutationFn: () => famApi.createPostingRule({ ...draft, debit_ledger_rule_json: parseJson(draft.debit_ledger_rule_json), credit_ledger_rule_json: parseJson(draft.credit_ledger_rule_json), tax_ledger_rule_json: parseJson(draft.tax_ledger_rule_json) }), onSuccess: () => { toast({ title: "Posting rule saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[26rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create posting rule</CardTitle></CardHeader><CardContent className="space-y-3">{["source_module", "transaction_type", "debit_ledger_rule_json", "credit_ledger_rule_json", "tax_ledger_rule_json"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save posting rule</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Posting rules</CardTitle></CardHeader><CardContent><State label="posting rules" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["source_module", "transaction_type", "active", "roundoff_ledger_id"]} /></CardContent></Card></div>;
}

function ListCreateInline({ fields, draft, setDraft, onCreate }: { fields: string[]; draft: FAMRecord; setDraft: (value: FAMRecord | ((current: FAMRecord) => FAMRecord)) => void; onCreate: () => void }) {
  return <Card><CardContent className="grid gap-3 p-4 md:grid-cols-6">{fields.map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] || "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<div className="flex items-end"><Button onClick={onCreate}>Add</Button></div></CardContent></Card>;
}

function AuditView() {
  const query = useQuery({ queryKey: ["fam", "audit"], queryFn: famApi.auditLogs });
  const rows = listItems(query.data);
  return <Card><CardContent className="p-5"><State label="audit logs" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["performed_at", "record_type", "record_id", "action", "performed_by", "ip_address"]} /></CardContent></Card>;
}

function BankingView() {
  const accounts = useQuery({ queryKey: ["fam", "bankAccounts"], queryFn: famApi.bankAccounts });
  const statements = useQuery({ queryKey: ["fam", "bankStatements"], queryFn: famApi.bankStatements });
  const reconciliation = useQuery({ queryKey: ["fam", "bankReconciliation"], queryFn: famApi.bankReconciliation });
  const accountRows = listItems(accounts.data);
  const statementRows = listItems(statements.data);
  const recon = (reconciliation.data || {}) as FAMRecord;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Bank accounts</p><p className="text-2xl font-semibold">{accountRows.length}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Statements</p><p className="text-2xl font-semibold">{statementRows.length}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Unmatched lines</p><p className="text-2xl font-semibold">{text(recon.unmatched_count)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Bank feeds</p><p className="text-lg font-semibold">Manual import only</p></CardContent></Card>
      </div>
      <Card><CardHeader><CardTitle className="text-base">Banking actions</CardTitle></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {[["Bank Accounts", "/fam/bank-accounts"], ["Statements", "/fam/bank-statements"], ["Reconciliation", "/fam/bank-reconciliation"], ["Bank Book", "/fam/bank-book"], ["Cash Book", "/fam/cash-book"]].map(([label, to]) => <Button key={to} asChild variant="outline"><Link to={to}>{label}</Link></Button>)}
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Recent statements</CardTitle></CardHeader><CardContent><State label="banking" isLoading={accounts.isLoading || statements.isLoading || reconciliation.isLoading} isError={accounts.isError || statements.isError || reconciliation.isError} /><DataTable rows={statementRows} columns={["id", "bank_account_id", "statement_period_start", "statement_period_end", "status", "imported_file_name"]} /></CardContent></Card>
    </div>
  );
}

function BankAccountsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "bankAccounts"], queryFn: famApi.bankAccounts });
  const [draft, setDraft] = useState<FAMRecord>({ ledger_id: 1, bank_name: "HDFC Bank", branch_name: "Bengaluru", account_number_masked: "XXXX1234", ifsc: "HDFC0001234", account_type: "current", opening_balance: 0, active: true });
  const mutation = useMutation({ mutationFn: () => famApi.createBankAccount(draft), onSuccess: () => { toast({ title: "Bank account saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create bank account</CardTitle></CardHeader><CardContent className="space-y-3">{["ledger_id", "bank_name", "branch_name", "account_number_masked", "ifsc", "account_type", "opening_balance"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save bank account</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Bank accounts</CardTitle></CardHeader><CardContent><State label="bank accounts" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["bank_name", "branch_name", "ledger_id", "account_number_masked", "ifsc", "account_type", "opening_balance", "active"]} /></CardContent></Card></div>;
}

function PaymentModesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "paymentModes"], queryFn: famApi.paymentModes });
  const [draft, setDraft] = useState<FAMRecord>({ name: "UPI", type: "upi", default_ledger_id: 1, active: true });
  const mutation = useMutation({ mutationFn: () => famApi.createPaymentMode(draft), onSuccess: () => { toast({ title: "Payment mode saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create payment mode</CardTitle></CardHeader><CardContent className="space-y-3">{["name", "type", "default_ledger_id"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save payment mode</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Payment modes</CardTitle></CardHeader><CardContent><State label="payment modes" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["name", "type", "default_ledger_id", "active"]} /></CardContent></Card></div>;
}

function BankStatementsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "bankStatements"], queryFn: famApi.bankStatements });
  const [draft, setDraft] = useState<FAMRecord>({ bank_account_id: 1, statement_period_start: "2026-06-01", statement_period_end: "2026-06-30", imported_file_name: "hdfc-june.csv", file_content: "transaction_date,description,reference_number,debit_amount,credit_amount,balance\n2026-06-06,Receipt from customer,REF-1,0,1000,1000" });
  const mutation = useMutation({ mutationFn: () => famApi.importBankStatement(draft), onSuccess: () => { toast({ title: "Bank statement imported" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[28rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Upload statement</CardTitle></CardHeader><CardContent className="space-y-3">{["bank_account_id", "statement_period_start", "statement_period_end", "imported_file_name"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("period") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Field label="CSV content"><textarea className="min-h-36 w-full rounded-md border bg-background px-3 py-2 text-sm" value={String(draft.file_content || "")} onChange={(event) => setDraft((current) => ({ ...current, file_content: event.target.value }))} /></Field><p className="text-xs text-muted-foreground">Manual import only. Statement lines are imported for review and are not posted automatically.</p><Button className="w-full" onClick={() => mutation.mutate()}>Import statement</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Bank statements</CardTitle></CardHeader><CardContent><State label="bank statements" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["id", "bank_account_id", "statement_period_start", "statement_period_end", "status", "imported_file_name"]} />{listItems(query.data).slice(0, 4).map((item) => <Button key={String(item.id)} asChild variant="link" className="px-0"><Link to={`/fam/bank-statements/${item.id}`}>Open statement #{text(item.id)}</Link></Button>)}</CardContent></Card></div>;
}

function BankStatementDetailView() {
  const { id = "1" } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "bankStatement", id], queryFn: () => famApi.bankStatement(id) });
  const data = (query.data || {}) as FAMRecord;
  const firstLine = (((data.lines as FAMRecord[] | undefined) || [])[0] || {}) as FAMRecord;
  const action = useMutation({ mutationFn: (run: () => Promise<FAMRecord>) => run(), onSuccess: () => { toast({ title: "Bank reconciliation updated" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4">{["status", "bank_account_id", "statement_period_start", "statement_period_end"].map((field) => <Card key={field}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{field.replace(/_/g, " ")}</p><p className="text-lg font-semibold">{text(data[field])}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">Review and match</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-2"><Button onClick={() => action.mutate(() => famApi.autoMatchBankStatement(id))}>Auto-match</Button><Button variant="outline" onClick={() => action.mutate(() => famApi.matchBankStatement(id, { statement_line_id: Number(firstLine.id || 1), voucher_id: Number(firstLine.matched_voucher_id || 1), matched_amount: Number(firstLine.credit_amount || firstLine.debit_amount || 1000), confirm: true }))}>Confirm match</Button><Button variant="outline" onClick={() => action.mutate(() => famApi.ignoreBankStatementLine(id, { statement_line_id: Number(firstLine.id || 1), reason: "Non-book item" }))}>Ignore line</Button><Button variant="outline" onClick={() => action.mutate(() => famApi.reconcileBankStatement(id))}>Reconcile statement</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Statement lines</CardTitle></CardHeader><CardContent><State label="statement" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.lines as FAMRecord[] | undefined) || []} columns={["transaction_date", "description", "reference_number", "debit_amount", "credit_amount", "balance", "matched_status", "matched_voucher_id"]} /></CardContent></Card></div>;
}

function BankReconciliationView() {
  const query = useQuery({ queryKey: ["fam", "bankReconciliation"], queryFn: famApi.bankReconciliation });
  const data = (query.data || {}) as FAMRecord;
  return <div className="space-y-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Unmatched statement lines</p><p className="text-2xl font-semibold">{text(data.unmatched_count)}</p></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Reconciliation sessions</CardTitle></CardHeader><CardContent><State label="bank reconciliation" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.sessions as FAMRecord[] | undefined) || []} columns={["statement_id", "bank_account_id", "book_balance", "bank_statement_balance", "status", "reconciled_at"]} /></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Statements</CardTitle></CardHeader><CardContent><DataTable rows={(data.statements as FAMRecord[] | undefined) || []} columns={["id", "bank_account_id", "status", "statement_period_start", "statement_period_end"]} /></CardContent></Card></div>;
}

function BookView({ kind }: { kind: "bank" | "cash" }) {
  const query = useQuery({ queryKey: ["fam", `${kind}Book`], queryFn: kind === "bank" ? famApi.bankBook : famApi.cashBook });
  const data = (query.data || {}) as FAMRecord;
  const summaryCards: Array<[string, unknown]> = [["Opening", data.openingBalance], ["Debit", data.debitTotal], ["Credit", data.creditTotal], ["Closing", data.closingBalance]];
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4">{summaryCards.map(([label, value]) => <Card key={label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="text-lg font-semibold">{money(value)}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">{kind === "bank" ? "Bank" : "Cash"} ledgers</CardTitle></CardHeader><CardContent><State label={`${kind} book`} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.ledgers as FAMRecord[] | undefined) || []} columns={["ledger_code", "ledger_name", "ledger_type", "current_balance_dr", "current_balance_cr"]} /></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Voucher entries</CardTitle></CardHeader><CardContent><DataTable rows={(data.items as FAMRecord[] | undefined) || []} columns={["voucher_date", "voucher_number", "ledger_id", "debit_amount", "credit_amount", "running_balance", "narration"]} /></CardContent></Card></div>;
}

function ContraView() {
  const [draft, setDraft] = useState<FAMRecord>({ from_ledger_id: 1, to_ledger_id: 2, amount: 1000, contra_date: "2026-06-06", reference_number: "CONTRA-1", narration: "Cash deposited to bank" });
  const mutation = useMutation({ mutationFn: () => famApi.postContra(draft), onSuccess: () => toast({ title: "Contra voucher posted" }) });
  return <Card><CardHeader><CardTitle className="text-base">Post contra entry</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{["from_ledger_id", "to_ledger_id", "amount", "contra_date", "reference_number", "narration"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<div className="md:col-span-2"><Button onClick={() => mutation.mutate()}>Post contra</Button></div></CardContent></Card>;
}

function BankChargesView() {
  const [draft, setDraft] = useState<FAMRecord>({ bank_account_id: 1, expense_ledger_id: 1, amount: 250, charge_date: "2026-06-06", reference_number: "CHG-1", narration: "Monthly bank charges" });
  const mutation = useMutation({ mutationFn: () => famApi.postBankCharges(draft), onSuccess: () => toast({ title: "Bank charge voucher posted" }) });
  return <Card><CardHeader><CardTitle className="text-base">Post bank charges</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{["bank_account_id", "expense_ledger_id", "amount", "charge_date", "reference_number", "narration"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<div className="md:col-span-2"><Button onClick={() => mutation.mutate()}>Post bank charge</Button></div></CardContent></Card>;
}

function GSTHomeView() {
  const links = [["Registrations", "/fam/gst/registrations"], ["Rates", "/fam/gst/rates"], ["HSN/SAC", "/fam/gst/hsn-sac"], ["Sales Register", "/fam/gst/sales-register"], ["Purchase Register", "/fam/gst/purchase-register"], ["GSTR-1", "/fam/gst/gstr1"], ["GSTR-3B", "/fam/gst/gstr3b"], ["E-Invoice", "/fam/gst/einvoice"], ["E-Way Bill", "/fam/gst/ewaybill"], ["Reconciliation", "/fam/gst/reconciliation"]];
  return <div className="grid gap-3 md:grid-cols-3">{links.map(([label, href]) => <Card key={href}><CardContent className="flex items-center justify-between p-4"><span className="font-medium">{label}</span><Button asChild variant="outline"><Link to={href}>Open</Link></Button></CardContent></Card>)}</div>;
}

function GSTMasterView({ kind }: { kind: "registrations" | "rates" | "hsn" }) {
  const queryClient = useQueryClient();
  const config = {
    registrations: { queryKey: "gstRegistrations", queryFn: famApi.gstRegistrations, mutationFn: famApi.createGstRegistration, fields: ["gstin", "legal_name", "trade_name", "state_code", "registration_type", "effective_from"], columns: ["gstin", "legal_name", "state_code", "registration_type", "effective_from", "active"], draft: { registration_type: "regular", effective_from: "2026-04-01", active: true } },
    rates: { queryKey: "gstRates", queryFn: famApi.gstRates, mutationFn: famApi.createGstRate, fields: ["rate_name", "tax_type", "cgst_rate", "sgst_rate", "igst_rate", "cess_rate", "effective_from"], columns: ["rate_name", "tax_type", "cgst_rate", "sgst_rate", "igst_rate", "cess_rate", "effective_from", "active"], draft: { tax_type: "goods", cgst_rate: 9, sgst_rate: 9, igst_rate: 18, cess_rate: 0, effective_from: "2026-04-01", active: true } },
    hsn: { queryKey: "hsnSac", queryFn: famApi.hsnSac, mutationFn: famApi.createHsnSac, fields: ["code", "description", "type", "default_gst_rate_id"], columns: ["code", "description", "type", "default_gst_rate_id", "active"], draft: { type: "hsn", active: true } },
  }[kind];
  const query = useQuery({ queryKey: ["fam", config.queryKey], queryFn: config.queryFn });
  const [draft, setDraft] = useState<FAMRecord>(config.draft);
  const mutation = useMutation({ mutationFn: () => config.mutationFn(draft), onSuccess: () => { toast({ title: "GST master saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create {kind}</CardTitle></CardHeader><CardContent className="space-y-3">{config.fields.map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Records</CardTitle></CardHeader><CardContent><State label={kind} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={config.columns} /></CardContent></Card></div>;
}

function GSTSettingsView() {
  return <div className="grid gap-4 md:grid-cols-2"><ProviderSettingsView kind="einvoice" /><ProviderSettingsView kind="ewaybill" /></div>;
}

function GSTRegisterView({ kind }: { kind: "sales" | "purchase" }) {
  const query = useQuery({ queryKey: ["fam", "gst", kind], queryFn: kind === "sales" ? famApi.gstSalesRegister : famApi.gstPurchaseRegister });
  const data = (query.data || {}) as FAMRecord;
  return <Card><CardHeader><CardTitle className="text-base">{kind === "sales" ? "Sales" : "Purchase"} GST register</CardTitle></CardHeader><CardContent><State label={`${kind} register`} isLoading={query.isLoading} isError={query.isError} /><div className="mb-3 grid gap-3 md:grid-cols-5">{["taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "cess_amount"].map((key) => <Card key={key}><CardContent className="p-3"><p className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</p><p className="font-semibold">{money((data.totals as FAMRecord | undefined)?.[key])}</p></CardContent></Card>)}</div><DataTable rows={listItems(query.data)} columns={["transaction_type", "supply_type", "gstin", "place_of_supply_state", "hsn_sac_code", "taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "itc_eligible", "reverse_charge"]} /></CardContent></Card>;
}

function GSTReturnView({ kind }: { kind: "gstr1" | "gstr3b" }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", kind], queryFn: kind === "gstr1" ? famApi.gstr1 : famApi.gstr3b });
  const [draft, setDraft] = useState<FAMRecord>({ period_month: 6, period_year: 2026 });
  const mutation = useMutation({ mutationFn: () => kind === "gstr1" ? famApi.prepareGstr1(draft) : famApi.prepareGstr3b(draft), onSuccess: () => { toast({ title: `${kind.toUpperCase()} prepared` }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[20rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Prepare {kind.toUpperCase()}</CardTitle></CardHeader><CardContent className="space-y-3">{["period_month", "period_year"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field])} onChange={(event) => setDraft((current) => ({ ...current, [field]: Number(event.target.value) }))} /></Field>)}<p className="text-xs text-muted-foreground">Working return only. GST portal filing is not integrated.</p><Button className="w-full" onClick={() => mutation.mutate()}>Prepare</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Prepared records</CardTitle></CardHeader><CardContent><State label={kind} isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["section", "taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "cess_amount", "record_count"]} /></CardContent></Card></div>;
}

function GSTReconciliationView() {
  const query = useQuery({ queryKey: ["fam", "gstReconciliation"], queryFn: famApi.gstReconciliation });
  return <Card><CardHeader><CardTitle className="text-base">GST reconciliation foundation</CardTitle></CardHeader><CardContent><State label="GST reconciliation" isLoading={query.isLoading} isError={query.isError} /><p className="mb-3 text-sm text-muted-foreground">External portal reconciliation is not configured. Exceptions are tracked without pretending portal data exists.</p><DataTable rows={listItems(query.data)} columns={["source_type", "source_record_id", "mismatch_type", "expected_amount", "actual_amount", "status", "notes"]} /></CardContent></Card>;
}

function ProviderSettingsView({ kind }: { kind: "einvoice" | "ewaybill" }) {
  const queryClient = useQueryClient();
  const isEinvoice = kind === "einvoice";
  const query = useQuery({ queryKey: ["fam", kind, "settings"], queryFn: isEinvoice ? famApi.einvoiceSettings : famApi.ewaybillSettings });
  const [draft, setDraft] = useState<FAMRecord>({});
  const effective = { ...((query.data || {}) as FAMRecord), ...draft };
  const save = useMutation({ mutationFn: () => isEinvoice ? famApi.updateEinvoiceSettings(effective) : famApi.updateEwaybillSettings(effective), onSuccess: () => { toast({ title: "Provider settings saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const generate = useMutation({ mutationFn: () => isEinvoice ? famApi.generateEinvoice(1) : famApi.generateEwaybill(1), onSuccess: (data) => toast({ title: text((data as FAMRecord).message) }) });
  return <Card><CardHeader><CardTitle className="text-base">{isEinvoice ? "E-Invoice" : "E-Way Bill"} provider</CardTitle></CardHeader><CardContent className="space-y-3"><State label={`${kind} settings`} isLoading={query.isLoading} isError={query.isError} /><Badge variant={effective.credentials_configured ? "default" : "secondary"}>{effective.credentials_configured ? "configured" : "not configured"}</Badge>{["provider_name", "api_base_url", ...(isEinvoice ? ["applicable_from"] : ["threshold_amount"])].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(effective[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<div className="flex flex-wrap gap-2"><Button onClick={() => save.mutate()}>Save settings</Button><Button variant="outline" onClick={() => generate.mutate()}>Generate test job</Button></div><p className="text-xs text-muted-foreground">No IRN or EWB number is generated unless a real provider is configured.</p></CardContent></Card>;
}

function PurchasesHomeView() {
  const links = [
    ["Purchase Bills", "/fam/purchase-bills"],
    ["Expenses", "/fam/expenses"],
    ["TDS", "/fam/tds"],
    ["Purchase Register", "/fam/purchase-register"],
    ["Expense Register", "/fam/expense-register"],
    ["Vendor Payments", "/fam/vendor-payments"],
    ["Payables Dashboard", "/fam/payables/dashboard"],
  ];
  return <div className="grid gap-3 md:grid-cols-3">{links.map(([label, href]) => <Card key={href}><CardContent className="flex items-center justify-between p-4"><span className="font-medium">{label}</span><Button asChild variant="outline"><Link to={href}>Open</Link></Button></CardContent></Card>)}</div>;
}

function defaultPurchaseBill(): FAMRecord {
  return {
    vendor_id: 2,
    bill_number: `PB-${Date.now().toString().slice(-5)}`,
    bill_date: "2026-06-06",
    due_date: "2026-07-06",
    gstin: "29ABCDE1234F1Z5",
    place_of_supply: "29",
    discount_total: 0,
    lines: [{ expense_ledger_id: 1, description: "Professional services", hsn_sac: "998314", quantity: 1, rate: 1000, taxable_value: 1000, gst_amount: 180, tds_section_id: 1, tds_amount: 100, line_total: 1080 }],
  };
}

function PurchaseBillFormView({ detail }: { detail?: boolean }) {
  const params = useParams();
  const queryClient = useQueryClient();
  const billQuery = useQuery({ queryKey: ["fam", "purchaseBill", params.id], queryFn: () => famApi.purchaseBill(params.id || "1"), enabled: detail && Boolean(params.id) });
  const [draft, setDraft] = useState<FAMRecord>(defaultPurchaseBill());
  const effective = (detail && billQuery.data ? billQuery.data : draft) as FAMRecord;
  const lines = ((effective.lines as FAMRecord[] | undefined) || []) as FAMRecord[];
  const subtotal = lines.reduce((sum, line) => sum + Number(line.taxable_value || (Number(line.quantity || 0) * Number(line.rate || 0))), 0);
  const gstTotal = lines.reduce((sum, line) => sum + Number(line.gst_amount || 0), 0);
  const tdsTotal = lines.reduce((sum, line) => sum + Number(line.tds_amount || 0), 0);
  const grandTotal = subtotal + gstTotal - Number(effective.discount_total || 0) - tdsTotal;
  const billId = String(effective.id || params.id || "");
  const canEdit = String(effective.status || "draft") === "draft" && !detail;
  const patch = (key: string, value: unknown) => setDraft((current) => ({ ...effective, ...current, [key]: numericFields.has(key) ? Number(value) : value }));
  const patchLine = (index: number, key: string, value: unknown) => patch("lines", lines.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: numericFields.has(key) ? Number(value) : value } : line));
  const save = useMutation({ mutationFn: () => detail && billId ? famApi.updatePurchaseBill(billId, effective) : famApi.createPurchaseBill(effective), onSuccess: () => { toast({ title: "Purchase bill saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const post = useMutation({ mutationFn: () => famApi.postPurchaseBill(billId), onSuccess: () => { toast({ title: "Purchase bill posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  const cancel = useMutation({ mutationFn: () => famApi.cancelPurchaseBill(billId), onSuccess: () => { toast({ title: "Purchase bill cancelled" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return (
    <div className="space-y-4">
      <State label="purchase bill" isLoading={billQuery.isLoading} isError={billQuery.isError} />
      <div className="grid gap-3 md:grid-cols-4">
        {["vendor_id", "bill_number", "bill_date", "due_date", "gstin", "place_of_supply", "discount_total"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(effective[field] ?? "")} onChange={(event) => patch(field, event.target.value)} disabled={detail && !canEdit} /></Field>)}
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Status</p><Badge variant={statusTone(effective.status || "draft")}>{text(effective.status || "draft")}</Badge></CardContent></Card>
      </div>
      <Card><CardHeader><CardTitle className="text-base">Bill lines</CardTitle></CardHeader><CardContent className="space-y-3"><div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[980px] text-sm"><thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground"><tr>{["expense_ledger_id", "description", "hsn_sac", "quantity", "rate", "taxable_value", "gst_amount", "tds_section_id", "tds_amount", "line_total"].map((column) => <th key={column} className="px-3 py-2">{column.replace(/_/g, " ")}</th>)}</tr></thead><tbody>{lines.map((line, index) => <tr key={index} className="border-t">{["expense_ledger_id", "description", "hsn_sac", "quantity", "rate", "taxable_value", "gst_amount", "tds_section_id", "tds_amount", "line_total"].map((field) => <td key={field} className="px-3 py-2"><Input value={String(line[field] ?? "")} onChange={(event) => patchLine(index, field, event.target.value)} disabled={detail && !canEdit} /></td>)}</tr>)}</tbody></table></div>{!detail ? <Button variant="outline" onClick={() => patch("lines", [...lines, { expense_ledger_id: 1, description: "", quantity: 1, rate: 0, taxable_value: 0, gst_amount: 0, tds_amount: 0, line_total: 0 }])}><Plus className="h-4 w-4" />Add line</Button> : null}</CardContent></Card>
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Subtotal</p><p className="text-lg font-semibold">{money(effective.subtotal || subtotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Input GST</p><p className="text-lg font-semibold">{money(effective.gst_total || gstTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">TDS deduction</p><p className="text-lg font-semibold">{money(effective.tds_amount || tdsTotal)}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Grand total</p><p className="text-lg font-semibold">{money(effective.grand_total || grandTotal)}</p></CardContent></Card>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => save.mutate()} disabled={save.isPending}><Save className="h-4 w-4" />Save bill</Button>
        {billId ? <Button variant="outline" onClick={() => post.mutate()} disabled={post.isPending || String(effective.status) !== "draft"}>Post bill</Button> : null}
        {billId ? <Button variant="outline" onClick={() => cancel.mutate()} disabled={cancel.isPending || ["paid", "cancelled"].includes(String(effective.status))}>Cancel bill</Button> : null}
      </div>
      {detail ? <Card><CardHeader><CardTitle className="text-base">Audit trail</CardTitle></CardHeader><CardContent><DataTable rows={(effective.audit_logs as FAMRecord[] | undefined) || []} columns={["action", "performed_by", "performed_at", "remarks"]} /></CardContent></Card> : null}
    </div>
  );
}

function PurchaseBillsView() {
  const query = useQuery({ queryKey: ["fam", "purchaseBills"], queryFn: famApi.purchaseBills });
  const rows = listItems(query.data);
  return <Card><CardHeader><CardTitle className="text-base">Vendor bills</CardTitle></CardHeader><CardContent className="space-y-3"><Button asChild><Link to="/fam/purchase-bills/new"><Plus className="h-4 w-4" />New purchase bill</Link></Button><State label="purchase bills" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["bill_number", "vendor_id", "bill_date", "due_date", "subtotal", "gst_total", "tds_amount", "grand_total", "status", "voucher_id"]} />{rows.slice(0, 4).map((item) => <Button key={String(item.id)} asChild variant="link" className="px-0"><Link to={`/fam/purchase-bills/${item.id}`}>Open bill {text(item.bill_number)}</Link></Button>)}</CardContent></Card>;
}

function ExpenseFormView() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<FAMRecord>({ claimant_name: "Finance User", claim_number: "EXP-001", claim_date: "2026-06-06", status: "draft", lines: [{ expense_ledger_id: 1, description: "Travel expense", taxable_value: 1200, gst_amount: 0 }] });
  const lines = (draft.lines as FAMRecord[]) || [];
  const total = lines.reduce((sum, line) => sum + Number(line.taxable_value || 0) + Number(line.gst_amount || 0), 0);
  const mutation = useMutation({ mutationFn: () => famApi.createExpense(draft), onSuccess: () => { toast({ title: "Expense claim saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4">{["claimant_name", "claim_number", "claim_date", "status"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}</div><Card><CardHeader><CardTitle className="text-base">Expense lines</CardTitle></CardHeader><CardContent className="space-y-3">{lines.map((line, index) => <div key={index} className="grid gap-3 md:grid-cols-4">{["expense_ledger_id", "description", "taxable_value", "gst_amount"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(line[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, lines: lines.map((item, lineIndex) => lineIndex === index ? { ...item, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value } : item) }))} /></Field>)}</div>)}<Button variant="outline" onClick={() => setDraft((current) => ({ ...current, lines: [...lines, { expense_ledger_id: 1, description: "", taxable_value: 0, gst_amount: 0 }] }))}><Plus className="h-4 w-4" />Add expense line</Button></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Claim total</p><p className="text-lg font-semibold">{money(total)}</p></CardContent></Card><Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>Save expense claim</Button></div>;
}

function ExpensesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "expenses"], queryFn: famApi.expenses });
  const rows = listItems(query.data);
  const post = useMutation({ mutationFn: (id: number | string) => famApi.postExpense(id), onSuccess: () => { toast({ title: "Expense posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <Card><CardHeader><CardTitle className="text-base">Expense claims</CardTitle></CardHeader><CardContent className="space-y-3"><Button asChild><Link to="/fam/expenses/new"><Plus className="h-4 w-4" />New expense</Link></Button><State label="expenses" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["claim_number", "employee_id", "claim_date", "total_amount", "status", "voucher_id"]} />{rows.slice(0, 3).map((item) => <Button key={String(item.id)} variant="outline" onClick={() => post.mutate(String(item.id))} disabled={String(item.status) !== "draft"}>Post {text(item.claim_number)}</Button>)}</CardContent></Card>;
}

function TDSHomeView() {
  const [draft, setDraft] = useState<FAMRecord>({ vendor_id: 2, section_id: 1, taxable_amount: 1000, deduction_date: "2026-06-06" });
  const calc = useMutation({ mutationFn: () => famApi.calculateTds(draft), onSuccess: (data) => toast({ title: `TDS ${money((data as FAMRecord).tds_amount)}` }) });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Calculate TDS</CardTitle></CardHeader><CardContent className="space-y-3">{["vendor_id", "section_id", "taxable_amount", "deduction_date"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => calc.mutate()}>Calculate TDS</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">TDS workbench</CardTitle></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2">{[["Sections", "/fam/tds/sections"], ["Transactions", "/fam/tds/transactions"], ["Payable", "/fam/tds/payable"]].map(([label, href]) => <Button key={href} asChild variant="outline"><Link to={href}>{label}</Link></Button>)}<p className="text-xs text-muted-foreground sm:col-span-2">TDS return filing is not implemented or simulated in this phase.</p></CardContent></Card></div>;
}

function TDSSectionsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "tdsSections"], queryFn: famApi.tdsSections });
  const [draft, setDraft] = useState<FAMRecord>({ section_code: "194J", description: "Professional fees", default_rate: 10, threshold_amount: 30000, effective_from: "2026-04-01", active: true });
  const mutation = useMutation({ mutationFn: () => famApi.createTdsSection(draft), onSuccess: () => { toast({ title: "TDS section saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create TDS section</CardTitle></CardHeader><CardContent className="space-y-3">{["section_code", "description", "default_rate", "threshold_amount", "effective_from"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save section</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Sections</CardTitle></CardHeader><CardContent><State label="TDS sections" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["section_code", "description", "default_rate", "threshold_amount", "effective_from", "active"]} /></CardContent></Card></div>;
}

function TDSTransactionsView() {
  const query = useQuery({ queryKey: ["fam", "tdsTransactions"], queryFn: famApi.tdsTransactions });
  return <Card><CardHeader><CardTitle className="text-base">TDS transaction register</CardTitle></CardHeader><CardContent><State label="TDS transactions" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["voucher_id", "vendor_id", "section_id", "taxable_amount", "tds_rate", "tds_amount", "deduction_date", "status"]} /></CardContent></Card>;
}

function TDSPayableView() {
  const query = useQuery({ queryKey: ["fam", "tdsPayable"], queryFn: famApi.tdsPayable });
  const data = (query.data || {}) as FAMRecord;
  return <div className="space-y-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">TDS payable</p><p className="text-2xl font-semibold">{money(data.total_payable || data.totalPayable)}</p></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Section-wise payable</CardTitle></CardHeader><CardContent><State label="TDS payable" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.items as FAMRecord[] | undefined) || []} columns={["section_id", "section_code", "vendor_id", "taxable_amount", "tds_amount", "status"]} /><p className="mt-3 text-xs text-muted-foreground">Filing/export is unsupported unless a future backend endpoint is added.</p></CardContent></Card></div>;
}

function PurchaseRegisterView() {
  const query = useQuery({ queryKey: ["fam", "purchaseRegister"], queryFn: famApi.purchaseRegister });
  const data = (query.data || {}) as FAMRecord;
  return <Card><CardHeader><CardTitle className="text-base">Purchase register</CardTitle></CardHeader><CardContent className="space-y-3"><State label="purchase register" isLoading={query.isLoading} isError={query.isError} /><div className="grid gap-3 md:grid-cols-4">{["subtotal", "gst_total", "tds_amount", "grand_total"].map((key) => <Card key={key}><CardContent className="p-3"><p className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</p><p className="font-semibold">{money((data.totals as FAMRecord | undefined)?.[key] || data[key])}</p></CardContent></Card>)}</div><DataTable rows={listItems(data)} columns={["bill_number", "vendor_id", "bill_date", "gstin", "place_of_supply", "subtotal", "gst_total", "tds_amount", "grand_total", "status"]} /></CardContent></Card>;
}

function ExpenseRegisterView() {
  const query = useQuery({ queryKey: ["fam", "expenseRegister"], queryFn: famApi.expenseRegister });
  const data = (query.data || {}) as FAMRecord;
  return <Card><CardHeader><CardTitle className="text-base">Expense register</CardTitle></CardHeader><CardContent className="space-y-3"><State label="expense register" isLoading={query.isLoading} isError={query.isError} /><Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Total expenses</p><p className="font-semibold">{money(data.total_amount || (data.totals as FAMRecord | undefined)?.total_amount)}</p></CardContent></Card><DataTable rows={listItems(data)} columns={["claim_number", "employee_id", "claim_date", "total_amount", "status", "voucher_id"]} /></CardContent></Card>;
}

function VendorPaymentsView() {
  const queryClient = useQueryClient();
  const dashboard = useQuery({ queryKey: ["fam", "payablesDashboard"], queryFn: famApi.payablesDashboard });
  const [draft, setDraft] = useState<FAMRecord>({ payment_date: "2026-06-06", bank_ledger_id: 3, items: [{ vendor_id: 2, purchase_bill_id: 1, bill_reference_id: 2, amount: 900 }] });
  const line = ((draft.items as FAMRecord[]) || [])[0] || {};
  const prepare = useMutation({ mutationFn: () => famApi.prepareVendorPayment(draft), onSuccess: () => toast({ title: "Payment run prepared" }) });
  const post = useMutation({ mutationFn: () => famApi.postVendorPayment(draft), onSuccess: () => { toast({ title: "Vendor payment posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Vendor payment run</CardTitle></CardHeader><CardContent className="space-y-3">{["payment_date", "bank_ledger_id"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}{["vendor_id", "purchase_bill_id", "bill_reference_id", "amount"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(line[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, items: [{ ...line, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }] }))} /></Field>)}<div className="flex gap-2"><Button variant="outline" onClick={() => prepare.mutate()}>Prepare</Button><Button onClick={() => post.mutate()}>Post payment</Button></div></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Open payables</CardTitle></CardHeader><CardContent><State label="payables" isLoading={dashboard.isLoading} isError={dashboard.isError} /><DataTable rows={(dashboard.data as FAMRecord | undefined)?.items as FAMRecord[] || []} columns={["bill_number", "party_id", "due_date", "outstanding_amount", "status"]} /></CardContent></Card></div>;
}

function PayablesDashboardView() {
  const query = useQuery({ queryKey: ["fam", "payablesDashboard"], queryFn: famApi.payablesDashboard });
  const data = (query.data || {}) as FAMRecord;
  const buckets = (data.buckets || {}) as FAMRecord;
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-4"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total payable</p><p className="text-lg font-semibold">{money(data.totalOutstanding || data.total_payable)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Draft bills</p><p className="text-lg font-semibold">{text(data.draftBills)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Posted bills</p><p className="text-lg font-semibold">{text(data.postedBills)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Paid bills</p><p className="text-lg font-semibold">{text(data.paidBills)}</p></CardContent></Card></div><div className="grid gap-3 md:grid-cols-6">{["Not due", "0-30", "31-60", "61-90", "91-180", ">180"].map((bucket) => <Card key={bucket}><CardContent className="p-3"><p className="text-xs text-muted-foreground">{bucket}</p><p className="font-semibold">{money(buckets[bucket])}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">Payable bills</CardTitle></CardHeader><CardContent><State label="payables dashboard" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={(data.items as FAMRecord[] | undefined) || []} columns={["bill_number", "party_id", "due_date", "aging_bucket", "outstanding_amount", "status"]} /></CardContent></Card></div>;
}

function InventoryDashboardView() {
  const dashboard = useQuery({ queryKey: ["fam", "inventoryDashboard"], queryFn: famApi.inventoryDashboard });
  const source = useQuery({ queryKey: ["fam", "inventorySourceAudit"], queryFn: famApi.inventorySourceAudit });
  const data = (dashboard.data || {}) as FAMRecord;
  const kpis: Array<[string, React.ReactNode]> = [["Items", text(data.items_count)], ["Warehouses", text(data.warehouses_count)], ["Stock value", money(data.total_stock_value)], ["Low stock", text(data.low_stock_count)]];
  const links: Array<[string, string]> = [["Items", "/fam/inventory/items"], ["Warehouses", "/fam/inventory/warehouses"], ["Stock In", "/fam/inventory/stock-in"], ["Stock Out", "/fam/inventory/stock-out"], ["Transfers", "/fam/inventory/stock-transfers"], ["Adjustments", "/fam/inventory/stock-adjustments"], ["Summary", "/fam/inventory/stock-summary"], ["Valuation", "/fam/inventory/valuation"], ["AI", "/fam/inventory/ai"]];
  return <div className="space-y-4"><State label="inventory dashboard" isLoading={dashboard.isLoading} isError={dashboard.isError} /><div className="grid gap-3 md:grid-cols-4">{kpis.map(([label, value]) => <Card key={label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></CardContent></Card>)}</div><Card><CardHeader><CardTitle className="text-base">Inventory workbench</CardTitle></CardHeader><CardContent className="grid gap-2 sm:grid-cols-3">{links.map(([label, href]) => <Button key={href} asChild variant="outline"><Link to={href}>{label}</Link></Button>)}</CardContent></Card><Card><CardHeader><CardTitle className="text-base">Source merge audit</CardTitle></CardHeader><CardContent><State label="source audit" isLoading={source.isLoading} isError={source.isError} /><DataTable rows={((source.data as FAMRecord | undefined)?.files as FAMRecord[] | undefined) || []} columns={["path", "exists"]} /></CardContent></Card></div>;
}

function InventoryItemsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["fam", "inventoryItems"], queryFn: () => famApi.inventoryItems() });
  const [draft, setDraft] = useState<FAMRecord>({ sku: "ITEM-001", item_name: "Demo Stock Item", purchase_rate: 100, sales_rate: 150, reorder_level: 5, min_stock: 2, track_inventory: true });
  const mutation = useMutation({ mutationFn: () => famApi.createInventoryItem(draft), onSuccess: () => { toast({ title: "Stock item saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create item</CardTitle></CardHeader><CardContent className="space-y-3">{["sku", "item_name", "hsn_code", "stock_group_id", "unit_id", "default_warehouse_id", "purchase_rate", "sales_rate", "reorder_level", "min_stock"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save item</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Stock items</CardTitle></CardHeader><CardContent><State label="stock items" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={["sku", "item_name", "hsn_code", "current_quantity", "average_cost", "reorder_level", "active"]} />{listItems(query.data).slice(0, 4).map((item) => <Button key={String(item.id)} asChild variant="link" className="px-0"><Link to={`/fam/inventory/items/${item.id}`}>Open {text(item.item_name)}</Link></Button>)}</CardContent></Card></div>;
}

function InventoryItemDetailView({ ledger = false }: { ledger?: boolean }) {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["fam", ledger ? "inventoryItemLedger" : "inventoryItem", id], queryFn: () => ledger ? famApi.inventoryItemLedger(id || "0") : famApi.inventoryItem(id || "0") });
  const data = (query.data || {}) as FAMRecord;
  const rows = ledger ? listItems(query.data) : ((data.ledger as FAMRecord[] | undefined) || []);
  const stats: Array<[string, React.ReactNode]> = [["SKU", text(data.sku)], ["Quantity", text(data.current_quantity)], ["Average cost", text(data.average_cost)], ["Stock value", money(data.stock_value)]];
  return <Card><CardHeader><CardTitle className="text-base">{ledger ? "Item ledger" : text(data.item_name || "Item detail")}</CardTitle></CardHeader><CardContent className="space-y-3"><State label="item detail" isLoading={query.isLoading} isError={query.isError} />{!ledger ? <div className="grid gap-3 md:grid-cols-4">{stats.map(([label, value]) => <Card key={label}><CardContent className="p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="font-semibold">{value}</p></CardContent></Card>)}</div> : null}<DataTable rows={rows} columns={["movement_id", "warehouse_id", "quantity_in", "quantity_out", "rate", "value", "balance_quantity"]} /></CardContent></Card>;
}

function InventoryMasterView({ kind }: { kind: "groups" | "units" | "warehouses" }) {
  const queryClient = useQueryClient();
  const config = {
    groups: { queryKey: "inventoryGroups", query: famApi.inventoryStockGroups, create: famApi.createInventoryStockGroup, initial: { group_code: "RAW", group_name: "Raw Materials" }, fields: ["group_code", "group_name", "parent_group_id"], columns: ["group_code", "group_name", "parent_group_id", "active"] },
    units: { queryKey: "inventoryUnits", query: famApi.inventoryUnits, create: famApi.createInventoryUnit, initial: { unit_code: "PCS", unit_name: "Pieces", symbol: "pcs", decimal_allowed: true }, fields: ["unit_code", "unit_name", "symbol"], columns: ["unit_code", "unit_name", "symbol", "decimal_allowed", "active"] },
    warehouses: { queryKey: "inventoryWarehouses", query: famApi.inventoryWarehouses, create: famApi.createInventoryWarehouse, initial: { warehouse_code: "MAIN", warehouse_name: "Main Warehouse" }, fields: ["warehouse_code", "warehouse_name", "branch_id", "address"], columns: ["warehouse_code", "warehouse_name", "branch_id", "active"] },
  }[kind];
  const query = useQuery({ queryKey: ["fam", config.queryKey], queryFn: config.query });
  const [draft, setDraft] = useState<FAMRecord>(config.initial);
  const mutation = useMutation({ mutationFn: () => config.create(draft), onSuccess: () => { toast({ title: "Inventory master saved" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Create</CardTitle></CardHeader><CardContent className="space-y-3">{config.fields.map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}<Button className="w-full" onClick={() => mutation.mutate()}>Save</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Records</CardTitle></CardHeader><CardContent><State label="inventory masters" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={listItems(query.data)} columns={config.columns} /></CardContent></Card></div>;
}

function InventoryMovementView({ mode }: { mode: "in" | "out" | "purchase" | "delivery" }) {
  const queryClient = useQueryClient();
  const movementType = mode === "in" ? "stock_in" : mode === "out" ? "stock_out" : mode === "purchase" ? "purchase_receipt" : "delivery_note";
  const quantityKey = mode === "out" || mode === "delivery" ? "quantity_out" : "quantity_in";
  const [draft, setDraft] = useState<FAMRecord>({ movement_date: "2026-06-06", movement_type: movementType, lines: [{ stock_item_id: 1, warehouse_id: 1, [quantityKey]: 1, rate: 100 }] });
  const line = ((draft.lines as FAMRecord[]) || [])[0] || {};
  const mutation = useMutation({ mutationFn: async () => { const movement = await famApi.createInventoryStockMovement(draft); return famApi.postInventoryStockMovement(String((movement as FAMRecord).id), draft); }, onSuccess: () => { toast({ title: "Stock movement posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <Card><CardHeader><CardTitle className="text-base">Post {movementType.replace(/_/g, " ")}</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">{["movement_date", "reference_number", "narration"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.value }))} /></Field>)}{["stock_item_id", "warehouse_id", quantityKey, "rate"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(line[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, lines: [{ ...line, [field]: Number(event.target.value) }] }))} /></Field>)}<div className="md:col-span-3"><Button onClick={() => mutation.mutate()}>Post movement</Button></div></CardContent></Card>;
}

function InventoryTransferView() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<FAMRecord>({ transfer_date: "2026-06-06", from_warehouse_id: 1, to_warehouse_id: 2, lines: [{ stock_item_id: 1, quantity: 1, rate: 100 }] });
  const line = ((draft.lines as FAMRecord[]) || [])[0] || {};
  const mutation = useMutation({ mutationFn: async () => { const transfer = await famApi.createInventoryTransfer(draft); return famApi.postInventoryTransfer(String((transfer as FAMRecord).id)); }, onSuccess: () => { toast({ title: "Transfer posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <Card><CardHeader><CardTitle className="text-base">Stock transfer</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">{["transfer_date", "from_warehouse_id", "to_warehouse_id"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}{["stock_item_id", "quantity", "rate"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(line[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, lines: [{ ...line, [field]: Number(event.target.value) }] }))} /></Field>)}<div className="md:col-span-3"><Button onClick={() => mutation.mutate()}>Post transfer</Button></div></CardContent></Card>;
}

function InventoryAdjustmentView() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<FAMRecord>({ adjustment_date: "2026-06-06", warehouse_id: 1, reason: "Cycle count", lines: [{ stock_item_id: 1, quantity_in: 1, quantity_out: 0, rate: 100 }] });
  const line = ((draft.lines as FAMRecord[]) || [])[0] || {};
  const mutation = useMutation({ mutationFn: async () => { const adjustment = await famApi.createInventoryAdjustment(draft); return famApi.postInventoryAdjustment(String((adjustment as FAMRecord).id), draft); }, onSuccess: () => { toast({ title: "Adjustment posted" }); queryClient.invalidateQueries({ queryKey: ["fam"] }); } });
  return <Card><CardHeader><CardTitle className="text-base">Stock adjustment</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">{["adjustment_date", "warehouse_id", "reason"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input type={field.includes("date") ? "date" : "text"} value={String(draft[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, [field]: numericFields.has(field) ? Number(event.target.value) : event.target.value }))} /></Field>)}{["stock_item_id", "quantity_in", "quantity_out", "rate"].map((field) => <Field key={field} label={field.replace(/_/g, " ")}><Input value={String(line[field] ?? "")} onChange={(event) => setDraft((current) => ({ ...current, lines: [{ ...line, [field]: Number(event.target.value) }] }))} /></Field>)}<div className="md:col-span-3"><Button onClick={() => mutation.mutate()}>Post adjustment</Button></div></CardContent></Card>;
}

function InventorySummaryView({ kind }: { kind: "summary" | "valuation" | "reorder" | "reports" }) {
  const query = useQuery({ queryKey: ["fam", `inventory-${kind}`], queryFn: () => kind === "valuation" ? famApi.inventoryValuation() : kind === "reorder" ? famApi.inventoryReorderAlerts() : kind === "reports" ? famApi.inventoryReports() : famApi.inventoryStockSummary() });
  const data = (query.data || {}) as FAMRecord;
  const rows = kind === "reports" ? ((data.summary as FAMRecord | undefined)?.items as FAMRecord[] | undefined) || [] : listItems(query.data);
  return <Card><CardHeader><CardTitle className="text-base">{kind === "valuation" ? `Total value ${money(data.total_inventory_value)}` : "Inventory records"}</CardTitle></CardHeader><CardContent className="space-y-3"><State label="inventory report" isLoading={query.isLoading} isError={query.isError} /><DataTable rows={rows} columns={["sku", "item_name", "current_quantity", "average_cost", "stock_value", "is_low_stock"]} /></CardContent></Card>;
}

function InventoryAIView() {
  const [prompt, setPrompt] = useState("Show reorder and dead stock risks.");
  const mutation = useMutation({ mutationFn: () => famApi.inventoryAI({ prompt }) });
  const data = (mutation.data || {}) as FAMRecord;
  const response = (data.response || data.response_json || {}) as FAMRecord;
  return <div className="grid gap-4 lg:grid-cols-[28rem_1fr]"><Card><CardHeader><CardTitle className="text-base">Audited AI request</CardTitle></CardHeader><CardContent className="space-y-3"><Field label="Prompt"><textarea className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm" value={prompt} onChange={(event) => setPrompt(event.target.value)} /></Field><Button onClick={() => mutation.mutate()}>Run inventory AI</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Result</CardTitle></CardHeader><CardContent className="space-y-2 text-sm"><State label="inventory AI" isLoading={mutation.isPending} isError={mutation.isError} /><p>{text(response.message || "No request submitted.")}</p><Badge variant="outline">{text(data.status)}</Badge><p className="text-xs text-muted-foreground">Requests are logged in fam_inventory_ai_logs. Unsupported providers remain labelled as not configured.</p></CardContent></Card></div>;
}

function parseJson(value: unknown) {
  if (!value) return undefined;
  try {
    return typeof value === "string" ? JSON.parse(value) : value;
  } catch {
    return { raw: String(value) };
  }
}

const numericFields = new Set(["financial_year_id", "ledger_id", "ledger_group_id", "voucher_type_id", "debit_amount", "credit_amount", "opening_balance_dr", "opening_balance_cr", "opening_balance", "sequence_order", "numbering_sequence", "cost_center_id", "party_id", "payment_terms_days", "credit_limit", "original_amount", "outstanding_amount", "from_bill_reference_id", "to_bill_reference_id", "allocated_amount", "invoice_id", "receipt_id", "allocation_id", "source_record_id", "roundoff_ledger_id", "bank_account_id", "default_ledger_id", "statement_line_id", "voucher_id", "ledger_entry_id", "matched_amount", "expense_ledger_id", "from_ledger_id", "to_ledger_id", "amount", "cgst_rate", "sgst_rate", "igst_rate", "cess_rate", "default_gst_rate_id", "period_month", "period_year", "threshold_amount", "taxable_value", "vendor_id", "quantity", "quantity_in", "quantity_out", "rate", "gst_rate_id", "gst_amount", "tds_section_id", "tds_amount", "line_total", "subtotal", "discount_total", "gst_total", "grand_total", "employee_id", "total_amount", "default_rate", "section_id", "taxable_amount", "tds_rate", "bank_ledger_id", "purchase_bill_id", "bill_reference_id", "stock_group_id", "unit_id", "default_warehouse_id", "inventory_ledger_id", "cogs_ledger_id", "warehouse_id", "from_warehouse_id", "to_warehouse_id", "stock_item_id", "purchase_rate", "sales_rate", "reorder_level", "min_stock", "max_stock", "parent_group_id", "branch_id", "adjustment_ledger_id"]);

function getListConfig(kind: FAMViewKind) {
  if (kind === "financialYears") return { label: "financial year", query: famApi.financialYears, create: famApi.createFinancialYear, initial: { name: "FY 2027-28", start_date: "2027-04-01", end_date: "2028-03-31", status: "open", is_current: false }, fields: ["name", "start_date", "end_date"], columns: ["name", "start_date", "end_date", "status", "is_current"] };
  if (kind === "ledgerGroups") return { label: "ledger group", query: famApi.ledgerGroups, create: famApi.createLedgerGroup, initial: { group_name: "", group_code: "", nature: "asset", sequence_order: 100 }, fields: ["group_name", "group_code", "nature", "sequence_order"], columns: ["group_code", "group_name", "nature", "system_group", "active"] };
  if (kind === "ledgers") return { label: "ledger", query: famApi.ledgers, create: famApi.createLedger, initial: { ledger_code: "", ledger_name: "", ledger_group_id: 1, nature: "asset", ledger_type: "general" }, fields: ["ledger_code", "ledger_name", "ledger_group_id", "nature", "ledger_type"], columns: ["ledger_code", "ledger_name", "nature", "ledger_type", "current_balance_dr", "current_balance_cr", "active"] };
  if (kind === "voucherTypes") return { label: "voucher type", query: famApi.voucherTypes, create: famApi.createVoucherType, initial: { voucher_type_code: "", voucher_type_name: "", category: "journal", numbering_prefix: "JV", numbering_sequence: 1, auto_numbering: true }, fields: ["voucher_type_code", "voucher_type_name", "category", "numbering_prefix", "numbering_sequence"], columns: ["voucher_type_code", "voucher_type_name", "category", "numbering_prefix", "numbering_sequence", "active"] };
  if (kind === "costCenters") return { label: "cost center", query: famApi.costCenters, create: famApi.createCostCenter, initial: { code: "", name: "" }, fields: ["code", "name"], columns: ["code", "name", "parent_id", "active"] };
  return { label: "branch", query: famApi.branches, create: famApi.createBranch, initial: { branch_code: "", branch_name: "", gstin: "", state_code: "" }, fields: ["branch_code", "branch_name", "gstin", "state_code"], columns: ["branch_code", "branch_name", "gstin", "state_code", "active"] };
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  const id = `fam-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  const control = isValidElement(children)
    ? cloneElement(children as React.ReactElement<{ id?: string; "aria-label"?: string }>, { id, "aria-label": label })
    : children;
  return <div className="space-y-2"><Label htmlFor={id} className="capitalize">{label}</Label>{control}</div>;
}

function AuditRow({ item }: { item: FAMRecord }) {
  return <div className="flex items-center justify-between rounded-md border p-3 text-sm"><span>{text(item.action)} {text(item.record_type)} #{text(item.record_id)}</span><span className="text-xs text-muted-foreground">{text(item.performed_at)}</span></div>;
}

export default function FAMWorkspacePage({ kind }: { kind: FAMViewKind }) {
  const meta = viewMeta[kind];
  const queryClient = useQueryClient();
  let content: React.ReactNode = null;
  if (kind === "dashboard") content = <DashboardView />;
  else if (kind === "settings") content = <SettingsView />;
  else if (kind === "chartOfAccounts") content = <ChartView />;
  else if (kind === "openingBalances") content = <OpeningBalancesView />;
  else if (kind === "voucherNew") content = <VoucherEntryView mode="new" />;
  else if (kind === "journal") content = <VoucherEntryView mode="journal" />;
  else if (kind === "voucherDetail") content = <VoucherEntryView mode="detail" />;
  else if (kind === "vouchers") content = <VouchersView />;
  else if (kind === "dayBook") content = <DayBookView />;
  else if (kind === "ledgerEntries") content = <LedgerEntriesView />;
  else if (kind === "ledgerDetailEntries") content = <LedgerEntriesView detail />;
  else if (kind === "parties") content = <PartiesView />;
  else if (kind === "customers") content = <PartiesView partyType="customer" />;
  else if (kind === "vendors") content = <PartiesView partyType="vendor" />;
  else if (kind === "partyDetail") content = <PartyDetailView />;
  else if (kind === "ar") content = <OutstandingView kind="ar" />;
  else if (kind === "arAging") content = <AgingView kind="ar" />;
  else if (kind === "arOutstanding") content = <OutstandingView kind="ar" />;
  else if (kind === "ap") content = <OutstandingView kind="ap" />;
  else if (kind === "apAging") content = <AgingView kind="ap" />;
  else if (kind === "apOutstanding") content = <OutstandingView kind="ap" />;
  else if (kind === "billReferences") content = <BillReferencesView />;
  else if (kind === "billAllocations") content = <BillAllocationsView />;
  else if (kind === "srmIntegration") content = <SRMIntegrationView />;
  else if (kind === "postingJobs") content = <PostingJobsView />;
  else if (kind === "postingJobDetail") content = <PostingJobDetailView />;
  else if (kind === "postingRules") content = <PostingRulesView />;
  else if (kind === "banking") content = <BankingView />;
  else if (kind === "bankAccounts") content = <BankAccountsView />;
  else if (kind === "paymentModes") content = <PaymentModesView />;
  else if (kind === "bankStatements") content = <BankStatementsView />;
  else if (kind === "bankStatementDetail") content = <BankStatementDetailView />;
  else if (kind === "bankReconciliation") content = <BankReconciliationView />;
  else if (kind === "bankBook") content = <BookView kind="bank" />;
  else if (kind === "cashBook") content = <BookView kind="cash" />;
  else if (kind === "contra") content = <ContraView />;
  else if (kind === "bankCharges") content = <BankChargesView />;
  else if (kind === "gst") content = <GSTHomeView />;
  else if (kind === "gstSettings") content = <GSTSettingsView />;
  else if (kind === "gstRegistrations") content = <GSTMasterView kind="registrations" />;
  else if (kind === "gstRates") content = <GSTMasterView kind="rates" />;
  else if (kind === "gstHsnSac") content = <GSTMasterView kind="hsn" />;
  else if (kind === "gstSalesRegister") content = <GSTRegisterView kind="sales" />;
  else if (kind === "gstPurchaseRegister") content = <GSTRegisterView kind="purchase" />;
  else if (kind === "gstr1") content = <GSTReturnView kind="gstr1" />;
  else if (kind === "gstr3b") content = <GSTReturnView kind="gstr3b" />;
  else if (kind === "gstReconciliation") content = <GSTReconciliationView />;
  else if (kind === "einvoice") content = <ProviderSettingsView kind="einvoice" />;
  else if (kind === "ewaybill") content = <ProviderSettingsView kind="ewaybill" />;
  else if (kind === "purchases") content = <PurchasesHomeView />;
  else if (kind === "purchaseBills") content = <PurchaseBillsView />;
  else if (kind === "purchaseBillNew") content = <PurchaseBillFormView />;
  else if (kind === "purchaseBillDetail") content = <PurchaseBillFormView detail />;
  else if (kind === "expenses") content = <ExpensesView />;
  else if (kind === "expenseNew") content = <ExpenseFormView />;
  else if (kind === "tds") content = <TDSHomeView />;
  else if (kind === "tdsSections") content = <TDSSectionsView />;
  else if (kind === "tdsTransactions") content = <TDSTransactionsView />;
  else if (kind === "tdsPayable") content = <TDSPayableView />;
  else if (kind === "purchaseRegister") content = <PurchaseRegisterView />;
  else if (kind === "expenseRegister") content = <ExpenseRegisterView />;
  else if (kind === "vendorPayments") content = <VendorPaymentsView />;
  else if (kind === "payablesDashboard") content = <PayablesDashboardView />;
  else if (kind === "inventory" || kind === "inventoryDashboard") content = <InventoryDashboardView />;
  else if (kind === "inventoryItems") content = <InventoryItemsView />;
  else if (kind === "inventoryItemDetail") content = <InventoryItemDetailView />;
  else if (kind === "inventoryCategories" || kind === "inventoryStockGroups") content = <InventoryMasterView kind="groups" />;
  else if (kind === "inventoryUnits") content = <InventoryMasterView kind="units" />;
  else if (kind === "inventoryWarehouses") content = <InventoryMasterView kind="warehouses" />;
  else if (kind === "inventoryStockIn") content = <InventoryMovementView mode="in" />;
  else if (kind === "inventoryStockOut") content = <InventoryMovementView mode="out" />;
  else if (kind === "inventoryPurchaseReceipts") content = <InventoryMovementView mode="purchase" />;
  else if (kind === "inventoryDeliveryNotes") content = <InventoryMovementView mode="delivery" />;
  else if (kind === "inventoryStockTransfers") content = <InventoryTransferView />;
  else if (kind === "inventoryStockAdjustments") content = <InventoryAdjustmentView />;
  else if (kind === "inventoryStockSummary") content = <InventorySummaryView kind="summary" />;
  else if (kind === "inventoryItemLedger") content = <InventoryItemDetailView ledger />;
  else if (kind === "inventoryValuation") content = <InventorySummaryView kind="valuation" />;
  else if (kind === "inventoryReorderAlerts") content = <InventorySummaryView kind="reorder" />;
  else if (kind === "inventoryReports") content = <InventorySummaryView kind="reports" />;
  else if (kind === "inventoryAI") content = <InventoryAIView />;
  else if (kind === "audit") content = <AuditView />;
  else content = <ListCreateView kind={kind} />;

  return (
    <section className="space-y-5">
      <PageHeader meta={meta} onRefresh={() => queryClient.invalidateQueries({ queryKey: ["fam"] })} />
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <ShieldCheck className="mr-2 inline h-4 w-4" />FAM is the statutory books engine. SRM remains the operational revenue engine; no SRM invoice screens are duplicated here.
      </div>
      {content}
    </section>
  );
}
