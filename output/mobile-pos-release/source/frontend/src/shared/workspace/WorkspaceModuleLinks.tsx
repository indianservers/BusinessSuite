import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
const modules = [{ id: "pms", label: "Projects" }, { id: "crm", label: "CRM" }, { id: "hrms", label: "People" }, { id: "srm", label: "Sales" }, { id: "fam", label: "Finance" }];
export function WorkspaceModuleLinks({ current }: { current: string }) {
  const user = useAuthStore(s => s.user);
  return <nav className="wd-module-links" aria-label="Module workspaces">{modules.filter(module => canAccessRoute(`/${module.id}/workspaces`, user?.role, user?.is_superuser)).map(module => <Link key={module.id} to={`/${module.id}/workspaces`} aria-current={module.id === current ? "page" : undefined}>{module.label}</Link>)}</nav>;
}
