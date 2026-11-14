import { toast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { pmsWorkspaceOptions } from "@/shared/workspace/pms-workspace-options";
import { workspaceDataScope } from "@/shared/workspace/workspace-management-types";
import PageWorkTools from "@/components/app/PageWorkTools";
import RouteContent from "@/components/app/RouteContent";
import SetupReadiness from "@/components/suite/SetupReadiness";
import { useRouteViewState } from "@/hooks/use-route-view-state";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import { Button } from "@/components/ui/button";
import { useSmartCreation } from "@/shared/creation/SmartCreationProvider";
import ModuleWorkflowBoard from "@/shared/workflow-board/ModuleWorkflowBoard";
import { CustomFieldsForm, type FieldDraft } from "../components/CustomFields";
import CompactActions from "@/components/actions/CompactActions";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import {WorkspacePicker,WorkspaceHero,WorkspaceMetric,workspaceColors,workspaceDefaultColor,type BoardWorkspace} from "./WorkspaceBoardChrome";
import ModuleSwitcher from "@/components/layout/ModuleSwitcher";
import type {CSSProperties} from "react";
import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { ManagePersonButton } from "../components/people/PersonIdentity";
import InvitationInbox from "../components/InvitationInbox";
import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import PageRefreshButton from "@/components/app/PageRefreshButton";
import RefreshPagesCatalog from "@/components/app/RefreshPagesCatalog";
import { usePageRefresh } from "@/lib/page-refresh";
import { useRefreshableEffect } from "@/lib/page-refresh";
import Sidebar from "@/components/layout/Sidebar";
import GlobalSearch from "@/components/app/GlobalSearch";
import { Menu } from "lucide-react";
import UndoRedo from "../components/UndoRedo";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { CalendarDays, Gauge, ArrowLeft, ArrowUpRight, CheckCircle2, ChevronDown, ChevronRight, Copy, Folder, LayoutGrid, List, Loader2, Plus, Search, ShieldCheck, Sparkles, Users, LogOut, X, MessageSquare, Zap, Bug, FileText } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { projectsAPI } from "../services/api";
import { usePMSRealtime, useRealtimeStore } from "../realtime";
import CreateTaskModal from "../components/CreateTaskModal";
import QuickCreateProject from "../components/QuickCreateProject";
import { WorkspaceWork, TaskDrawer, WorkspaceAvatar } from "./WorkspaceWork";
import { type WorkspaceMember, type WorkspaceProject, type WorkTask, personName, workspaceBase as base, tones, taskBucket, taskAssignees, workspaceError } from "./workspaceTypes";
import "./workspaces.css";
import "./WorkspaceBoardChrome.css";
import WorkspaceActivity from "./WorkspaceActivity";
import WorkspacePlanning from "./WorkspacePlanning";
import WorkspaceCollaboration from "./WorkspaceCollaboration";
import { beginProgress } from "@/components/app/AsyncProgress";
import MessagingNavLink from "@/components/layout/MessagingNavLink";
import PMSMoreMenu from "@/components/layout/PMSMoreMenu";
import PMSProfileMenu from "@/components/layout/PMSProfileMenu";
import BranchSwitcher from "@/components/suite/BranchSwitcher";
import NewMenu from "@/components/app/NewMenu";
import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import { useSignOut } from "@/hooks/use-sign-out";
import { canAccessRoute } from "@/lib/roles";

type Workspace = BoardWorkspace;
type Invitation = { id: number; email: string; role: string; status: string; account_exists?: boolean };
type View = "board" | "list" | "people" | "calendar" | "workload" | "activity";
type Modal = "workspace" | "invite" | "join" | "project" | null;

export default function WorkspacesPage(props:{creationWindow?:boolean}={}) {
  const scope=useRecordScope(),user=useAuthStore(state=>state.user);
  return <ScopedWorkspacesPage key={JSON.stringify([scope,user?.role,user?.primary_role,user?.is_superuser,user?.access?.companyDisabledModules])} {...props}/>;
}
function ScopedWorkspacesPage({ creationWindow = false }: { creationWindow?: boolean } = {}) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const smartCreation = useSmartCreation();
  const [navigationOpen,setNavigationOpen] = useState(false);
  const [navigationCollapsed,setNavigationCollapsed] = useState(()=>localStorage.getItem("sidebarCollapsed")==="true");
  useEffect(()=>{localStorage.setItem("sidebarCollapsed",String(navigationCollapsed));},[navigationCollapsed]);
  useEffect(()=>{
    if(!navigationOpen) return;
    const main=document.querySelector<HTMLElement>(".ws-main");
    main?.setAttribute("inert","");
    return()=>{main?.removeAttribute("inert");};
  },[navigationOpen]);

  const { user } = useAuthStore();
  const workspaceClient=useQueryClient(),workspaceScope=workspaceDataScope(user);
  const requestedWorkspace = Number(params.get("workspace"));
  const signOut = useSignOut("/pms/login");

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<number>();
  const collectionKey = `pms-workspace:${requestedWorkspace || selected || "default"}`;
  const [filtersVersion, setFiltersVersion] = useRouteViewState(`${collectionKey}:filters-version`,0);
  const overviewKey = `pms-workspace-overview:${user?.id}:${user?.access?.companyId}:${selected}`;
  const [overviewOpen, setOverviewOpen] = useState(false);
  const [overviewReady, setOverviewReady] = useState("");
  useEffect(() => {
    let expanded = false;
    try { expanded = localStorage.getItem(overviewKey) === "true"; } catch { /* Optional preference storage. */ }
    setOverviewOpen(expanded); setOverviewReady(overviewKey);
  }, [overviewKey]);

  const workspaceRequests=useRef(0);
  const colorKey=`pms-workspace-colors-${user?.id}-${user?.access?.companyId}`;
  const [workspaceColorMap,setWorkspaceColorMap]=useState<Record<number,string>>({});
  useEffect(()=>{try{setWorkspaceColorMap(Object.fromEntries(Object.entries(JSON.parse(localStorage.getItem(colorKey)||"{}")||{}).filter(([,value])=>workspaceColors.includes(String(value))).map(([id,value])=>[id,String(value)])))}catch{setWorkspaceColorMap({})}},[colorKey]);
  const changeWorkspaceColor=(color:string)=>{if(!selected)return;const next={...workspaceColorMap,[selected]:color};setWorkspaceColorMap(next);localStorage.setItem(colorKey,JSON.stringify(next))};
  const switchWorkspace=(id:number)=>{setMembers([]);setProjects([]);setTasks([]);setDetailsLoading(true);setSelected(id);setError("");setParams(current=>{const next=new URLSearchParams(current);next.set("workspace",String(id));next.delete("task");next.delete("project");next.delete("invite");return next})};
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const detailsLoadedFor = useRef<number>();
  const detailsRequest = useRef(0);
  const detailsInFlight = useRef(new Map<string, Promise<void>>());
  const [taskScope,setTaskScope]=useRouteViewState<"all"|"open"|"unassigned"|"completed">(`${collectionKey}:scope`,"all");

  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [tasks, setTasks] = useState<WorkTask[]>([]);
  const scopedTasks=useMemo(()=>tasks.filter(task=>{
    if(taskScope==="all")return true;
    if(taskScope==="completed")return ["Done","Completed","Closed","Resolved"].includes(task.status);
    const open=!["Done","Completed","Closed","Resolved","Cancelled","Canceled","Rejected"].includes(task.status);
    return open&&(taskScope!=="unassigned"||!taskAssignees(task).length);
  }),[tasks,taskScope]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const requestedView = params.get("view");
  const supportedViews: View[] = ["board", "list", "calendar", "workload", "activity"];
  const [view, setView] = useRouteViewState<View>(`${collectionKey}:view`,() => supportedViews.includes(requestedView as View) ? requestedView as View : "list");
  useEffect(() => {
    if (["board", "list", "calendar", "workload", "activity"].includes(requestedView || "")) setView(requestedView as View);
  }, [requestedView]);
  useEffect(() => { if (view === "people" || params.has("people")) navigate("/pms/people", { replace: true }); }, [view, params, navigate]);
  const [modal, setModal] = useState<Modal>(params.get("invite") ? "join" : null);
  const [name, setName] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [projectCustomFields,setProjectCustomFields]=useState<FieldDraft>({});
  useEffect(()=>setProjectCustomFields({}),[modal]);
  const [keyEdited, setKeyEdited] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Member");
  const [token, setToken] = useState(params.get("invite") || "");
  const [inviteLink, setInviteLink] = useState("");
  const [query, setQuery] = useRouteViewState(`${collectionKey}:query`,"");
  const [projectFilter, setProjectFilter] = useRouteViewState(`${collectionKey}:project`,"");
  const [assigneeFilter, setAssigneeFilter] = useRouteViewState(`${collectionKey}:assignee`,"");
  const [addingPeople, setAddingPeople] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [workspaceLoadFailed, setWorkspaceLoadFailed] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [taskOpen, setTaskOpen] = useState<number | null>(null);
  const [showTaskCreate, setShowTaskCreate] = useState(false);
  const [calendarCreate, setCalendarCreate] = useState<{day:string;project:string}|null>(null);
  const [quickWorkType, setQuickWorkType] = useState<"Task" | "Story" | "Bug">("Task");
  const [chatOpen, setChatOpen] = useState(false);
  const [detailsFailed, setDetailsFailed] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const workspace = workspaces.find(w => w.id === selected);
  const requestedUnavailable=!loading&&!workspaceLoadFailed&&!!requestedWorkspace&&!workspaces.some(w=>w.id===requestedWorkspace);
  const pendingWorkspaceScope=!!requestedWorkspace&&selected!==requestedWorkspace;
  const manages = workspace?.role === "Owner" || workspace?.role === "Admin";
  const canEdit = !!workspace && workspace.role !== "Guest";
  const canCreateWorkspace = !!user && canAccessRoute("/pms/projects/new", user.role, user.is_superuser);
  const connected = useRealtimeStore(s => s.connected);
  const completed = tasks.filter(t => taskBucket(t.status) === "Done").length;
  const progress = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
  const assignablePeople = useMemo(() => members.filter(m => m.role !== "Guest").map(m => ({ id: m.user_id, email: m.email, name: personName(m.email) })), [members]);
  const createProjectId = Number(projectFilter) || projects[0]?.id;
  const loadWorkspaces = useCallback(async (preferred?: number, force = false) => {
    const request=++workspaceRequests.current;
    const data = await workspaceClient.fetchQuery({...pmsWorkspaceOptions(workspaceScope),...(preferred||force?{staleTime:0}:{})});
    if(request!==workspaceRequests.current)return;
    const saved = Number(localStorage.getItem(`pms-workspace-${user?.id}`));
    setWorkspaceLoadFailed(false); setWorkspaces(data); setSelected(current => preferred || (requestedWorkspace ? data.some(w => w.id === requestedWorkspace) ? requestedWorkspace : undefined : data.some(w => w.id === current) ? current : data.some(w => w.id === saved) ? saved : data[0]?.id));
  }, [user?.id, requestedWorkspace, workspaceClient, workspaceScope]);
  usePageRefresh(() => loadWorkspaces(undefined,true));
  useEffect(()=>{if(selected&&!requestedWorkspace)setParams(current=>{const next=new URLSearchParams(current);next.set("workspace",String(selected));return next},{replace:true})},[selected,requestedWorkspace,setParams]);
  useEffect(() => { if (selected && user?.id) localStorage.setItem(`pms-workspace-${user.id}`, String(selected)); }, [selected, user?.id]);
  const loadDetails = useCallback(async () => {
    if (!selected) return;
    const key = `${selected}:${manages}`;
    const pending = detailsInFlight.current.get(key);
    if (pending) return pending;
    const load = async () => {
    const request=++detailsRequest.current;
    const overview = await api.get<{ projects: WorkspaceProject[]; tasks: WorkTask[]; role: string; members?: WorkspaceMember[]; invitations?: Invitation[] }>(`${base}/workspaces/${selected}/overview`, {params:{include_people:true}});
    if (selectedRef.current !== selected || request !== detailsRequest.current) return;
    // Older rolling-deployment APIs ignore the opt-in flag. Preserve their
    // existing separately authorized reads instead of inventing empty people.
    const [peopleResult, invitesResult] = await Promise.allSettled([
      Array.isArray(overview.data.members) ? Promise.resolve({data:overview.data.members}) : api.get<WorkspaceMember[]>(`${base}/workspaces/${selected}/members`),
      Array.isArray(overview.data.invitations) ? Promise.resolve({data:overview.data.invitations}) : manages ? api.get<Invitation[]>(`${base}/workspaces/${selected}/invitations`) : Promise.resolve({ data: [] as Invitation[] }),
    ]);
    if (selectedRef.current !== selected || request !== detailsRequest.current) return;
    detailsLoadedFor.current = selected;
    setDetailsFailed(false);
    setWorkspaces(current => current.map(w => w.id === selected && w.role !== overview.data.role ? { ...w, role: overview.data.role } : w));
    setProjects(overview.data.projects);setTasks(overview.data.tasks);
    setMembers(peopleResult.status === "fulfilled" ? peopleResult.value.data : []);
    setInvitations(invitesResult.status === "fulfilled" ? invitesResult.value.data : []);
    const warnings=[peopleResult.status==="rejected"?"Member details could not be loaded.":"",invitesResult.status==="rejected"?"Invitations could not be loaded.":""].filter(Boolean);
    setError(warnings.join(" "));
    };
    const request = load();
    detailsInFlight.current.set(key, request);
    try { await request; }
    finally { if (detailsInFlight.current.get(key) === request) detailsInFlight.current.delete(key); }
  }, [selected, manages]);
  usePageRefresh(loadDetails);
  useEffect(() => { const changed = () => { void loadDetails().catch(e => setError(workspaceError(e))); }; window.addEventListener("pms:people-changed", changed); return () => window.removeEventListener("pms:people-changed", changed); }, [loadDetails]);

  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    const finish = beginProgress(modal === "project" ? "Creating project" : modal === "workspace" ? "Creating workspace" : modal === "invite" ? "Preparing invitation" : "Saving changes");
    try { await action(); finish(); } catch (e) { finish(false); setError(workspaceError(e)); } finally { setBusy(false); }
  };
  useRefreshableEffect(() => { const finish = beginProgress("Loading workspaces"); loadWorkspaces().then(() => finish()).catch(e => { finish(false); setWorkspaceLoadFailed(true); setError(workspaceError(e)); }).finally(() => setLoading(false)); }, [loadWorkspaces]);
  useEffect(() => {
    setMembers([]); setProjects([]); setTasks([]); setInvitations([]); setTaskOpen(null);
    let active = true;
    setDetailsLoading(!!selected); setDetailsFailed(false);
    const finish = selected ? beginProgress("Opening workspace") : undefined;
    void loadDetails().then(() => finish?.()).catch(e => { finish?.(false); if (active) { setDetailsFailed(true); setError(workspaceError(e)); } }).finally(() => { if (active) setDetailsLoading(false); });
    return () => { active = false; };
  }, [loadDetails]);
  useEffect(() => {
    const taskId = Number(params.get("task"));
    if (!taskId || detailsLoadedFor.current !== selected || detailsLoading || loading) return;
    if (tasks.some(task => task.id === taskId)) setTaskOpen(taskId);
    else setNotice("This task is not available in the selected workspace.");
    setParams(current => { const next = new URLSearchParams(current); next.delete("task"); return next; }, { replace: true });
  }, [params, selected, tasks, detailsLoading, loading, setParams]);
  useEffect(() => { if (workspace?.role !== "Owner") setRole("Member"); }, [workspace?.role]);
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(""), 3500); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !(e.target as HTMLElement)?.closest("input, textarea, select, [contenteditable=true], [role=dialog], [role=menu]")) { e.preventDefault(); searchRef.current?.focus(); } };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || modal || showTaskCreate || taskOpen) return;
      if ((event.target as HTMLElement)?.closest("input, textarea, select, [contenteditable=true], [role=dialog], [role=menu]")) return;
      if (event.key.toLowerCase() === "c" && canEdit && projects.length) { event.preventDefault(); setShowTaskCreate(true); }
    };
    window.addEventListener("keydown", shortcut); return () => window.removeEventListener("keydown", shortcut);
  }, [canEdit, projects.length, modal, showTaskCreate, taskOpen]);
  usePMSRealtime({ onEvent: event => { if (/^(task\.|comment\.|project\.)/.test(event.type)) void loadDetails().catch(() => undefined); }, onFallbackPoll: () => { void loadDetails().catch(() => undefined); }, showToast: false });
  useEffect(() => {
    if (loading || detailsLoading || detailsLoadedFor.current !== selected || !user) return;
    if (!params.get("mine") && !params.get("people")) return;
    if (params.get("mine")) { setView("list"); setProjectFilter(""); setQuery(""); setAssigneeFilter(String(user.id)); }
    if (params.get("people")) setView("people");
    setParams(current => { const next = new URLSearchParams(current); next.delete("mine"); next.delete("people"); return next; }, { replace: true });
  }, [params, loading, detailsLoading, selected, user?.id, setParams]);
  const [creatingProject, setCreatingProject] = useState(false);
  const openModal = (next: Modal) => { if (next === "workspace" && !creationWindow && smartCreation?.open("/pms/workspaces?new=workspace", record => { const id = Number((record as { id?: string | number } | undefined)?.id); if (id) void loadWorkspaces(id).then(() => switchWorkspace(id)); })) return; if (next === "project") { setCreatingProject(true); return; } setName(""); setProjectKey(""); setKeyEdited(false); setInviteLink(""); setError(""); setModal(next); };
  useEffect(() => {
    const intent = params.get("new");
    if (!intent || loading || detailsLoading) return;
    if (intent !== "workspace" && (detailsLoadedFor.current !== selected || (requestedWorkspace && selected !== requestedWorkspace))) return;
    const projectId = Number(params.get("project"));
    if (projectId && projects.some(project => project.id === projectId)) setProjectFilter(String(projectId));
    if (["task", "story", "bug"].includes(intent) && canEdit) {
      if (projects.length) { setQuickWorkType(intent === "bug" ? "Bug" : intent === "story" ? "Story" : "Task"); setShowTaskCreate(true); }
      else if (manages) { openModal("project"); setNotice("Create your first project before adding work items."); }
      else setNotice("Ask a workspace admin to create the first project.");
    } else if (intent === "project" && manages) openModal("project");
    else if (intent === "user" && manages) openModal("invite");
    else if (intent === "workspace" && canCreateWorkspace) openModal("workspace");
    else setNotice("Your workspace role does not allow this action.");
    setParams(current => { const next = new URLSearchParams(current); next.delete("new"); next.delete("project"); return next; }, { replace: true });
  }, [params, loading, detailsLoading, selected, requestedWorkspace, projects, canEdit, manages, canCreateWorkspace, setParams]);
  async function updateTask(task: WorkTask, changes: Partial<WorkTask>) {
    if (!canEdit) return false;
    const workspaceId = selected;
    const finish = beginProgress("Saving task");
    setError("");
    const payload="updated_at" in task?{...changes,expected_updated_at:task.updated_at??null}:changes;
    try {
      await api.patch(`${base}/tasks/${task.id}`, payload);
      if (selectedRef.current === workspaceId) {
        try { await loadDetails(); }
        catch (e) { setNotice(`Task saved, but the workspace could not refresh. Refresh workspace data before continuing. ${workspaceError(e)}`); }
      }
      finish(); return true;
    }
    catch (e) { finish(false); if (selectedRef.current === workspaceId) setError(workspaceError(e)); return false; }
  }
  async function submitModal() {
    await act(async () => {
      if (modal === "workspace") { const { data } = await api.post<Workspace>(`${base}/workspaces`, { name }); setWorkspaces(current => [...current.filter(workspace => workspace.id !== data.id), data]); switchWorkspace(data.id); setModal(null); toast({ title: "Workspace created", description: data.name }); void loadWorkspaces(data.id).catch(() => setNotice("Workspace created. The list could not be refreshed; refresh to see the latest details.")); }
      if (modal === "join") { const { data } = await api.post(`${base}/workspace-invitations/accept`, { token: token.trim() }); setToken(""); await loadWorkspaces(data.workspace_id);switchWorkspace(data.workspace_id); setModal(null); }
      if (modal === "project" && selected) { const p = await projectsAPI.create({ name, project_key: projectKey, workspace_id: selected, custom_fields:projectCustomFields, status: "Active" }); await loadDetails(); setProjectFilter(String(p.id)); setModal(null); }
      if (modal === "invite" && selected) { const { data } = await api.post(`${base}/workspaces/${selected}/invitations`, { email, role }); setInviteLink(`${window.location.origin}/pms/invitation?token=${encodeURIComponent(data.token)}`); setNotice("Invitation created — waiting for activation or acceptance"); setView("people"); setEmail(""); await loadDetails(); }
    });
  }

  return <div style={{"--wb-accent":workspaceColorMap[selected||0]||workspaceDefaultColor(selected||1)} as CSSProperties} className={`ws-app wb-reference ${navigationCollapsed ? "kf-workspace-collapsed" : ""} ${navigationOpen ? "kf-navigation-open" : ""}`}>
    <Sidebar embedded open={navigationOpen} collapsed={navigationCollapsed && !navigationOpen} onClose={()=>setNavigationOpen(false)} onToggleCollapse={()=>setNavigationCollapsed(value=>!value)} />
    <div className="ws-main"><header className="suite-app-bar ws-topbar"><button className="kf-mobile-menu" aria-label="Open navigation" onClick={()=>setNavigationOpen(true)}><Menu size={20}/></button><div className="wb-module-menu"><ModuleSwitcher/></div><NativeSelect className="ws-mobile-switch" aria-label="Mobile workspace" value={selected || ""} onChange={e => e.target.value === "new" ? openModal("workspace") : switchWorkspace(Number(e.target.value))}><option value="" disabled>Workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}{canCreateWorkspace && <option value="new">+ New workspace</option>}</NativeSelect><div className="kf-workspace-command"><GlobalSearch /></div><div className="ws-connection"><i className={connected ? "live" : ""} /><span>{connected ? "Live updates" : "Auto refresh"}</span></div><BranchSwitcher /><PageRefreshButton compact /><RefreshPagesCatalog /><SuiteNotificationBell /><PMSMoreMenu /><WorkspacePicker items={workspaces} current={workspace} onSelect={switchWorkspace} onCreate={()=>openModal("workspace")} canCreate={canCreateWorkspace} colors={workspaceColorMap} onColor={changeWorkspaceColor}/><PMSProfileMenu onCreateTask={() => { if (canEdit && projects.length) { setQuickWorkType("Task"); setShowTaskCreate(true); } else setNotice("Ask a workspace admin to create a project or grant task access."); }} onMyWork={() => { setView("list"); setProjectFilter(""); setQuery(""); setAssigneeFilter(String(user?.id)); }} onViewPeople={() => setView("people")} /></header>
      <RouteContent className="ws-content" scrollRoot freshness={false}><SetupReadiness embedded />{!loading && !detailsLoading && (!selected || detailsLoadedFor.current === selected || detailsFailed) && <InvitationInbox />}
        {error && <div role="alert" className="ws-alert">{error}<button aria-label="Dismiss error" onClick={() => setError("")}><X size={15} /></button></div>}
        {loading || detailsLoading || (!!selected && detailsLoadedFor.current !== selected && !detailsFailed) || pendingWorkspaceScope&&!requestedUnavailable&&!workspaceLoadFailed ? <div className="ws-loading"><Loader2 className="animate-spin" />Loading your workspace…</div> : requestedUnavailable ? <div role="alert" className="ws-onboarding"><h2>Workspace unavailable</h2><p>This workspace is unavailable or you do not have access.</p>{workspaces.length>0&&<button type="button" className="ws-button ws-primary" onClick={()=>switchWorkspace(workspaces[0].id)}>Open an available workspace</button>}</div> : (!workspace||pendingWorkspaceScope) && workspaceLoadFailed ? <div className="ws-onboarding"><h2>Unable to load your workspaces</h2><p>Your work is still saved. Retry the connection.</p><button className="ws-button ws-primary" onClick={() => { setLoading(true); setError(""); void loadWorkspaces().catch(e => { setWorkspaceLoadFailed(true); setError(workspaceError(e)); }).finally(() => setLoading(false)); }}>Retry loading workspaces</button></div> : !workspace ? <div className="ws-onboarding"><div className="ws-onboarding-art"><Folder size={42} /><span><Users size={24} /></span></div><span className="ws-eyebrow">YOUR NEXT CHAPTER STARTS HERE</span><h2>Good work happens together.</h2><p>Create a home for your projects. Invite your people.<br />Turn the next big idea into done.</p><div>{canCreateWorkspace && <Button type="submit" variant="default" className="ws-button ws-primary" onClick={() => openModal("workspace")}><Plus size={16} />Create workspace</Button>}<button className="ws-button ws-outline" onClick={() => openModal("join")}>Join a workspace</button></div><small>Workspace creation is available to PMS administrators and project managers.</small></div> : <>
          {detailsFailed && <div role="alert" className="ws-alert">Workspace data could not be loaded. <button onClick={() => { setDetailsLoading(true); void loadDetails().then(() => { setDetailsFailed(false); }).catch(e => setError(workspaceError(e))).finally(() => setDetailsLoading(false)); }}>Retry workspace</button></div>}
          {!detailsFailed && <>
          <header className="wb-work-header"><h1>{workspace.name}</h1><span>{projects.length} projects · {tasks.length} loaded tasks</span></header>
          <details className="wb-overview" key={overviewKey} open={overviewReady === overviewKey && overviewOpen} onToggle={event => {
            if (overviewReady !== overviewKey) return;
            const expanded = event.currentTarget.open; setOverviewOpen(expanded);
            try { localStorage.setItem(overviewKey, String(expanded)); } catch { /* Work remains available without storage. */ }
          }}>
          <summary>Workspace overview<span>Members, metrics and delivery pipeline</span></summary>
          <WorkspaceHero workspace={workspace} members={members} projects={projects.length} canManage={manages} onAdd={()=>setAddingPeople(true)} onInvite={()=>openModal("invite")}/>
          <div className="wb-metrics"><WorkspaceMetric label="Projects" value={projects.length} kind="purple" points={projects.map(()=>1)} onClick={()=>navigate(`/pms/projects?workspace=${selected}`)}/><WorkspaceMetric label="Open tasks" value={tasks.filter(t=>!["Done","Completed","Closed","Resolved","Cancelled","Canceled","Rejected"].includes(t.status)).length} kind="blue" points={projects.map(p=>tasks.filter(t=>t.project_id===p.id&&!["Done","Completed","Closed","Resolved","Cancelled","Canceled","Rejected"].includes(t.status)).length)} onClick={()=>{setTaskScope("open");setQuery("");setProjectFilter("");setFiltersVersion(v=>v+1);setView("list");setAssigneeFilter("")}}/><WorkspaceMetric label="Need an owner" value={tasks.filter(t=>!taskAssignees(t).length&&!["Done","Completed","Closed","Resolved","Cancelled","Canceled","Rejected"].includes(t.status)).length} kind="orange" points={projects.map(p=>tasks.filter(t=>t.project_id===p.id&&!taskAssignees(t).length&&!["Done","Completed","Closed","Resolved","Cancelled","Canceled","Rejected"].includes(t.status)).length)} onClick={()=>{setTaskScope("unassigned");setQuery("");setProjectFilter("");setFiltersVersion(v=>v+1);setAssigneeFilter("unassigned");setView("list")}}/><WorkspaceMetric label="Completed" value={`${progress}%`} kind="green" points={projects.map(p=>tasks.filter(t=>t.project_id===p.id&&taskBucket(t.status)==="Done").length)} onClick={()=>{setTaskScope("completed");setQuery("");setProjectFilter("");setAssigneeFilter("");setFiltersVersion(v=>v+1);setView("list")}}/></div>
          <ModuleWorkflowBoard key={selected} module="pms" workspaceId={selected} />
          </details>
          {taskScope!=="all"&&<div className="flex items-center gap-3 rounded border p-2 text-sm">Showing {taskScope} tasks<button className="text-primary underline" onClick={()=>setTaskScope("all")}>Show all tasks</button></div>}
          <div className="ws-viewbar"><div role="tablist" aria-label="Workspace views" onKeyDown={event => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
            const current = tabs.indexOf(event.target as HTMLButtonElement);
            if (current < 0) return;
            event.preventDefault();
            const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
            tabs[next].focus(); tabs[next].click();
          }}>{([{ id: "list", label: "List", icon: List }, { id: "board", label: "Board", icon: LayoutGrid }, { id: "people", label: "People", icon: Users }, { id: "calendar", label: "Calendar", icon: CalendarDays }, { id: "workload", label: "Workload", icon: Gauge }, { id: "activity", label: "Activity", icon: ShieldCheck }] as const).filter(v => v.id !== "activity" || manages).map(v => <button role="tab" tabIndex={view === v.id ? 0 : -1} aria-selected={view === v.id} key={v.id} onClick={() => setView(v.id)} className={view === v.id ? "active" : ""}><v.icon size={16} />{v.label}{v.id === "people" && <span data-count-badge data-count-tone="purple">{members.length}</span>}</button>)}<Link className="wb-extra-tab" to={projects.length?`/pms/projects/${createProjectId}/gantt`:`/pms/projects?workspace=${selected}`}><Gauge size={16}/>Timeline</Link><Link className="wb-extra-tab" to={`/pms/reports?workspace=${selected}`}><FileText size={16}/>Reports</Link></div><div className="wb-view-actions"><ModuleNewMenu>{(moduleActions, menuLoading) => <NewMenu disabled={loading || detailsLoading || menuLoading} actions={[
          ...(canEdit ? [{ label: "Task", description: "Capture work and assign your team", icon: CheckCircle2, onSelect: () => projects.length ? (setQuickWorkType("Task"), setShowTaskCreate(true)) : manages ? openModal("project") : setNotice("Ask a workspace admin to create the first project.") }] : []),
          ...(canEdit && projects.length ? ([{ label: "Story", icon: FileText, type: "Story" }, { label: "Bug", icon: Bug, type: "Bug" }] as const).map(item => ({ label: item.label, icon: item.icon, description: "Create a work item and assign collaborators", onSelect: () => { setQuickWorkType(item.type); setShowTaskCreate(true); } })) : []),
          ...(manages ? [{ label: "Project", description: "Organize a new initiative", icon: Folder, onSelect: () => openModal("project") }, { label: "Add existing person", description: "Add registered people directly", icon: Users, onSelect: () => setAddingPeople(true) }] : []),
          ...(canCreateWorkspace ? [{ label: "Workspace", description: "Create a home for another team", icon: LayoutGrid, onSelect: () => openModal("workspace") }] : []),
          ...moduleActions.filter(action => !["Task", "Story", "Bug", "Project", "Workspace"].includes(action.label)),
        ]} />}</ModuleNewMenu><details className="wb-board-options"><summary data-overflow-trigger aria-label="Board options">...</summary><div><PageWorkTools contextual/><button onClick={()=>setChatOpen(value=>!value)}><MessageSquare size={15}/>{chatOpen?"Hide chat":"Team chat"}</button><Link to={`/pms/recovery?workspace=${selected}`}>Recovery</Link>{canEdit&&workspace&&<UndoRedo workspaceId={workspace.id} refreshKey={tasks} onChanged={()=>{void loadDetails()}} onError={setError}/>}</div></details></div><span className="ws-view-hint">{view === "calendar" ? "Double-click a date to add a task. Drag to reschedule." : view === "workload" ? "Shared effort, split across collaborators." : view === "people" ? "A clear view of who’s doing what" : canEdit ? "Double-click to open · Right-click for actions · Drag to move" : "You have read-only access"}</span></div>
          <div className={`ws-work-and-chat ${chatOpen ? "chat-open" : ""}`}><div className="ws-work-area"><><WorkspaceWork totalTaskCount={tasks.length} filterRevision={filtersVersion} onViewChange={setView} searchInputRef={searchRef} renderPlanning={filteredTasks => (view === "calendar" || view === "workload") ? <WorkspacePlanning sharedFilters onRefresh={loadDetails} key={workspace.id} canEdit={canEdit} onUpdate={updateTask} onCreate={(day,project) => { setCalendarCreate({day,project}); setQuickWorkType("Task"); setShowTaskCreate(true); }} view={view} tasks={filteredTasks} members={members} projects={projects} onOpen={setTaskOpen} /> : view === "activity" ? <WorkspaceActivity key={workspace.id} workspaceId={workspace.id} onOpen={setTaskOpen} /> : null} workspaceId={selected} onQueryChange={setQuery} onCreateTask={()=>{if(projects.length){setQuickWorkType("Task");setShowTaskCreate(true)}else if(manages)openModal("project");else setNotice("Ask an administrator to create a project first.")}} key={`${user?.id}:${user?.access?.companyId}:${selected}:${filtersVersion}`} onClearSearch={() => {setQuery("");setTaskScope("all")}} tasks={scopedTasks} members={members} projects={projects} view={view} query={query} projectFilter={projectFilter} setProjectFilter={setProjectFilter} assigneeFilter={assigneeFilter} setAssigneeFilter={setAssigneeFilter} canEdit={canEdit} updateTask={updateTask} onOpen={id => { setError(""); setTaskOpen(id); }} onRefresh={loadDetails} onInvite={manages ? () => setAddingPeople(true) : undefined} onError={setError} onNotice={setNotice} renderMemberActions={m => {
            const editable = manages && m.role !== "Owner" && (workspace.role === "Owner" || m.role !== "Admin");
            return editable ? <><NativeSelect aria-label={`Role for ${m.email}`} value={m.role} disabled={busy} onChange={e => { const next = e.target.value; void act(async () => { await api.patch(`${base}/workspaces/${workspace.id}/members/${m.id}`, { role: next }); await loadDetails(); }); }}>{["Admin", "Member", "Guest"].filter(r => workspace.role === "Owner" || r !== "Admin").map(r => <option key={r}>{r}</option>)}</NativeSelect><button disabled={busy} onClick={() => { void act(async () => { await api.delete(`${base}/workspaces/${workspace.id}/members/${m.id}`); await loadDetails(); }); }}>Remove</button></> : <span><ShieldCheck size={12} />{m.role === "Owner" ? "Workspace owner" : m.role === "Guest" ? "Can view work" : "Can collaborate"}</span>;
          }} /></>
          </div><div id="workspace-collaboration" className="ws-collaboration-panel" hidden={!chatOpen}><WorkspaceCollaboration enabled={chatOpen} key={workspace.id} workspaceId={workspace.id} canEdit={canEdit} tasks={tasks} onOpen={setTaskOpen} /></div></div>
          {view === "people" && manages && <section className="ws-invitations" aria-label="Workspace invitations"><h3>Invitations · {invitations.filter(i => i.status === "pending").length} waiting</h3><p className="text-sm text-slate-500">Share the invitation link with your teammate. Members appear above after they accept.</p>{!invitations.length && <p>No invitations yet.</p>}{invitations.map(i => <div key={i.id}><span>{i.email}<small>{i.role} · {i.status === "pending" ? i.account_exists ? "Waiting for acceptance" : "Waiting for account activation" : i.status === "accepted" ? "Accepted · Team member" : i.status}</small></span>{["pending", "expired", "revoked"].includes(i.status) && !members.some(m => m.email.toLowerCase() === i.email.toLowerCase()) && <button disabled={busy} onClick={() => { void act(async () => { const { data } = await api.post(`${base}/workspaces/${workspace.id}/invitations`, { email: i.email, role: i.role }); setInviteLink(`${window.location.origin}/pms/invitation?token=${encodeURIComponent(data.token)}`); setEmail(""); setRole(i.role); setModal("invite"); setNotice("New invitation link created; previous link is no longer valid"); await loadDetails(); }); }}>Resend / new link</button>}{i.status === "pending" && <button disabled={busy} onClick={() => { void act(async () => { await api.delete(`${base}/workspaces/${workspace.id}/invitations/${i.id}`); setNotice("Invitation revoked"); await loadDetails(); }); }}>Revoke</button>}</div>)}</section>}
          <footer className="ws-board-footer"><span><CheckCircle2 size={14} />One shared source of truth. Every view stays in sync.</span><CompactActions><Link to={`/pms/workspace-tools?workspace=${workspace.id}`}>Workspace tools<ArrowUpRight size={12} /></Link>{manages && <Link to={`/pms/automation?workspace=${workspace.id}`}><Zap size={14} />Automation</Link>}{projects.length > 0 && <Link to={`/pms/projects/${createProjectId}/gantt`}>Open Gantt<ArrowUpRight size={12} /></Link>}{manages && <Button type="submit" variant="default" onClick={() => openModal("project")}><Plus size={14} />Create project</Button>}</CompactActions></footer>
          </>}
        </>}
      </RouteContent>
    </div>
    {navigationOpen && <button className="kf-navigation-overlay" aria-label="Close navigation overlay" onClick={()=>setNavigationOpen(false)} />}
    <div className="ws-notice" role="status" aria-live="polite">{notice && <><CheckCircle2 size={16} />{notice}</>}</div>
    <Dialog.Root open={modal !== null} onOpenChange={open => { if (!open) setModal(null); }}><Dialog.Portal><Dialog.Overlay className="ws-overlay" /><Dialog.Content className="ws-modal" data-smart-create-enhanced="true" data-smart-create-size="standard"><Dialog.Close className="ws-modal-close" aria-label="Close dialog"><X size={19} /></Dialog.Close><span className="ws-modal-symbol">{modal === "invite" ? <Users size={24} /> : <Folder size={24} />}</span><Dialog.Title>{modal === "workspace" ? "A home for your team." : modal === "invite" ? "Great work takes great people." : modal === "project" ? "Make room for your next idea." : "Your team is waiting."}</Dialog.Title><Dialog.Description>{modal === "invite" ? "Create a secure share link for your teammate’s email. An invitation email is queued automatically; you can also copy the secure link." : modal === "project" ? "Create a project inside this workspace." : modal === "join" ? "Sign in with the invited email and accept your invitation." : "Give your workspace a name. Invite your teammates next."}</Dialog.Description>{error && <div role="alert" className="ws-alert">{error}</div>}<CompactForm onSubmit={e => { e.preventDefault(); void submitModal(); }}>{modal === "workspace" || modal === "project" ? <><label>{modal === "workspace" ? "Workspace name" : "Project name"}<input aria-label={modal === "workspace" ? "Workspace name" : "Project name"} autoFocus value={name} onChange={e => { setName(e.target.value); if (modal === "project" && !keyEdited) setProjectKey(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6)); }} required maxLength={180} placeholder={modal === "workspace" ? "e.g. Product studio" : "e.g. Website launch"} /></label>{modal === "project" && <label>Project key<input aria-label="Project key" value={projectKey} onChange={e => { setKeyEdited(true); setProjectKey(e.target.value.toUpperCase()); }} required maxLength={10} pattern="[A-Z0-9]{2,10}" placeholder="e.g. WEB" /></label>}</> : modal === "join" ? <label>Invitation token<input aria-label="Invitation token" autoFocus value={token} onChange={e => setToken(e.target.value)} required /><small>Invitations expire after seven days.</small></label> : <><label>Email address<input aria-label="Teammate email" type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="teammate@company.com" autoFocus /></label><label>Workspace role<NativeSelect aria-label="Invitation role" value={role} onChange={e => setRole(e.target.value)}>{["Admin", "Member", "Guest"].filter(r => workspace?.role === "Owner" || r !== "Admin").map(r => <option key={r}>{r}</option>)}</NativeSelect><small>{role === "Guest" ? "Can view work without making changes." : role === "Admin" ? "Can manage projects, invitations, and members." : "Can create, assign, and update tasks and add comments."}</small></label></>}{modal === "project" && <CustomFieldsForm placement="quick_create" entity="project" values={projectCustomFields} onChange={setProjectCustomFields}/>} {inviteLink && <div className="ws-share-link"><span><CheckCircle2 size={15} />Invitation ready</span><p>Waiting for activation or acceptance. An email is queued for delivery. You can also copy this link; existing users receive an in-app notification.</p><input aria-label="Share invitation link" readOnly value={inviteLink} onFocus={e => e.target.select()} /><Button variant="outline" type="button" onClick={() => { void act(async () => { await navigator.clipboard.writeText(inviteLink); setNotice("Invitation link copied"); }); }}><Copy size={14} />Copy link</Button></div>}<div className="ws-modal-actions"><Dialog.Close className="ws-button ws-outline" type="button">{inviteLink ? "Done" : "Cancel"}</Dialog.Close><Button type="submit" variant="default" className="ws-button ws-primary" disabled={busy}>{busy && <Loader2 size={14} className="animate-spin" />}{modal === "workspace" ? "Create workspace" : modal === "project" ? "Create project" : modal === "join" ? "Accept invitation" : "Create invitation"}</Button></div></CompactForm></Dialog.Content></Dialog.Portal></Dialog.Root>
    <QuickCreateProject open={creatingProject} initialWorkspace={selected || undefined} onClose={() => setCreatingProject(false)} onCreated={() => { void loadDetails().catch(e => setError(workspaceError(e))); }} />
    <CreateTaskModal initialDueDate={calendarCreate?.day || ""} initialWorkType={quickWorkType} projects={projects} workspacePeople={assignablePeople} isOpen={showTaskCreate} onClose={() => { setShowTaskCreate(false); setCalendarCreate(null); }} projectId={Number(calendarCreate?.project) || createProjectId || 0} onTaskCreated={(task, createAnother) => { if (!createAnother) { setShowTaskCreate(false); setCalendarCreate(null); } if (!calendarCreate) setView("board"); setQuery(""); setAssigneeFilter(""); setProjectFilter(String(task.project_id)); setFiltersVersion(v => v + 1); setNotice("Task created — visible in your workspace"); void loadDetails().catch(e => setError(workspaceError(e))); }} />
    <AddExistingPeopleDialog open={addingPeople} onClose={() => setAddingPeople(false)} workspaceId={workspace?.id} onAdded={loadDetails} />
    <TaskDrawer error={error} task={!requestedUnavailable&&!pendingWorkspaceScope?tasks.find(t => t.id === taskOpen):undefined} members={members} canEdit={canEdit} onClose={() => setTaskOpen(null)} onUpdate={updateTask} onRefresh={loadDetails} onError={setError} />
  </div>;
}
