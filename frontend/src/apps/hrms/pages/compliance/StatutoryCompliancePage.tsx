import "./statutory-form16-mobile.css";
import "./statutory-history-mobile.css";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./statutory-generate-mobile.css";
import { useMobile } from "@/components/mobile/useMobile";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import "./statutory-calendar-mobile.css";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useState, type InputHTMLAttributes } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileCheck2, Loader2, TriangleAlert, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { employeeApi, form16Api, payrollApi, statutoryApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { payrollError } from "../payroll/PayrollDeliverySettings";

const TABS = ["Compliance Calendar", "Generate Files", "Form 16", "Submission History"] as const;
const TYPES = ["PF", "ESI", "PT", "LWF", "TDS"];
const FILE_TYPES = [
  ["pf_ecr", "Generate PF ECR"],
  ["esi", "Generate ESI Return"],
  ["pt", "Generate PT Challan"],
  ["lwf", "Generate LWF Return"],
  ["tds_24q", "Generate TDS 24Q"],
  ["tds_26q", "Generate TDS 26Q"],
] as const;

type CalendarItem = {
  id: number;
  statutory_type: string;
  due_date: string;
  period_start?: string;
  period_end?: string;
  description?: string;
  status: string;
  effective_status?: string;
  reminder_due_on?: string;
  reminder_status?: string;
  reminder_days_before?: number;
};

type Submission = {
  id: number;
  statutory_type: string;
  payroll_run_id: number;
  payroll_period?: string;
  validation_status: string;
  validation_errors_json?: Array<{ row: number; field: string; code?: string; message?: string; error: string; severity?: string }>;
  filing_status?: string;
  digital_signature_status?: string;
  portal_connector_status?: string;
  row_count?: number;
  total_amount?: number;
  submitted_at?: string;
  portal_reference?: string;
};

type PayrollRun = {
  id: number;
  month: number;
  year: number;
  status: string;
  total_employees?: number;
  employee_count?: number;
};

type CompliancePreview = {
  export_type: string;
  rule?: string;
  total_employees: number;
  total_amount: number;
  validation_errors: string[];
  rows: Array<Record<string, unknown> & { validation_errors?: string[] }>;
};

type ComplianceExport = {
  id: number;
  export_type: string;
  file_path: string;
};

type Form16Record = {
  id: number;
  employeeId: number;
  employee?: { id: number; employeeId?: string; name?: string; pan?: string };
  financialYear: string;
  partAFilePath?: string;
  partBFilePath?: string;
  combinedFilePath?: string;
  status: string;
  taxableIncome?: number | string;
  taxDeducted?: number | string;
  digitalSignatureStatus?: string;
  reviewedAt?: string;
  signedFilePath?: string;
  generatedAt?: string;
  publishedAt?: string;
};

type EmployeeOption = {
  id: number;
  employee_id?: string;
  employeeId?: string;
  first_name?: string;
  firstName?: string;
  last_name?: string;
  lastName?: string;
};

const money = (value: unknown) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0));

export default function StatutoryCompliancePage() {
  usePageTitle("Statutory Compliance");
  const phone = useMobile(480);
  const [tab, setTab] = useState<(typeof TABS)[number]>(new URLSearchParams(window.location.search).get("tab") === "form16" ? "Form 16" : "Compliance Calendar");

  return (
    <div className="hrms-statutory-page space-y-6">
      <div>
        <h1 className="page-title">Statutory Compliance</h1>
        <p className="page-description">Track due dates, generate statutory files, and monitor portal submission status.</p>
      </div>
      <div className="hrms-statutory-tabs flex flex-wrap gap-2 border-b">
        {TABS.map((item) => (
          <button
            key={item}
            aria-pressed={phone ? tab === item : undefined}
            type="button"
            onClick={() => setTab(item)}
            className={cn("border-b-2 px-3 py-2 text-sm font-medium", tab === item ? "border-primary text-primary" : "border-transparent text-muted-foreground")}
          >
            {item}
          </button>
        ))}
      </div>
      {tab === "Compliance Calendar" && <CalendarTab />}
      {tab === "Generate Files" && <GenerateTab />}
      {tab === "Form 16" && <Form16Tab />}
      {tab === "Submission History" && <HistoryTab />}
    </div>
  );
}

