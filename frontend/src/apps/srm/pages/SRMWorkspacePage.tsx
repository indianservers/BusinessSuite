import { useMemo, useState, type ElementType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  CreditCard,
  FileCheck2,
  FileText,
  FolderKanban,
  HandCoins,
  Link2,
  Receipt,
  Search,
  Settings,
  TrendingUp,
  WalletCards,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { srmApi } from "../api";
import type { SRMRecord, SRMViewKind } from "../types";

type SRMQueryEndpoint =
  | "salesOrders"
  | "contracts"
  | "engagements"
  | "billingPlans"
  | "invoiceDrafts"
  | "invoices"
  | "collectionsAging"
  | "leadToCash"
  | "profitability"
  | "reports"
  | "settings";

type ViewMeta = {
  title: string;
  description: string;
  icon: ElementType;
  endpoint?: SRMQueryEndpoint;
};

const viewMeta: Record<SRMViewKind, ViewMeta> = {
  dashboard: {
    title: "SRM Dashboard",
    description: "Commercial health across orders, contracts, billing, collections, and margin.",
    icon: BarChart3,
  },
  salesOrders: {
    title: "Sales Orders",
    description: "Track approved commercial commitments before delivery and billing.",
    icon: Receipt,
    endpoint: "salesOrders",
  },
  contracts: {
    title: "Contracts",
    description: "Review contract status, value, dates, and customer commitments.",
    icon: FileCheck2,
    endpoint: "contracts",
  },
  engagements: {
    title: "Engagements",
    description: "Bridge confirmed revenue to PMS delivery and billing execution.",
    icon: BriefcaseBusiness,
    endpoint: "engagements",
  },
  billingPlans: {
    title: "Billing Plans",
    description: "Monitor fixed fee, milestone, T&M, recurring, and hybrid billing schedules.",
    icon: WalletCards,
    endpoint: "billingPlans",
  },
  invoiceDrafts: {
    title: "Invoice Drafts",
    description: "Validate draft invoices before approval, export, and customer send.",
    icon: FileText,
    endpoint: "invoiceDrafts",
  },
  invoices: {
    title: "Invoices",
    description: "Manage invoice approval, dispatch, payment status, and balances.",
    icon: CreditCard,
    endpoint: "invoices",
  },
  collections: {
    title: "Collections",
    description: "Prioritize outstanding customers, aging buckets, reminders, and escalations.",
    icon: HandCoins,
    endpoint: "collectionsAging",
  },
  revenueRecognition: {
    title: "Revenue Recognition",
    description: "Review lead-to-cash movement and revenue readiness checkpoints.",
    icon: CheckCircle2,
    endpoint: "leadToCash",
  },
  profitability: {
    title: "Profitability",
    description: "Compare order, billing, collection, cost, gross margin, and cash margin.",
    icon: TrendingUp,
    endpoint: "profitability",
  },
  customer360: {
    title: "Customer 360",
    description: "Search a customer or linked CRM/SRM record to see the complete revenue lifecycle.",
    icon: FolderKanban,
  },
  reports: {
    title: "Reports",
    description: "Open SRM operating reports for sales, invoice, aging, margin, and cash.",
    icon: BarChart3,
    endpoint: "reports",
  },
  settings: {
    title: "Settings",
    description: "Control SRM operating settings, approval thresholds, and module configuration.",
    icon: Settings,
    endpoint: "settings",
  },
};

function asList(data: unknown): SRMRecord[] {
  if (Array.isArray(data)) return data as SRMRecord[];
  if (data && typeof data === "object") return [data as SRMRecord];
  return [];
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return Array.isArray(value) ? `${value.length}` : "Linked";
  return String(value).replace(/_/g, " ");
}

function money(value: unknown) {
  const amount = Number(value || 0);
  return amount.toLocaleString(undefined, { maximumFractionDigits: 0, style: "currency", currency: "INR" });
}

function statusTone(status: unknown) {
  const value = String(status || "").toLowerCase();
  if (["approved", "confirmed", "paid", "sent", "healthy", "active", "normal"].includes(value)) return "default";
  if (["pending_approval", "draft", "partially_paid", "queued", "watch"].includes(value)) return "secondary";
  if (["rejected", "cancelled", "overdue", "at_risk", "high"].includes(value)) return "destructive";
  return "outline";
}

function SectionState({ label, isLoading, isError, isEmpty, onRetry }: { label: string; isLoading?: boolean; isError?: boolean; isEmpty?: boolean; onRetry?: () => void }) {
  if (isLoading) return <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">Loading {label}...</div>;
  if (isError) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex flex-col gap-3 p-6 text-sm md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <span>Unable to load {label}.</span>
          </div>
          {onRetry ? <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button> : null}
        </CardContent>
      </Card>
    );
  }
  if (isEmpty) return <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">No {label} found for the current filters.</div>;
  return null;
}

