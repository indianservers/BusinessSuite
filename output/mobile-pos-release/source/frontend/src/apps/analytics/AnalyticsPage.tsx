import { SmartCreateAction } from "@/shared/creation/SmartCreateAction";
import {useModuleAction} from "@/hooks/use-module-action";
import {api} from "@/services/api";
import { useCreateIntent } from "@/hooks/use-create-intent";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
import {NativeSelect} from "@/components/ui/native-select";
import RecordDefinitionActions, {useDefinitionPermission} from "@/components/RecordDefinitionActions";
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
import AnalyticsOverview from "./AnalyticsOverview";
import "./analytics.css";

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
  if (pathname.includes("scheduled-reports")) return "schedules";
  if (pathname.includes("reports")) return "reports";
  if (pathname.includes("dashboards")) return "dashboards";
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
    <div className="analytics-workspace">
      <div className="analytics-page-header">
        <div className="analytics-header-inner">
        <div className="analytics-eyebrow"><span className="analytics-workspace-mark">B</span> Business Suite <span>/</span> Insights</div>
        <div className="analytics-title-row"><div><h1>Analytics</h1>
        <p>Your workspace, by the numbers.</p></div>
        <Button variant="outline" size="sm" onClick={() => navigate("/ai/report-explainer?module_name=analytics")}><Sparkles className="h-4 w-4" />Ask AI</Button></div>
        <nav className="analytics-navigation" aria-label="Analytics sections">
          {sections.map((item) => {
            const Icon = item.icon;
            return <button key={item.key} type="button" aria-current={active === item.key ? "page" : undefined} onClick={() => navigate(item.path)}><Icon className="h-3.5 w-3.5" />{item.key === "home" ? "Overview" : item.label}</button>;
          })}
        </nav>
        </div>
      </div>
      <div className="analytics-page-content">
        {active === "home" ? <AnalyticsOverview /> : null}
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

