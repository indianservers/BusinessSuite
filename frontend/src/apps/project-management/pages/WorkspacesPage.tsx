import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { CalendarDays, Gauge, ArrowLeft, ArrowUpRight, CheckCircle2, ChevronDown, ChevronRight, Copy, Folder, LayoutGrid, List, Loader2, Plus, Search, ShieldCheck, Sparkles, Users, LogOut, X } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { projectsAPI } from "../services/api";
import { usePMSRealtime, useRealtimeStore } from "../realtime";
import CreateTaskModal from "../components/CreateTaskModal";
import { WorkspaceWork, TaskDrawer, WorkspaceAvatar } from "./WorkspaceWork";
import { type WorkspaceMember, type WorkspaceProject, type WorkTask, personName, workspaceBase as base, tones, taskBucket, taskAssignees, workspaceError } from "./workspaceTypes";
import "./workspaces.css";
import WorkspaceActivity from "./WorkspaceActivity";
import WorkspacePlanning from "./WorkspacePlanning";
import WorkspaceCollaboration from "./WorkspaceCollaboration";
import AsyncProgress, { beginProgress } from "@/components/app/AsyncProgress";
import NewMenu from "@/components/app/NewMenu";
import { useSignOut } from "@/hooks/use-sign-out";

type Workspace = { id: number; name: string; role: string };
type Invitation = { id: number; email: string; role: string; status: string; account_exists?: boolean };
type View = "board" | "list" | "people" | "calendar" | "workload" | "activity";
type Modal = "workspace" | "invite" | "join" | "project" | null;