function CalendarTab() {
  const phone = useMobile(480);
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ statutory_type: "", status: "", year: String(new Date().getFullYear()) });
  const [marking, setMarking] = useState<CalendarItem | null>(null);
  const [remarks, setRemarks] = useState("");
  const params = { ...filters, statutory_type: filters.statutory_type || undefined, status: filters.status || undefined, year: filters.year || undefined };
  const summary = useQuery({ queryKey: ["statutory-summary"], queryFn: () => statutoryApi.complianceSummary().then((r) => r.data) });
  const calendar = useQuery({ queryKey: ["statutory-calendar", params], queryFn: () => statutoryApi.calendar(params).then((r) => r.data as CalendarItem[]) });
  const markFiled = useMutation({
    mutationFn: () => statutoryApi.markFiled(marking!.id, { review_remarks: remarks || undefined }),
    onSuccess: () => {
      toast({ title: "Marked as filed" });
      setMarking(null);
      setRemarks("");
      qc.invalidateQueries({ queryKey: ["statutory-calendar"] });
      qc.invalidateQueries({ queryKey: ["statutory-summary"] });
    },
    onError: () => toast({ title: "Unable to mark filed", variant: "destructive" }),
  });
  const counts = summary.data?.counts || {};

  const filedContent = marking ? (
          <div className="hrms-statutory-filed-form space-y-4">
            <p className="text-sm text-muted-foreground">Confirm filing for {marking.statutory_type} due on {marking.due_date}.</p>
            <Input aria-label="Filing remarks" disabled={phone && markFiled.isPending} value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Optional remarks" />
            {phone && markFiled.isError && <p role="alert" className="text-sm text-destructive">Filing could not update. Your remarks are retained.</p>}
            <div className="hrms-statutory-filed-actions flex justify-end gap-2"><Button variant="outline" onClick={() => setMarking(null)}>Cancel</Button><Button data-save-action={phone ? "" : undefined} onClick={() => markFiled.mutate()} disabled={markFiled.isPending}>Confirm</Button></div>
          </div>
  ) : null;

  return (
    <div className="hrms-statutory-calendar space-y-5">
      <div className="hrms-statutory-kpis grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Summary label="Pending" value={phone && !summary.data ? "—" : counts.Pending || 0} className="bg-yellow-50 text-yellow-700" />
        <Summary label="Filed" value={phone && !summary.data ? "—" : counts.Filed || 0} className="bg-green-50 text-green-700" />
        <Summary label="Overdue" value={phone && !summary.data ? "—" : counts.Overdue || 0} className="bg-red-50 text-red-700" />
        <Summary label="Upcoming this month" value={phone && !summary.data ? "—" : summary.data?.upcoming_count || 0} className="bg-blue-50 text-blue-700" />
      </div>

      {phone && (summary.isError || calendar.isError) && <p role="alert" className="text-sm text-destructive">Compliance calendar could not load. <Button variant="outline" onClick={() => { if (summary.isError) void summary.refetch(); if (calendar.isError) void calendar.refetch(); }}>Retry compliance calendar</Button></p>}
      <Card>
        <CardHeader><CardTitle className="text-base">Compliance Calendar</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="hrms-statutory-calendar-filters grid gap-3 sm:grid-cols-3">
            <NativeSelect className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Compliance type" value={filters.statutory_type} onChange={(e) => setFilters({ ...filters, statutory_type: e.target.value })}>
              <option value="">All types</option>{TYPES.map((type) => <option key={type}>{type}</option>)}
            </NativeSelect>
            <NativeSelect className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Compliance status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All statuses</option>{["Pending", "Filed", "Overdue"].map((status) => <option key={status}>{status}</option>)}
            </NativeSelect>
            <Input aria-label="Compliance year" value={filters.year} onChange={(e) => setFilters({ ...filters, year: e.target.value })} placeholder="Year" />
          </div>
          {calendar.isLoading ? <div className="h-40 animate-pulse rounded bg-muted" /> : phone && calendar.isError && !calendar.data ? <p className="text-sm text-muted-foreground">Calendar entries are unavailable until the request succeeds.</p> : (
            <div className="overflow-x-auto rounded-lg border">
              <GridTable gridId="apps/hrms/pages/compliance/StatutoryCompliancePage:table-1" className="w-full min-w-[820px] text-sm">
                <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Description</th><th className="px-3 py-2 text-left">Period</th><th className="px-3 py-2 text-left">Due Date</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
                <tbody>
                  {(calendar.data || []).map((item) => {
                    const overdue = item.status !== "Filed" && new Date(item.due_date) < new Date();
                    return (
                      <tr {...recordPreviewProps(item)} key={item.id} className="border-t">
                        <td className="px-3 py-2"><TypeBadge type={item.statutory_type} /></td>
                        <td className="px-3 py-2">{item.description || "Statutory filing"}</td>
                        <td className="px-3 py-2">{item.period_start || "-"} to {item.period_end || "-"}</td>
                        <td className="px-3 py-2">{item.due_date}</td>
                        <td className="px-3 py-2">
                          <StatusBadge status={item.effective_status || (overdue ? "Overdue" : item.status)} />
                          {item.reminder_due_on && <p className="mt-1 text-xs text-muted-foreground">Reminder {item.reminder_status || "scheduled"}: {item.reminder_due_on}</p>}
                        </td>
                        <td className="px-3 py-2 text-right">{item.status !== "Filed" && <Button size="sm" variant="outline" onClick={() => { if (phone) { setRemarks(""); markFiled.reset(); } setMarking(item); }}>Mark Filed</Button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </GridTable>
            </div>
          )}
        </CardContent>
      </Card>
      {marking && (phone ? <SmartCreateModal definition={{ entity: "statutory-filing", title: "Mark Filed", presentation: "page", size: "compact" }} mobileSheet busy={markFiled.isPending} onClose={() => setMarking(null)}>{filedContent}</SmartCreateModal> : <Modal title="Mark Filed" onClose={() => setMarking(null)}>{filedContent}</Modal>)}
    </div>
  );
}

function GenerateTab() {
  const phone = useMobile(480);
  const qc = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [lastResult, setLastResult] = useState<any>(null);
  const [complianceExport, setComplianceExport] = useState<ComplianceExport | null>(null);
  const [ackSubmission, setAckSubmission] = useState<number | null>(null);
  const [ack, setAck] = useState("");
  const runs = useQuery({ queryKey: ["payroll-runs-statutory"], queryFn: () => payrollApi.runs({ status: "locked,paid" }).then((r) => r.data as PayrollRun[]) });
  const submissions = useQuery({ queryKey: ["statutory-submissions", selectedRunId], queryFn: () => statutoryApi.submissions({ payroll_run_id: selectedRunId }).then((r) => r.data as Submission[]), enabled: !!selectedRunId });
  const pfPreview = useQuery({
    queryKey: ["hrms-pf-ecr-preview", selectedRunId],
    queryFn: () => statutoryApi.pfEcrPreview(selectedRunId!).then((r) => r.data as CompliancePreview),
    enabled: !!selectedRunId,
  });
  const esiPreview = useQuery({
    queryKey: ["hrms-esi-preview", selectedRunId],
    queryFn: () => statutoryApi.esiPreview(selectedRunId!).then((r) => r.data as CompliancePreview),
    enabled: !!selectedRunId,
  });
  const generate = useMutation({
    mutationFn: (type: string) => statutoryApi.generate(selectedRunId!, type),
    onSuccess: (response) => {
      setLastResult(response.data);
      toast({ title: "File generated" });
      qc.invalidateQueries({ queryKey: ["statutory-submissions"] });
    },
    onError: () => toast({ title: "Unable to generate file", variant: "destructive" }),
  });
  const complianceGenerate = useMutation({
    mutationFn: (type: "pf" | "esi") =>
      type === "pf" ? statutoryApi.generatePfEcr(selectedRunId!) : statutoryApi.generateEsi(selectedRunId!),
    onSuccess: (response) => {
      setComplianceExport(response.data as ComplianceExport);
      toast({ title: "Compliance export generated", description: response.data.file_path });
      qc.invalidateQueries({ queryKey: ["hrms-pf-ecr-preview"] });
      qc.invalidateQueries({ queryKey: ["hrms-esi-preview"] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string | { validation_errors?: string[]; message?: string } } } })?.response?.data?.detail;
      const description = typeof detail === "string" ? detail : detail?.validation_errors?.slice(0, 3).join("; ") || detail?.message || "Unable to generate compliance export";
      toast({ title: "Validation failed", description, variant: "destructive" });
    },
  });
  const markSubmitted = useMutation({
    mutationFn: () => statutoryApi.markSubmitted(ackSubmission!, { portal_reference: ack }),
    onSuccess: () => {
      toast({ title: "Marked as submitted" });
      setAckSubmission(null);
      setAck("");
      qc.invalidateQueries({ queryKey: ["statutory-submissions"] });
    },
  });
  const lockedRuns = (runs.data || []).filter((run) => ["locked", "paid"].includes(run.status));


  const downloadFile = useMutation({
    mutationFn: (target: { kind: "export"; item: ComplianceExport } | { kind: "submission"; id: number }) => target.kind === "export" ? downloadComplianceExport(target.item) : download(target.id),
  });
  const busy = generate.isPending || complianceGenerate.isPending || markSubmitted.isPending || downloadFile.isPending;
  function chooseRun(id: number | null) {
    if (phone) {
      if (busy || id === selectedRunId) return;
      setLastResult(null); setComplianceExport(null);
      generate.reset(); complianceGenerate.reset(); downloadFile.reset();
    }
    setSelectedRunId(id);
  }
  function openAck(id: number) {
    if (phone) { setAck(""); markSubmitted.reset(); }
    setAckSubmission(id);
  }
  const legacyButtons = FILE_TYPES.map(([type, label]) => (
    <Button key={type} className="w-full justify-start" variant="outline" onClick={() => generate.mutate(type)} disabled={generate.isPending || phone && busy}>
      {generate.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />} {label}
    </Button>
  ));
  const ackContent = <div className="hrms-statutory-ack-form space-y-4">
    {phone && <p className="text-sm text-muted-foreground">Submission #{ackSubmission}</p>}
    <Input aria-label="Portal acknowledgement" disabled={phone && markSubmitted.isPending} value={ack} onChange={e => setAck(e.target.value)} placeholder="Acknowledgement number" />
    {phone && markSubmitted.isError && <p role="alert" className="text-sm text-destructive">Acknowledgement could not save. Your number is retained.</p>}
    <div className="hrms-statutory-ack-actions flex justify-end gap-2"><Button variant="outline" onClick={() => setAckSubmission(null)}>Cancel</Button><Button data-save-action={phone ? "" : undefined} disabled={!ack || markSubmitted.isPending} onClick={() => markSubmitted.mutate()}>Save</Button></div>
  </div>;

  return (
    <div className="hrms-statutory-generate grid gap-5 xl:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Payroll Runs</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {runs.isLoading && <div className="h-40 animate-pulse rounded bg-muted" />}
          {phone ? <NativeSelect aria-label="Payroll run" loading={runs.isFetching} error={runs.isError} disabled={busy} value={selectedRunId || ""} onChange={e => chooseRun(Number(e.target.value) || null)}><option value="">Select a locked or paid run</option>{lockedRuns.map(run => <option key={run.id} value={run.id}>{run.month}/{run.year} · {run.status} · {run.total_employees || run.employee_count || 0} employees</option>)}</NativeSelect> : lockedRuns.map((run) => (
            <button key={run.id} type="button" onClick={() => setSelectedRunId(run.id)} className={cn("w-full rounded-lg border p-3 text-left", selectedRunId === run.id && "border-primary bg-primary/10")}>
              <p className="font-medium">{run.month}/{run.year}</p>
              <p className="text-sm text-muted-foreground">{run.status} - {run.total_employees || run.employee_count || 0} employees</p>
            </button>
          ))}
          {phone && runs.isSuccess && !lockedRuns.length && <p className="text-sm text-muted-foreground">No locked or paid payroll runs found.</p>}
        </CardContent>
      </Card>
      <div className="space-y-5">
        {phone && [runs, submissions, pfPreview, esiPreview].some(query => query.isError) && <p role="alert" className="text-sm text-destructive">Statutory file information could not load. <Button variant="outline" onClick={() => { for (const query of [runs, submissions, pfPreview, esiPreview]) if (query.isError) void query.refetch(); }}>Retry statutory files</Button></p>}
        {phone && generate.isError && <p role="alert" className="text-sm text-destructive">Statutory file could not generate. Try its action again.</p>}
        {phone && complianceGenerate.isError && <p role="alert" className="text-sm text-destructive">Compliance export could not generate. Review validation and try again.</p>}
        {phone && downloadFile.isError && <p role="alert" className="text-sm text-destructive">File could not download. Retry its download action.</p>}
        {selectedRunId && (
          <div className="grid gap-4 lg:grid-cols-2">
            <MobileDisclosure title={`PF ECR preview${pfPreview.data?.validation_errors?.length ? ` (${pfPreview.data.validation_errors.length} issues)` : ""}`} maxWidth={480}><CompliancePreviewCard
              title="PF ECR"
              description="EPFO ECR wage and contribution preview"
              preview={pfPreview.data}
              loading={pfPreview.isLoading}
              columns={["uan", "member_name", "gross_wages", "epf_wages", "employee_pf_contribution", "employer_pf_contribution", "eps_contribution"]}
              onGenerate={() => complianceGenerate.mutate("pf")}
              generating={complianceGenerate.isPending || phone && busy}
            /></MobileDisclosure>
            <MobileDisclosure title={`ESI preview${esiPreview.data?.validation_errors?.length ? ` (${esiPreview.data.validation_errors.length} issues)` : ""}`} maxWidth={480}><CompliancePreviewCard
              title="ESI Challan"
              description="ESI contribution report and challan preview"
              preview={esiPreview.data}
              loading={esiPreview.isLoading}
              columns={["esic_number", "employee_name", "gross_wages", "employee_esi", "employer_esi", "payable_days"]}
              onGenerate={() => complianceGenerate.mutate("esi")}
              generating={complianceGenerate.isPending || phone && busy}
            /></MobileDisclosure>
          </div>
        )}
        {complianceExport && (
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
              <div>
                <p className="font-medium">{complianceExport.export_type.toUpperCase()} generated</p>
                <p className="text-muted-foreground">{complianceExport.file_path}</p>
              </div>
              <Button size="sm" variant="outline" disabled={phone && downloadFile.isPending} onClick={() => phone ? downloadFile.mutate({ kind: "export", item: complianceExport }) : downloadComplianceExport(complianceExport)}>
                <Download className="mr-2 h-4 w-4" /> Download
              </Button>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader><CardTitle className="text-base">Generate Files</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {!selectedRunId && <p className="text-sm text-muted-foreground">Select a locked or paid payroll run to generate files.</p>}
            {selectedRunId && (phone ? <div className="hrms-statutory-legacy-buttons">{legacyButtons}</div> : legacyButtons)}
            {lastResult && (
              <div className="rounded-lg border p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <StatusBadge status={lastResult.filing_status || lastResult.validation_status} />
                  <Badge variant="outline">{lastResult.portal_connector_status || "not_configured"}</Badge>
                  <Badge variant="outline">{lastResult.digital_signature_status || "not_applicable"}</Badge>
                  <span className="text-sm">{lastResult.row_count} rows - {money(lastResult.total_amount)}</span>
                </div>
                {!!lastResult.errors?.length && <ErrorList errors={lastResult.errors} />}
                {!lastResult.errors?.length && <div className="flex gap-2"><Button size="sm" variant="outline" disabled={phone && downloadFile.isPending} onClick={() => phone ? downloadFile.mutate({ kind: "submission", id: lastResult.submission_id }) : download(lastResult.submission_id)}>Download CSV</Button><Button size="sm" onClick={() => phone ? openAck(lastResult.submission_id) : setAckSubmission(lastResult.submission_id)}>Mark as Submitted</Button></div>}
              </div>
            )}
          </CardContent>
        </Card>
        <HistoryTable rows={submissions.data || []} compact onMarkSubmitted={phone ? openAck : setAckSubmission} onDownload={phone ? id => downloadFile.mutate({ kind: "submission", id }) : undefined} downloadBusy={phone && downloadFile.isPending} />
      </div>
      {ackSubmission && (phone ? <SmartCreateModal definition={{ entity: "statutory-ack", title: "Portal ACK Number", presentation: "page", size: "compact" }} mobileSheet busy={markSubmitted.isPending} onClose={() => setAckSubmission(null)}>{ackContent}</SmartCreateModal> : <Modal title="Portal ACK Number" onClose={() => setAckSubmission(null)}>{ackContent}</Modal>)}
    </div>
  );
}

function Form16Upload(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}

function Form16Tab() {
  const qc = useQueryClient();
  const phone = useMobile(480);
  const FileControl = phone ? Form16Upload : "input";
  const downloadFile = useMutation({ mutationFn: (record: Form16Record) => downloadForm16(record) });
  const permissions = useQuery({ queryKey: ["payroll-delivery-settings"], queryFn: () => payrollApi.deliverySettings().then(r => r.data as { can_manage: boolean; can_approve: boolean; form16_trust_configured: boolean }) });
  const canApprove = Boolean(permissions.data?.can_approve);
  const now = new Date();
  const defaultFyStart = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const [financialYear, setFinancialYear] = useState(`${defaultFyStart}-${String(defaultFyStart + 1).slice(-2)}`);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<number[]>([]);
  const [employeePage, setEmployeePage] = useState(1);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const employees = useQuery({
    queryKey: ["form16-employees", employeePage, employeeSearch],
    queryFn: () => employeeApi.list({ page: employeePage, per_page: 100, search: employeeSearch || undefined }).then((r) => r.data),
  });
  const records = useQuery({
    queryKey: ["form16-records", financialYear],
    queryFn: () => form16Api.list(financialYear).then((r) => r.data as Form16Record[]),
  });
  const employeeRows: EmployeeOption[] = Array.isArray(employees.data) ? employees.data : employees.data?.items || employees.data?.data || [];
  const generate = useMutation({
    mutationFn: () => form16Api.generate({
      financialYear,
      employeeIds: selectedEmployeeIds.length ? selectedEmployeeIds : undefined,
    }),
    onSuccess: (response) => {
      toast({ title: "Form 16 generated", description: `${response.data.length} employee record(s) updated.` });
      setSelectedEmployeeIds([]);
      qc.invalidateQueries({ queryKey: ["form16-records"] });
    },
    onError: error => toast({ title: "Unable to generate Form 16", description: payrollError(error), variant: "destructive" }),
  });
  const uploadPartA = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      return form16Api.uploadPartA(id, formData);
    },
    onSuccess: () => {
      toast({ title: "Part A uploaded" });
      qc.invalidateQueries({ queryKey: ["form16-records"] });
    },
    onError: () => toast({ title: "Unable to upload Part A", variant: "destructive" }),
  });
  const publish = useMutation({
    mutationFn: (id: number) => form16Api.publish(id),
    onSuccess: () => {
      toast({ title: "Form 16 published to ESS" });
      qc.invalidateQueries({ queryKey: ["form16-records"] });
    },
    onError: error => toast({ title: "Unable to publish Form 16", description: payrollError(error), variant: "destructive" }),
  });

  const workflow = useMutation({
    mutationFn: ({ action, id, file }: { action: string; id?: number; file?: File }) => {
      if (action === "review") return form16Api.review(id!);
      if (action === "withdraw") return form16Api.withdraw(id!);
      const data = new FormData(); data.append("file", file!);
      if (action === "trust") return form16Api.uploadSigningTrust(data);
      if (action === "part-b") return form16Api.uploadPartB(id!, data);
      return form16Api.uploadSigned(id!, data);
    },
    onSuccess: () => { toast({ title: "Form 16 workflow updated" }); qc.invalidateQueries({ queryKey: ["form16-records"] }); qc.invalidateQueries({ queryKey: ["payroll-delivery-settings"] }); },
    onError: error => toast({ title: "Form 16 operation failed", description: payrollError(error), variant: "destructive" }),
  });

  const phoneBusy = phone && (generate.isPending || uploadPartA.isPending || publish.isPending || workflow.isPending || downloadFile.isPending);
  const operationError = generate.error || uploadPartA.error || publish.error || workflow.error;

  const toggleEmployee = (id: number) => {
    setSelectedEmployeeIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  return (
    <div className="hrms-form16 grid gap-5 xl:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Generate Form 16</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <MobileDisclosure maxWidth={480} title="Signing setup & workflow guidance">
          <p className="text-sm text-muted-foreground">Generate from locked or paid payroll. Upload TRACES Part A, review the merged certificate, sign the downloaded PDF using the authorized signatory's DSC, then upload it for verification and publication.</p>
          <label className="block space-y-2 text-sm">Trusted public signing certificate (PEM)<Input aria-label="Form 16 signing trust certificate" type="file" accept=".pem,.crt" disabled={workflow.isPending || !canApprove || phoneBusy} onChange={event => { const file = event.target.files?.[0]; if (file) workflow.mutate({ action: "trust", file }); event.target.value = ""; }} /></label>
          <p className="text-sm">Signing trust: {phone && !permissions.data ? "Unavailable" : permissions.data?.form16_trust_configured ? "Configured" : "Public signatory certificate required"}</p>
          {permissions.data && !canApprove && <p className="text-xs text-muted-foreground">A payroll approver must configure signing trust, review, and publish certificates.</p>}
          <p className="text-xs text-muted-foreground">Upload only an authorized public certificate. Private keys stay with the signatory. Signature integrity and configured trust are checked locally; online revocation is not checked.</p>
          </MobileDisclosure>
          {phone && permissions.isError && <p role="alert">Signing permissions could not load. <Button variant="outline" onClick={() => void permissions.refetch()}>Retry signing permissions</Button></p>}
          <div className="space-y-2">
            <Label htmlFor="form16-financial-year">Financial Year</Label>
            <Input id="form16-financial-year" disabled={phoneBusy} value={financialYear} onChange={(e) => setFinancialYear(e.target.value)} placeholder="2025-26" />
          </div>
          <MobileDisclosure maxWidth={480} title={`Employees · ${selectedEmployeeIds.length ? `${selectedEmployeeIds.length} selected` : "All eligible"}`}>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Employees</Label>
              <Button type="button" variant="ghost" size="sm" disabled={phoneBusy} onClick={() => setSelectedEmployeeIds([])}>All</Button>
            </div>
            <Input disabled={phoneBusy} aria-label="Search Form 16 employees" placeholder="Search employees" value={employeeSearch} onChange={event => { setEmployeeSearch(event.target.value); setEmployeePage(1); }} />
            <div className="max-h-72 space-y-2 overflow-auto rounded-md border p-2">
              {employees.isLoading && <div className="h-24 animate-pulse rounded bg-muted" />}
              {employeeRows.map((employee) => {
                const name = employeeName(employee);
                return (
                  <label key={employee.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-muted">
                    <input type="checkbox" disabled={phoneBusy} checked={selectedEmployeeIds.includes(employee.id)} onChange={() => toggleEmployee(employee.id)} />
                    <span className="min-w-0 truncate">{name}</span>
                  </label>
                );
              })}
              {!employees.isLoading && !(phone && employees.isError) && !employeeRows.length && <p className="px-2 py-4 text-sm text-muted-foreground">No employees found.</p>}
            </div>
            {employees.isError && <p role="alert" className="text-sm">Employee selection could not load. <Button variant="outline" onClick={() => employees.refetch()}>Retry employees</Button></p>}
            <div className="flex items-center gap-2 text-xs"><Button size="sm" variant="outline" disabled={employeePage === 1 || employees.isFetching || phoneBusy} onClick={() => setEmployeePage(value => value - 1)}>Previous employees</Button><span>Page {employeePage}</span><Button size="sm" variant="outline" disabled={employeeRows.length < 100 || employees.isFetching || phoneBusy} onClick={() => setEmployeePage(value => value + 1)}>Next employees</Button></div>
            <p className="text-xs text-muted-foreground">Leave empty to generate for employees with payroll in this financial year.</p>
          </div>
          </MobileDisclosure>
          {phone && operationError && <p role="alert" className="text-sm text-destructive">Form 16 operation failed. {payrollError(operationError)} Retry the same action.</p>}
          {phone && uploadPartA.isError && uploadPartA.variables && <Button variant="outline" disabled={phoneBusy} onClick={() => uploadPartA.mutate(uploadPartA.variables!)}>Retry Part A upload · {uploadPartA.variables.file.name}</Button>}
          {phone && workflow.isError && workflow.variables?.file && <Button variant="outline" disabled={phoneBusy} onClick={() => workflow.mutate(workflow.variables!)}>Retry file upload · {workflow.variables.file.name}</Button>}
          {phoneBusy && <p role="status">Processing Form 16…</p>}
          {phone && downloadFile.isError && <p role="alert" className="text-sm text-destructive">Form 16 download failed. Use its download action to retry.</p>}
          <Button className="w-full" onClick={() => generate.mutate()} disabled={!financialYear || generate.isPending || phoneBusy}>
            {generate.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}
            Generate Part B
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Employee Form 16 Records</CardTitle>
              <p className="text-sm text-muted-foreground">Prepare Part B, upload Part A, review, verify the signed PDF, and publish to employee self-service.</p>
            </div>
            <Badge variant="outline">{phone && !records.data ? "—" : records.data?.length || 0} records</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {phone && records.isError && <p role="alert">Form 16 records could not load. <Button variant="outline" onClick={() => void records.refetch()}>Retry Form 16 records</Button></p>}
          {records.isLoading ? <div className="h-48 animate-pulse rounded bg-muted" /> : phone && records.isError && !records.data ? null : (
            <div className="overflow-x-auto rounded-lg border">
              <GridTable gridId="apps/hrms/pages/compliance/StatutoryCompliancePage:table-2" className="w-full min-w-[960px] text-sm">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Employee</th>
                    <th className="px-3 py-2 text-left">PAN</th>
                    <th className="px-3 py-2 text-left">Taxable Income</th>
                    <th className="px-3 py-2 text-left">TDS</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-left">Files</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(records.data || []).map((record) => (
                    <tr {...recordPreviewProps(record)} key={record.id} className="border-t align-top">
                      <td className="px-3 py-2">
                        <p className="font-medium">{record.employee?.name || `Employee #${record.employeeId}`}</p>
                        <p className="text-xs text-muted-foreground">{record.employee?.employeeId || record.employeeId}</p>
                      </td>
                      <td className="px-3 py-2">{record.employee?.pan || "-"}</td>
                      <td className="px-3 py-2">{money(record.taxableIncome)}</td>
                      <td className="px-3 py-2">{money(record.taxDeducted)}</td>
                      <td className="px-3 py-2"><StatusBadge status={record.status} /><p className="mt-1 text-xs">Signature: {record.digitalSignatureStatus || "pending"}</p><p className="text-xs">Review: {record.reviewedAt ? "Complete" : "Required"}</p></td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          <Badge variant={record.partAFilePath ? "outline" : "secondary"}>Part A</Badge>
                          <Badge variant={record.partBFilePath ? "outline" : "secondary"}>Part B</Badge>
                          <Badge variant={record.combinedFilePath ? "outline" : "secondary"}>Combined</Badge>
                          {record.signedFilePath && <Badge variant="outline">Signed &amp; verified</Badge>}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap justify-end gap-2">
                          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border px-3 text-xs font-medium hover:bg-muted">
                            <Upload className="mr-2 h-4 w-4" /> Part A
                            <FileControl
                              type="file"
                              accept="application/pdf"
                              className={phone ? "sr-only" : "hidden"}
                              aria-label={phone ? `Upload Part A for ${record.employee?.name || record.employeeId}` : undefined}
                              disabled={phoneBusy}
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) uploadPartA.mutate({ id: record.id, file });
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border px-3 text-xs">Upload reviewed Part B<FileControl aria-label={`Upload reviewed Part B for ${record.employee?.name || record.employeeId}`} type="file" accept="application/pdf" className="sr-only" disabled={record.status === "published" || workflow.isPending || phoneBusy} onChange={event => { const file = event.target.files?.[0]; if (file) workflow.mutate({ action: "part-b", id: record.id, file }); event.target.value = ""; }} /></label>
                          <Button size="sm" variant="outline" disabled={!canApprove || !record.partAFilePath || !record.partBFilePath || record.status === "published" || workflow.isPending || phoneBusy} onClick={() => workflow.mutate({ action: "review", id: record.id })}>Confirm review</Button>
                          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border px-3 text-xs">Upload DSC-signed PDF<FileControl aria-label={`Upload DSC-signed Form 16 for ${record.employee?.name || record.employeeId}`} type="file" accept="application/pdf" className="sr-only" disabled={!canApprove || !record.reviewedAt || record.status === "published" || workflow.isPending || phoneBusy} onChange={event => { const file = event.target.files?.[0]; if (file) workflow.mutate({ action: "signed", id: record.id, file }); event.target.value = ""; }} /></label>
                          <Button size="sm" variant="outline" onClick={() => publish.mutate(record.id)} disabled={!canApprove || record.status === "published" || record.digitalSignatureStatus !== "verified" || !record.reviewedAt || publish.isPending || phoneBusy}>Publish verified Form 16</Button>
                          {record.status === "published" && <Button size="sm" variant="outline" disabled={!canApprove || workflow.isPending || phoneBusy} onClick={() => workflow.mutate({ action: "withdraw", id: record.id })}>Withdraw for correction</Button>}
                          <Button size="sm" variant="ghost" onClick={() => phone ? downloadFile.mutate(record) : downloadForm16(record)} disabled={phoneBusy || (!record.partBFilePath && !record.combinedFilePath && !record.partAFilePath)}>
                            <Download className="h-4 w-4" />
                            Download for review / signing
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!records.data?.length && (
                    <tr><td colSpan={7} className="px-3 py-10 text-center text-muted-foreground">No Form 16 records generated for this financial year.</td></tr>
                  )}
                </tbody>
              </GridTable>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HistoryTab() {
  const phone = useMobile(480);
  const downloadFile = useMutation({ mutationFn: (id: number) => download(id) });
  const [filters, setFilters] = useState({ statutory_type: "", validation_status: "" });
  const params = { statutory_type: filters.statutory_type || undefined, validation_status: filters.validation_status || undefined };
  const submissions = useQuery({ queryKey: ["statutory-submissions-all", params], queryFn: () => statutoryApi.submissions(params).then((r) => r.data as Submission[]) });
  return (
    <div className="hrms-statutory-history space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <NativeSelect className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Submission type" value={filters.statutory_type} onChange={(e) => setFilters({ ...filters, statutory_type: e.target.value })}><option value="">All types</option>{["PF_ECR", "ESI", "PT", "LWF", "TDS_24Q", "TDS_26Q"].map((type) => <option key={type}>{type}</option>)}</NativeSelect>
        <NativeSelect className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Submission validation status" value={filters.validation_status} onChange={(e) => setFilters({ ...filters, validation_status: e.target.value })}><option value="">All statuses</option>{["valid", "invalid", "submitted"].map((status) => <option key={status}>{status}</option>)}</NativeSelect>
      </div>
      {phone && submissions.isError && <p role="alert" className="text-sm text-destructive">Submission history could not load. <Button variant="outline" onClick={() => void submissions.refetch()}>Retry submission history</Button></p>}
      {phone && downloadFile.isPending && <p role="status">Preparing submission CSV…</p>}
      {phone && downloadFile.isError && <p role="alert" className="text-sm text-destructive">Submission CSV could not download. Use its download action to retry.</p>}
      {submissions.isLoading ? <div className="h-40 animate-pulse rounded bg-muted" /> : phone && submissions.isError && !submissions.data ? null : <HistoryTable rows={submissions.data || []} onDownload={phone ? id => downloadFile.mutate(id) : undefined} downloadBusy={phone && downloadFile.isPending} showValidationDetails={phone} />}
    </div>
  );
}

function HistoryTable({ rows, compact, onMarkSubmitted, onDownload, downloadBusy, showValidationDetails }: { rows: Submission[]; compact?: boolean; onMarkSubmitted?: (id: number) => void; onDownload?: (id: number) => void; downloadBusy?: boolean; showValidationDetails?: boolean }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{compact ? "Previous Submissions" : "Submission History"}</CardTitle></CardHeader>
      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <GridTable gridId="apps/hrms/pages/compliance/StatutoryCompliancePage:table-3" className="w-full min-w-[840px] text-sm">
            <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Payroll Period</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">Rows</th><th className="px-3 py-2 text-left">Amount</th><th className="px-3 py-2 text-left">Submission</th><th className="px-3 py-2 text-left">ACK Number</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr {...recordPreviewProps(row)} key={row.id} className="border-t">
                  <td className="px-3 py-2"><TypeBadge type={row.statutory_type} /></td>
                  <td className="px-3 py-2">{row.payroll_period || row.payroll_run_id}</td>
                  <td className="px-3 py-2"><StatusBadge status={row.filing_status || row.validation_status} />{row.validation_status === "invalid" && <Badge variant="outline" className="ml-2">{row.validation_errors_json?.length || 0} errors</Badge>}{showValidationDetails && row.validation_status === "invalid" && !!row.validation_errors_json?.length && <HistoryValidationErrors data-grid-value="" row={row} />}</td>
                  <td className="px-3 py-2">{row.row_count || 0}</td>
                  <td className="px-3 py-2">{money(row.total_amount)}</td>
                  <td className="px-3 py-2">
                    <p>{row.submitted_at ? new Date(row.submitted_at).toLocaleString("en-IN") : row.portal_connector_status || "ready for manual upload"}</p>
                    <p className="text-xs text-muted-foreground">{row.digital_signature_status || "signature not applicable"}</p>
                  </td>
                  <td className="px-3 py-2">{row.portal_reference || "-"}</td>
                  <td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" aria-label={onDownload ? `Download submission ${row.id}` : undefined} disabled={downloadBusy} onClick={() => onDownload ? onDownload(row.id) : download(row.id)}><Download className="h-4 w-4" /></Button>{onMarkSubmitted && row.validation_status === "valid" && <Button size="sm" variant="outline" onClick={() => onMarkSubmitted(row.id)}>Submit</Button>}</td>
                </tr>
              ))}
            </tbody>
          </GridTable>
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryValidationErrors({ row }: { row: Submission; "data-grid-value"?: string }) {
  return <details className="hrms-statutory-validation"><summary aria-label={`Validation errors for submission ${row.id}`}>{row.validation_errors_json!.length} validation errors</summary><div>{row.validation_errors_json!.map((error, index) => <p key={index}>Row {error.row}, {error.field}{error.code ? ` (${error.code})` : ""}{error.severity ? ` [${error.severity}]` : ""}: {error.message || error.error}</p>)}</div></details>;
}

function CompliancePreviewCard({
  title,
  description,
  preview,
  loading,
  columns,
  onGenerate,
  generating,
}: {
  title: string;
  description: string;
  preview?: CompliancePreview;
  loading: boolean;
  columns: string[];
  onGenerate: () => void;
  generating: boolean;
}) {
  const phone = useMobile(480);
  const errors = preview?.validation_errors || [];
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <Badge variant={errors.length ? "destructive" : "outline"}>{loading ? "Checking" : phone && !preview ? "Unavailable" : `${errors.length} issues`}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-md border p-2">
            <p className="text-xs text-muted-foreground">Rule</p>
            <p className="font-medium">{preview?.rule || "-"}</p>
          </div>
          <div className="rounded-md border p-2">
            <p className="text-xs text-muted-foreground">Employees</p>
            <p className="font-medium">{phone && !preview ? "—" : preview?.total_employees || 0}</p>
          </div>
          <div className="rounded-md border p-2">
            <p className="text-xs text-muted-foreground">Amount</p>
            <p className="font-medium">{phone && !preview ? "—" : money(preview?.total_amount)}</p>
          </div>
        </div>
        {errors.length > 0 && (
          <div className="max-h-24 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
            {errors.slice(0, phone ? undefined : 6).map((error) => <p key={error}>{error}</p>)}
          </div>
        )}
        {phone && !preview ? <p role={loading ? "status" : undefined} className="text-sm text-muted-foreground">{loading ? "Loading preview…" : "Preview is unavailable."}</p> : <div className="overflow-x-auto rounded-md border">
          <GridTable gridId="apps/hrms/pages/compliance/StatutoryCompliancePage:table-4" className="w-full min-w-[640px] text-xs">
            <thead className="bg-muted/60">
              <tr>{columns.map((column) => <th key={column} className="px-2 py-2 text-left capitalize">{column.replace(/_/g, " ")}</th>)}</tr>
            </thead>
            <tbody>
              {(preview?.rows || []).slice(0, phone ? undefined : 5).map((row, index) => (
                <tr {...recordPreviewProps(row)} key={index} className="border-t">
                  {columns.map((column) => <td key={column} className="px-2 py-2">{String(row[column] ?? "-")}</td>)}
                </tr>
              ))}
              {!loading && (!phone || !!preview) && !preview?.rows?.length && <tr><td colSpan={columns.length} className="px-2 py-4 text-center text-muted-foreground">No contribution rows found.</td></tr>}
            </tbody>
          </GridTable>
        </div>}
        <Button className="w-full" variant="outline" onClick={onGenerate} disabled={!preview || errors.length > 0 || generating}>
          {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}
          Generate {title}
        </Button>
      </CardContent>
    </Card>
  );
}

function Summary({ label, value, className }: { label: string; value: number | string; className: string }) {
  return <Card><CardContent className="p-5"><div className={cn("mb-3 inline-flex rounded-lg p-2", className)}><TriangleAlert className="h-5 w-5" /></div><p className="text-2xl font-semibold">{value}</p><p className="text-sm text-muted-foreground">{label}</p></CardContent></Card>;
}

function TypeBadge({ type }: { type: string }) {
  return <Badge variant="outline">{type}</Badge>;
}

function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();
  const cls = lower === "filed" || lower === "valid" || lower === "submitted" ? "bg-green-100 text-green-800" : lower === "overdue" || lower === "invalid" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800";
  return <Badge className={cn("border-0 capitalize", cls)}>{status}</Badge>;
}

function ErrorList({ errors }: { errors: Array<{ row: number; field: string; code?: string; message?: string; error: string; severity?: string }> }) {
  const [open, setOpen] = useState(false);
  return <div><Button variant="outline" size="sm" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} validation errors</Button>{open && <div className="mt-3 max-h-52 overflow-auto rounded border p-3 text-sm">{errors.map((err, index) => <p key={index}>Row {err.row}, {err.field} {err.code ? `(${err.code})` : ""}: {err.message || err.error}</p>)}</div>}</div>;
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><div className="w-full max-w-md rounded-lg bg-background p-5 shadow-lg"><div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">{title}</h2><Button variant="ghost" size="sm" onClick={onClose}>Close</Button></div>{children}</div></div>;
}

function employeeName(employee: EmployeeOption) {
  const first = employee.first_name || employee.firstName || "";
  const last = employee.last_name || employee.lastName || "";
  const name = `${first} ${last}`.trim();
  return name || employee.employee_id || employee.employeeId || `Employee #${employee.id}`;
}

async function download(id: number) {
  const response = await statutoryApi.downloadSubmission(id);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `statutory_submission_${id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

async function downloadForm16(record: Form16Record) {
  const response = await form16Api.download(record.id);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `form16_${record.employee?.employeeId || record.employeeId}_${record.financialYear}.pdf`;
  link.click();
  URL.revokeObjectURL(url);
}

async function downloadComplianceExport(item: ComplianceExport) {
  const response = await statutoryApi.downloadComplianceExport(item.id);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${item.export_type}_${item.id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
