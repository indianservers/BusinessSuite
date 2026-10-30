import { consolidateNavigation, activeWorkspace, workspacePageHref } from "@/lib/navigation-workspaces";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, Search } from "lucide-react";
import { getRoleNav, canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import PMSPersonalNavigation from "./PMSPersonalNavigation";

export default function PMSNavigationMenu({ workspaceId, collapsed, onNavigate }: { workspaceId?: number; collapsed: boolean; onNavigate: () => void }) {
  const user = useAuthStore(s => s.user);
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const available = getRoleNav(user?.role, user?.is_superuser, "/pms").filter(i => i.to.startsWith("/pms") && canAccessRoute(i.to, user?.role, user?.is_superuser));
  const items = query.trim() ? available : consolidateNavigation(available);
  const currentWorkspace = activeWorkspace(consolidateNavigation(available), location.pathname);
  const groups = [...new Set(items.map(i => i.group || "Other"))];
  return <div className="pms-navigation-menu">
    {!query && <PMSPersonalNavigation collapsed={collapsed} onNavigate={onNavigate} />}
    {!collapsed && <label className="pms-menu-search"><Search size={15} /><input aria-label="Search PMS menu" placeholder="Find a page…" value={query} onChange={e => setQuery(e.target.value)} /></label>}
    {groups.map(group => {
      const children = items.filter(i => i.group === group && `${group} ${i.label}`.toLowerCase().includes(query.toLowerCase()));
      if (!children.length) return null;
      const active = currentWorkspace?.group === group || children.some(i => location.pathname === i.to || (i.to !== "/pms" && location.pathname.startsWith(i.to + "/")));
      const open = !!query || collapsed || (expanded[group] ?? (active || group === "Overview"));
      return <details key={group} className="pms-menu-group" open={open}>
        <summary aria-label={group} className={active ? "pms-menu-current" : ""} onClick={event => { event.preventDefault(); setExpanded(current => ({ ...current, [group]: !open })); }}><span>{collapsed ? group.slice(0, 2) : group}</span><ChevronDown size={14} /></summary>
        <div>{children.map(i => <Link key={i.to} to={workspacePageHref(i.to, location.search, workspaceId)} title={i.label} onClick={onNavigate} aria-current={location.pathname === i.to || (!query && currentWorkspace?.to === i.to) ? "page" : undefined}><i.icon size={17} />{!collapsed && <span>{i.label}</span>}</Link>)}</div>
      </details>;
    })}
    {!items.some(i => `${i.group} ${i.label}`.toLowerCase().includes(query.toLowerCase())) && <p className="px-3 text-xs">No matching pages.</p>}
  </div>;
}
