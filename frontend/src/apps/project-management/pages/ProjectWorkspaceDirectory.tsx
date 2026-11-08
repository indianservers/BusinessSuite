import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Layers3, ListTodo, Plus, Users } from "lucide-react";
import { api } from "@/services/api";
import { recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { usePageRefresh } from "@/lib/page-refresh";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { WorkspaceDirectory } from "@/shared/workspace/WorkspaceDirectory";
import { WorkspaceModuleLinks } from "@/shared/workspace/WorkspaceModuleLinks";
import { workspaceBase, workspaceError } from "./workspaceTypes";

type Workspace = { id: number; name: string; role: string; description?: string; owners?: string[]; member_count?: number; created_at?: string; project_count?: number; task_count?: number; completed_task_count?: number };
export default function ProjectWorkspaceDirectory() {
  const user = useAuthStore(s => s.user);
  const scope = `${user?.id}:${user?.access?.companyId}:${(sessionStorage.getItem("suite-organization") || "")}:${(sessionStorage.getItem("suite-branch") || "")}`;
  const authorization = JSON.stringify([user?.role, user?.is_superuser, user?.access?.grants.project_management]);
  return <ProjectDirectoryContent key={`${scope}:${authorization}`} scope={scope} authorization={authorization} />;
}
function ProjectDirectoryContent({ scope, authorization }: { scope: string; authorization: string }) {
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const queryKey = ["workspace-directory", "pms", scope, authorization];
  const query = useQuery({ queryKey, queryFn: ({ signal }) => api.get<Workspace[]>(`${workspaceBase}/workspaces`, { signal }).then(result => result.data), staleTime: 30_000, retry: false });
  usePageRefresh(() => query.refetch());
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const saved = (event: Event) => {
      const change = (event as CustomEvent<RecordSaved>).detail;
      if (!creating && /\/project-management\/(workspaces|projects|tasks|task-studio)(?:\/|$|\?)/.test(change.url)) void qc.invalidateQueries({ queryKey: ["workspace-directory", "pms", scope, authorization] });
    };
    window.addEventListener(recordSavedEvent, saved);
    return () => window.removeEventListener(recordSavedEvent, saved);
  }, [qc, scope, authorization, creating]);
  const grant = user?.access?.grants.project_management;
  const canCreate = Boolean(user && canAccessRoute("/pms/projects/new", user.role, user.is_superuser) && (user.is_superuser || !grant || grant.enabled && grant.actions.includes("create")));
  const create = useMutation({ mutationFn: (value: string) => api.post<Workspace>(`${workspaceBase}/workspaces`, { name: value }).then(result => result.data), onSuccess: workspace => {
    qc.setQueryData<Workspace[]>(queryKey, current => [...(current || []).filter(row => row.id !== workspace.id), workspace]);
    void qc.invalidateQueries({ queryKey });
    setCreating(false); setName(""); setNotice(`Workspace “${workspace.name}” created. Open it to add projects and members.`);
  } });
  const denied = [401, 403, 404].includes((query.error as { response?: { status?: number } } | null)?.response?.status || 0);
  const entries = (denied ? [] : query.data || []).map(workspace => ({ id: String(workspace.id), name: workspace.name, description: workspace.description, href: `/pms/workspaces?workspace=${workspace.id}`, role: workspace.role, owner: workspace.owners?.join(", "), members: workspace.member_count, createdAt: workspace.created_at, projects: workspace.project_count, tasks: workspace.task_count, completedTasks: workspace.completed_task_count, status: "Active", icon: FolderKanban, links: [
    { label: "Open workspace", href: `/pms/workspaces?workspace=${workspace.id}` },
    { label: "View projects", href: `/pms/projects?workspace=${workspace.id}` },
    { label: "Project settings", href: "/pms/settings" },
  ].filter(link => canAccessRoute(link.href.split("?")[0], user?.role, user?.is_superuser)) }));
  const actions = [
    { label: "Create project", href: "/pms/projects/new", icon: FolderKanban },
    { label: "Create task", href: "/pms/tasks/new", icon: ListTodo },
    { label: "Manage people", href: "/pms/people", icon: Users },
    { label: "View workload", href: "/pms/workload", icon: Layers3 },
  ].filter(action => canAccessRoute(action.href, user?.role, user?.is_superuser) && (!action.href.endsWith("/new") || user?.is_superuser || !grant || grant.enabled && grant.actions.includes("create")));
  return <><WorkspaceDirectory module="pms" title="Workspaces" description="Organize projects, teams, tasks and delivery in dedicated spaces." icon={Layers3} entries={entries} loading={query.isFetching} error={query.isError ? workspaceError(query.error) : undefined} onRetry={() => void query.refetch()} onCreate={canCreate ? () => { create.reset(); setCreating(true); } : undefined} actions={actions}>
    {notice && <p role="status" className="mt-4 text-sm text-emerald-700">{notice}</p>}
    <WorkspaceModuleLinks current="pms" />
  </WorkspaceDirectory>
  <Dialog open={creating} onOpenChange={open => { if (!create.isPending) setCreating(open); }}><DialogContent onInteractOutside={event => { if (create.isPending) event.preventDefault(); }} onEscapeKeyDown={event => { if (create.isPending) event.preventDefault(); }}><DialogTitle className="text-xl font-semibold">Create Workspace</DialogTitle><p className="text-sm text-muted-foreground">Give your project team a dedicated space. You will be its owner.</p><form className="space-y-5" onSubmit={event => { event.preventDefault(); if (name.trim() && !create.isPending) create.mutate(name.trim()); }}><label className="block space-y-2 text-sm font-medium"><span>Workspace name</span><Input autoFocus required maxLength={180} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Client delivery" disabled={create.isPending} /></label>{user?.access?.companyName && <p className="text-xs text-muted-foreground">Company: {user.access.companyName}</p>}{create.isError && <p role="alert" className="text-sm text-destructive">{workspaceError(create.error)}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={create.isPending} onClick={() => setCreating(false)}>Cancel</Button><Button disabled={create.isPending || !name.trim()}><Plus size={16} />{create.isPending ? "Creating…" : "Create Workspace"}</Button></div></form></DialogContent></Dialog></>;
}
