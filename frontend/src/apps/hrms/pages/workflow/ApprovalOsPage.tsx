import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, FileCheck2, History, Inbox, RefreshCw, Smartphone, Sparkles, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";
import { formatDateTime } from "@/lib/utils";
import { getRoleKey } from "@/lib/roles";
import { approvalOsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

type ApprovalItem = {
  id: string;
  source: string;
  source_module: string;
  approval_type: string;
  entity_type: string;
  entity_id: number;
  title: string;
  description?: string | null;
  requester_user_id?: number | null;
  assigned_to_user_id?: number | null;
  assigned_role?: string | null;
  priority: string;
  status: string;
  sla_due_at?: string | null;
  submitted_at?: string | null;
  escalated_at?: string | null;
  ai_summary?: string | null;
  mobile_enabled: boolean;
  action_url: string;
  can_decide: boolean;
};

type ApprovalInbox = {
  summary: {
    total: number;
    pending: number;
    overdue: number;
    escalated: number;
    high_priority: number;
    by_module: Record<string, number>;
    by_type: Record<string, number>;
  };
  items: ApprovalItem[];
};

function toneForStatus(status: string) {
  const value = status.toLowerCase();
  if (value === "approved" || value === "completed") return "bg-green-100 text-green-800";
  if (value === "rejected") return "bg-red-100 text-red-800";
  if (value === "pending") return "bg-amber-100 text-amber-800";
  return "bg-muted text-muted-foreground";
}

function nativeApprovalId(item: ApprovalItem) {
  return item.id.startsWith("approval:") ? Number(item.id.split(":")[1]) : null;
}

export default function ApprovalOsPage() {
  usePageTitle("Approval OS");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const [scope, setScope] = useState<"mine" | "all" | "submitted">(roleKey === "employee" ? "submitted" : "mine");
  const [status, setStatus] = useState("Pending");
  const [module, setModule] = useState("");
  const [reasonById, setReasonById] = useState<Record<string, string>>({});

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["approval-os", scope, status, module],
    queryFn: () =>
      approvalOsApi.inbox({
        scope,
        status: status || undefined,
        module: module || undefined,
      }).then((response) => response.data as ApprovalInbox),
  });

  const decide = useMutation({
    mutationFn: ({ item, decision }: { item: ApprovalItem; decision: "approve" | "reject" }) => {
      const id = nativeApprovalId(item);
      if (!id) throw new Error("Workflow-engine approvals should be opened from Workflow Inbox.");
      const payload = { reason: reasonById[item.id] || undefined };
      return decision === "approve" ? approvalOsApi.approve(id, payload) : approvalOsApi.reject(id, payload);
    },
    onSuccess: () => {
      toast({ title: "Approval decision recorded" });
      qc.invalidateQueries({ queryKey: ["approval-os"] });
    },
    onError: (error: Error) => toast({ title: error.message || "Unable to decide approval", variant: "destructive" }),
  });

  const summary = data?.summary;
  const moduleRows = useMemo(() => Object.entries(summary?.by_module || {}), [summary]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-muted-foreground">Business Operating System</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Approval OS</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            One decision queue for CRM, PMS, HRMS, Finance, AI, and system approvals with SLA, escalation, comments, audit, and mobile readiness.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant={scope === "mine" ? "default" : "outline"} onClick={() => setScope("mine")}>Assigned to me</Button>
          <Button variant={scope === "submitted" ? "default" : "outline"} onClick={() => setScope("submitted")}>Submitted by me</Button>
          {roleKey !== "employee" ? <Button variant={scope === "all" ? "default" : "outline"} onClick={() => setScope("all")}>All</Button> : null}
          <Button variant="outline" onClick={() => refetch()}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <Metric icon={Inbox} label="Total" value={isLoading ? "-" : summary?.total ?? 0} />
        <Metric icon={Clock3} label="Pending" value={isLoading ? "-" : summary?.pending ?? 0} />
        <Metric icon={AlertTriangle} label="Overdue SLA" value={isLoading ? "-" : summary?.overdue ?? 0} />
        <Metric icon={History} label="Escalated" value={isLoading ? "-" : summary?.escalated ?? 0} />
        <Metric icon={FileCheck2} label="High Priority" value={isLoading ? "-" : summary?.high_priority ?? 0} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.78fr_1.22fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Control Plane</CardTitle>
            <CardDescription>Filter by module and status.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                {["Pending", "Approved", "Rejected", ""].map((item) => <option key={item} value={item}>{item || "Any status"}</option>)}
              </select>
              <Input value={module} onChange={(event) => setModule(event.target.value)} placeholder="Module: crm, pms, hrms" />
            </div>
            <div className="space-y-2">
              {moduleRows.length ? moduleRows.map(([name, count]) => (
                <div key={name} className="flex items-center justify-between rounded-md border p-3">
                  <span className="text-sm font-medium capitalize">{name}</span>
                  <Badge variant="outline">{count}</Badge>
                </div>
              )) : <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">No module mix for this filter.</p>}
            </div>
            <div className="grid gap-3">
              <Control icon={Sparkles} title="AI summaries" detail="Each request can carry an evidence-backed decision summary." />
              <Control icon={Smartphone} title="Mobile approvals" detail="Approval items expose mobile readiness and compact decision data." />
              <Control icon={History} title="Audit history" detail="Native Approval OS decisions write immutable history entries." />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Unified Inbox</CardTitle>
            <CardDescription>Native Approval OS records plus workflow-engine approvals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? <div className="h-32 rounded-lg border bg-muted/30" /> : null}
            {!isLoading && data?.items.map((item) => {
              const id = nativeApprovalId(item);
              const overdue = item.sla_due_at ? new Date(item.sla_due_at).getTime() < Date.now() && item.status.toLowerCase() === "pending" : false;
              return (
                <div key={item.id} className="rounded-lg border p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold">{item.title}</p>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneForStatus(item.status)}`}>{item.status}</span>
                        {item.priority.toLowerCase() !== "normal" ? <Badge variant={item.priority.toLowerCase() === "high" ? "destructive" : "outline"}>{item.priority}</Badge> : null}
                        {overdue ? <Badge variant="destructive">SLA overdue</Badge> : null}
                        {!id ? <Badge variant="outline">Workflow engine</Badge> : null}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {item.source_module} / {item.approval_type} / {item.entity_type} #{item.entity_id}
                      </p>
                      {item.ai_summary ? <p className="mt-3 rounded-md border bg-muted/30 p-3 text-sm">{item.ai_summary}</p> : null}
                      <p className="mt-2 text-xs text-muted-foreground">
                        Submitted {formatDateTime(item.submitted_at || null)}
                        {item.sla_due_at ? ` - SLA ${formatDateTime(item.sla_due_at)}` : ""}
                        {item.assigned_role ? ` - Role ${item.assigned_role}` : ""}
                      </p>
                    </div>
                    {item.can_decide && id ? (
                      <div className="flex min-w-[240px] flex-col gap-2">
                        <Input
                          value={reasonById[item.id] || ""}
                          onChange={(event) => setReasonById({ ...reasonById, [item.id]: event.target.value })}
                          placeholder="Decision note"
                        />
                        <div className="flex gap-2">
                          <Button size="sm" className="flex-1" onClick={() => decide.mutate({ item, decision: "approve" })} disabled={decide.isPending}>
                            <CheckCircle2 className="mr-2 h-4 w-4" />Approve
                          </Button>
                          <Button size="sm" variant="outline" className="flex-1" onClick={() => decide.mutate({ item, decision: "reject" })} disabled={decide.isPending}>
                            <XCircle className="mr-2 h-4 w-4" />Reject
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                        {id ? "View only" : "Open Workflow Inbox to decide"}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {!isLoading && !data?.items.length ? <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No approvals match this view.</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <Icon className="mb-3 h-5 w-5 text-primary" />
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

function Control({ icon: Icon, title, detail }: { icon: React.ElementType; title: string; detail: string }) {
  return (
    <div className="flex gap-3 rounded-md border p-3">
      <Icon className="mt-0.5 h-4 w-4 text-primary" />
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}