function PageHeader({ meta, isFetching, onRefresh }: { meta: ViewMeta; isFetching?: boolean; onRefresh?: () => void }) {
  const Icon = meta.icon;
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{meta.title}</h1>
          <p className="text-sm text-muted-foreground">{meta.description}</p>
        </div>
      </div>
      {onRefresh ? (
        <Button variant="outline" onClick={onRefresh} disabled={isFetching}>
          Refresh
        </Button>
      ) : null}
    </div>
  );
}

function DashboardView() {
  const query = useQuery({ queryKey: ["srm", "dashboard"], queryFn: () => srmApi.dashboard() });
  const data = (query.data || {}) as SRMRecord;
  const kpis: [string, unknown][] = [
    ["Total sales orders", data.total_sales_orders],
    ["Pending approvals", data.pending_approvals],
    ["Confirmed orders", data.confirmed_sales_orders],
    ["Active contracts", data.active_contracts],
    ["Active engagements", data.active_engagements],
    ["Active billing plans", data.active_billing_plans],
    ["Invoice drafts pending", data.invoice_drafts_pending],
    ["Sent invoices", data.sent_invoices],
    ["Total invoiced", money(data.total_invoiced_value)],
    ["Collected", money(data.total_collected_value)],
    ["Outstanding", money(data.outstanding_value)],
    ["Overdue", money(data.overdue_value)],
  ];
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.dashboard} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <SectionState label="dashboard" isLoading={query.isLoading} isError={query.isError} onRetry={() => query.refetch()} />
      {!query.isLoading && !query.isError ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {kpis.map(([label, value]) => (
              <Card key={label}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium uppercase text-muted-foreground">{label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">{formatValue(value)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <RecordList title="Recent Sales Orders" records={asList(data.recent_sales_orders)} primaryKey="order_number" secondaryKey="title" amountKey="total_amount" />
            <RecordList title="Recent Invoices" records={asList(data.recent_invoices)} primaryKey="invoice_number" secondaryKey="status" amountKey="balance_amount" />
            <RecordList title="Collection Alerts" records={asList(data.collection_alerts)} primaryKey="invoice_number" secondaryKey="overdue_days" amountKey="balance_amount" />
            <TrendCard title="Revenue Trend" records={asList(data.revenue_trend)} />
            <SummaryCard title="Profitability Summary" data={(data.profitability_summary || {}) as SRMRecord} />
            <SummaryCard title="CRM/PMS Linked Activity" data={(data.crm_pms_activity_summary || data.linked_activity_summary || {}) as SRMRecord} />
          </div>
        </>
      ) : null}
    </div>
  );
}

function Customer360View() {
  const [search, setSearch] = useState("");
  const [submitted, setSubmitted] = useState("");
  const params = useMemo(() => {
    const value = submitted.trim();
    if (!value) return {};
    return { q: value };
  }, [submitted]);
  const query = useQuery({
    queryKey: ["srm", "customer360", params],
    queryFn: () => srmApi.customer360(params),
    enabled: Boolean(submitted),
  });
  const data = (query.data || {}) as SRMRecord;
  const hasResults = Boolean(data.matched);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.customer360} isFetching={query.isFetching} onRefresh={submitted ? () => query.refetch() : undefined} />
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Customer 360 search"
              className="pl-9"
              placeholder="Search by customer name, customer ID, CRM deal, sales order, or engagement"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") setSubmitted(search);
              }}
            />
          </div>
          <Button onClick={() => setSubmitted(search)}>Search Customer 360</Button>
        </CardContent>
      </Card>
      {!submitted ? <SectionState label="Customer 360 data" isEmpty /> : null}
      <SectionState label="Customer 360 data" isLoading={query.isLoading} isError={query.isError} onRetry={() => query.refetch()} />
      {submitted && !query.isLoading && !query.isError && !hasResults ? <SectionState label="Customer 360 data" isEmpty /> : null}
      {hasResults ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <MetricCard label="Customer ID" value={data.customer_id} />
            <MetricCard label="Outstanding" value={money(data.outstanding_amount)} />
            <MetricCard label="Sales Orders" value={asList(data.sales_orders).length} />
            <MetricCard label="Invoices" value={asList(data.invoices).length} />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <SummaryCard title="CRM References" data={(data.crm_references || {}) as SRMRecord} />
            <SummaryCard title="Aging" data={(data.aging || {}) as SRMRecord} />
            <RecordList title="Sales Orders" records={asList(data.sales_orders)} primaryKey="order_number" secondaryKey="status" amountKey="total_amount" />
            <RecordList title="Contracts" records={asList(data.contracts)} primaryKey="contract_number" secondaryKey="status" amountKey="contract_value" />
            <RecordList title="Engagements" records={asList(data.engagements)} primaryKey="engagement_number" secondaryKey="status" amountKey="budget_amount" />
            <RecordList title="Billing Plans" records={asList(data.billing_plans)} primaryKey="name" secondaryKey="status" amountKey="total_amount" />
            <RecordList title="Invoices" records={asList(data.invoices)} primaryKey="invoice_number" secondaryKey="status" amountKey="balance_amount" />
            <RecordList title="Receipts" records={asList(data.receipts)} primaryKey="receipt_number" secondaryKey="status" amountKey="amount" />
            <RecordList title="Collection Reminders" records={asList(data.collection_reminders)} primaryKey="reminder_type" secondaryKey="status" amountKey="invoice_id" />
            <RecordList title="PMS Projects" records={asList(data.pms_projects)} primaryKey="project_key" secondaryKey="name" amountKey="budget_amount" />
            <RecordList title="Profitability" records={asList(data.profitability)} primaryKey="status" secondaryKey="collection_status" amountKey="gross_margin" />
            <RecordList title="Timeline / Audit Trail" records={asList(data.timeline || data.audit_trail)} primaryKey="action" secondaryKey="type" amountKey="entity_id" />
          </div>
        </>
      ) : null}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: unknown }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{formatValue(value)}</p>
      </CardContent>
    </Card>
  );
}

