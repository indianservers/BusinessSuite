import type React from "react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, CalendarClock, Download, FileSpreadsheet, Gauge, LayoutDashboard, LineChart, Receipt, Search, ShieldAlert, Sparkles, Table2 } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { analyticsApi, type AnalyticsList, type AnalyticsRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";

type SectionKey = "home" | "builder" | "reports" | "dashboards" | "schedules" | "exports" | "funnel" | "forecast" | "profitability" | "collections" | "campaigns" | "anomalies";

const sections: Array<{ key: SectionKey; label: string; path: string; icon: typeof BarChart3 }> = [
  { key: "home", label: "Analytics", path: "/analytics", icon: BarChart3 },
  { key: "builder", label: "Builder", path: "/analytics/report-builder", icon: Table2 },
  { key: "reports", label: "Reports", path: "/analytics/reports", icon: FileSpreadsheet },
  { key: "dashboards", label: "Dashboards", path: "/analytics/dashboards", icon: LayoutDashboard },
  { key: "schedules", label: "Schedules", path: "/analytics/scheduled-reports", icon: CalendarClock },
  { key: "exports", label: "Exports", path: "/analytics/exports", icon: Download },
  { key: "funnel", label: "Funnel", path: "/analytics/funnel", icon: Gauge },
  { key: "forecast", label: "Forecast", path: "/analytics/forecast", icon: LineChart },
  { key: "profitability", label: "Profitability", path: "/analytics/profitability", icon: Receipt },
  { key: "collections", label: "Collections", path: "/analytics/collections", icon: Receipt },
  { key: "campaigns", label: "Campaigns", path: "/analytics/campaigns", icon: Search },
  { key: "anomalies", label: "Anomalies", path: "/analytics/anomalies", icon: ShieldAlert },
];

function activeSection(pathname: string): SectionKey {
  if (pathname.includes("report-builder")) return "builder";
  if (pathname.includes("reports")) return "reports";
  if (pathname.includes("dashboards")) return "dashboards";
  if (pathname.includes("scheduled-reports")) return "schedules";
  if (pathname.includes("exports")) return "exports";
  if (pathname.includes("funnel")) return "funnel";
  if (pathname.includes("forecast")) return "forecast";
  if (pathname.includes("profitability")) return "profitability";
  if (pathname.includes("collections")) return "collections";
  if (pathname.includes("campaigns")) return "campaigns";
  if (pathname.includes("anomalies")) return "anomalies";
  return "home";
}

export default function AnalyticsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">Business Suite</p>
        <h1 className="text-2xl font-semibold">Analytics and Export Engine</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Report builder, dashboard builder, cross-module CRM/SRM/PMS analytics, scheduled runs, audited CSV/XLSX/PDF exports, and anomaly placeholders.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {sections.map((item) => {
            const Icon = item.icon;
            return <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>;
          })}
          <Button variant="outline" size="sm" onClick={() => navigate("/ai/report-explainer?module_name=analytics")}><Sparkles className="h-4 w-4" />AI Explainer</Button>
        </div>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "home" ? <Home /> : null}
        {active === "builder" ? <ReportBuilder /> : null}
        {active === "reports" ? <Reports selectedId={params.id} /> : null}
        {active === "dashboards" ? <Dashboards selectedId={params.id} /> : null}
        {active === "schedules" ? <Schedules /> : null}
        {active === "exports" ? <ExportAudit /> : null}
        {active === "funnel" ? <DataSection title="Funnel Analytics" queryKey="analytics-funnel" queryFn={analyticsApi.funnel} /> : null}
        {active === "forecast" ? <DataSection title="Forecast Analytics" queryKey="analytics-forecast" queryFn={analyticsApi.forecast} /> : null}
        {active === "profitability" ? <GenericSection title="Profitability Analytics" description="Financial margin data requires analytics profitability permission." queryKey="analytics-profitability" queryFn={analyticsApi.profitability} /> : null}
        {active === "collections" ? <GenericSection title="Collection Analytics" description="Outstanding invoices, receipt movement, and collection risk." queryKey="analytics-collections" queryFn={analyticsApi.collections} /> : null}
        {active === "campaigns" ? <GenericSection title="Campaign Analytics" description="Campaign send, failure, blocked, and attribution metrics." queryKey="analytics-campaigns" queryFn={analyticsApi.campaigns} /> : null}
        {active === "anomalies" ? <DataSection title="Anomaly Detection Placeholder" queryKey="analytics-anomalies" queryFn={analyticsApi.anomalies} /> : null}
      </div>
    </div>
  );
}

