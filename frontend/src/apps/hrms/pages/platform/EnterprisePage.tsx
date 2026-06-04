import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi, enterpriseApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/hooks/use-toast";
import { getApiBaseUrl } from "@/config/runtime";
import { cn } from "@/lib/utils";

type Policy = {
  id: number;
  name: string;
  min_length: number;
  require_uppercase: boolean;
  require_lowercase: boolean;
  require_number: boolean;
  require_special?: boolean;
  require_symbol?: boolean;
  max_age_days?: number;
  expiry_days?: number;
  lockout_attempts: number;
  lockout_duration_minutes?: number;
  lockout_minutes?: number;
  mfa_required?: boolean;
  is_default?: boolean;
  is_active: boolean;
};

type SsoProvider = {
  id?: number;
  name: string;
  provider_type: string;
  is_active: boolean;
  is_default: boolean;
  button_label?: string;
  button_icon?: string;
  domain_hint?: string;
  client_id?: string;
  client_secret?: string;
  authorization_url?: string;
  token_url?: string;
  userinfo_url?: string;
  scope?: string;
  redirect_uri?: string;
  idp_entity_id?: string;
  idp_sso_url?: string;
  idp_x509_cert?: string;
  sp_entity_id?: string;
  attr_email?: string;
  attr_first_name?: string;
  attr_last_name?: string;
  attr_role?: string;
  auto_provision?: boolean;
  default_role_id?: number | "";
};

type IpPolicy = {
  id?: number;
  cidr: string;
  action: "allow" | "block";
  description?: string;
  is_active: boolean;
};

type PrivacyRequest = {
  id: number;
  employee_id?: number | null;
  request_type: string;
  status: string;
  requested_by_email?: string | null;
  resolution_notes?: string | null;
  processing_result_json?: Record<string, unknown> | null;
  created_at: string;
};

const blankProvider: SsoProvider = {
  name: "",
  provider_type: "google",
  is_active: true,
  is_default: false,
  button_label: "",
  button_icon: "google",
  domain_hint: "",
  scope: "openid email profile",
  attr_email: "email",
  attr_first_name: "given_name",
  attr_last_name: "family_name",
  auto_provision: true,
  default_role_id: "",
};

export default function EnterprisePage() {
  usePageTitle("Enterprise");
  const user = useAuthStore((state) => state.user);
  const [tab, setTab] = useState<"Security Policy" | "SSO Providers" | "IP Policies" | "Privacy">("Security Policy");
  if (!user?.is_superuser) {
    return <div className="rounded-lg border p-6 text-sm text-muted-foreground">Enterprise security settings are available to administrators only.</div>;
  }
  return (
    <div className="space-y-6">
      <div><h1 className="page-title">Enterprise Platform</h1><p className="page-description">Security policy, MFA enforcement, and enterprise SSO configuration.</p></div>
      <div className="flex gap-2 border-b">
        {["Security Policy", "SSO Providers", "IP Policies", "Privacy"].map((item) => <button key={item} onClick={() => setTab(item as "Security Policy" | "SSO Providers" | "IP Policies" | "Privacy")} className={cn("border-b-2 px-3 py-2 text-sm font-medium", tab === item ? "border-primary text-primary" : "border-transparent text-muted-foreground")}>{item}</button>)}
      </div>
      {tab === "Security Policy" ? <SecurityPolicy /> : tab === "SSO Providers" ? <SsoProviders /> : tab === "IP Policies" ? <IpPolicies /> : <PrivacyOps />}
    </div>
  );
}