function RecordList({ title, records, primaryKey, secondaryKey, amountKey }: { title: string; records: SRMRecord[]; primaryKey: string; secondaryKey: string; amountKey: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {records.length ? records.slice(0, 6).map((record, index) => (
          <div key={`${title}-${record.id || index}`} className="flex items-center justify-between gap-3 rounded-lg border p-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{formatValue(record[primaryKey] || record.name || record.title || `Record ${index + 1}`)}</p>
              <p className="truncate text-xs text-muted-foreground">{formatValue(record[secondaryKey] || record.customer_id || record.created_at)}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {record.status ? <Badge variant={statusTone(record.status)}>{formatValue(record.status)}</Badge> : null}
              <span className="text-sm font-medium">{typeof record[amountKey] === "number" ? money(record[amountKey]) : formatValue(record[amountKey])}</span>
            </div>
          </div>
        )) : <SectionState label={title.toLowerCase()} isEmpty />}
      </CardContent>
    </Card>
  );
}

function SummaryCard({ title, data }: { title: string; data: SRMRecord }) {
  const entries = Object.entries(data || {}).slice(0, 12);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Link2 className="h-4 w-4" />{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length ? (
          <dl className="grid gap-3 sm:grid-cols-2">
            {entries.map(([key, value]) => (
              <div key={key} className="rounded-lg border p-3">
                <dt className="text-xs uppercase text-muted-foreground">{key.replace(/_/g, " ")}</dt>
                <dd className="mt-1 text-sm font-medium">{formatValue(value)}</dd>
              </div>
            ))}
          </dl>
        ) : <SectionState label={title.toLowerCase()} isEmpty />}
      </CardContent>
    </Card>
  );
}

function TrendCard({ title, records }: { title: string; records: SRMRecord[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {records.length ? records.map((record, index) => (
          <div key={`${title}-${index}`} className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border p-3 text-sm">
            <span>{formatValue(record.date || record.recognized_on || record.event_type)}</span>
            <span className="font-medium">{money(record.amount)}</span>
          </div>
        )) : <SectionState label={title.toLowerCase()} isEmpty />}
      </CardContent>
    </Card>
  );
}

function useRevenueAction() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const mutation = useMutation({
    mutationFn: async ({ label, run }: { label: string; run: () => Promise<unknown> }) => {
      setMessage("");
      const result = await run();
      return { label, result };
    },
    onSuccess: ({ label }) => {
      queryClient.invalidateQueries({ queryKey: ["srm"] });
      const text = `${label} completed`;
      setMessage(text);
      toast({ title: text });
    },
    onError: (err: unknown) => {
      const text = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || "Revenue action failed";
      setMessage(text);
      toast({ title: "SRM validation", description: text, variant: "destructive" });
    },
  });
  return { ...mutation, message };
}

function useCanManageRevenue() {
  const user = useAuthStore((state) => state.user);
  const roleValue = typeof user?.role === "object" && user.role ? (user.role as { name?: string }).name : user?.role;
  const role = String(roleValue || "").toLowerCase();
  const isSuperuser = useAuthStore((state) => Boolean(state.user?.is_superuser));
  return isSuperuser || ["admin", "srm_admin", "srm_finance_manager", "srm_collection_executive"].includes(role);
}

function useSrmRole() {
  const user = useAuthStore((state) => state.user);
  const roleValue = typeof user?.role === "object" && user.role ? (user.role as { name?: string }).name : user?.role;
  return {
    role: String(roleValue || "").toLowerCase(),
    isSuperuser: Boolean(user?.is_superuser),
  };
}

function useCanManageSettings() {
  const { role, isSuperuser } = useSrmRole();
  return isSuperuser || ["admin", "srm_admin"].includes(role);
}

