import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowDown, ArrowUp, CheckSquare, Clock3, FileText, Folder, Pin, Star, TrendingUp, Users } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleNav } from "@/lib/roles";
import { emptyPmsNavigation, usePmsNavigation, type PmsPage } from "@/store/pmsNavigation";
import { suiteScope } from "@/store/suitePreferences";
import "./pms-personal-navigation.css";

export const pmsPrimaryPages = [
  { path: "/pms/workspaces?mine=1", label: "My Tasks", icon: CheckSquare },
  { path: "/pms/notes", label: "Notes", icon: FileText },
  { path: "/pms/projects", label: "Projects", icon: Folder },
  { path: "/pms/members", label: "People", icon: Users },
];
export default function PMSPersonalNavigation({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const user = useAuthStore(s => s.user), location = useLocation();
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const saved = usePmsNavigation(s => s.contexts[scope] || emptyPmsNavigation);
  const { visit, pin, move } = usePmsNavigation();
  const permitted = (p: PmsPage) => p.path.startsWith("/pms") && canAccessRoute(p.path.split("?")[0], user?.role, user?.is_superuser);
  const primary = pmsPrimaryPages.filter(permitted);
  const nav = getRoleNav(user?.role, user?.is_superuser, "/pms").filter(p => p.to.startsWith("/pms") && canAccessRoute(p.to, user?.role, user?.is_superuser));
  const available = [...new Map([...primary, ...nav.map(i => ({ path: i.to, label: i.label }))].map(p => [p.path, p])).values()];
  useEffect(() => {
    const params = new URLSearchParams(location.search); params.delete("token"); params.delete("invite");
    const path = location.pathname + (params.size ? `?${params}` : "");
    const primary = pmsPrimaryPages.find(p => p.path === path);
    const exact = getRoleNav(user?.role, user?.is_superuser, "/pms").find(p => p.to === location.pathname);
    const label = primary?.label || (params.get("mine") ? "My Tasks" : undefined) || exact?.label || (/\/projects\/\d+\/members/.test(path) ? `Project #${path.match(/projects\/(\d+)/)?.[1]} members` : /\/projects\/\d+/.test(path) ? `Project #${path.match(/projects\/(\d+)/)?.[1]} work` : "Workspace");
    if (user?.id && location.pathname.startsWith("/pms")) visit(scope, { path, label }, user.id);
  }, [location.pathname, location.search, scope, user?.id, user?.role, user?.is_superuser, visit]);
  const favorites = saved.favorites.filter(permitted);
  const history = Object.entries(saved.visits).filter(([path]) => permitted({ path, label: "" }));
  const defaults = (user?.is_superuser || /admin|manager|hr/i.test(user?.role || "")) ? ["/pms/members", "/pms/projects", "/pms/workspaces?mine=1", "/pms/notes", "/pms/workload"] : ["/pms/workspaces?mine=1", "/pms/notes", "/pms/projects", "/pms/members", "/pms/calendar"];
  const top = history.length > 1 ? [...history].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5).map(([path]) => ({ path, label: available.find(p => p.path === path)?.label || saved.recent.find(p => p.path === path)?.label || "Workspace" })) : defaults.map(path => available.find(p => p.path === path)).filter((p): p is PmsPage => !!p).slice(0, 5);
  const recent = saved.recent.filter(permitted).slice(0, 5);
  const row = (page: PmsPage, title: string, Icon = Star) => <div className="pms-personal-row" key={page.path}>
    <Link to={page.path} onClick={onNavigate} title={page.label} aria-label={`${title}: ${page.label}`} aria-current={location.pathname + location.search === page.path ? "page" : undefined}><Icon size={16} />{!collapsed && <span>{page.label}</span>}</Link>
    {!collapsed && <button type="button" className={favorites.some(p => p.path === page.path) ? "is-pinned" : ""} aria-label={`${favorites.some(p => p.path === page.path) ? "Unpin" : "Pin"} ${page.label}`} onClick={() => pin(scope, page)}><Pin size={13} /></button>}
  </div>;
  return <div className="pms-personal-nav">
    <section aria-label="Daily work">{primary.map(p => row(p, "Daily work", p.icon))}</section>
    {!!favorites.length && <section aria-label="Favorite pages">{!collapsed && <h3>Favorites · your order</h3>}{favorites.map(p => row(p, "Favorite"))}</section>}
    <section aria-label="Top 5">{!collapsed && <><h3>Top 5</h3>{history.length <= 1 && <p className="pms-nav-hint">Suggested for your role. Frequent pages appear as you work.</p>}</>}{top.map(p => row(p, "Top 5", TrendingUp))}</section>
    <section aria-label="Recent 5">{!collapsed && <h3>Recent 5</h3>}{recent.map(p => row(p, "Recent 5", Clock3))}{!collapsed && !recent.length && <p className="pms-nav-hint">Recently opened work will appear here.</p>}</section>
    {!collapsed && <details className="pms-favorites-editor"><summary>Pin & reorder pages</summary><p className="pms-nav-hint">Favorites keep your chosen order; visit counts never rearrange them. Saved per account and organization in this browser.</p>{favorites.map((p, index) => <div className="pms-favorite-order" key={p.path}><span>{p.label}</span><button aria-label={`Move ${p.label} up`} disabled={index === 0} onClick={() => move(scope, p.path, -1)}><ArrowUp size={14}/></button><button aria-label={`Move ${p.label} down`} disabled={index === favorites.length - 1} onClick={() => move(scope, p.path, 1)}><ArrowDown size={14}/></button></div>)}<div className="pms-pin-options">{available.map(p => <label key={p.path}><input type="checkbox" checked={favorites.some(f => f.path === p.path)} onChange={() => pin(scope, p)} />{p.label}</label>)}</div></details>}
  </div>;
}
