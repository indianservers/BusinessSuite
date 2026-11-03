import { useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CheckCircle2, BarChart3, BriefcaseBusiness, ChevronDown, ChevronsDownUp, ChevronsUpDown, CircleHelp, FolderKanban, LayoutDashboard, MessagesSquare, Search, Settings2, Sparkles, Star, Users, X } from "lucide-react";
import { canAccessRoute, getRoleNav, type RoleNavItem } from "@/lib/roles";
import { activeWorkspace, workspacePageHref } from "@/lib/navigation-workspaces";
import { menuItems, menuLabel, menuMatches, menuPages } from "@/lib/navigation-menu";
import { useAuthStore } from "@/store/authStore";
import { defaultSuitePreferences, suiteScope, useSuitePreferences } from "@/store/suitePreferences";
import PMSPersonalNavigation from "./PMSPersonalNavigation";
import HRPersonalNavigation from "./HRPersonalNavigation";
import CRMPersonalNavigation from "./CRMPersonalNavigation";
import "./module-navigation.css";

const categoryIcon = (name: string) => /overview|home|dashboard/i.test(name) ? LayoutDashboard
  : /people|team|customer|recruitment/i.test(name) ? Users
  : /planning|task|project|attendance|sales|transaction/i.test(name) ? FolderKanban
  : /report|analytic|finance|payroll|revenue/i.test(name) ? BarChart3
  : /setting|admin|security|compliance/i.test(name) ? Settings2
  : /AI|assistant|agent/i.test(name) ? Sparkles
  : /communication|collaboration|support|request/i.test(name) ? MessagesSquare : BriefcaseBusiness;

