import type React from "react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, GitBranch, Inbox, ListChecks, Play, RefreshCw, Send, ShieldCheck, Webhook, Zap } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { automationApi, type AutomationRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

type SectionKey = "workflows" | "blueprints" | "approvals" | "assignment-rules" | "cadences" | "webhooks" | "logs";

const sections: Array<{ key: SectionKey; label: string; icon: typeof Zap; path: string }> = [
  { key: "workflows", label: "Workflows", icon: Zap, path: "/admin/automation/workflows" },
  { key: "blueprints", label: "Blueprints", icon: GitBranch, path: "/admin/automation/blueprints" },
  { key: "approvals", label: "Approvals", icon: ShieldCheck, path: "/admin/automation/approvals" },
  { key: "assignment-rules", label: "Assignment Rules", icon: ListChecks, path: "/admin/automation/assignment-rules" },
  { key: "cadences", label: "Cadences", icon: Send, path: "/admin/automation/cadences" },
  { key: "webhooks", label: "Webhooks", icon: Webhook, path: "/admin/automation/webhooks" },
  { key: "logs", label: "Logs", icon: Inbox, path: "/admin/automation/logs" },
];

function sectionFromPath(pathname: string): SectionKey {
  return sections.find((item) => pathname.startsWith(item.path))?.key || "workflows";
}

function parseJson(value: string, fallback: unknown) {
  try {
    return value.trim() ? JSON.parse(value) : fallback;
  } catch {
    throw new Error("JSON is not valid");
  }
}

export default function AutomationStudioPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = sectionFromPath(location.pathname);
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">Admin</p>
          <h1 className="text-2xl font-semibold tracking-normal">Automation Studio</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">Reusable CRM, SRM, and PMS automation with JSON-only conditions, guarded actions, approvals, cadences, webhooks, and execution logs.</p>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {sections.map((item) => {
            const Icon = item.icon;
            return (
              <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}>
                <Icon className="h-4 w-4" />
                {item.label}
              </Button>
            );
          })}
        </div>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "workflows" ? <WorkflowSection /> : null}
        {active === "blueprints" ? <BlueprintSection /> : null}
        {active === "approvals" ? <ApprovalSection /> : null}
        {active === "assignment-rules" ? <AssignmentSection /> : null}
        {active === "cadences" ? <CadenceSection /> : null}
        {active === "webhooks" ? <WebhookSection /> : null}
        {active === "logs" ? <LogSection /> : null}
      </div>
    </div>
  );
}

function useRefresh(keys: string[]) {
  const qc = useQueryClient();
  return () => keys.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
}

function QueryState({ isLoading, isError, onRetry }: { isLoading: boolean; isError: boolean; onRetry: () => void }) {
  if (isLoading) return <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading automation data...</div>;
  if (isError) {
    return (
      <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
        <span>Automation data could not be loaded.</span>
        <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw className="h-4 w-4" />Retry</Button>
      </div>
    );
  }
  return null;
}

function RecordList({ items, empty }: { items?: AutomationRecord[]; empty: string }) {
  if (!items?.length) return <div className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">{empty}</div>;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((item) => (
        <Card key={String(item.id)}>
          <CardContent className="flex items-start justify-between gap-3 p-4">
            <div>
              <p className="font-medium">{String(item.name || item.module_name || item.record_type || `Record ${item.id}`)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{String(item.module_name || "automation")} / {String(item.record_type || item.trigger_type || item.status || "configured")}</p>
            </div>
            <Badge variant="outline">{String(item.status || (item.is_active ? "active" : "draft"))}</Badge>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <textarea className="min-h-28 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function WorkflowSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-workflows", "automation-logs"]);
  const query = useQuery({ queryKey: ["automation-workflows"], queryFn: automationApi.workflows });
  const [name, setName] = useState("Quote discount approval");
  const [conditions, setConditions] = useState('[{"field":"discount_percent","operator":"greater_or_equal","value":15}]');
  const [actions, setActions] = useState('[{"type":"submit_approval","rule_id":1},{"type":"send_notification","title":"Approval needed","message":"Quote needs review"}]');
  const create = useMutation({
    mutationFn: () => automationApi.createWorkflow({ name, module_name: "crm", record_type: "quote", trigger_type: "quote_submitted", conditions: parseJson(conditions, []), actions: parseJson(actions, []), is_active: true }),
    onSuccess: () => { toast({ title: "Workflow saved" }); refresh(); },
    onError: (error: Error) => toast({ title: error.message || "Workflow could not be saved", variant: "destructive" }),
  });
  const first = query.data?.items?.[0];
  const run = useMutation({
    mutationFn: () => automationApi.testWorkflow(Number(first?.id), { record: { discount_percent: 20 }, record_id: 1001, depth: 0 }),
    onSuccess: () => { toast({ title: "Workflow test logged" }); refresh(); },
  });
  return (
    <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <Card>
        <CardHeader><CardTitle>Create Workflow</CardTitle><CardDescription>Conditions and actions are stored as JSON only.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <Field label="Name"><Input value={name} onChange={(event) => setName(event.target.value)} /></Field>
          <TextAreaField label="Conditions JSON" value={conditions} onChange={setConditions} />
          <TextAreaField label="Actions JSON" value={actions} onChange={setActions} />
          <Button onClick={() => create.mutate()} disabled={create.isPending}><CheckCircle2 className="h-4 w-4" />Save Workflow</Button>
        </CardContent>
      </Card>
      <div className="space-y-4">
        <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Workflow Registry</h2><Button variant="outline" size="sm" disabled={!first || run.isPending} onClick={() => run.mutate()}><Play className="h-4 w-4" />Test First</Button></div>
        <QueryState isLoading={query.isLoading} isError={query.isError} onRetry={() => query.refetch()} />
        <RecordList items={query.data?.items} empty="No workflows configured yet." />
      </div>
    </div>
  );
}

function BlueprintSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-blueprints"]);
  const query = useQuery({ queryKey: ["automation-blueprints"], queryFn: automationApi.blueprints });
  const create = useMutation({
    mutationFn: () => automationApi.createBlueprint({
      name: "Deal Qualification Blueprint",
      module_name: "crm",
      record_type: "deal",
      stages: [{ stage_key: "qualified", label: "Qualified" }, { stage_key: "proposal", label: "Proposal", required_fields: ["amount"] }],
      transitions: [{ from_stage_key: "qualified", to_stage_key: "proposal", required_fields: ["amount"], requires_approval: false }],
    }),
    onSuccess: () => { toast({ title: "Blueprint saved" }); refresh(); },
  });
  return <SimpleSection title="Blueprints" description="Allowed stage transitions with required-field and approval gates." button="Create Blueprint" onAction={() => create.mutate()} query={query} empty="No blueprints configured yet." />;
}

function ApprovalSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-approvals"]);
  const query = useQuery({ queryKey: ["automation-approvals"], queryFn: automationApi.approvals });
  const create = useMutation({
    mutationFn: () => automationApi.createApproval({ module_name: "crm", record_type: "quote", record_id: 501, payload_json: { discount_percent: 20 } }),
    onSuccess: () => { toast({ title: "Approval request created" }); refresh(); },
  });
  return <SimpleSection title="Approvals" description="Approval queue for quote discount, margin, sales order, and write-off compatible flows." button="Create Request" onAction={() => create.mutate()} query={query} empty="No approval requests found." />;
}

function AssignmentSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-assignments"]);
  const query = useQuery({ queryKey: ["automation-assignments"], queryFn: automationApi.assignmentRules });
  const create = useMutation({
    mutationFn: () => automationApi.createAssignmentRule({ name: "Enterprise source assignment", module_name: "crm", record_type: "lead", condition_json: [{ field: "source", operator: "equals", value: "website" }], assignment_json: { owner_strategy: "territory" } }),
    onSuccess: () => { toast({ title: "Assignment rule saved" }); refresh(); },
  });
  return <SimpleSection title="Assignment Rules" description="Territory, source, and owner assignment tests for incoming records." button="Create Rule" onAction={() => create.mutate()} query={query} empty="No assignment rules configured yet." />;
}

function CadenceSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-cadences"]);
  const query = useQuery({ queryKey: ["automation-cadences"], queryFn: automationApi.cadences });
  const create = useMutation({
    mutationFn: () => automationApi.createCadence({ name: "New lead nurture", module_name: "crm", target_type: "lead", stop_rules_json: { stop_on: ["won", "lost", "converted"] }, steps: [{ step_type: "email", delay_hours: 2, payload_json: { template_id: "intro" } }, { step_type: "task", delay_hours: 24, payload_json: { title: "Follow up" } }] }),
    onSuccess: () => { toast({ title: "Cadence saved" }); refresh(); },
  });
  return <SimpleSection title="Cadences" description="Task, email, and WhatsApp-placeholder steps with enroll, pause, and resume support." button="Create Cadence" onAction={() => create.mutate()} query={query} empty="No cadences configured yet." />;
}

function WebhookSection() {
  const { toast } = useToast();
  const refresh = useRefresh(["automation-webhooks"]);
  const query = useQuery({ queryKey: ["automation-webhooks"], queryFn: automationApi.webhooks });
  const create = useMutation({
    mutationFn: () => automationApi.createWebhook({ name: "Revenue operations hook", target_url: "https://example.com/hooks/revenue", event_types_json: ["quote.approved", "deal.won"] }),
    onSuccess: () => { toast({ title: "Webhook saved" }); refresh(); },
  });
  return <SimpleSection title="Webhooks" description="Webhook endpoints are configured records; workflow actions cannot inject arbitrary URLs." button="Create Webhook" onAction={() => create.mutate()} query={query} empty="No webhook endpoints configured yet." />;
}

function LogSection() {
  const query = useQuery({ queryKey: ["automation-logs"], queryFn: automationApi.logs });
  return <SimpleSection title="Execution Logs" description="All workflow tests, failures, retries, webhook tests, and guarded action outcomes." query={query} empty="No execution logs found." />;
}

function SimpleSection({ title, description, button, onAction, query, empty }: { title: string; description: string; button?: string; onAction?: () => void; query: ReturnType<typeof useQuery<{ items: AutomationRecord[]; total: number }>>; empty: string }) {
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
        {button ? <Button onClick={onAction}><CheckCircle2 className="h-4 w-4" />{button}</Button> : null}
      </div>
      <QueryState isLoading={query.isLoading} isError={query.isError} onRetry={() => query.refetch()} />
      <RecordList items={items} empty={empty} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}
