import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Code2, KeyRound, Landmark, Package, RefreshCw, Settings, ShieldCheck, Smartphone, Store, Webhook } from "lucide-react";
import { saasApi, type SaaSRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Section = "mobile" | "developer" | "api-keys" | "webhooks" | "api-logs" | "docs" | "marketplace" | "installed" | "sandbox" | "company-settings" | "feature-flags" | "subscription" | "usage";

const nav: Array<{ key: Section; label: string; path: string; icon: typeof Code2 }> = [
  { key: "mobile", label: "Mobile CRM", path: "/mobile", icon: Smartphone },
  { key: "api-keys", label: "API Keys", path: "/developer/api-keys", icon: KeyRound },
  { key: "webhooks", label: "Webhooks", path: "/developer/webhooks", icon: Webhook },
  { key: "api-logs", label: "API Logs", path: "/developer/api-logs", icon: Code2 },
  { key: "docs", label: "Docs", path: "/developer/docs", icon: Code2 },
  { key: "marketplace", label: "Marketplace", path: "/marketplace/apps", icon: Store },
  { key: "installed", label: "Installed", path: "/marketplace/installed", icon: Package },
  { key: "sandbox", label: "Sandbox", path: "/admin/sandbox", icon: ShieldCheck },
  { key: "company-settings", label: "Company", path: "/admin/company-settings", icon: Settings },
  { key: "feature-flags", label: "Flags", path: "/admin/feature-flags", icon: RefreshCw },
  { key: "subscription", label: "Subscription", path: "/admin/subscription", icon: Landmark },
  { key: "usage", label: "Usage", path: "/admin/usage", icon: Briefcase },
];

function activeSection(pathname: string): Section {
  if (pathname.startsWith("/developer/api-keys")) return "api-keys";
  if (pathname.startsWith("/developer/webhooks")) return "webhooks";
  if (pathname.startsWith("/developer/api-logs")) return "api-logs";
  if (pathname.startsWith("/developer/docs")) return "docs";
  if (pathname.startsWith("/developer")) return "developer";
  if (pathname.startsWith("/marketplace/installed")) return "installed";
  if (pathname.startsWith("/marketplace")) return "marketplace";
  if (pathname.startsWith("/admin/sandbox")) return "sandbox";
  if (pathname.startsWith("/admin/company-settings")) return "company-settings";
  if (pathname.startsWith("/admin/feature-flags")) return "feature-flags";
  if (pathname.startsWith("/admin/subscription")) return "subscription";
  if (pathname.startsWith("/admin/usage")) return "usage";
  return "mobile";
}

export default function SaaSWorkspacePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">SaaS Packaging</p>
        <h1 className="text-2xl font-semibold">{active === "mobile" ? "Mobile CRM" : active.startsWith("api") || active === "webhooks" || active === "docs" ? "Developer Hub" : active === "marketplace" || active === "installed" ? "Marketplace" : "Admin SaaS Controls"}</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Portal-safe access, mobile CRM, developer keys, webhooks, internal marketplace, sandbox requests, tenant settings, and subscription feature gates.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {nav.map((item) => { const Icon = item.icon; return <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>; })}
        </div>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "mobile" ? <MobileCRM /> : null}
        {active === "api-keys" || active === "developer" ? <APIKeys /> : null}
        {active === "webhooks" ? <Webhooks /> : null}
        {active === "api-logs" ? <ListPanel title="API logs" queryKey="api-logs" queryFn={saasApi.apiLogs} /> : null}
        {active === "docs" ? <Docs /> : null}
        {active === "marketplace" ? <Marketplace /> : null}
        {active === "installed" ? <ListPanel title="Installed apps" queryKey="installed-apps" queryFn={saasApi.installedMarketplaceApps} /> : null}
        {active === "sandbox" ? <Sandbox /> : null}
        {active === "company-settings" ? <CompanySettings /> : null}
        {active === "feature-flags" ? <FeatureFlags /> : null}
        {active === "subscription" ? <Subscription /> : null}
        {active === "usage" ? <ListPanel title="Usage metrics" queryKey="usage" queryFn={saasApi.usage} /> : null}
      </div>
    </div>
  );
}

function MobileCRM() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["checkins"], queryFn: saasApi.checkIns });
  const [form, setForm] = useState({ customer_name: "", notes: "", latitude: "", longitude: "" });
  const create = useMutation({ mutationFn: saasApi.createCheckIn, onSuccess: () => qc.invalidateQueries({ queryKey: ["checkins"] }) });
  return <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]"><Card><CardHeader><CardTitle>Sales visit check-in</CardTitle></CardHeader><CardContent className="space-y-3"><Input placeholder="Customer name" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} /><Input placeholder="Latitude" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} /><Input placeholder="Longitude" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} /><Input placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /><Button onClick={() => create.mutate(form)}>Check in</Button><p className="text-sm text-muted-foreground">Offline queue placeholder. Actions are not queued unless a production sync worker is added.</p></CardContent></Card><RecordList title="Recent check-ins" items={query.data?.items || []} /></div>;
}

function APIKeys() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["api-keys"], queryFn: saasApi.apiKeys });
  const [created, setCreated] = useState<string | null>(null);
  const create = useMutation({ mutationFn: () => saasApi.createApiKey({ name: "Integration key", scopes: ["crm.read", "srm.read"] }), onSuccess: (data) => { setCreated(data.api_key); qc.invalidateQueries({ queryKey: ["api-keys"] }); } });
  return <div className="space-y-4"><Button onClick={() => create.mutate()}>Create scoped API key</Button>{created ? <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">One-time key: {created}</div> : null}<RecordList title="API keys" items={query.data?.items || []} /></div>;
}

