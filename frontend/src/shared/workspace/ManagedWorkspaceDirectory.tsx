import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Archive, Layers3, ListTodo, Plus, Settings2, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useWorkspaceContext } from "./useWorkspaceContext";
import { usePageRefresh } from "@/lib/page-refresh";
import { recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { WorkspaceDirectory, type DirectoryAction, type DirectoryMetric } from "./WorkspaceDirectory";
import { WorkspaceEditor } from "./WorkspaceEditor";
import { WorkspaceActivityFeed } from "./WorkspaceActivityFeed";
import { WorkspaceModuleLinks } from "./WorkspaceModuleLinks";
import { workspaceIcon } from "./workspace-icons";
import { workspaceApiBase, workspaceDataScope, workspaceSelectionKey, type WorkspaceActivity, type WorkspaceDraft, type WorkspaceModule, type SavedWorkspace } from "./workspace-management-types";

type DomainView = { id: string; label: string; href: string; icon: LucideIcon; description?: string };
type Props = { module: WorkspaceModule; title: string; description: string; icon: LucideIcon; views: DomainView[]; actions: DirectoryAction[]; metrics?: DirectoryMetric[]; children?: ReactNode; renderTeam?: (workspace: SavedWorkspace) => ReactNode };
export default function ManagedWorkspaceDirectory(props: Props) {
  const user = useAuthStore(state => state.user);
  const context = useWorkspaceContext();
  const scope = workspaceDataScope(user);
  if (!context.ready) return <main className="workspace-directory"><p role={context.error ? "alert" : "status"}>{context.loading ? "Loading workspace branch context…" : "Choose an available branch to open workspaces."}</p>{context.error && <Button variant="outline" onClick={context.retry}>Retry branch context</Button>}</main>;
  return <ManagedWorkspaceContent key={`${props.module}:${scope}`} {...props} scope={scope} />;
}
function ManagedWorkspaceContent({ module, title, description, icon, views, actions, metrics, children, renderTeam, scope }: Props & { scope: string }) {
  const user = useAuthStore(state => state.user);
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const base = workspaceApiBase(module);
  const key = ["managed-workspaces", module, scope];
  const selected = params.get("space");
  const createIntent = params.get("new") === "workspace";
  const tab = params.get("spaceTab") || "overview";
  const [editor, setEditor] = useState<SavedWorkspace | "new" | null>(null);
  const [pendingStatus, setPendingStatus] = useState<SavedWorkspace | null>(null);
  const [notice, setNotice] = useState("");
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => api.get<{ items: SavedWorkspace[]; can_create: boolean; branch_name?: string }>(base, { signal }).then(response => response.data), staleTime: 30_000, retry: false });
  useEffect(() => {
    if (!createIntent || !query.isSuccess) return;
    if (query.data.can_create) setEditor("new"); else setNotice("Workspace creation is unavailable for your current access.");
    setParams(current => { const next = new URLSearchParams(current); next.delete("new"); return next; }, { replace: true });
  }, [createIntent, query.isSuccess, query.data?.can_create, setParams]);
  const denied = [401, 403, 404].includes((query.error as { response?: { status?: number } } | null)?.response?.status || 0);
  const items = denied ? [] : query.data?.items || [];
  const detail = useQuery({ queryKey: ["managed-workspace-detail", module, scope, selected], enabled: Boolean(selected), queryFn: ({ signal }) => api.get<SavedWorkspace>(`${base}/${selected}`, { signal }).then(response => response.data), staleTime: 0, gcTime: 0, retry: false });
  const workspace = detail.isError ? undefined : detail.data;
  const selectionKey = workspaceSelectionKey(user, module);
  useEffect(() => {
    if (selected && detail.isSuccess && detail.data.status === "Active") try { localStorage.setItem(selectionKey, selected); } catch { /* Optional selection preference. */ }
  }, [selected, detail.isSuccess, detail.data, selectionKey]);
  const activityKey = ["managed-workspace-activity", module, scope, selected];
  const activity = useQuery({ queryKey: activityKey, queryFn: ({ signal }) => api.get<WorkspaceActivity[]>(`${base}${selected ? `/${selected}` : ""}/activity`, { signal }).then(response => response.data), enabled: query.isSuccess && !denied && (!selected || Boolean(workspace)), retry: false });
  const people = useQuery({ queryKey: ["workspace-eligible-people", module, scope, editor === "new" ? null : editor?.id], queryFn: ({ signal }) => api.get<{ user_id: number; email: string }[]>(`${base}/eligible-people`, { signal, params: editor && editor !== "new" ? { ref: editor.id } : undefined }).then(response => response.data), enabled: Boolean(editor) && module !== "pms", retry: false });
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: key }), qc.invalidateQueries({ queryKey: ["managed-workspace-activity", module, scope] }), qc.invalidateQueries({ queryKey: ["managed-workspace-detail", module, scope] }), qc.invalidateQueries({ queryKey: ["workspace-directory", "pms"] })]);
  usePageRefresh(() => refresh());
  useEffect(() => {
    const saved = (event: Event) => {
      const url = (event as CustomEvent<RecordSaved>).detail.url;
      const relevant = url.includes(base) || url.includes(module === "pms" ? "/project-management/" : module === "hrms" ? "/employees/" : `/${module}/`);
      if (!relevant || url.includes("/workspace-directory") && (editor || pendingStatus)) return;
      void qc.invalidateQueries({ queryKey: ["managed-workspaces", module, scope] });
      if (url.includes(base)) {
        void qc.invalidateQueries({ queryKey: ["managed-workspace-activity", module, scope] });
        void qc.invalidateQueries({ queryKey: ["managed-workspace-detail", module, scope] });
      }
    };
    window.addEventListener(recordSavedEvent, saved); return () => window.removeEventListener(recordSavedEvent, saved);
  }, [qc, module, scope, base, editor, pendingStatus]);
  const mutation = useMutation({ mutationFn: ({ draft, existing }: { draft: WorkspaceDraft; existing?: SavedWorkspace }) => existing ? api.put<SavedWorkspace>(`${base}/${existing.id}`, draft).then(response => response.data) : api.post<SavedWorkspace>(base, draft).then(response => response.data), onError: error => { if ((error as { response?: { status?: number } }).response?.status === 409) void refresh(); }, onSuccess: async saved => { qc.setQueryData(["managed-workspace-detail", module, scope, saved.id], saved); await refresh(); setEditor(null); setPendingStatus(null); setNotice(`Workspace “${saved.name}” saved.`); } });
  function selectTab(value: string) { setParams(current => { const next = new URLSearchParams(current); next.set("spaceTab", value); return next; }); }
  function back() { setParams(current => { const next = new URLSearchParams(current); next.delete("space"); next.delete("spaceTab"); return next; }); }
  const openEditor = (value: SavedWorkspace | "new") => { if (mutation.isPending) return; mutation.reset(); setEditor(value); };
  function changeStatus(item: SavedWorkspace) { mutation.reset(); setPendingStatus(item); }
  const entries = items.map(item => ({ id: item.id, name: item.name, description: item.description, icon: workspaceIcon(item.icon), color: item.color, href: `/${module}/workspaces?space=${item.id}`, category: module.toUpperCase(), role: item.role, owner: item.owners?.join(", "), members: item.member_count, status: item.status, createdAt: item.created_at, updatedAt: item.updated_at, activityCount: (item as SavedWorkspace & { activity_count?: number }).activity_count, projects: item.project_count, tasks: item.task_count, completedTasks: item.completed_task_count,
    links: [{ label: "Workspace overview", href: `/${module}/workspaces?space=${item.id}` }, ...(module === "pms" && item.status === "Active" && views.some(view => view.id === "projects") ? [{ label: "View projects", href: `/pms/projects?workspace=${item.id}` }] : [])], commands: [...(item.can_manage ? [{ label: "Workspace settings", onSelect: () => openEditor(item) }] : []), ...(item.can_archive ? [{ label: item.status === "Active" ? "Archive workspace" : "Restore workspace", onSelect: () => changeStatus(item) }] : [])] }));
  const activityItems = denied || activity.isError ? [] : activity.data || [];
  const primaryAction = actions.find(action => /^(Create|New|Add)\b/.test(action.label));
  const actionHref = (href: string, item: SavedWorkspace) => `${href}${href.includes("?") ? "&" : "?"}${module === "pms" ? href.startsWith("/pms/projects/new") ? "workspace_id" : "workspace" : "space"}=${item.id}`;
  const availableViews = workspace ? views.filter(view => workspace.views.includes(view.id)) : views;
  return <>
    {selected ? <main className="workspace-directory"><button type="button" className="wd-back-link" onClick={back}><ArrowLeft size={16} />All workspaces</button>{detail.isPending ? <p role="status">Checking workspace access…</p> : !workspace ? <div className="wd-error" role="alert">{denied ? "Workspace access is no longer available." : "This workspace is unavailable in the current company and branch."}</div> : <><header className="wd-detail-hero"><span className="wd-hero-icon" style={{ color: workspace.color }}>{(() => { const Icon = workspaceIcon(workspace.icon); return <Icon size={30} />; })()}</span><div><h1>{workspace.name}</h1><p>{workspace.description}</p><small>{title} · {workspace.status} · {workspace.owners?.join(", ") || workspace.role}</small></div>{primaryAction && workspace.status === "Active" && <Button asChild><Link to={actionHref(primaryAction.href, workspace)}><Plus size={16} />{primaryAction.label}</Link></Button>}{workspace.can_manage && <Button variant="outline" onClick={() => openEditor(workspace)}><Settings2 size={16} />Settings</Button>}{workspace.can_archive && <Button variant="outline" onClick={() => changeStatus(workspace)}><Archive size={16} />{workspace.status === "Active" ? "Archive" : "Restore"}</Button>}</header><nav className="wd-detail-tabs" aria-label="Workspace sections">{["overview", "team", "activity"].map(value => <button type="button" key={value} aria-current={tab === value ? "page" : undefined} onClick={() => selectTab(value)}>{value === "overview" ? "Overview" : value === "team" ? "Team & access" : "Activity"}</button>)}{workspace.can_manage && <button type="button" onClick={() => openEditor(workspace)}>Settings</button>}</nav>
      {tab === "activity" ? <WorkspaceActivityFeed items={activityItems} loading={activity.isFetching} error={activity.isError} onRetry={() => void activity.refetch()} /> : tab === "team" ? module === "pms" && renderTeam && workspace.status === "Active" ? renderTeam(workspace) : <section className="wd-activity"><h2><Users size={18} />Workspace team</h2><p>{workspace.visibility === "organization" ? "People with module access in this branch can open this workspace." : "This workspace is open to its owner and listed members."} Record access remains controlled by module permissions.</p><div className="wd-member-edit"><span>{workspace.owners?.join(", ") || `Owner #${workspace.owner_id}`}</span><strong>Owner</strong></div>{workspace.members?.map(member => <div className="wd-member-edit" key={member.user_id}><span>{workspace.member_details?.find(person => person.user_id === member.user_id)?.email || `Member #${member.user_id}`}</span><span>{member.role}</span></div>)}{module !== "pms" && workspace.can_manage && <Button variant="outline" onClick={() => openEditor(workspace)}>Manage members</Button>}</section> : <><section className="wd-branch-overview"><h2>Current branch overview</h2><p>Figures reflect the records you can access in this company and branch.</p><div>{metrics?.map(metric => <div key={metric.label}><metric.icon size={20} /><span>{metric.label}</span><strong>{metric.value}</strong></div>)}{module === "pms" && <><div><Layers3 size={20} /><span>Projects</span><strong>{workspace.project_count ?? "—"}</strong></div><div><Users size={20} /><span>Members</span><strong>{workspace.member_count ?? "—"}</strong></div><div><ListTodo size={20} /><span>Tasks</span><strong>{workspace.task_count ?? "—"}</strong></div><div><ListTodo size={20} /><span>Completed tasks</span><strong>{workspace.completed_task_count ?? "—"}</strong></div></>}</div></section>{workspace.status === "Archived" ? <p className="wd-notice">This workspace is archived. Restore it to resume work.</p> : <section className="wd-domain-tools" aria-label="Workspace tools">{!availableViews.length && <p className="wd-notice">No workspace tools selected.{workspace.can_manage && <Button variant="ghost" onClick={() => openEditor(workspace)}>Choose workspace tools</Button>}</p>}{availableViews.map(view => <Link to={module === "pms" ? `${view.href}${view.href.includes("?") ? "&" : "?"}workspace=${workspace.id}` : `${view.href}${view.href.includes("?") ? "&" : "?"}space=${workspace.id}`} key={view.id}><view.icon size={25} /><strong>{view.label}</strong><span>{view.description}</span></Link>)}</section>}<WorkspaceActivityFeed items={activityItems.slice(0, 5)} loading={activity.isFetching} error={activity.isError} onRetry={() => void activity.refetch()} /></>}
      </>}<WorkspaceModuleLinks current={module} /></main> : <WorkspaceDirectory module={module} title={title} description={description} icon={icon} entries={entries} actions={actions} metrics={denied ? [] : metrics} branchLabel={query.data?.branch_name} notice={module === "pms" ? undefined : "Business figures cover your authorized records in the current company and branch."} loading={query.isFetching} error={query.isError ? errorText(query.error) : undefined} onRetry={() => void query.refetch()} onCreate={query.data?.can_create && !denied ? () => openEditor("new") : undefined} enableManagement>{!denied && <WorkspaceActivityFeed items={activityItems} loading={activity.isFetching} error={activity.isError} onRetry={() => void activity.refetch()} />}<section className="wd-domain-tools" aria-label="Module tools">{views.map(view => <Link key={view.id} to={view.href}><view.icon size={20} /><strong>{view.label}</strong></Link>)}</section>{children}<WorkspaceModuleLinks current={module} /></WorkspaceDirectory>}
    {notice && <p role="status" className="wd-save-notice">{notice}</p>}
    {editor && <WorkspaceEditor key={editor === "new" ? "new" : `${editor.id}:${editor.version}`} workspace={editor === "new" ? undefined : editor} views={views} moduleLabel={title} company={user?.access?.companyName} branchLabel={query.data?.branch_name} pms={module === "pms"} people={(people.data || []).filter(person => person.user_id !== user?.id || editor !== "new")} loadingPeople={people.isFetching} busy={mutation.isPending} error={mutation.isError ? errorText(mutation.error) : people.isError ? "Eligible members could not load. Save other settings or retry after reopening." : undefined} onSave={draft => mutation.mutate({ draft, existing: editor === "new" ? undefined : editor })} onClose={() => setEditor(null)} />}
    {pendingStatus && <Dialog open onOpenChange={open => { if (!open && !mutation.isPending) setPendingStatus(null); }}><DialogContent><DialogTitle>{pendingStatus.status === "Active" ? "Archive workspace?" : "Restore workspace?"}</DialogTitle><p className="text-sm text-muted-foreground">{pendingStatus.name}. Existing business records will be preserved.</p>{mutation.isError && <p role="alert">{errorText(mutation.error)}</p>}<div className="flex justify-end gap-2"><Button variant="outline" disabled={mutation.isPending} onClick={() => setPendingStatus(null)}>Cancel</Button><Button disabled={mutation.isPending} onClick={() => mutation.mutate({ existing: pendingStatus, draft: { name: pendingStatus.name, description: pendingStatus.description, color: pendingStatus.color, icon: pendingStatus.icon, visibility: pendingStatus.visibility, views: pendingStatus.views, members: module === "pms" ? [] : pendingStatus.members || [], expected_version: pendingStatus.version, expected_status: pendingStatus.status, status: pendingStatus.status === "Active" ? "Archived" : "Active" } })}>{mutation.isPending ? "Saving…" : pendingStatus.status === "Active" ? "Archive workspace" : "Restore workspace"}</Button></div></DialogContent></Dialog>}
  </>;
}
function errorText(error: unknown) { const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === "string" ? detail : "Workspace could not be saved. Check the current permissions and try again."; }
