import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Folder, Users, LayoutGrid, Bug, FileText } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import NewMenu, { type NewAction } from "@/components/app/NewMenu";

export default function PMSQuickAddMenu() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore(s => s.user);
  const [context, setContext] = useState<{ id: number; role: string; name: string }>();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true; setLoading(true); setContext(undefined);
    const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1];
    void Promise.all([
      api.get<{ id: number; role: string; name: string }[]>("/project-management/workspaces"),
      project ? api.get<{ workspace_id?: number }>(`/project-management/projects/${project}`).then(r => r.data.workspace_id).catch(() => undefined) : Promise.resolve(undefined),
    ]).then(([{ data }, projectWorkspace]) => {
      if (!active) return;
      const preferred = projectWorkspace || Number(new URLSearchParams(location.search).get("workspace")) || Number(localStorage.getItem(`pms-workspace-${user?.id}`));
      setContext(data.find(w => w.id === preferred) || data[0]);
    }).catch(() => undefined).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [location.pathname, location.search, user?.id]);
  const open = (kind: string) => {
    const params = new URLSearchParams({ new: kind });
    if (context) params.set("workspace", String(context.id));
    const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1];
    if (project) params.set("project", project);
    navigate(`/pms/workspaces?${params}`);
  };
  const actions: NewAction[] = [];
  actions.push({ label: "Private note", description: "Capture an idea, with or without a project", icon: FileText, onSelect: () => { const project = location.pathname.match(/\/pms\/projects\/(\d+)/)?.[1]; navigate(`/pms/notes?new=1${project ? `&project=${project}` : ""}`); } });
  if (context && context.role !== "Guest") {
    for (const [label, kind, icon] of [["Task", "task", CheckCircle2], ["Story", "story", FileText], ["Bug", "bug", Bug]] as const) actions.push({ label, description: `Add to ${context.name}`, icon, onSelect: () => open(kind) });
  }
  if (context && ["Owner", "Admin"].includes(context.role)) actions.push({ label: "Project", description: `Organize work in ${context.name}`, icon: Folder, onSelect: () => open("project") }, { label: "User / invitation", description: "Invite a person with a secure share link", icon: Users, onSelect: () => open("user") });
  if (canAccessRoute("/pms/projects/new", user?.role, user?.is_superuser)) actions.push({ label: "Workspace", description: "Create a workspace for a team", icon: LayoutGrid, onSelect: () => open("workspace") });
  return <NewMenu actions={actions} disabled={loading} />;
}
