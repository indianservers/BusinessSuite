import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowUpDown,
  BarChart3,
  Bell,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Edit3,
  FileCheck2,
  Filter,
  GitMerge,
  GripVertical,
  IndianRupee,
  LayoutGrid,
  ListFilter,
  Mail,
  Megaphone,
  Phone,
  Plus,
  Save,
  Search,
  Sparkles,
  Target,
  Upload,
  Users,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { exportRows } from "@/lib/export";
import { formatCurrency, formatDate, statusColor } from "@/lib/utils";
import { crmApi, type CRMApiRecord, type CRMApiValue, type CRMApprovalRequest, type CRMApprovalWorkflow, type CRMCalendarEvent, type CRMDuplicateGroup, type CRMWinLossReport } from "./api";

type CRMLead = {
  id: number;
  name: string;
  company: string;
  email?: string;
  phone?: string;
  source: string;
  status: string;
  rating: string;
  leadScore: number;
  scoreLabel: string;
  owner?: string;
  value: number;
  nextFollowUp?: string;
  lastContacted?: string;
  industry?: string;
};

type CRMDeal = {
  id: number;
  name: string;
  company: string;
  contact: string;
  owner: string;
  pipelineId: number;
  stageId: number;
  stage: string;
  amount: number;
  probability: number;
  closeDate: string;
  nextStep: string;
  products: string[];
};

type CRMRecord = CRMApiRecord;

const emptyRecords: CRMRecord[] = [];
const emptyLeads: CRMLead[] = [];
const emptyDeals: CRMDeal[] = [];

type CRMPageKind =
  | "dashboard"
  | "leads"
  | "contacts"
  | "companies"
  | "deals"
  | "pipeline"
  | "pipelineSettings"
  | "activities"
  | "tasks"
  | "calendar"
  | "calendarIntegrations"
  | "webhooks"
  | "campaigns"
  | "products"
  | "quotations"
  | "approvalSettings"
  | "myApprovals"
  | "duplicates"
  | "territories"
  | "tickets"
  | "files"
  | "reports"
  | "automation"
  | "leadCash"
  | "forecasting"
  | "customer360"
  | "importExport"
  | "settings"
  | "leadScoring"
  | "featureChecklist"
  | "admin";

const pageTitles: Record<CRMPageKind, string> = {
  dashboard: "CRM Dashboard",
  leads: "Leads",
  contacts: "Contacts",
  companies: "Companies",
  deals: "Deals",
  pipeline: "Sales Pipeline",
  pipelineSettings: "Pipeline Settings",
  activities: "Activities",
  tasks: "CRM Tasks",
  calendar: "Calendar",
  calendarIntegrations: "Calendar Integrations",
  webhooks: "Webhooks",
  campaigns: "Campaigns",
  products: "Products",
  quotations: "Quotations",
  approvalSettings: "Approval Settings",
  myApprovals: "My Approvals",
  duplicates: "Duplicate Management",
  territories: "Territory Settings",
  tickets: "Support Tickets",
  files: "Files",
  reports: "Reports",
  automation: "Automation",
  leadCash: "Lead-to-Cash",
  forecasting: "Forecasting",
  customer360: "Customer 360",
  importExport: "Import & Export",
  settings: "CRM Settings",
  leadScoring: "Lead Scoring",
  featureChecklist: "Feature Checklist",
  admin: "CRM Admin",
};

const savedViews = ["My records", "Hot pipeline", "Due this week", "No follow-up", "Recently updated"];
type CRMFilters = { owner: string; status: string; type: string; territory: string };
type SortState = { key: string; direction: "asc" | "desc" } | null;
type DashboardQuickCreateKind = "leads" | "contacts" | "companies" | "deals" | "tasks";

const dashboardQuickCreateKinds: Array<{ kind: DashboardQuickCreateKind; label: string }> = [
  { kind: "leads", label: "Lead" },
  { kind: "contacts", label: "Contact" },
  { kind: "companies", label: "Company" },
  { kind: "deals", label: "Deal" },
  { kind: "tasks", label: "Task" },
];

type QuickFormField = {
  key: string;
  label: string;
  type?: "text" | "email" | "number" | "date" | "textarea" | "select";
  placeholder?: string;
  options?: string[];
  required?: boolean;
  width?: "full" | "half" | "third";
};