function ReportBuilder() {
  const { toast } = useToast();
  const [editing,setEditing]=useState<AnalyticsRecord|null>(null);
  const canCreate=useDefinitionPermission(["analytics_report_builder","analytics_manage"],"create"),canEdit=useDefinitionPermission(["analytics_report_builder","analytics_manage"],"edit");
  const saved=useQuery({queryKey:["analytics-reports"],queryFn:analyticsApi.reports}),refresh=useRefresh("analytics-reports");
  const [draft, setDraft] = useState({
    name: "Lead to Cash",
    module_name: "lead_to_cash",
    report_type: "table",
    visibility: "public",
    fields: "customer,deal,invoice,status,total",
    filters: "{\"status\":\"open\"}",
  });
  const create = useMutation({
    mutationFn: () => {const body={...editing,
      name: draft.name,
      module_name: draft.module_name,
      report_type: draft.report_type,
      visibility: draft.visibility,
      fields_json: draft.fields.split(",").map((field) => field.trim()).filter(Boolean),
      filters_json: draft.filters.trim() ? JSON.parse(draft.filters) : {},
    };return editing?api.put(`/analytics/reports/${editing.id}`,body):analyticsApi.createReport(body);},
    onSuccess: (result) => {if(editing)setEditing((result as {data:AnalyticsRecord}).data);refresh();toast({ title: "Report saved" });},
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return (
    <SectionShell title="Report Builder" description="Select data source, fields, filters, grouping, sorting, preview, save, run, and export.">
      <label>Saved report<NativeSelect aria-label="Saved report" value={String(editing?.id||"")} onChange={event=>{const row=saved.data?.items.find(item=>String(item.id)===event.target.value);setEditing(row||null);if(row)setDraft({name:String(row.name),module_name:String(row.module_name),report_type:String(row.report_type),visibility:String(row.visibility),fields:(row.fields_json as string[]||[]).join(","),filters:JSON.stringify(row.filters_json||{})});}}><option value="">New report</option>{saved.data?.items.map(row=><option key={row.id} value={row.id}>{String(row.name)}</option>)}</NativeSelect></label>{editing&&<RecordDefinitionActions record={editing} endpoint={`/analytics/reports/${editing.id}`} queryKeys={["analytics-reports"]} permissions={["analytics_report_builder","analytics_manage"]} canRename={false} onDeleted={()=>setEditing(null)}/>}
      <div className="grid gap-3 rounded-md border bg-card p-4 md:grid-cols-2">
        <Input aria-label="Report name" value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
        <Input aria-label="Data source" value={draft.module_name} onChange={(event) => setDraft((current) => ({ ...current, module_name: event.target.value }))} />
        <Input aria-label="Report type" value={draft.report_type} onChange={(event) => setDraft((current) => ({ ...current, report_type: event.target.value }))} />
        <Input aria-label="Visibility" value={draft.visibility} onChange={(event) => setDraft((current) => ({ ...current, visibility: event.target.value }))} />
        <Input aria-label="Fields" className="md:col-span-2" value={draft.fields} onChange={(event) => setDraft((current) => ({ ...current, fields: event.target.value }))} />
        <textarea aria-label="Filters JSON" className="min-h-24 rounded-md border bg-background px-3 py-2 font-mono text-sm md:col-span-2" value={draft.filters} onChange={(event) => setDraft((current) => ({ ...current, filters: event.target.value }))} />
        <Button className="w-fit" disabled={create.isPending || !draft.name.trim() || !(editing?canEdit:canCreate)} onClick={() => create.mutate()}>Save Report</Button>
      </div>
    </SectionShell>
  );
}

function Reports({ selectedId }: { selectedId?: string }) {
  const canRun=useDefinitionPermission(["analytics_view","analytics_report_builder","analytics_manage"],"approve"),canExport=useDefinitionPermission(["analytics_export"],"export");
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["analytics-reports"], queryFn: analyticsApi.reports });
  const refresh = useRefresh("analytics-reports");
  const create = useMutation({ mutationFn: () => analyticsApi.createReport({ name: "Deal to Invoice", module_name: "lead_to_cash", report_type: "table", visibility: "public" }), onSuccess: () => { toast({ title: "Report saved" }); refresh(); } });
  const [chosen,setChosen]=useState(0);
  const reportId = Number(selectedId || chosen || query.data?.items?.[0]?.id || 0);
  const run = useMutation({ mutationFn: () => analyticsApi.runReport(reportId), onSuccess: (data: AnalyticsRecord) => toast({ title: `Run ${String(data.total)} rows` }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const exportCsv = useMutation({
    mutationFn: () => analyticsApi.exportReport(reportId, { export_type: "csv" }),
    onSuccess: async (data: AnalyticsRecord) => {
      toast({ title: `Export ${String(data.status)}` });
      if (data.id) await analyticsApi.downloadExport(Number(data.id));
    },
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return <SectionFrame title="Saved Reports" description="Saved report definitions can be run and exported as real files." action="Create Report" onAction={() => create.mutate()} query={query} actions={item=><RecordDefinitionActions record={item} endpoint={`/analytics/reports/${item.id}`} queryKeys={["analytics-reports"]} permissions={["analytics_manage","analytics_admin"]}/>}><label>Report to run<NativeSelect aria-label="Report to run" value={reportId||""} onChange={event=>setChosen(Number(event.target.value))}><option value="">Choose report</option>{query.data?.items.map(item=><option key={item.id} value={item.id}>{String(item.name)}</option>)}</NativeSelect></label><Button variant="outline" disabled={!canRun||!reportId||run.isPending} onClick={() => run.mutate()}>Run</Button><Button variant="outline" disabled={!canExport||!reportId||exportCsv.isPending} onClick={() => exportCsv.mutate()}>Export CSV</Button></SectionFrame>;
}

function Dashboards({ selectedId }: { selectedId?: string }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["analytics-dashboards"], queryFn: analyticsApi.dashboards });
  const refresh = useRefresh("analytics-dashboards");
  const create = useMutation({ mutationFn: () => analyticsApi.createDashboard({ name: "Executive Dashboard", visibility: "public" }), onSuccess: () => { toast({ title: "Dashboard saved" }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const [chosen,setChosen]=useState(0);
  const canManage=useDefinitionPermission(["analytics_manage"],"create");
  const id = Number(selectedId || chosen || query.data?.items?.[0]?.id || 0);
  const widget = useMutation({ mutationFn: () => analyticsApi.addWidget(id, { widget_type: "kpi", title: "Pipeline Value", config_json: { source: "crm_deals" } }), onSuccess: () => toast({ title: "Widget saved" }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  return <SectionFrame title="Dashboard Builder" description="Add KPI, chart, table, and funnel widgets with role-aware visibility." action="Create Dashboard" onAction={() => create.mutate()} query={query} actions={item=><RecordDefinitionActions record={item} endpoint={`/analytics/dashboards/${item.id}`} queryKeys={["analytics-dashboards"]} permissions={["analytics_manage","analytics_admin"]}/>}><label>Dashboard to edit<NativeSelect aria-label="Dashboard to edit" value={id||""} onChange={event=>setChosen(Number(event.target.value))}><option value="">Choose dashboard</option>{query.data?.items.map(item=><option key={item.id} value={item.id}>{String(item.name)}</option>)}</NativeSelect></label><SmartCreateAction title="Add KPI Widget"><Button variant="outline" disabled={!canManage||!id||widget.isPending} onClick={() => widget.mutate()}>Add KPI Widget</Button></SmartCreateAction></SectionFrame>;
}

function Schedules() {
  const {toast}=useToast(),refresh=useRefresh("analytics-schedules");
  const query=useQuery({queryKey:["analytics-schedules"],queryFn:analyticsApi.schedules}),reports=useQuery({queryKey:["analytics-reports"],queryFn:analyticsApi.reports});
  const [editing,setEditing]=useState<AnalyticsRecord|null>(null);
  const canEdit=useDefinitionPermission(["analytics_schedule"],"edit");
  const [open,setOpen]=useState(false),[error,setError]=useState(""),[selected,setSelected]=useState(0),[draft,setDraft]=useState({name:"",report_id:"",frequency:"weekly",recipients:""});
  const allowed=useDefinitionPermission(["analytics_schedule"],"create"),canRun=useDefinitionPermission(["analytics_schedule"],"approve");
  useCreateIntent(kind => { if (kind === "schedule" && allowed) { setError(""); setOpen(true); } });
  const create=useMutation({mutationFn:()=>{const body={name:draft.name.trim(),report_id:Number(draft.report_id),frequency:draft.frequency,recipients_json:draft.recipients.split(",").map(value=>value.trim()).filter(Boolean),active:true};return editing?api.put(`/analytics/schedules/${editing.id}`,body):analyticsApi.createSchedule(body);},onSuccess:()=>{setOpen(false);refresh();toast({title:"Schedule saved"});},onError:error=>setError(actionError(error))});
  const id=selected||Number(query.data?.items[0]?.id||0);const run=useMutation({mutationFn:()=>analyticsApi.runSchedule(id),onSuccess:(data:AnalyticsRecord)=>toast({title:`Schedule run ${data.status}`}),onError:error=>toast({title:actionError(error),variant:"destructive"})});
  return <><SectionFrame title="Scheduled Reports" description="Choose the report, recipients and frequency before creating a schedule." action="Create Schedule" onAction={()=>{setEditing(null);setDraft({name:"",report_id:"",frequency:"weekly",recipients:""});setError("");setOpen(true);}} query={query} actions={item=><><Button variant="outline" disabled={!canEdit} aria-label={`Edit ${item.name}`} onClick={()=>{setEditing(item);setDraft({name:String(item.name),report_id:String(item.report_id),frequency:String(item.frequency),recipients:(item.recipients_json as string[]||[]).join(",")});setOpen(true);}}>Edit schedule</Button><RecordDefinitionActions record={item} endpoint={`/analytics/schedules/${item.id}`} queryKeys={["analytics-schedules"]} permissions={["analytics_schedule"]} canRename={false}/></>}><label>Schedule to run<NativeSelect aria-label="Schedule to run" value={id||""} onChange={event=>setSelected(Number(event.target.value))}><option value="">Choose schedule</option>{query.data?.items.map(item=><option key={item.id} value={item.id}>{String(item.name)}</option>)}</NativeSelect></label><Button variant="outline" disabled={!canRun||!id||run.isPending} onClick={()=>run.mutate()}>Run Now</Button></SectionFrame>
  <Dialog open={open} onOpenChange={value=>{if(!create.isPending)setOpen(value);}}><DialogContent><DialogTitle>{editing?"Edit":"Create"} report schedule</DialogTitle><form className="space-y-3" onSubmit={event=>{event.preventDefault();create.mutate();}}><label>Schedule name<Input aria-label="Schedule name" required value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label>Report<NativeSelect aria-label="Schedule report" required value={draft.report_id} onChange={event=>setDraft({...draft,report_id:event.target.value})}><option value="">Choose saved report</option>{reports.data?.items.map(item=><option key={item.id} value={item.id}>{String(item.name)}</option>)}</NativeSelect></label><label>Frequency<NativeSelect aria-label="Schedule frequency" value={draft.frequency} onChange={event=>setDraft({...draft,frequency:event.target.value})}>{["daily","weekly","monthly"].map(value=><option key={value}>{value}</option>)}</NativeSelect></label><label>Recipients<Input aria-label="Schedule recipients" required type="email" multiple value={draft.recipients} onChange={event=>setDraft({...draft,recipients:event.target.value})}/></label>{error&&<p role="alert">{error}</p>}<Button type="submit" disabled={!(editing?canEdit:allowed)||create.isPending}>Save schedule</Button></form></DialogContent></Dialog></>;
}

function ExportAudit() {
  const canExport=useModuleAction("export");
  const {toast}=useToast();const download=useMutation({mutationFn:analyticsApi.downloadExport,onError:error=>toast({title:actionError(error),variant:"destructive"})});
  return <GenericSection title="Export Audit Logs" description="Every export completion, failure, and download is auditable." queryKey="analytics-export-audit" queryFn={analyticsApi.exportAudit} actions={item=>item.id?<Button size="sm" variant="outline" disabled={!canExport||download.isPending} onClick={()=>download.mutate(Number(item.id))}>Download</Button>:null}/>;
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
  const canCreate=useDefinitionPermission(["analytics_manage","analytics_schedule","analytics_report_builder"],"create");
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
        <div className="flex flex-wrap gap-2">{children}{action ? action === "Create Schedule" ? <Button disabled={!canCreate} onClick={onAction}>{action}</Button> : <SmartCreateAction title={action} description={description}><Button disabled={!canCreate} onClick={onAction}>{action}</Button></SmartCreateAction> : null}</div>
      </div>
      {query.isLoading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading analytics data...</div> : null}
      {query.isError ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">Analytics data could not be loaded.</div> : null}
      {!query.isLoading && !items.length ? <div className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">No analytics records yet.</div> : null}
      <GroupedRecords scope="apps/analytics/AnalyticsPage:cards-1" items={(items) || []} fields={standardRecordGroups((items) || [])} gridClassName="grid gap-3 md:grid-cols-2" renderItem={(item) => <Card key={String(item.id)}><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">{String(item.name || item.title || item.report_id || item.invoice_number || `Record ${item.id}`)}</p><p className="mt-1 text-xs text-muted-foreground">{String(item.module_name || item.report_type || item.export_type || item.status || "analytics")}</p></div><Badge variant="outline">{String(item.status || item.visibility || "ready")}</Badge></div>{actions ? <div className="flex flex-wrap gap-2">{actions(item)}</div> : null}</CardContent></Card>}/>
    </div>
  );
}