export default function ModuleNavigation({ collapsed = false, onNavigate, workspaceId, modulePath, customItems }: {
  collapsed?: boolean; onNavigate: () => void; workspaceId?: number; modulePath?: string; customItems?: RoleNavItem[];
}) {
  const location = useLocation(), id = useId();
  const user = useAuthStore(state => state.user);
  const moduleKey = (modulePath || location.pathname).split("/")[1] || "suite";
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const preferences = useSuitePreferences(state => state.contexts[scope] || defaultSuitePreferences);
  const update = useSuitePreferences(state => state.update);
  const [query, setQuery] = useState("");
  const [submenus, setSubmenus] = useState<Record<string, boolean>>({});
  // Custom catalogs are already filtered by their server-side application permissions.
  const available = customItems ? [...customItems] : getRoleNav(user?.role, user?.is_superuser, modulePath || location.pathname)
    .filter(item => canAccessRoute(item.to.split("?")[0], user?.role, user?.is_superuser));
  if (moduleKey === "pms" && !available.some(item => item.to === "/pms/my-work") && canAccessRoute("/pms/my-work", user?.role, user?.is_superuser)) {
    available.push({ to: "/pms/my-work", label: "My work", icon: CheckCircle2, group: "Tasks & projects" });
  }
  if (moduleKey === "hrms" && available.some(item => item.to === "/hrms/interns")) {
    for (const [path, label] of [["operations", "Profiles & work"], ["dashboard", "Intern dashboard"], ["applications", "Signups & approvals"], ["list", "All interns"], ["batches", "Intern batches"], ["tasks", "Intern task assignment"], ["reviews", "Daily reports & reviews"], ["performance", "Performance & completion"]]) {
      const to = `/hrms/interns/${path}`;
      if (!available.some(item => item.to === to) && canAccessRoute(to, user?.role, user?.is_superuser)) available.push({ to, label, icon: Users, group: available.find(item => item.to === "/hrms/interns")?.group });
    }
  }
  const consolidated = menuItems(available);
  const current = activeWorkspace(consolidated, location.pathname) || available.filter(item =>
    location.pathname === item.to.split("?")[0] || location.pathname.startsWith(item.to.split("?")[0] + "/"))
    .sort((a, b) => b.to.length - a.to.length)[0];
  const activeGroup = current?.group;
  const items = query.trim() ? available.filter(item => menuMatches(item, query)) : consolidated;
  const groups = [...new Set(items.map(item => item.group || "Workspace"))];
  const allGroups = [...new Set(consolidated.map(item => item.group || "Workspace"))];
  const key = (group: string) => `menu-v2:${moduleKey}:${group}`;
  const previous = useRef(location.pathname);
  useEffect(() => { setQuery(""); setSubmenus({}); }, [moduleKey]);
  useEffect(() => {
    if (previous.current === location.pathname) return;
    previous.current = location.pathname;
    if (activeGroup) {
      const stored = useSuitePreferences.getState().contexts[scope] || defaultSuitePreferences;
      update(scope, { groups: { ...stored.groups, [key(activeGroup)]: true } });
    }
  }, [location.pathname, activeGroup, moduleKey, scope, update]);
  const expandAll = (expanded: boolean) => update(scope, { groups: {
    ...preferences.groups, ...Object.fromEntries(allGroups.map(group => [key(group), expanded])),
  } });
  const isCurrent = (to: string) => {
    const [path, search] = to.split("?");
    return (location.pathname === path || (path.split("/").length > 2 && location.pathname.startsWith(path + "/")))
      && (!search || search === location.search.slice(1));
  };
  return <div className={`module-menu ${collapsed ? "is-collapsed" : ""}`} data-module={moduleKey}>
    {!collapsed && <>
      <label className="module-menu-search"><Search size={16} /><input aria-label="Find a page in this application" placeholder="Find a page…" value={query}
        onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === "Escape") setQuery(""); }} />
        {query && <button type="button" aria-label="Clear menu search" onClick={() => setQuery("")}><X size={14} /></button>}
      </label>
      <div className="module-menu-toolbar"><span>{query.trim() ? `${items.length} results` : "Explore workspace"}</span><div>
        <button type="button" aria-label="Expand all menu categories" title="Expand all categories" onClick={() => expandAll(true)}><ChevronsUpDown size={14} /></button>
        <button type="button" aria-label="Collapse all menu categories" title="Collapse all categories" onClick={() => expandAll(false)}><ChevronsDownUp size={14} /></button>
      </div></div>
    </>}
    <ul className="module-menu-categories">{groups.map((group, index) => {
      const children = items.filter(item => (item.group || "Workspace") === group);
      const expanded = collapsed || !!query.trim() || (preferences.groups[key(group)] ?? (activeGroup ? group === activeGroup : index === 0));
      const Icon = categoryIcon(group), panel = `${id}-category-${index}`;
      return <li className={`module-menu-category ${group === activeGroup ? "is-current" : ""}`} key={group}>
        {!collapsed && <button type="button" className="module-menu-heading" aria-expanded={expanded} aria-controls={panel}
          onClick={() => update(scope, { groups: { ...preferences.groups, [key(group)]: !expanded } })}>
          <span className="module-menu-category-icon"><Icon size={16} /></span><span className="module-menu-category-name">{group}</span>
          <span className="module-menu-count">{children.length}</span><ChevronDown className="module-menu-chevron" size={14} />
        </button>}
        {expanded && <ul id={panel} className="module-menu-links">{children.map(item => {
          const pages = menuPages(item), label = menuLabel(item), selected = isCurrent(item.to) || (!query.trim() && current?.to === item.to);
          const submenuId = `${panel}-${encodeURIComponent(item.to)}`;
          const submenuOpen = submenus[item.to] ?? (selected || pages.some(page => isCurrent(page.to)));
          return <li key={item.to + item.label}>
            <div className={`module-menu-row ${selected ? "is-active" : ""}`}>
              <Link to={workspacePageHref(item.to, location.search, workspaceId)} onClick={() => {
                if (pages.length > 1) setSubmenus(previous => ({ ...previous, [item.to]: true }));
                onNavigate();
              }} title={label} aria-label={label} aria-current={selected ? "page" : undefined}>
                <item.icon size={17} />{!collapsed && <span>{label}</span>}
              </Link>
              {!collapsed && !query.trim() && pages.length > 1 && <button type="button" className="module-menu-subtoggle" aria-label={`${submenuOpen ? "Collapse" : "Expand"} ${label} pages`} aria-expanded={submenuOpen} aria-controls={submenuId}
                onClick={() => setSubmenus(previous => ({ ...previous, [item.to]: !submenuOpen }))}><ChevronDown size={13} /></button>}
            </div>
            {!collapsed && !query.trim() && pages.length > 1 && submenuOpen && <ul id={submenuId} className="module-menu-pages">{pages.filter(page => page.to !== item.to).map(page =>
              <li key={page.to}><Link to={workspacePageHref(page.to, location.search, workspaceId)} onClick={onNavigate} aria-current={isCurrent(page.to) ? "page" : undefined}>{menuLabel(page)}</Link></li>)}</ul>}
          </li>;
        })}</ul>}
      </li>;
    })}</ul>
    {!items.length && <div className="module-menu-empty"><CircleHelp size={22} /><strong>No pages found</strong><p>Try a page name or category.</p><button type="button" onClick={() => setQuery("")}>Clear search</button></div>}
    {!collapsed && !query.trim() && ["pms", "crm", "hrms"].includes(moduleKey) && <details className="module-menu-shortcuts">
      <summary><Star size={15} /><span>Your shortcuts</span><ChevronDown size={14} /></summary><div>
        {moduleKey === "pms" && <PMSPersonalNavigation onNavigate={onNavigate} />}
        {moduleKey === "crm" && <CRMPersonalNavigation onNavigate={onNavigate} />}
        {moduleKey === "hrms" && <HRPersonalNavigation onNavigate={onNavigate} />}
      </div>
    </details>}
  </div>;
}
