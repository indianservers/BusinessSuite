import { Link } from "react-router-dom";
import { Flag } from "lucide-react";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import ModuleNavigation from "./ModuleNavigation";

export default function WorkspaceBoardNavigation({ projectId, ...props }: { workspaceId?: number; projectId?: number; collapsed: boolean; onNavigate: () => void }) {
  const user = useAuthStore(state => state.user);
  const milestones = projectId ? `/pms/projects/${projectId}/milestones` : undefined;
  return <>
    <ModuleNavigation {...props} modulePath="/pms" />
    {milestones && canAccessRoute(milestones, user?.role, user?.is_superuser) && <Link className="nav-link mx-3" to={milestones} onClick={props.onNavigate} title="Project milestones"><Flag size={17} />{!props.collapsed && "Project milestones"}</Link>}
  </>;
}
