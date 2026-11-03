import { NativeSelect } from "@/components/ui/native-select";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Clock3, FileCheck2, GitBranch, History, Inbox, Plus, ReceiptText, Save, ShieldCheck, Trash2, UserCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { getRoleKey } from "@/lib/roles";
import { formatDateTime } from "@/lib/utils";
import { workflowApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { useAuthStore } from "@/store/authStore";
import { NOTIF_UNREAD_KEY } from "@/components/layout/Topbar";

type WorkflowItem = {
  id: string;
  source: string;
  source_id: number;
  title: string;
  requester_name?: string | null;
  status: string;
  priority: string;
  submitted_at?: string | null;
  action_url: string;
  action_label: string;
  role_scope: string;
};

type WorkflowSummary = {
  total: number;
  pending_action: number;
  submitted_by_me: number;
  by_source: Record<string, number>;
  items: WorkflowItem[];
};

type WorkflowStep = {
  step_order: number;
  step_type: string;
  approver_type: string;
  approver_value: string;
  condition_expression: string;
  timeout_hours: string;
  escalation_user_id: string;
  delegation_role: string;
  audit_note: string;
  is_required: boolean;
};

type WorkflowDefinition = {
  id: number;
  name: string;
  module: string;
  trigger_event: string;
  description?: string;
  is_active: boolean;
  steps?: WorkflowStep[];
};

const sourceIcon: Record<string, React.ElementType> = {
  leave: Clock3,
  timesheet: FileCheck2,
  attendance: CheckCircle2,
  reimbursement: ReceiptText,
  payroll: ReceiptText,
};

const blankStep = (order: number): WorkflowStep => ({
  step_order: order,
  step_type: "Approval",
  approver_type: "Role",
  approver_value: "hr",
  condition_expression: "",
  timeout_hours: "24",
  escalation_user_id: "",
  delegation_role: "",
  audit_note: "",
  is_required: true,
});

function statusTone(status: string) {
  if (["Approved", "Locked", "Paid"].includes(status)) return "bg-green-100 text-green-800";
  if (["Rejected", "Cancelled"].includes(status)) return "bg-red-100 text-red-800";
  if (["Completed", "Submitted", "Pending"].includes(status)) return "bg-amber-100 text-amber-800";
  return "bg-muted text-muted-foreground";
}

function hrmsActionUrl(url: string) {
  if (url.startsWith("/hrms")) return url;
  if (url.startsWith("/crm") || url.startsWith("/pms")) return "/hrms";
  return url.startsWith("/") ? `/hrms${url}` : `/hrms/${url}`;
}

export default function WorkflowInboxPage() {
  usePageTitle("Workflow Inbox");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const [mine, setMine] = useState(roleKey === "employee");
  const [view, setView] = useState<"queue" | "designer">("queue");
  const [definitionForm, setDefinitionForm] = useState({
    name: "",
    module: "leave",
    trigger_event: "leave_submitted",
    description: "",
  });
  const [steps, setSteps] = useState<WorkflowStep[]>([blankStep(1)]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["workflow-inbox", mine],
    queryFn: () => workflowApi.inbox(mine).then((response) => response.data as WorkflowSummary),
  });

  const { data: definitions } = useQuery({
    queryKey: ["workflow-definitions"],
    queryFn: () => workflowApi.definitions().then((response) => response.data as WorkflowDefinition[]),
    retry: false,
  });

  const createDefinition = useMutation({
    mutationFn: () =>
      workflowApi.createDefinition({
        ...definitionForm,
        steps: steps.map((step, index) => ({
          step_order: index + 1,
          step_type: step.step_type,
          approver_type: step.approver_type,
          approver_value: step.approver_value || null,
          condition_expression: step.condition_expression || null,
          timeout_hours: step.timeout_hours ? Number(step.timeout_hours) : null,
          escalation_user_id: step.escalation_user_id ? Number(step.escalation_user_id) : null,
          is_required: step.is_required,
        })),
      }),
    onSuccess: () => {
      toast({ title: "Workflow definition saved" });
      setDefinitionForm({ name: "", module: "leave", trigger_event: "leave_submitted", description: "" });
      setSteps([blankStep(1)]);
      qc.invalidateQueries({ queryKey: ["workflow-definitions"] });
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
    },
    onError: () => toast({ title: "Unable to save workflow", variant: "destructive" }),
  });

  const sourceRows = useMemo(() => Object.entries(data?.by_source || {}), [data]);

  const addStep = () => setSteps((current) => [...current, blankStep(current.length + 1)]);
  const updateStep = (index: number, patch: Partial<WorkflowStep>) => {
    setSteps((current) => current.map((step, stepIndex) => stepIndex === index ? { ...step, ...patch } : step));
  };
  const removeStep = (index: number) => {
    setSteps((current) => current.filter((_, stepIndex) => stepIndex !== index).map((step, stepIndex) => ({ ...step, step_order: stepIndex + 1 })));
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {view === "designer" ? "Workflow automation" : roleKey === "employee" ? "Employee self service" : "Approvals"}
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            {view === "designer" ? "Workflow designer" : roleKey === "employee" ? "My requests" : "Workflow inbox"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {view === "designer"
              ? "Build approval flows for leave, payroll, attendance, documents, onboarding, and helpdesk."
              : roleKey === "employee"
                ? "Track leave, timesheets, reimbursements, and submitted HR requests."
                : "Review leave, timesheets, attendance, reimbursements, and payroll actions from one queue."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant={view === "queue" ? "default" : "outline"} onClick={() => setView("queue")}>
            <Inbox className="mr-2 h-4 w-4" />
            Queue
          </Button>
          {roleKey !== "employee" && (
            <Button variant={view === "designer" ? "default" : "outline"} onClick={() => setView("designer")}>
              <GitBranch className="mr-2 h-4 w-4" />
              Designer
            </Button>
          )}
          {view === "queue" && roleKey !== "employee" && (
            <Button variant={mine ? "outline" : "default"} onClick={() => setMine(false)}>Team queue</Button>
          )}
          {view === "queue" && <Button variant={mine ? "default" : "outline"} onClick={() => setMine(true)}>My submissions</Button>}
          {view === "queue" && <Button variant="outline" onClick={() => refetch()}>Refresh</Button>}
        </div>
      </div>

      {view === "queue" ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card><CardContent className="p-5"><Inbox className="mb-3 h-5 w-5 text-primary" /><p className="text-2xl font-semibold">{isLoading ? "-" : data?.total ?? 0}</p><p className="text-sm text-muted-foreground">Total items</p></CardContent></Card>
            <Card><CardContent className="p-5"><Clock3 className="mb-3 h-5 w-5 text-amber-600" /><p className="text-2xl font-semibold">{isLoading ? "-" : data?.pending_action ?? 0}</p><p className="text-sm text-muted-foreground">Pending action</p></CardContent></Card>
            <Card><CardContent className="p-5"><FileCheck2 className="mb-3 h-5 w-5 text-green-600" /><p className="text-2xl font-semibold">{isLoading ? "-" : data?.submitted_by_me ?? 0}</p><p className="text-sm text-muted-foreground">Submitted by me</p></CardContent></Card>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <WorkflowControlCard icon={ShieldCheck} title="Multi-level approvals" detail="Sequential, conditional, and role-based steps are tracked per request." />
            <WorkflowControlCard icon={UserCheck} title="Delegation ready" detail="Approver delegation and backup roles are visible before handoff." />
            <WorkflowControlCard icon={History} title="Audit trail" detail="Every submission, approval, escalation, timeout, and rejection is audit-ready." />
          </div>

          <div className="grid gap-5 lg:grid-cols-[0.75fr_1.25fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Queue Mix</CardTitle>
                <CardDescription>Grouped by workflow source</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {sourceRows.length === 0 ? <p className="text-sm text-muted-foreground">No active workflow items.</p> : sourceRows.map(([source, count]) => {
                  const Icon = sourceIcon[source] || Inbox;
                  return (
                    <div key={source} className="flex items-center justify-between rounded-lg border p-3">
                      <span className="flex items-center gap-3 text-sm font-medium capitalize"><Icon className="h-4 w-4 text-primary" />{source}</span>
                      <Badge variant="outline">{count}</Badge>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Items</CardTitle>
                <CardDescription>{mine ? "Your submitted requests" : "Requests waiting for review"}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {isLoading ? (
                  <div className="h-24 rounded-lg border bg-muted/30" />
                ) : data?.items.length ? data.items.map((item) => {
                  const Icon = sourceIcon[item.source] || Inbox;
                  return (
                    <div key={item.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium">{item.title}</p>
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusTone(item.status)}`}>{item.status}</span>
                            {item.priority === "High" && <Badge variant="destructive">High</Badge>}
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">{item.requester_name || "System"} - {formatDateTime(item.submitted_at || null)}</p>
                        </div>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link to={hrmsActionUrl(item.action_url)}>{item.action_label}<ArrowRight className="ml-2 h-4 w-4" /></Link>
                      </Button>
                    </div>
                  );
                }) : <p className="rounded-lg border p-4 text-sm text-muted-foreground">No workflow items found.</p>}
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create Workflow</CardTitle>
              <CardDescription>Use simple conditions like days_count &gt; 3 or amount &gt; 10000.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Name</Label>
                  <Input value={definitionForm.name} onChange={(e) => setDefinitionForm({ ...definitionForm, name: e.target.value })} placeholder="Leave approval - India" />
                </div>
                <div className="space-y-1.5">
                  <Label>Module</Label>
                  <NativeSelect className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={definitionForm.module} onChange={(e) => setDefinitionForm({ ...definitionForm, module: e.target.value })}>
                    {["leave", "payroll", "attendance", "documents", "onboarding", "helpdesk", "reimbursement"].map((module) => <option key={module}>{module}</option>)}
                  </NativeSelect>
                </div>
                <div className="space-y-1.5">
                  <Label>Trigger Event</Label>
                  <Input value={definitionForm.trigger_event} onChange={(e) => setDefinitionForm({ ...definitionForm, trigger_event: e.target.value })} placeholder="leave_submitted" />
                </div>
                <div className="space-y-1.5">
                  <Label>Description</Label>
                  <Input value={definitionForm.description} onChange={(e) => setDefinitionForm({ ...definitionForm, description: e.target.value })} />
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">Approval Steps</p>
                  <Button variant="outline" size="sm" onClick={addStep}><Plus className="mr-2 h-4 w-4" />Add Step</Button>
                </div>
                {steps.map((step, index) => (
                  <div key={index} className="rounded-lg border p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <Badge variant="outline">Step {index + 1}</Badge>
                      {steps.length > 1 && <Button variant="ghost" size="icon" onClick={() => removeStep(index)}><Trash2 className="h-4 w-4" /></Button>}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label>Approver Type</Label>
                        <NativeSelect className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={step.approver_type} onChange={(e) => updateStep(index, { approver_type: e.target.value })}>
                          {["Role", "User"].map((type) => <option key={type}>{type}</option>)}
                        </NativeSelect>
                      </div>
                      <div className="space-y-1.5">
                        <Label>Approver Value</Label>
                        <Input value={step.approver_value} onChange={(e) => updateStep(index, { approver_value: e.target.value })} placeholder="hr or user ID" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Condition</Label>
                        <Input value={step.condition_expression} onChange={(e) => updateStep(index, { condition_expression: e.target.value })} placeholder="days_count > 3" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Delegation Role</Label>
                        <Input value={step.delegation_role} onChange={(e) => updateStep(index, { delegation_role: e.target.value })} placeholder="backup_hr_manager" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <Label>Timeout Hrs</Label>
                          <Input type="number" value={step.timeout_hours} onChange={(e) => updateStep(index, { timeout_hours: e.target.value })} />
                        </div>
                        <div className="space-y-1.5">
                          <Label>Escalate User ID</Label>
                          <Input type="number" value={step.escalation_user_id} onChange={(e) => updateStep(index, { escalation_user_id: e.target.value })} />
                        </div>
                      </div>
                      <div className="space-y-1.5 sm:col-span-2">
                        <Label>Audit Note</Label>
                        <Input value={step.audit_note} onChange={(e) => updateStep(index, { audit_note: e.target.value })} placeholder="Captured in approval audit trail" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <Card className="bg-muted/30">
                <CardContent className="grid gap-3 p-4 md:grid-cols-3">
                  {[
                    ["Condition examples", "days_count > 3, amount > 10000, department = Finance"],
                    ["Escalation policy", "Timeout escalates to user/role and marks request at risk."],
                    ["Delegation policy", "Backup role handles approvals during leave or out-of-office periods."],
                  ].map(([title, detail]) => (
                    <div key={title} className="rounded-md border bg-background p-3">
                      <p className="text-sm font-semibold">{title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Button disabled={!definitionForm.name || !definitionForm.trigger_event || createDefinition.isPending} onClick={() => createDefinition.mutate()}>
                <Save className="mr-2 h-4 w-4" />
                Save Workflow
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Active Definitions</CardTitle>
              <CardDescription>Live workflow rules grouped by module and trigger.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(definitions || []).map((definition) => (
                <div key={definition.id} className="rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{definition.name}</p>
                      <p className="text-sm text-muted-foreground">{definition.module} - {definition.trigger_event}</p>
                    </div>
                    <Badge variant={definition.is_active ? "default" : "outline"}>{definition.is_active ? "Active" : "Inactive"}</Badge>
                  </div>
                  <div className="mt-3 space-y-2">
                    {(definition.steps || []).map((step) => (
                      <div key={`${definition.id}-${step.step_order}`} className="rounded-md bg-muted/40 p-2 text-xs">
                        Step {step.step_order}: {step.approver_type} {step.approver_value || ""}
                        {step.condition_expression ? ` when ${step.condition_expression}` : ""}
                        {step.escalation_user_id ? `; escalates to ${step.escalation_user_id}` : ""}
                      </div>
                    ))}
                    {!definition.steps?.length && <p className="text-xs text-muted-foreground">No step details returned.</p>}
                  </div>
                </div>
              ))}
              {!definitions?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No workflow definitions configured yet.</p>}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function WorkflowControlCard({ icon: Icon, title, detail }: { icon: React.ElementType; title: string; detail: string }) {
  return (
    <Card>
      <CardContent className="flex gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
