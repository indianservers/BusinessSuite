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
import { toast } from "@/hooks/use-toast";
import InternApplicationSettings from "./InternApplicationSettings";
type Row = Record<string, any>;
const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
export default function InternApplicationsPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number>();
  const [filter, setFilter] = useState("Pending");
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
  const list = applications.filter((a) => !filter || a.status === filter);
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
      toast({
        title:
          r.data.status === "Approved"
            ? `Application approved · ${r.data.intern_id}`
            : "Application rejected",
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
          Intern Applications
        </h1>
        <p className="page-description">
          Review applications and activate approved interns in the same HRMS.
        </p>
      </div>
      <InternApplicationSettings />
      <div className="flex flex-wrap gap-2">
        <Link to="/hrms/interns/profiles" className="inline-flex items-center rounded-md border px-3 py-2 text-sm">Manage connected profiles</Link>
        {["Pending", "Correction Requested", "Approved", "Rejected", ""].map((status) => (
          <Button
            key={status}
            variant={filter === status ? "default" : "outline"}
            onClick={() => {
              setFilter(status);
              setSelected(undefined);
            }}
          >
            {status || "All Applications"} (
            {applications.filter((a) => !status || a.status === status).length})
          </Button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-destructive">
          HRMS recruitment permission is required to review applications.
        </p>
      ) : isLoading ? (
        <p>Loading applications…</p>
      ) : !list.length ? (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            No {filter.toLowerCase()} applications yet. Applications submitted
            from the public Interns Hub page will appear here.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div className="space-y-3">
            {list.map((item) => (
              <button
                key={item.id}
                className={`w-full rounded-xl border bg-card p-4 text-left ${item.id === application?.id ? "border-primary ring-1 ring-primary" : ""}`}
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
                    <CardTitle>Review & Activate Account</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <form
                      className="grid gap-4 sm:grid-cols-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        mutation.mutate("Approved");
                      }}
                    >
                      <div>
                        <Label htmlFor="approval-branch">Branch *</Label>
                        <select
                          id="approval-branch"
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
                        <Label htmlFor="approval-department">
                          Department *
                        </Label>
                        <select
                          id="approval-department"
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
                        <Label htmlFor="approval-designation">
                          Designation *
                        </Label>
                        <select
                          id="approval-designation"
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
                        <Label htmlFor="approval-manager">
                          Reporting Manager *
                        </Label>
                        <select
                          id="approval-manager"
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
                        <Label htmlFor="approval-date">Joining Date *</Label>
                        <Input
                          id="approval-date"
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
                      <div className="sm:col-span-2">
                        <Label htmlFor="approval-note">Note to Applicant</Label>
                        <textarea
                          id="approval-note"
                          className={selectClass + " h-auto py-2"}
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
                      <div className="flex flex-wrap justify-end gap-3 sm:col-span-2">
                        <Button
                          type="button"
                          variant="outline"
                          disabled={mutation.isPending}
                          onClick={() => mutation.mutate("Rejected")}
                        >
                          Reject Application
                        </Button>
                        <Button type="button" variant="outline" disabled={mutation.isPending} onClick={()=>mutation.mutate("Correction Requested")}>Request Corrections</Button>
                        <Button disabled={mutation.isPending}>
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