function ActionMessage({ message }: { message?: string }) {
  if (!message) return null;
  return <div className="rounded-lg border bg-muted/40 p-3 text-sm" role="status">{message}</div>;
}

function InvoiceDraftsView() {
  const canManage = useCanManageRevenue();
  const query = useQuery({ queryKey: ["srm", "invoiceDrafts"], queryFn: srmApi.invoiceDrafts });
  const action = useRevenueAction();
  const records = asList(query.data);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.invoiceDrafts} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <ActionMessage message={!canManage ? "Read-only revenue access: create, approve, send, and allocation actions are hidden for this role." : action.message} />
      {canManage ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Generate Invoice Drafts</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <Button variant="outline" onClick={() => action.mutate({ label: "Sales order draft", run: () => srmApi.draftInvoiceFromSalesOrder(1) })}>Draft from Sales Order</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Engagement draft", run: () => srmApi.draftInvoiceFromEngagement(2) })}>Draft from Engagement</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Billing milestone draft", run: () => srmApi.draftInvoiceFromBillingMilestone(1) })}>Draft from Billing Milestone</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "PMS milestone draft", run: () => srmApi.draftInvoiceFromPmsMilestone(301) })}>Draft from PMS Milestone</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Timesheet draft", run: () => srmApi.draftInvoiceFromTimesheets({ engagement_id: 2, time_log_ids: [901], hourly_rate: 1000, currency: "INR" }) })}>Draft from Timesheets</Button>
            <Button onClick={() => action.mutate({ label: "Manual invoice draft", run: () => srmApi.manualInvoice({ customer_id: 10, currency: "INR", lines: [{ description: "Manual revenue line", quantity: 1, unit_price: 25000, tax_amount: 4500 }] }) })}>Create Manual Invoice</Button>
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        <RecordList title="Invoice Drafts" records={records} primaryKey="source_type" secondaryKey="status" amountKey="total_amount" />
        <SummaryCard title="Source Evidence" data={{ sales_order: "Supported", engagement: "Supported", billing_milestone: "Duplicate guarded", pms_milestone: "Client approval required", timesheets: "Approved billable logs only", manual: "Source-tagged lines" }} />
      </div>
    </div>
  );
}

function InvoicesView() {
  const canManage = useCanManageRevenue();
  const list = useQuery({ queryKey: ["srm", "invoices"], queryFn: srmApi.invoices });
  const invoiceId = Number(asList(list.data)[0]?.id || 1);
  const detail = useQuery({ queryKey: ["srm", "invoice", invoiceId], queryFn: () => srmApi.invoice(invoiceId), enabled: invoiceId > 0 });
  const action = useRevenueAction();
  const invoice = (detail.data || asList(list.data)[0] || {}) as SRMRecord;
  const pdfHref = `/api/v1/srm/invoices/${invoiceId}/pdf`;
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.invoices} isFetching={list.isFetching || detail.isFetching} onRefresh={() => { list.refetch(); detail.refetch(); }} />
      <ActionMessage message={!canManage ? "Read-only revenue access: invoice approval, send/export, and line edits are hidden for this role." : action.message} />
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Invoice Number" value={invoice.invoice_number} />
        <MetricCard label="Total Amount" value={money(invoice.total_amount)} />
        <MetricCard label="Paid Amount" value={money(invoice.paid_amount)} />
        <MetricCard label="Balance Amount" value={money(invoice.balance_amount)} />
      </div>
      {canManage ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invoice Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => action.mutate({ label: "Invoice approval", run: () => srmApi.approveInvoice(invoiceId) })}>Approve Invoice</Button>
            <Button onClick={() => action.mutate({ label: "Invoice send/export", run: () => srmApi.sendInvoice(invoiceId) })}>Send / Export Invoice</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Invoice line", run: () => srmApi.addInvoiceLine(invoiceId, { description: "Additional line", quantity: 1, unit_price: 5000, tax_amount: 900 }) })}>Add Invoice Line</Button>
            <Button asChild variant="outline"><a href={pdfHref} target="_blank" rel="noreferrer">Download PDF</a></Button>
          </CardContent>
        </Card>
      ) : (
        <Button asChild variant="outline"><a href={pdfHref} target="_blank" rel="noreferrer">Download PDF</a></Button>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <RecordList title="Invoices" records={asList(list.data)} primaryKey="invoice_number" secondaryKey="status" amountKey="balance_amount" />
        <RecordList title="Invoice Lines" records={asList(invoice.lines)} primaryKey="description" secondaryKey="source_type" amountKey="line_total" />
        <RecordList title="Receipt Allocations" records={asList(invoice.allocations || invoice.receipt_allocations)} primaryKey="receipt_number" secondaryKey="status" amountKey="amount" />
        <RecordList title="Audit / History" records={asList(invoice.history || invoice.audit)} primaryKey="to_status" secondaryKey="action" amountKey="actor_user_id" />
      </div>
    </div>
  );
}

