import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { ManagePersonButton, PersonIdentity } from "../components/people/PersonIdentity";
import { openPerson } from "../components/people/peopleTypes";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Copy, Mail, Plus, RefreshCw, Users } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePageRefresh } from "@/lib/page-refresh";
import InvitationInbox from "../components/InvitationInbox";
import { workspaceError } from "./workspaceTypes";

type Workspace = { id: number; name: string; role: string };
type Project = { id: number; name: string; workspace_id?: number; can_manage_members?: boolean; can_edit_project?: boolean };
type Person = { id: number; email: string; name?: string; photo_url?: string; role?: string; availability?: string };
type Member = { id: number; user_id: number; email: string; role: string; name?: string; photo_url?: string; availability?: string };
type Invite = { id: number; email: string; role: string; status: string; token?: string; expires_at: string };
const base = "/project-management";
const control = "min-h-10 rounded-md border bg-background px-3 py-2 text-sm";
const inviteUrl = (token: string) => `${window.location.origin}/pms/invitation?token=${encodeURIComponent(token)}`;

export default function MemberManagementPage() {
  const [params, setParams] = useSearchParams();
  const { projectId } = useParams();
  const wid = Number(params.get("workspace"));
  const pid = Number(projectId || params.get("project"));
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project>();
  const [members, setMembers] = useState<Member[]>([]);
  const [workspaceMembers, setWorkspaceMembers] = useState<Member[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [invitations, setInvitations] = useState<Invite[]>([]);
  const [query, setQuery] = useState(params.get("email") || "");
  const [role, setRole] = useState("Member");
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("Member");
  const generation = useRef(0);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const workspace = workspaces.find(w => w.id === wid);
  const managesWorkspace = workspace?.role === "Owner" || workspace?.role === "Admin";
  const canManage = pid ? !!(project?.can_manage_members || (project?.workspace_id && managesWorkspace) || (!project?.workspace_id && project?.can_edit_project)) : managesWorkspace;
  const roles = pid ? ["Member", "Viewer", "Lead", "Manager", "Admin"] : ["Member", "Guest", ...(workspace?.role === "Owner" ? ["Admin"] : [])];
  const choose = (workspace: number, project = 0) => {
    setQuery(params.get("email") || ""); setNotice(""); setRole("Member");
    setParams({ ...(workspace ? { workspace: String(workspace) } : {}), ...(project ? { project: String(project) } : {}), ...(params.get("email") ? { email: params.get("email")! } : {}) });
  };
  useEffect(() => {
    let active = true;
    void api.get<Workspace[]>(`${base}/workspaces`).then(r => {
      if (!active) return;
      setWorkspaces(r.data);
      if (!wid && !pid && r.data.length) setParams(p => { const next = new URLSearchParams(p); next.set("workspace", String(r.data[0].id)); return next; }, { replace: true });
    }).catch(e => { if (active) { setError(workspaceError(e)); setLoading(false); } });
    return () => { active = false; };
  }, [wid, pid, setParams]);
  const load = useCallback(async () => {
    const request = ++generation.current;
    const selectedProject = pid ? (await api.get<Project>(`${base}/projects/${pid}`)).data : undefined;
    if (request !== generation.current) return;
    setProject(selectedProject);
    const workspaceId = selectedProject?.workspace_id || wid;
    if (selectedProject?.workspace_id && wid !== selectedProject.workspace_id) {
      setParams(p => { const next = new URLSearchParams(p); next.set("workspace", String(selectedProject.workspace_id)); return next; }, { replace: true });
      return;
    }
    if (!workspaceId && !pid) { setMembers([]); setPeople([]); setInvitations([]); return; }
    const actor = workspaces.find(w => w.id === workspaceId);
    const admin = actor?.role === "Owner" || actor?.role === "Admin";
    const [wm, pm, directory, invites, library] = await Promise.all([
      workspaceId ? api.get<Member[]>(`${base}/workspaces/${workspaceId}/members`) : Promise.resolve({ data: [] as Member[] }),
      pid ? api.get<Member[]>(`${base}/projects/${pid}/members`) : Promise.resolve({ data: [] as Member[] }),
      workspaceId && admin ? api.get<Person[]>(`${base}/workspaces/${workspaceId}/eligible-people`) : !workspaceId && selectedProject?.can_edit_project ? api.get<{ items: Person[] }>("/users/directory", { params: { page_size: 200 } }).then(r => ({ data: r.data.items })) : Promise.resolve({ data: [] as Person[] }),
      workspaceId && admin ? api.get<Invite[]>(`${base}/workspaces/${workspaceId}/invitations`) : Promise.resolve({ data: [] as Invite[] }),
      workspaceId ? api.get<{ projects: Project[] }>(`${base}/workspaces/${workspaceId}/overview`).then(r => ({ data: r.data.projects })) : Promise.resolve({ data: [] as Project[] }),
    ]);
    if (request !== generation.current) return;
    setWorkspaceMembers(wm.data); setMembers(pid ? pm.data : wm.data); setPeople(directory.data); setInvitations(invites.data); setProjects(library.data);
  }, [wid, pid, workspaces, setParams]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setMembers([]); setPeople([]); setInvitations([]);
    void load().catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; generation.current++; };
  }, [load]);
  usePageRefresh(load);
  useEffect(() => { const changed = () => { void load().catch(e => setError(workspaceError(e))); }; window.addEventListener("pms:people-changed", changed); return () => window.removeEventListener("pms:people-changed", changed); }, [load]);
  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); await load(); } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  };
  const copy = (token: string) => { void navigator.clipboard.writeText(inviteUrl(token)).then(() => setNotice("Invitation link copied")).catch(() => setError("Copy was unavailable. Select and copy the link below.")); };
  const candidates = people.filter(p => !members.some(m => m.user_id === p.id) && (!query || `${p.name || ""} ${p.email}`.toLowerCase().includes(query.toLowerCase())));
  return <div className="mx-auto max-w-6xl space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="page-title">Members & invitations</h1><p className="page-description">Add registered people directly. Invite new people by email and track their acceptance here.</p></div><div className="flex flex-wrap gap-2"><Button disabled={!canManage} onClick={() => setAdding(true)}>Add existing person</Button><Button asChild variant="outline"><Link to="/pms/people">Open people directory</Link></Button><a className="self-center text-sm underline" href="#invitations">Invite by email</a></div></header>
    <InvitationInbox />
    <section aria-label="Membership destination" className="flex flex-wrap items-end gap-4 rounded-xl border bg-card p-4">
      <label className="grid gap-2 text-sm">Workspace<select className={control} aria-label="Manage workspace" disabled={busy || !!projectId} value={wid || ""} onChange={e => choose(Number(e.target.value))}><option value="">Choose workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label>
      <label className="grid gap-2 text-sm">Project (optional)<select className={control} aria-label="Manage project" disabled={busy || !!projectId} value={pid || ""} onChange={e => choose(wid, Number(e.target.value))}><option value="">Workspace members</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}{project && !projects.some(p => p.id === project.id) && <option value={project.id}>{project.name}</option>}</select></label>
      <Button variant="outline" disabled={busy || loading} onClick={() => void act(async () => {})}><RefreshCw size={15} />Refresh</Button>
    </section>
    {error && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{error}</p>}
    {notice && <p role="status" className="rounded border border-emerald-300 bg-emerald-50 p-3 text-emerald-900">{notice}</p>}
    {loading ? <p role="status">Loading members…</p> : !wid && !pid ? <p>Create or join a workspace to manage its members. <Link className="underline" to="/pms/workspaces">Open workspaces</Link></p> : <>
      <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="text-lg font-semibold"><Users className="mr-2 inline" size={19} />{project?.name || workspace?.name} · {pid ? "Project team" : "Workspace members"} ({members.length})</h2>
        <p className="text-sm text-muted-foreground">{pid ? "Project teams organize responsibility. Workspace members retain their existing access to shared workspace projects." : "Owners and authorized scoped Admin/HR roles manage membership. Only the workspace owner can appoint admins. Members collaborate; guests can view work."}</p>
        {!canManage && <p className="text-sm">Ask a scoped organization Admin/HR or workspace owner/admin to add people or change roles.</p>}
        {!members.length && <p className="text-sm">No project team members yet. Add people below.</p>}
        {members.map(m => {
          const editable = canManage && (pid || (m.role !== "Owner" && (workspace?.role === "Owner" || m.role !== "Admin")));
          const path = pid ? `${base}/projects/${pid}/members/${m.id}` : `${base}/workspaces/${wid}/members/${m.id}`;
          return <div className="flex flex-wrap items-center justify-between gap-3 border-t py-3" key={m.id}><PersonIdentity person={m} /><div className="flex flex-wrap items-center gap-3"><ManagePersonButton userId={m.user_id} workspaceId={wid || undefined} projectId={pid || undefined} />{editable ? <select className={control} aria-label={`Role for ${m.email}`} disabled={busy} value={m.role} onChange={e => void act(async () => { await api.patch(path, { role: e.target.value }); setNotice("Member role updated"); })}>{[...new Set([...roles, m.role])].map(r => <option key={r}>{r}</option>)}</select> : <span className="text-sm">{m.role}</span>}{editable && <Button variant="outline" disabled={busy} onClick={() => openPerson({ userId: m.user_id, workspaceId: wid || undefined, projectId: pid || undefined })}>Preview removal / reassign</Button>}</div></div>;
        })}
      </section>
      {canManage && <section aria-label="Add registered people" className="space-y-4 rounded-xl border bg-card p-4"><h2 className="text-lg font-semibold">Add from directory</h2><p className="text-sm text-muted-foreground">Registered people join immediately. {pid ? "People outside this workspace will also be added as workspace members in the same step." : "No invitation token or acceptance is needed."}</p><div className="flex flex-wrap gap-3"><Input aria-label="Find people to add" className="max-w-md" placeholder="Search name or email…" value={query} onChange={e => setQuery(e.target.value)} /><label className="flex items-center gap-2 text-sm">Add with role<select className={control} aria-label="New member role" value={role} disabled={busy} onChange={e => setRole(e.target.value)}>{roles.map(r => <option key={r}>{r}</option>)}</select></label></div><div className="max-h-80 overflow-y-auto">{!candidates.length && <p className="text-sm">No matching people available to add. Try another email or send an invitation below.</p>}{candidates.map(p => <div className="flex flex-wrap items-center justify-between gap-3 border-t py-3" key={p.id}><span className="break-all text-sm">{p.name && <strong className="block">{p.name}</strong>}{p.email}<small className="block text-muted-foreground">{workspaceMembers.some(m => m.user_id === p.id) ? "Already in workspace" : pid ? "Will also join workspace as Member" : "Registered account"}</small></span><Button disabled={busy} onClick={() => void act(async () => { await api.post(pid ? `${base}/projects/${pid}/members` : `${base}/workspaces/${wid}/members`, { user_id: p.id, role, ...(pid ? { add_to_workspace: true } : {}) }); setNotice(`${p.email} added to ${pid ? "project team" : "workspace"}`); })}><Plus size={15} />{pid ? "Add to project" : "Add to workspace"}</Button></div>)}</div></section>}
      {managesWorkspace && <section id="invitations" aria-label="Manage invitations" className="space-y-4 rounded-xl border bg-card p-4"><h2 className="text-lg font-semibold"><Mail className="mr-2 inline" size={19} />Workspace invitations</h2><p className="text-sm text-muted-foreground">Email is queued and registered recipients receive an in-app notification. Invitations expire after 7 days. After acceptance, add them to a project above.</p><form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void act(async () => { await api.post(`${base}/workspaces/${wid}/invitations`, { email, role: inviteRole === "Admin" && workspace?.role !== "Owner" ? "Member" : inviteRole }); setEmail(""); setNotice("Invitation created. Copy the link below or resend it anytime."); }); }}><label className="grid flex-1 gap-2 text-sm">Invite by email<Input type="email" aria-label="Invitation email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="new.teammate@company.com" /></label><label className="grid gap-2 text-sm">Invitation role<select className={control} aria-label="Invitation workspace role" value={inviteRole} disabled={busy} onChange={e => setInviteRole(e.target.value)}>{["Member", "Guest", ...(workspace?.role === "Owner" ? ["Admin"] : [])].map(r => <option key={r}>{r}</option>)}</select></label><Button disabled={busy}>Send workspace invitation</Button></form>
        {!invitations.length && <p className="text-sm">No invitations yet.</p>}
        {invitations.map(i => <article className="space-y-2 rounded-lg border p-3" key={i.id}><div className="flex flex-wrap justify-between gap-3"><div className="break-all text-sm"><strong>{i.email}</strong><p>{i.role} · {i.status} · Expires {new Date(i.expires_at + "Z").toLocaleDateString()}</p></div><div className="flex flex-wrap gap-2">{i.token && <Button variant="outline" disabled={busy} onClick={() => copy(i.token!)}><Copy size={14} />Copy invite link</Button>}{i.status !== "accepted" && i.status !== "revoked" && <Button variant="outline" disabled={busy} onClick={() => void act(async () => { await api.post(`${base}/workspaces/${wid}/invitations/${i.id}/resend`); setNotice("Invitation resent. A new link is ready; the previous link is invalid."); })}>Resend invitation</Button>}{i.status === "pending" && <Button variant="outline" disabled={busy} onClick={() => void act(async () => { await api.delete(`${base}/workspaces/${wid}/invitations/${i.id}`); setNotice("Invitation revoked"); })}>Revoke</Button>}</div></div>{i.token ? <><Input aria-label={`Invite link for ${i.email}`} readOnly value={inviteUrl(i.token)} onFocus={e => e.target.select()} /><details><summary className="cursor-pointer text-xs">Show invitation token</summary><code className="mt-2 block break-all text-xs">{i.token}</code></details></> : i.status === "pending" && <p className="text-xs text-muted-foreground">This older link cannot be recovered. Resend to generate a new shareable invitation.</p>}</article>)}
      </section>}
    </>}
    <AddExistingPeopleDialog open={adding} onClose={() => setAdding(false)} workspaceId={wid || undefined} projectId={pid || undefined} onAdded={async () => { await load(); setNotice("Existing people added directly"); }} />
  </div>;
}
