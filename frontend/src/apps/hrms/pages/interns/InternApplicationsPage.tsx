import { useState, useDeferredValue, useRef } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, UserPlus, ArrowLeft } from "lucide-react";
import { api, companyApi } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";
import InternApplicationSettings from "./InternApplicationSettings";
import InternQuickLinks from "./InternQuickLinks";
type Row = Record<string, any>;
const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

type DecisionStatus = "Approved" | "Rejected" | "Correction Requested";
type OrganizationOptions = { branches: Row[]; departments: Row[]; designations: Row[]; managers: Row[] };
const reviewable = (application: Row) => ["Pending", "Correction Requested"].includes(application.status);
const newDecision = (): Row => ({ branch_id: "", department_id: "", designation_id: "", reporting_manager_id: "", date_of_joining: new Date().toLocaleDateString("en-CA"), review_note: "" });
const decisionBody = (status: DecisionStatus, values: Row) => status === "Approved" ? {
  ...Object.fromEntries(Object.entries(values).map(([key, value]) => [key, key.endsWith("_id") ? Number(value) || null : value])), status,
  ...(Number(values.reporting_manager_id) < 0 ? { reporting_manager_id: null, reporting_manager_user_id: -Number(values.reporting_manager_id) } : {}),
} : { status, review_note: values.review_note };
const reviewError = (error: any) => typeof error.response?.data?.detail === "string" ? error.response.data.detail : "Could not update this application. Please refresh and retry.";