const quickFormFieldsByKind: Partial<Record<CRMPageKind, QuickFormField[]>> = {
  leads: [
    { key: "name", label: "Lead name", required: true, placeholder: "Jane Shah" },
    { key: "company", label: "Company", placeholder: "Acme India" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+91 98765 43210" },
    { key: "source", label: "Source", type: "select", options: ["Website", "Referral", "Event", "Partner", "Phone Call", "Manual Entry"] },
    { key: "status", label: "Status", type: "select", options: ["New", "Qualified", "Working", "Converted", "Lost"] },
    { key: "rating", label: "Rating", type: "select", options: ["Cold", "Warm", "Hot"] },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  contacts: [
    { key: "name", label: "Contact name", required: true, placeholder: "Jane Shah" },
    { key: "company", label: "Company", placeholder: "Acme India" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+91 98765 43210" },
    { key: "source", label: "Source", type: "select", options: ["Manual Entry", "Referral", "Website", "Partner"] },
    { key: "stage", label: "Lifecycle stage", type: "select", options: ["Lead", "Opportunity", "Customer"] },
    { key: "status", label: "Status", type: "select", options: ["Active", "Prospect", "Dormant"] },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  companies: [
    { key: "name", label: "Company name", required: true, placeholder: "Acme India" },
    { key: "industry", label: "Industry", placeholder: "Software" },
    { key: "type", label: "Account type", type: "select", options: ["Prospect", "Customer", "Partner", "Vendor"] },
    { key: "revenue", label: "Annual revenue", type: "number", placeholder: "5000000" },
    { key: "status", label: "Status", type: "select", options: ["Active", "Prospect", "Inactive"] },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  deals: [
    { key: "name", label: "Deal name", required: true, placeholder: "ERP rollout" },
    { key: "amount", label: "Amount", type: "number", placeholder: "500000" },
    { key: "probability", label: "Probability %", type: "number", placeholder: "10" },
    { key: "status", label: "Status", type: "select", options: ["Open", "Won", "Lost"] },
    { key: "nextFollowUp", label: "Expected close", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  activities: [
    { key: "subject", label: "Subject", required: true, placeholder: "Follow-up call" },
    { key: "type", label: "Activity type", type: "select", options: ["Task", "Call", "Meeting", "Email"] },
    { key: "status", label: "Status", type: "select", options: ["Planned", "Open", "Completed"] },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  tasks: [
    { key: "subject", label: "Task title", required: true, placeholder: "Call lead" },
    { key: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Completed"] },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  products: [
    { key: "name", label: "Product name", required: true, placeholder: "CRM Starter" },
    { key: "sku", label: "SKU", placeholder: "CRM-STARTER" },
    { key: "category", label: "Category", placeholder: "Software" },
    { key: "price", label: "Unit price", type: "number", placeholder: "25000" },
    { key: "status", label: "Status", type: "select", options: ["Active", "Draft", "Inactive"] },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  quotations: [
    { key: "quote", label: "Quote number", placeholder: "QT-2026-001" },
    { key: "status", label: "Status", type: "select", options: ["Draft", "Sent", "Accepted", "Rejected"] },
    { key: "issueDate", label: "Issue date", type: "date" },
    { key: "expiryDate", label: "Expiry date", type: "date" },
    { key: "total", label: "Total amount", type: "number", placeholder: "150000" },
  ],
  campaigns: [
    { key: "name", label: "Campaign name", required: true, placeholder: "Q2 Lead Nurture" },
    { key: "type", label: "Campaign type", type: "select", options: ["Email", "WhatsApp", "Event", "Ads"] },
    { key: "status", label: "Status", type: "select", options: ["Planned", "Active", "Completed"] },
    { key: "startDate", label: "Start date", type: "date" },
    { key: "endDate", label: "End date", type: "date" },
    { key: "budget", label: "Budget", type: "number", placeholder: "100000" },
    { key: "expectedRevenue", label: "Expected revenue", type: "number", placeholder: "250000" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  tickets: [
    { key: "subject", label: "Ticket subject", required: true, placeholder: "Customer issue" },
    { key: "number", label: "Ticket number", placeholder: "TCK-2026-001" },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High", "Critical"] },
    { key: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Resolved"] },
    { key: "category", label: "Category", type: "select", options: ["General", "Billing", "Technical", "Onboarding"] },
    { key: "source", label: "Source", type: "select", options: ["Manual", "Email", "Phone", "Portal"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
};
type AutomationCard = [title: string, value: string, detail: string, Icon: React.ElementType];
type CRMApiState<T> = { data: T; loading: boolean; error: string | null };
type InlineFieldType = "text" | "number" | "date" | "select" | "tags";
type InlineEditConfig = { type: InlineFieldType; apiField: string; options?: string[] };

const customFieldEntities = [
  { value: "leads", label: "Leads" },
  { value: "contacts", label: "Contacts" },
  { value: "companies", label: "Accounts" },
  { value: "deals", label: "Deals" },
  { value: "quotations", label: "Quotations" },
  { value: "tasks", label: "Tasks" },
];

const customFieldTypes = [
  "text",
  "long_text",
  "number",
  "currency",
  "date",
  "datetime",
  "dropdown",
  "multi_select",
  "checkbox",
  "email",
  "phone",
  "url",
  "user",
  "owner",
];

const listInlineEditConfig: Partial<Record<CRMPageKind, Record<string, InlineEditConfig>>> = {
  leads: {
    name: { type: "text", apiField: "full_name" },
    company: { type: "text", apiField: "company_name" },
    email: { type: "text", apiField: "email" },
    phone: { type: "text", apiField: "phone" },
    source: { type: "select", apiField: "source", options: ["Website", "Referral", "Event", "Partner", "Phone Call", "Email Campaign", "Other"] },
    status: { type: "select", apiField: "status", options: ["New", "Contacted", "Qualified", "Converted", "Lost"] },
    rating: { type: "select", apiField: "rating", options: ["Hot", "Warm", "Cold"] },
    leadScore: { type: "number", apiField: "lead_score" },
    value: { type: "number", apiField: "estimated_value" },
    nextFollowUp: { type: "date", apiField: "next_follow_up_at" },
  },
  contacts: {
    name: { type: "text", apiField: "full_name" },
    email: { type: "text", apiField: "email" },
    phone: { type: "text", apiField: "phone" },
    title: { type: "text", apiField: "job_title" },
    stage: { type: "select", apiField: "lifecycle_stage", options: ["Lead", "Opportunity", "Customer", "Inactive"] },
    status: { type: "select", apiField: "status", options: ["Active", "Open", "Inactive"] },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
  },
  companies: {
    name: { type: "text", apiField: "name" },
    industry: { type: "text", apiField: "industry" },
    type: { type: "select", apiField: "account_type", options: ["Prospect", "Customer", "Partner", "Vendor"] },
    status: { type: "select", apiField: "status", options: ["Active", "Inactive", "Prospect"] },
    revenue: { type: "number", apiField: "annual_revenue" },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
    city: { type: "text", apiField: "city" },
    email: { type: "text", apiField: "email" },
  },
  deals: {
    name: { type: "text", apiField: "name" },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
    stageId: { type: "number", apiField: "stage_id" },
    amount: { type: "number", apiField: "amount" },
    probability: { type: "number", apiField: "probability" },
    closeDate: { type: "date", apiField: "expected_close_date" },
    status: { type: "select", apiField: "status", options: ["Open", "Won", "Lost"] },
  },
  tasks: {
    subject: { type: "text", apiField: "title" },
    owner: { type: "number", apiField: "ownerId" },
    due: { type: "date", apiField: "due_date" },
    status: { type: "select", apiField: "status", options: ["To Do", "In Progress", "Completed", "Done"] },
    priority: { type: "select", apiField: "priority", options: ["Low", "Medium", "High", "Critical"] },
  },
};

const apiEntityForKind: Partial<Record<CRMPageKind, string>> = {
  leads: "leads",
  contacts: "contacts",
  companies: "companies",
  deals: "deals",
  pipeline: "deals",
  pipelineSettings: "pipelines",
  activities: "activities",
  tasks: "tasks",
  calendar: "meetings",
  products: "products",
  quotations: "quotations",
  campaigns: "campaigns",
  tickets: "tickets",
  files: "files",
  settings: "custom-fields",
  leadScoring: "lead-scoring-rules",
  admin: "owners",
};

function useCrmRecords<T = CRMRecord>(entity: string | undefined, fallback: T[], params?: Record<string, unknown>): CRMApiState<T[]> {
  const [state, setState] = useState<CRMApiState<T[]>>({ data: fallback, loading: Boolean(entity), error: null });

  useEffect(() => {
    if (!entity) {
      setState({ data: fallback, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    crmApi
      .list<CRMApiRecord>(entity, { per_page: 100, ...(params || {}) })
      .then((response) => {
        if (!cancelled) setState({ data: response.data.items.map((item) => normalizeApiRecord(kindlessEntity(entity), item)) as T[], loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ data: fallback, loading: false, error: err?.response?.data?.detail || "CRM API is not reachable." });
      });
    return () => {
      cancelled = true;
    };
  }, [entity, JSON.stringify(params)]);

  return state;
}

function kindlessEntity(entity: string) {
  if (entity === "companies") return "companies";
  if (entity === "products") return "products";
  if (entity === "quotations") return "quotations";
  if (entity === "deals") return "deals";
  if (entity === "leads") return "leads";
  if (entity === "contacts") return "contacts";
  if (entity === "activities") return "activities";
  if (entity === "tasks") return "tasks";
  if (entity === "meetings") return "meetings";
  if (entity === "custom-fields") return "settings";
  if (entity === "owners") return "admin";
  return entity;
}

export default function CRMWorkspacePage({ kind }: { kind: CRMPageKind }) {
  if (kind === "pipeline") return <PipelinePage />;
  if (kind === "pipelineSettings") return <PipelineSettingsPage />;
  if (kind === "leadScoring") return <LeadScoringSettingsPage />;
  if (kind === "calendar") return <CRMCalendarPage />;
  if (kind === "calendarIntegrations") return <CalendarIntegrationsPage />;
  if (kind === "webhooks") return <WebhookSettingsPage />;
  if (kind === "approvalSettings") return <ApprovalSettingsPage />;
  if (kind === "myApprovals") return <MyApprovalsPage />;
  if (kind === "duplicates") return <DuplicateManagementPage />;
  if (kind === "territories") return <TerritorySettingsPage />;
  if (kind === "featureChecklist") return <CRMFeatureChecklistPage />;
  if (kind === "settings") return <CustomFieldsSettingsPage />;
  if (kind === "dashboard") return <CRMDashboard />;
  if (kind === "reports") return <CRMReports />;
  if (kind === "automation") return <SalesAutomationPage />;
  if (kind === "leadCash") return <LeadToCashPage />;
  if (kind === "forecasting") return <ForecastingPage />;
  if (kind === "customer360") return <Customer360Page />;
  if (kind === "importExport") return <ImportExportPage />;
  return <CRMListPage kind={kind} />;
}

function CRMDashboard() {
  const navigate = useNavigate();
  const leadState = useCrmRecords<CRMRecord>("leads", emptyRecords);
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const [quickCreateKind, setQuickCreateKind] = useState<DashboardQuickCreateKind>("leads");
  const [showQuickCreate, setShowQuickCreate] = useState(false);
  const [quickCreateSaving, setQuickCreateSaving] = useState(false);
  const [quickCreateError, setQuickCreateError] = useState<string | null>(null);
  const crmLeads = useMemo(() => leadState.data.map(recordToLead), [leadState.data]);
  const crmDeals = useMemo(() => dealState.data.map((record) => recordToDeal(record, stageState.data)), [dealState.data, stageState.data]);
  const stageNames = useMemo(() => stageState.data.map((stage) => String(stage.name)).filter(Boolean), [stageState.data]);
  const wonRevenue = crmDeals.filter((deal) => deal.stage === "Won").reduce((sum, deal) => sum + deal.amount, 0);
  const pipelineValue = crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).reduce((sum, deal) => sum + deal.amount, 0);
  const weighted = crmDeals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  const overdueFollowUps = crmLeads.filter((lead) => lead.nextFollowUp && new Date(lead.nextFollowUp) < new Date() && lead.status !== "Converted").length;
  const openDeals = crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).length;
  const wonDeals = crmDeals.filter((deal) => deal.stage === "Won").length;
  const lostDeals = crmDeals.filter((deal) => deal.stage === "Lost").length;
  const convertedLeads = crmLeads.filter((lead) => lead.status === "Converted").length;
  const hotLeads = crmLeads.filter((lead) => lead.rating === "Hot" || lead.scoreLabel === "Hot").length;
  const averageDealSize = crmDeals.length ? crmDeals.reduce((sum, deal) => sum + deal.amount, 0) / crmDeals.length : 0;
  const winRate = wonDeals + lostDeals ? Math.round((wonDeals / (wonDeals + lostDeals)) * 100) : 0;
  const conversionRate = crmLeads.length ? Math.round((convertedLeads / crmLeads.length) * 100) : 0;
  const weightedCoverage = pipelineValue ? Math.round((weighted / pipelineValue) * 100) : 0;
  const staleOpenDeals = crmDeals.filter((deal) => deal.closeDate && new Date(deal.closeDate) < new Date() && !["Won", "Lost"].includes(deal.stage)).length;
  const chartData = stageNames.map((stage) => ({
    stage,
    value: crmDeals.filter((deal) => deal.stage === stage).reduce((sum, deal) => sum + deal.amount, 0),
  }));
  const sourceData = ["Website", "Referral", "Event", "Partner", "Phone Call", "Email Campaign"].map((source) => ({
    name: source,
    value: crmLeads.filter((lead) => lead.source === source).length,
  }));
  const revenueTrend = useMemo(() => {
    const buckets = new Map<string, { month: string; revenue: number; forecast: number }>();
    dealState.data.forEach((deal) => {
      const rawDate = String(deal.closed_at || deal.wonAt || deal.won_at || deal.expected_close_date || deal.createdAt || deal.created_at || "");
      const date = rawDate ? new Date(rawDate) : null;
      if (!date || Number.isNaN(date.getTime())) return;
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      const month = date.toLocaleDateString(undefined, { month: "short" });
      const current = buckets.get(key) || { month, revenue: 0, forecast: 0 };
      const amount = Number(deal.amount || 0);
      if (String(deal.status || "").toLowerCase() === "won") current.revenue += amount;
      current.forecast += (amount * Number(deal.probability || 0)) / 100;
      buckets.set(key, current);
    });
    return Array.from(buckets.entries()).sort(([a], [b]) => a.localeCompare(b)).slice(-6).map(([, value]) => value);
  }, [dealState.data]);
  const insightRows = [
    `${crmLeads.filter((lead) => lead.rating === "Hot" || lead.scoreLabel === "Hot").length} hot leads are visible from current CRM data.`,
    `${crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).length} open deals carry ${formatCurrency(pipelineValue)} in pipeline value.`,
    `${crmDeals.filter((deal) => deal.closeDate && new Date(deal.closeDate) < new Date() && !["Won", "Lost"].includes(deal.stage)).length} open deals are past expected close date.`,
    `${crmDeals.filter((deal) => deal.probability >= 70 && !["Won", "Lost"].includes(deal.stage)).length} high-probability deals should be reviewed for approvals and quotation follow-up.`,
  ];
  const createQuickRecord = (draft: CRMRecord, customFields?: CRMApiRecord) => {
    const apiEntity = apiEntityForKind[quickCreateKind];
    if (!apiEntity) return;
    const payload = { ...createPayloadForKind(quickCreateKind, draft), customFields: customFields || {} };
    setQuickCreateSaving(true);
    setQuickCreateError(null);
    crmApi
      .create<CRMApiRecord>(apiEntity, payload)
      .then((response) => {
        setShowQuickCreate(false);
        const detailPath = detailPathFor(quickCreateKind);
        if (detailPath && response.data?.id) {
          navigate(`${detailPath}/${response.data.id}`);
          return;
        }
        navigate(`/crm/${quickCreateKind}`);
      })
      .catch((err) => setQuickCreateError(err?.response?.data?.detail || "CRM record could not be created."))
      .finally(() => setQuickCreateSaving(false));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="VyaparaCRM" description="Sales command center for leads, accounts, deals, pipeline, activities, quotations, support, automation, and analytics." action="Quick create" onAction={() => setShowQuickCreate(true)} />
      {leadState.error || dealState.error || stageState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{leadState.error || dealState.error || stageState.error}</div> : null}
      {leadState.loading || dealState.loading || stageState.loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading CRM dashboard...</div> : null}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric icon={Users} label="Total leads" value={crmLeads.length} tone="blue" />
        <Metric icon={LayoutGrid} label="Open deals" value={crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).length} tone="emerald" />
        <Metric icon={IndianRupee} label="Pipeline value" value={formatCurrency(pipelineValue)} tone="violet" />
        <Metric icon={BarChart3} label="Expected revenue" value={formatCurrency(weighted)} tone="amber" />
        <Metric icon={Activity} label="Overdue follow-ups" value={overdueFollowUps} tone="red" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_0.9fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Pipeline by stage</CardTitle>
            <Badge variant="outline">{formatCurrency(wonRevenue)} won</Badge>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="stage" tickLine={false} axisLine={false} interval={0} angle={-18} textAnchor="end" height={70} />
                <YAxis tickFormatter={(value) => `${Number(value) / 100000}L`} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                <Bar dataKey="value" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Leads by source</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sourceData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={104}>
                  {sourceData.map((_, index) => <Cell key={index} fill={["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0891b2"][index]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Card>
          <CardHeader><CardTitle>Revenue trend and forecast</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={revenueTrend}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} />
                <YAxis tickFormatter={(value) => `${Number(value) / 100000}L`} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => formatCurrency(Number(value) * 100000)} />
                <Line type="monotone" dataKey="revenue" stroke="#16a34a" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="forecast" stroke="#2563eb" strokeWidth={3} strokeDasharray="4 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>AI Insights</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {insightRows.map((text) => <Insight key={text} text={text} />)}
          </CardContent>
        </Card>
      </div>

      <DashboardStatistics
        leads={crmLeads.length}
        hotLeads={hotLeads}
        convertedLeads={convertedLeads}
        openDeals={openDeals}
        wonDeals={wonDeals}
        lostDeals={lostDeals}
        pipelineValue={pipelineValue}
        weighted={weighted}
        wonRevenue={wonRevenue}
        averageDealSize={averageDealSize}
        conversionRate={conversionRate}
        winRate={winRate}
        weightedCoverage={weightedCoverage}
        overdueFollowUps={overdueFollowUps}
        staleOpenDeals={staleOpenDeals}
      />
      {showQuickCreate ? (
        <DashboardQuickCreateDialog
          kind={quickCreateKind}
          saving={quickCreateSaving}
          error={quickCreateError}
          onKindChange={(kind) => {
            setQuickCreateKind(kind);
            setQuickCreateError(null);
          }}
          onClose={() => setShowQuickCreate(false)}
          onCreate={createQuickRecord}
        />
      ) : null}
    </div>
  );
}

function DashboardStatistics({
  leads,
  hotLeads,
  convertedLeads,
  openDeals,
  wonDeals,
  lostDeals,
  pipelineValue,
  weighted,
  wonRevenue,
  averageDealSize,
  conversionRate,
  winRate,
  weightedCoverage,
  overdueFollowUps,
  staleOpenDeals,
}: {
  leads: number;
  hotLeads: number;
  convertedLeads: number;
  openDeals: number;
  wonDeals: number;
  lostDeals: number;
  pipelineValue: number;
  weighted: number;
  wonRevenue: number;
  averageDealSize: number;
  conversionRate: number;
  winRate: number;
  weightedCoverage: number;
  overdueFollowUps: number;
  staleOpenDeals: number;
}) {
  const funnelRows = [
    { label: "Total leads", value: leads, max: Math.max(leads, 1), tone: "bg-emerald-500" },
    { label: "Hot leads", value: hotLeads, max: Math.max(leads, 1), tone: "bg-amber-500" },
    { label: "Converted leads", value: convertedLeads, max: Math.max(leads, 1), tone: "bg-blue-500" },
    { label: "Open deals", value: openDeals, max: Math.max(openDeals + wonDeals + lostDeals, 1), tone: "bg-violet-500" },
  ];
  const cards = [
    { label: "Lead conversion", value: `${conversionRate}%`, detail: `${convertedLeads} converted from ${leads}`, Icon: Target },
    { label: "Win rate", value: `${winRate}%`, detail: `${wonDeals} won / ${lostDeals} lost`, Icon: CheckCircle2 },
    { label: "Weighted coverage", value: `${weightedCoverage}%`, detail: `${formatCurrency(weighted)} weighted`, Icon: BarChart3 },
    { label: "Average deal size", value: formatCurrency(averageDealSize), detail: `${formatCurrency(wonRevenue)} won revenue`, Icon: IndianRupee },
  ];
  const hygieneRows = [
    { label: "Overdue follow-ups", value: overdueFollowUps, note: "Leads needing action" },
    { label: "Past close date", value: staleOpenDeals, note: "Open deals to review" },
    { label: "Active pipeline", value: formatCurrency(pipelineValue), note: "Open deal value" },
  ];

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Dashboard Statistics</h2>
        <p className="text-sm text-muted-foreground">Live CRM performance calculated from leads, deals, stage movement, and follow-up data.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, detail, Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-700">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-2xl font-semibold">{value}</p>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{detail}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Lead-to-revenue funnel</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {funnelRows.map((row) => {
              const width = row.value > 0 ? Math.max(6, Math.round((row.value / row.max) * 100)) : 0;
              return (
                <div key={row.label} className="space-y-2">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium">{row.label}</span>
                    <span className="text-muted-foreground">{row.value}</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                    <div className={`h-full rounded-full ${row.tone}`} style={{ width: `${width}%` }} />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pipeline hygiene</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {hygieneRows.map((row) => (
              <div key={row.label} className="rounded-md border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{row.label}</span>
                  <span className="text-lg font-semibold">{row.value}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{row.note}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function PipelinePage() {
  const navigate = useNavigate();
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc" });
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const activePipelineId = selectedPipelineId || Number(pipelineState.data.find((pipeline) => pipeline.is_default)?.id || pipelineState.data[0]?.id || 0);
  const pipelineStages = useMemo(() => stageState.data.filter((stage) => Number(stage.pipeline_id || stage.pipelineId || 0) === activePipelineId), [stageState.data, activePipelineId]);
  const stageByName = useMemo(() => new Map(pipelineStages.map((stage) => [String(stage.name), stage])), [pipelineStages]);
  const initialDeals = useMemo<CRMDeal[]>(() => dealState.data.filter((record) => Number(record.pipelineId || record.pipeline_id || 0) === activePipelineId).map((record) => recordToDeal(record, pipelineStages)), [dealState.data, pipelineStages, activePipelineId]);
  const [deals, setDeals] = useState<CRMDeal[]>(initialDeals);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const activeDeal = deals.find((deal) => deal.id === activeId);
  const visibleDeals = deals.filter((deal) => [deal.name, deal.company, deal.owner].join(" ").toLowerCase().includes(filter.toLowerCase()));

  useEffect(() => {
    setDeals(initialDeals);
  }, [initialDeals]);

  const onDragStart = (event: DragStartEvent) => setActiveId(event.active.id as number);
  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    if (!over) return;
    const targetStage = String(over.id).startsWith("stage-") ? String(over.id).replace("stage-", "") : deals.find((deal) => deal.id === over.id)?.stage;
    if (!targetStage) return;
    const targetStageRecord = stageByName.get(targetStage);
    if (!targetStageRecord) return;
    const probability = Number(targetStageRecord.probability ?? stageProbability(targetStage));
    const status = targetStageRecord.is_won ? "Won" : targetStageRecord.is_lost ? "Lost" : "Open";
    const previousDeals = deals;
    setDeals((items) => items.map((deal) => (deal.id === active.id ? { ...deal, stage: targetStage, stageId: Number(targetStageRecord.id), pipelineId: activePipelineId, probability } : deal)));
    crmApi.update("deals", Number(active.id), { pipeline_id: activePipelineId, stage_id: Number(targetStageRecord.id), probability, status }).catch(() => setDeals(previousDeals));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Sales Pipeline" description="Switch between custom pipelines and drag deals between organization-scoped stages." action="Pipeline settings" onAction={() => navigate("/crm/pipeline-settings")} />
      {dealState.error || stageState.error || pipelineState.error ? <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">{dealState.error || stageState.error || pipelineState.error}</div> : null}
      {dealState.loading || stageState.loading || pipelineState.loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading CRM pipeline...</div> : null}
      <div className="grid gap-3 lg:grid-cols-[18rem_1fr]">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Pipeline</span>
          <select className="h-10 w-full rounded-md border bg-background px-3" value={activePipelineId || ""} onChange={(event) => setSelectedPipelineId(Number(event.target.value))}>
            {pipelineState.data.map((pipeline) => <option key={String(pipeline.id)} value={Number(pipeline.id)}>{String(pipeline.name)}</option>)}
          </select>
        </label>
        <Toolbar search={filter} onSearch={setFilter} />
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {pipelineStages.map((stageRecord) => {
            const stage = String(stageRecord.name);
            const stageDeals = visibleDeals.filter((deal) => deal.stage === stage);
            return <PipelineColumn key={stageRecord.id as string | number} stage={stage} stageRecord={stageRecord} deals={stageDeals} />;
          })}
          {!pipelineStages.length ? <div className="flex h-48 min-w-80 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">No stages configured for this pipeline.</div> : null}
        </div>
        <DragOverlay>{activeDeal ? <DealCard deal={activeDeal} overlay /> : null}</DragOverlay>
      </DndContext>
    </div>
  );
}

function PipelineColumn({ stage, stageRecord, deals }: { stage: string; stageRecord: CRMRecord; deals: CRMDeal[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: `stage-${stage}` });
  const value = deals.reduce((sum, deal) => sum + deal.amount, 0);
  const weighted = deals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  return (
    <section ref={setNodeRef} className={`flex h-[calc(100vh-14rem)] w-80 shrink-0 flex-col rounded-lg border bg-muted/35 ${isOver ? "ring-2 ring-primary/40" : ""}`}>
      <header className="border-b bg-background p-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="truncate text-sm font-semibold">{stage}</h2>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{deals.length}</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{Number(stageRecord.probability || 0)}% / {formatCurrency(value)} total / {formatCurrency(weighted)} weighted</p>
      </header>
      <SortableContext items={deals.map((deal) => deal.id)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 space-y-3 overflow-y-auto p-3">
          {deals.map((deal) => <DealCard key={deal.id} deal={deal} />)}
          {!deals.length ? <div className="flex h-28 items-center justify-center rounded-lg border border-dashed bg-background/60 text-sm text-muted-foreground">Drop deal here</div> : null}
        </div>
      </SortableContext>
    </section>
  );
}

function DealCard({ deal, overlay = false }: { deal: CRMDeal; overlay?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: deal.id });
  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-lg border bg-card p-3 shadow-sm ${isDragging ? "opacity-50" : ""} ${overlay ? "w-72 shadow-xl" : ""}`}
    >
      <div className="flex items-start gap-2">
        <button type="button" className="rounded p-1 text-muted-foreground hover:bg-muted" {...attributes} {...listeners} aria-label="Drag deal">
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-sm font-semibold">{deal.name}</h3>
          <p className="mt-1 truncate text-xs text-muted-foreground">{deal.company} / {deal.contact}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="font-semibold">{formatCurrency(deal.amount)}</span>
        <Badge variant="outline">{deal.probability}%</Badge>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Close {formatDate(deal.closeDate)}</p>
      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">Next: {deal.nextStep}</p>
    </article>
  );
}

function CustomFieldsSettingsPageLegacy() {
  const [fields, setFields] = useState<CRMRecord[]>([]);
  const [draft, setDraft] = useState<CRMRecord>({ entity: "leads", fieldKey: "", label: "", fieldType: "text", isActive: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    crmApi
      .list<CRMRecord>("custom-fields", { per_page: 100, sort_by: "position", sort_order: "asc" })
      .then((response) => setFields(response.data.items || []))
      .catch((err) => setError(err?.response?.data?.detail || "Custom fields could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const createField = () => {
    if (!draft.fieldKey || !draft.label) return;
    setLoading(true);
    setError(null);
    crmApi
      .create<CRMRecord>("custom-fields", draft)
      .then(() => {
        setDraft({ entity: draft.entity || "leads", fieldKey: "", label: "", fieldType: draft.fieldType || "text", isActive: true });
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Custom field could not be created."))
      .finally(() => setLoading(false));
  };

  return (
    <div className="space-y-5">
      <PageHeader title="CRM Settings" description={descriptionFor("settings")} action="Create field" onAction={createField} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardHeader><CardTitle>Custom Fields</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="space-y-1 text-sm"><span className="font-medium">Entity</span><select className="h-10 w-full rounded-md border bg-background px-3" value={String(draft.entity || "leads")} onChange={(event) => setDraft((current) => ({ ...current, entity: event.target.value }))}><option value="leads">Leads</option><option value="contacts">Contacts</option><option value="companies">Accounts</option><option value="deals">Deals</option><option value="quotations">Quotations</option><option value="tasks">Tasks</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Field key</span><Input value={String(draft.fieldKey || "")} onChange={(event) => setDraft((current) => ({ ...current, fieldKey: event.target.value }))} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Label</span><Input value={String(draft.label || "")} onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={String(draft.fieldType || "text")} onChange={(event) => setDraft((current) => ({ ...current, fieldType: event.target.value }))}><option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="boolean">Boolean</option><option value="select">Select</option></select></label>
          </div>
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-left"><tr><th className="px-3 py-2">Entity</th><th className="px-3 py-2">Label</th><th className="px-3 py-2">Key</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Status</th></tr></thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={String(field.id)} className="border-t">
                    <td className="px-3 py-2">{labelFor(String(field.entity || ""))}</td>
                    <td className="px-3 py-2 font-medium">{String(field.label || "")}</td>
                    <td className="px-3 py-2 text-muted-foreground">{String(field.fieldKey || field.field_key || "")}</td>
                    <td className="px-3 py-2">{labelFor(String(field.fieldType || field.field_type || "text"))}</td>
                    <td className="px-3 py-2"><Badge className={statusColor(field.isActive === false ? "inactive" : "active")}>{field.isActive === false ? "Inactive" : "Active"}</Badge></td>
                  </tr>
                ))}
                {!fields.length ? <tr><td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">{loading ? "Loading custom fields..." : "No custom fields configured."}</td></tr> : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PipelineSettingsPage() {
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc" });
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const [pipelines, setPipelines] = useState<CRMRecord[]>([]);
  const [stages, setStages] = useState<CRMRecord[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [pipelineName, setPipelineName] = useState("");
  const [stageDraft, setStageDraft] = useState<CRMRecord>({ name: "", probability: 10, color: "#2563eb", is_won: false, is_lost: false });
  const [error, setError] = useState<string | null>(null);
  const activePipelineId = selectedPipelineId || Number(pipelines.find((pipeline) => pipeline.is_default)?.id || pipelines[0]?.id || 0);
  const activeStages = stages.filter((stage) => Number(stage.pipeline_id || stage.pipelineId || 0) === activePipelineId).sort((a, b) => Number(a.position || 0) - Number(b.position || 0));
  const stageDealCounts = useMemo(() => {
    const counts = new Map<number, number>();
    dealState.data.forEach((deal) => counts.set(Number(deal.stageId || deal.stage_id || 0), (counts.get(Number(deal.stageId || deal.stage_id || 0)) || 0) + 1));
    return counts;
  }, [dealState.data]);

  useEffect(() => setPipelines(pipelineState.data), [pipelineState.data]);
  useEffect(() => setStages(stageState.data), [stageState.data]);

  const createPipeline = () => {
    const name = pipelineName.trim();
    if (!name) return;
    crmApi.create<CRMApiRecord>("pipelines", { name, description: "Custom sales pipeline" }).then((response) => {
      setPipelines((items) => [...items, normalizeApiRecord("pipelines", response.data) as CRMRecord]);
      setSelectedPipelineId(Number(response.data.id));
      setPipelineName("");
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create pipeline."));
  };

  const createStage = () => {
    if (!activePipelineId || !String(stageDraft.name || "").trim()) return;
    const position = activeStages.length + 1;
    crmApi.createPipelineStage<CRMApiRecord>(activePipelineId, { ...stageDraft, position }).then((response) => {
      setStages((items) => [...items, normalizeApiRecord("pipeline-stages", response.data) as CRMRecord]);
      setStageDraft({ name: "", probability: 10, color: "#2563eb", is_won: false, is_lost: false });
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create stage."));
  };

  const updateStage = (stage: CRMRecord, patch: CRMApiRecord) => {
    const stageId = Number(stage.id);
    const previous = stages;
    setStages((items) => items.map((item) => Number(item.id) === stageId ? ({ ...item, ...patch } as CRMRecord) : item));
    crmApi.update("pipeline-stages", stageId, patch).catch((err) => {
      setStages(previous);
      setError(err?.response?.data?.detail || "Could not update stage.");
    });
  };

  const deleteStage = (stage: CRMRecord, remapStageId?: number) => {
    crmApi.delete("pipeline-stages", Number(stage.id), remapStageId ? { remapStageId } : undefined).then(() => {
      setStages((items) => items.filter((item) => Number(item.id) !== Number(stage.id)));
    }).catch((err) => setError(err?.response?.data?.detail || "Could not delete stage."));
  };

  const onStageDragEnd = (event: DragEndEvent) => {
    const activeId = Number(event.active.id);
    const overId = Number(event.over?.id);
    if (!activeId || !overId || activeId === overId) return;
    const oldIndex = activeStages.findIndex((stage) => Number(stage.id) === activeId);
    const newIndex = activeStages.findIndex((stage) => Number(stage.id) === overId);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = [...activeStages];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);
    const withPositions: CRMRecord[] = reordered.map((stage, index) => ({ ...stage, position: index + 1 }));
    setStages((items) => items.map((stage) => withPositions.find((item) => Number(item.id) === Number(stage.id)) || stage));
    withPositions.forEach((stage) => crmApi.update("pipeline-stages", Number(stage.id), { position: Number(stage.position) }).catch(() => undefined));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Pipeline Settings" description="Create multiple deal pipelines and maintain each pipeline's custom stages." action="Back to board" onAction={() => window.history.back()} />
      {error || pipelineState.error || stageState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error || pipelineState.error || stageState.error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[20rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Pipelines</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={pipelineName} onChange={(event) => setPipelineName(event.target.value)} placeholder="New pipeline name" />
              <Button onClick={createPipeline}><Plus className="h-4 w-4" /></Button>
            </div>
            <div className="space-y-2">
              {pipelines.map((pipeline) => (
                <button key={String(pipeline.id)} type="button" className={`w-full rounded-md border px-3 py-2 text-left text-sm ${Number(pipeline.id) === activePipelineId ? "border-primary bg-primary/10" : "bg-card"}`} onClick={() => setSelectedPipelineId(Number(pipeline.id))}>
                  <span className="block font-medium">{String(pipeline.name)}</span>
                  <span className="text-xs text-muted-foreground">{pipeline.is_default ? "Default pipeline" : "Custom pipeline"}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Stages</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_7rem_6rem_7rem_7rem_auto] md:items-end">
              <label className="space-y-1 text-sm"><span className="font-medium">Name</span><Input value={String(stageDraft.name || "")} onChange={(event) => setStageDraft((current) => ({ ...current, name: event.target.value }))} /></label>
              <label className="space-y-1 text-sm"><span className="font-medium">Probability</span><Input type="number" value={Number(stageDraft.probability || 0)} onChange={(event) => setStageDraft((current) => ({ ...current, probability: Number(event.target.value) }))} /></label>
              <label className="space-y-1 text-sm"><span className="font-medium">Color</span><Input type="color" value={String(stageDraft.color || "#2563eb")} onChange={(event) => setStageDraft((current) => ({ ...current, color: event.target.value }))} /></label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stageDraft.is_won)} onChange={(event) => setStageDraft((current) => ({ ...current, is_won: event.target.checked, is_lost: event.target.checked ? false : current.is_lost }))} />Won</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stageDraft.is_lost)} onChange={(event) => setStageDraft((current) => ({ ...current, is_lost: event.target.checked, is_won: event.target.checked ? false : current.is_won }))} />Lost</label>
              <Button onClick={createStage}>Add</Button>
            </div>
            <DndContext collisionDetection={closestCorners} onDragEnd={onStageDragEnd}>
              <SortableContext items={activeStages.map((stage) => Number(stage.id))} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {activeStages.map((stage) => (
                    <PipelineStageSettingsRow
                      key={String(stage.id)}
                      stage={stage}
                      stages={activeStages}
                      dealCount={stageDealCounts.get(Number(stage.id)) || 0}
                      onUpdate={updateStage}
                      onDelete={deleteStage}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PipelineStageSettingsRow({ stage, stages, dealCount, onUpdate, onDelete }: { stage: CRMRecord; stages: CRMRecord[]; dealCount: number; onUpdate: (stage: CRMRecord, patch: CRMApiRecord) => void; onDelete: (stage: CRMRecord, remapStageId?: number) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: Number(stage.id) });
  const [remapStageId, setRemapStageId] = useState("");
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`grid gap-2 rounded-md border bg-card p-3 md:grid-cols-[2rem_1fr_7rem_6rem_5rem_5rem_8rem_auto] md:items-center ${isDragging ? "opacity-60" : ""}`}>
      <button type="button" className="rounded p-1 text-muted-foreground hover:bg-muted" {...attributes} {...listeners} aria-label="Reorder stage"><GripVertical className="h-4 w-4" /></button>
      <Input value={String(stage.name || "")} onChange={(event) => onUpdate(stage, { name: event.target.value })} />
      <Input type="number" value={Number(stage.probability || 0)} onChange={(event) => onUpdate(stage, { probability: Number(event.target.value) })} />
      <Input type="color" value={String(stage.color || "#2563eb")} onChange={(event) => onUpdate(stage, { color: event.target.value })} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stage.is_won)} onChange={(event) => onUpdate(stage, { is_won: event.target.checked, is_lost: event.target.checked ? false : Boolean(stage.is_lost) })} />Won</label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stage.is_lost)} onChange={(event) => onUpdate(stage, { is_lost: event.target.checked, is_won: event.target.checked ? false : Boolean(stage.is_won) })} />Lost</label>
      {dealCount ? (
        <select className="h-10 rounded-md border bg-background px-2 text-sm" value={remapStageId} onChange={(event) => setRemapStageId(event.target.value)}>
          <option value="">Remap {dealCount}</option>
          {stages.filter((item) => Number(item.id) !== Number(stage.id)).map((item) => <option key={String(item.id)} value={Number(item.id)}>{String(item.name)}</option>)}
        </select>
      ) : <span className="text-sm text-muted-foreground">No deals</span>}
      <Button variant="outline" size="sm" onClick={() => onDelete(stage, remapStageId ? Number(remapStageId) : undefined)}>Delete</Button>
    </div>
  );
}

function CustomFieldsSettingsPage() {
  const [entity, setEntity] = useState("leads");
  const [fields, setFields] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState<CRMApiRecord>({ entityType: "leads", fieldName: "", fieldKey: "", fieldType: "text", options: "", isRequired: false, isUnique: false, isVisible: true, isFilterable: false, displayOrder: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.list<CRMApiRecord>("custom-fields", { entityType: entity, sort_by: "position", sort_order: "asc", per_page: 100 })
      .then((response) => setFields(response.data.items || []))
      .catch((err) => setError(err?.response?.data?.detail || "Custom fields could not be loaded."))
      .finally(() => setLoading(false));
  };
  useEffect(load, [entity]);
  useEffect(() => setDraft((current) => ({ ...current, entityType: entity, displayOrder: fields.length + 1 })), [entity, fields.length]);
  const patchDraft = (key: string, value: CRMApiRecord[string]) => setDraft((current) => ({ ...current, [key]: value }));
  const payloadForField = (field: CRMApiRecord) => ({
    entityType: field.entityType || field.entity || entity,
    fieldName: field.fieldName || field.label || field.field_name,
    fieldKey: field.fieldKey || field.field_key,
    fieldType: field.fieldType || field.field_type || "text",
    options: parseOptions(field.options ?? field.options_json),
    isRequired: Boolean(field.isRequired ?? field.is_required),
    isUnique: Boolean(field.isUnique ?? field.is_unique),
    isVisible: Boolean(field.isVisible ?? field.is_visible ?? true),
    isFilterable: Boolean(field.isFilterable ?? field.is_filterable),
    displayOrder: Number(field.displayOrder || field.position || 0),
  });
  const createField = () => {
    setError(null);
    const payload = payloadForField(draft);
    if (!payload.fieldName || !payload.fieldKey) {
      setError("Field name and key are required.");
      return;
    }
    crmApi.create<CRMApiRecord>("custom-fields", payload)
      .then((response) => {
        setFields((items) => [...items, response.data]);
        setDraft({ entityType: entity, fieldName: "", fieldKey: "", fieldType: "text", options: "", isRequired: false, isUnique: false, isVisible: true, isFilterable: false, displayOrder: fields.length + 2 });
      })
      .catch((err) => setError(err?.response?.data?.detail || "Could not create custom field."));
  };
  const updateField = (field: CRMApiRecord, patch: CRMApiRecord) => {
    const id = Number(field.id);
    const previous = fields;
    const next = { ...field, ...patch };
    setFields((items) => items.map((item) => Number(item.id) === id ? next : item));
    crmApi.update("custom-fields", id, payloadForField(next)).catch((err) => {
      setFields(previous);
      setError(err?.response?.data?.detail || "Could not update custom field.");
    });
  };
  const deleteField = (field: CRMApiRecord) => {
    crmApi.delete("custom-fields", Number(field.id)).then(() => {
      setFields((items) => items.filter((item) => Number(item.id) !== Number(field.id)));
    }).catch((err) => setError(err?.response?.data?.detail || "Could not delete custom field."));
  };
  const moveField = (field: CRMApiRecord, direction: -1 | 1) => {
    const sorted = [...fields].sort((a, b) => Number(a.displayOrder || a.position || 0) - Number(b.displayOrder || b.position || 0));
    const index = sorted.findIndex((item) => Number(item.id) === Number(field.id));
    const target = index + direction;
    if (target < 0 || target >= sorted.length) return;
    [sorted[index], sorted[target]] = [sorted[target], sorted[index]];
    const reordered: CRMApiRecord[] = sorted.map((item, itemIndex) => ({ ...(item as CRMApiRecord), displayOrder: itemIndex + 1, position: itemIndex + 1 }));
    setFields(reordered);
    reordered.forEach((item) => crmApi.update("custom-fields", Number(item.id), { displayOrder: Number(item.displayOrder) }).catch(() => undefined));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Custom Fields" description="Admin configuration for CRM custom fields, validation, visibility, and filterable columns." action="Add field" onAction={createField} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[12rem_1fr_10rem_1.2fr_7rem_6rem_6rem_6rem_auto] lg:items-end">
          <Field label="Entity"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={entity} onChange={(event) => setEntity(event.target.value)}>{customFieldEntities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
          <Field label="Field name"><Input value={String(draft.fieldName || "")} onChange={(event) => patchDraft("fieldName", event.target.value)} onBlur={() => !draft.fieldKey && patchDraft("fieldKey", slugifyKey(String(draft.fieldName || "")))} /></Field>
          <Field label="Field key"><Input value={String(draft.fieldKey || "")} onChange={(event) => patchDraft("fieldKey", slugifyKey(event.target.value))} /></Field>
          <Field label="Type"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(draft.fieldType || "text")} onChange={(event) => patchDraft("fieldType", event.target.value)}>{customFieldTypes.map((type) => <option key={type} value={type}>{labelFor(type)}</option>)}</select></Field>
          <Field label="Required"><ToggleBox checked={Boolean(draft.isRequired)} onChange={(checked) => patchDraft("isRequired", checked)} /></Field>
          <Field label="Unique"><ToggleBox checked={Boolean(draft.isUnique)} onChange={(checked) => patchDraft("isUnique", checked)} /></Field>
          <Field label="Visible"><ToggleBox checked={Boolean(draft.isVisible ?? true)} onChange={(checked) => patchDraft("isVisible", checked)} /></Field>
          <Field label="Filterable"><ToggleBox checked={Boolean(draft.isFilterable)} onChange={(checked) => patchDraft("isFilterable", checked)} /></Field>
          <Button onClick={createField}>Create</Button>
          {["dropdown", "multi_select"].includes(String(draft.fieldType)) ? <div className="lg:col-span-9"><Field label="Options"><Input value={String(draft.options || "")} onChange={(event) => patchDraft("options", event.target.value)} placeholder="Comma separated options" /></Field></div> : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{customFieldEntities.find((item) => item.value === entity)?.label} Fields</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="text-sm text-muted-foreground">Loading custom fields...</p> : null}
          {fields.map((field) => (
            <div key={String(field.id)} className="grid gap-2 rounded-md border p-3 xl:grid-cols-[5rem_1fr_10rem_10rem_1fr_6rem_6rem_6rem_6rem_auto] xl:items-center">
              <div className="flex gap-1"><Button variant="ghost" size="sm" onClick={() => moveField(field, -1)}><ChevronLeft className="h-4 w-4" /></Button><Button variant="ghost" size="sm" onClick={() => moveField(field, 1)}><ChevronRight className="h-4 w-4" /></Button></div>
              <Input value={String(field.fieldName || field.label || "")} onChange={(event) => updateField(field, { fieldName: event.target.value })} />
              <Input value={String(field.fieldKey || field.field_key || "")} onChange={(event) => updateField(field, { fieldKey: slugifyKey(event.target.value) })} />
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(field.fieldType || field.field_type || "text")} onChange={(event) => updateField(field, { fieldType: event.target.value })}>{customFieldTypes.map((type) => <option key={type} value={type}>{labelFor(type)}</option>)}</select>
              <Input value={optionsText(field.options ?? field.options_json)} onChange={(event) => updateField(field, { options: event.target.value })} placeholder="Options" />
              <ToggleBox checked={Boolean(field.isRequired ?? field.is_required)} onChange={(checked) => updateField(field, { isRequired: checked })} />
              <ToggleBox checked={Boolean(field.isUnique ?? field.is_unique)} onChange={(checked) => updateField(field, { isUnique: checked })} />
              <ToggleBox checked={Boolean(field.isVisible ?? field.is_visible ?? true)} onChange={(checked) => updateField(field, { isVisible: checked })} />
              <ToggleBox checked={Boolean(field.isFilterable ?? field.is_filterable)} onChange={(checked) => updateField(field, { isFilterable: checked })} />
              <Button variant="outline" size="sm" onClick={() => deleteField(field)}>Delete</Button>
            </div>
          ))}
          {!loading && !fields.length ? <p className="text-sm text-muted-foreground">No custom fields configured for this entity yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function ToggleBox({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return <input className="h-5 w-5" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />;
}

function parseOptions(value: unknown) {
  if (Array.isArray(value)) return value.map(String);
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function optionsText(value: unknown) {
  return Array.isArray(value) ? value.join(", ") : String(value || "");
}

function slugifyKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function LeadScoringSettingsPage() {
  const ruleState = useCrmRecords<CRMRecord>("lead-scoring-rules", emptyRecords);
  const [rules, setRules] = useState<CRMRecord[]>([]);
  const [draft, setDraft] = useState<CRMRecord>({ name: "", field: "email", operator: "exists", value: "", points: 10, is_active: true });
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setRules(ruleState.data), [ruleState.data]);

  const createRule = () => {
    if (!String(draft.name || "").trim()) return;
    crmApi.create<CRMApiRecord>("lead-scoring-rules", draft).then((response) => {
      setRules((items) => [...items, normalizeApiRecord("lead-scoring-rules", response.data) as CRMRecord]);
      setDraft({ name: "", field: "email", operator: "exists", value: "", points: 10, is_active: true });
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create scoring rule."));
  };

  const updateRule = (rule: CRMRecord, patch: CRMApiRecord) => {
    const previous = rules;
    setRules((items) => items.map((item) => Number(item.id) === Number(rule.id) ? ({ ...item, ...patch } as CRMRecord) : item));
    crmApi.update("lead-scoring-rules", Number(rule.id), patch).catch((err) => {
      setRules(previous);
      setError(err?.response?.data?.detail || "Could not update scoring rule.");
    });
  };

  const deleteRule = (rule: CRMRecord) => {
    crmApi.delete("lead-scoring-rules", Number(rule.id)).then(() => setRules((items) => items.filter((item) => Number(item.id) !== Number(rule.id)))).catch((err) => setError(err?.response?.data?.detail || "Could not delete scoring rule."));
  };

  const recalculateAll = () => {
    setMessage("");
    setError(null);
    crmApi.recalculateLeadScores().then((response) => setMessage(`Recalculated ${response.data.updated} automatic leads.`)).catch((err) => setError(err?.response?.data?.detail || "Could not recalculate lead scores."));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Lead Scoring" description="Configure automatic 0-100 CRM lead scoring rules and keep manual overrides when needed." action="Recalculate all" onAction={recalculateAll} />
      {error || ruleState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error || ruleState.error}</div> : null}
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{message}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader><CardTitle>Scoring Rules</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {ruleState.loading ? <p className="text-sm text-muted-foreground">Loading scoring rules...</p> : null}
            {rules.map((rule) => (
              <div key={String(rule.id)} className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_9rem_8rem_8rem_6rem_6rem_auto] md:items-center">
                <Input value={String(rule.name || "")} onChange={(event) => updateRule(rule, { name: event.target.value })} />
                <Input value={String(rule.field || "")} onChange={(event) => updateRule(rule, { field: event.target.value })} />
                <RuleOperatorSelect value={String(rule.operator || "exists")} onChange={(operator) => updateRule(rule, { operator })} />
                <Input value={String(rule.value || "")} onChange={(event) => updateRule(rule, { value: event.target.value })} />
                <Input type="number" value={Number(rule.points || 0)} onChange={(event) => updateRule(rule, { points: Number(event.target.value) })} />
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(rule.is_active ?? rule.isActive ?? true)} onChange={(event) => updateRule(rule, { is_active: event.target.checked })} />Active</label>
                <Button variant="outline" size="sm" onClick={() => deleteRule(rule)}>Delete</Button>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Add Rule</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={String(draft.name || "")} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Field"><Input value={String(draft.field || "")} onChange={(event) => setDraft((current) => ({ ...current, field: event.target.value }))} /></Field>
            <Field label="Operator"><RuleOperatorSelect value={String(draft.operator || "exists")} onChange={(operator) => setDraft((current) => ({ ...current, operator }))} /></Field>
            <Field label="Value"><Input value={String(draft.value || "")} onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))} /></Field>
            <Field label="Points"><Input type="number" value={Number(draft.points || 0)} onChange={(event) => setDraft((current) => ({ ...current, points: Number(event.target.value) }))} /></Field>
            <Button className="w-full" onClick={createRule}>Add scoring rule</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RuleOperatorSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <select className="h-10 rounded-md border bg-background px-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
      {["exists", "not_exists", "equals", "not_equals", "contains", "gt", "gte", "lt", "lte", "older_than_days"].map((operator) => <option key={operator} value={operator}>{operator}</option>)}
    </select>
  );
}

type CalendarView = "month" | "week" | "day" | "agenda";
type CalendarFilters = { ownerId: string; type: string; status: string };

function CRMCalendarPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<CalendarView>("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [events, setEvents] = useState<CRMCalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<CalendarFilters>({ ownerId: "all", type: "all", status: "all" });
  const [selected, setSelected] = useState<CRMCalendarEvent | null>(null);
  const [createDate, setCreateDate] = useState<Date | null>(null);
  const range = useMemo(() => calendarRange(cursor, view), [cursor, view]);

  const loadCalendar = () => {
    setLoading(true);
    setError(null);
    crmApi
      .calendar({
        startDate: range.start.toISOString(),
        endDate: range.end.toISOString(),
        ownerId: filters.ownerId === "all" ? undefined : Number(filters.ownerId),
        type: filters.type === "all" ? undefined : filters.type,
      })
      .then((response) => setEvents(response.data.items))
      .catch((err) => setError(err?.response?.data?.detail || "CRM calendar is not reachable."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCalendar();
  }, [range.start.toISOString(), range.end.toISOString(), filters.ownerId, filters.type]);

  const visibleEvents = useMemo(() => {
    return events.filter((event) => filters.status === "all" || String(event.status || "").toLowerCase() === filters.status.toLowerCase());
  }, [events, filters.status]);
  const ownerIds = useMemo(() => uniqueCalendarValues(events.map((event) => event.ownerId).filter(Boolean).map(String)), [events]);
  const statuses = useMemo(() => uniqueCalendarValues(events.map((event) => String(event.status || "")).filter(Boolean)), [events]);

  const moveCursor = (direction: number) => {
    setCursor((date) => {
      const next = new Date(date);
      if (view === "month") next.setMonth(next.getMonth() + direction);
      if (view === "week") next.setDate(next.getDate() + direction * 7);
      if (view === "day" || view === "agenda") next.setDate(next.getDate() + direction);
      return next;
    });
  };

  const rescheduleEvent = (event: CRMCalendarEvent, targetDate: Date) => {
    const originalStart = new Date(event.start);
    const originalEnd = new Date(event.end || event.start);
    const nextStart = new Date(targetDate);
    nextStart.setHours(originalStart.getHours(), originalStart.getMinutes(), 0, 0);
    const duration = Math.max(originalEnd.getTime() - originalStart.getTime(), 30 * 60 * 1000);
    const nextEnd = new Date(nextStart.getTime() + duration);
    const patch = calendarPatchFor(event, nextStart, nextEnd);
    setEvents((items) => items.map((item) => (item.id === event.id ? { ...item, start: nextStart.toISOString(), end: nextEnd.toISOString() } : item)));
    crmApi.update(event.source, event.recordId, patch).catch(() => {
      setError("Could not reschedule the calendar event.");
      loadCalendar();
    });
  };

  const onDragEnd = (event: DragEndEvent) => {
    if (!event.over) return;
    const calendarEvent = visibleEvents.find((item) => item.id === event.active.id);
    const targetDate = parseLocalDateKey(String(event.over.id).replace("day-", ""));
    if (calendarEvent && !Number.isNaN(targetDate.getTime())) rescheduleEvent(calendarEvent, targetDate);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Calendar" description="Tasks, meetings, calls, follow-ups, quotation expiries, and expected deal closes in one CRM schedule." action="Create activity" onAction={() => setCreateDate(new Date())} />
      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="icon" onClick={() => moveCursor(-1)} aria-label="Previous period"><ChevronLeft className="h-4 w-4" /></Button>
              <Button variant="outline" size="icon" onClick={() => moveCursor(1)} aria-label="Next period"><ChevronRight className="h-4 w-4" /></Button>
              <Button variant="outline" onClick={() => setCursor(new Date())}>Today</Button>
              <h2 className="px-2 text-lg font-semibold">{calendarTitle(cursor, view)}</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => navigate("/crm/calendar-integrations")}><CalendarDays className="h-4 w-4" />Integrations</Button>
              {(["month", "week", "day", "agenda"] as CalendarView[]).map((item) => (
                <Button key={item} variant={view === item ? "default" : "outline"} size="sm" onClick={() => setView(item)}>{item[0].toUpperCase() + item.slice(1)}</Button>
              ))}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <FilterSelect label="Owner" value={filters.ownerId} values={ownerIds} onChange={(ownerId) => setFilters((current) => ({ ...current, ownerId }))} allLabel="All owners" />
            <FilterSelect label="Type" value={filters.type} values={["task", "meeting", "call", "follow_up", "quotation", "deal"]} onChange={(type) => setFilters((current) => ({ ...current, type }))} allLabel="All types" />
            <FilterSelect label="Status" value={filters.status} values={statuses} onChange={(status) => setFilters((current) => ({ ...current, status }))} allLabel="All statuses" />
            <div className="flex items-end">
              <Button variant="outline" className="w-full" onClick={() => setFilters({ ownerId: "all", type: "all", status: "all" })}><X className="h-4 w-4" />Clear</Button>
            </div>
          </div>
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
          {loading ? <div className="rounded-md border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">Loading CRM calendar...</div> : null}
          <DndContext onDragEnd={onDragEnd}>
            {view === "agenda" ? (
              <CalendarAgenda events={visibleEvents} onOpen={setSelected} />
            ) : view === "month" ? (
              <CalendarMonth cursor={cursor} events={visibleEvents} onCreate={setCreateDate} onOpen={setSelected} />
            ) : (
              <CalendarTimeGrid cursor={cursor} view={view} events={visibleEvents} onCreate={setCreateDate} onOpen={setSelected} />
            )}
          </DndContext>
        </CardContent>
      </Card>
      {selected ? <CalendarEventDialog event={selected} onClose={() => setSelected(null)} onOpenRecord={(path) => navigate(path)} onComplete={() => markCalendarTaskComplete(selected, setEvents, setError)} onSynced={loadCalendar} /> : null}
      {createDate ? <CalendarCreateDialog date={createDate} onClose={() => setCreateDate(null)} onCreated={() => { setCreateDate(null); loadCalendar(); }} /> : null}
    </div>
  );
}

function CalendarMonth({ cursor, events, onCreate, onOpen }: { cursor: Date; events: CRMCalendarEvent[]; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const days = monthDays(cursor);
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className="grid grid-cols-7 border-b bg-muted/40 text-xs font-medium text-muted-foreground">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <div key={day} className="px-3 py-2">{day}</div>)}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day) => (
          <CalendarDayCell key={day.toISOString()} date={day} muted={day.getMonth() !== cursor.getMonth()} events={eventsForDay(events, day)} onCreate={onCreate} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}

function CalendarTimeGrid({ cursor, view, events, onCreate, onOpen }: { cursor: Date; view: "week" | "day"; events: CRMCalendarEvent[]; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const days = view === "day" ? [startOfDay(cursor)] : weekDays(cursor);
  return (
    <div className={`grid gap-3 ${view === "day" ? "md:grid-cols-1" : "md:grid-cols-7"}`}>
      {days.map((day) => (
        <CalendarDayCell key={day.toISOString()} date={day} events={eventsForDay(events, day)} onCreate={onCreate} onOpen={onOpen} tall />
      ))}
    </div>
  );
}

function CalendarDayCell({ date, events, muted = false, tall = false, onCreate, onOpen }: { date: Date; events: CRMCalendarEvent[]; muted?: boolean; tall?: boolean; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: `day-${dateKey(date)}` });
  return (
    <section ref={setNodeRef} className={`min-h-36 border-r border-b p-2 last:border-r-0 ${tall ? "min-h-[28rem]" : ""} ${muted ? "bg-muted/20 text-muted-foreground" : "bg-background"} ${isOver ? "ring-2 ring-primary/50" : ""}`}>
      <button type="button" className="mb-2 flex w-full items-center justify-between rounded px-1 py-0.5 text-left text-xs hover:bg-muted" onClick={() => onCreate(date)}>
        <span className="font-medium">{date.toLocaleDateString(undefined, { weekday: tall ? "short" : undefined, month: tall ? "short" : undefined, day: "numeric" })}</span>
        <Plus className="h-3.5 w-3.5" />
      </button>
      <div className="space-y-1">
        {events.map((event) => <CalendarEventPill key={event.id} event={event} onOpen={onOpen} />)}
      </div>
    </section>
  );
}

function CalendarEventPill({ event, onOpen }: { event: CRMCalendarEvent; onOpen: (event: CRMCalendarEvent) => void }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: event.id });
  return (
    <button
      ref={setNodeRef}
      type="button"
      style={{ borderLeftColor: event.color, transform: CSS.Transform.toString(transform) }}
      className="w-full rounded border border-l-4 bg-card px-2 py-1 text-left text-xs shadow-sm hover:bg-muted"
      onClick={() => onOpen(event)}
      {...attributes}
      {...listeners}
    >
      <span className="block truncate font-medium">{event.title}</span>
      <span className="block truncate text-muted-foreground">{timeLabel(event.start)} / {event.category}</span>
      {event.source === "meetings" && event.syncStatus ? <span className="mt-1 inline-flex rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">{labelFor(event.syncStatus)}</span> : null}
    </button>
  );
}

function CalendarAgenda({ events, onOpen }: { events: CRMCalendarEvent[]; onOpen: (event: CRMCalendarEvent) => void }) {
  if (!events.length) return <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">No CRM calendar items in this range.</div>;
  return (
    <div className="divide-y rounded-lg border">
      {events.map((event) => (
        <button key={event.id} type="button" className="grid w-full gap-3 p-4 text-left hover:bg-muted/50 md:grid-cols-[9rem_1fr_8rem_8rem_8rem]" onClick={() => onOpen(event)}>
          <span className="text-sm font-medium">{formatDate(event.start)}</span>
          <span><span className="block font-medium">{event.title}</span><span className="text-sm text-muted-foreground">{timeLabel(event.start)} / {event.category}</span></span>
          <Badge className={statusColor(String(event.status || event.type))}>{event.status || event.type}</Badge>
          <Badge variant="outline">{event.source === "meetings" ? labelFor(event.syncStatus || "not_synced") : "-"}</Badge>
          <span className="text-sm text-muted-foreground">Owner {event.ownerId || "-"}</span>
        </button>
      ))}
    </div>
  );
}

function CalendarEventDialog({ event, onClose, onOpenRecord, onComplete, onSynced }: { event: CRMCalendarEvent; onClose: () => void; onOpenRecord: (path: string) => void; onComplete: () => void; onSynced: () => void }) {
  const path = relatedCalendarPath(event);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const syncMeeting = () => {
    setSyncing(true);
    setError(null);
    crmApi.syncMeeting(event.recordId).then(() => onSynced()).catch((err) => setError(err?.response?.data?.detail || "Meeting could not be synced.")).finally(() => setSyncing(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div><CardTitle>{event.title}</CardTitle><p className="text-sm text-muted-foreground">{formatDate(event.start)} at {timeLabel(event.start)}</p></div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-3">
            <InfoTile label="Type" value={event.category || event.type} />
            <InfoTile label="Status" value={event.status || "-"} />
            <InfoTile label="Owner" value={String(event.ownerId || "-")} />
          </div>
          {event.source === "meetings" ? (
            <div className="grid gap-3 md:grid-cols-3">
              <InfoTile label="Calendar sync" value={event.syncStatus || "not_synced"} />
              <InfoTile label="Provider" value={event.externalProvider || "-"} />
              <InfoTile label="External event" value={event.externalEventId || "-"} />
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {event.source === "tasks" ? <Button onClick={onComplete}><CheckCircle2 className="h-4 w-4" />Mark complete</Button> : null}
            {event.source === "meetings" ? <Button onClick={syncMeeting} disabled={syncing}><CalendarDays className="h-4 w-4" />{syncing ? "Syncing..." : "Sync to calendar"}</Button> : null}
            {path ? <Button variant="outline" onClick={() => onOpenRecord(path)}>Open related record</Button> : null}
            <Button variant="outline" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CalendarCreateDialog({ date, onClose, onCreated }: { date: Date; onClose: () => void; onCreated: () => void }) {
  const [kind, setKind] = useState<"tasks" | "meetings">("tasks");
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("To Do");
  const [time, setTime] = useState("10:00");
  const [syncToCalendar, setSyncToCalendar] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = () => {
    const start = dateWithTime(date, time);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const payload = kind === "tasks"
      ? { title: title || "New task", due_date: start.toISOString(), status }
      : { title: title || "New meeting", start_time: start.toISOString(), end_time: end.toISOString(), status: "Scheduled", syncToCalendar };
    setSaving(true);
    setError(null);
    crmApi.create(kind, payload).then(onCreated).catch((err) => setError(err?.response?.data?.detail || "Could not create calendar item.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>Create calendar item</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm"><span className="font-medium">Type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={kind} onChange={(event) => setKind(event.target.value as "tasks" | "meetings")}><option value="tasks">Task</option><option value="meetings">Meeting</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Time</span><Input type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label>
          </div>
          <label className="space-y-1 text-sm"><span className="font-medium">Title</span><Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Follow up with customer" /></label>
          {kind === "tasks" ? <label className="space-y-1 text-sm"><span className="font-medium">Status</span><Input value={status} onChange={(event) => setStatus(event.target.value)} /></label> : null}
          {kind === "meetings" ? <label className="flex items-center gap-2 rounded-md border bg-muted/25 p-3 text-sm"><input type="checkbox" checked={syncToCalendar} onChange={(event) => setSyncToCalendar(event.target.checked)} />Sync to connected calendar</label> : null}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving}>{saving ? "Saving..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CRMListPage({ kind }: { kind: CRMPageKind }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [selectedView, setSelectedView] = useState(savedViews[0]);
  const [filters, setFilters] = useState<CRMFilters>({ owner: "all", status: "all", type: "all", territory: "all" });
  const [showFilters, setShowFilters] = useState(kind === "calendar");
  const [selectedRecord, setSelectedRecord] = useState<CRMRecord | null>(null);
  const apiEntity = apiEntityForKind[kind];
  const apiParams = filters.territory !== "all" ? { territoryId: Number(filters.territory) } : undefined;
  const { data: apiRows, loading, error } = useCrmRecords(apiEntity, emptyRecords, apiParams);
  const [localRows, setLocalRows] = useState<CRMRecord[]>([]);
  const [contacts, setContacts] = useState<CRMRecord[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [importExportError, setImportExportError] = useState<string | null>(null);
  const records = localRows.length ? localRows : apiRows;
  const rows = useMemo(() => filterRecords(records, search, selectedView, filters), [records, search, selectedView, filters]);
  const owners = useMemo(() => uniqueValues(records, "owner"), [records]);
  const statuses = useMemo(() => uniqueValues(records, "status"), [records]);
  const types = useMemo(() => uniqueValues(records, "type"), [records]);
  const territories = useMemo(() => uniqueValues(records, "territoryId"), [records]);

  useEffect(() => {
    setLocalRows([]);
    setSelectedRecord(null);
  }, [kind]);

  const createRecord = (draft: CRMRecord, customFields?: CRMApiRecord) => {
    const nextId = records.length + 1;
    const title = pageTitles[kind].replace("CRM ", "").replace(/s$/, "");
    const record = { id: nextId, ...defaultRecordFor(kind, nextId, title), ...draft };
    if (apiEntity) {
      setCreateSaving(true);
      setCreateError(null);
      crmApi
        .create<CRMApiRecord>(apiEntity, { ...createPayloadForKind(kind, record), customFields: customFields || {} })
        .then((response) => {
          const created = normalizeApiRecord(kindlessEntity(apiEntity), response.data);
          setLocalRows((items) => [created, ...items.filter((item) => Number(item.id) !== Number(created.id)), ...apiRows.filter((item) => Number(item.id) !== Number(created.id))]);
          setSelectedRecord(created);
          setShowCreate(false);
        })
        .catch((err) => setCreateError(err?.response?.data?.detail || "CRM record could not be created."))
        .finally(() => setCreateSaving(false));
      return;
    }
    setLocalRows((items) => [record, ...records, ...items]);
    setSelectedRecord(record);
    setShowCreate(false);
  };

  const saveInlineCell = (row: CRMRecord, key: string, value: string | number | boolean | null) => {
    if (!apiEntity || !row.id) return Promise.resolve();
    const config = listInlineEditConfig[kind]?.[key];
    if (!config) return Promise.resolve();
    const previous = records;
    const nextRows = records.map((item) => (Number(item.id) === Number(row.id) ? { ...item, [key]: value } : item));
    setLocalRows(nextRows);
    setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? { ...current, [key]: value } : current));
    const payloadValue = normalizeInlineValue(config, value);
    return crmApi.update(apiEntity, Number(row.id), { [config.apiField]: payloadValue }).catch((err) => {
      setLocalRows(previous);
      setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? row : current));
      throw new Error(err?.response?.data?.detail || "Inline update failed.");
    });
  };

  const importRows = (items: CRMRecord[]) => {
    if (!apiEntity) {
      setLocalRows(items);
      return;
    }
    setImportExportError(null);
    crmApi
      .importRows<{ created: number; items?: CRMApiRecord[]; errors?: Array<{ row: number; error: string }> }>(apiEntity, items as CRMApiRecord[])
      .then((response) => {
        if (response.data.errors?.length) {
          setImportExportError(response.data.errors.map((item) => `Row ${item.row}: ${item.error}`).join("; "));
          return;
        }
        const imported = (response.data.items || []).map((item) => normalizeApiRecord(kindlessEntity(apiEntity), item));
        setLocalRows([...imported, ...records]);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "CRM import failed."));
  };

  const exportServerRows = () => {
    if (!apiEntity) {
      exportRows(`${pageTitles[kind].toLowerCase().replace(/\s+/g, "-")}.csv`, rows);
      return;
    }
    setImportExportError(null);
    crmApi
      .exportEntity(apiEntity)
      .then((response) => {
        const url = URL.createObjectURL(response.data);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${apiEntity}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "CRM export failed."));
  };

  return (
    <div className="space-y-6">
      <PageHeader title={pageTitles[kind]} description={descriptionFor(kind)} action={actionFor(kind)} onAction={() => setShowCreate(true)} />
      <Toolbar
        search={search}
        onSearch={setSearch}
        selectedView={selectedView}
        onViewChange={setSelectedView}
        onToggleFilters={() => setShowFilters((value) => !value)}
        contacts={contacts}
        onImportContacts={importRows}
        onExportServer={exportServerRows}
        importLabel={`Import ${pageTitles[kind].replace("CRM ", "")}`}
        exportLabel={`Export ${pageTitles[kind].replace("CRM ", "")}`}
      />
      {importExportError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{importExportError}</div> : null}
      {showFilters ? (
        <FilterPanel
          filters={filters}
          onChange={setFilters}
          owners={owners}
          statuses={statuses}
          types={types}
          territories={territories}
          onClear={() => setFilters({ owner: "all", status: "all", type: "all", territory: "all" })}
        />
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <SmartCRMTable rows={rows} title={pageTitles[kind]} kind={kind} onSelect={setSelectedRecord} onOpen={detailPathFor(kind) ? (row) => navigate(`${detailPathFor(kind)}/${row.id}`) : undefined} onInlineSave={saveInlineCell} onBulkDelete={apiEntity ? (selectedRows) => Promise.all(selectedRows.map((row) => crmApi.delete(apiEntity, Number(row.id)))).then(() => {
          const selectedIds = new Set(selectedRows.map((row) => Number(row.id)));
          setLocalRows(records.filter((row) => !selectedIds.has(Number(row.id))));
          setSelectedRecord(null);
        }) : undefined} loading={loading} error={error} />
        <RecordPanel record={selectedRecord || rows[0] || null} kind={kind} />
      </div>
      {showCreate ? <CreateRecordDialog kind={kind} saving={createSaving} error={createError} onClose={() => setShowCreate(false)} onCreate={createRecord} /> : null}
    </div>
  );
}

function ApprovalSettingsPage() {
  const [workflows, setWorkflows] = useState<CRMApprovalWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.approvalWorkflows().then((response) => setWorkflows(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Approval workflows could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const toggleWorkflow = (workflow: CRMApprovalWorkflow) => {
    crmApi.updateApprovalWorkflow(Number(workflow.id), { isActive: !workflow.isActive }).then((response) => {
      setWorkflows((items) => items.map((item) => (Number(item.id) === Number(workflow.id) ? response.data : item)));
    }).catch((err) => setError(err?.response?.data?.detail || "Workflow could not be updated."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Approval Settings" description={descriptionFor("approvalSettings")} action="Create workflow" onAction={() => setShowCreate(true)} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading approval workflows...</div> : null}
      <div className="grid gap-4">
        {workflows.map((workflow) => (
          <Card key={workflow.id}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_11rem_10rem_9rem] lg:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{workflow.name}</p>
                  <Badge className={workflow.isActive ? statusColor("Active") : statusColor("Inactive")}>{workflow.isActive ? "Active" : "Inactive"}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{labelFor(String(workflow.entityType))} / {labelFor(String(workflow.triggerType))} / {(workflow.steps || []).length} step(s)</p>
                <p className="mt-1 text-xs text-muted-foreground">Conditions {JSON.stringify(workflow.conditions || {})}</p>
              </div>
              <Badge variant="outline">{labelFor(String(workflow.entityType))}</Badge>
              <span className="text-sm text-muted-foreground">{labelFor(String(workflow.triggerType))}</span>
              <Button variant="outline" onClick={() => toggleWorkflow(workflow)}>{workflow.isActive ? "Deactivate" : "Activate"}</Button>
            </CardContent>
          </Card>
        ))}
        {!loading && !workflows.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No approval workflows configured yet.</CardContent></Card> : null}
      </div>
      {showCreate ? <ApprovalWorkflowDialog onClose={() => setShowCreate(false)} onCreated={(workflow) => { setWorkflows((items) => [workflow, ...items]); setShowCreate(false); }} /> : null}
    </div>
  );
}

function ApprovalWorkflowDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (workflow: CRMApprovalWorkflow) => void }) {
  const [draft, setDraft] = useState({
    name: "High value deal approval",
    entityType: "deal",
    triggerType: "manual",
    conditions: "{\"minAmount\":1000000}",
    approverType: "user",
    approverId: "1",
    actionOnReject: "stop",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const patch = (key: string, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  const submit = () => {
    setSaving(true);
    setError(null);
    let conditions: CRMApiRecord = {};
    try {
      conditions = draft.conditions.trim() ? JSON.parse(draft.conditions) : {};
    } catch {
      setSaving(false);
      setError("Conditions must be valid JSON.");
      return;
    }
    crmApi.createApprovalWorkflow({
      name: draft.name,
      entityType: draft.entityType,
      triggerType: draft.triggerType,
      conditions,
      isActive: true,
      steps: [{ stepOrder: 1, approverType: draft.approverType, approverId: draft.approverType === "manager" ? null : Number(draft.approverId || 0), actionOnReject: draft.actionOnReject }],
    }).then((response) => onCreated(response.data)).catch((err) => setError(err?.response?.data?.detail || "Workflow could not be created.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Create Approval Workflow</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm"><span className="font-medium">Name</span><Input value={draft.name} onChange={(event) => patch("name", event.target.value)} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Entity</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.entityType} onChange={(event) => patch("entityType", event.target.value)}><option value="deal">Deal</option><option value="quotation">Quotation</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Trigger</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.triggerType} onChange={(event) => patch("triggerType", event.target.value)}><option value="manual">Manual submit</option><option value="discount">Discount approval</option><option value="stage">Stage approval</option><option value="high-value">High-value deal</option><option value="contract-price">Contract/price approval</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Approver type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.approverType} onChange={(event) => patch("approverType", event.target.value)}><option value="user">User</option><option value="role">Role</option><option value="manager">Manager</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Approver ID</span><Input type="number" value={draft.approverId} disabled={draft.approverType === "manager"} onChange={(event) => patch("approverId", event.target.value)} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Reject action</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.actionOnReject} onChange={(event) => patch("actionOnReject", event.target.value)}><option value="stop">Stop</option><option value="send_back">Send back</option></select></label>
          </div>
          <label className="space-y-1 text-sm"><span className="font-medium">Conditions JSON</span><textarea className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={draft.conditions} onChange={(event) => patch("conditions", event.target.value)} /></label>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving}>{saving ? "Creating..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function MyApprovalsPage() {
  const [approvals, setApprovals] = useState<CRMApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.myPendingApprovals().then((response) => setApprovals(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Pending approvals could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const decide = (approval: CRMApprovalRequest, approve: boolean) => {
    const comments = window.prompt(approve ? "Approval comments" : "Rejection comments") || "";
    const action = approve ? crmApi.approve : crmApi.reject;
    action(Number(approval.id), { comments }).then(load).catch((err) => setError(err?.response?.data?.detail || "Approval decision could not be saved."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="My Approvals" description={descriptionFor("myApprovals")} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading pending approvals...</div> : null}
      <div className="grid gap-4">
        {approvals.map((approval) => (
          <Card key={approval.id}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_9rem_9rem_12rem] lg:items-center">
              <div>
                <p className="font-semibold">{approval.workflow?.name || "CRM approval"}</p>
                <p className="text-sm text-muted-foreground">{labelFor(approval.entityType)} #{approval.entityId} submitted {formatDate(approval.submittedAt || "")}</p>
              </div>
              <Badge className={statusColor(approval.status)}>{approval.status}</Badge>
              <Badge variant="outline">{labelFor(approval.entityType)}</Badge>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => decide(approval, true)}><CheckCircle2 className="h-4 w-4" />Approve</Button>
                <Button size="sm" variant="outline" onClick={() => decide(approval, false)}><X className="h-4 w-4" />Reject</Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {!loading && !approvals.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No approvals are waiting on you.</CardContent></Card> : null}
      </div>
    </div>
  );
}

function DuplicateManagementPage() {
  const [entityType, setEntityType] = useState("contact");
  const [groups, setGroups] = useState<CRMDuplicateGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<CRMDuplicateGroup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.duplicates({ entityType }).then((response) => setGroups(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Duplicate scan could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, [entityType]);
  const scanAll = () => {
    setLoading(true);
    setError(null);
    crmApi.scanDuplicates().then((response) => setGroups(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Duplicate scan failed.")).finally(() => setLoading(false));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Duplicate Management" description={descriptionFor("duplicates")} action="Scan all" onAction={scanAll} />
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div className="flex gap-2">
            {["lead", "contact", "account"].map((type) => (
              <Button key={type} type="button" variant={entityType === type ? "default" : "outline"} onClick={() => setEntityType(type)}>{labelFor(type)}</Button>
            ))}
          </div>
          <Badge variant="outline">{groups.length} duplicate group(s)</Badge>
        </CardContent>
      </Card>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Scanning CRM records...</div> : null}
      <div className="grid gap-4">
        {groups.map((group) => (
          <Card key={String(group.id)}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_8rem_12rem] lg:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{group.records.map((record) => duplicateRecordTitle(record, group.entityType)).join(" / ")}</p>
                  <Badge className={group.score >= 90 ? statusColor("High") : statusColor("Medium")}>{group.score}% match</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{group.reasons.join(", ") || "Possible duplicate"}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {group.matchingFields.map((field) => <Badge key={field} variant="outline">{labelFor(field)}</Badge>)}
                </div>
              </div>
              <Badge variant="outline">{labelFor(group.entityType)}</Badge>
              <Button onClick={() => setSelectedGroup(group)}><GitMerge className="h-4 w-4" />Merge</Button>
            </CardContent>
          </Card>
        ))}
        {!loading && !groups.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No duplicate groups found for this scope.</CardContent></Card> : null}
      </div>
      {selectedGroup ? <MergeWizardModal group={selectedGroup} onClose={() => setSelectedGroup(null)} onMerged={() => { setSelectedGroup(null); load(); }} /> : null}
    </div>
  );
}

function CalendarIntegrationsPage() {
  const [items, setItems] = useState<CRMApiRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.calendarIntegrations().then((response) => setItems(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Calendar integrations could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const connect = (provider: "google" | "outlook" | "mock") => {
    setMessage(null);
    setError(null);
    crmApi
      .connectCalendarIntegration({ provider, mock: true })
      .then(() => {
        setMessage(`${provider === "mock" ? "Development" : labelFor(provider)} calendar connected with placeholder OAuth settings.`);
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Calendar could not be connected."));
  };
  const disconnect = (id: number) => {
    crmApi.disconnectCalendarIntegration(id).then(() => { setMessage("Calendar integration disconnected."); load(); }).catch((err) => setError(err?.response?.data?.detail || "Calendar could not be disconnected."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Calendar Integrations" description="Connect CRM meetings to external calendars. OAuth adapters are isolated behind provider settings and tokens are never returned to the browser." action="Connect Mock" onAction={() => connect("mock")} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Google Calendar</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Uses minimal calendar event scopes once OAuth client settings are configured.</p>
            <Button className="w-full" onClick={() => connect("google")}><CalendarDays className="h-4 w-4" />Connect Google Calendar</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Outlook Calendar</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Ready for Microsoft OAuth token exchange and Graph Calendar events.</p>
            <Button className="w-full" onClick={() => connect("outlook")}><CalendarDays className="h-4 w-4" />Connect Outlook</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Development Provider</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Creates local external event IDs for testing sync flows without third-party credentials.</p>
            <Button className="w-full" variant="outline" onClick={() => connect("mock")}><CalendarDays className="h-4 w-4" />Connect Mock</Button>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Connected Calendars</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="text-sm text-muted-foreground">Loading integrations...</p> : null}
          {items.map((item) => (
            <div key={String(item.id)} className="grid gap-3 rounded-md border p-4 md:grid-cols-[1fr_8rem_12rem_auto] md:items-center">
              <div><p className="font-medium">{labelFor(String(item.provider || "calendar"))}</p><p className="text-sm text-muted-foreground">User {String(item.userId || item.user_id || "-")} / scopes {(Array.isArray(item.scopes) ? item.scopes.join(", ") : "calendar.events")}</p></div>
              <Badge className={statusColor(item.isActive === false ? "Inactive" : "Active")}>{item.isActive === false ? "Inactive" : "Active"}</Badge>
              <span className="text-sm text-muted-foreground">Expires {formatDate(String(item.expiresAt || "")) || "not set"}</span>
              <Button variant="outline" size="sm" onClick={() => disconnect(Number(item.id))}>Disconnect</Button>
            </div>
          ))}
          {!loading && !items.length ? <p className="text-sm text-muted-foreground">No calendar integrations connected yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function WebhookSettingsPage() {
  const [webhooks, setWebhooks] = useState<CRMApiRecord[]>([]);
  const [events, setEvents] = useState<string[]>([]);
  const [selected, setSelected] = useState<CRMApiRecord | null>(null);
  const [deliveries, setDeliveries] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState({ name: "", url: "", secret: "", events: ["lead.created"] as string[], isActive: true });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.webhooks().then((response) => { setWebhooks(response.data.items || []); setEvents(response.data.events || []); }).catch((err) => setError(err?.response?.data?.detail || "Webhooks could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  useEffect(() => {
    if (!selected?.id) {
      setDeliveries([]);
      return;
    }
    crmApi.webhookDeliveries(Number(selected.id)).then((response) => setDeliveries(response.data.items || [])).catch(() => setDeliveries([]));
  }, [selected?.id]);
  const toggleEvent = (event: string) => {
    setDraft((current) => ({ ...current, events: current.events.includes(event) ? current.events.filter((item) => item !== event) : [...current.events, event].sort() }));
  };
  const resetDraft = () => setDraft({ name: "", url: "", secret: "", events: ["lead.created"], isActive: true });
  const create = () => {
    if (!draft.name.trim() || !draft.url.trim()) return;
    setError(null);
    crmApi.createWebhook(draft).then((response) => { setMessage("Webhook created. Secret is masked after creation."); setSelected(response.data); resetDraft(); load(); }).catch((err) => setError(err?.response?.data?.detail || "Webhook could not be created."));
  };
  const toggleActive = (webhook: CRMApiRecord) => {
    crmApi.updateWebhook(Number(webhook.id), { isActive: !(webhook.isActive ?? webhook.is_active) }).then(load).catch((err) => setError(err?.response?.data?.detail || "Webhook could not be updated."));
  };
  const test = (webhook: CRMApiRecord) => {
    setError(null);
    crmApi.testWebhook(Number(webhook.id)).then((response) => { setMessage(`Test delivery ${String(response.data.status || "queued")}.`); setSelected(webhook); crmApi.webhookDeliveries(Number(webhook.id)).then((res) => setDeliveries(res.data.items || [])); }).catch((err) => setError(err?.response?.data?.detail || "Webhook test failed."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Webhook Settings" description="Send signed CRM automation events to Zapier, n8n, and integration endpoints." action="Create webhook" onAction={create} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[26rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Create Webhook</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Endpoint URL"><Input value={draft.url} onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))} placeholder="https://hooks.example.com/crm" /></Field>
            <Field label="Secret">
              <Input value={draft.secret} onChange={(event) => setDraft((current) => ({ ...current, secret: event.target.value }))} placeholder="Leave blank to generate" />
            </Field>
            <label className="flex items-center gap-2 rounded-md border bg-muted/25 p-3 text-sm"><input type="checkbox" checked={draft.isActive} onChange={(event) => setDraft((current) => ({ ...current, isActive: event.target.checked }))} />Active</label>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="grid max-h-72 gap-2 overflow-y-auto rounded-md border p-3">
                {events.map((event) => (
                  <label key={event} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.events.includes(event)} onChange={() => toggleEvent(event)} />{event}</label>
                ))}
              </div>
            </div>
            <div className="flex gap-2"><Button className="flex-1" onClick={create}><Plus className="h-4 w-4" />Create</Button><Button variant="outline" onClick={resetDraft}>Reset</Button></div>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Configured Webhooks</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {loading ? <p className="text-sm text-muted-foreground">Loading webhooks...</p> : null}
              {webhooks.map((webhook) => (
                <div key={String(webhook.id)} className="grid gap-3 rounded-md border p-4 lg:grid-cols-[1fr_8rem_9rem_14rem] lg:items-center">
                  <div className="min-w-0">
                    <p className="font-medium">{String(webhook.name || "")}</p>
                    <p className="truncate text-sm text-muted-foreground">{String(webhook.url || "")}</p>
                    <div className="mt-2 flex flex-wrap gap-1">{(Array.isArray(webhook.events) ? webhook.events : []).slice(0, 4).map((event) => <Badge key={String(event)} variant="outline">{String(event)}</Badge>)}</div>
                  </div>
                  <Badge className={statusColor((webhook.isActive ?? webhook.is_active) ? "Active" : "Inactive")}>{(webhook.isActive ?? webhook.is_active) ? "Active" : "Inactive"}</Badge>
                  <span className="text-sm text-muted-foreground">Secret {String(webhook.secret || "masked")}</span>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => setSelected(webhook)}>Logs</Button>
                    <Button variant="outline" size="sm" onClick={() => test(webhook)}>Test</Button>
                    <Button variant="outline" size="sm" onClick={() => toggleActive(webhook)}>{(webhook.isActive ?? webhook.is_active) ? "Disable" : "Enable"}</Button>
                    <Button variant="outline" size="sm" onClick={() => crmApi.deleteWebhook(Number(webhook.id)).then(load)}>Delete</Button>
                  </div>
                </div>
              ))}
              {!loading && !webhooks.length ? <p className="text-sm text-muted-foreground">No webhooks configured yet.</p> : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Delivery Log{selected ? ` / ${String(selected.name || selected.id)}` : ""}</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              {!selected ? <p className="text-sm text-muted-foreground">Select a webhook to view deliveries.</p> : null}
              {selected ? <ReportTable title="" rows={deliveries} columns={["eventType", "status", "responseCode", "attemptCount", "nextRetryAt", "createdAt"]} /> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

const crmFeatureChecklist = [
  { feature: "CRM list pages", status: "Ready", api: "GET /api/v1/crm/{entity}", frontend: "Workspace lists", notes: "Leads, contacts, companies/accounts, deals, activities, tasks, campaigns, products, quotations, tickets, files, owners, and custom fields use backend APIs." },
  { feature: "Record detail pages", status: "Ready", api: "GET/PATCH/DELETE /api/v1/crm/{entity}/{id}", frontend: "Lead/contact/account/deal/quotation detail", notes: "Detail payload includes related records, custom fields, duplicate summary, approval state, and timeline." },
  { feature: "Activity timeline", status: "Ready", api: "Related timeline in detail payload", frontend: "Timeline cards on detail pages", notes: "Notes, tasks, calls, emails, meetings, approvals, PDF generation, enrichment, and duplicate merge events are surfaced." },
  { feature: "Pipeline management", status: "Ready", api: "Pipelines, stages, deal updates", frontend: "Pipeline board and settings", notes: "Multiple pipelines and organization-scoped stages are supported." },
  { feature: "Custom fields", status: "Ready", api: "Custom fields and values", frontend: "Settings, create forms, list columns, detail fields", notes: "Visible fields render in lists; values can be edited on detail pages." },
  { feature: "Duplicate detection and merge", status: "Ready", api: "Duplicates scan and merge", frontend: "Duplicate management", notes: "Lead, contact, and account matching is organization-scoped." },
  { feature: "Approvals", status: "Ready", api: "Approval workflows and requests", frontend: "Settings, my approvals, deal/quote detail", notes: "Deal and quotation final actions are blocked while approval is pending or rejected." },
  { feature: "Quotation PDF", status: "Ready", api: "GET quotation PDF, send PDF email", frontend: "Quotation detail actions", notes: "Generated PDF uses persisted quotation, account, contact, line item, and company data." },
  { feature: "Calendar", status: "Ready", api: "GET /api/v1/crm/calendar", frontend: "Calendar page", notes: "Tasks, meetings, calls, activities, quotation expiries, and deal close dates render from DB records." },
  { feature: "Reports", status: "Ready", api: "Win/loss, funnel, revenue, territory reports", frontend: "Reports page", notes: "Charts and tables are backed by organization-scoped deal data." },
  { feature: "Territories", status: "Ready", api: "Territory CRUD and auto-assign", frontend: "Territory settings", notes: "Lead, account, and deal assignment follows territory rules with manual override support." },
  { feature: "Enrichment", status: "Ready", api: "Preview, apply, history", frontend: "Lead/contact detail modal", notes: "Provider abstraction supports manual, CSV/import, and future third-party providers." },
  { feature: "WhatsApp/SMS", status: "Ready", api: "Messages and templates", frontend: "Lead/contact/deal detail compose", notes: "Provider credentials remain server-side; mock provider supports local testing." },
  { feature: "Calendar integrations", status: "Ready", api: "Integration connect, disconnect, sync", frontend: "Calendar integrations page", notes: "Mock provider is available; Google/Outlook adapters have isolated TODO configuration points." },
  { feature: "Outbound webhooks", status: "Ready", api: "Webhook CRUD, test, deliveries", frontend: "Webhook settings", notes: "Signed deliveries are logged and retried with backoff." },
  { feature: "Organization isolation", status: "Ready", api: "Organization-scoped queries", frontend: "Route-level API usage", notes: "Direct record URLs use the same backend organization filter as list pages." },
];

function CRMFeatureChecklistPage() {
  const statusCounts = crmFeatureChecklist.reduce<Record<string, number>>((counts, row) => {
    counts[row.status] = (counts[row.status] || 0) + 1;
    return counts;
  }, {});
  return (
    <div className="space-y-6">
      <PageHeader title="CRM Feature Checklist" description={descriptionFor("featureChecklist")} />
      <div className="grid gap-3 md:grid-cols-3">
        {Object.entries(statusCounts).map(([status, count]) => (
          <Metric key={status} icon={CheckCircle2} label={status} value={count} tone={status === "Ready" ? "emerald" : "amber"} />
        ))}
        <Metric icon={FileCheck2} label="Tracked features" value={crmFeatureChecklist.length} tone="blue" />
      </div>
      <Card>
        <CardHeader><CardTitle>Integration Readiness</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="text-left text-xs uppercase text-muted-foreground">
              <tr className="border-b">
                <th className="px-3 py-2">Feature</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">API availability</th>
                <th className="px-3 py-2">Frontend availability</th>
                <th className="px-3 py-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {crmFeatureChecklist.map((row) => (
                <tr key={row.feature} className="border-b align-top">
                  <td className="px-3 py-3 font-medium">{row.feature}</td>
                  <td className="px-3 py-3"><Badge className={statusColor(row.status)}>{row.status}</Badge></td>
                  <td className="px-3 py-3 text-muted-foreground">{row.api}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.frontend}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function TerritorySettingsPage() {
  const [territories, setTerritories] = useState<CRMApiRecord[]>([]);
  const [reportRows, setReportRows] = useState<CRMApiRecord[]>([]);
  const [users, setUsers] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState({ name: "", country: "India", state: "", city: "", industry: "", companySize: "", priority: "100", userId: "" });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    crmApi.territories().then((response) => setTerritories(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Territories could not be loaded.")).finally(() => setLoading(false));
    crmApi.territoryReport().then((response) => setReportRows(response.data.items || [])).catch(() => setReportRows([]));
    crmApi.searchUsers({ q: "", limit: 25 }).then((response) => setUsers(response.data.items || [])).catch(() => setUsers([]));
  };
  useEffect(load, []);
  const create = () => {
    if (!draft.name.trim()) return;
    const rules = { country: draft.country || undefined, state: draft.state || undefined, city: draft.city || undefined, industry: draft.industry || undefined, companySize: draft.companySize || undefined };
    crmApi.createTerritory({ name: draft.name, country: draft.country, state: draft.state, city: draft.city, priority: Number(draft.priority || 100), rules, isActive: true })
      .then((response) => (draft.userId ? crmApi.addTerritoryUser(Number(response.data.id), { userId: Number(draft.userId) }).then(() => undefined) : Promise.resolve(undefined)))
      .then(() => {
        setDraft({ name: "", country: "India", state: "", city: "", industry: "", companySize: "", priority: "100", userId: "" });
        setMessage("Territory created.");
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Territory could not be created."));
  };
  const toggle = (territory: CRMApiRecord) => {
    crmApi.updateTerritory(Number(territory.id), { isActive: !(territory.isActive ?? territory.is_active) }).then(load).catch((err) => setError(err?.response?.data?.detail || "Territory could not be updated."));
  };
  const autoAssign = (overrideManual = false) => {
    crmApi.autoAssignTerritories({ overrideManual }).then((response) => setMessage(`Assigned ${response.data.updated} CRM records.`)).then(load).catch((err) => setError(err?.response?.data?.detail || "Auto-assignment failed."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Territory Settings" description="Create organization-scoped routing territories, assign users, and auto-assign leads, accounts, and deals by rule priority." action="Run Auto-Assign" onAction={() => autoAssign(false)} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Create Territory</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Country"><Input value={draft.country} onChange={(event) => setDraft((current) => ({ ...current, country: event.target.value }))} /></Field>
            <Field label="State"><Input value={draft.state} onChange={(event) => setDraft((current) => ({ ...current, state: event.target.value }))} /></Field>
            <Field label="City"><Input value={draft.city} onChange={(event) => setDraft((current) => ({ ...current, city: event.target.value }))} /></Field>
            <Field label="Industry"><Input value={draft.industry} onChange={(event) => setDraft((current) => ({ ...current, industry: event.target.value }))} /></Field>
            <Field label="Company size">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.companySize} onChange={(event) => setDraft((current) => ({ ...current, companySize: event.target.value }))}>
                <option value="">Any size</option><option value="small">Small</option><option value="mid_market">Mid market</option><option value="enterprise">Enterprise</option><option value="strategic">Strategic</option>
              </select>
            </Field>
            <Field label="Priority"><Input type="number" value={draft.priority} onChange={(event) => setDraft((current) => ({ ...current, priority: event.target.value }))} /></Field>
            <Field label="Assigned user">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.userId} onChange={(event) => setDraft((current) => ({ ...current, userId: event.target.value }))}>
                <option value="">No default user</option>
                {users.map((user) => <option key={String(user.id)} value={String(user.id)}>{String(user.displayName || user.email || user.id)}</option>)}
              </select>
            </Field>
            <Button className="w-full" onClick={create}><Plus className="h-4 w-4" />Create territory</Button>
            <Button className="w-full" variant="outline" onClick={() => autoAssign(true)}>Reassign including manual overrides</Button>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Territory Rules</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {loading ? <p className="text-sm text-muted-foreground">Loading territories...</p> : null}
              {territories.map((territory) => (
                <div key={String(territory.id)} className="grid gap-3 rounded-md border p-4 md:grid-cols-[1fr_8rem_9rem_auto] md:items-center">
                  <div><p className="font-medium">{String(territory.name || "")}</p><p className="text-sm text-muted-foreground">{String(territory.city || territory.state || territory.country || "Custom rule")} / priority {String(territory.priority || 100)}</p></div>
                  <Badge className={statusColor((territory.isActive ?? territory.is_active) ? "Active" : "Inactive")}>{(territory.isActive ?? territory.is_active) ? "Active" : "Inactive"}</Badge>
                  <span className="text-sm text-muted-foreground">{Array.isArray(territory.users) ? territory.users.length : 0} user(s)</span>
                  <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => toggle(territory)}>{(territory.isActive ?? territory.is_active) ? "Deactivate" : "Activate"}</Button><Button variant="outline" size="sm" onClick={() => crmApi.deleteTerritory(Number(territory.id)).then(load)}>Delete</Button></div>
                </div>
              ))}
            </CardContent>
          </Card>
          <ReportTable title="Territory-wise Report" rows={reportRows} columns={["territory", "users", "leads", "accounts", "deals", "wonRevenue"]} />
        </div>
      </div>
    </div>
  );
}

function MergeWizardModal({ group, onClose, onMerged }: { group: CRMDuplicateGroup; onClose: () => void; onMerged: () => void }) {
  const records = group.records || [];
  const [winnerId, setWinnerId] = useState<number>(() => Number(records[0]?.id || 0));
  const [fieldValues, setFieldValues] = useState<CRMApiRecord>(() => mergeDefaultFieldValues(records, group.entityType));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const fields = mergeFieldsFor(group.entityType);
  const submit = () => {
    setSaving(true);
    setError(null);
    crmApi.mergeDuplicates({
      entityType: group.entityType,
      winnerId,
      loserIds: records.map((record) => Number(record.id)).filter((id) => id !== winnerId),
      fieldValues,
    }).then(onMerged).catch((err) => setError(err?.response?.data?.detail || "Records could not be merged.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[92vh] w-full max-w-5xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <div><CardTitle>Merge Duplicate Records</CardTitle><p className="text-sm text-muted-foreground">{group.reasons.join(", ")}</p></div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-3">
            {records.map((record) => (
              <button key={String(record.id)} type="button" onClick={() => setWinnerId(Number(record.id))} className={`rounded-md border p-3 text-left ${winnerId === Number(record.id) ? "border-primary bg-primary/5" : "bg-card"}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{duplicateRecordTitle(record, group.entityType)}</p>
                  <Badge variant={winnerId === Number(record.id) ? "default" : "outline"}>{winnerId === Number(record.id) ? "Winner" : `#${record.id}`}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{valueText(record.email || record.phone || record.website || record.company_name)}</p>
              </button>
            ))}
          </div>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/60">
                <tr>
                  <th className="px-3 py-2 text-left">Field</th>
                  {records.map((record) => <th key={String(record.id)} className="px-3 py-2 text-left">{duplicateRecordTitle(record, group.entityType)}</th>)}
                  <th className="px-3 py-2 text-left">Selected value</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={field} className="border-t">
                    <td className="px-3 py-2 font-medium">{labelFor(field)}</td>
                    {records.map((record) => (
                      <td key={String(record.id)} className="px-3 py-2">
                        <Button type="button" size="sm" variant="outline" onClick={() => setFieldValues((current) => ({ ...current, [field]: record[field] as CRMApiRecord[string] }))}>{valueText(record[field]) || "-"}</Button>
                      </td>
                    ))}
                    <td className="px-3 py-2">{valueText(fieldValues[field]) || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">Merge will relink activities, notes, tasks, deals, and quotations to the winning record, then soft-delete the losing record(s).</div>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving || records.length < 2}>{saving ? "Merging..." : "Merge records"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CRMReports() {
  const defaultEnd = new Date().toISOString().slice(0, 10);
  const defaultStart = new Date(new Date().getFullYear(), new Date().getMonth() - 11, 1).toISOString().slice(0, 10);
  const [filters, setFilters] = useState({ startDate: defaultStart, endDate: defaultEnd, ownerId: "all", pipelineId: "all" });
  const [report, setReport] = useState<CRMWinLossReport | null>(null);
  const [funnel, setFunnel] = useState<CRMApiRecord[]>([]);
  const [revenueTrend, setRevenueTrend] = useState<CRMApiRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc", per_page: 100 });
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords, { per_page: 100 });
  const ownerOptions = useMemo(() => {
    const ids = Array.from(new Set(dealState.data.map((deal) => Number(deal.ownerId || deal.owner_user_id || 0)).filter(Boolean)));
    return ids.map((id) => ({ id, label: `User ${id}` }));
  }, [dealState.data]);
  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { startDate: filters.startDate, endDate: filters.endDate };
    if (filters.ownerId !== "all") params.ownerId = Number(filters.ownerId);
    if (filters.pipelineId !== "all") params.pipelineId = Number(filters.pipelineId);
    return params;
  }, [filters]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      crmApi.winLossReport(queryParams),
      crmApi.salesFunnelReport(queryParams),
      crmApi.revenueTrendReport(queryParams),
    ])
      .then(([winLossResponse, funnelResponse, trendResponse]) => {
        setReport(winLossResponse.data);
        setFunnel(funnelResponse.data.items || []);
        setRevenueTrend(trendResponse.data.items || winLossResponse.data.revenueWonTrend || []);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Win/loss analysis could not be loaded."))
      .finally(() => setLoading(false));
  }, [queryParams]);

  const summary = report?.summary;
  const exportData = () => {
    if (!report) return;
    exportRows("crm-win-loss-analysis.csv", [
      ...(report.winRateByMonth || []).map((row) => ({ section: "Win rate by month", ...row })),
      ...(report.winRateByOwner || []).map((row) => ({ section: "Win rate by owner", ...row })),
      ...(report.winRateByPipeline || []).map((row) => ({ section: "Win rate by pipeline", ...row })),
      ...(report.winLossBySource || []).map((row) => ({ section: "Win/loss by source", ...row })),
      ...(report.lostReasonBreakdown || []).map((row) => ({ section: "Lost reasons", ...row })),
      ...funnel.map((row) => ({ section: "Sales funnel", ...row })),
    ]);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Win/Loss Analysis" description="Monthly win rate, owner and pipeline performance, source quality, lost reasons, sales cycle, revenue trend, and stage conversion." action="Export CSV" onAction={exportData} />
      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-5 md:items-end">
          <div className="space-y-1">
            <Label>Start date</Label>
            <Input type="date" value={filters.startDate} onChange={(event) => setFilters((current) => ({ ...current, startDate: event.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>End date</Label>
            <Input type="date" value={filters.endDate} onChange={(event) => setFilters((current) => ({ ...current, endDate: event.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Owner</Label>
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={filters.ownerId} onChange={(event) => setFilters((current) => ({ ...current, ownerId: event.target.value }))}>
              <option value="all">All owners</option>
              {ownerOptions.map((owner) => <option key={owner.id} value={owner.id}>{owner.label}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Pipeline</Label>
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={filters.pipelineId} onChange={(event) => setFilters((current) => ({ ...current, pipelineId: event.target.value }))}>
              <option value="all">All pipelines</option>
              {pipelineState.data.map((pipeline) => <option key={String(pipeline.id)} value={String(pipeline.id)}>{String(pipeline.name || `Pipeline ${pipeline.id}`)}</option>)}
            </select>
          </div>
          <Button variant="outline" onClick={exportData} disabled={!report}><Download className="h-4 w-4" />CSV</Button>
        </CardContent>
      </Card>
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 md:grid-cols-4">
        <Metric icon={CheckCircle2} label="Win rate" value={loading ? "..." : `${summary?.winRate ?? 0}%`} tone="emerald" />
        <Metric icon={IndianRupee} label="Revenue won" value={loading ? "..." : formatCurrency(summary?.wonRevenue || 0)} tone="blue" />
        <Metric icon={Target} label="Avg won deal" value={loading ? "..." : formatCurrency(summary?.averageWonDealSize || 0)} tone="violet" />
        <Metric icon={Clock} label="Avg sales cycle" value={loading ? "..." : `${summary?.averageSalesCycleDays ?? 0} days`} tone="amber" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Win Rate by Month</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={report?.winRateByMonth || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, "Win rate"]} />
                <Line type="monotone" dataKey="winRate" stroke="#059669" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Revenue Won Trend</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenueTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                <Bar dataKey="revenue" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Win/Loss by Source</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={report?.winLossBySource || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="key" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="won" stackId="source" fill="#16a34a" />
                <Bar dataKey="lost" stackId="source" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Conversion Funnel by Stage</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="stage" width={110} />
                <Tooltip formatter={(value, name) => name === "amount" ? formatCurrency(Number(value)) : value} />
                <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <ReportTable title="By Owner" rows={report?.winRateByOwner || []} columns={["key", "won", "lost", "winRate", "wonRevenue"]} />
        <ReportTable title="By Pipeline" rows={report?.winRateByPipeline || []} columns={["key", "won", "lost", "winRate", "wonRevenue"]} />
        <ReportTable title="Lost Reasons" rows={report?.lostReasonBreakdown || []} columns={["reason", "count", "amount"]} />
      </div>
      <Card>
        <CardHeader><CardTitle>Closed Deals</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>{["Deal", "Status", "Source", "Owner", "Pipeline", "Amount", "Closed"].map((heading) => <th key={heading} className="px-4 py-3">{heading}</th>)}</tr>
            </thead>
            <tbody>
              {(report?.deals || []).slice(0, 10).map((deal) => (
                <tr key={String(deal.id)} className="border-t">
                  <td className="px-4 py-3 font-medium">{String(deal.name || "")}</td>
                  <td className="px-4 py-3"><Badge className={statusColor(String(deal.status || ""))}>{String(deal.status || "")}</Badge></td>
                  <td className="px-4 py-3">{String(deal.source || "-")}</td>
                  <td className="px-4 py-3">{String(deal.owner || "-")}</td>
                  <td className="px-4 py-3">{String(deal.pipeline || "-")}</td>
                  <td className="px-4 py-3">{formatCurrency(Number(deal.amount || 0))}</td>
                  <td className="px-4 py-3">{deal.closedAt ? formatDate(String(deal.closedAt)) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function ReportTable({ title, rows, columns }: { title: string; rows: CRMApiRecord[]; columns: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
            <tr>{columns.map((column) => <th key={column} className="px-3 py-2">{labelFor(column)}</th>)}</tr>
          </thead>
          <tbody>
            {rows.length ? rows.slice(0, 8).map((row, index) => (
              <tr key={`${title}-${index}`} className="border-t">
                {columns.map((column) => {
                  const value = row[column];
                  const isCurrency = ["amount", "wonRevenue", "lostAmount"].includes(column);
                  const isRate = column.toLowerCase().includes("rate");
                  return <td key={column} className="px-3 py-2">{isCurrency ? formatCurrency(Number(value || 0)) : isRate ? `${Number(value || 0).toFixed(1)}%` : String(value ?? "-")}</td>;
                })}
              </tr>
            )) : (
              <tr><td className="px-3 py-4 text-sm text-muted-foreground" colSpan={columns.length}>No report rows for the selected filters.</td></tr>
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function LeadToCashPage() {
  const leadState = useCrmRecords<CRMRecord>("leads", emptyRecords);
  const companyState = useCrmRecords<CRMRecord>("companies", emptyRecords);
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const quoteState = useCrmRecords<CRMRecord>("quotations", emptyRecords);
  const crmLeads = useMemo(() => leadState.data.map(recordToLead), [leadState.data]);
  const crmDeals = useMemo(() => dealState.data.map((record) => recordToDeal(record, emptyRecords)), [dealState.data]);
  const crmCompanies = companyState.data;
  const crmQuotations = quoteState.data;
  const flow = [
    ["Lead", "Qualified", `${crmLeads.filter((lead) => lead.status === "Qualified").length} qualified leads`, "/crm/leads"],
    ["Contact", "Created", `${crmLeads.filter((lead) => lead.status === "Converted").length} converted contacts`, "/crm/contacts"],
    ["Company", "Linked", `${crmCompanies.length} accounts`, "/crm/companies"],
    ["Deal", "Open", `${crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).length} active deals`, "/crm/deals"],
    ["Quotation", "Sent", `${crmQuotations.filter((quote) => quote.status === "Sent").length} sent quotes`, "/crm/quotations"],
    ["Order/Invoice", "Handoff", "Ready for finance handoff", "/crm/lead-to-cash"],
  ];
  const handoffRows = [
    ...crmQuotations.filter((quote) => ["Accepted", "Approved", "Sent"].includes(String(quote.status))).slice(0, 3).map((quote) => ({
      item: String(quote.quote || quote.quote_number || `Quote #${quote.id}`),
      customer: String(quote.companyId || quote.company_id || "Linked account"),
      amount: Number(quote.total || quote.total_amount || 0),
      status: String(quote.status || "Draft"),
      next: String(quote.status) === "Accepted" ? "Create order and invoice draft" : "Follow up quotation approval or customer confirmation",
    })),
    ...crmDeals.filter((deal) => deal.stage === "Won").slice(0, 2).map((deal) => ({
      item: deal.name,
      customer: deal.company || "Linked account",
      amount: deal.amount,
      status: "Won",
      next: "Send order confirmation",
    })),
  ].slice(0, 5);

  return (
    <div className="space-y-6">
      <PageHeader title="Lead-to-Cash" description="Convert leads into contacts, companies, deals, quotations, and order/invoice handoff without leaving CRM." action="Convert lead" />
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {flow.map(([label, status, detail, path], index) => (
          <Card key={label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">{index + 1}</div>
                <Badge variant="outline">{status}</Badge>
              </div>
              <p className="mt-3 font-semibold">{label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
              <a className="mt-3 inline-flex text-xs font-medium text-primary" href={path}>Open stage</a>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader><CardTitle>Conversion Workbench</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {crmLeads.slice(0, 5).map((lead) => (
              <div key={lead.id} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_9rem_9rem_auto] md:items-center">
                <div><p className="font-medium">{lead.name}</p><p className="text-sm text-muted-foreground">{lead.company} / {lead.source}</p></div>
                <Badge className={statusColor(lead.rating)}>{lead.rating}</Badge>
                <span className="text-sm font-medium">{formatCurrency(lead.value)}</span>
                <Button size="sm">Convert</Button>
              </div>
            ))}
            {!crmLeads.length ? <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">No leads available for conversion.</p> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Invoice Handoff Queue</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {handoffRows.map((row) => (
              <div key={row.item} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-medium">{row.item}</p><p className="text-sm text-muted-foreground">{row.customer}</p></div>
                  <Badge>{row.status}</Badge>
                </div>
                <p className="mt-2 text-sm font-semibold">{formatCurrency(row.amount)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{row.next}</p>
              </div>
            ))}
            {!handoffRows.length ? <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">No quotes or won deals are ready for handoff.</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SalesAutomationPage() {
  const automationCards: AutomationCard[] = [
    ["Reminders", "18 active", "Follow-up reminders from leads, deals, quotations, and tickets.", Bell],
    ["SLA follow-ups", "4 at risk", "Escalate customer replies and support-linked sales tasks before breach.", Clock],
    ["Stale deal alerts", "3 stale", "Detect opportunities without activity or next step updates.", AlertTriangle],
    ["Auto-assignment", "Round robin", "Route website, campaign, and partner leads to available owners.", Users],
    ["Email sequences", "6 live", "Drip campaigns for nurture, proposal follow-up, and renewal.", Mail],
    ["WhatsApp sequences", "5 live", "Message templates for demo reminders and quote expiry nudges.", Phone],
  ];
  const rules = [
    { rule: "Qualified lead follow-up", trigger: "Status = Qualified", action: "Create task + WhatsApp reminder", owner: "Sales Ops" },
    { rule: "Stale negotiation", trigger: "No activity for 5 days", action: "Alert owner and manager", owner: "Sales Manager" },
    { rule: "Quote expiry", trigger: "Expiry in 2 days", action: "Email sequence + task", owner: "Revenue Ops" },
    { rule: "Critical customer ticket", trigger: "Priority = Critical", action: "Pause renewal ask and notify owner", owner: "Support Lead" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Sales Automation" description="Reminders, SLA follow-ups, stale deal alerts, auto-assignment, email sequences, and WhatsApp sequences." action="Create rule" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {automationCards.map(([title, value, detail, Icon]) => (
          <Card key={String(title)}>
            <CardContent className="flex gap-3 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
              <div><p className="font-semibold">{title}</p><p className="text-2xl font-semibold">{value}</p><p className="text-sm text-muted-foreground">{detail}</p></div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Automation Rules</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {rules.map((row) => (
            <div key={row.rule} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_13rem_15rem_9rem] md:items-center">
              <p className="font-medium">{row.rule}</p>
              <span className="text-sm text-muted-foreground">{row.trigger}</span>
              <span className="text-sm">{row.action}</span>
              <Badge variant="outline">{row.owner}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ForecastingPage() {
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const crmDeals = useMemo(() => dealState.data.map((record) => recordToDeal(record, emptyRecords)), [dealState.data]);
  const weighted = crmDeals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  const target = 6500000;
  const commit = crmDeals.filter((deal) => deal.probability >= 70).reduce((sum, deal) => sum + deal.amount, 0);
  const bestCase = crmDeals.filter((deal) => deal.probability >= 40).reduce((sum, deal) => sum + deal.amount, 0);
  const atRisk = crmDeals.filter((deal) => deal.probability < 40 && !["Won", "Lost"].includes(deal.stage)).reduce((sum, deal) => sum + deal.amount, 0);
  const forecastRows = [
    { view: "Commit", amount: commit, confidence: "High", owner: "Sales Manager" },
    { view: "Best case", amount: bestCase, confidence: "Medium", owner: "Revenue Ops" },
    { view: "At risk", amount: atRisk, confidence: "Low", owner: "Deal owners" },
    { view: "Weighted pipeline", amount: weighted, confidence: "Model", owner: "CRM Forecast" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Forecasting" description="Weighted pipeline, monthly targets, quota tracking, and commit/best-case/at-risk sales views." action="Export forecast" />
      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={Target} label="Monthly target" value={formatCurrency(target)} tone="blue" />
        <Metric icon={IndianRupee} label="Weighted forecast" value={formatCurrency(weighted)} tone="emerald" />
        <Metric icon={CheckCircle2} label="Commit" value={formatCurrency(commit)} tone="violet" />
        <Metric icon={AlertTriangle} label="At risk" value={formatCurrency(atRisk)} tone="red" />
      </div>
      <Card>
        <CardHeader><CardTitle>Forecast Views</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {forecastRows.map((row) => (
            <div key={row.view} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_12rem_8rem_10rem] md:items-center">
              <p className="font-medium">{row.view}</p>
              <span className="font-semibold">{formatCurrency(row.amount)}</span>
              <Badge variant={row.confidence === "Low" ? "destructive" : "outline"}>{row.confidence}</Badge>
              <span className="text-sm text-muted-foreground">{row.owner}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Quota Tracking</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {["Ananya Rao", "Karan Shah", "Meera Iyer"].map((owner) => {
            const amount = crmDeals.filter((deal) => deal.owner === owner).reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
            const pct = Math.min(100, Math.round((amount / 2000000) * 100));
            return (
              <div key={owner} className="rounded-lg border p-4">
                <div className="flex items-center justify-between"><p className="font-medium">{owner}</p><Badge>{pct}%</Badge></div>
                <div className="mt-3 h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
                <p className="mt-2 text-sm text-muted-foreground">{formatCurrency(amount)} weighted quota coverage</p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

function Customer360Page() {
  const companyState = useCrmRecords<CRMRecord>("companies", emptyRecords);
  const customers = companyState.data.map((company) => customer360For(String(company.name)));
  return (
    <div className="space-y-6">
      <PageHeader title="Customer 360" description="Contacts, companies, deals, tickets, activities, quotations, files, and campaigns in one customer view." action="Open customer" />
      <div className="grid gap-4 xl:grid-cols-2">
        {customers.map((customer) => (
          <Card key={customer.company}>
            <CardHeader className="flex-row items-start justify-between">
              <div><CardTitle>{customer.company}</CardTitle><p className="text-sm text-muted-foreground">{customer.industry}</p></div>
              <Badge>{customer.status}</Badge>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              {customer.metrics.map(([label, value]) => (
                <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="text-lg font-semibold">{value}</p></div>
              ))}
              <div className="md:col-span-3 rounded-lg border bg-muted/30 p-3 text-sm">
                <p className="font-medium">Timeline</p>
                <div className="mt-2 space-y-2">
                  {customer.timeline.map((item) => <TimelineItem key={item} text={item} />)}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ImportExportPage() {
  const imports = [
    { file: "crm-contacts-may.csv", rows: 428, duplicates: 12, valid: 409, status: "Preview ready" },
    { file: "partner-leads.xlsx", rows: 96, duplicates: 4, valid: 88, status: "Imported" },
    { file: "company-cleanup.csv", rows: 74, duplicates: 9, valid: 61, status: "Rolled back" },
  ];
  const mapping = [
    ["Full Name", "name", "Required"],
    ["Email Address", "email", "Duplicate key"],
    ["Mobile", "phone", "Normalize"],
    ["Company", "company", "Create if missing"],
    ["Owner Email", "owner", "Assign user"],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Import & Export Engine" description="Field mapping, duplicate detection, validation preview, rollback, and import history for CRM data." action="Upload import" />
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={Upload} label="Imports" value={imports.length} tone="blue" />
        <Metric icon={FileCheck2} label="Valid rows" value={imports.reduce((sum, row) => sum + row.valid, 0)} tone="emerald" />
        <Metric icon={AlertTriangle} label="Duplicates" value={imports.reduce((sum, row) => sum + row.duplicates, 0)} tone="amber" />
        <Metric icon={Download} label="Exports" value="12" tone="violet" />
        <Metric icon={Clock} label="Rollback window" value="24h" tone="red" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader><CardTitle>Import History</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {imports.map((row) => (
              <div key={row.file} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_7rem_7rem_7rem_auto] md:items-center">
                <p className="font-medium">{row.file}</p>
                <span className="text-sm">{row.rows} rows</span>
                <span className="text-sm text-amber-700">{row.duplicates} dupes</span>
                <span className="text-sm text-emerald-700">{row.valid} valid</span>
                <Button variant="outline" size="sm">{row.status === "Imported" ? "Rollback" : "Open"}</Button>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Field Mapping Preview</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {mapping.map(([source, target, rule]) => (
              <div key={source} className="rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between gap-2"><span className="font-medium">{source}</span><span>{target}</span></div>
                <p className="mt-1 text-xs text-muted-foreground">{rule}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Toolbar({
  search,
  onSearch,
  selectedView,
  onViewChange,
  onToggleFilters,
  contacts,
  onImportContacts,
  onExportServer,
  importLabel = "Import Contacts",
  exportLabel = "Export Contacts",
}: {
  search: string;
  onSearch: (value: string) => void;
  selectedView?: string;
  onViewChange?: (value: string) => void;
  onToggleFilters?: () => void;
  contacts?: CRMRecord[];
  onImportContacts?: (rows: CRMRecord[]) => void;
  onExportServer?: () => void;
  importLabel?: string;
  exportLabel?: string;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const handleImport = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !onImportContacts) return;
    file.text().then((text) => {
      const imported = parseCsv(text);
      if (imported.length) onImportContacts(imported);
    });
    event.target.value = "";
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-3 lg:flex-row lg:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search records, owners, companies..." className="border-0 p-0 shadow-none focus-visible:ring-0" />
      </div>
      {selectedView && onViewChange ? (
        <div className="flex gap-2 overflow-x-auto">
          {savedViews.map((view) => (
            <Button key={view} type="button" size="sm" variant={selectedView === view ? "default" : "outline"} onClick={() => onViewChange(view)}>
              {view}
            </Button>
          ))}
        </div>
      ) : null}
      <Button variant="outline" onClick={onToggleFilters}><Filter className="h-4 w-4" />Filters</Button>
      <Button variant="outline" onClick={onExportServer || (() => exportRows("crm-contacts.csv", contacts || []))}><Download className="h-4 w-4" />{exportLabel}</Button>
      <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleImport} />
      <Button variant="outline" onClick={() => inputRef.current?.click()}><Upload className="h-4 w-4" />{importLabel}</Button>
    </div>
  );
}

function FilterPanel({
  filters,
  onChange,
  owners,
  statuses,
  types,
  territories,
  onClear,
}: {
  filters: CRMFilters;
  onChange: (filters: CRMFilters) => void;
  owners: string[];
  statuses: string[];
  types: string[];
  territories: string[];
  onClear: () => void;
}) {
  const patch = (update: Partial<CRMFilters>) => onChange({ ...filters, ...update });
  return (
    <Card>
      <CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_1fr_1fr_1fr_auto] md:items-end">
        <Field label="Owner">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.owner} onChange={(event) => patch({ owner: event.target.value })}>
            <option value="all">All owners</option>
            {owners.map((owner) => <option key={owner} value={owner}>{owner}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.status} onChange={(event) => patch({ status: event.target.value })}>
            <option value="all">All statuses</option>
            {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </Field>
        <Field label="Type">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.type} onChange={(event) => patch({ type: event.target.value })}>
            <option value="all">All types</option>
            {types.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </Field>
        <Field label="Territory">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.territory} onChange={(event) => patch({ territory: event.target.value })}>
            <option value="all">All territories</option>
            {territories.map((territory) => <option key={territory} value={territory}>Territory {territory}</option>)}
          </select>
        </Field>
        <Button variant="outline" onClick={onClear}>Clear</Button>
      </CardContent>
    </Card>
  );
}

function SmartCRMTable({ rows, title, kind, onSelect, onOpen, onInlineSave, onBulkDelete, loading, error }: { rows: CRMRecord[]; title: string; kind: CRMPageKind; onSelect: (row: CRMRecord) => void; onOpen?: (row: CRMRecord) => void; onInlineSave?: (row: CRMRecord, key: string, value: string | number | boolean | null) => Promise<unknown>; onBulkDelete?: (rows: CRMRecord[]) => Promise<unknown>; loading?: boolean; error?: string | null }) {
  const [sort, setSort] = useState<SortState>(null);
  const [columnOrder, setColumnOrder] = useState<string[]>([]);
  const [widths, setWidths] = useState<Record<string, number>>({});
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);
  const columns = useMemo(() => {
    const keys = Array.from(rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set<string>()));
    const known = columnOrder.filter((key) => keys.includes(key));
    const fresh = keys.filter((key) => !known.includes(key));
    return [...known, ...fresh];
  }, [rows, columnOrder]);
  const visibleRows = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => compareValues(a[sort.key], b[sort.key], sort.direction));
  }, [rows, sort]);
  const selectableRows = visibleRows.filter((row) => row.id !== undefined && row.id !== null);
  const selectedRows = selectableRows.filter((row) => selectedIds[String(row.id)]);
  const allSelected = Boolean(selectableRows.length) && selectedRows.length === selectableRows.length;

  useEffect(() => {
    setSelectedIds((current) => {
      const visibleIds = new Set(selectableRows.map((row) => String(row.id)));
      return Object.fromEntries(Object.entries(current).filter(([id]) => visibleIds.has(id)));
    });
  }, [visibleRows]);

  const toggleSort = (key: string) => {
    setSort((current) => {
      if (current?.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  };
  const moveColumn = (key: string, direction: -1 | 1) => {
    const current = columns;
    const index = current.indexOf(key);
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    [next[index], next[target]] = [next[target], next[index]];
    setColumnOrder(next);
  };
  const startResize = (key: string, event: React.MouseEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = widths[key] || 160;
    const onMove = (moveEvent: MouseEvent) => {
      setWidths((current) => ({ ...current, [key]: Math.max(96, startWidth + moveEvent.clientX - startX) }));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  const toggleAllRows = (checked: boolean) => {
    setSelectedIds(checked ? Object.fromEntries(selectableRows.map((row) => [String(row.id), true])) : {});
  };
  const toggleRow = (row: CRMRecord, checked: boolean) => {
    setSelectedIds((current) => ({ ...current, [String(row.id)]: checked }));
  };
  const bulkDelete = () => {
    if (!onBulkDelete || !selectedRows.length) return;
    if (!window.confirm(`Delete ${selectedRows.length} selected ${title.toLowerCase()} record${selectedRows.length === 1 ? "" : "s"}?`)) return;
    setBulkSaving(true);
    setBulkError(null);
    onBulkDelete(selectedRows)
      .then(() => setSelectedIds({}))
      .catch((err) => setBulkError(err?.response?.data?.detail || err?.message || "Selected records could not be deleted."))
      .finally(() => setBulkSaving(false));
  };

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle className="text-base">{title} Grid</CardTitle>
          {selectedRows.length ? <p className="text-sm text-muted-foreground">{selectedRows.length} selected</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {onBulkDelete && selectedRows.length ? <Button variant="outline" size="sm" onClick={bulkDelete} disabled={bulkSaving}>{bulkSaving ? "Deleting..." : "Delete selected"}</Button> : null}
          <Button variant="outline" size="sm" onClick={() => exportRows(`${title.toLowerCase().replace(/\s+/g, "-")}.csv`, visibleRows)}>
            <Download className="h-4 w-4" />Export Grid
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {error ? <div className="border-t bg-amber-50 px-4 py-2 text-sm text-amber-800">{error}</div> : null}
        {bulkError ? <div className="border-t bg-red-50 px-4 py-2 text-sm text-red-700">{bulkError}</div> : null}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] table-fixed text-sm">
            <thead className="sticky top-0 bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-12 px-4 py-3">
                  <input type="checkbox" checked={allSelected} disabled={!selectableRows.length} onChange={(event) => toggleAllRows(event.target.checked)} aria-label={`Select all ${title}`} />
                </th>
                {columns.map((key) => (
                  <th key={key} style={{ width: widths[key] || 160 }} className="relative px-4 py-3 font-medium">
                    <div className="flex items-center gap-1">
                      <button className="flex min-w-0 items-center gap-1 truncate" onClick={() => toggleSort(key)}>
                        <span className="truncate">{key.replace(/([A-Z])/g, " $1")}</span>
                        <ArrowUpDown className="h-3 w-3 shrink-0" />
                      </button>
                      <button className="rounded p-0.5 hover:bg-background" onClick={() => moveColumn(key, -1)} aria-label={`Move ${key} left`}><ChevronLeft className="h-3 w-3" /></button>
                      <button className="rounded p-0.5 hover:bg-background" onClick={() => moveColumn(key, 1)} aria-label={`Move ${key} right`}><ChevronRight className="h-3 w-3" /></button>
                    </div>
                    <button className="absolute right-0 top-0 h-full w-1 cursor-col-resize bg-border/60 opacity-0 hover:opacity-100" onMouseDown={(event) => startResize(key, event)} aria-label={`Resize ${key}`} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-12 text-center text-muted-foreground" colSpan={Math.max(columns.length + 1, 1)}>Loading CRM records...</td></tr>
              ) : null}
              {!loading && visibleRows.map((row, index) => (
                <tr key={index} className="border-t hover:bg-muted/35">
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={Boolean(selectedIds[String(row.id)])} disabled={row.id === undefined || row.id === null} onChange={(event) => toggleRow(row, event.target.checked)} aria-label={`Select record ${String(row.id || index + 1)}`} />
                  </td>
                  {columns.map((key) => (
                    <td key={key} style={{ width: widths[key] || 160 }} className="px-4 py-3">
                      <InlineTableCell row={row} fieldKey={key} kind={kind} value={row[key]} onSelect={onSelect} onOpen={onOpen} onSave={onInlineSave} />
                    </td>
                  ))}
                </tr>
              ))}
              {!loading && !visibleRows.length ? (
                <tr><td className="px-4 py-12 text-center text-muted-foreground" colSpan={Math.max(columns.length + 1, 1)}>No CRM records found</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function InlineTableCell({ row, fieldKey, kind, value, onSelect, onOpen, onSave }: { row: CRMRecord; fieldKey: string; kind: CRMPageKind; value: CRMApiValue; onSelect: (row: CRMRecord) => void; onOpen?: (row: CRMRecord) => void; onSave?: (row: CRMRecord, key: string, value: string | number | boolean | null) => Promise<unknown> }) {
  const config = listInlineEditConfig[kind]?.[fieldKey];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(valueText(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(valueText(value)), [value]);
  const commit = () => {
    if (!config || !onSave || draft === valueText(value)) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    onSave(row, fieldKey, draft)
      .then(() => setEditing(false))
      .catch((err) => {
        setDraft(valueText(value));
        setError(err?.message || "Could not save.");
      })
      .finally(() => setSaving(false));
  };
  const cancel = () => {
    setDraft(valueText(value));
    setError(null);
    setEditing(false);
  };
  if (editing && config) {
    return (
      <div className="space-y-1" onClick={(event) => event.stopPropagation()}>
        <InlineEditor config={config} value={draft} autoFocus onChange={setDraft} onCommit={commit} onCancel={cancel} />
        <div className="flex items-center gap-2 text-xs">
          {saving ? <span className="text-muted-foreground">Saving...</span> : null}
          {error ? <span className="text-destructive">{error}</span> : null}
        </div>
      </div>
    );
  }
  return (
    <button type="button" className="group flex w-full items-center justify-between gap-2 truncate text-left" onClick={() => onSelect(row)} onDoubleClick={() => onOpen?.(row)}>
      <span className="truncate">{renderCell(fieldKey, value)}</span>
      {config ? <span className="shrink-0 rounded p-0.5 text-muted-foreground opacity-0 group-hover:opacity-100" onClick={(event) => { event.stopPropagation(); setEditing(true); }}><Edit3 className="h-3.5 w-3.5" /></span> : null}
    </button>
  );
}

function InlineEditor({ config, value, autoFocus, onChange, onCommit, onCancel }: { config: InlineEditConfig; value: string; autoFocus?: boolean; onChange: (value: string) => void; onCommit: () => void; onCancel: () => void }) {
  const common = {
    value,
    autoFocus,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(event.target.value),
    onKeyDown: (event: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
      if (event.key === "Enter") onCommit();
      if (event.key === "Escape") onCancel();
    },
    onBlur: onCommit,
  };
  if (config.type === "select") {
    return (
      <select className="h-9 w-full rounded-md border bg-background px-2 text-sm" {...common}>
        {(config.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }
  return <Input className="h-9" type={config.type === "number" ? "number" : config.type === "date" ? "date" : "text"} {...common} />;
}

function PageHeader({ title, description, action, onAction }: { title: string; description: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 className="page-title">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action ? <Button onClick={onAction}><Plus className="h-4 w-4" />{action}</Button> : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone }: { icon: React.ElementType; label: string; value: string | number; tone: "blue" | "emerald" | "violet" | "amber" | "red" }) {
  const tones = {
    blue: "bg-blue-100 text-blue-700",
    emerald: "bg-emerald-100 text-emerald-700",
    violet: "bg-violet-100 text-violet-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  };
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`rounded-lg p-3 ${tones[tone]}`}><Icon className="h-5 w-5" /></div>
        <div><p className="text-sm text-muted-foreground">{label}</p><p className="text-2xl font-semibold">{value}</p></div>
      </CardContent>
    </Card>
  );
}

function RecordPanel({ record, kind }: { record: CRMRecord | null; kind: CRMPageKind }) {
  if (!record) return <Card><CardContent className="p-5 text-sm text-muted-foreground">Select a record to inspect details.</CardContent></Card>;
  const customer360 = kind === "contacts" || kind === "companies" ? customer360For(String(record.company || record.name || "")) : null;
  return (
    <Card className="h-fit">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">{String(record.name || record.company || record.deal || record.subject || record.quote || record.number || record.file || record.rule || pageTitles[kind])}</CardTitle>
        <p className="text-sm text-muted-foreground">Operational detail panel</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid max-h-[28rem] gap-2 overflow-y-auto pr-1">
          {Object.entries(record).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
              <span className="text-muted-foreground">{key.replace(/([A-Z])/g, " $1")}</span>
              <span className="text-right font-medium">{typeof value === "number" && isMoneyField(key) ? formatCurrency(value) : String(value)}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline"><Phone className="h-4 w-4" />Log call</Button>
          <Button variant="outline"><Mail className="h-4 w-4" />Log email</Button>
          <Button variant="outline"><CalendarDays className="h-4 w-4" />Schedule</Button>
          <Button variant="outline"><ListFilter className="h-4 w-4" />Task</Button>
        </div>
        {customer360 ? (
          <div className="rounded-lg border bg-primary/5 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Customer 360</p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {customer360.metrics.map(([label, value]) => (
                <div key={label} className="rounded-md bg-background p-2">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-2 text-sm">
              {customer360.timeline.slice(0, 3).map((item) => <TimelineItem key={item} text={item} />)}
            </div>
          </div>
        ) : null}
        <div className="rounded-lg border bg-muted/30 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Timeline</p>
          <div className="mt-3 space-y-3 text-sm">
            <TimelineItem text="Record updated by owner" />
            <TimelineItem text="Follow-up task generated" />
            <TimelineItem text="Notification sent to assigned user" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function customer360For(companyName: string) {
  return {
    company: companyName || "Customer",
    industry: "Account",
    status: "Active",
    metrics: [
      ["Contacts", "-"],
      ["Deals", "-"],
      ["Pipeline", "-"],
      ["Notes", "-"],
    ] as Array<[string, string | number]>,
    timeline: [
      "Customer 360 reads from CRM APIs.",
      "Open related CRM grids for persisted contacts, deals, notes, and quotations.",
    ],
  };
}

function DashboardQuickCreateDialog({
  kind,
  saving,
  error,
  onKindChange,
  onClose,
  onCreate,
}: {
  kind: DashboardQuickCreateKind;
  saving?: boolean;
  error?: string | null;
  onKindChange: (kind: DashboardQuickCreateKind) => void;
  onClose: () => void;
  onCreate: (draft: CRMRecord, customFields?: CRMApiRecord) => void;
}) {
  return (
    <CreateRecordDialog
      kind={kind}
      saving={saving}
      error={error}
      onClose={onClose}
      onCreate={onCreate}
      header={
        <div className="flex flex-wrap gap-2">
          {dashboardQuickCreateKinds.map((item) => (
            <Button key={item.kind} type="button" size="sm" variant={kind === item.kind ? "default" : "outline"} onClick={() => onKindChange(item.kind)} disabled={saving}>
              {item.label}
            </Button>
          ))}
        </div>
      }
    />
  );
}

function CreateRecordDialog({ kind, saving, error, onClose, onCreate, header }: { kind: CRMPageKind; saving?: boolean; error?: string | null; onClose: () => void; onCreate: (draft: CRMRecord, customFields?: CRMApiRecord) => void; header?: React.ReactNode }) {
  const title = actionFor(kind) || "Create record";
  const entity = apiEntityForKind[kind];
  const customFieldState = useCrmRecords<CRMApiRecord>(entity && customFieldEntities.some((item) => item.value === entity) ? "custom-fields" : undefined, [], entity ? { entityType: entity } : undefined);
  const formFields = quickFormFieldsByKind[kind] || [
    { key: "name", label: "Name", required: true, placeholder: "Record name" },
    { key: "status", label: "Status", placeholder: "New" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" as const },
  ];
  const defaultName = `New ${pageTitles[kind].replace("CRM ", "").replace(/s$/, "")}`;
  const initialDraft = useMemo(() => ({
    name: defaultName,
    subject: defaultName,
    owner: "",
    status: kind === "tickets" ? "Open" : "New",
    nextFollowUp: new Date().toISOString().slice(0, 10),
  }), [defaultName, kind]);
  const [draft, setDraft] = useState<CRMRecord>(initialDraft);
  const [customValues, setCustomValues] = useState<CRMApiRecord>({});
  useEffect(() => {
    setDraft(initialDraft);
    setCustomValues({});
  }, [initialDraft]);
  const patchDraft = (key: string, value: CRMApiValue) => setDraft((current) => ({ ...current, [key]: value }));
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start justify-between">
          <div><CardTitle>{title}</CardTitle><p className="text-sm text-muted-foreground">Fast-create form with required CRM fields.</p></div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {header}
          {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
          <div className="grid gap-4 md:grid-cols-2">
            {formFields.map((field) => (
              <div key={field.key} className={field.width === "full" ? "md:col-span-2" : undefined}>
                <Field label={`${field.label}${field.required ? " *" : ""}`}>
                  <QuickFormInput field={field} draft={draft} patchDraft={patchDraft} />
                </Field>
              </div>
            ))}
          </div>
          {customFieldState.data.filter((field) => Boolean(field.isVisible ?? field.is_visible ?? true)).map((field) => (
            <Field key={String(field.id)} label={`${String(field.fieldName || field.label || field.field_key)}${field.isRequired || field.is_required ? " *" : ""}`}>
              <CustomFieldInput field={field} value={customValues[String(field.fieldKey || field.field_key || field.id)]} onChange={(value) => setCustomValues((current) => ({ ...current, [String(field.fieldKey || field.field_key || field.id)]: value }))} />
            </Field>
          ))}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button><Button onClick={() => onCreate(draft, customValues)} disabled={saving}>{saving ? "Creating..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CustomFieldInput({ field, value, onChange }: { field: CRMApiRecord; value: CRMApiRecord[string]; onChange: (value: CRMApiRecord[string]) => void }) {
  const type = String(field.fieldType || field.field_type || "text");
  const options = parseOptions(field.options ?? field.options_json);
  if (type === "dropdown") {
    return <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={String(value || "")} onChange={(event) => onChange(event.target.value)}><option value="">Select</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>;
  }
  if (type === "multi_select") {
    return <Input value={Array.isArray(value) ? value.join(", ") : String(value || "")} onChange={(event) => onChange(parseOptions(event.target.value))} placeholder={options.length ? options.join(", ") : "Comma separated values"} />;
  }
  if (type === "checkbox") {
    return <ToggleBox checked={Boolean(value)} onChange={onChange} />;
  }
  const inputType = type === "number" || type === "currency" || type === "user" || type === "owner" ? "number" : type === "date" ? "date" : type === "datetime" ? "datetime-local" : type === "email" ? "email" : type === "url" ? "url" : "text";
  return <Input type={inputType} value={String(value || "")} onChange={(event) => onChange(event.target.value)} />;
}

function QuickFormInput({
  field,
  draft,
  patchDraft,
}: {
  field: QuickFormField;
  draft: CRMRecord;
  patchDraft: (key: string, value: CRMApiValue) => void;
}) {
  const value = String(draft[field.key] || "");
  const updateValue = (nextValue: string) => {
    patchDraft(field.key, nextValue);
    if (field.key === "name" && !String(draft.subject || "").trim()) {
      patchDraft("subject", nextValue);
    }
    if (field.key === "subject" && !String(draft.name || "").trim()) {
      patchDraft("name", nextValue);
    }
  };

  if (field.type === "select") {
    return (
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={(event) => updateValue(event.target.value)}>
        <option value="">{field.placeholder || "Select"}</option>
        {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
        value={value}
        placeholder={field.placeholder}
        onChange={(event) => updateValue(event.target.value)}
      />
    );
  }

  return (
    <Input
      type={field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "email" ? "email" : "text"}
      value={value}
      placeholder={field.placeholder}
      onChange={(event) => updateValue(event.target.value)}
    />
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function TimelineItem({ text }: { text: string }) {
  return <div className="flex gap-2"><span className="mt-1 h-2 w-2 rounded-full bg-primary" /><span>{text}</span></div>;
}

function Insight({ text }: { text: string }) {
  return <div className="rounded-lg border bg-muted/40 p-4 text-sm">{text}</div>;
}

function filterRecords(records: CRMRecord[], search: string, view: string, filters: CRMFilters) {
  const text = search.toLowerCase();
  const today = new Date("2026-05-10");
  const weekEnd = new Date("2026-05-17");
  return records.filter((row) => {
    const matchesSearch = Object.values(row).join(" ").toLowerCase().includes(text);
    const matchesOwner = filters.owner === "all" || row.owner === filters.owner;
    const matchesStatus = filters.status === "all" || row.status === filters.status;
    const matchesType = filters.type === "all" || row.type === filters.type;
    const matchesTerritory = filters.territory === "all" || String(row.territoryId || row.territory_id || "") === filters.territory;
    const dueValue = String(row.due || row.nextFollowUp || row.closeDate || row.expiryDate || "");
    const dueDate = dueValue ? new Date(dueValue) : null;
    const matchesView =
      view === "Due this week"
        ? !!dueDate && dueDate >= today && dueDate <= weekEnd
        : view === "Hot pipeline"
          ? ["Hot", "High", "Urgent", "Critical", "Negotiation", "Contract Sent"].some((value) => Object.values(row).includes(value))
          : view === "No follow-up"
            ? !dueValue
            : true;
    return matchesSearch && matchesOwner && matchesStatus && matchesType && matchesTerritory && matchesView;
  });
}

function uniqueValues(records: CRMRecord[], key: string) {
  return Array.from(new Set(records.map((row) => row[key]).filter(Boolean).map(String))).sort();
}

function parseCsv(text: string): CRMRecord[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    return headers.reduce<CRMRecord>((row, header, index) => {
      row[header || `field${index + 1}`] = values[index] || "";
      return row;
    }, {});
  });
}

function splitCsvLine(line: string) {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current);
  return values.map((value) => value.trim());
}

function compareValues(a: unknown, b: unknown, direction: "asc" | "desc") {
  const multiplier = direction === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
  const dateA = Date.parse(String(a));
  const dateB = Date.parse(String(b));
  if (!Number.isNaN(dateA) && !Number.isNaN(dateB)) return (dateA - dateB) * multiplier;
  return String(a ?? "").localeCompare(String(b ?? "")) * multiplier;
}

function renderCell(key: string, value: CRMApiRecord[string]) {
  if (key === "leadScore") return <Badge className={statusColor(scoreLabel(Number(value || 0)))}>{Number(value || 0)} / {scoreLabel(Number(value || 0))}</Badge>;
  if (isBadgeField(key)) return <Badge className={statusColor(String(value))}>{String(value)}</Badge>;
  if (key.toLowerCase().includes("date") || key.toLowerCase().includes("due") || key.toLowerCase().includes("followup")) return formatDate(String(value));
  if (typeof value === "number" && isMoneyField(key)) return formatCurrency(value);
  return String(value ?? "");
}

function scoreLabel(score: number) {
  if (score <= 30) return "Cold";
  if (score <= 70) return "Warm";
  return "Hot";
}

function valueText(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function duplicateRecordTitle(record: CRMApiRecord, entityType: string) {
  if (entityType === "account") return valueText(record.name) || `Account #${record.id}`;
  return valueText(record.full_name || record.name) || `${labelFor(entityType)} #${record.id}`;
}

function mergeFieldsFor(entityType: string) {
  if (entityType === "account") return ["name", "website", "email", "phone", "industry", "account_type", "city", "state", "country", "notes"];
  if (entityType === "lead") return ["first_name", "last_name", "full_name", "email", "phone", "company_name", "job_title", "source", "status", "rating", "notes"];
  return ["first_name", "last_name", "full_name", "email", "phone", "job_title", "department", "lifecycle_stage", "status", "notes"];
}

function mergeDefaultFieldValues(records: CRMApiRecord[], entityType: string) {
  return mergeFieldsFor(entityType).reduce<CRMApiRecord>((values, field) => {
    const recordWithValue = records.find((record) => valueText(record[field]));
    values[field] = recordWithValue?.[field] as CRMApiRecord[string];
    return values;
  }, {});
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-medium">{value}</p>
    </div>
  );
}

function FilterSelect({ label, value, values, allLabel, onChange }: { label: string; value: string; values: string[]; allLabel: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium">{label}</span>
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="all">{allLabel}</option>
        {values.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
      </select>
    </label>
  );
}

function uniqueCalendarValues(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function calendarRange(cursor: Date, view: CalendarView) {
  if (view === "month") {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const end = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0, 23, 59, 59);
    start.setDate(start.getDate() - start.getDay());
    end.setDate(end.getDate() + (6 - end.getDay()));
    return { start, end };
  }
  if (view === "week") {
    const start = startOfDay(cursor);
    start.setDate(start.getDate() - start.getDay());
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    end.setHours(23, 59, 59, 999);
    return { start, end };
  }
  const start = startOfDay(cursor);
  const end = new Date(start);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function startOfDay(date: Date) {
  const output = new Date(date);
  output.setHours(0, 0, 0, 0);
  return output;
}

function monthDays(cursor: Date) {
  const { start, end } = calendarRange(cursor, "month");
  const days: Date[] = [];
  const day = new Date(start);
  while (day <= end) {
    days.push(new Date(day));
    day.setDate(day.getDate() + 1);
  }
  return days;
}

function weekDays(cursor: Date) {
  const { start } = calendarRange(cursor, "week");
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseLocalDateKey(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year || 1970, (month || 1) - 1, day || 1);
}

function eventsForDay(events: CRMCalendarEvent[], day: Date) {
  const key = dateKey(day);
  return events.filter((event) => dateKey(new Date(event.start)) === key).sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
}

function calendarTitle(cursor: Date, view: CalendarView) {
  if (view === "month") return cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  if (view === "week") {
    const days = weekDays(cursor);
    return `${days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
  }
  return cursor.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function timeLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function dateWithTime(date: Date, time: string) {
  const [hours, minutes] = time.split(":").map(Number);
  const output = new Date(date);
  output.setHours(hours || 0, minutes || 0, 0, 0);
  return output;
}

function calendarPatchFor(event: CRMCalendarEvent, start: Date, end: Date): CRMApiRecord {
  if (event.source === "tasks") return { due_date: start.toISOString() };
  if (event.source === "meetings") return { start_time: start.toISOString(), end_time: end.toISOString() };
  if (event.source === "calls") return { call_time: start.toISOString() };
  if (event.source === "activities") return { activity_date: start.toISOString(), due_date: start.toISOString() };
  if (event.source === "quotations") return { expiry_date: dateKey(start) };
  if (event.source === "deals") return { expected_close_date: dateKey(start) };
  return {};
}

function relatedCalendarPath(event: CRMCalendarEvent) {
  if (event.entityType === "lead" && event.entityId) return `/crm/leads/${event.entityId}`;
  if (event.entityType === "contact" && event.entityId) return `/crm/contacts/${event.entityId}`;
  if (event.entityType === "account" && event.entityId) return `/crm/accounts/${event.entityId}`;
  if (event.entityType === "deal" && event.entityId) return `/crm/deals/${event.entityId}`;
  if (event.entityType === "quotation" && event.entityId) return `/crm/quotations/${event.entityId}`;
  return "";
}

function markCalendarTaskComplete(event: CRMCalendarEvent, setEvents: React.Dispatch<React.SetStateAction<CRMCalendarEvent[]>>, setError: React.Dispatch<React.SetStateAction<string | null>>) {
  crmApi
    .update("tasks", event.recordId, { status: "Completed", completed_at: new Date().toISOString() })
    .then(() => setEvents((items) => items.map((item) => (item.id === event.id ? { ...item, status: "Completed" } : item))))
    .catch((err) => setError(err?.response?.data?.detail || "Could not mark task complete."));
}

function normalizeInlineValue(config: InlineEditConfig, value: string | number | boolean | null) {
  if (value === null || value === "") return null;
  if (config.type === "number") return Number(value);
  if (config.type === "date") return String(value).slice(0, 10);
  return value;
}

function detailPathFor(kind: CRMPageKind) {
  if (kind === "leads") return "/crm/leads";
  if (kind === "contacts") return "/crm/contacts";
  if (kind === "companies") return "/crm/accounts";
  if (kind === "deals") return "/crm/deals";
  if (kind === "quotations") return "/crm/quotations";
  return "";
}

function normalizeApiRecord(kind: string, record: CRMApiRecord): CRMRecord {
  const id = Number(record.id || 0);
  if (kind === "leads") {
    return { id, name: String(record.full_name || [record.first_name, record.last_name].filter(Boolean).join(" ") || "Lead"), company: String(record.company_name || ""), email: String(record.email || ""), phone: String(record.phone || ""), source: String(record.source || "Other"), status: String(record.status || "New"), rating: String(record.scoreLabel || record.lead_score_label || record.rating || "Warm"), leadScore: Number(record.leadScore || record.lead_score || 0), scoreLabel: String(record.scoreLabel || record.lead_score_label || record.rating || "Cold"), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), value: Number(record.estimated_value || 0), nextFollowUp: String(record.next_follow_up_at || ""), lastContacted: String(record.last_contacted_at || ""), industry: String(record.industry || ""), createdAt: String(record.createdAt || "") };
  }
  if (kind === "contacts") {
    return { id, name: String(record.full_name || [record.first_name, record.last_name].filter(Boolean).join(" ") || "Contact"), email: String(record.email || ""), phone: String(record.phone || ""), companyId: Number(record.company_id || 0), title: String(record.job_title || ""), stage: String(record.lifecycle_stage || ""), source: String(record.source || ""), status: String(record.status || "Active"), owner: String(record.ownerId || record.owner_user_id || "") };
  }
  if (kind === "companies") {
    return { id, name: String(record.name || "Company"), industry: String(record.industry || ""), type: String(record.account_type || ""), status: String(record.status || "Active"), revenue: Number(record.annual_revenue || 0), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), city: String(record.city || ""), email: String(record.email || "") };
  }
  if (kind === "deals") {
    return { id, name: String(record.name || "Deal"), companyId: Number(record.company_id || 0), contactId: Number(record.contact_id || 0), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), stageId: Number(record.stage_id || 0), pipelineId: Number(record.pipeline_id || 0), stage: String(record.stage || record.status || "Open"), amount: Number(record.amount || 0), probability: Number(record.probability || 0), closeDate: String(record.expected_close_date || ""), nextStep: String(record.description || record.status || ""), status: String(record.status || "Open") };
  }
  if (kind === "activities") {
    return { id, subject: String(record.subject || "Activity"), type: String(record.activity_type || ""), owner: String(record.ownerId || record.owner_user_id || ""), due: String(record.due_date || ""), status: String(record.status || "Pending"), priority: String(record.priority || "Medium") };
  }
  if (kind === "tasks") {
    return { id, subject: String(record.title || "Task"), owner: String(record.ownerId || record.owner_user_id || ""), due: String(record.due_date || ""), status: String(record.status || "To Do"), priority: String(record.priority || "Medium") };
  }
  if (kind === "meetings") {
    return { id, subject: String(record.title || "Meeting"), type: "Meeting", location: String(record.location || ""), due: String(record.start_time || ""), status: String(record.status || "Scheduled"), syncStatus: String(record.syncStatus || record.sync_status || "not_synced"), externalProvider: String(record.externalProvider || record.external_provider || "") };
  }
  if (kind === "products") {
    return { id, name: String(record.name || "Product"), sku: String(record.sku || ""), category: String(record.category || ""), price: Number(record.unit_price || 0), status: String(record.status || "Active") };
  }
  if (kind === "quotations") {
    return { id, quote: String(record.quote_number || ""), dealId: Number(record.deal_id || 0), companyId: Number(record.company_id || 0), status: String(record.status || "Draft"), issueDate: String(record.issue_date || ""), expiryDate: String(record.expiry_date || ""), total: Number(record.total_amount || 0) };
  }
  if (kind === "campaigns") {
    return { id, name: String(record.name || "Campaign"), type: String(record.campaign_type || ""), status: String(record.status || "Planned"), startDate: String(record.start_date || ""), endDate: String(record.end_date || ""), budget: Number(record.budget_amount || 0), expectedRevenue: Number(record.expected_revenue || 0) };
  }
  if (kind === "tickets") {
    return { id, number: String(record.ticket_number || ""), subject: String(record.subject || "Ticket"), priority: String(record.priority || "Medium"), status: String(record.status || "Open"), category: String(record.category || ""), source: String(record.source || "Manual"), due: String(record.due_date || "") };
  }
  if (kind === "files") {
    return { id, name: String(record.original_name || record.file_name || "File"), fileName: String(record.file_name || ""), type: String(record.mime_type || ""), size: Number(record.size_bytes || 0), visibility: String(record.visibility || "Internal"), storagePath: String(record.storage_path || "") };
  }
  if (kind === "settings") {
    return { id, setting: String(record.label || record.field_key || "Custom field"), area: String(record.entity || ""), type: String(record.field_type || ""), status: record.is_active === false ? "Inactive" : "Ready" };
  }
  if (kind === "admin") {
    return { id, adminArea: String(record.full_name || "Owner"), permission: String(record.role || ""), email: String(record.email || ""), status: String(record.status || "Active") };
  }
  if (kind === "lead-scoring-rules") {
    return { id, name: String(record.name || ""), field: String(record.field || ""), operator: String(record.operator || ""), value: String(record.value || ""), points: Number(record.points || 0), is_active: Boolean(record.is_active ?? record.isActive ?? true) };
  }
  return { id, ...record };
}

function recordToLead(record: CRMRecord): CRMLead {
  return {
    id: Number(record.id || 0),
    name: String(record.name || record.full_name || "Lead"),
    company: String(record.company || record.company_name || ""),
    email: String(record.email || ""),
    phone: String(record.phone || ""),
    source: String(record.source || "Other"),
    status: String(record.status || "New"),
    rating: String(record.rating || "Warm"),
    leadScore: Number(record.leadScore || record.lead_score || 0),
    scoreLabel: String(record.scoreLabel || record.lead_score_label || record.rating || "Cold"),
    owner: String(record.owner || record.ownerId || ""),
    value: Number(record.value || record.estimated_value || 0),
    nextFollowUp: String(record.nextFollowUp || record.next_follow_up_at || ""),
    lastContacted: String(record.lastContacted || record.last_contacted_at || ""),
    industry: String(record.industry || ""),
  };
}

function recordToDeal(record: CRMRecord, stages: CRMRecord[]): CRMDeal {
  const stageId = Number(record.stageId || record.stage_id || 0);
  const stage = stages.find((item) => Number(item.id) === stageId);
  return {
    id: Number(record.id || 0),
    name: String(record.name || "Deal"),
    company: String(record.company || record.companyId || record.company_id || ""),
    contact: String(record.contact || record.contactId || record.contact_id || ""),
    owner: String(record.owner || record.ownerId || ""),
    pipelineId: Number(record.pipelineId || record.pipeline_id || stage?.pipeline_id || 0),
    stageId,
    stage: String(record.stage || stage?.name || record.status || "Open"),
    amount: Number(record.amount || 0),
    probability: Number(record.probability || 0),
    closeDate: String(record.closeDate || record.expected_close_date || ""),
    nextStep: String(record.nextStep || record.description || ""),
    products: [],
  };
}

function createPayloadForKind(kind: CRMPageKind, record: CRMRecord): CRMApiRecord {
  const ownerId = Number(record.owner || record.ownerId || 0) || undefined;
  if (kind === "leads") {
    const name = String(record.name || "New Lead");
    const [firstName, ...rest] = name.split(" ");
    return { first_name: firstName || name, last_name: rest.join(" "), full_name: name, email: record.email, phone: record.phone, company_name: record.company, source: record.source, status: record.status, rating: record.rating, lead_score: record.leadScore, estimated_value: record.value, industry: record.industry, next_follow_up_at: record.nextFollowUp, ownerId };
  }
  if (kind === "contacts") {
    const name = String(record.name || "New Contact");
    const [firstName, ...rest] = name.split(" ");
    return { first_name: firstName || name, last_name: rest.join(" "), full_name: name, email: record.email, phone: record.phone, lifecycle_stage: record.stage || "Lead", source: record.source, status: record.status, next_follow_up_at: record.nextFollowUp, ownerId };
  }
  if (kind === "companies") return { name: record.name, industry: record.industry, account_type: record.type, status: record.status, annual_revenue: record.revenue, ownerId };
  if (kind === "deals") return { name: record.name, pipeline_id: record.pipelineId || 1, stage_id: record.stageId || 1, amount: record.amount, probability: record.probability, status: record.status || "Open", expected_close_date: record.nextFollowUp, ownerId };
  if (kind === "activities") return { activity_type: record.type || "Task", subject: record.subject || record.name || "Activity", status: record.status, priority: record.priority, due_date: record.nextFollowUp, ownerId };
  if (kind === "tasks") return { title: record.subject || record.name || "Task", status: record.status, priority: record.priority, due_date: record.nextFollowUp, ownerId };
  if (kind === "products") return { name: record.name, sku: record.sku, category: record.category, unit_price: record.price, status: record.status, ownerId };
  if (kind === "quotations") return { quote_number: record.quote || `QT-${Date.now()}`, issue_date: record.issueDate || new Date().toISOString().slice(0, 10), expiry_date: record.expiryDate || new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10), status: record.status || "Draft", total_amount: record.total };
  if (kind === "campaigns") return { name: record.name, campaign_type: record.type || "Email", status: record.status || "Planned", start_date: record.startDate || new Date().toISOString().slice(0, 10), end_date: record.endDate || new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10), budget_amount: record.budget || 0, expected_revenue: record.expectedRevenue || 0, ownerId };
  if (kind === "tickets") return { ticket_number: record.number || `TCK-${Date.now()}`, subject: record.subject || record.name || "Customer request", priority: record.priority || "Medium", status: record.status || "Open", category: record.category || "General", source: record.source || "Manual", due_date: record.nextFollowUp, ownerId };
  if (kind === "files") return { file_name: record.fileName || `crm-file-${Date.now()}.txt`, original_name: record.name || "CRM file", storage_path: record.storagePath || "metadata-only", mime_type: record.type || "text/plain", size_bytes: record.size || 0, visibility: record.visibility || "Internal" };
  if (kind === "settings") return { entity: record.area || "leads", field_key: String(record.setting || "custom_field").toLowerCase().replace(/\W+/g, "_"), label: record.setting || "Custom field", field_type: record.type || "text" };
  if (kind === "admin") return { full_name: record.adminArea || "CRM Owner", email: record.email || `owner${Date.now()}@example.com`, role: record.permission || "Sales Executive", status: record.status || "Active" };
  return record;
}

function defaultRecordFor(kind: CRMPageKind, id: number, title: string): CRMRecord {
  if (kind === "leads") return {
    leadId: `LD-${String(1100 + id).padStart(4, "0")}`,
    name: `${title} ${id}`,
    company: "New Account",
    designation: "Decision Maker",
    email: `lead${id}@newaccount.example`,
    phone: "+91 90000 00000",
    mobile: "+91 90000 00001",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    source: "Website",
    campaign: "Inbound Demo",
    status: "New",
    rating: "Warm",
    lifecycleStage: "Lead",
    owner: "Ananya Rao",
    value: 250000,
    expectedCloseDate: "2026-06-20",
    productInterest: "CRM Starter",
    requirement: "Evaluate CRM workflow",
    budgetRange: "2L-5L",
    decisionMaker: "Yes",
    leadScore: 62,
    probability: "25%",
    nextFollowUp: "2026-05-14",
    lastContacted: "2026-05-10",
    lastActivity: "Created lead",
    preferredChannel: "Email",
    tags: "New, Website",
    notes: "Fresh inbound lead",
  };
  if (kind === "contacts") return {
    contactId: `CT-${String(2100 + id).padStart(4, "0")}`,
    name: `${title} ${id}`,
    company: "New Account",
    title: "Manager",
    department: "Sales",
    email: `contact${id}@newaccount.example`,
    alternateEmail: "",
    phone: "+91 90000 00000",
    mobile: "+91 90000 00001",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    lifecycle: "Opportunity",
    accountType: "Prospect",
    owner: "Ananya Rao",
    status: "Active",
    source: "Manual Entry",
    leadSource: "Website",
    lastContacted: "2026-05-10",
    nextFollowUp: "2026-05-14",
    birthday: "1990-01-01",
    linkedin: "linkedin.com/in/new-contact",
    preferredChannel: "Email",
    emailOptIn: "Yes",
    smsOptIn: "Yes",
    openDeals: 0,
    lifetimeValue: 0,
    supportStatus: "None",
    tags: "New",
    notes: "New CRM contact",
  };
  if (kind === "deals") return { name: `${title} ${id}`, company: "New Account", owner: "Karan Shah", stage: "Prospecting", amount: 500000, probability: "10%", closeDate: "2026-06-15" };
  if (kind === "tickets") return { number: `TCK-${1100 + id}`, subject: "New customer request", priority: "Medium", status: "Open", company: "New Account", owner: "Support Desk" };
  return { name: `${title} ${id}`, owner: "Ananya Rao", status: "New", nextFollowUp: "2026-05-14" };
}

function toLeadRecord(lead: CRMLead): CRMRecord {
  const index = lead.id - 1;
  const designations = ["Founder", "Operations Head", "Director", "Clinic Administrator", "Plant Manager", "Retail Growth Lead", "Managing Partner", "Principal Consultant"];
  const cities = ["Hyderabad", "Kochi", "Pune", "Mumbai", "Chennai", "Bengaluru", "Delhi", "Ahmedabad"];
  const states = ["Telangana", "Kerala", "Maharashtra", "Maharashtra", "Tamil Nadu", "Karnataka", "Delhi", "Gujarat"];
  const campaigns = ["Website Demo", "Referral Connect", "Education Expo", "Healthcare Outreach", "Partner Pipeline", "Retail Growth Ads", "Marketplace Listing", "Social Prospecting"];
  const products = ["CRM Growth", "CRM Starter", "Training Pack", "Support Retainer", "Enterprise Suite", "Marketing Automation", "CRM Growth", "Data Migration"];
  const requirements = [
    "Centralize sales follow-ups and opportunity tracking",
    "Manage site visits, broker leads, and quotation follow-ups",
    "Track admissions enquiries and training partnerships",
    "Improve patient enquiry follow-up and SLA visibility",
    "Connect plant enquiries with ERP implementation pipeline",
    "Automate retail campaigns and lead assignment",
    "Track advisory prospects and compliance-heavy deal notes",
    "Manage consulting proposals and cloud migration leads",
  ];

  return {
    leadId: `LD-${String(1000 + lead.id).padStart(4, "0")}`,
    name: lead.name,
    company: lead.company,
    designation: designations[index] || "Decision Maker",
    email: lead.email,
    phone: lead.phone,
    mobile: String(lead.phone || "").replace("110", "220"),
    city: cities[index] || "Bengaluru",
    state: states[index] || "Karnataka",
    country: "India",
    source: lead.source,
    campaign: campaigns[index] || lead.source,
    status: lead.status,
    rating: lead.rating,
    lifecycleStage: lead.status === "Converted" ? "Customer" : "Lead",
    owner: lead.owner,
    value: lead.value,
    expectedCloseDate: ["2026-05-28", "2026-06-10", "2026-06-02", "2026-06-18", "2026-05-24", "2026-05-30", "2026-06-05", "2026-06-12"][index] || "2026-06-20",
    productInterest: products[index] || "CRM Starter",
    requirement: requirements[index] || "Evaluate CRM workflow",
    budgetRange: lead.value >= 800000 ? "8L+" : lead.value >= 400000 ? "4L-8L" : "2L-4L",
    decisionMaker: ["Yes", "No", "Influencer", "Yes", "Yes", "Influencer", "Yes", "No"][index] || "Yes",
    leadScore: [92, 74, 68, 48, 95, 71, 88, 41][index] || 60,
    probability: lead.rating === "Hot" ? "70%" : lead.rating === "Warm" ? "40%" : "15%",
    nextFollowUp: lead.nextFollowUp,
    lastContacted: lead.lastContacted,
    lastActivity: ["Discovery call", "Referral email", "Event scan", "Intro call", "Partner handoff", "Campaign click", "Marketplace enquiry", "Social DM"][index] || "Follow-up",
    preferredChannel: ["Phone", "Email", "WhatsApp", "Phone", "Email", "Email", "Phone", "LinkedIn"][index] || "Email",
    tags: [lead.rating, lead.source, lead.industry].join(", "),
    notes: requirements[index] || "Qualified CRM enquiry",
  };
}

function toContactRecord(lead: CRMLead): CRMRecord {
  const index = lead.id - 1;
  const leadRecord = toLeadRecord(lead);
  const titles = ["Founder", "Sales Director", "Program Head", "Clinic Admin", "Manufacturing Head", "Retail Lead", "Partner", "Consultant"];
  const departments = ["Leadership", "Sales", "Admissions", "Operations", "Manufacturing", "Marketing", "Advisory", "Consulting"];

  return {
    contactId: `CT-${String(2000 + lead.id).padStart(4, "0")}`,
    name: lead.name,
    company: lead.company,
    title: titles[index] || String(leadRecord.designation),
    department: departments[index] || "Sales",
    email: lead.email,
    alternateEmail: String(lead.email || "").replace("@", ".alt@"),
    phone: lead.phone,
    mobile: String(leadRecord.mobile),
    city: String(leadRecord.city),
    state: String(leadRecord.state),
    country: "India",
    lifecycle: lead.status === "Converted" ? "Customer" : "Opportunity",
    accountType: lead.status === "Converted" ? "Customer" : "Prospect",
    owner: lead.owner,
    status: lead.status === "Converted" ? "Active" : "Open",
    source: lead.source,
    leadSource: lead.source,
    lastContacted: lead.lastContacted,
    nextFollowUp: lead.nextFollowUp,
    birthday: ["1986-02-14", "1990-08-21", "1982-11-02", "1988-04-18", "1979-07-09", "1992-12-05", "1984-09-27", "1991-03-30"][index] || "1990-01-01",
    linkedin: `linkedin.com/in/${lead.name.toLowerCase().replace(/\s+/g, "-")}`,
    preferredChannel: String(leadRecord.preferredChannel),
    emailOptIn: index % 3 === 0 ? "No" : "Yes",
    smsOptIn: index % 2 === 0 ? "Yes" : "No",
    openDeals: lead.status === "Converted" ? 0 : 1,
    lifetimeValue: lead.status === "Converted" ? lead.value : 0,
    supportStatus: lead.status === "Converted" ? "Active SLA" : "None",
    tags: `${lead.rating}, ${lead.industry}`,
    notes: `Primary contact for ${lead.company}`,
  };
}

function descriptionFor(kind: CRMPageKind) {
  const descriptions: Record<CRMPageKind, string> = {
    dashboard: "",
    leads: "Capture, qualify, assign, import, export, and convert leads.",
    contacts: "Manage people, lifecycle stages, follow-up dates, and account links.",
    companies: "Account master data with owners, industries, revenue, and status.",
    deals: "Opportunities with amount, probability, products, quotations, and owners.",
    pipeline: "",
    pipelineSettings: "Multiple sales pipelines, custom stages, probabilities, colors, and win/loss mapping.",
    activities: "Calls, emails, meetings, demos, proposals, and follow-up outcomes.",
    tasks: "CRM task queue for owners, teams, reminders, and related records.",
    calendar: "Follow-ups, meetings, expected close dates, campaigns, and quote expiries.",
    calendarIntegrations: "Google, Outlook, and development calendar sync configuration.",
    webhooks: "Outbound signed events for Zapier, n8n, and CRM integrations.",
    campaigns: "Campaign planning, lead generation, ROI, and conversion tracking.",
    products: "Products and services used in deals and quotations.",
    quotations: "Draft, send, accept, reject, and convert quotations.",
    approvalSettings: "Configure deal discount, quotation, stage, high-value, contract, and price approvals.",
    myApprovals: "Review CRM approvals assigned to you and record decisions.",
    duplicates: "Detect and review duplicate CRM leads, contacts, and accounts.",
    territories: "Manage sales territories, rule priority, assigned users, and automatic CRM routing.",
    tickets: "Customer support tickets linked to contacts, companies, and deals.",
    files: "Attachments for leads, contacts, accounts, deals, quotes, and tickets.",
    reports: "",
    automation: "Owner assignment, reminders, quote expiry, critical ticket escalation, and stale lead rules.",
    leadCash: "Lead-to-cash conversion from lead to contact, account, deal, quote, and invoice handoff.",
    forecasting: "Weighted pipeline, monthly target tracking, quota coverage, and commit/best-case/at-risk views.",
    customer360: "Unified customer view across contacts, companies, deals, tickets, activities, quotations, files, and campaigns.",
    importExport: "Field mapping, duplicate detection, validation preview, rollback, and import history.",
    settings: "Lead sources, statuses, pipelines, quote settings, ticket categories, notifications, and import/export.",
    leadScoring: "Automatic and manual numeric lead scoring from 0 to 100.",
    featureChecklist: "Admin/developer readiness matrix for CRM APIs, frontend surfaces, and integration notes.",
    admin: "CRM roles, permissions, teams, audit logs, templates, and system settings.",
  };
  return descriptions[kind];
}

function actionFor(kind: CRMPageKind) {
  if (["leads", "contacts", "companies", "deals", "activities", "tasks", "campaigns", "products", "quotations", "tickets"].includes(kind)) return `Create ${pageTitles[kind].replace("CRM ", "").replace(/s$/, "")}`;
  if (kind === "approvalSettings") return "Create workflow";
  if (kind === "pipelineSettings") return "Back to board";
  if (kind === "leadScoring") return "Recalculate all";
  if (kind === "automation") return "Create rule";
  if (kind === "files") return "Upload metadata";
  return undefined;
}

function isBadgeField(key: string) {
  const lower = key.toLowerCase();
  return ["status", "priority", "rating", "stage", "visibility", "type"].some((item) => lower.includes(item));
}

function labelFor(key: string) {
  return key.replace(/_/g, " ").replace(/-/g, " ").replace(/([A-Z])/g, " $1").replace(/\b\w/g, (char) => char.toUpperCase());
}

function isMoneyField(key: string) {
  const lower = key.toLowerCase();
  return ["amount", "value", "revenue", "budget", "price", "total"].some((item) => lower.includes(item));
}

function stageProbability(stage: string) {
  return ({
    Prospecting: 10,
    Qualification: 25,
    "Needs Analysis": 40,
    "Proposal Sent": 55,
    Negotiation: 70,
    "Contract Sent": 85,
    Won: 100,
    Lost: 0,
  } as Record<string, number>)[stage] ?? 0;
}