function Webhooks() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["webhooks"], queryFn: saasApi.webhooks });
  const create = useMutation({ mutationFn: () => saasApi.createWebhook({ name: "CRM event webhook", target_url: "https://example.com/business-suite/webhook", events: ["lead.created"], secret: "secret" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }) });
  const test = useMutation({ mutationFn: (id: number) => saasApi.testWebhook(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }) });
  return <div className="space-y-4"><Button onClick={() => create.mutate()}>Create HTTPS webhook</Button><RecordList title="Webhooks" items={query.data?.items || []} action={(item) => <Button size="sm" variant="outline" onClick={() => test.mutate(Number(item.id))}>Test</Button>} /></div>;
}

function Marketplace() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["marketplace-apps"], queryFn: saasApi.marketplaceApps });
  const create = useMutation({ mutationFn: () => saasApi.createMarketplaceApp({ name: "Internal CRM Extension", category: "internal", description: "Internal extension placeholder" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["marketplace-apps"] }) });
  const install = useMutation({ mutationFn: (id: number) => saasApi.installMarketplaceApp(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["installed-apps"] }) });
  return <div className="space-y-4"><div className="flex items-center gap-2"><Button onClick={() => create.mutate()}>Create internal app</Button><Badge variant="outline">Internal extensions only</Badge></div><RecordList title="Marketplace apps" items={query.data?.items || []} action={(item) => <Button size="sm" variant="outline" onClick={() => install.mutate(Number(item.id))}>Install</Button>} /></div>;
}

function Sandbox() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["sandboxes"], queryFn: saasApi.sandboxes });
  const create = useMutation({ mutationFn: () => saasApi.createSandbox({ name: "UAT Sandbox", copy_sample_data: false }), onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }) });
  const refresh = useMutation({ mutationFn: (id: number) => saasApi.refreshSandbox(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }) });
  return <div className="space-y-4"><Button onClick={() => create.mutate()}>Create sandbox request</Button><RecordList title="Sandboxes" items={query.data?.items || []} action={(item) => <Button size="sm" variant="outline" onClick={() => refresh.mutate(Number(item.id))}>Refresh</Button>} /></div>;
}

function CompanySettings() {
  const query = useQuery({ queryKey: ["company-settings"], queryFn: saasApi.companySettings });
  const mutation = useMutation({ mutationFn: () => saasApi.updateCompanySettings({ company_name: "Business Suite", fiscal_year_start_month: 4, base_currency: "INR", timezone: "Asia/Calcutta", tax_defaults: { gst: "not_configured" }, business_hours: { weekdays: "09:00-18:00" }, numbering_settings: { quote: "QT-{YYYY}-{SEQ}" } }), onSuccess: () => query.refetch() });
  return <div className="space-y-4"><Button onClick={() => mutation.mutate()}>Save default settings</Button><RecordList title="Company settings" items={query.data ? [query.data] : []} /></div>;
}

function FeatureFlags() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["feature-flags"], queryFn: saasApi.featureFlags });
  const mutation = useMutation({ mutationFn: () => saasApi.upsertFeatureFlag({ feature_key: "portals", enabled: true, upgrade_message: "Upgrade to Ultimate for portals." }), onSuccess: () => qc.invalidateQueries({ queryKey: ["feature-flags"] }) });
  return <div className="space-y-4"><Button onClick={() => mutation.mutate()}>Enable portals flag</Button><RecordList title="Feature flags" items={query.data?.items || []} /></div>;
}

function Subscription() {
  const query = useQuery({ queryKey: ["subscription"], queryFn: saasApi.subscription });
  const plans = useQuery({ queryKey: ["subscription-plans"], queryFn: saasApi.subscriptionPlans });
  const mutation = useMutation({ mutationFn: () => saasApi.updateSubscription({ edition: "ultimate", status: "active", admin_override: true }), onSuccess: () => query.refetch() });
  return <div className="space-y-4"><Button onClick={() => mutation.mutate()}>Set Ultimate with admin override</Button><RecordList title="Current subscription" items={query.data ? [query.data] : []} /><RecordList title="Plans" items={plans.data?.items || []} /></div>;
}

function Docs() {
  const query = useQuery({ queryKey: ["developer-docs"], queryFn: saasApi.developerDocs });
  return <RecordList title="Developer docs" items={query.data ? [query.data] : []} />;
}

function ListPanel({ title, queryKey, queryFn }: { title: string; queryKey: string; queryFn: () => Promise<{ items: SaaSRecord[] }> }) {
  const query = useQuery({ queryKey: [queryKey], queryFn });
  return <RecordList title={title} items={query.data?.items || []} />;
}

function RecordList({ title, items, action }: { title: string; items: SaaSRecord[]; action?: (item: SaaSRecord) => ReactNode }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent>{items.length ? <div className="grid gap-3 md:grid-cols-2">{items.map((item, index) => <div key={item.id || index} className="rounded-md border p-3"><div className="flex items-center justify-between gap-2"><p className="font-medium">{item.name || item.company_name || item.metric_key || item.feature_key || item.key_prefix || `Record ${item.id || index + 1}`}</p>{item.status ? <Badge variant="outline">{item.status}</Badge> : null}</div><pre className="mt-2 max-h-36 overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(item, null, 2)}</pre>{action ? <div className="mt-2">{action(item)}</div> : null}</div>)}</div> : <p className="text-sm text-muted-foreground">No records yet.</p>}</CardContent></Card>;
}