function CollectionsView() {
  const canManage = useCanManageRevenue();
  const aging = useQuery({ queryKey: ["srm", "collectionsAging"], queryFn: srmApi.collectionsAging });
  const invoices = useQuery({ queryKey: ["srm", "collectionInvoices"], queryFn: srmApi.invoices });
  const customer = useQuery({ queryKey: ["srm", "customerCollections", 10], queryFn: () => srmApi.customerCollections(10) });
  const action = useRevenueAction();
  const invoiceId = Number(asList(invoices.data)[0]?.id || 1);
  const [receiptId, setReceiptId] = useState(1);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.collections} isFetching={aging.isFetching || invoices.isFetching} onRefresh={() => { aging.refetch(); invoices.refetch(); customer.refetch(); }} />
      <ActionMessage message={!canManage ? "Read-only collection access: receipt, reminder, escalation, and write-off actions are hidden for this role." : action.message} />
      <div className="grid gap-3 md:grid-cols-6">
        {["Not due", "Due", "Overdue", "Escalated", "Collected", "Written-off"].map((label) => <MetricCard key={label} label={label} value={label === "Overdue" ? "Review" : "Tracked"} />)}
      </div>
      {canManage ? (
        <Card>
          <CardHeader><CardTitle className="text-base">Receipts and Collection Actions</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button onClick={() => action.mutate({ label: "Receipt created", run: async () => { const receipt = await srmApi.createReceipt({ customer_id: 10, amount: 100000, payment_method: "bank_transfer" }) as SRMRecord; setReceiptId(Number(receipt.id || 1)); return receipt; } })}>Create Receipt</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Receipt confirmed", run: () => srmApi.confirmReceipt(receiptId) })}>Confirm Receipt</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Partial allocation", run: () => srmApi.allocateReceipt(receiptId, { invoice_id: invoiceId, amount: 50000 }) })}>Allocate Partial Payment</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Full allocation", run: () => srmApi.allocateReceipt(receiptId, { invoice_id: invoiceId, amount: 100000 }) })}>Allocate Full Payment</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Reminder sent", run: () => srmApi.sendCollectionReminder({ customer_id: 10, invoice_id: invoiceId, message: "Payment reminder" }) })}>Send Reminder</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Collection escalated", run: () => srmApi.escalateCollection(invoiceId, { message: "Escalate overdue invoice" }) })}>Escalate</Button>
            <Button variant="outline" onClick={() => action.mutate({ label: "Write-off requested", run: () => srmApi.requestWriteOff(invoiceId, { reason: "Commercial approval required", amount: 10000 }) })}>Request Write-off</Button>
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        <RecordList title="Invoice Aging" records={asList(aging.data)} primaryKey="customer_id" secondaryKey="days_1_30" amountKey="total_outstanding" />
        <RecordList title="Customer Outstanding" records={asList(customer.data && typeof customer.data === "object" ? (customer.data as SRMRecord).invoices : [])} primaryKey="invoice_number" secondaryKey="status" amountKey="balance_amount" />
        <RecordList title="Receipts" records={asList(customer.data && typeof customer.data === "object" ? (customer.data as SRMRecord).receipts : [])} primaryKey="receipt_number" secondaryKey="status" amountKey="unallocated_amount" />
        <RecordList title="Reminder / Escalation / Write-off History" records={asList(customer.data && typeof customer.data === "object" ? (customer.data as SRMRecord).reminders : [])} primaryKey="reminder_type" secondaryKey="status" amountKey="invoice_id" />
      </div>
    </div>
  );
}

function ProfitabilityView() {
  const [filters, setFilters] = useState({ engagement_id: "", project_id: "", customer_id: "", crm_deal_id: "", sales_order_id: "" });
  const query = useQuery({
    queryKey: ["srm", "profitability", filters],
    queryFn: () => srmApi.profitabilityByFilters(Object.fromEntries(Object.entries(filters).filter(([, value]) => value).map(([key, value]) => [key, Number(value)]))),
  });
  const records = asList(query.data);
  const profitability = (records[0] || {}) as SRMRecord;
  const profitabilityValues: SRMRecord = {
    quoted_value: profitability.quoted_value ?? 0,
    sales_order_value: profitability.sales_order_value ?? profitability.order_amount ?? 0,
    contract_value: profitability.contract_value ?? 0,
    billing_plan_value: profitability.billing_plan_value ?? 0,
    delivery_budget: profitability.delivery_budget ?? 0,
    approved_timesheet_cost: profitability.approved_timesheet_cost ?? 0,
    employee_cost: profitability.employee_cost ?? 0,
    gross_margin: profitability.gross_margin ?? profitability.gross_margin_amount ?? 0,
    cash_margin: profitability.cash_margin ?? 0,
    collection_status: profitability.collection_status ?? "not_billed",
  };
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.profitability} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <Card>
        <CardHeader><CardTitle className="text-base">Profitability Filters</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          {Object.keys(filters).map((key) => (
            <Input key={key} aria-label={key.replace(/_/g, " ")} placeholder={key.replace(/_/g, " ")} value={filters[key as keyof typeof filters]} onChange={(event) => setFilters((current) => ({ ...current, [key]: event.target.value }))} />
          ))}
        </CardContent>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <RecordList title="Engagement Profitability" records={records} primaryKey="engagement_id" secondaryKey="collection_status" amountKey="gross_margin" />
        <SummaryCard title="Profitability Values" data={profitabilityValues} />
      </div>
    </div>
  );
}

