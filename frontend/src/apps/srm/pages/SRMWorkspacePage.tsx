import { useMemo, useState, type ElementType, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  Boxes,
  CheckCircle2,
  CreditCard,
  FileCheck2,
  FileText,
  FolderKanban,
  HandCoins,
  Link2,
  Package,
  Plus,
  Receipt,
  RotateCcw,
  Search,
  Settings,
  Sparkles,
  Store,
  Trash2,
  TrendingUp,
  WalletCards,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { inventoryEntryPoints, inventorySourceFeatureCount, mappedInventorySourceFeatureCount } from "@/apps/inventory/sourceCatalog";
import { srmApi } from "../api";
import { syncSrmNow, useSrmRealtimeInvalidation } from "../realtime";
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
    title: "Sales & Inventory Dashboard",
    description: "Commercial and stock health across sales orders, POS, inventory, billing, collections, and margin.",
    icon: BarChart3,
  },
  salesOrders: {
    title: "Sales Orders",
    description: "Track approved commercial commitments before delivery and billing.",
    icon: Receipt,
    endpoint: "salesOrders",
  },
  posSessions: {
    title: "POS Sessions",
    description: "Open, monitor, and audit real POS register sessions from the SRM database.",
    icon: Store,
  },
  cashierClosing: {
    title: "Cashier Closing",
    description: "Close register sessions with expected cash, counted cash, and variance evidence.",
    icon: BarChart3,
  },
  posReturns: {
    title: "POS Returns",
    description: "Create and audit POS returns, refunds, and stock-in reversal movements.",
    icon: RotateCcw,
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
  if (data && typeof data === "object" && Array.isArray((data as { items?: unknown }).items)) return (data as { items: SRMRecord[] }).items;
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

function apiErrorMessage(err: unknown, fallback = "Action failed") {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || fallback;
}

function numericField(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function amountField(value: string, fallback = 0) {
  const parsed = numericField(value);
  return parsed ?? fallback;
}

type InvoiceLineDraft = {
  description: string;
  quantity: string;
  unit_price: string;
  tax_amount: string;
};

function createInvoiceLineDraft(): InvoiceLineDraft {
  return { description: "", quantity: "1", unit_price: "0", tax_amount: "0" };
}

function invoiceLineAmount(line: InvoiceLineDraft) {
  return amountField(line.quantity) * amountField(line.unit_price) + amountField(line.tax_amount);
}

function compactRecord(record: SRMRecord) {
  return Object.fromEntries(Object.entries(record).filter(([, value]) => value !== undefined && value !== "")) as SRMRecord;
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
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => { window.location.href = "/ai/copilot?module_name=srm"; }}>
            <Sparkles className="h-4 w-4" />AI Copilot
          </Button>
          <Button variant="outline" onClick={onRefresh} disabled={isFetching}>
            Refresh
          </Button>
        </div>
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
      <SalesInventoryLaunchpad />
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

const coreLaunchpad = [
  {
    title: "Sales",
    description: "Sales orders, invoices, delivery documents, quotations, returns, and customer commitments.",
    icon: Receipt,
    to: "/srm/sales-orders",
    action: "Open sales",
  },
  {
    title: "POS",
    description: "Counter billing, register sessions, held bills, cashier closing, and POS configuration.",
    icon: Store,
    to: "/srm/pos",
    action: "Open POS",
  },
  {
    title: "Inventory",
    description: "Products, stock, warehouses, purchases, transfers, manufacturing, batches, and reports.",
    icon: Package,
    to: "/srm/inventory/dashboard",
    action: "Open inventory",
  },
  {
    title: "Source Map",
    description: `${mappedInventorySourceFeatureCount}/${inventorySourceFeatureCount} cloned Vyapara ERP sales, POS, and inventory entry points are mapped into Sales & Inventory.`,
    icon: Boxes,
    to: "/srm/inventory/source",
    action: "View mapped features",
  },
];

function SalesInventoryLaunchpad() {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sales, Inventory & POS Operations</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {coreLaunchpad.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.title} to={item.to} className="rounded-lg border p-4 transition hover:border-primary/60 hover:bg-muted/60">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </span>
                <span className="mt-3 block text-sm font-semibold">{item.title}</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">{item.description}</span>
                <span className="mt-3 block text-xs font-semibold text-primary">{item.action}</span>
              </Link>
            );
          })}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Entry Points</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          {inventoryEntryPoints.map((entry) => {
            const Icon = entry.icon;
            return (
              <Button key={entry.to} asChild variant="outline" className="h-auto justify-start gap-3 px-3 py-2 text-left">
                <Link to={entry.to}>
                  <Icon className="h-4 w-4" />
                  <span>
                    <span className="block text-sm font-medium">{entry.label}</span>
                    <span className="block text-xs font-normal text-muted-foreground">{entry.description}</span>
                  </span>
                </Link>
              </Button>
            );
          })}
        </CardContent>
      </Card>
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