function useRefresh(key: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: [key] });
}

function actionError(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Action failed. Please try again.";
}

function Home() {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {["Report Builder", "Dashboard Builder", "Export Engine", "Forecast", "Profitability", "Collections"].map((item) => <Card key={item}><CardContent className="p-4"><p className="font-medium">{item}</p><p className="mt-1 text-sm text-muted-foreground">Cross-module analytics capability backed by `/api/v1/analytics`.</p></CardContent></Card>)}
    </div>
  );
}

function ReportBuilder() {
  const { toast } = useToast();
  const [draft, setDraft] = useState({
    name: "Lead to Cash",
    module_name: "lead_to_cash",
    report_type: "table",
    visibility: "public",
    fields: "customer,deal,invoice,status,total",
    filters: "{\"status\":\"open\"}",
  });
  const create = useMutation({
    mutationFn: () => analyticsApi.createReport({
      name: draft.name,
      module_name: draft.module_name,
      report_type: draft.report_type,
      visibility: draft.visibility,
      fields_json: draft.fields.split(",").map((field) => field.trim()).filter(Boolean),
      filters_json: draft.filters.trim() ? JSON.parse(draft.filters) : {},
    }),
    onSuccess: () => toast({ title: "Report saved" }),
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return (
    <SectionShell title="Report Builder" description="Select data source, fields, filters, grouping, sorting, preview, save, run, and export.">
      <div className="grid gap-3 rounded-md border bg-card p-4 md:grid-cols-2">
        <Input aria-label="Report name" value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
        <Input aria-label="Data source" value={draft.module_name} onChange={(event) => setDraft((current) => ({ ...current, module_name: event.target.value }))} />
        <Input aria-label="Report type" value={draft.report_type} onChange={(event) => setDraft((current) => ({ ...current, report_type: event.target.value }))} />
        <Input aria-label="Visibility" value={draft.visibility} onChange={(event) => setDraft((current) => ({ ...current, visibility: event.target.value }))} />
        <Input aria-label="Fields" className="md:col-span-2" value={draft.fields} onChange={(event) => setDraft((current) => ({ ...current, fields: event.target.value }))} />
        <textarea aria-label="Filters JSON" className="min-h-24 rounded-md border bg-background px-3 py-2 font-mono text-sm md:col-span-2" value={draft.filters} onChange={(event) => setDraft((current) => ({ ...current, filters: event.target.value }))} />
        <Button className="w-fit" disabled={create.isPending || !draft.name.trim()} onClick={() => create.mutate()}>Save Report</Button>
      </div>
    </SectionShell>
  );
}

function Reports({ selectedId }: { selectedId?: string }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["analytics-reports"], queryFn: analyticsApi.reports });
  const refresh = useRefresh("analytics-reports");
  const create = useMutation({ mutationFn: () => analyticsApi.createReport({ name: "Deal to Invoice", module_name: "lead_to_cash", report_type: "table", visibility: "public" }), onSuccess: () => { toast({ title: "Report saved" }); refresh(); } });
  const reportId = Number(selectedId || query.data?.items?.[0]?.id || 0);
  const run = useMutation({ mutationFn: () => analyticsApi.runReport(reportId), onSuccess: (data: AnalyticsRecord) => toast({ title: `Run ${String(data.total)} rows` }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const exportCsv = useMutation({
    mutationFn: () => analyticsApi.exportReport(reportId, { export_type: "csv" }),
    onSuccess: (data: AnalyticsRecord) => {
      toast({ title: `Export ${String(data.status)}` });
      if (data.id) window.open(`/api/v1/analytics/exports/${data.id}/download`, "_blank", "noopener,noreferrer");
    },
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return <SectionFrame title="Saved Reports" description="Saved report definitions can be run and exported as real files." action="Create Report" onAction={() => create.mutate()} query={query}><Button variant="outline" disabled={!reportId} onClick={() => run.mutate()}>Run</Button><Button variant="outline" disabled={!reportId} onClick={() => exportCsv.mutate()}>Export CSV</Button></SectionFrame>;
}

function Dashboards({ selectedId }: { selectedId?: string }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["analytics-dashboards"], queryFn: analyticsApi.dashboards });
  const refresh = useRefresh("analytics-dashboards");
  const create = useMutation({ mutationFn: () => analyticsApi.createDashboard({ name: "Executive Dashboard", visibility: "public" }), onSuccess: () => { toast({ title: "Dashboard saved" }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const id = Number(selectedId || query.data?.items?.[0]?.id || 1);
  const widget = useMutation({ mutationFn: () => analyticsApi.addWidget(id, { widget_type: "kpi", title: "Pipeline Value", config_json: { source: "crm_deals" } }), onSuccess: () => toast({ title: "Widget saved" }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  return <SectionFrame title="Dashboard Builder" description="Add KPI, chart, table, and funnel widgets with role-aware visibility." action="Create Dashboard" onAction={() => create.mutate()} query={query}><Button variant="outline" onClick={() => widget.mutate()}>Add KPI Widget</Button></SectionFrame>;
}

function Schedules() {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["analytics-schedules"], queryFn: analyticsApi.schedules });
  const refresh = useRefresh("analytics-schedules");
  const create = useMutation({ mutationFn: async () => { const report = await analyticsApi.createReport({ name: "Weekly Forecast", module_name: "crm_deals", report_type: "summary" }); return analyticsApi.createSchedule({ report_id: report.id, name: "Weekly Forecast", frequency: "weekly", recipients_json: ["owner@example.com"], active: true }); }, onSuccess: () => { toast({ title: "Schedule saved" }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const firstId = Number(query.data?.items?.[0]?.id || 0);
  const run = useMutation({ mutationFn: () => analyticsApi.runSchedule(firstId), onSuccess: (data: AnalyticsRecord) => toast({ title: `Schedule run ${data.status}` }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  return <SectionFrame title="Scheduled Reports" description="Schedules are sync-run ready now and async-ready for larger reports." action="Create Schedule" onAction={() => create.mutate()} query={query}><Button variant="outline" disabled={!firstId} onClick={() => run.mutate()}>Run Now</Button></SectionFrame>;
}

function ExportAudit() {
  return <GenericSection title="Export Audit Logs" description="Every export completion, failure, and download is auditable." queryKey="analytics-export-audit" queryFn={analyticsApi.exportAudit} actions={(item) => item.id ? <Button size="sm" variant="outline" onClick={() => window.open(`/api/v1/analytics/exports/${item.id}/download`, "_blank", "noopener,noreferrer")}>Download</Button> : null} />;
}

function DataSection({ title, queryKey, queryFn }: { title: string; queryKey: string; queryFn: () => Promise<unknown> }) {
  const query = useQuery({ queryKey: [queryKey], queryFn });
  return <SectionShell title={title} description="Live analytics endpoint backed by CRM, Communication, SRM, or cross-module records."><pre className="max-h-96 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">{JSON.stringify(query.data || {}, null, 2)}</pre></SectionShell>;
}

function GenericSection({ title, description, queryKey, queryFn, actions }: { title: string; description: string; queryKey: string; queryFn: () => Promise<AnalyticsList>; actions?: (item: AnalyticsRecord) => React.ReactNode }) {
  const query = useQuery({ queryKey: [queryKey], queryFn });
  return <SectionFrame title={title} description={description} query={query} actions={actions} />;
}

function SectionShell({ title, description, children }: { title: string; description: string; children?: React.ReactNode }) {
  return <div className="space-y-4"><div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>{children}</div>;
}

function SectionFrame({ title, description, action, onAction, query, children, actions }: { title: string; description: string; action?: string; onAction?: () => void; query: ReturnType<typeof useQuery<AnalyticsList>>; children?: React.ReactNode; actions?: (item: AnalyticsRecord) => React.ReactNode }) {
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
        <div className="flex flex-wrap gap-2">{children}{action ? <Button onClick={onAction}>{action}</Button> : null}</div>
      </div>
      {query.isLoading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading analytics data...</div> : null}
      {query.isError ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">Analytics data could not be loaded.</div> : null}
      {!query.isLoading && !items.length ? <div className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">No analytics records yet.</div> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => <Card key={String(item.id)}><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">{String(item.name || item.title || item.report_id || item.invoice_number || `Record ${item.id}`)}</p><p className="mt-1 text-xs text-muted-foreground">{String(item.module_name || item.report_type || item.export_type || item.status || "analytics")}</p></div><Badge variant="outline">{String(item.status || item.visibility || "ready")}</Badge></div>{actions ? <div className="flex flex-wrap gap-2">{actions(item)}</div> : null}</CardContent></Card>)}
      </div>
    </div>
  );
}
