import { useCallback, useEffect, useRef, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { workspaceError } from "../../pages/workspaceTypes";
import { peopleBase, peopleChanged, usePersonManagement, type Person, type Membership } from "./peopleTypes";
import { PersonIdentity } from "./PersonIdentity";
import AddExistingPeopleDialog from "./AddExistingPeopleDialog";

type Profile = { values: Record<string, string | null>; version: string; canEdit: boolean; field_permissions: Record<string, { can_view: boolean; can_edit: boolean; reason: string }> };
type Detail = Person & { workspaces: Membership[]; projects: Membership[]; access_sources: (Membership & { explanation?: string; capabilities?: string[]; scope?: string; policy_status?: string; module_enabled?: boolean })[]; permissions: Record<string, boolean>; unavailable_reasons: Record<string, string>; profile?: Profile; suspension?: { reason?: string; end_at?: string }; history: { id: number; action: string; actor: string; reason: string; created_at: string }[] };
type Action = { kind: "remove_project" | "remove_workspace" | "suspend" | "reactivate" | "offboard" | "terminate"; workspaceId?: number; projectId?: number };
type Preview = { version: string; tasks: { id: number; title: string; project_id: number }[]; projects: { id: number; name: string }[]; approvals: { id: number; title: string }[]; workflow_approvals: { id: number; status: string }[]; owned_workspace_ids: number[]; blockers: string[] };
const explanations = {
  remove_project: ["Remove from project", "Removes this project-team membership only. Shared workspace access and employment remain unchanged. Open work is transferred to the selected person."],
  remove_workspace: ["Remove from workspace", "Ends access to this workspace and its project teams. Your account and employment remain active. Open work needs a handover first."],
  suspend: ["Suspend account", "Blocks sign-in and revokes existing sessions across the account. Employment and memberships are retained. Transfer open work first; reactivate manually or choose an end date."],
  reactivate: ["Reactivate account", "Restores sign-in. Previously revoked sessions stay revoked. This does not restore memberships removed during offboarding."],
  offboard: ["Offboard and transfer work", "Transfers open tasks, project ownership, and pending approvals, removes team memberships in this organization, and suspends the account. This does not terminate employment."],
  terminate: ["Terminate employment", "Completes the handover, removes team memberships, revokes sign-in, and records Terminated on the HR employment record. Employment cannot be restored with Reactivate; use the HR rehire process."],
} as const;
const profileFields = [["preferred_display_name", "Display name"], ["first_name", "First name"], ["last_name", "Last name"], ["bio", "Bio"], ["timezone", "Timezone"], ["phone_number_country_code", "Phone country code"], ["phone_number", "Phone number"]] as const;

export default function PersonManagementHost() {
  const context = usePersonManagement(s => s.context);
  const close = usePersonManagement(s => s.close);
  const generation = useRef(0);
  const [person, setPerson] = useState<Detail>();
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [action, setAction] = useState<Action>();
  const [preview, setPreview] = useState<Preview>();
  const [replacement, setReplacement] = useState(0);
  const [candidates, setCandidates] = useState<Person[]>([]);
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");
  const [endAt, setEndAt] = useState("");
  const [draft, setDraft] = useState<Record<string, string | null>>({});
  const load = useCallback(async () => {
    if (!context) return;
    const request = ++generation.current;
    const { data } = await api.get<Detail>(`${peopleBase}/${context.userId}`);
    if (request !== generation.current) return;
    setPerson(data); setDraft(data.profile?.values || {});
  }, [context]);
  useEffect(() => {
    let active = true;
    setTab("Overview"); setAction(undefined); setPreview(undefined); setNotice(""); setAddOpen(false);
    setPerson(undefined); setError(""); setLoading(!!context);
    if (context) void load().catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; generation.current++; };
  }, [context, load]);
  const prepare = async (next: Action) => {
    if (!context) return;
    setTab("Actions"); setAction(next); setPreview(undefined); setReplacement(0); setReason(""); setEndAt(""); setSearch(""); setError(""); setBusy(true);
    try {
      const requests = [api.get<{ items: Person[] }>(`${peopleBase}/directory`, { params: { status: "active", ...(next.workspaceId || context.workspaceId ? { workspace_id: next.workspaceId || context.workspaceId } : context.projectId ? { project_id: context.projectId } : {}) } })];
      const [people] = await Promise.all(requests); setCandidates(people.data.items.filter(p => p.id !== context.userId));
      if (next.kind !== "reactivate") setPreview((await api.get<Preview>(`${peopleBase}/${context.userId}/preview`, { params: { workspace_id: next.workspaceId, project_id: next.projectId } })).data);
    } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  };
  const apply = async () => {
    if (!context || !action) return;
    setBusy(true); setError("");
    try {
      const { data } = await api.post(`${peopleBase}/${context.userId}/actions`, { action: action.kind, reason, workspace_id: action.workspaceId, project_id: action.projectId, replacement_user_id: replacement || undefined, end_at: endAt ? new Date(endAt).toISOString() : undefined, preview_version: preview?.version });
      setNotice(data.message); setAction(undefined); setPreview(undefined); peopleChanged(); await load();
    } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  };
  const hasImpact = !!preview && !!(preview.tasks.length || preview.projects.length || preview.approvals.length || preview.workflow_approvals.length);
  return <><Dialog open={!!context} onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent overlayClassName="z-[100]" className="z-[101] max-h-[92dvh] max-w-4xl overflow-y-auto"><DialogTitle className="text-xl font-semibold">Manage person</DialogTitle>
    {error && <p role="alert" className="rounded border border-destructive p-3 text-sm text-destructive">{error}</p>}{notice && <p role="status" className="rounded border border-emerald-300 p-3 text-sm">{notice}</p>}
    {loading ? <p role="status">Loading person and effective access…</p> : person && <>
      <div className="flex flex-wrap items-center justify-between gap-3"><PersonIdentity person={person} /><span className="rounded-full border px-3 py-1 text-xs capitalize">{person.status}</span></div>
      {person.suspension?.reason && <p className="rounded border p-3 text-sm">Suspension: {person.suspension.reason}{person.suspension.end_at && <> · Reactivates on the first fresh sign-in after {new Date(person.suspension.end_at).toLocaleString()}</>}</p>}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Person management sections">{["Overview", "Profile", "Access", "History", "Actions"].map(name => <button type="button" role="tab" aria-selected={tab === name} className={`rounded border px-3 py-2 text-sm ${tab === name ? "bg-primary text-primary-foreground" : ""}`} onClick={() => setTab(name)} key={name}>{name}</button>)}</div>
      {tab === "Overview" && <div className="space-y-4"><Button disabled={!person.permissions.memberships || busy || person.status !== "active"} onClick={() => setAddOpen(true)}>Add existing person to workspace / project</Button>{!person.permissions.memberships && <p className="text-xs text-muted-foreground">{person.unavailable_reasons.memberships}</p>}
        <section><h3 className="font-semibold">Workspaces · {person.workspaces.length}</h3>{person.workspaces.map(m => <div className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm" key={m.id}><span>{m.name} · {m.role}</span><div><Button size="sm" variant="outline" disabled={m.can_remove === false || !person.permissions.memberships || m.role === "Owner" || busy} onClick={() => void prepare({ kind: "remove_workspace", workspaceId: m.workspace_id })}>Remove from workspace</Button>{m.can_remove === false && <p className="mt-1 text-xs text-muted-foreground">{m.unavailable_reason}</p>}</div></div>)}</section>
        <section><h3 className="font-semibold">Project teams · {person.projects.length}</h3>{person.projects.map(m => <div className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm" data-project-id={m.project_id} key={m.id}><span>{m.name} · {m.role}<small className="block text-muted-foreground">{person.workspaces.find(w => w.workspace_id === m.workspace_id)?.name || "Organization project"}</small></span><Button size="sm" variant="outline" disabled={m.can_remove === false || !person.permissions.memberships || busy} onClick={() => void prepare({ kind: "remove_project", projectId: m.project_id })}>Remove from project</Button>{m.can_remove === false && <p className="text-xs text-muted-foreground">{m.unavailable_reason}</p>}</div>)}</section><p className="text-xs text-muted-foreground">Removing a project team membership does not revoke access inherited from a shared workspace. Remove workspace membership to end that access.</p></div>}
      {tab === "Profile" && <div className="space-y-3"><p className="text-sm">Only fields permitted by your HR profile and field-level permissions can be edited here. Login email and organization roles require their dedicated administration flows.</p>{person.profile ? <form className="space-y-3" onSubmit={async e => { e.preventDefault(); setBusy(true); setError(""); try { const values = Object.fromEntries(Object.entries(draft).filter(([k, v]) => v !== person.profile?.values[k] && person.profile?.field_permissions[k]?.can_edit)); await api.patch(`${peopleBase}/${person.id}/profile`, { values, version: person.profile!.version, reason }); setNotice("Profile updated"); peopleChanged(); await load(); } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); } }}><div className="grid gap-3 sm:grid-cols-2">{profileFields.map(([key, label]) => {
        const permission = person.profile!.field_permissions[key];
        return <label className="block text-sm" key={key}>{label}<Input aria-label={`Person ${label}`} disabled={busy || !permission?.can_edit} value={permission?.can_view ? draft[key] || "" : "Hidden by field permissions"} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /><small className="text-muted-foreground">{permission?.can_edit ? "Editable" : "Read only"} · {permission?.reason}</small></label>;
      })}</div><label className="block text-sm">Reason for profile edit<Input required minLength={3} value={reason} onChange={e => setReason(e.target.value)} /></label><Button disabled={busy || !person.permissions.profile}>Save permitted fields</Button></form> : <p className="rounded border p-3 text-sm">{person.unavailable_reasons.profile}</p>}</div>}
      {tab === "Access" && <section className="space-y-3"><h3 className="font-semibold">Effective access and its source</h3><p className="text-sm text-muted-foreground">Permissions combine these sources within their assigned organization and scope. A project role does not remove access inherited from the workspace.</p>{person.access_sources.map((s, i) => <article className="rounded border p-3 text-sm" key={i}><strong>{s.source}</strong><p>{s.name || "Organization"} · {s.role}</p>{s.explanation && <p className="text-xs text-muted-foreground">{s.explanation}</p>}{s.scope && <p className="text-xs">Scope: {s.scope}</p>}{s.policy_status && <p className="text-xs">Organization access: {s.policy_status}{s.module_enabled === false ? " · PMS is disabled by policy" : ""}</p>}{!!s.capabilities?.length && <p className="mt-1 text-xs text-muted-foreground">Effective permissions: {s.capabilities.join(", ")}</p>}</article>)}</section>}
      {tab === "History" && <section className="space-y-3"><h3 className="font-semibold">Membership and access-change history</h3>{!person.history.length && <p className="text-sm text-muted-foreground">No recorded changes are visible within your assigned scope.</p>}{person.history.map(h => <article className="rounded border p-3 text-sm" key={h.id}><strong>{h.action.replace(/_/g, " ")}</strong><p>{h.reason}</p><small className="text-muted-foreground">{h.actor} · {new Date(h.created_at).toLocaleString()}</small></article>)}</section>}
      {tab === "Actions" && <div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2">{(["suspend", "reactivate", "offboard", "terminate"] as const).map(kind => {
        const allowed = person.permissions[kind] && (kind === "reactivate" ? person.status === "suspended" : person.status === "active");
        return <article className="rounded border p-3" key={kind}><strong className="text-sm">{explanations[kind][0]}</strong><p className="my-2 text-xs text-muted-foreground">{explanations[kind][1]}</p><Button size="sm" variant="outline" disabled={!allowed || busy} onClick={() => void prepare({ kind })}>{explanations[kind][0]}</Button>{!allowed && <p className="mt-2 text-xs text-muted-foreground">{person.status === "terminated" ? "Terminated employment requires the HR rehire process." : person.status !== "active" && kind !== "reactivate" ? "This account is already inactive." : person.unavailable_reasons[kind] || person.unavailable_reasons.lifecycle}</p>}</article>;
      })}</div>
        {action && <section aria-label="Affected assignments preview" className="space-y-3 rounded-xl border border-amber-300 p-4"><h3 className="font-semibold">{explanations[action.kind][0]} · Review before applying</h3><p className="text-sm">{explanations[action.kind][1]}</p>{busy && !preview && action.kind !== "reactivate" && <p role="status">Loading affected assignments…</p>}{preview && <><p className="text-sm">{preview.tasks.length} open tasks · {preview.projects.length} owned/managed projects · {preview.approvals.length + preview.workflow_approvals.length} pending approvals</p><div className="max-h-44 overflow-auto text-sm">{preview.tasks.map(t => <p key={`t${t.id}`}>Task: {t.title}</p>)}{preview.projects.map(p => <p key={`p${p.id}`}>Ownership: {p.name}</p>)}{preview.approvals.map(a => <p key={`a${a.id}`}>Approval: {a.title}</p>)}{preview.workflow_approvals.map(a => <p key={`w${a.id}`}>Workflow approval #{a.id}</p>)}</div>{!!preview.owned_workspace_ids.length && action.kind !== "suspend" && <p className="text-sm text-destructive">Transfer ownership of the listed workspaces before offboarding or removing the owner.</p>}{preview.blockers.map((b, i) => <p className="text-sm text-destructive" key={i}>{b}</p>)}</>}
          {hasImpact && <div><h4 className="text-sm font-medium">Transfer open work to an eligible active person</h4><p className="text-xs text-muted-foreground">The replacement must already be a Member of affected workspaces. Project ownership requires administrative access; pending approvals require an authorized Admin/HR approver.</p><Input aria-label="Search handover people" placeholder="Search name, email or role" value={search} onChange={e => setSearch(e.target.value)} /><div className="mt-2 max-h-48 overflow-auto">{candidates.filter(p => `${p.name} ${p.email} ${p.role}`.toLowerCase().includes(search.toLowerCase())).map(p => <label className="flex items-center gap-2 rounded border p-2" key={p.id}><input name="handover-person" type="radio" checked={replacement === p.id} onChange={() => setReplacement(p.id)} /><PersonIdentity person={p} /></label>)}</div></div>}
          <label className="block text-sm">Reason<Input required minLength={3} aria-label="Person action reason" value={reason} onChange={e => setReason(e.target.value)} /></label>{action.kind === "suspend" && <label className="block text-sm">Optional suspension end date<Input aria-label="Suspension end date" type="datetime-local" value={endAt} onChange={e => setEndAt(e.target.value)} /><small className="text-muted-foreground">The account reactivates on the first fresh sign-in after this time. Leave blank for manual reactivation.</small></label>}
          <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={() => setAction(undefined)}>Cancel</Button><Button disabled={busy || reason.trim().length < 3 || (action.kind !== "reactivate" && !preview) || (hasImpact && !replacement) || !!preview?.blockers.length || (!!preview?.owned_workspace_ids.length && ["remove_workspace", "offboard", "terminate"].includes(action.kind))} onClick={() => void apply()}>{busy ? "Applying…" : `Apply: ${explanations[action.kind][0]}`}</Button></div>
        </section>}
      </div>}
    </>}
  </DialogContent></Dialog><AddExistingPeopleDialog open={addOpen && !!person} onClose={() => setAddOpen(false)} workspaceId={context?.workspaceId} projectId={context?.projectId} personIds={person ? [person.id] : []} onAdded={load} /></>;
}
