import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseBackup, Download, FileSearch, GitMerge, KeyRound, LockKeyhole, Network, RefreshCw, ShieldCheck, SlidersHorizontal, Upload, Users } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { adminSecurityApi, type AdminSecurityList, type AdminSecurityRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";

type Section =
  | "security"
  | "profiles"
  | "roles"
  | "field-security"
  | "record-sharing"
  | "data-sharing"
  | "ip-restrictions"
  | "audit-logs"
  | "import"
  | "duplicates"
  | "export-control"
  | "backups"
  | "compliance"
  | "data-retention";

const sections: Array<{ key: Section; label: string; path: string; icon: typeof ShieldCheck }> = [
  { key: "security", label: "Security", path: "/admin/security", icon: ShieldCheck },
  { key: "profiles", label: "Profiles", path: "/admin/profiles", icon: Users },
  { key: "roles", label: "Roles", path: "/admin/roles", icon: KeyRound },
  { key: "field-security", label: "Field Security", path: "/admin/field-security", icon: LockKeyhole },
  { key: "record-sharing", label: "Record Sharing", path: "/admin/record-sharing", icon: Network },
  { key: "data-sharing", label: "Data Sharing", path: "/admin/data-sharing", icon: SlidersHorizontal },
  { key: "ip-restrictions", label: "IP Rules", path: "/admin/ip-restrictions", icon: ShieldCheck },
  { key: "audit-logs", label: "Audit", path: "/admin/audit-logs", icon: FileSearch },
  { key: "import", label: "Import", path: "/admin/import", icon: Upload },
  { key: "duplicates", label: "Duplicates", path: "/admin/duplicates", icon: GitMerge },
  { key: "export-control", label: "Export Control", path: "/admin/export-control", icon: Download },
  { key: "backups", label: "Backups", path: "/admin/backups", icon: DatabaseBackup },
  { key: "compliance", label: "Compliance", path: "/admin/compliance", icon: ShieldCheck },
  { key: "data-retention", label: "Retention", path: "/admin/data-retention", icon: RefreshCw },
];

function activeSection(pathname: string): Section {
  const match = sections.find((section) => pathname === section.path || pathname.startsWith(`${section.path}/`));
  return match?.key || "security";
}

function errorText(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } })?.response;
  return response?.data?.detail || "Request failed";
}

export default function AdminSecurityPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">CRM Phase 8</p>
        <h1 className="text-2xl font-semibold">Enterprise Security and Data Governance</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Profiles, roles, field security, record sharing, audited imports, duplicate control, exports, backups, compliance, and retention controls.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
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
        {active === "security" ? <SecurityOverview /> : null}
        {active === "profiles" ? <Profiles /> : null}
        {active === "roles" ? <Roles /> : null}
        {active === "field-security" ? <FieldSecurity /> : null}
        {active === "record-sharing" ? <RecordSharing /> : null}
        {active === "data-sharing" ? <DataSharing /> : null}
        {active === "ip-restrictions" ? <IPRestrictions /> : null}
        {active === "audit-logs" ? <AuditLogs /> : null}
        {active === "import" ? <ImportWizard /> : null}
        {active === "duplicates" ? <DuplicateManagement /> : null}
        {active === "export-control" ? <ExportControl /> : null}
        {active === "backups" ? <Backups /> : null}
        {active === "compliance" ? <Compliance /> : null}
        {active === "data-retention" ? <Retention /> : null}
      </div>
    </div>
  );
}

function useInvalidate(key: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: [key] });
}