function IntakeJobErrors({ jobId, total }: { jobId: number; total: number }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const { data, error } = useQuery<Row>({ queryKey: ["intake-job-errors", jobId, page, total], enabled: open,
    queryFn: () => api.get(`/interns-hub/admin/application-jobs/${jobId}/errors`, { params: { page } }).then(r => r.data) });
  return <details onToggle={e => setOpen(e.currentTarget.open)}><summary>Application errors ({total})</summary>
    {error && <p role="alert">{reviewError(error)}</p>}
    <ul>{data?.items.map((item: Row) => <li key={item.id}>#{item.id}: {item.message}</li>)}</ul>
    <div className="flex gap-3"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous errors</Button>
      <Button size="sm" variant="outline" disabled={!data || page * 50 >= data.total} onClick={() => setPage(p => p + 1)}>More errors</Button></div>
  </details>;
}

function DecisionFields({ decision, setDecision, options, prefix, approval = true, requireReason = false }: {
  decision: Row; setDecision: (value: Row) => void; options?: OrganizationOptions; prefix: string; approval?: boolean; requireReason?: boolean;
}) {
  return <>
    {approval && <>
      <div>
        <Label htmlFor={`${prefix}-branch`}>Branch *</Label>
        <select
          id={`${prefix}-branch`}
          required
          className={selectClass}
          value={decision.branch_id}
          onChange={(e) =>
            setDecision({
              ...decision,
              branch_id: e.target.value,
              department_id: "",
              designation_id: "",
            })
          }
        >
          <option value="">Select Branch</option>
          {options?.branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor={`${prefix}-department`}>
          Department *
        </Label>
        <select
          id={`${prefix}-department`}
          required
          className={selectClass}
          value={decision.department_id}
          onChange={(e) =>
            setDecision({
              ...decision,
              department_id: e.target.value,
              designation_id: "",
            })
          }
        >
          <option value="">Select Department</option>
          {options?.departments
            .filter(
              (d) => d.branch_id === Number(decision.branch_id),
            )
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
        </select>
      </div>
      <div>
        <Label htmlFor={`${prefix}-designation`}>
          Designation *
        </Label>
        <select
          id={`${prefix}-designation`}
          required
          className={selectClass}
          value={decision.designation_id}
          onChange={(e) =>
            setDecision({
              ...decision,
              designation_id: e.target.value,
            })
          }
        >
          <option value="">Select Designation</option>
          {options?.designations
            .filter(
              (d) =>
                d.department_id ===
                Number(decision.department_id),
            )
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
        </select>
      </div>
      <div>
        <Label htmlFor={`${prefix}-manager`}>
          Reporting Manager *
        </Label>
        <select
          id={`${prefix}-manager`}
          required
          className={selectClass}
          value={decision.reporting_manager_id}
          onChange={(e) =>
            setDecision({
              ...decision,
              reporting_manager_id: e.target.value,
            })
          }
        >
          <option value="">Select Manager</option>
          {options?.managers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor={`${prefix}-date`}>Joining Date *</Label>
        <Input
          id={`${prefix}-date`}
          type="date"
          required
          value={decision.date_of_joining}
          onChange={(e) =>
            setDecision({
              ...decision,
              date_of_joining: e.target.value,
            })
          }
        />
      </div>
    </>}
      <div className="sm:col-span-2">
        <Label htmlFor={`${prefix}-note`}>{requireReason ? "Reason / instructions *" : "Note to Applicant"}</Label>
        <textarea
          id={`${prefix}-note`}
          className={selectClass + " h-auto py-2"}
          required={requireReason}
          maxLength={2000}
          rows={3}
          value={decision.review_note}
          onChange={(e) =>
            setDecision({
              ...decision,
              review_note: e.target.value,
            })
          }
        />
      </div>
  </>;
}
export default function InternApplicationsPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number>();
  const [filter, setFilter] = useState("Pending");
  const [search, setSearch] = useState("");
  const [checkedIds, setCheckedIds] = useState<number[]>([]);
  const [bulkReview, setBulkReview] = useState<{ status: DecisionStatus; ids: number[] } | null>(null);
  const [bulkDecision, setBulkDecision] = useState<Row>(newDecision);
  const [intakePage, setIntakePage] = useState(1);
  const deferredSearch = useDeferredValue(search);
  const [bulkAll, setBulkAll] = useState(false);
  const bulkKey = useRef(crypto.randomUUID());
  const [bulkResult, setBulkResult] = useState<{ succeeded: number; failed: { id: number; name: string; message: string }[] } | null>(null);
  const [decision, setDecision] = useState<Row>({
    branch_id: "",
    department_id: "",
    designation_id: "",
    reporting_manager_id: "",
    date_of_joining: new Date().toLocaleDateString("en-CA"),
    review_note: "",
  });
  const { data: intake, isLoading, error } = useQuery<Row>({
    queryKey: ["intern-applications", filter, deferredSearch, intakePage],
    queryFn: () => api.get("/interns-hub/admin/application-intake", { params: { status: filter, search: deferredSearch, page: intakePage, per_page: 50 } }).then(r => r.data),
  });
  const applications: Row[] = intake?.items || [];
  const { data: intakeJobs } = useQuery<Row>({ queryKey: ["intake-jobs"],
    queryFn: () => api.get("/interns-hub/admin/application-jobs").then(r => r.data), refetchInterval: 10000 });
  const { data: options } = useQuery({
    queryKey: ["intern-application-organization"],
    queryFn: async () => {
      const [branches, departments, designations, managerResponse] = await Promise.all([
        companyApi.listBranches(),
        companyApi.listDepartments(),
        companyApi.listDesignations(),
        api.get("/interns-hub/admin/reporting-managers"),
      ]);
      const managers = managerResponse.data as Row[];
      return {
        branches: branches.data as Row[],
        departments: departments.data as Row[],
        designations: designations.data as Row[],
        managers,
      };
    },
  });
  const list = applications.filter((a) => (!filter || a.status === filter) && `${a.full_name} ${a.email} ${a.reference}`.toLowerCase().includes(search.trim().toLowerCase()));
  const eligible = list.filter(reviewable);
  const checkedApplications = applications.filter(item => checkedIds.includes(item.id) && reviewable(item));
  const allChecked = eligible.length > 0 && eligible.every(item => checkedIds.includes(item.id));
  const refreshApplications = () => {
    for (const key of ["intern-applications", "intern-hub-admin", "employees", "intern-management"]) void qc.invalidateQueries({ queryKey: [key] });
  };
  const application = list.find((a) => a.id === selected) || list[0];
  const mutation = useMutation({
    mutationFn: (status: DecisionStatus) =>
      api.post(`/interns-hub/admin/applications/${application.id}/decision`, decisionBody(status, decision)),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["intern-applications"] });
      qc.invalidateQueries({ queryKey: ["intern-hub-admin"] });
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["intern-management"] });
      toast({
        title:
          r.data.status === "Approved"
            ? `Application approved · ${r.data.intern_id}`
            : r.data.status === "Correction Requested" ? "Corrections requested" : "Application rejected",
        description:
          r.data.status === "Approved"
            ? "The intern can now sign in with their application email and password."
            : undefined,
      });
    },
    onError: (e: any) =>
      toast({
        title: "Could not review application",
        description:
          typeof e.response?.data?.detail === "string"
            ? e.response.data.detail
            : "Please check the selected job details.",
        variant: "destructive",
      }),
  });
  const bulkMutation = useMutation({
    mutationFn: async ({ status, ids, values }: { status: DecisionStatus; ids: number[]; values: Row }) => {
      const response = await api.post("/interns-hub/admin/application-jobs", {
        application_ids: ids, all_filtered: bulkAll, status: filter, search: deferredSearch,
        decision: decisionBody(status, values), request_key: bulkKey.current,
      });
      return response.data;
    },
    onSuccess: job => {
      const failed = (job.result?.failed || []).map((item: Row) => ({ ...item, name: `Application #${item.id}` }));
      setBulkResult({ succeeded: job.result?.succeeded || 0, failed });
      setCheckedIds([]); setBulkAll(false); setBulkReview(null);
      refreshApplications(); void qc.invalidateQueries({ queryKey: ["intake-jobs"] });
      toast({ title: `Intake operation #${job.id}: ${job.status}`, description: `${job.cursor}/${job.total} processed. Progress is saved; you can leave this page.` });
    },
    onError: error => toast({ title: "Could not start intake operation", description: reviewError(error), variant: "destructive" }),
  });
  const busy = mutation.isPending || bulkMutation.isPending;
  const openBulkReview = (status: DecisionStatus) => {
    setBulkDecision(newDecision());
    bulkKey.current = crypto.randomUUID();
    setBulkReview({ status, ids: checkedApplications.map(item => item.id) });
  };
  const labels: Record<string, string> = {
    parent_name: "Parent / Guardian",
    mobile: "Mobile",
    identity_type: "ID Proof Type",
    gender: "Gender",
    date_of_birth: "Date of Birth",
    city: "City",
    state: "State",
    tenth_marks: "10th Percentage",
    twelfth_marks: "12th Percentage",
    degree: "Current Degree",
    current_year: "Current Year",
    college: "College / University",
    specialization: "Specialization",
    passout_year: "Year of Passout",
    area_of_interest: "Area of Interest",
    skills: "Skills",
    role: "Applying For",
    mode: "Preferred Mode",
    available_from: "Available From",
    duration: "Duration",
    address: "Current Address",
    linkedin: "LinkedIn",
    emergency_contact: "Emergency Contact",
  };
  return (
    <div className="space-y-6">
      <Link
        className="inline-flex items-center gap-2 text-sm text-primary"
        to="/hrms/interns-hub"
      >
        <ArrowLeft className="h-4 w-4" />
        Interns Hub Management
      </Link>
      <div>
        <h1 className="page-title flex items-center gap-2">
          <UserPlus />
          Signups & Approvals
        </h1>
        <p className="page-description">
          New signups appear below. Select an applicant, check their details, then approve to activate their intern account.
        </p>
      </div>
      <InternQuickLinks />
      <details className="rounded-xl border bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium">Signup form settings</summary>
        <div className="mt-4"><InternApplicationSettings /></div>
      </details>
      <Input aria-label="Search signups" placeholder="Search signups by name, email or reference…" value={search} onChange={(event) => { setSearch(event.target.value); setIntakePage(1); setBulkAll(false); setSelected(undefined); setCheckedIds([]); }} />
      <div className="flex flex-wrap gap-2">
        <Link to="/hrms/interns/profiles" className="inline-flex items-center rounded-md border px-3 py-2 text-sm">Manage connected profiles</Link>
        {["Pending", "Correction Requested", "Approved", "Rejected", ""].map((status) => (
          <Button
            key={status}
            variant={filter === status ? "default" : "outline"}
            onClick={() => {
              setFilter(status); setIntakePage(1); setBulkAll(false);
              setSelected(undefined);
              setCheckedIds([]);
            }}
          >
            {status || "All Applications"} (
            {status ? intake?.counts?.[status] || 0 : Object.values(intake?.counts || {}).reduce((total: number, count) => total + Number(count), 0)})
          </Button>
        ))}
      </div>
      {!error && !isLoading && eligible.length > 0 && <section aria-label="Bulk application actions" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" aria-label="Select all reviewable signups" checked={bulkAll || allChecked}
            ref={node => { if (node) node.indeterminate = !allChecked && eligible.some(item => checkedIds.includes(item.id)); }}
            disabled={busy} onChange={event => { setBulkAll(false); setCheckedIds(event.target.checked ? eligible.map(item => item.id) : []); }} />
          Select all shown ({eligible.length})
        </label>
        <span className="text-sm" role="status">{bulkAll ? intake?.reviewable_total : checkedApplications.length} selected</span>
        <Button disabled={(!checkedApplications.length && !bulkAll) || busy} onClick={() => openBulkReview("Approved")}>Approve selected</Button>
        <Button variant="outline" disabled={(!checkedApplications.length && !bulkAll) || busy} onClick={() => openBulkReview("Rejected")}>Reject selected</Button>
        <Button variant="outline" disabled={(!checkedApplications.length && !bulkAll) || busy} onClick={() => openBulkReview("Correction Requested")}>Request corrections for selected</Button>
        {!bulkAll && <Button variant="outline" disabled={busy} onClick={() => { setBulkAll(true); setCheckedIds([]); }}>Select all {intake?.reviewable_total} matching reviewable applications</Button>}
        {(checkedIds.length > 0 || bulkAll) && <Button variant="ghost" disabled={busy} onClick={() => { setCheckedIds([]); setBulkAll(false); }}>Clear selection</Button>}
      </section>}
      <div className="flex flex-wrap items-center gap-3"><span>{intake?.total || 0} matching applications · Page {intakePage}</span>
        <Button variant="outline" disabled={intakePage === 1 || busy} onClick={() => { setIntakePage(p => p - 1); setCheckedIds([]); setSelected(undefined); }}>Previous</Button>
        <Button variant="outline" disabled={!intake || intakePage * 50 >= intake.total || busy} onClick={() => { setIntakePage(p => p + 1); setCheckedIds([]); setSelected(undefined); }}>Next</Button></div>
      {!!intakeJobs?.items.length && <section className="rounded-xl border bg-card p-4 space-y-3" aria-label="Intake operations"><h2 className="font-semibold">Intake operations</h2>
        {intakeJobs.items.map((job: Row) => <div key={job.id} className="space-y-2"><div className="flex flex-wrap items-center gap-3"><strong>#{job.id} · {job.status}</strong><span>{job.cursor}/{job.total} processed · {job.result?.succeeded || 0} succeeded · {job.result?.failed_count || 0} failed</span>
          {job.status !== "Completed" && <Button variant="outline" disabled={busy} onClick={async () => { try { await api.post(`/interns-hub/admin/application-jobs/${job.id}/continue`); refreshApplications(); void qc.invalidateQueries({ queryKey: ["intake-jobs"] }); } catch (error) { toast({ title: "Could not continue intake", description: reviewError(error), variant: "destructive" }); } }}>Process next chunk</Button>}</div>
          {job.error && <p role="alert" className="text-destructive">{job.error}</p>}
          {!!job.result?.failed_count && <IntakeJobErrors jobId={job.id} total={job.result.failed_count} />}
        </div>)}<p className="text-xs text-muted-foreground">You can leave this page. Scheduled processing resumes pending operations; you can also process the next chunk here.</p></section>}
      {bulkResult && <section className="rounded-xl border bg-card p-4" aria-label="Bulk review results">
        <p role="status">{bulkResult.succeeded} application(s) updated. {bulkResult.failed.length} failed.</p>
        {bulkResult.failed.length > 0 && <><p className="mt-2 text-sm text-muted-foreground">Successful applications have been removed from the selection. Review these errors before retrying.</p>
          <ul className="mt-2 space-y-1 text-sm text-destructive">{bulkResult.failed.map(item => <li key={item.id}><strong>{item.name}:</strong> {item.message}</li>)}</ul></>}
      </section>}
      <Dialog open={!!bulkReview} onOpenChange={open => { if (!open && !bulkMutation.isPending) setBulkReview(null); }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{bulkReview?.status === "Approved" ? "Approve selected interns" : bulkReview?.status === "Rejected" ? "Reject selected applications" : "Request corrections for selected applications"}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">This will update {bulkAll ? intake?.reviewable_total : bulkReview?.ids.length || 0} selected application(s). {bulkReview?.status === "Approved" ? "The same branch, department, designation, manager and joining date will apply to everyone selected." : "The reason or instructions below will apply to every selected applicant."}</p>
          <form onSubmit={event => {
            event.preventDefault();
            if (bulkReview && (bulkReview.status === "Approved" || bulkDecision.review_note.trim())) bulkMutation.mutate({ ...bulkReview, values: { ...bulkDecision } });
          }}>
            <fieldset disabled={bulkMutation.isPending} className="grid gap-4 sm:grid-cols-2">
              <DecisionFields decision={bulkDecision} setDecision={setBulkDecision} options={options} prefix="bulk-review" approval={bulkReview?.status === "Approved"} requireReason={bulkReview?.status !== "Approved"} />
              <div className="flex flex-wrap justify-end gap-3 sm:col-span-2">
                <Button type="button" variant="outline" onClick={() => setBulkReview(null)}>Cancel</Button>
                <Button type="submit" disabled={bulkReview?.status !== "Approved" && !bulkDecision.review_note.trim()}>{bulkReview?.status === "Approved" ? "Approve & onboard selected" : bulkReview?.status === "Rejected" ? "Confirm rejection" : "Send correction requests"}</Button>
              </div>
            </fieldset>
            {bulkMutation.isPending && <p role="status" className="mt-3 text-sm">Starting a resumable intake operation. Progress will be saved on the server.</p>}
          </form>
        </DialogContent>
      </Dialog>
      {error ? (
        <p role="alert" className="text-destructive">
          HRMS recruitment permission is required to review applications.
        </p>
      ) : isLoading ? (
        <p>Loading applications…</p>
      ) : !list.length ? (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            No {filter.toLowerCase()} applications{search ? " match your search" : " yet"}. Applications submitted
            from the public Interns Hub page will appear here.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div className="space-y-3">
            {list.map((item) => (
              <div key={item.id} className="rounded-xl border bg-card">
                <label className="flex items-center gap-2 px-4 pt-3 text-xs text-muted-foreground">
                  <input type="checkbox" aria-label={`Select ${item.full_name}`} checked={reviewable(item) && checkedIds.includes(item.id)} disabled={!reviewable(item) || busy}
                    onChange={event => setCheckedIds(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))} />
                  {reviewable(item) ? "Select for bulk review" : "Already reviewed"}
                </label>
              <button
                type="button"
                disabled={busy}
                className={`w-full rounded-xl p-4 text-left ${item.id === application?.id ? "border-primary ring-1 ring-primary" : ""}`}
                onClick={() => {
                  setSelected(item.id);
                  setDecision({
                    ...decision,
                    date_of_joining: item.details.available_from,
                    review_note: "",
                  });
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <b className="text-sm">{item.full_name}</b>
                  <Badge variant="outline">{item.status}</Badge>
                </div>
                <p className="mt-1 break-all text-xs text-muted-foreground">
                  {item.email}
                </p>
                <p className="mt-3 text-xs">{item.details.role}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.reference}
                </p>
              </button>
              </div>
            ))}
          </div>
          {application && (
            <div className="space-y-5">
              <Card>
                <CardHeader>
                  <CardTitle>{application.full_name}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {application.email} · {application.reference}
                  </p>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                    {Object.entries(labels).map(([key, label]) => (
                      <div key={key}>
                        <dt className="text-xs text-muted-foreground">
                          {label}
                        </dt>
                        <dd className="mt-1 break-words text-sm">
                          {application.details[key] ?? "—"}
                        </dd>
                      </div>
                    ))}
                    <div>
                      <dt className="text-xs text-muted-foreground">
                        ID Number
                      </dt>
                      <dd className="mt-1 text-sm">
                        •••• {application.identity_last4}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
              {["Pending","Correction Requested"].includes(application.status) ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Approve this intern</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <form
                      className="grid gap-4 sm:grid-cols-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        mutation.mutate("Approved");
                      }}
                    >
                      <DecisionFields decision={decision} setDecision={setDecision} options={options} prefix="approval" />
                      <div className="flex flex-wrap justify-end gap-3 sm:col-span-2">
                        <Button
                          type="button"
                          variant="outline"
                          disabled={busy}
                          onClick={() => mutation.mutate("Rejected")}
                        >
                          Reject Application
                        </Button>
                        <Button type="button" variant="outline" disabled={busy} onClick={()=>mutation.mutate("Correction Requested")}>Request Corrections</Button>
                        <Button disabled={busy}>
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                          Approve & Onboard
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground sm:col-span-2">
                        Approval creates an HRMS employee, restricted intern
                        account and unique intern ID. No résumé or document
                        upload is required.
                      </p>
                    </form>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="pt-6">
                    <Badge variant="outline">{application.status}</Badge>
                    {application.intern_id && (
                      <p className="mt-3 font-semibold">
                        Intern ID: {application.intern_id}
                      </p>
                    )}
                    {application.review_note && (
                      <p className="mt-3 text-sm">{application.review_note}</p>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
