import { useState, type ReactNode } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Bot, CheckCircle2, FileText, Gauge, Lightbulb, Mail, Play, ScrollText, Settings, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiCopilotApi, type AICopilotRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

type SectionKey = "copilot" | "record-summary" | "deal-coach" | "forecast" | "collection-risk" | "workflow-builder" | "report-explainer" | "prompt-templates" | "provider-settings" | "action-log";

const nav: Array<{ key: SectionKey; label: string; path: string; icon: typeof Sparkles }> = [
  { key: "copilot", label: "Copilot", path: "/ai/copilot", icon: Sparkles },
  { key: "record-summary", label: "Record Summary", path: "/ai/record-summary", icon: FileText },
  { key: "deal-coach", label: "Deal Coach", path: "/ai/deal-coach", icon: Lightbulb },
  { key: "forecast", label: "Forecast", path: "/ai/forecast", icon: Gauge },
  { key: "collection-risk", label: "Collection Risk", path: "/ai/collection-risk", icon: ShieldCheck },
  { key: "workflow-builder", label: "Workflow Draft", path: "/ai/workflow-builder", icon: Workflow },
  { key: "report-explainer", label: "Report Explainer", path: "/ai/report-explainer", icon: Bot },
  { key: "prompt-templates", label: "Prompts", path: "/ai/prompt-templates", icon: FileText },
  { key: "provider-settings", label: "Providers", path: "/ai/provider-settings", icon: Settings },
  { key: "action-log", label: "Action Log", path: "/ai/action-log", icon: ScrollText },
];