export default function WorkspacesPage() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuthStore();
  const requestedWorkspace = Number(params.get("workspace"));
  const signOut = useSignOut("/pms/login");
  const [filtersVersion, setFiltersVersion] = useState(0);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<number>();
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [tasks, setTasks] = useState<WorkTask[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [view, setView] = useState<View>("list");
  const [modal, setModal] = useState<Modal>(params.get("invite") ? "join" : null);
  const [name, setName] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [keyEdited, setKeyEdited] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Member");
  const [token, setToken] = useState(params.get("invite") || "");
  const [inviteLink, setInviteLink] = useState("");
  const [query, setQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [workspaceLoadFailed, setWorkspaceLoadFailed] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [taskOpen, setTaskOpen] = useState<number | null>(null);
  const [showTaskCreate, setShowTaskCreate] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const workspace = workspaces.find(w => w.id === selected);
  const manages = workspace?.role === "Owner" || workspace?.role === "Admin";
  const canEdit = !!workspace && workspace.role !== "Guest";
  const connected = useRealtimeStore(s => s.connected);
  const completed = tasks.filter(t => taskBucket(t.status) === "Done").length;
  const progress = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
  const assignablePeople = useMemo(() => members.filter(m => m.role !== "Guest").map(m => ({ id: m.user_id, email: m.email, name: personName(m.email) })), [members]);
  const createProjectId = Number(projectFilter) || projects[0]?.id;
  const loadWorkspaces = useCallback(async (preferred?: number) => {
    const { data } = await api.get<Workspace[]>(`${base}/workspaces`);
    const saved = Number(localStorage.getItem(`pms-workspace-${user?.id}`));
    setWorkspaceLoadFailed(false); setWorkspaces(data); setSelected(current => preferred || (data.some(w => w.id === requestedWorkspace) ? requestedWorkspace : data.some(w => w.id === current) ? current : data.some(w => w.id === saved) ? saved : data[0]?.id));
  }, [user?.id, requestedWorkspace]);
  useEffect(() => { if (selected && user?.id) localStorage.setItem(`pms-workspace-${user.id}`, String(selected)); }, [selected, user?.id]);
  const loadDetails = useCallback(async () => {
    if (!selected) return;
    const [people, overview, invites] = await Promise.all([
      api.get<WorkspaceMember[]>(`${base}/workspaces/${selected}/members`),
      api.get<{ projects: WorkspaceProject[]; tasks: WorkTask[]; role: string }>(`${base}/workspaces/${selected}/overview`),
      manages ? api.get<Invitation[]>(`${base}/workspaces/${selected}/invitations`) : Promise.resolve({ data: [] as Invitation[] }),
    ]);
    if (selectedRef.current !== selected) return;
    setWorkspaces(current => current.map(w => w.id === selected && w.role !== overview.data.role ? { ...w, role: overview.data.role } : w));
    setMembers(people.data); setProjects(overview.data.projects); setTasks(overview.data.tasks); setInvitations(invites.data);
  }, [selected, manages]);
  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    const finish = beginProgress(modal === "project" ? "Creating project" : modal === "workspace" ? "Creating workspace" : modal === "invite" ? "Preparing invitation" : "Saving changes");
    try { await action(); finish(); } catch (e) { finish(false); setError(workspaceError(e)); } finally { setBusy(false); }
  };
  useEffect(() => { const finish = beginProgress("Loading workspaces"); loadWorkspaces().then(() => finish()).catch(e => { finish(false); setWorkspaceLoadFailed(true); setError(workspaceError(e)); }).finally(() => setLoading(false)); }, [loadWorkspaces]);
  useEffect(() => {
    setMembers([]); setProjects([]); setTasks([]); setInvitations([]); setProjectFilter(""); setTaskOpen(null); setAssigneeFilter("");
    let active = true;
    setDetailsLoading(!!selected);
    const finish = selected ? beginProgress("Opening workspace") : undefined;
    void loadDetails().then(() => finish?.()).catch(e => { finish?.(false); if (active) setError(workspaceError(e)); }).finally(() => { if (active) setDetailsLoading(false); });
    return () => { active = false; };
  }, [loadDetails]);
  useEffect(() => { if (workspace?.role !== "Owner") setRole("Member"); }, [workspace?.role]);
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(""), 3500); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement)) { e.preventDefault(); searchRef.current?.focus(); } };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, []);
  usePMSRealtime({ onEvent: event => { if (/^(task\.|comment\.|project\.)/.test(event.type)) void loadDetails().catch(() => undefined); }, onFallbackPoll: () => { void loadDetails().catch(() => undefined); }, showToast: false });
  const openModal = (next: Modal) => { setName(""); setProjectKey(""); setKeyEdited(false); setInviteLink(""); setError(""); setModal(next); };
  async function updateTask(task: WorkTask, changes: Partial<WorkTask>) {
    if (!canEdit) return false;
    const workspaceId = selected;
    const finish = beginProgress("Saving task");
    setError(""); setTasks(current => current.map(t => t.id === task.id ? { ...t, ...changes } : t));
    try { await api.patch(`${base}/tasks/${task.id}`, changes); if (selectedRef.current === workspaceId) await loadDetails(); finish(); return true; }
    catch (e) { finish(false); if (selectedRef.current === workspaceId) { setTasks(current => current.map(t => t.id === task.id ? task : t)); setError(workspaceError(e)); await loadDetails().catch(() => undefined); } return false; }
  }
  async function submitModal() {
    await act(async () => {
      if (modal === "workspace") { const { data } = await api.post<Workspace>(`${base}/workspaces`, { name }); await loadWorkspaces(data.id); setModal(null); }
      if (modal === "join") { const { data } = await api.post(`${base}/workspace-invitations/accept`, { token: token.trim() }); setToken(""); setParams({}); await loadWorkspaces(data.workspace_id); setModal(null); }
      if (modal === "project" && selected) { const p = await projectsAPI.create({ name, project_key: projectKey, workspace_id: selected, status: "Active" }); await loadDetails(); setProjectFilter(String(p.id)); setModal(null); }
      if (modal === "invite" && selected) { const { data } = await api.post(`${base}/workspaces/${selected}/invitations`, { email, role }); setInviteLink(`${window.location.origin}/pms/invitation?token=${encodeURIComponent(data.token)}`); setNotice("Invitation created — waiting for activation or acceptance"); setView("people"); setEmail(""); await loadDetails(); }
    });
  }
  return <div className="ws-app"><AsyncProgress />
    <aside className="ws-rail" aria-label="Suite navigation"><Link to="/pms" className="ws-logo" title="Back to PMS"><Sparkles size={21} /></Link><Link to="/pms" className="ws-rail-item"><LayoutGrid size={20} /><span>Home</span></Link><button className={`ws-rail-item ${view !== "people" ? "active" : ""}`} onClick={() => setView("board")}><Folder size={20} /><span>Work</span></button><button className={`ws-rail-item ${view === "people" ? "active" : ""}`} onClick={() => setView("people")}><Users size={20} /><span>People</span></button><div className="ws-rail-bottom"><button className="ws-rail-item" onClick={() => openModal("join")}><Plus size={20} /><span>Join</span></button><button className="ws-rail-item" onClick={() => void signOut()} title={user?.email}><LogOut size={19} /><span>Logout</span></button><WorkspaceAvatar email={user?.email || "You"} /></div></aside>
    <aside className="ws-sidebar"><div className="ws-wordmark">KaryaFlow<span>WORKSPACE</span></div><label className="ws-workspace-switch"><span className="ws-workspace-mark">{workspace?.name.charAt(0).toUpperCase() || "K"}</span><select aria-label="Workspace" value={selected || ""} onChange={e => { setSelected(Number(e.target.value)); setError(""); }}><option value="" disabled>Choose workspace</option>{workspaces.map(w => <option value={w.id} key={w.id}>{w.name} · {w.role}</option>)}</select><ChevronDown size={14} /></label><div className="ws-sidebar-actions"><button onClick={() => openModal("workspace")}><Plus size={14} />Create workspace</button><button onClick={() => openModal("join")}>Join</button></div><span className="ws-nav-caption">YOUR WORKSPACE</span><nav aria-label="Workspace navigation"><button className={view !== "people" ? "active" : ""} onClick={() => { setView("board"); setProjectFilter(""); setAssigneeFilter(""); }}><LayoutGrid size={17} />All work<span>{tasks.length}</span></button><button className={view === "people" ? "active" : ""} onClick={() => setView("people")}><Users size={17} />People<span>{members.length}</span></button><button onClick={() => { setView("list"); setAssigneeFilter(String(user?.id)); }}><CheckCircle2 size={17} />My tasks<span>{tasks.filter(t => taskAssignees(t).includes(user?.id || 0) && taskBucket(t.status) !== "Done").length}</span></button></nav><div className="ws-nav-caption ws-project-caption">PROJECTS{manages && <button aria-label="Create project" onClick={() => openModal("project")}><Plus size={15} /></button>}</div><div className="ws-project-nav">{projects.map((p, i) => <button key={p.id} className={projectFilter === String(p.id) ? "active" : ""} onClick={() => { setProjectFilter(String(p.id)); setView("board"); }}><span className={`ws-project-dot ${tones[i % tones.length]}`} />{p.name}<ChevronRight size={13} /></button>)}{!projects.length && <p>Your projects will appear here.</p>}</div><div className="ws-sidebar-bottom"><div className="ws-small-avatars">{members.slice(0, 4).map((m, i) => <WorkspaceAvatar key={m.id} email={m.email} tone={tones[i % tones.length]} />)}</div><strong>A little less busywork.</strong><p>A little more great work.</p>{manages && <button className="ws-invite-sidebar" onClick={() => openModal("invite")}><Plus size={15} />Invite your team</button>}<Link to="/pms/overview"><ArrowLeft size={13} />Back to Business Suite</Link></div></aside>
    <div className="ws-main"><header className="ws-topbar"><div className="ws-breadcrumb"><span>{workspace?.name || "Workspaces"}</span><ChevronRight size={13} /><strong>{view === "people" ? "People" : "All work"}</strong></div><select className="ws-mobile-switch" aria-label="Mobile workspace" value={selected || ""} onChange={e => e.target.value === "new" ? openModal("workspace") : setSelected(Number(e.target.value))}><option value="" disabled>Workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}<option value="new">+ New workspace</option></select><div className="ws-search"><Search size={16} /><input ref={searchRef} aria-label="Search workspace" placeholder={view === "people" ? "Find a teammate…" : "Search tasks, descriptions, or IDs…"} value={query} onChange={e => setQuery(e.target.value)} /><kbd>/</kbd></div><div className="ws-connection"><i className={connected ? "live" : ""} /><span>{connected ? "Live updates" : "Auto refresh"}</span></div><WorkspaceAvatar email={user?.email || "You"} /></header>
      <div className="ws-content"><div className="ws-heading"><div><div className="ws-eyebrow">A SHARED SPACE FOR GREAT WORK</div><h1>{workspace?.name || "Find your flow"}<span className="ws-heading-dot">.</span></h1><p>{workspace ? "Less chasing updates. More moving forward, together." : "Bring your people and projects into one thoughtful workspace."}</p></div><div className="ws-heading-actions">{workspace && <span className="ws-role-badge"><ShieldCheck size={13} />{workspace.role}</span>}{manages && <button className="ws-button ws-outline" onClick={() => openModal("invite")}><Users size={15} />Invite people</button>}<NewMenu disabled={loading || detailsLoading} actions={[
          ...(canEdit ? [{ label: "Task", description: "Capture work and assign your team", icon: CheckCircle2, onSelect: () => projects.length ? setShowTaskCreate(true) : manages ? openModal("project") : setNotice("Ask a workspace admin to create the first project.") }] : []),
          ...(manages ? [{ label: "Project", description: "Organize a new initiative", icon: Folder, onSelect: () => openModal("project") }, { label: "Invite teammate", description: "Create a secure invitation link", icon: Users, onSelect: () => openModal("invite") }] : []),
          ...((user?.is_superuser || ["pms_org_admin", "pms_project_manager"].includes(user?.role || "")) ? [{ label: "Workspace", description: "Create a home for another team", icon: LayoutGrid, onSelect: () => openModal("workspace") }] : []),
        ]} /></div></div>
        {error && <div role="alert" className="ws-alert">{error}<button aria-label="Dismiss error" onClick={() => setError("")}><X size={15} /></button></div>}
        {loading || detailsLoading ? <div className="ws-loading"><Loader2 className="animate-spin" />Loading your workspace…</div> : !workspace && workspaceLoadFailed ? <div className="ws-onboarding"><h2>Unable to load your workspaces</h2><p>Your work is still saved. Retry the connection.</p><button className="ws-button ws-primary" onClick={() => { setLoading(true); setError(""); void loadWorkspaces().catch(e => { setWorkspaceLoadFailed(true); setError(workspaceError(e)); }).finally(() => setLoading(false)); }}>Retry loading workspaces</button></div> : !workspace ? <div className="ws-onboarding"><div className="ws-onboarding-art"><Folder size={42} /><span><Users size={24} /></span></div><span className="ws-eyebrow">YOUR NEXT CHAPTER STARTS HERE</span><h2>Good work happens together.</h2><p>Create a home for your projects. Invite your people.<br />Turn the next big idea into done.</p><div><button className="ws-button ws-primary" onClick={() => openModal("workspace")}><Plus size={16} />Create workspace</button><button className="ws-button ws-outline" onClick={() => openModal("join")}>Join a workspace</button></div><small>Workspace creation is available to PMS administrators and project managers.</small></div> : <>
          <div className="ws-summary"><div><span className="ws-summary-icon lilac"><Folder size={17} /></span><strong>{projects.length}</strong><span>projects</span></div><div><span className="ws-summary-icon blue"><LayoutGrid size={17} /></span><strong>{tasks.length - completed}</strong><span>open tasks</span></div><button onClick={() => { setAssigneeFilter("unassigned"); setView("list"); }}><span className="ws-summary-icon peach"><Users size={17} /></span><strong>{tasks.filter(t => !taskAssignees(t).length && taskBucket(t.status) !== "Done").length}</strong><span>need an owner</span></button><div className="ws-summary-progress"><div className="ws-progress-track"><i style={{ width: `${progress}%` }} /></div><strong>{progress}%</strong><span>complete</span></div></div>
          <div className="ws-viewbar"><div role="tablist" aria-label="Workspace views">{([{ id: "board", label: "Board", icon: LayoutGrid }, { id: "list", label: "List", icon: List }, { id: "people", label: "People", icon: Users }, { id: "calendar", label: "Calendar", icon: CalendarDays }, { id: "workload", label: "Workload", icon: Gauge }, { id: "activity", label: "Activity", icon: ShieldCheck }] as const).filter(v => v.id !== "activity" || manages).map(v => <button role="tab" aria-selected={view === v.id} key={v.id} onClick={() => setView(v.id)} className={view === v.id ? "active" : ""}><v.icon size={16} />{v.label}{v.id === "people" && <span>{members.length}</span>}</button>)}</div><span className="ws-view-hint">{view === "calendar" ? "Open a task to update its schedule." : view === "workload" ? "Shared effort, split across collaborators." : view === "people" ? "A clear view of who’s doing what" : canEdit ? "Drag to move. Drop on a teammate to assign." : "You have read-only access"}</span></div>
          <div className="ws-work-and-chat"><div className="ws-work-area"><>{(view === "calendar" || view === "workload") ? <WorkspacePlanning view={view} tasks={tasks.filter(t => !query || `${t.title} ${t.task_key} ${t.description || ""}`.toLowerCase().includes(query.toLowerCase()))} members={members} projects={projects} onOpen={setTaskOpen} /> : view === "activity" ? <WorkspaceActivity key={workspace.id} workspaceId={workspace.id} onOpen={setTaskOpen} /> : <WorkspaceWork key={`${selected}:${filtersVersion}`} onClearSearch={() => setQuery("")} tasks={tasks} members={members} projects={projects} view={view} query={query} projectFilter={projectFilter} setProjectFilter={setProjectFilter} assigneeFilter={assigneeFilter} setAssigneeFilter={setAssigneeFilter} canEdit={canEdit} updateTask={updateTask} onOpen={id => { setError(""); setTaskOpen(id); }} onRefresh={loadDetails} onInvite={manages ? () => openModal("invite") : undefined} onError={setError} onNotice={setNotice} renderMemberActions={m => {
            const editable = manages && m.role !== "Owner" && (workspace.role === "Owner" || m.role !== "Admin");
            return editable ? <><select aria-label={`Role for ${m.email}`} value={m.role} disabled={busy} onChange={e => { const next = e.target.value; void act(async () => { await api.patch(`${base}/workspaces/${workspace.id}/members/${m.id}`, { role: next }); await loadDetails(); }); }}>{["Admin", "Member", "Guest"].filter(r => workspace.role === "Owner" || r !== "Admin").map(r => <option key={r}>{r}</option>)}</select><button disabled={busy} onClick={() => { void act(async () => { await api.delete(`${base}/workspaces/${workspace.id}/members/${m.id}`); await loadDetails(); }); }}>Remove</button></> : <span><ShieldCheck size={12} />{m.role === "Owner" ? "Workspace owner" : m.role === "Guest" ? "Can view work" : "Can collaborate"}</span>;
          }} />}</>
          </div><WorkspaceCollaboration key={workspace.id} workspaceId={workspace.id} canEdit={canEdit} tasks={tasks} onOpen={setTaskOpen} /></div>
          {view === "people" && manages && <section className="ws-invitations" aria-label="Workspace invitations"><h3>Invitations · {invitations.filter(i => i.status === "pending").length} waiting</h3><p className="text-sm text-slate-500">Share the invitation link with your teammate. Members appear above after they accept.</p>{!invitations.length && <p>No invitations yet.</p>}{invitations.map(i => <div key={i.id}><span>{i.email}<small>{i.role} · {i.status === "pending" ? i.account_exists ? "Waiting for acceptance" : "Waiting for account activation" : i.status === "accepted" ? "Accepted · Team member" : i.status}</small></span>{["pending", "expired", "revoked"].includes(i.status) && !members.some(m => m.email.toLowerCase() === i.email.toLowerCase()) && <button disabled={busy} onClick={() => { void act(async () => { const { data } = await api.post(`${base}/workspaces/${workspace.id}/invitations`, { email: i.email, role: i.role }); setInviteLink(`${window.location.origin}/pms/invitation?token=${encodeURIComponent(data.token)}`); setEmail(""); setRole(i.role); setModal("invite"); setNotice("New invitation link created; previous link is no longer valid"); await loadDetails(); }); }}>Resend / new link</button>}{i.status === "pending" && <button disabled={busy} onClick={() => { void act(async () => { await api.delete(`${base}/workspaces/${workspace.id}/invitations/${i.id}`); setNotice("Invitation revoked"); await loadDetails(); }); }}>Revoke</button>}</div>)}</section>}
          <footer className="ws-board-footer"><span><CheckCircle2 size={14} />One shared source of truth. Every view stays in sync.</span><div>{projects.length > 0 && <Link to={`/pms/projects/${createProjectId}/gantt`}>Open Gantt<ArrowUpRight size={12} /></Link>}{manages && <button onClick={() => openModal("project")}><Plus size={14} />Create project</button>}</div></footer>
        </>}
      </div>
    </div>
    <div className="ws-notice" role="status" aria-live="polite">{notice && <><CheckCircle2 size={16} />{notice}</>}</div>
    <Dialog.Root open={modal !== null} onOpenChange={open => { if (!open) setModal(null); }}><Dialog.Portal><Dialog.Overlay className="ws-overlay" /><Dialog.Content className="ws-modal"><Dialog.Close className="ws-modal-close" aria-label="Close dialog"><X size={19} /></Dialog.Close><span className="ws-modal-symbol">{modal === "invite" ? <Users size={24} /> : <Folder size={24} />}</span><Dialog.Title>{modal === "workspace" ? "A home for your team." : modal === "invite" ? "Great work takes great people." : modal === "project" ? "Make room for your next idea." : "Your team is waiting."}</Dialog.Title><Dialog.Description>{modal === "invite" ? "Create a secure share link for your teammate’s email. No email is sent automatically." : modal === "project" ? "Create a project inside this workspace." : modal === "join" ? "Sign in with the invited email and accept your invitation." : "Give your workspace a name. Invite your teammates next."}</Dialog.Description>{error && <div role="alert" className="ws-alert">{error}</div>}<form onSubmit={e => { e.preventDefault(); void submitModal(); }}>{modal === "workspace" || modal === "project" ? <><label>{modal === "workspace" ? "Workspace name" : "Project name"}<input aria-label={modal === "workspace" ? "Workspace name" : "Project name"} autoFocus value={name} onChange={e => { setName(e.target.value); if (modal === "project" && !keyEdited) setProjectKey(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6)); }} required maxLength={180} placeholder={modal === "workspace" ? "e.g. Product studio" : "e.g. Website launch"} /></label>{modal === "project" && <label>Project key<input aria-label="Project key" value={projectKey} onChange={e => { setKeyEdited(true); setProjectKey(e.target.value.toUpperCase()); }} required maxLength={10} pattern="[A-Z0-9]{2,10}" placeholder="e.g. WEB" /></label>}</> : modal === "join" ? <label>Invitation token<input aria-label="Invitation token" autoFocus value={token} onChange={e => setToken(e.target.value)} required /><small>Invitations expire after seven days.</small></label> : <><label>Email address<input aria-label="Teammate email" type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="teammate@company.com" autoFocus /></label><label>Workspace role<select aria-label="Invitation role" value={role} onChange={e => setRole(e.target.value)}>{["Admin", "Member", "Guest"].filter(r => workspace?.role === "Owner" || r !== "Admin").map(r => <option key={r}>{r}</option>)}</select><small>{role === "Guest" ? "Can view work without making changes." : role === "Admin" ? "Can manage projects, invitations, and members." : "Can create, assign, and update tasks and add comments."}</small></label></>}{inviteLink && <div className="ws-share-link"><span><CheckCircle2 size={15} />Invitation ready</span><p>Waiting for activation or acceptance. Copy and send this link to the invited person. Existing users also receive an in-app notification.</p><input aria-label="Share invitation link" readOnly value={inviteLink} onFocus={e => e.target.select()} /><button type="button" onClick={() => { void act(async () => { await navigator.clipboard.writeText(inviteLink); setNotice("Invitation link copied"); }); }}><Copy size={14} />Copy link</button></div>}<div className="ws-modal-actions"><Dialog.Close className="ws-button ws-outline" type="button">{inviteLink ? "Done" : "Cancel"}</Dialog.Close><button className="ws-button ws-primary" disabled={busy}>{busy && <Loader2 size={14} className="animate-spin" />}{modal === "workspace" ? "Create workspace" : modal === "project" ? "Create project" : modal === "join" ? "Accept invitation" : "Create invitation"}</button></div></form></Dialog.Content></Dialog.Portal></Dialog.Root>
    <CreateTaskModal projects={projects} workspacePeople={assignablePeople} isOpen={showTaskCreate} onClose={() => setShowTaskCreate(false)} projectId={createProjectId || 0} onTaskCreated={(task) => { setShowTaskCreate(false); setView("board"); setQuery(""); setAssigneeFilter(""); setProjectFilter(String(task.project_id)); setFiltersVersion(v => v + 1); setNotice("Task created — visible in your workspace"); void loadDetails().catch(e => setError(workspaceError(e))); }} />
    <TaskDrawer error={error} task={tasks.find(t => t.id === taskOpen)} members={members} canEdit={canEdit} onClose={() => setTaskOpen(null)} onUpdate={updateTask} onRefresh={loadDetails} onError={setError} />
  </div>;
}