function SecurityOverview() {
  const query = useQuery({ queryKey: ["admin-security-overview"], queryFn: adminSecurityApi.overview });
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {Object.entries(query.data || {}).map(([key, value]) => (
        <Card key={key}>
          <CardContent className="p-4">
            <p className="text-sm capitalize text-muted-foreground">{key.replace(/_/g, " ")}</p>
            <p className="mt-2 text-2xl font-semibold">{String(value)}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Profiles() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-profiles");
  const query = useQuery({ queryKey: ["admin-profiles"], queryFn: adminSecurityApi.profiles });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createProfile({ name: `Sales Profile ${Date.now()}`, description: "Phase 8 governed sales profile", active: true }),
    onSuccess: (profile) => {
      adminSecurityApi.setProfilePermissions(Number(profile.id), ["admin_security_view", "admin_audit_view"]);
      toast({ title: "Profile created" });
      refresh();
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  return <ListSection title="Profiles and permission sets" description="Profiles carry permission bundles and are consumed by backend FLS/import enforcement." query={query} action="Create profile" onAction={() => create.mutate()} />;
}

function Roles() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-roles");
  const query = useQuery({ queryKey: ["admin-roles"], queryFn: adminSecurityApi.roles });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createRole({ name: `Regional Sales Manager ${Date.now()}`, description: "Team hierarchy role", active: true }),
    onSuccess: () => {
      toast({ title: "Role created" });
      refresh();
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  return <ListSection title="Roles and hierarchy" description="Roles support reporting hierarchy and profile assignment for CRM visibility." query={query} action="Create role" onAction={() => create.mutate()} />;
}

function FieldSecurity() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-field-security");
  const query = useQuery({ queryKey: ["admin-field-security"], queryFn: adminSecurityApi.fieldSecurity });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createFieldSecurity({ module_name: "leads", field_name: "annual_revenue", profile_id: 1, can_view: true, can_edit: false, mask_value: true }),
    onSuccess: () => {
      toast({ title: "Field rule saved" });
      refresh();
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  const validate = useMutation({
    mutationFn: () => adminSecurityApi.validateFieldUpdate({ module_name: "leads", record: { annual_revenue: 1000000 } }),
    onSuccess: () => toast({ title: "Field update accepted" }),
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  return <ListSection title="Field-level security" description="Hidden, read-only, and masked CRM fields are enforced by backend helpers and import validation." query={query} action="Add read-only rule" onAction={() => create.mutate()}><Button variant="outline" onClick={() => validate.mutate()}>Validate field update</Button></ListSection>;
}

function RecordSharing() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-record-sharing");
  const query = useQuery({ queryKey: ["admin-record-sharing"], queryFn: adminSecurityApi.recordSharingRules });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createRecordSharingRule({ module_name: "deals", rule_name: "Share enterprise deals", condition_json: { segment: "enterprise" }, share_with_type: "role", share_with_id: 1, access_level: "read", active: true }),
    onSuccess: () => {
      toast({ title: "Sharing rule saved" });
      refresh();
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  const share = useMutation({
    mutationFn: () => adminSecurityApi.shareRecord({ module_name: "deals", record_id: 100, share_with_type: "user", share_with_id: 1, access_level: "read" }),
    onSuccess: () => toast({ title: "Record shared" }),
  });
  return <ListSection title="Record sharing" description="Rules and manual shares govern explicit record visibility." query={query} action="Create sharing rule" onAction={() => create.mutate()}><Button variant="outline" onClick={() => share.mutate()}>Manual share</Button></ListSection>;
}

function DataSharing() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-data-sharing");
  const query = useQuery({ queryKey: ["admin-data-sharing"], queryFn: adminSecurityApi.dataSharingRules });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createDataSharingRule({ module_name: "accounts", name: "Branch data policy", rule_json: { branch: "west" }, access_level: "read", active: true }),
    onSuccess: () => {
      toast({ title: "Data sharing rule saved" });
      refresh();
    },
  });
  return <ListSection title="Data sharing rules" description="Cross-team and branch data sharing rules are stored separately from CRM operational records." query={query} action="Create data rule" onAction={() => create.mutate()} />;
}

function IPRestrictions() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-ip-restrictions");
  const query = useQuery({ queryKey: ["admin-ip-restrictions"], queryFn: adminSecurityApi.ipRestrictions });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createIpRestriction({ cidr: "203.0.113.0/24", action: "allow", description: "Office network", active: true, environment_safe: true }),
    onSuccess: () => {
      toast({ title: "IP rule saved" });
      refresh();
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  return <ListSection title="IP restrictions" description="Unsafe deny-all rules are blocked by backend validation." query={query} action="Add allow rule" onAction={() => create.mutate()} />;
}

function AuditLogs() {
  const query = useQuery({ queryKey: ["admin-audit-logs"], queryFn: adminSecurityApi.auditLogs });
  return <ListSection title="Audit logs" description="Profile, role, sharing, import, duplicate, export, backup, and compliance actions write audit evidence." query={query}><Button variant="outline" onClick={() => window.open("/api/v1/admin/audit-logs/export", "_blank", "noopener,noreferrer")}>Export audit CSV</Button></ListSection>;
}

function ImportWizard() {
  const { toast } = useToast();
  const [jobId, setJobId] = useState<number | null>(null);
  const upload = useMutation({
    mutationFn: () => adminSecurityApi.importsUpload({ module_name: "leads", filename: "phase8-leads.csv", rows: [{ company_name: "Phase 8 Lead", email: "phase8@example.com", status: "New" }] }),
    onSuccess: (job) => {
      setJobId(Number(job.id));
      toast({ title: "Import uploaded" });
    },
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  const map = useMutation({
    mutationFn: () => adminSecurityApi.importsMap(Number(jobId), { mapping: { company_name: "company_name", email: "email", status: "status" } }),
    onSuccess: () => toast({ title: "Fields mapped" }),
  });
  const run = useMutation({
    mutationFn: () => adminSecurityApi.importsRun(Number(jobId)),
    onSuccess: (job) => toast({ title: `Import ${String(job.status)}` }),
    onError: (error) => toast({ title: errorText(error), variant: "destructive" }),
  });
  const errors = useQuery({ queryKey: ["admin-import-errors", jobId], queryFn: () => adminSecurityApi.importErrors(Number(jobId)), enabled: Boolean(jobId) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => upload.mutate()}>Upload CSV</Button>
        <Button variant="outline" disabled={!jobId} onClick={() => map.mutate()}>Map fields</Button>
        <Button variant="outline" disabled={!jobId} onClick={() => run.mutate()}>Run import</Button>
      </div>
      <ListCard title="Import errors and duplicate rows" items={errors.data?.items || []} />
    </div>
  );
}

function DuplicateManagement() {
  const { toast } = useToast();
  const refreshRules = useInvalidate("admin-duplicate-rules");
  const rules = useQuery({ queryKey: ["admin-duplicate-rules"], queryFn: adminSecurityApi.duplicateRules });
  const candidates = useQuery({ queryKey: ["admin-duplicate-candidates"], queryFn: adminSecurityApi.duplicateCandidates });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createDuplicateRule({ module_name: "leads", name: "Lead email duplicate", match_fields_json: ["email"], match_logic: "any", active: true }),
    onSuccess: () => {
      toast({ title: "Duplicate rule saved" });
      refreshRules();
    },
  });
  const scan = useMutation({ mutationFn: () => adminSecurityApi.scanDuplicates({ module_name: "leads" }), onSuccess: () => candidates.refetch() });
  const merge = useMutation({ mutationFn: () => adminSecurityApi.mergeDuplicates({ module_name: "leads", winner_record_id: 1, loser_record_ids: [2] }), onSuccess: () => toast({ title: "Merge log recorded" }) });
  return <div className="space-y-4"><div className="flex flex-wrap gap-2"><Button onClick={() => create.mutate()}>Create duplicate rule</Button><Button variant="outline" onClick={() => scan.mutate()}>Scan duplicates</Button><Button variant="outline" onClick={() => merge.mutate()}>Record merge</Button></div><ListCard title="Duplicate rules" items={rules.data?.items || []} /><ListCard title="Duplicate candidates" items={candidates.data?.items || []} /></div>;
}

function ExportControl() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-export-controls");
  const query = useQuery({ queryKey: ["admin-export-controls"], queryFn: adminSecurityApi.exportControls });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createExportControl({ module_name: "deals", max_rows: 5000, require_approval: true, watermark: true, active: true }),
    onSuccess: () => {
      toast({ title: "Export control saved" });
      refresh();
    },
  });
  return <ListSection title="Export controls" description="Export row limits, approval requirements, and watermark policy are governed before downloads." query={query} action="Create export control" onAction={() => create.mutate()} />;
}