function activeSection(pathname: string): SectionKey {
  const match = nav.find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`));
  return match?.key || "copilot";
}

const endpointBySection: Partial<Record<SectionKey, string>> = {
  "record-summary": "summary",
  "deal-coach": "deal-coach",
  forecast: "forecast-insight",
  "collection-risk": "collection-risk",
  "workflow-builder": "workflow-draft",
  "report-explainer": "report-explain",
  copilot: "summary",
};

export default function AICopilotPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">Business Suite</p>
        <h1 className="text-2xl font-semibold">AI Copilot</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Secure CRM, SRM, PMS, and analytics copilot with provider settings, sanitized context, user confirmation, and auditable actions.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {nav.map((item) => {
            const Icon = item.icon;
            return <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>;
          })}
        </div>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "provider-settings" ? <ProviderSettings /> : null}
        {active === "prompt-templates" ? <PromptTemplates /> : null}
        {active === "action-log" ? <ActionLog /> : null}
        {!["provider-settings", "prompt-templates", "action-log"].includes(active) ? <RunPanel active={active} /> : null}
      </div>
    </div>
  );
}

function RunPanel({ active }: { active: SectionKey }) {
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<AICopilotRecord>(() => ({
    module_name: searchParams.get("module_name") || (active === "collection-risk" ? "srm" : "crm"),
    record_type: searchParams.get("record_type") || (active === "collection-risk" ? "collection" : active === "deal-coach" ? "deal" : "lead"),
    record_id: searchParams.get("record_id") || "",
    prompt: searchParams.get("prompt") || "",
  }));
  const [result, setResult] = useState<AICopilotRecord | null>(null);
  const [providerMessage, setProviderMessage] = useState<string | null>(null);
  const endpoint = endpointBySection[active] || "summary";
  const mutation = useMutation({
    mutationFn: () => aiCopilotApi.run(endpoint, { ...form, record_id: Number(form.record_id) || undefined }),
    onSuccess: (data) => {
      setProviderMessage(null);
      setResult(data);
      toast({ title: "AI result generated" });
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      setProviderMessage(detail?.message || detail || "AI provider not configured or request blocked.");
      setResult(null);
    },
  });
  const action = useMutation({
    mutationFn: () => aiCopilotApi.previewAction({ action_type: active === "workflow-builder" ? "draft_workflow" : "draft_email", module_name: form.module_name, record_type: form.record_type, record_id: Number(form.record_id) || undefined, input_json: { prompt: form.prompt } }),
    onSuccess: (data) => setResult({ ...data, actionPreview: true }),
    onError: (err: any) => setProviderMessage(err?.response?.data?.detail || "AI action preview was blocked."),
  });
  return (
    <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <Card>
        <CardHeader><CardTitle>{labelFor(active)}</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {providerMessage ? <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{providerMessage}</div> : null}
          <Field label="Module"><Input value={String(form.module_name || "")} onChange={(event) => setForm({ ...form, module_name: event.target.value })} /></Field>
          <Field label="Record Type"><Input value={String(form.record_type || "")} onChange={(event) => setForm({ ...form, record_type: event.target.value })} /></Field>
          <Field label="Record ID"><Input value={String(form.record_id || "")} onChange={(event) => setForm({ ...form, record_id: event.target.value })} /></Field>
          <Field label="Prompt"><textarea value={String(form.prompt || "")} onChange={(event) => setForm({ ...form, prompt: event.target.value })} rows={4} className="w-full rounded-md border bg-background px-3 py-2 text-sm" /></Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}><Play className="h-4 w-4" />Generate</Button>
            <Button variant="outline" onClick={() => action.mutate()} disabled={action.isPending}><CheckCircle2 className="h-4 w-4" />Preview Action</Button>
          </div>
        </CardContent>
      </Card>
      <ResultCard result={result} />
    </div>
  );
}

function ProviderSettings() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["ai-provider-settings"], queryFn: aiCopilotApi.providerSettings });
  const create = useMutation({
    mutationFn: () => aiCopilotApi.createProviderSetting({ provider_name: "mock", model_name: "mock-business-suite", enabled: true, data_sharing_allowed: true, masked_api_key_reference: "mock-test-only", max_tokens: 1200, temperature: 0.2 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-provider-settings"] }),
  });
  const test = useMutation({ mutationFn: (id: number) => aiCopilotApi.testProviderSetting(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-provider-settings"] }) });
  return (
    <Section title="AI Provider Settings" action={<Button onClick={() => create.mutate()}>Add Mock Provider</Button>}>
      <div className="grid gap-3 md:grid-cols-2">
        {(query.data?.items || []).map((item) => <Card key={item.id}><CardContent className="flex items-start justify-between gap-3 p-4"><div><p className="font-medium">{item.provider_name} / {item.model_name}</p><p className="mt-1 text-sm text-muted-foreground">Data sharing {item.data_sharing_allowed ? "allowed" : "blocked"}</p></div><div className="flex flex-col items-end gap-2"><Badge variant={item.enabled ? "default" : "outline"}>{item.enabled ? "Enabled" : "Disabled"}</Badge><Button variant="outline" size="sm" onClick={() => test.mutate(Number(item.id))}>Test</Button></div></CardContent></Card>)}
      </div>
      {!query.isLoading && !(query.data?.items || []).length ? <p className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">No AI provider is configured.</p> : null}
    </Section>
  );
}

function PromptTemplates() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["ai-prompt-templates"], queryFn: aiCopilotApi.promptTemplates });
  const create = useMutation({
    mutationFn: () => aiCopilotApi.createPromptTemplate({ name: "CRM Record Summary", use_case: "summary", module_name: "crm", system_prompt: "Use sanitized Business Suite context only.", user_prompt_template: "Summarize record with evidence and confidence.", output_schema_json: { summary: "string", confidence: "number" }, active: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-prompt-templates"] }),
  });
  return (
    <Section title="AI Prompt Templates" action={<Button onClick={() => create.mutate()}>Create Summary Prompt</Button>}>
      <div className="grid gap-3 md:grid-cols-2">
        {(query.data?.items || []).map((item) => <Card key={item.id}><CardContent className="p-4"><p className="font-medium">{item.name}</p><p className="mt-1 text-sm text-muted-foreground">{item.module_name} / {item.use_case}</p><Badge className="mt-3" variant={item.active ? "default" : "outline"}>{item.active ? "Active" : "Inactive"}</Badge></CardContent></Card>)}
      </div>
    </Section>
  );
}

function ActionLog() {
  const query = useQuery({ queryKey: ["ai-action-log"], queryFn: aiCopilotApi.actionLog });
  return (
    <Section title="AI Action Log">
      <div className="space-y-2">
        {(query.data?.items || []).map((item) => <div key={item.id} className="rounded-md border bg-card px-4 py-3 text-sm"><div className="flex items-center justify-between gap-3"><span className="font-medium">{item.event_type}</span><Badge variant="outline">{item.status}</Badge></div><p className="mt-1 text-xs text-muted-foreground">{item.module_name || "ai"} {item.record_type || ""} #{item.record_id || "-"} by user #{item.created_by || "-"}</p></div>)}
      </div>
    </Section>
  );
}

function ResultCard({ result }: { result: AICopilotRecord | null }) {
  return (
    <Card>
      <CardHeader><CardTitle>AI Output</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {!result ? <p className="text-sm text-muted-foreground">Generated results, evidence, confidence, and action previews appear here.</p> : null}
        {result ? <pre className="max-h-[32rem] overflow-auto rounded-md border bg-muted/35 p-3 text-xs">{JSON.stringify(result, null, 2)}</pre> : null}
      </CardContent>
    </Card>
  );
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return <div className="space-y-4"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><h2 className="text-lg font-semibold">{title}</h2>{action}</div>{children}</div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function labelFor(value: string) {
  return value.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