function PrivacyOps() {
  const qc = useQueryClient();
  const [draft, setDraft] = useState({ employee_id: "", request_type: "export", requested_by_email: "" });
  const requests = useQuery({ queryKey: ["privacy-requests"], queryFn: () => enterpriseApi.privacyRequests().then((r) => r.data as PrivacyRequest[]) });
  const create = useMutation({
    mutationFn: () => enterpriseApi.createPrivacyRequest({ ...draft, employee_id: draft.employee_id ? Number(draft.employee_id) : null }),
    onSuccess: () => {
      toast({ title: "Privacy request created" });
      setDraft({ employee_id: "", request_type: "export", requested_by_email: "" });
      qc.invalidateQueries({ queryKey: ["privacy-requests"] });
    },
  });
  const process = useMutation({
    mutationFn: (id: number) => enterpriseApi.processPrivacyRequest(id),
    onSuccess: () => {
      toast({ title: "Privacy request processed" });
      qc.invalidateQueries({ queryKey: ["privacy-requests"] });
    },
    onError: () => toast({ title: "Privacy processing blocked", variant: "destructive" }),
  });
  const retention = useMutation({
    mutationFn: (dryRun: boolean) => enterpriseApi.runRetentionPolicies(dryRun),
    onSuccess: (res) => toast({ title: "Retention run complete", description: `${res.data.eligible || 0} eligible, ${res.data.blocked || 0} blocked.` }),
  });
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Privacy Request</CardTitle><CardDescription>Exports use masked sensitive identifiers. Delete requests are blocked by active legal holds and retention.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <Field label="Employee ID"><Input value={draft.employee_id} onChange={(e) => setDraft({ ...draft, employee_id: e.target.value })} /></Field>
          <Field label="Request Type"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.request_type} onChange={(e) => setDraft({ ...draft, request_type: e.target.value })}><option value="export">Export</option><option value="anonymize">Anonymize/Delete</option></select></Field>
          <Field label="Requester Email"><Input value={draft.requested_by_email} onChange={(e) => setDraft({ ...draft, requested_by_email: e.target.value })} /></Field>
          <Button onClick={() => create.mutate()} disabled={!draft.employee_id || create.isPending}>Create Request</Button>
          <div className="flex gap-2 border-t pt-4">
            <Button variant="outline" onClick={() => retention.mutate(true)}>Dry Run Retention</Button>
            <Button variant="outline" onClick={() => retention.mutate(false)}>Run Retention</Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Privacy Queue</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">ID</th><th className="px-3 py-2 text-left">Employee</th><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">Result</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
              <tbody>{(requests.data || []).map((row) => <tr key={row.id} className="border-t"><td className="px-3 py-2">{row.id}</td><td className="px-3 py-2">{row.employee_id || "-"}</td><td className="px-3 py-2">{row.request_type}</td><td className="px-3 py-2"><Badge variant={row.status === "Blocked" ? "destructive" : "secondary"}>{row.status}</Badge></td><td className="max-w-[320px] truncate px-3 py-2 text-muted-foreground">{row.resolution_notes || JSON.stringify(row.processing_result_json || {})}</td><td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" onClick={() => process.mutate(row.id)}>Process</Button></td></tr>)}</tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function IpPolicies() {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<IpPolicy>({ cidr: "", action: "allow", description: "", is_active: true });
  const policies = useQuery({ queryKey: ["ip-policies"], queryFn: () => authApi.ipPolicies().then((r) => r.data as IpPolicy[]) });
  const save = useMutation({
    mutationFn: () => draft.id ? authApi.updateIpPolicy(draft.id, draft) : authApi.createIpPolicy(draft),
    onSuccess: () => {
      toast({ title: "IP policy saved" });
      setDraft({ cidr: "", action: "allow", description: "", is_active: true });
      qc.invalidateQueries({ queryKey: ["ip-policies"] });
    },
    onError: () => toast({ title: "Invalid IP policy", variant: "destructive" }),
  });
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">{draft.id ? "Edit" : "Add"} IP Policy</CardTitle><CardDescription>Blocklist entries always win. If any allowlist entry is active, unmatched IPs are rejected.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <Field label="CIDR"><Input placeholder="203.0.113.0/24" value={draft.cidr} onChange={(e) => setDraft({ ...draft, cidr: e.target.value })} /></Field>
          <Field label="Action"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value as "allow" | "block" })}><option value="allow">Allow</option><option value="block">Block</option></select></Field>
          <Field label="Description"><Input value={draft.description || ""} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />Active</label>
          <Button onClick={() => save.mutate()} disabled={!draft.cidr || save.isPending}>Save Policy</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">IP Allowlist / Blocklist</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">CIDR</th><th className="px-3 py-2 text-left">Action</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">Description</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
              <tbody>{(policies.data || []).map((row) => <tr key={row.id} className="border-t"><td className="px-3 py-2">{row.cidr}</td><td className="px-3 py-2"><Badge variant={row.action === "block" ? "destructive" : "secondary"}>{row.action}</Badge></td><td className="px-3 py-2">{row.is_active ? "Active" : "Inactive"}</td><td className="px-3 py-2">{row.description || "-"}</td><td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" onClick={() => setDraft(row)}>Edit</Button></td></tr>)}</tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SecurityPolicy() {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Policy | null>(null);
  const policies = useQuery({ queryKey: ["password-policies"], queryFn: () => authApi.passwordPolicies().then((r) => r.data as Policy[]) });
  const attempts = useQuery({ queryKey: ["admin-login-attempts"], queryFn: () => authApi.loginAttempts().then((r) => r.data) });
  const policy = useMemo(() => (policies.data || []).find((item) => item.is_default) || policies.data?.[0], [policies.data]);
  useEffect(() => { if (policy) setDraft(policy); }, [policy?.id]);
  const save = useMutation({
    mutationFn: () => authApi.updatePasswordPolicy(draft!.id, draft),
    onSuccess: () => { toast({ title: "Policy saved" }); qc.invalidateQueries({ queryKey: ["password-policies"] }); },
  });
  const enforce = useMutation({
    mutationFn: () => authApi.enforceMfaPolicy(draft!.id),
    onSuccess: (res) => { toast({ title: "MFA enforcement enabled", description: `${res.data.users_without_mfa} users still need setup.` }); qc.invalidateQueries({ queryKey: ["password-policies"] }); },
  });
  if (!draft) return <div className="h-40 animate-pulse rounded bg-muted" />;
  const patch = (changes: Partial<Policy>) => setDraft((current) => current ? { ...current, ...changes } : current);
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Password & Lockout Policy</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Min Password Length"><Input type="number" min={8} max={32} value={draft.min_length} onChange={(e) => patch({ min_length: Number(e.target.value) })} /></Field>
          <Field label="Password Expiry (days)"><Input type="number" value={draft.max_age_days ?? draft.expiry_days ?? 0} onChange={(e) => patch({ max_age_days: Number(e.target.value), expiry_days: Number(e.target.value) })} /></Field>
          <Field label="Max Failed Attempts"><Input type="number" value={draft.lockout_attempts} onChange={(e) => patch({ lockout_attempts: Number(e.target.value) })} /></Field>
          <Field label="Lockout Duration"><Input type="number" value={draft.lockout_duration_minutes ?? draft.lockout_minutes ?? 30} onChange={(e) => patch({ lockout_duration_minutes: Number(e.target.value), lockout_minutes: Number(e.target.value) })} /></Field>
          {[
            ["require_uppercase", "Require Uppercase"],
            ["require_lowercase", "Require Lowercase"],
            ["require_number", "Require Number"],
            ["require_special", "Require Special"],
          ].map(([key, label]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean((draft as unknown as Record<string, unknown>)[key])} onChange={(e) => patch({ [key]: e.target.checked } as Partial<Policy>)} />{label}</label>)}
          <div className="sm:col-span-2"><Button onClick={() => save.mutate()} disabled={save.isPending}>Save Policy</Button></div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">MFA Enforcement</CardTitle><CardDescription>When enabled, all users must set up 2FA before accessing the system.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4"><span>Enforce MFA for all users</span><Switch checked={Boolean(draft.mfa_required)} onChange={() => patch({ mfa_required: !draft.mfa_required })} /></div>
          <Button onClick={() => enforce.mutate()} disabled={enforce.isPending}><ShieldCheck className="mr-2 h-4 w-4" />Enforce MFA</Button>
        </CardContent>
      </Card>
      <Card className="xl:col-span-2">
        <CardHeader><CardTitle className="text-base">Login Attempt Log</CardTitle></CardHeader>
        <CardContent><AttemptsTable rows={attempts.data || []} /></CardContent>
      </Card>
    </div>
  );
}

