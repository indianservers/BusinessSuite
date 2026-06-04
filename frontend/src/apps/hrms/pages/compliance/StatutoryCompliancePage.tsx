import { useState } from "react";
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
  const [tab, setTab] = useState<(typeof TABS)[number]>("Compliance Calendar");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Statutory Compliance</h1>
        <p className="page-description">Track due dates, generate statutory files, and monitor portal submission status.</p>
      </div>
      <div className="flex flex-wrap gap-2 border-b">
        {TABS.map((item) => (
          <button
            key={item}
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

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Summary label="Pending" value={counts.Pending || 0} className="bg-yellow-50 text-yellow-700" />
        <Summary label="Filed" value={counts.Filed || 0} className="bg-green-50 text-green-700" />
        <Summary label="Overdue" value={counts.Overdue || 0} className="bg-red-50 text-red-700" />
        <Summary label="Upcoming this month" value={summary.data?.upcoming_count || 0} className="bg-blue-50 text-blue-700" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Compliance Calendar</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.statutory_type} onChange={(e) => setFilters({ ...filters, statutory_type: e.target.value })}>
              <option value="">All types</option>{TYPES.map((type) => <option key={type}>{type}</option>)}
            </select>
            <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All statuses</option>{["Pending", "Filed", "Overdue"].map((status) => <option key={status}>{status}</option>)}
            </select>
            <Input value={filters.year} onChange={(e) => setFilters({ ...filters, year: e.target.value })} placeholder="Year" />
          </div>
          {calendar.isLoading ? <div className="h-40 animate-pulse rounded bg-muted" /> : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[820px] text-sm">
                <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Description</th><th className="px-3 py-2 text-left">Period</th><th className="px-3 py-2 text-left">Due Date</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
                <tbody>
                  {(calendar.data || []).map((item) => {
                    const overdue = item.status !== "Filed" && new Date(item.due_date) < new Date();
                    return (
                      <tr key={item.id} className="border-t">
                        <td className="px-3 py-2"><TypeBadge type={item.statutory_type} /></td>
                        <td className="px-3 py-2">{item.description || "Statutory filing"}</td>
                        <td className="px-3 py-2">{item.period_start || "-"} to {item.period_end || "-"}</td>
                        <td className="px-3 py-2">{item.due_date}</td>
                        <td className="px-3 py-2">
                          <StatusBadge status={item.effective_status || (overdue ? "Overdue" : item.status)} />
                          {item.reminder_due_on && <p className="mt-1 text-xs text-muted-foreground">Reminder {item.reminder_status || "scheduled"}: {item.reminder_due_on}</p>}
                        </td>
                        <td className="px-3 py-2 text-right">{item.status !== "Filed" && <Button size="sm" variant="outline" onClick={() => setMarking(item)}>Mark Filed</Button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      {marking && (
        <Modal title="Mark Filed" onClose={() => setMarking(null)}>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Confirm filing for {marking.statutory_type} due on {marking.due_date}.</p>
            <Input value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Optional remarks" />
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setMarking(null)}>Cancel</Button><Button onClick={() => markFiled.mutate()} disabled={markFiled.isPending}>Confirm</Button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function GenerateTab() {
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

  return (
    <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Payroll Runs</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {runs.isLoading && <div className="h-40 animate-pulse rounded bg-muted" />}
          {lockedRuns.map((run) => (
            <button key={run.id} type="button" onClick={() => setSelectedRunId(run.id)} className={cn("w-full rounded-lg border p-3 text-left", selectedRunId === run.id && "border-primary bg-primary/10")}>
              <p className="font-medium">{run.month}/{run.year}</p>
              <p className="text-sm text-muted-foreground">{run.status} - {run.total_employees || run.employee_count || 0} employees</p>
            </button>
          ))}
        </CardContent>
      </Card>
      <div className="space-y-5">
        {selectedRunId && (
          <div className="grid gap-4 lg:grid-cols-2">
            <CompliancePreviewCard
              title="PF ECR"
              description="EPFO ECR wage and contribution preview"
              preview={pfPreview.data}
              loading={pfPreview.isLoading}
              columns={["uan", "member_name", "gross_wages", "epf_wages", "employee_pf_contribution", "employer_pf_contribution", "eps_contribution"]}
              onGenerate={() => complianceGenerate.mutate("pf")}
              generating={complianceGenerate.isPending}
            />
            <CompliancePreviewCard
              title="ESI Challan"
              description="ESI contribution report and challan preview"
              preview={esiPreview.data}
              loading={esiPreview.isLoading}
              columns={["esic_number", "employee_name", "gross_wages", "employee_esi", "employer_esi", "payable_days"]}
              onGenerate={() => complianceGenerate.mutate("esi")}
              generating={complianceGenerate.isPending}
            />
          </div>
        )}
        {complianceExport && (
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
              <div>
                <p className="font-medium">{complianceExport.export_type.toUpperCase()} generated</p>
                <p className="text-muted-foreground">{complianceExport.file_path}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => downloadComplianceExport(complianceExport)}>
                <Download className="mr-2 h-4 w-4" /> Download
              </Button>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader><CardTitle className="text-base">Generate Files</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {!selectedRunId && <p className="text-sm text-muted-foreground">Select a locked or paid payroll run to generate files.</p>}
            {selectedRunId && FILE_TYPES.map(([type, label]) => (
              <Button key={type} className="w-full justify-start" variant="outline" onClick={() => generate.mutate(type)} disabled={generate.isPending}>
                {generate.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />} {label}
              </Button>
            ))}
            {lastResult && (
              <div className="rounded-lg border p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <StatusBadge status={lastResult.filing_status || lastResult.validation_status} />
                  <Badge variant="outline">{lastResult.portal_connector_status || "not_configured"}</Badge>
                  <Badge variant="outline">{lastResult.digital_signature_status || "not_applicable"}</Badge>
                  <span className="text-sm">{lastResult.row_count} rows - {money(lastResult.total_amount)}</span>
                </div>
                {!!lastResult.errors?.length && <ErrorList errors={lastResult.errors} />}
                {!lastResult.errors?.length && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => download(lastResult.submission_id)}>Download CSV</Button><Button size="sm" onClick={() => setAckSubmission(lastResult.submission_id)}>Mark as Submitted</Button></div>}
              </div>
            )}
          </CardContent>
        </Card>
        <HistoryTable rows={submissions.data || []} compact onMarkSubmitted={setAckSubmission} />
      </div>
      {ackSubmission && (
        <Modal title="Portal ACK Number" onClose={() => setAckSubmission(null)}>
          <div className="space-y-4">
            <Input value={ack} onChange={(e) => setAck(e.target.value)} placeholder="Acknowledgement number" />
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setAckSubmission(null)}>Cancel</Button><Button disabled={!ack || markSubmitted.isPending} onClick={() => markSubmitted.mutate()}>Save</Button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Form16Tab() {
  const qc = useQueryClient();
  const now = new Date();
  const defaultFyStart = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const [financialYear, setFinancialYear] = useState(`${defaultFyStart}-${String(defaultFyStart + 1).slice(-2)}`);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<number[]>([]);
  const employees = useQuery({
    queryKey: ["form16-employees"],
    queryFn: () => employeeApi.list({ limit: 500, per_page: 500 }).then((r) => r.data),
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
    onError: () => toast({ title: "Unable to generate Form 16", variant: "destructive" }),
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
    onError: () => toast({ title: "Unable to publish Form 16", variant: "destructive" }),
  });

  const toggleEmployee = (id: number) => {
    setSelectedEmployeeIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Generate Form 16</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Financial Year</Label>
            <Input value={financialYear} onChange={(e) => setFinancialYear(e.target.value)} placeholder="2025-26" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Employees</Label>
              <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedEmployeeIds([])}>All</Button>
            </div>
            <div className="max-h-72 space-y-2 overflow-auto rounded-md border p-2">
              {employees.isLoading && <div className="h-24 animate-pulse rounded bg-muted" />}
              {employeeRows.map((employee) => {
                const name = employeeName(employee);
                return (
                  <label key={employee.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-muted">
                    <input type="checkbox" checked={selectedEmployeeIds.includes(employee.id)} onChange={() => toggleEmployee(employee.id)} />
                    <span className="min-w-0 truncate">{name}</span>
                  </label>
                );
              })}
              {!employees.isLoading && !employeeRows.length && <p className="px-2 py-4 text-sm text-muted-foreground">No employees found.</p>}
            </div>
            <p className="text-xs text-muted-foreground">Leave empty to generate for employees with payroll in this financial year.</p>
          </div>
          <Button className="w-full" onClick={() => generate.mutate()} disabled={!financialYear || generate.isPending}>
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
              <p className="text-sm text-muted-foreground">Upload TRACES Part A, publish approved certificates, and download employee PDFs.</p>
            </div>
            <Badge variant="outline">{records.data?.length || 0} records</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {records.isLoading ? <div className="h-48 animate-pulse rounded bg-muted" /> : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[960px] text-sm">
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
                    <tr key={record.id} className="border-t align-top">
                      <td className="px-3 py-2">
                        <p className="font-medium">{record.employee?.name || `Employee #${record.employeeId}`}</p>
                        <p className="text-xs text-muted-foreground">{record.employee?.employeeId || record.employeeId}</p>
                      </td>
                      <td className="px-3 py-2">{record.employee?.pan || "-"}</td>
                      <td className="px-3 py-2">{money(record.taxableIncome)}</td>
                      <td className="px-3 py-2">{money(record.taxDeducted)}</td>
                      <td className="px-3 py-2"><StatusBadge status={record.status} /></td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          <Badge variant={record.partAFilePath ? "outline" : "secondary"}>Part A</Badge>
                          <Badge variant={record.partBFilePath ? "outline" : "secondary"}>Part B</Badge>
                          <Badge variant={record.combinedFilePath ? "outline" : "secondary"}>Combined</Badge>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap justify-end gap-2">
                          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border px-3 text-xs font-medium hover:bg-muted">
                            <Upload className="mr-2 h-4 w-4" /> Part A
                            <input
                              type="file"
                              accept="application/pdf"
                              className="hidden"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) uploadPartA.mutate({ id: record.id, file });
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                          <Button size="sm" variant="outline" onClick={() => publish.mutate(record.id)} disabled={record.status === "published" || publish.isPending}>Publish</Button>
                          <Button size="sm" variant="ghost" onClick={() => downloadForm16(record)} disabled={!record.partBFilePath && !record.combinedFilePath && !record.partAFilePath}>
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!records.data?.length && (
                    <tr><td colSpan={7} className="px-3 py-10 text-center text-muted-foreground">No Form 16 records generated for this financial year.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HistoryTab() {
  const [filters, setFilters] = useState({ statutory_type: "", validation_status: "" });
  const params = { statutory_type: filters.statutory_type || undefined, validation_status: filters.validation_status || undefined };
  const submissions = useQuery({ queryKey: ["statutory-submissions-all", params], queryFn: () => statutoryApi.submissions(params).then((r) => r.data as Submission[]) });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.statutory_type} onChange={(e) => setFilters({ ...filters, statutory_type: e.target.value })}><option value="">All types</option>{["PF_ECR", "ESI", "PT", "LWF", "TDS_24Q", "TDS_26Q"].map((type) => <option key={type}>{type}</option>)}</select>
        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.validation_status} onChange={(e) => setFilters({ ...filters, validation_status: e.target.value })}><option value="">All statuses</option>{["valid", "invalid", "submitted"].map((status) => <option key={status}>{status}</option>)}</select>
      </div>
      {submissions.isLoading ? <div className="h-40 animate-pulse rounded bg-muted" /> : <HistoryTable rows={submissions.data || []} />}
    </div>
  );
}

function HistoryTable({ rows, compact, onMarkSubmitted }: { rows: Submission[]; compact?: boolean; onMarkSubmitted?: (id: number) => void }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{compact ? "Previous Submissions" : "Submission History"}</CardTitle></CardHeader>
      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[840px] text-sm">
            <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Payroll Period</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">Rows</th><th className="px-3 py-2 text-left">Amount</th><th className="px-3 py-2 text-left">Submission</th><th className="px-3 py-2 text-left">ACK Number</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="px-3 py-2"><TypeBadge type={row.statutory_type} /></td>
                  <td className="px-3 py-2">{row.payroll_period || row.payroll_run_id}</td>
                  <td className="px-3 py-2"><StatusBadge status={row.filing_status || row.validation_status} />{row.validation_status === "invalid" && <Badge variant="outline" className="ml-2">{row.validation_errors_json?.length || 0} errors</Badge>}</td>
                  <td className="px-3 py-2">{row.row_count || 0}</td>
                  <td className="px-3 py-2">{money(row.total_amount)}</td>
                  <td className="px-3 py-2">
                    <p>{row.submitted_at ? new Date(row.submitted_at).toLocaleString("en-IN") : row.portal_connector_status || "ready for manual upload"}</p>
                    <p className="text-xs text-muted-foreground">{row.digital_signature_status || "signature not applicable"}</p>
                  </td>
                  <td className="px-3 py-2">{row.portal_reference || "-"}</td>
                  <td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" onClick={() => download(row.id)}><Download className="h-4 w-4" /></Button>{onMarkSubmitted && row.validation_status === "valid" && <Button size="sm" variant="outline" onClick={() => onMarkSubmitted(row.id)}>Submit</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
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
  const errors = preview?.validation_errors || [];
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <Badge variant={errors.length ? "destructive" : "outline"}>{loading ? "Checking" : `${errors.length} issues`}</Badge>
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
            <p className="font-medium">{preview?.total_employees || 0}</p>
          </div>
          <div className="rounded-md border p-2">
            <p className="text-xs text-muted-foreground">Amount</p>
            <p className="font-medium">{money(preview?.total_amount)}</p>
          </div>
        </div>
        {errors.length > 0 && (
          <div className="max-h-24 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
            {errors.slice(0, 6).map((error) => <p key={error}>{error}</p>)}
          </div>
        )}
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[640px] text-xs">
            <thead className="bg-muted/60">
              <tr>{columns.map((column) => <th key={column} className="px-2 py-2 text-left capitalize">{column.replace(/_/g, " ")}</th>)}</tr>
            </thead>
            <tbody>
              {(preview?.rows || []).slice(0, 5).map((row, index) => (
                <tr key={index} className="border-t">
                  {columns.map((column) => <td key={column} className="px-2 py-2">{String(row[column] ?? "-")}</td>)}
                </tr>
              ))}
              {!loading && !preview?.rows?.length && <tr><td colSpan={columns.length} className="px-2 py-4 text-center text-muted-foreground">No contribution rows found.</td></tr>}
            </tbody>
          </table>
        </div>
        <Button className="w-full" variant="outline" onClick={onGenerate} disabled={!preview || errors.length > 0 || generating}>
          {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}
          Generate {title}
        </Button>
      </CardContent>
    </Card>
  );
}

function Summary({ label, value, className }: { label: string; value: number; className: string }) {
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