function RevenueEventsView() {
  const dashboard = useQuery({ queryKey: ["srm", "dashboard", "revenueEvents"], queryFn: srmApi.dashboard });
  const leadToCash = useQuery({ queryKey: ["srm", "leadToCash"], queryFn: srmApi.leadToCash });
  const events = asList((dashboard.data as SRMRecord | undefined)?.revenue_trend);
  return (
    <div className="space-y-5">
      <PageHeader meta={{ ...viewMeta.revenueRecognition, title: "Revenue Events / Revenue Operations", description: "Operational revenue, invoice, milestone, and cash events. This is not presented as a full IFRS 15 automation engine." }} isFetching={dashboard.isFetching || leadToCash.isFetching} onRefresh={() => { dashboard.refetch(); leadToCash.refetch(); }} />
      <div className="grid gap-4 xl:grid-cols-2">
        <RecordList title="Revenue Events" records={events} primaryKey="event_type" secondaryKey="date" amountKey="amount" />
        <SummaryCard title="Invoice / Receipt / Cash Events" data={(leadToCash.data || {}) as SRMRecord} />
        <RecordList title="Milestone Events" records={events.filter((item) => String(item.event_type || "").includes("milestone"))} primaryKey="event_type" secondaryKey="date" amountKey="amount" />
        <RecordList title="Audit-backed Event History" records={events} primaryKey="event_type" secondaryKey="currency" amountKey="amount" />
      </div>
    </div>
  );
}

const reportDefinitions = [
  { key: "sales_order_report", title: "Sales Order Report", description: "Orders by customer, owner, value, and lifecycle status.", filters: "Date range, customer, owner, status" },
  { key: "contract_report", title: "Contract Report", description: "Contract value, active/renewal status, and customer commitments.", filters: "Customer, status, renewal window" },
  { key: "invoice_register", title: "Invoice Register", description: "Invoice numbers, statuses, totals, paid amounts, and balances.", filters: "Invoice date, customer, status" },
  { key: "invoice_aging", title: "Invoice Aging", description: "Invoice-level due, overdue, and paid aging posture.", filters: "Due date, customer, aging bucket" },
  { key: "collection_aging", title: "Collection Aging", description: "Customer aging buckets for collection prioritization.", filters: "Customer, bucket, risk" },
  { key: "customer_outstanding", title: "Customer Outstanding", description: "Open receivables and outstanding customer balances.", filters: "Customer, amount range, owner" },
  { key: "engagement_profitability", title: "Engagement Profitability", description: "Engagement revenue, delivery cost, gross margin, and cash margin.", filters: "Engagement, customer, status" },
  { key: "project_profitability", title: "Project Profitability", description: "PMS-linked project revenue, cost, and margin performance.", filters: "Project, engagement, project manager" },
  { key: "customer_profitability", title: "Customer Profitability", description: "Customer-level revenue, cost, collections, and margin.", filters: "Customer, period, margin status" },
  { key: "lead_to_cash_report", title: "Lead-to-Cash Report", description: "CRM won handoff through order, engagement, invoice, and collection.", filters: "CRM deal, sales order, engagement" },
  { key: "sales_to_delivery_margin", title: "Sales-to-Delivery Margin", description: "Compare quoted/order value against delivery budget and actual cost.", filters: "Sales owner, delivery owner, period" },
  { key: "cash_margin_report", title: "Cash Margin Report", description: "Collected cash less delivery cost and open collection exposure.", filters: "Customer, invoice status, collection status" },
];

function previewRows(value: unknown): SRMRecord[] {
  if (Array.isArray(value)) return value.slice(0, 3) as SRMRecord[];
  if (value && typeof value === "object") {
    const record = value as SRMRecord;
    const nested = Object.values(record).find(Array.isArray);
    if (Array.isArray(nested) && nested.length) return nested.slice(0, 3) as SRMRecord[];
    return [record];
  }
  return [];
}

