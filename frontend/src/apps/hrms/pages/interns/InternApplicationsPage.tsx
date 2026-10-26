import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, UserPlus, ArrowLeft } from "lucide-react";
import { api, companyApi, employeeApi } from "@/services/api";
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
} : { status, review_note: values.review_note };
const reviewError = (error: any) => typeof error.response?.data?.detail === "string" ? error.response.data.detail : "Could not update this application. Please refresh and retry.";

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
              {m.first_name} {m.last_name} ({m.employee_id})
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
  const [bulkProgress, setBulkProgress] = useState(0);
  const [bulkResult, setBulkResult] = useState<{ succeeded: number; failed: { id: number; name: string; message: string }[] } | null>(null);
  const [decision, setDecision] = useState<Row>({
    branch_id: "",
    department_id: "",
    designation_id: "",
    reporting_manager_id: "",
    date_of_joining: new Date().toLocaleDateString("en-CA"),
    review_note: "",
  });
  const {
    data: applications = [],
    isLoading,
    error,
  } = useQuery<Row[]>({
    queryKey: ["intern-applications"],
    queryFn: () =>
      api.get("/interns-hub/admin/applications").then((r) => r.data),
  });
  const { data: options } = useQuery({
    queryKey: ["intern-application-organization"],
    queryFn: async () => {
      const [branches, departments, designations] = await Promise.all([
        companyApi.listBranches(),
        companyApi.listDepartments(),
        companyApi.listDesignations(),
      ]);
      const managers: Row[] = [];
      let page = 1;
      while (true) {
        const { data } = await employeeApi.list({
          page,
          per_page: 100,
          status: "Active",
        });
        managers.push(
          ...data.items.filter(
            (e: Row) => (e.employment_type || "").toLowerCase() !== "intern",
          ),
        );
        if (
          !data.items.length ||
          page * 100 >= data.total ||
          data.items.length < 100
        )
          break;
        page++;
      }
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
    mutationFn: (status: string) =>
      api.post(`/interns-hub/admin/applications/${application.id}/decision`, {
        status,
        ...Object.fromEntries(
          Object.entries(decision).map(([k, v]) => [
            k,
            k.endsWith("_id") ? Number(v) || null : v,
          ]),
        ),
      }),
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
      const failed: { id: number; name: string; message: string }[] = [];
      let succeeded = 0;
      setBulkProgress(0);
      for (const id of ids) {
        try {
          await api.post(`/interns-hub/admin/applications/${id}/decision`, decisionBody(status, values));
          succeeded++;
        } catch (error) {
          failed.push({ id, name: applications.find(item => item.id === id)?.full_name || `Application #${id}`, message: reviewError(error) });
        }
        setBulkProgress(succeeded + failed.length);
      }
      return { succeeded, failed };
    },
    onSuccess: result => {
      setBulkResult(result);
      setCheckedIds(result.failed.map(item => item.id));
      setBulkReview(null);
      refreshApplications();
      toast({ title: `${result.succeeded} application(s) updated${result.failed.length ? `, ${result.failed.length} failed` : ""}`, variant: result.failed.length ? "destructive" : "default" });
    },
  });
  const busy = mutation.isPending || bulkMutation.isPending;
  const openBulkReview = (status: DecisionStatus) => {
    setBulkDecision(newDecision());
    setBulkProgress(0);
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
      <Input aria-label="Search signups" placeholder="Search signups by name, email or reference…" value={search} onChange={(event) => { setSearch(event.target.value); setSelected(undefined); setCheckedIds([]); }} />
      <div className="flex flex-wrap gap-2">
        <Link to="/hrms/interns/profiles" className="inline-flex items-center rounded-md border px-3 py-2 text-sm">Manage connected profiles</Link>
        {["Pending", "Correction Requested", "Approved", "Rejected", ""].map((status) => (
          <Button
            key={status}
            variant={filter === status ? "default" : "outline"}
            onClick={() => {
              setFilter(status);
              setSelected(undefined);
              setCheckedIds([]);
            }}
          >
            {status || "All Applications"} (
            {applications.filter((a) => !status || a.status === status).length})
          </Button>
        ))}
      </div>
      {!error && !isLoading && eligible.length > 0 && <section aria-label="Bulk application actions" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" aria-label="Select all reviewable signups" checked={allChecked}
            ref={node => { if (node) node.indeterminate = !allChecked && eligible.some(item => checkedIds.includes(item.id)); }}
            disabled={busy} onChange={event => setCheckedIds(event.target.checked ? eligible.map(item => item.id) : [])} />
          Select all shown ({eligible.length})
        </label>
        <span className="text-sm" role="status">{checkedApplications.length} selected</span>
        <Button disabled={!checkedApplications.length || busy} onClick={() => openBulkReview("Approved")}>Approve selected</Button>
        <Button variant="outline" disabled={!checkedApplications.length || busy} onClick={() => openBulkReview("Rejected")}>Reject selected</Button>
        <Button variant="outline" disabled={!checkedApplications.length || busy} onClick={() => openBulkReview("Correction Requested")}>Request corrections for selected</Button>
        {checkedIds.length > 0 && <Button variant="ghost" disabled={busy} onClick={() => setCheckedIds([])}>Clear selection</Button>}
      </section>}
      {bulkResult && <section className="rounded-xl border bg-card p-4" aria-label="Bulk review results">
        <p role="status">{bulkResult.succeeded} application(s) updated. {bulkResult.failed.length} failed.</p>
        {bulkResult.failed.length > 0 && <><p className="mt-2 text-sm text-muted-foreground">Successful applications have been removed from the selection. Review these errors before retrying.</p>
          <ul className="mt-2 space-y-1 text-sm text-destructive">{bulkResult.failed.map(item => <li key={item.id}><strong>{item.name}:</strong> {item.message}</li>)}</ul></>}
      </section>}
      <Dialog open={!!bulkReview} onOpenChange={open => { if (!open && !bulkMutation.isPending) setBulkReview(null); }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{bulkReview?.status === "Approved" ? "Approve selected interns" : bulkReview?.status === "Rejected" ? "Reject selected applications" : "Request corrections for selected applications"}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">This will update {bulkReview?.ids.length || 0} selected application(s). {bulkReview?.status === "Approved" ? "The same branch, department, designation, manager and joining date will apply to everyone selected." : "The reason or instructions below will apply to every selected applicant."}</p>
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
            {bulkMutation.isPending && <p role="status" className="mt-3 text-sm">Processing {bulkProgress} of {bulkReview?.ids.length} applications. Keep this page open.</p>}
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