function SsoProviders() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<SsoProvider | null>(null);
  const providers = useQuery({ queryKey: ["sso-admin-providers"], queryFn: () => authApi.ssoAdminProviders().then((r) => r.data as SsoProvider[]) });
  const save = useMutation({
    mutationFn: (provider: SsoProvider) => provider.id ? authApi.updateSsoProvider(provider.id, provider) : authApi.createSsoProvider(provider),
    onSuccess: () => { toast({ title: "SSO provider saved" }); setEditing(null); qc.invalidateQueries({ queryKey: ["sso-admin-providers"] }); },
  });
  const remove = useMutation({ mutationFn: (id: number) => authApi.deleteSsoProvider(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["sso-admin-providers"] }) });
  const test = useMutation({ mutationFn: (id: number) => authApi.testSsoProvider(id), onSuccess: (res) => toast({ title: `Connection ${res.data.overall}` }) });
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Button onClick={() => setEditing(blankProvider)}><Plus className="mr-2 h-4 w-4" />Add Provider</Button></div>
      <Card><CardContent className="p-0"><table className="w-full text-sm"><thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Name</th><th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Domain</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-right">Actions</th></tr></thead><tbody>{(providers.data || []).map((provider) => <tr key={provider.id} className="border-t"><td className="px-3 py-2">{provider.name}</td><td className="px-3 py-2"><Badge variant="outline">{provider.provider_type}</Badge></td><td className="px-3 py-2">{provider.domain_hint || "-"}</td><td className="px-3 py-2"><Badge>{provider.is_active ? "Active" : "Inactive"}</Badge>{provider.is_default && <Badge variant="outline" className="ml-2">Default</Badge>}</td><td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" onClick={() => setEditing(provider)}>Edit</Button><Button size="sm" variant="ghost" onClick={() => provider.id && test.mutate(provider.id)}>Test</Button><Button size="icon" variant="ghost" className="text-destructive" onClick={() => provider.id && remove.mutate(provider.id)}><Trash2 className="h-4 w-4" /></Button></td></tr>)}</tbody></table></CardContent></Card>
      {editing && <ProviderDialog provider={editing} onClose={() => setEditing(null)} onSave={(provider) => save.mutate(provider)} />}
    </div>
  );
}