function ReportsView() {
  const query = useQuery({ queryKey: ["srm", "reports"], queryFn: srmApi.reports });
  const [selected, setSelected] = useState(reportDefinitions[0].key);
  const [message, setMessage] = useState("");
  const data = (query.data || {}) as SRMRecord;
  const selectedDefinition = reportDefinitions.find((item) => item.key === selected) || reportDefinitions[0];
  const rows = previewRows(data[selectedDefinition.key]);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.reports} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <ActionMessage message={message} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <div className="grid gap-3 md:grid-cols-2">
          {reportDefinitions.map((report) => (
            <Card key={report.key} className={selected === report.key ? "border-primary/60" : undefined}>
              <CardHeader>
                <CardTitle className="text-base">{report.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{report.description}</p>
                <div className="rounded-lg border bg-muted/30 p-3 text-xs">
                  <span className="font-medium">Filters:</span> {report.filters}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => { setSelected(report.key); setMessage(`${report.title} preview loaded`); }}>View details</Button>
                  <Button size="sm" variant="secondary" onClick={() => setMessage(`${report.title} export is not yet supported by the current SRM API.`)}>Export</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="xl:sticky xl:top-4 xl:self-start">
          <CardHeader>
            <CardTitle className="text-base">{selectedDefinition.title} Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input aria-label="report customer filter" placeholder="Customer" />
              <Input aria-label="report status filter" placeholder="Status" />
              <Input aria-label="report from date filter" placeholder="From date" />
              <Input aria-label="report to date filter" placeholder="To date" />
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[420px] text-sm">
                <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">Metric</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2 text-right">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {query.isLoading ? (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-muted-foreground">Loading report preview...</td></tr>
                  ) : rows.length ? rows.map((row, index) => (
                    <tr key={`${selected}-${index}`} className="border-t">
                      <td className="px-3 py-2">{formatValue(row.invoice_number || row.order_number || row.contract_number || row.engagement_number || row.customer_id || row.id || selectedDefinition.title)}</td>
                      <td className="px-3 py-2">{formatValue(row.status || row.collection_status || row.margin_status || "available")}</td>
                      <td className="px-3 py-2 text-right">{formatValue(row.total || row.total_amount || row.total_outstanding || row.gross_margin || row.cash_margin_total || row.count || row.value || "-")}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan={3} className="px-3 py-6 text-center text-muted-foreground">No preview data available for this report.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground">Export is shown as a future enhancement unless a backend export endpoint is added.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

const defaultSettings: Record<string, unknown> = {
  invoice_number_prefix: "INV",
  sales_order_number_prefix: "SO",
  contract_number_prefix: "CTR",
  default_payment_terms: "Net 30",
  default_tax_vat_settings: "GST 18%",
  default_billing_plan_rules: "Milestone billing follows approved sales order value.",
  collection_reminder_templates: "Gentle reminder, overdue reminder, escalation notice",
  escalation_thresholds: "7, 15, 30 days overdue",
  write_off_approval_required: true,
  dashboard_visibility_preferences: "Show revenue, collections, and profitability cards",
};

const settingLabels: Record<string, string> = {
  invoice_number_prefix: "invoice numbering prefix",
  sales_order_number_prefix: "sales order numbering prefix",
  contract_number_prefix: "contract numbering prefix",
  default_payment_terms: "default payment terms",
  default_tax_vat_settings: "default tax/VAT settings",
  default_billing_plan_rules: "default billing plan rules",
  collection_reminder_templates: "collection reminder templates",
  escalation_thresholds: "escalation thresholds",
  write_off_approval_required: "write-off approval requirement",
  dashboard_visibility_preferences: "dashboard visibility preferences",
};

function settingsFromRows(rows: SRMRecord[]): Record<string, unknown> {
  return rows.reduce((acc, row) => {
    const key = String(row.key || "");
    if (!key) return acc;
    const value = row.value_json;
    acc[key] = value && typeof value === "object" && !Array.isArray(value) && "value" in value ? (value as SRMRecord).value : value;
    return acc;
  }, { ...defaultSettings });
}

function SettingsView() {
  const canManage = useCanManageSettings();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["srm", "settings"], queryFn: srmApi.settings });
  const [draft, setDraft] = useState<Record<string, unknown>>(defaultSettings);
  const [message, setMessage] = useState("");
  const rows = asList(query.data);
  const settings = { ...settingsFromRows(rows), ...draft };
  const save = useMutation({
    mutationFn: async () => {
      const missing = ["invoice_number_prefix", "sales_order_number_prefix", "contract_number_prefix", "default_payment_terms"].find((key) => !String(settings[key] || "").trim());
      if (missing) throw new Error(`${settingLabels[missing] || missing.replace(/_/g, " ")} is required`);
      await Promise.all(Object.entries(settings).map(([key, value]) => srmApi.updateSetting(key, { value })));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["srm", "settings"] });
      setMessage("SRM settings saved");
      toast({ title: "SRM settings saved" });
    },
    onError: (error: unknown) => {
      const text = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (error as Error)?.message || "Unable to save SRM settings";
      setMessage(text);
      toast({ title: "SRM settings validation", description: text, variant: "destructive" });
    },
  });
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.settings} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <ActionMessage message={!canManage ? "Read-only mode: SRM settings can be viewed but only SRM Admin or srm_settings_manage users can edit." : message} />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Revenue Configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {Object.keys(defaultSettings).map((key) => {
            const label = settingLabels[key] || key.replace(/_/g, " ");
            const value = settings[key];
            if (typeof defaultSettings[key] === "boolean") {
              return (
                <label key={key} className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                  <span className="font-medium capitalize">{label}</span>
                  <input aria-label={label} type="checkbox" disabled={!canManage} checked={Boolean(value)} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.checked }))} />
                </label>
              );
            }
            return (
              <label key={key} className="space-y-2 text-sm">
                <span className="font-medium capitalize">{label}</span>
                <Input aria-label={label} disabled={!canManage} value={String(value || "")} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} />
              </label>
            );
          })}
        </CardContent>
      </Card>
      {canManage ? (
        <Button onClick={() => save.mutate()} disabled={save.isPending}>Save Settings</Button>
      ) : null}
    </div>
  );
}

