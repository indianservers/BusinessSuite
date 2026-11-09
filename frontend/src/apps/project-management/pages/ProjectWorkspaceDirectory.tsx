import { FolderKanban, Layers3, ListTodo, Users } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { pmsWorkspaceViews as views } from "./pms-workspace-views";
import ManagedWorkspaceDirectory from "@/shared/workspace/ManagedWorkspaceDirectory";
import { WorkspaceMemberPanel } from "./WorkspaceMemberPanel";

export default function ProjectWorkspaceDirectory() {
  const user = useAuthStore(state => state.user);
  const allowed = (path: string) => canAccessRoute(path.split(/[?#]/)[0], user?.role, user?.is_superuser);
  const grant = user?.access?.grants.project_management;
  const create = user?.is_superuser || !grant || grant.enabled && grant.actions.includes("create");
  const actions = [{ label: "Create project", href: "/pms/projects/new", icon: FolderKanban }, { label: "Create task", href: "/pms/tasks/new", icon: ListTodo }, { label: "Manage people", href: "/pms/people", icon: Users }, { label: "View workload", href: "/pms/workload", icon: Layers3 }].filter(action => allowed(action.href) && (!action.href.endsWith("/new") || create));
  return <ManagedWorkspaceDirectory module="pms" title="Workspaces" description="Organize projects, teams, tasks and delivery in dedicated spaces." icon={Layers3} views={views.filter(view => allowed(view.href))} actions={actions} renderTeam={workspace => <WorkspaceMemberPanel id={workspace.id} canManage={workspace.can_manage} />} />;
}