function SourceDraftControls({ action }: { action: ReturnType<typeof useRevenueAction> }) {
  const [source, setSource] = useState({
    salesOrderId: "",
    engagementId: "",
    billingMilestoneId: "",
    pmsMilestoneId: "",
    timesheetEngagementId: "",
    timeLogIds: "",
    hourlyRate: "1000",
    currency: "INR",
  });
  const update = (key: keyof typeof source, value: string) => setSource((current) => ({ ...current, [key]: value }));
  const timeLogIds = source.timeLogIds.split(",").map((value) => Number(value.trim())).filter((value) => Number.isFinite(value) && value > 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Generate Invoice From Source</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Sales order ID</span>
            <Input inputMode="numeric" value={source.salesOrderId} onChange={(event) => update("salesOrderId", event.target.value)} />
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Engagement ID</span>
            <Input inputMode="numeric" value={source.engagementId} onChange={(event) => update("engagementId", event.target.value)} />
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Billing milestone ID</span>
            <Input inputMode="numeric" value={source.billingMilestoneId} onChange={(event) => update("billingMilestoneId", event.target.value)} />
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">PMS milestone ID</span>
            <Input inputMode="numeric" value={source.pmsMilestoneId} onChange={(event) => update("pmsMilestoneId", event.target.value)} />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Timesheet engagement ID</span>
            <Input inputMode="numeric" value={source.timesheetEngagementId} onChange={(event) => update("timesheetEngagementId", event.target.value)} />
          </label>
          <label className="space-y-2 text-sm md:col-span-2">
            <span className="font-medium">Time log IDs</span>
            <Input placeholder="901, 902, 903" value={source.timeLogIds} onChange={(event) => update("timeLogIds", event.target.value)} />
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Hourly rate</span>
            <Input inputMode="decimal" value={source.hourlyRate} onChange={(event) => update("hourlyRate", event.target.value)} />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={action.isPending || !numericField(source.salesOrderId)} onClick={() => action.mutate({ label: "Sales order draft", run: () => srmApi.draftInvoiceFromSalesOrder(Number(source.salesOrderId)) })}>Draft from Sales Order</Button>
          <Button variant="outline" disabled={action.isPending || !numericField(source.engagementId)} onClick={() => action.mutate({ label: "Engagement draft", run: () => srmApi.draftInvoiceFromEngagement(Number(source.engagementId)) })}>Draft from Engagement</Button>
          <Button variant="outline" disabled={action.isPending || !numericField(source.billingMilestoneId)} onClick={() => action.mutate({ label: "Billing milestone draft", run: () => srmApi.draftInvoiceFromBillingMilestone(Number(source.billingMilestoneId)) })}>Draft from Billing Milestone</Button>
          <Button variant="outline" disabled={action.isPending || !numericField(source.pmsMilestoneId)} onClick={() => action.mutate({ label: "PMS milestone draft", run: () => srmApi.draftInvoiceFromPmsMilestone(Number(source.pmsMilestoneId)) })}>Draft from PMS Milestone</Button>
          <Button
            variant="outline"
            disabled={action.isPending || !numericField(source.timesheetEngagementId) || !timeLogIds.length}
            onClick={() => action.mutate({
              label: "Timesheet draft",
              run: () => srmApi.draftInvoiceFromTimesheets({
                engagement_id: Number(source.timesheetEngagementId),
                time_log_ids: timeLogIds,
                hourly_rate: amountField(source.hourlyRate),
                currency: source.currency,
              }),
            })}
          >
            Draft from Timesheets
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ManualInvoiceComposer({ onCreated }: { onCreated?: () => void }) {
  const [form, setForm] = useState({
    template: "services",
    customer_id: "",
    sales_order_id: "",
    engagement_id: "",
    currency: "INR",
    issue_date: "",
    due_date: "",
    terms: "Due on receipt",
    notes: "",
  });
  const [lines, setLines] = useState<InvoiceLineDraft[]>([createInvoiceLineDraft()]);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const updateLine = (index: number, key: keyof InvoiceLineDraft, value: string) => setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line));
  const preparedLines = lines
    .filter((line) => line.description.trim())
    .map((line) => ({
      description: line.description.trim(),
      quantity: amountField(line.quantity, 1),
      unit_price: amountField(line.unit_price),
      tax_amount: amountField(line.tax_amount),
      line_total: invoiceLineAmount(line),
    }));
  const subtotal = preparedLines.reduce((sum, line) => sum + Number(line.quantity) * Number(line.unit_price), 0);
  const tax = preparedLines.reduce((sum, line) => sum + Number(line.tax_amount), 0);
  const total = subtotal + tax;
  const create = useMutation({
    mutationFn: () => {
      if (!numericField(form.customer_id) && !numericField(form.sales_order_id) && !numericField(form.engagement_id)) {
        throw new Error("Enter a customer, sales order, or engagement ID before generating the invoice.");
      }
      if (!preparedLines.length) throw new Error("Add at least one invoice line with a description.");
      return srmApi.manualInvoice(compactRecord({
        customer_id: numericField(form.customer_id),
        sales_order_id: numericField(form.sales_order_id),
        engagement_id: numericField(form.engagement_id),
        currency: form.currency,
        issue_date: form.issue_date,
        due_date: form.due_date,
        lines: preparedLines,
      }));
    },
    onSuccess: () => {
      const text = "Manual invoice created from entered details";
      setMessage(text);
      toast({ title: text });
      queryClient.invalidateQueries({ queryKey: ["srm"] });
      onCreated?.();
    },
    onError: (err: unknown) => {
      const text = apiErrorMessage(err, "Invoice creation failed");
      setMessage(text);
      toast({ title: "Invoice creation failed", description: text, variant: "destructive" });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invoice Template and Preview</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={(event: FormEvent) => { event.preventDefault(); create.mutate(); }}>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Template</span>
              <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={form.template} onChange={(event) => update("template", event.target.value)}>
                <option value="services">Services invoice</option>
                <option value="milestone">Milestone invoice</option>
                <option value="time_materials">Time and materials</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Customer ID</span>
              <Input inputMode="numeric" value={form.customer_id} onChange={(event) => update("customer_id", event.target.value)} />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Sales order ID</span>
              <Input inputMode="numeric" value={form.sales_order_id} onChange={(event) => update("sales_order_id", event.target.value)} />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Engagement ID</span>
              <Input inputMode="numeric" value={form.engagement_id} onChange={(event) => update("engagement_id", event.target.value)} />
            </label>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Currency</span>
              <Input value={form.currency} onChange={(event) => update("currency", event.target.value.toUpperCase())} />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Issue date</span>
              <Input type="date" value={form.issue_date} onChange={(event) => update("issue_date", event.target.value)} />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Due date</span>
              <Input type="date" value={form.due_date} onChange={(event) => update("due_date", event.target.value)} />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Terms</span>
              <Input value={form.terms} onChange={(event) => update("terms", event.target.value)} />
            </label>
          </div>
          <div className="space-y-2">
            {lines.map((line, index) => (
              <div key={index} className="grid gap-2 rounded-lg border p-3 md:grid-cols-[minmax(180px,1fr)_110px_130px_130px_auto]">
                <Input aria-label="Line description" placeholder="Line description" value={line.description} onChange={(event) => updateLine(index, "description", event.target.value)} />
                <Input aria-label="Quantity" inputMode="decimal" value={line.quantity} onChange={(event) => updateLine(index, "quantity", event.target.value)} />
                <Input aria-label="Unit price" inputMode="decimal" value={line.unit_price} onChange={(event) => updateLine(index, "unit_price", event.target.value)} />
                <Input aria-label="Tax amount" inputMode="decimal" value={line.tax_amount} onChange={(event) => updateLine(index, "tax_amount", event.target.value)} />
                <Button type="button" variant="outline" size="icon" disabled={lines.length === 1} onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))} aria-label="Remove invoice line">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={() => setLines((current) => [...current, createInvoiceLineDraft()])}>
              <Plus className="h-4 w-4" />Add Line
            </Button>
          </div>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Notes</span>
            <textarea className="min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.notes} onChange={(event) => update("notes", event.target.value)} />
          </label>
          <div className="rounded-lg border bg-muted/30 p-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-sm font-semibold">{form.template.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</p>
                <p className="text-xs text-muted-foreground">Customer {form.customer_id || "-"} · Sales order {form.sales_order_id || "-"} · Engagement {form.engagement_id || "-"}</p>
                <p className="text-xs text-muted-foreground">Issue {form.issue_date || "-"} · Due {form.due_date || "-"}</p>
              </div>
              <div className="text-right">
                <p className="text-xs uppercase text-muted-foreground">Preview total</p>
                <p className="text-2xl font-semibold">{money(total)}</p>
              </div>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-left text-xs uppercase text-muted-foreground">
                  <tr><th className="py-2">Description</th><th>Qty</th><th>Unit</th><th>Tax</th><th className="text-right">Line total</th></tr>
                </thead>
                <tbody>
                  {preparedLines.length ? preparedLines.map((line, index) => (
                    <tr key={`${line.description}-${index}`} className="border-t">
                      <td className="py-2">{line.description}</td>
                      <td>{line.quantity}</td>
                      <td>{money(line.unit_price)}</td>
                      <td>{money(line.tax_amount)}</td>
                      <td className="text-right">{money(line.line_total)}</td>
                    </tr>
                  )) : <tr><td colSpan={5} className="py-3 text-center text-muted-foreground">Add line items to preview invoice totals.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="mt-3 grid gap-1 text-sm sm:ml-auto sm:w-72">
              <div className="flex justify-between"><span>Subtotal</span><span>{money(subtotal)}</span></div>
              <div className="flex justify-between"><span>Tax</span><span>{money(tax)}</span></div>
              <div className="flex justify-between font-semibold"><span>Total</span><span>{money(total)}</span></div>
              <p className="pt-2 text-xs text-muted-foreground">{form.terms}</p>
              {form.notes ? <p className="text-xs text-muted-foreground">{form.notes}</p> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating..." : "Create Invoice"}</Button>
            <ActionMessage message={message} />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function InvoiceLineEditor({ invoiceId, onSaved }: { invoiceId: number; onSaved?: () => void }) {
  const [line, setLine] = useState<InvoiceLineDraft>(createInvoiceLineDraft());
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: () => {
      if (!invoiceId) throw new Error("Select an invoice before adding a line.");
      if (!line.description.trim()) throw new Error("Line description is required.");
      return srmApi.addInvoiceLine(invoiceId, {
        description: line.description.trim(),
        quantity: amountField(line.quantity, 1),
        unit_price: amountField(line.unit_price),
        tax_amount: amountField(line.tax_amount),
        line_total: invoiceLineAmount(line),
      });
    },
    onSuccess: () => {
      const text = "Invoice line added";
      setMessage(text);
      toast({ title: text });
      queryClient.invalidateQueries({ queryKey: ["srm"] });
      setLine(createInvoiceLineDraft());
      onSaved?.();
    },
    onError: (err: unknown) => {
      const text = apiErrorMessage(err, "Unable to add invoice line");
      setMessage(text);
      toast({ title: "Invoice line failed", description: text, variant: "destructive" });
    },
  });

  return (
    <form className="space-y-3 rounded-lg border p-3" onSubmit={(event: FormEvent) => { event.preventDefault(); save.mutate(); }}>
      <div className="grid gap-2 md:grid-cols-[minmax(180px,1fr)_110px_130px_130px_auto]">
        <Input placeholder="Line description" value={line.description} onChange={(event) => setLine((current) => ({ ...current, description: event.target.value }))} />
        <Input aria-label="Quantity" inputMode="decimal" value={line.quantity} onChange={(event) => setLine((current) => ({ ...current, quantity: event.target.value }))} />
        <Input aria-label="Unit price" inputMode="decimal" value={line.unit_price} onChange={(event) => setLine((current) => ({ ...current, unit_price: event.target.value }))} />
        <Input aria-label="Tax amount" inputMode="decimal" value={line.tax_amount} onChange={(event) => setLine((current) => ({ ...current, tax_amount: event.target.value }))} />
        <Button type="submit" disabled={save.isPending || !invoiceId}>{save.isPending ? "Adding..." : "Add Line"}</Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">Line preview total: {money(invoiceLineAmount(line))}</span>
        <ActionMessage message={message} />
      </div>
    </form>
  );
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
        <>
          <SourceDraftControls action={action} />
          <ManualInvoiceComposer onCreated={() => query.refetch()} />
        </>
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
  const accountingStatus = (invoice.accounting_status || {}) as SRMRecord;
  const pdfHref = `/api/v1/srm/invoices/${invoiceId}/pdf`;
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.invoices} isFetching={list.isFetching || detail.isFetching} onRefresh={() => { list.refetch(); detail.refetch(); }} />
      <ActionMessage message={!canManage ? "Read-only revenue access: invoice approval, send/export, and line edits are hidden for this role." : action.message} />
      {canManage ? <ManualInvoiceComposer onCreated={() => { list.refetch(); detail.refetch(); }} /> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Invoice Number" value={invoice.invoice_number} />
        <MetricCard label="Total Amount" value={money(invoice.total_amount)} />
        <MetricCard label="Paid Amount" value={money(invoice.paid_amount)} />
        <MetricCard label="Balance Amount" value={money(invoice.balance_amount)} />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">FAM Accounting Status</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <MetricCard label="Posting Status" value={formatValue(accountingStatus.status || "not_posted")} />
          <MetricCard label="FAM Voucher" value={accountingStatus.voucher_id ? `#${accountingStatus.voucher_id}` : "Not posted"} />
          <MetricCard label="Posting Job" value={accountingStatus.job_id ? `#${accountingStatus.job_id}` : "Pending"} />
          <MetricCard label="FAM Ledger Link" value={asList(accountingStatus.mappings).length ? "Mapped" : "Not mapped"} />
        </CardContent>
      </Card>
      {canManage ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invoice Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={action.isPending || !invoiceId} onClick={() => action.mutate({ label: "Invoice approval", run: () => srmApi.approveInvoice(invoiceId) })}>Approve Invoice</Button>
              <Button disabled={action.isPending || !invoiceId} onClick={() => action.mutate({ label: "Invoice send/export", run: () => srmApi.sendInvoice(invoiceId) })}>Send / Export Invoice</Button>
              <Button asChild variant="outline"><a href={pdfHref} target="_blank" rel="noreferrer">Download PDF</a></Button>
            </div>
            <InvoiceLineEditor invoiceId={invoiceId} onSaved={() => detail.refetch()} />
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
        <RecordList title="Customer Outstanding and FAM Links" records={asList(customer.data && typeof customer.data === "object" ? (customer.data as SRMRecord).invoices : [])} primaryKey="invoice_number" secondaryKey="status" amountKey="balance_amount" />
        <RecordList title="Receipts and FAM Accounting Status" records={asList(customer.data && typeof customer.data === "object" ? (customer.data as SRMRecord).receipts : [])} primaryKey="receipt_number" secondaryKey="status" amountKey="unallocated_amount" />
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

function reportRows(value: unknown): SRMRecord[] {
  if (Array.isArray(value)) return value as SRMRecord[];
  if (value && typeof value === "object") {
    const record = value as SRMRecord;
    const nested = Object.values(record).find(Array.isArray);
    if (Array.isArray(nested)) return nested as SRMRecord[];
    return [record];
  }
  return [];
}

function exportReportCsv(title: string, rows: SRMRecord[]) {
  if (!rows.length) return false;
  const columns = Array.from(rows.reduce((set, row) => {
    Object.keys(row).forEach((key) => set.add(key));
    return set;
  }, new Set<string>()));
  const csv = [
    columns.map(csvCell).join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "srm-report"}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return true;
}

function csvCell(value: unknown) {
  const text = value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function ReportsView() {
  const query = useQuery({ queryKey: ["srm", "reports"], queryFn: srmApi.reports });
  const [selected, setSelected] = useState(reportDefinitions[0].key);
  const [message, setMessage] = useState("");
  const data = (query.data || {}) as SRMRecord;
  const selectedDefinition = reportDefinitions.find((item) => item.key === selected) || reportDefinitions[0];
  const rows = previewRows(data[selectedDefinition.key]);
  const exportRows = reportRows(data[selectedDefinition.key]);
  const exportSelected = (report = selectedDefinition) => {
    const availableRows = reportRows(data[report.key]);
    if (exportReportCsv(report.title, availableRows)) {
      setMessage(`${report.title} CSV exported with ${availableRows.length} row${availableRows.length === 1 ? "" : "s"}.`);
    } else {
      setMessage(`${report.title} has no rows available to export.`);
    }
  };
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
                  <Button size="sm" variant="secondary" disabled={query.isLoading} onClick={() => exportSelected(report)}>Export</Button>
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
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>{exportRows.length ? `${exportRows.length} row${exportRows.length === 1 ? "" : "s"} available for CSV export.` : "No rows available for CSV export."}</span>
              <Button size="sm" variant="outline" disabled={query.isLoading || !exportRows.length} onClick={() => exportSelected()}>Export CSV</Button>
            </div>
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

function POSSessionView() {
  const queryClient = useQueryClient();
  const canManage = useCanManageRevenue();
  const [openingCash, setOpeningCash] = useState("5000");
  const [cashAmount, setCashAmount] = useState("");
  const [cashReason, setCashReason] = useState("");
  const [movementType, setMovementType] = useState("cash_in");
  const query = useQuery({ queryKey: ["srm", "posSessions"], queryFn: srmApi.posSessions });
  const active = useQuery({ queryKey: ["srm", "activePosSession"], queryFn: srmApi.activePosSession });
  const activeSession = ((active.data as SRMRecord | undefined)?.session || null) as SRMRecord | null;
  const open = useMutation({
    mutationFn: () => srmApi.openPosSession({ branch: "Main Branch", register_name: "Main POS Register", opening_cash: amountField(openingCash) }),
    onSuccess: () => {
      toast({ title: "POS session opened" });
      queryClient.invalidateQueries({ queryKey: ["srm"] });
    },
  });
  const movement = useMutation({
    mutationFn: () => srmApi.createPosCashMovement({ session_id: activeSession?.id, movement_type: movementType, amount: amountField(cashAmount), reason: cashReason }),
    onSuccess: () => {
      setCashAmount("");
      setCashReason("");
      toast({ title: "Cash movement saved" });
      queryClient.invalidateQueries({ queryKey: ["srm"] });
    },
  });
  const rows = asList(query.data);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.posSessions} isFetching={query.isFetching || active.isFetching} onRefresh={() => { query.refetch(); active.refetch(); }} />
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Active session" value={activeSession ? formatValue(activeSession.session_number) : "None"} />
        <MetricCard label="Expected cash" value={money((active.data as SRMRecord | undefined)?.expected_cash)} />
        <MetricCard label="Cash sales" value={money((active.data as SRMRecord | undefined)?.cash_sales)} />
        <MetricCard label="Sales count" value={formatValue((active.data as SRMRecord | undefined)?.sales_count || 0)} />
      </div>
      {canManage ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">Open register session</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-[1fr_auto]">
              <Input value={openingCash} onChange={(event) => setOpeningCash(event.target.value)} placeholder="Opening cash" />
              <Button onClick={() => open.mutate()} disabled={open.isPending || Boolean(activeSession)}>Open Session</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Cash movement</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-[9rem_1fr_1fr_auto]">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={movementType} onChange={(event) => setMovementType(event.target.value)}>
                <option value="cash_in">Cash In</option>
                <option value="cash_out">Cash Out</option>
              </select>
              <Input value={cashAmount} onChange={(event) => setCashAmount(event.target.value)} placeholder="Amount" />
              <Input value={cashReason} onChange={(event) => setCashReason(event.target.value)} placeholder="Reason" />
              <Button onClick={() => movement.mutate()} disabled={movement.isPending || !activeSession || !amountField(cashAmount)}>Save</Button>
            </CardContent>
          </Card>
        </div>
      ) : null}
      <SectionState label="POS sessions" isLoading={query.isLoading} isError={query.isError} onRetry={() => query.refetch()} />
      {!query.isError ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                  <tr><th className="px-4 py-3">Session</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Register</th><th className="px-4 py-3">Opening</th><th className="px-4 py-3">Cash Sales</th><th className="px-4 py-3">Expected</th><th className="px-4 py-3">Variance</th></tr>
                </thead>
                <tbody>
                  {rows.length ? rows.map((row, index) => {
                    const session = (row.session || {}) as SRMRecord;
                    const closing = (row.closing || {}) as SRMRecord;
                    return (
                      <tr key={String(session.id || index)} className="border-b last:border-0">
                        <td className="px-4 py-3 font-medium">{formatValue(session.session_number)}</td>
                        <td className="px-4 py-3"><Badge variant={statusTone(session.status)}>{formatValue(session.status)}</Badge></td>
                        <td className="px-4 py-3">{formatValue(session.register_name)}</td>
                        <td className="px-4 py-3">{money(session.opening_cash)}</td>
                        <td className="px-4 py-3">{money(row.cash_sales)}</td>
                        <td className="px-4 py-3">{money(row.expected_cash)}</td>
                        <td className="px-4 py-3">{closing.variance !== undefined ? money(closing.variance) : "-"}</td>
                      </tr>
                    );
                  }) : <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">No POS sessions found.</td></tr>}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function CashierClosingView() {
  const queryClient = useQueryClient();
  const canManage = useCanManageRevenue();
  const [countedCash, setCountedCash] = useState("");
  const [notes, setNotes] = useState("");
  const active = useQuery({ queryKey: ["srm", "activePosSession"], queryFn: srmApi.activePosSession });
  const activeData = (active.data || {}) as SRMRecord;
  const session = (activeData.session || null) as SRMRecord | null;
  const close = useMutation({
    mutationFn: () => srmApi.closePosSession({ session_id: session?.id, counted_cash: amountField(countedCash), notes }),
    onSuccess: () => {
      toast({ title: "Cashier closing posted" });
      queryClient.invalidateQueries({ queryKey: ["srm"] });
    },
  });
  const expected = Number(activeData.expected_cash || 0);
  const counted = amountField(countedCash);
  return (
    <div className="space-y-5">
      <PageHeader meta={viewMeta.cashierClosing} isFetching={active.isFetching} onRefresh={() => active.refetch()} />
      <SectionState label="active POS session" isLoading={active.isLoading} isError={active.isError} onRetry={() => active.refetch()} />
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Session" value={session ? session.session_number : "No open session"} />
        <MetricCard label="Opening cash" value={money(session?.opening_cash)} />
        <MetricCard label="Expected cash" value={money(expected)} />
        <MetricCard label="Variance preview" value={money(counted - expected)} />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Close active session</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input value={countedCash} onChange={(event) => setCountedCash(event.target.value)} placeholder="Counted cash" />
          <Input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Closing notes" />
          <Button onClick={() => close.mutate()} disabled={!canManage || close.isPending || !session || !countedCash}>Close Session</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Closing evidence</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <MetricCard label="Cash sales" value={money(activeData.cash_sales)} />
          <MetricCard label="Cash in" value={money(activeData.cash_in)} />
          <MetricCard label="Cash out" value={money(activeData.cash_out)} />
          <MetricCard label="Sales count" value={formatValue(activeData.sales_count || 0)} />
        </CardContent>
      </Card>
    </div>
  );
}

function POSReturnsView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["srm", "posReturns"], queryFn: srmApi.posReturns });
  const [draft, setDraft] = useState({
    order_number: "",
    sales_order_line_id: "",
    product_id: "",
    quantity: "1",
    unit_price: "0",
    tax_amount: "0",
    refund_method: "cash",
    reason: "",
  });
  const mutation = useMutation({
    mutationFn: () => srmApi.createPosReturn({
      order_number: draft.order_number,
      refund_method: draft.refund_method,
      reason: draft.reason,
      lines: [{
        sales_order_line_id: amountField(draft.sales_order_line_id),
        product_id: amountField(draft.product_id),
        quantity: amountField(draft.quantity, 1),
        unit_price: amountField(draft.unit_price),
        tax_amount: amountField(draft.tax_amount),
        restock: true,
        condition: "sellable",
      }],
    }),
    onSuccess: async (result) => {
      toast({ title: "POS return created" });
      setDraft((current) => ({ ...current, sales_order_line_id: "", product_id: "", quantity: "1", tax_amount: "0", reason: "" }));
      await syncSrmNow(queryClient, {
        type: "pos_return_completed",
        source: "srm-pos-returns",
        ids: { return_id: Number((result as SRMRecord | undefined)?.id || 0) || undefined },
      });
    },
    onError: (error) => toast({ title: "Return failed", description: apiErrorMessage(error), variant: "destructive" }),
  });
  const rows = asList(query.data);
  return (
    <div className="space-y-4">
      <PageHeader meta={viewMeta.posReturns} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <div className="grid gap-4 lg:grid-cols-[24rem_1fr]">
        <Card>
          <CardHeader><CardTitle className="text-base">Create return</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <label className="space-y-2 text-sm"><span className="font-medium">POS order number</span><Input value={draft.order_number} onChange={(event) => setDraft((current) => ({ ...current, order_number: event.target.value }))} placeholder="POS-00001" /></label>
            <label className="space-y-2 text-sm"><span className="font-medium">Sales order line ID</span><Input value={draft.sales_order_line_id} onChange={(event) => setDraft((current) => ({ ...current, sales_order_line_id: event.target.value }))} /></label>
            <label className="space-y-2 text-sm"><span className="font-medium">Product ID</span><Input value={draft.product_id} onChange={(event) => setDraft((current) => ({ ...current, product_id: event.target.value }))} /></label>
            <div className="grid grid-cols-3 gap-2">
              <label className="space-y-2 text-sm"><span className="font-medium">Qty</span><Input value={draft.quantity} onChange={(event) => setDraft((current) => ({ ...current, quantity: event.target.value }))} /></label>
              <label className="space-y-2 text-sm"><span className="font-medium">Rate</span><Input value={draft.unit_price} onChange={(event) => setDraft((current) => ({ ...current, unit_price: event.target.value }))} /></label>
              <label className="space-y-2 text-sm"><span className="font-medium">Tax</span><Input value={draft.tax_amount} onChange={(event) => setDraft((current) => ({ ...current, tax_amount: event.target.value }))} /></label>
            </div>
            <label className="space-y-2 text-sm"><span className="font-medium">Refund method</span><Input value={draft.refund_method} onChange={(event) => setDraft((current) => ({ ...current, refund_method: event.target.value }))} /></label>
            <label className="space-y-2 text-sm"><span className="font-medium">Reason</span><Input value={draft.reason} onChange={(event) => setDraft((current) => ({ ...current, reason: event.target.value }))} /></label>
            <Button className="w-full" onClick={() => mutation.mutate()} disabled={!draft.order_number || mutation.isPending}>Create return</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Return register</CardTitle></CardHeader>
          <CardContent>
            <SectionState label="POS returns" isLoading={query.isLoading} isError={query.isError} isEmpty={!query.isLoading && !rows.length} onRetry={() => query.refetch()} />
            {rows.length ? (
              <div className="overflow-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      {["Return #", "Status", "Refund", "Amount", "Created"].map((head) => <th key={head} className="px-3 py-2 font-medium">{head}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={String(row.id)} className="border-t">
                        <td className="px-3 py-2 font-medium">{formatValue(row.return_number)}</td>
                        <td className="px-3 py-2"><Badge variant={statusTone(row.status)}>{formatValue(row.status)}</Badge></td>
                        <td className="px-3 py-2">{formatValue(row.refund_method)} / {formatValue(row.refund_status)}</td>
                        <td className="px-3 py-2">{money(row.refund_amount)}</td>
                        <td className="px-3 py-2">{formatValue(row.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CommercialCreateCard({ kind, onSaved }: { kind: SRMViewKind; onSaved?: () => void }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [salesOrder, setSalesOrder] = useState({
    title: "",
    customer_id: "",
    currency: "INR",
    expected_start_date: "",
    expected_end_date: "",
    terms: "",
    product_id: "",
    line_description: "",
    quantity: "1",
    unit_price: "0",
    tax_amount: "0",
  });
  const [contract, setContract] = useState({
    title: "",
    sales_order_id: "",
    customer_id: "",
    contract_type: "services",
    effective_date: "",
    expiry_date: "",
    contract_value: "0",
    currency: "INR",
    terms: "",
  });
  const [engagement, setEngagement] = useState({
    name: "",
    sales_order_id: "",
    contract_id: "",
    customer_id: "",
    billing_type: "fixed_fee",
    budget_amount: "0",
    currency: "INR",
    planned_start_date: "",
    planned_end_date: "",
  });
  const [billingPlan, setBillingPlan] = useState({
    engagement_id: "",
    name: "",
    billing_type: "fixed_fee",
    currency: "INR",
    total_amount: "0",
    recurrence_rule: "",
    milestone_name: "",
    milestone_due_date: "",
    milestone_amount: "0",
  });
  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === "salesOrders") {
        if (!salesOrder.title.trim()) throw new Error("Sales order title is required.");
        const quantity = amountField(salesOrder.quantity, 1);
        const unitPrice = amountField(salesOrder.unit_price);
        const taxAmount = amountField(salesOrder.tax_amount);
        const subtotal = quantity * unitPrice;
        return srmApi.createSalesOrder(compactRecord({
          title: salesOrder.title.trim(),
          customer_id: numericField(salesOrder.customer_id),
          currency: salesOrder.currency,
          subtotal,
          tax_amount: taxAmount,
          total_amount: subtotal + taxAmount,
          expected_start_date: salesOrder.expected_start_date,
          expected_end_date: salesOrder.expected_end_date,
          terms: salesOrder.terms,
          lines: salesOrder.line_description.trim() || numericField(salesOrder.product_id) ? [{
            product_id: numericField(salesOrder.product_id),
            service_type: numericField(salesOrder.product_id) ? "product" : "service",
            description: salesOrder.line_description.trim(),
            quantity,
            unit_price: unitPrice,
            tax_amount: taxAmount,
            line_total: subtotal + taxAmount,
          }] : [],
        }));
      }
      if (kind === "contracts") {
        if (!contract.title.trim()) throw new Error("Contract title is required.");
        return srmApi.createContract(compactRecord({
          title: contract.title.trim(),
          sales_order_id: numericField(contract.sales_order_id),
          customer_id: numericField(contract.customer_id),
          contract_type: contract.contract_type,
          effective_date: contract.effective_date,
          expiry_date: contract.expiry_date,
          contract_value: amountField(contract.contract_value),
          currency: contract.currency,
          terms: contract.terms,
        }));
      }
      if (kind === "engagements") {
        if (!engagement.name.trim()) throw new Error("Engagement name is required.");
        return srmApi.createEngagement(compactRecord({
          name: engagement.name.trim(),
          sales_order_id: numericField(engagement.sales_order_id),
          contract_id: numericField(engagement.contract_id),
          customer_id: numericField(engagement.customer_id),
          billing_type: engagement.billing_type,
          budget_amount: amountField(engagement.budget_amount),
          currency: engagement.currency,
          planned_start_date: engagement.planned_start_date,
          planned_end_date: engagement.planned_end_date,
        }));
      }
      if (kind === "billingPlans") {
        if (!numericField(billingPlan.engagement_id)) throw new Error("Engagement ID is required for a billing plan.");
        if (!billingPlan.name.trim()) throw new Error("Billing plan name is required.");
        return srmApi.createBillingPlan(compactRecord({
          engagement_id: Number(billingPlan.engagement_id),
          name: billingPlan.name.trim(),
          billing_type: billingPlan.billing_type,
          currency: billingPlan.currency,
          total_amount: amountField(billingPlan.total_amount),
          recurrence_rule: billingPlan.recurrence_rule,
          milestones: billingPlan.milestone_name.trim() ? [{
            name: billingPlan.milestone_name.trim(),
            due_date: billingPlan.milestone_due_date || undefined,
            amount: amountField(billingPlan.milestone_amount),
          }] : [],
        }));
      }
      throw new Error("Create form is not available for this SRM view.");
    },
    onSuccess: async (result) => {
      const text = `${viewMeta[kind].title.slice(0, -1) || viewMeta[kind].title} created`;
      setMessage(text);
      toast({ title: text });
      await syncSrmNow(queryClient, {
        type: kind === "salesOrders" ? "sales_order_changed" : "inventory_changed",
        source: `srm-${kind}-create`,
        ids: { id: Number((result as SRMRecord | undefined)?.id || 0) || undefined },
      });
      onSaved?.();
    },
    onError: (err: unknown) => {
      const text = apiErrorMessage(err, "Create failed");
      setMessage(text);
      toast({ title: "SRM create failed", description: text, variant: "destructive" });
    },
  });

  if (!["salesOrders", "contracts", "engagements", "billingPlans"].includes(kind)) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Create {viewMeta[kind].title.slice(0, -1)}</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={(event: FormEvent) => { event.preventDefault(); mutation.mutate(); }}>
          {kind === "salesOrders" ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-2 text-sm md:col-span-2"><span className="font-medium">Title</span><Input value={salesOrder.title} onChange={(event) => setSalesOrder((current) => ({ ...current, title: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Customer ID</span><Input inputMode="numeric" value={salesOrder.customer_id} onChange={(event) => setSalesOrder((current) => ({ ...current, customer_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Currency</span><Input value={salesOrder.currency} onChange={(event) => setSalesOrder((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} /></label>
              </div>
              <div className="grid gap-3 md:grid-cols-6">
                <label className="space-y-2 text-sm"><span className="font-medium">Product ID</span><Input inputMode="numeric" value={salesOrder.product_id} onChange={(event) => setSalesOrder((current) => ({ ...current, product_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm md:col-span-2"><span className="font-medium">Line item</span><Input value={salesOrder.line_description} onChange={(event) => setSalesOrder((current) => ({ ...current, line_description: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Qty</span><Input inputMode="decimal" value={salesOrder.quantity} onChange={(event) => setSalesOrder((current) => ({ ...current, quantity: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Unit price</span><Input inputMode="decimal" value={salesOrder.unit_price} onChange={(event) => setSalesOrder((current) => ({ ...current, unit_price: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Tax</span><Input inputMode="decimal" value={salesOrder.tax_amount} onChange={(event) => setSalesOrder((current) => ({ ...current, tax_amount: event.target.value }))} /></label>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <label className="space-y-2 text-sm"><span className="font-medium">Start date</span><Input type="date" value={salesOrder.expected_start_date} onChange={(event) => setSalesOrder((current) => ({ ...current, expected_start_date: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">End date</span><Input type="date" value={salesOrder.expected_end_date} onChange={(event) => setSalesOrder((current) => ({ ...current, expected_end_date: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Terms</span><Input value={salesOrder.terms} onChange={(event) => setSalesOrder((current) => ({ ...current, terms: event.target.value }))} /></label>
              </div>
            </>
          ) : null}
          {kind === "contracts" ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-2 text-sm md:col-span-2"><span className="font-medium">Title</span><Input value={contract.title} onChange={(event) => setContract((current) => ({ ...current, title: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Sales order ID</span><Input inputMode="numeric" value={contract.sales_order_id} onChange={(event) => setContract((current) => ({ ...current, sales_order_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Customer ID</span><Input inputMode="numeric" value={contract.customer_id} onChange={(event) => setContract((current) => ({ ...current, customer_id: event.target.value }))} /></label>
              </div>
              <div className="grid gap-3 md:grid-cols-5">
                <label className="space-y-2 text-sm"><span className="font-medium">Type</span><Input value={contract.contract_type} onChange={(event) => setContract((current) => ({ ...current, contract_type: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Effective</span><Input type="date" value={contract.effective_date} onChange={(event) => setContract((current) => ({ ...current, effective_date: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Expiry</span><Input type="date" value={contract.expiry_date} onChange={(event) => setContract((current) => ({ ...current, expiry_date: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Value</span><Input inputMode="decimal" value={contract.contract_value} onChange={(event) => setContract((current) => ({ ...current, contract_value: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Currency</span><Input value={contract.currency} onChange={(event) => setContract((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} /></label>
              </div>
              <label className="space-y-2 text-sm"><span className="font-medium">Terms</span><Input value={contract.terms} onChange={(event) => setContract((current) => ({ ...current, terms: event.target.value }))} /></label>
            </>
          ) : null}
          {kind === "engagements" ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-2 text-sm md:col-span-2"><span className="font-medium">Name</span><Input value={engagement.name} onChange={(event) => setEngagement((current) => ({ ...current, name: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Sales order ID</span><Input inputMode="numeric" value={engagement.sales_order_id} onChange={(event) => setEngagement((current) => ({ ...current, sales_order_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Contract ID</span><Input inputMode="numeric" value={engagement.contract_id} onChange={(event) => setEngagement((current) => ({ ...current, contract_id: event.target.value }))} /></label>
              </div>
              <div className="grid gap-3 md:grid-cols-5">
                <label className="space-y-2 text-sm"><span className="font-medium">Customer ID</span><Input inputMode="numeric" value={engagement.customer_id} onChange={(event) => setEngagement((current) => ({ ...current, customer_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Billing type</span><Input value={engagement.billing_type} onChange={(event) => setEngagement((current) => ({ ...current, billing_type: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Budget</span><Input inputMode="decimal" value={engagement.budget_amount} onChange={(event) => setEngagement((current) => ({ ...current, budget_amount: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Start</span><Input type="date" value={engagement.planned_start_date} onChange={(event) => setEngagement((current) => ({ ...current, planned_start_date: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">End</span><Input type="date" value={engagement.planned_end_date} onChange={(event) => setEngagement((current) => ({ ...current, planned_end_date: event.target.value }))} /></label>
              </div>
            </>
          ) : null}
          {kind === "billingPlans" ? (
            <>
              <div className="grid gap-3 md:grid-cols-5">
                <label className="space-y-2 text-sm"><span className="font-medium">Engagement ID</span><Input inputMode="numeric" value={billingPlan.engagement_id} onChange={(event) => setBillingPlan((current) => ({ ...current, engagement_id: event.target.value }))} /></label>
                <label className="space-y-2 text-sm md:col-span-2"><span className="font-medium">Plan name</span><Input value={billingPlan.name} onChange={(event) => setBillingPlan((current) => ({ ...current, name: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Billing type</span><Input value={billingPlan.billing_type} onChange={(event) => setBillingPlan((current) => ({ ...current, billing_type: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Total</span><Input inputMode="decimal" value={billingPlan.total_amount} onChange={(event) => setBillingPlan((current) => ({ ...current, total_amount: event.target.value }))} /></label>
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-2 text-sm"><span className="font-medium">Currency</span><Input value={billingPlan.currency} onChange={(event) => setBillingPlan((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Recurrence</span><Input placeholder="monthly, quarterly" value={billingPlan.recurrence_rule} onChange={(event) => setBillingPlan((current) => ({ ...current, recurrence_rule: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Milestone</span><Input value={billingPlan.milestone_name} onChange={(event) => setBillingPlan((current) => ({ ...current, milestone_name: event.target.value }))} /></label>
                <label className="space-y-2 text-sm"><span className="font-medium">Milestone amount</span><Input inputMode="decimal" value={billingPlan.milestone_amount} onChange={(event) => setBillingPlan((current) => ({ ...current, milestone_amount: event.target.value }))} /></label>
              </div>
            </>
          ) : null}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Saving..." : `Create ${viewMeta[kind].title.slice(0, -1)}`}</Button>
            <ActionMessage message={message} />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function GenericRouteView({ kind, meta }: { kind: SRMViewKind; meta: ViewMeta }) {
  const queryClient = useQueryClient();
  const canManage = useCanManageRevenue();
  const query = useQuery({
    queryKey: ["srm", kind],
    queryFn: () => srmApi[meta.endpoint as SRMQueryEndpoint](),
    enabled: Boolean(meta.endpoint),
    refetchInterval: kind === "salesOrders" ? 3000 : 10000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });
  useSrmRealtimeInvalidation(queryClient, Boolean(meta.endpoint));
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
    onSuccess: async () => {
      await syncSrmNow(queryClient, { type: kind === "salesOrders" ? "sales_order_changed" : "inventory_changed", source: `srm-${kind}-action` });
      toast({ title: "SRM updated" });
    },
    onError: (err: unknown) => {
      const message = apiErrorMessage(err);
      toast({ title: "SRM action failed", description: message, variant: "destructive" });
    },
  });

  return (
    <div className="space-y-5">
      <PageHeader meta={meta} isFetching={query.isFetching} onRefresh={() => query.refetch()} />
      <ActionMessage message={!canManage ? "Read-only revenue access: create and workflow actions are hidden for this role." : undefined} />
      {canManage ? <CommercialCreateCard kind={kind} onSaved={() => query.refetch()} /> : null}
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
                    const status = String(record.status || "").toLowerCase();
                    const metadata = (record.metadata_json || {}) as SRMRecord;
                    const isPosSale = metadata.source === "pos";
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
                            {canManage && kind === "salesOrders" && id ? (
                              <>
                                {isPosSale ? <span className="rounded-md border bg-muted/40 px-2 py-1 text-xs text-muted-foreground">POS posted</span> : null}
                                {!isPosSale && status === "draft" ? <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ name: "submitSalesOrder", id })}>Submit</Button> : null}
                                {!isPosSale && status === "pending_approval" ? <span className="rounded-md border bg-muted/40 px-2 py-1 text-xs text-muted-foreground">Awaiting approval</span> : null}
                                {!isPosSale && status === "approved" ? <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ name: "confirmSalesOrder", id })}>Confirm</Button> : null}
                                {!isPosSale && status === "confirmed" ? <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ name: "draftInvoiceFromSalesOrder", id })}>Draft invoice</Button> : null}
                                {!isPosSale && ["cancelled", "closed"].includes(status) ? <span className="text-xs text-muted-foreground">No action</span> : null}
                              </>
                            ) : null}
                            {canManage && kind === "engagements" && id ? <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ name: "createPmsProject", id })}>Create Project</Button> : null}
                            {canManage && kind === "invoices" && id ? (
                              <>
                                <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ name: "approveInvoice", id })}>Approve</Button>
                                <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ name: "sendInvoice", id })}>Send</Button>
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
  const queryClient = useQueryClient();
  useSrmRealtimeInvalidation(queryClient);
  const meta = viewMeta[kind];
  if (kind === "dashboard") return <DashboardView />;
  if (kind === "posSessions") return <POSSessionView />;
  if (kind === "cashierClosing") return <CashierClosingView />;
  if (kind === "posReturns") return <POSReturnsView />;
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