function ProviderDialog({ provider, onClose, onSave }: { provider: SsoProvider; onClose: () => void; onSave: (provider: SsoProvider) => void }) {
  const [draft, setDraft] = useState<SsoProvider>(provider);
  const [showSecret, setShowSecret] = useState(false);
  const apiBase = getApiBaseUrl();
  const fillGoogle = () => setDraft({ ...draft, provider_type: "google", button_icon: "google", authorization_url: "https://accounts.google.com/o/oauth2/v2/auth", token_url: "https://oauth2.googleapis.com/token", userinfo_url: "https://www.googleapis.com/oauth2/v3/userinfo" });
  const patch = (changes: Partial<SsoProvider>) => setDraft((current) => ({ ...current, ...changes }));
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-background p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">{draft.id ? "Edit" : "Add"} SSO Provider</h2><Button variant="ghost" onClick={onClose}>Close</Button></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name"><Input value={draft.name} onChange={(e) => patch({ name: e.target.value })} /></Field>
          <Field label="Provider Type"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.provider_type} onChange={(e) => patch({ provider_type: e.target.value, button_icon: e.target.value })}>{["google", "microsoft", "okta", "azure_ad", "custom_oidc", "saml"].map((item) => <option key={item}>{item}</option>)}</select></Field>
          <Field label="Button Label"><Input value={draft.button_label || ""} onChange={(e) => patch({ button_label: e.target.value })} /></Field>
          <Field label="Domain Hint"><Input value={draft.domain_hint || ""} onChange={(e) => patch({ domain_hint: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_default} onChange={(e) => patch({ is_default: e.target.checked })} />Is Default</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(draft.auto_provision)} onChange={(e) => patch({ auto_provision: e.target.checked })} />Auto Provision Users</label>
          {draft.provider_type !== "saml" ? (
            <>
              <Field label="Client ID"><Input value={draft.client_id || ""} onChange={(e) => patch({ client_id: e.target.value })} /></Field>
              <Field label="Client Secret"><div className="relative"><Input type={showSecret ? "text" : "password"} value={draft.client_secret || ""} onChange={(e) => patch({ client_secret: e.target.value })} /><button className="absolute right-2 top-2.5" onClick={() => setShowSecret(!showSecret)}>{showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></Field>
              <Field label="Authorization URL"><Input value={draft.authorization_url || ""} onChange={(e) => patch({ authorization_url: e.target.value })} /></Field>
              <Field label="Token URL"><Input value={draft.token_url || ""} onChange={(e) => patch({ token_url: e.target.value })} /></Field>
              <Field label="UserInfo URL"><Input value={draft.userinfo_url || ""} onChange={(e) => patch({ userinfo_url: e.target.value })} /></Field>
              <Field label="Scope"><Input value={draft.scope || "openid email profile"} onChange={(e) => patch({ scope: e.target.value })} /></Field>
              <p className="rounded border p-3 text-xs text-muted-foreground sm:col-span-2">Redirect URI: {apiBase}/auth/sso/callback/oidc/{draft.id || "{provider_id}"}</p>
              <Button type="button" variant="outline" onClick={fillGoogle}>Fill Google Defaults</Button>
            </>
          ) : (
            <>
              <Field label="IdP Entity ID"><Input value={draft.idp_entity_id || ""} onChange={(e) => patch({ idp_entity_id: e.target.value })} /></Field>
              <Field label="IdP SSO URL"><Input value={draft.idp_sso_url || ""} onChange={(e) => patch({ idp_sso_url: e.target.value })} /></Field>
              <Field label="IdP Certificate"><textarea className="min-h-24 rounded-md border bg-background p-2 text-sm sm:col-span-2" value={draft.idp_x509_cert || ""} onChange={(e) => patch({ idp_x509_cert: e.target.value })} /></Field>
            </>
          )}
          <Field label="Email Attribute"><Input value={draft.attr_email || "email"} onChange={(e) => patch({ attr_email: e.target.value })} /></Field>
          <Field label="First Name Attribute"><Input value={draft.attr_first_name || "given_name"} onChange={(e) => patch({ attr_first_name: e.target.value })} /></Field>
          <Field label="Last Name Attribute"><Input value={draft.attr_last_name || "family_name"} onChange={(e) => patch({ attr_last_name: e.target.value })} /></Field>
          <Field label="Role Attribute"><Input value={draft.attr_role || ""} onChange={(e) => patch({ attr_role: e.target.value })} /></Field>
        </div>
        <div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(draft)} disabled={!draft.name}>Save</Button></div>
      </div>
    </div>
  );
}

function AttemptsTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  return <div className="overflow-x-auto rounded-md border"><table className="w-full min-w-[760px] text-sm"><thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">User Email</th><th className="px-3 py-2 text-left">IP</th><th className="px-3 py-2 text-left">Time</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">MFA</th><th className="px-3 py-2 text-left">Failure Reason</th></tr></thead><tbody>{rows.slice(0, 50).map((row) => <tr key={String(row.id)} className={cn("border-t", row.success === false || row.status === "Failed" ? "bg-destructive/5" : "")}><td className="px-3 py-2">{String(row.email || "-")}</td><td className="px-3 py-2">{String(row.ip_address || "-")}</td><td className="px-3 py-2">{row.created_at ? new Date(String(row.created_at)).toLocaleString("en-IN") : "-"}</td><td className="px-3 py-2"><Badge variant={row.success === false || row.status === "Failed" ? "destructive" : "secondary"}>{String(row.status || "-")}</Badge></td><td className="px-3 py-2">{row.mfa_attempted ? <Badge variant="outline">{row.mfa_success ? "Passed" : "Failed"}</Badge> : "-"}</td><td className="px-3 py-2">{String(row.failure_reason || "-")}</td></tr>)}</tbody></table></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>;
}

function Switch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return <button type="button" onClick={onChange} className={cn("h-6 w-11 rounded-full p-0.5", checked ? "bg-primary" : "bg-muted-foreground/30")}><span className={cn("block h-5 w-5 rounded-full bg-background transition-transform", checked && "translate-x-5")} /></button>;
}
