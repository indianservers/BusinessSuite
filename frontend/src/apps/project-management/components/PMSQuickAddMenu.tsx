import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { useQueryClient } from "@tanstack/react-query";
import { pmsWorkspaceOptions } from "@/shared/workspace/pms-workspace-options";
import { workspaceDataScope } from "@/shared/workspace/workspace-management-types";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import { useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Folder, Users, LayoutGrid, Bug, FileText } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import NewMenu, { type NewAction } from "@/components/app/NewMenu";
import { contextualDestination } from "@/shared/creation/registry";


type QuickAddProps = { children?: (actions: NewAction[], loading?: boolean) => ReactNode };

export default function PMSQuickAddMenu(props: QuickAddProps = {}) {
  const scope = useRecordScope(), location = useLocation();
  return <ScopedPMSQuickAddMenu key={`${scope}:${location.pathname}:${location.search}`} {...props} scope={scope}/>;
}

function ScopedPMSQuickAddMenu({ children, scope }: QuickAddProps & {scope:string}) {
  const location = useLocation();
  const routerNavigate = useNavigate();
  const ownsScope = useRecordScopeOwner();
  const navigate = (path: string) => { if (ownsScope()) routerNavigate(contextualDestination(path, location)); };
  const user = useAuthStore(s => s.user);
  const client = useQueryClient();
  const workspaceScope = workspaceDataScope(user);
  const [context, setContext] = useState<{ id: number; role: string; name: string }>();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true; setLoading(true); setContext(undefined);
    const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1];
    void Promise.all([
      client.fetchQuery(pmsWorkspaceOptions(workspaceScope)),
      project ? client.fetchQuery({
        queryKey: ["pms-quick-add-project-context", workspaceScope, project],
        queryFn: ({signal}) => api.get<{ workspace_id?: number }>(`/project-management/projects/${project}`, {signal, timeout:15000}).then(r => r.data.workspace_id ?? null),
        staleTime: 30000,
        retry: false,
      }).catch(() => undefined) : Promise.resolve(undefined),
    ]).then(([data, projectWorkspace]) => {
      if (!active) return;
      const preferred = projectWorkspace || Number(new URLSearchParams(location.search).get("workspace")) || Number(localStorage.getItem(`pms-workspace-${user?.id}`));
      setContext(data.find(w => w.id === preferred) || data[0]);
    }).catch(() => undefined).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [location.pathname, location.search, user?.id, scope, workspaceScope, client]);
  const open = (kind: string) => {
    const params = new URLSearchParams({ new: kind });
    if (context) params.set("workspace", String(context.id));
    const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1];
    if (project) params.set("project", project);
    navigate(`/pms/workspaces?${params}`);
  };
  const actions: NewAction[] = [];
  actions.push({ label: "Private note", description: "Capture an idea, with or without a project", icon: FileText, menuPaths: ["/pms/notes"], onSelect: () => { const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1]; navigate(`/pms/notes?new=1${project ? `&project=${project}` : ""}`); } });
  if (context && context.role !== "Guest") {
    for (const [label, kind, icon] of [["Task", "task", CheckCircle2], ["Story", "story", FileText], ["Bug", "bug", Bug]] as const) actions.push({ label, description: `Add to ${context.name}`, icon, menuPaths: kind === "task" ? ["/pms/tasks", "/pms/my-work", "/pms/backlog", "/pms/work-hub"] : [], onSelect: () => navigate(`/pms/tasks/new?workType=${label}&workspace=${context.id}`) });
  }
  if (context && ["Owner", "Admin"].includes(context.role)) actions.push({ label: "Project", description: `Organize work in ${context.name}`, icon: Folder, menuPaths: ["/pms/projects"], onSelect: () => navigate(`/pms/projects/new?workspace_id=${context.id}`) }, { label: "User / invitation", description: "Invite a person with a secure share link", icon: Users, menuPaths: ["/pms/members", "/pms/people"], onSelect: () => open("user") });
  if (canAccessRoute("/pms/projects/new", user?.role, user?.is_superuser)) actions.push({ label: "Workspace", description: "Create a workspace for a team", icon: LayoutGrid, menuPaths: ["/pms/workspaces"], onSelect: () => open("workspace") });
  return children ? <>{children(loading ? [] : actions, loading)}</> : <NewMenu actions={actions} disabled={loading} />;
}