function Backups() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-backups");
  const query = useQuery({ queryKey: ["admin-backups"], queryFn: adminSecurityApi.backups });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.requestBackup({ scope: "crm" }),
    onSuccess: () => {
      toast({ title: "Backup request queued" });
      refresh();
    },
  });
  return <ListSection title="Backup and restore requests" description="Backup requests are auditable and non-destructive from the admin UI." query={query} action="Request CRM backup" onAction={() => create.mutate()} />;
}

function Compliance() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-compliance");
  const query = useQuery({ queryKey: ["admin-compliance"], queryFn: adminSecurityApi.compliance });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.upsertCompliance({ setting_key: "consent_required", setting_value_json: { enabled: true, region: "IN" }, active: true }),
    onSuccess: () => {
      toast({ title: "Compliance setting saved" });
      refresh();
    },
  });
  return <ListSection title="Compliance settings" description="Consent, privacy, and data governance settings are maintained as auditable records." query={query} action="Save consent policy" onAction={() => create.mutate()} />;
}

function Retention() {
  const { toast } = useToast();
  const refresh = useInvalidate("admin-retention");
  const query = useQuery({ queryKey: ["admin-retention"], queryFn: adminSecurityApi.retention });
  const create = useMutation({
    mutationFn: () => adminSecurityApi.createRetention({ module_name: "leads", retention_days: 2555, action: "archive", active: true }),
    onSuccess: () => {
      toast({ title: "Retention rule saved" });
      refresh();
    },
  });
  return <ListSection title="Data retention" description="Retention and archival policy is explicit, versioned, and audit-ready." query={query} action="Create retention rule" onAction={() => create.mutate()} />;
}

function ListSection({ title, description, query, action, onAction, children }: { title: string; description: string; query: ReturnType<typeof useQuery<AdminSecurityList>>; action?: string; onAction?: () => void; children?: ReactNode }) {
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex flex-wrap gap-2">{children}{action ? <Button onClick={onAction}>{action}</Button> : null}</div>
      </div>
      {query.isError ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">Admin security data could not be loaded.</div> : null}
      <ListCard title={title} items={items} loading={query.isLoading} />
    </div>
  );
}

function ListCard({ title, items, loading = false }: { title: string; items: AdminSecurityRecord[]; loading?: boolean }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {loading ? <p className="text-sm text-muted-foreground">Loading governance data...</p> : null}
        {!loading && !items.length ? <p className="text-sm text-muted-foreground">No records yet.</p> : null}
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item, index) => (
            <div key={String(item.id || index)} className="rounded-md border p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium">{String(item.name || item.rule_name || item.setting_key || item.module_name || item.action || item.filename || `Record ${index + 1}`)}</p>
                <Badge variant="outline">{String(item.status || (item.active ?? "ready"))}</Badge>
              </div>
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(item, null, 2)}</pre>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