function GenericRouteView({ kind, meta }: { kind: SRMViewKind; meta: ViewMeta }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["srm", kind],
    queryFn: () => srmApi[meta.endpoint as SRMQueryEndpoint](),
    enabled: Boolean(meta.endpoint),
  });
  const records = asList(query.data);
  const action = useMutation({
    mutationFn: async ({ name, id }: { name: string; id: number }) => {
      const actions: Record<string, (id: number) => Promise<unknown>> = {
        submitSalesOrder: srmApi.submitSalesOrder,
        confirmSalesOrder: srmApi.confirmSalesOrder,
        draftInvoiceFromSalesOrder: srmApi.draftInvoiceFromSalesOrder,
        createPmsProject: srmApi.createPmsProject,
        approveInvoice: srmApi.approveInvoice,
        sendInvoice: srmApi.sendInvoice,
      };
      const fn = actions[name];
      if (!fn) throw new Error(`Unsupported SRM action: ${name}`);
      return fn(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["srm"] });
      toast({ title: "SRM updated" });
    },
    onError: (err: unknown) => {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Action failed";
      toast({ title: "SRM action failed", description: message, variant: "destructive" });
    },
  });

  return (
    <div className="space-y-5">
      <PageHeader meta={meta} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <SectionState label={meta.title} isError={query.isError} onRetry={() => query.refetch()} />
      {!query.isError ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Record</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {query.isLoading ? (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">Loading {meta.title}...</td></tr>
                  ) : records.length ? records.map((record, index) => {
                    const id = Number(record.id || 0);
                    const name = record.title || record.name || record.invoice_number || record.order_number || record.contract_number || record.engagement_number || `Record ${index + 1}`;
                    const amount = record.total_amount || record.contract_value || record.budget_amount || record.outstanding_total || record.invoice_total || record.order_amount || record.total_outstanding;
                    return (
                      <tr key={`${kind}-${id || index}`} className="border-b last:border-0">
                        <td className="px-4 py-3 font-medium">{formatValue(name)}</td>
                        <td className="px-4 py-3">
                          <Badge variant={statusTone(record.status)}>{formatValue(record.status || "live")}</Badge>
                        </td>
                        <td className="px-4 py-3">{formatValue(record.customer_id)}</td>
                        <td className="px-4 py-3">{typeof amount === "number" ? money(amount) : formatValue(amount)}</td>
                        <td className="px-4 py-3">{formatValue(record.updated_at || record.created_at || record.snapshot_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-2">
                            {kind === "salesOrders" && id ? (
                              <>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ name: "submitSalesOrder", id })}>Submit</Button>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ name: "confirmSalesOrder", id })}>Confirm</Button>
                                <Button size="sm" onClick={() => action.mutate({ name: "draftInvoiceFromSalesOrder", id })}>Draft</Button>
                              </>
                            ) : null}
                            {kind === "engagements" && id ? <Button size="sm" onClick={() => action.mutate({ name: "createPmsProject", id })}>Create Project</Button> : null}
                            {kind === "invoices" && id ? (
                              <>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ name: "approveInvoice", id })}>Approve</Button>
                                <Button size="sm" onClick={() => action.mutate({ name: "sendInvoice", id })}>Send</Button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  }) : (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No {meta.title} found for your role.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export default function SRMWorkspacePage({ kind }: { kind: SRMViewKind }) {
  const meta = viewMeta[kind];
  if (kind === "dashboard") return <DashboardView />;
  if (kind === "customer360") return <Customer360View />;
  if (kind === "invoiceDrafts") return <InvoiceDraftsView />;
  if (kind === "invoices") return <InvoicesView />;
  if (kind === "collections") return <CollectionsView />;
  if (kind === "profitability") return <ProfitabilityView />;
  if (kind === "revenueRecognition") return <RevenueEventsView />;
  if (kind === "reports") return <ReportsView />;
  if (kind === "settings") return <SettingsView />;
  return <GenericRouteView kind={kind} meta={meta} />;
}
