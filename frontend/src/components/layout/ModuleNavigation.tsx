import MenuItemMore, { MenuItemIcon } from "./MenuItemMore";
import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import MenuQuickAdd from "./MenuQuickAdd";
import type { NewAction } from "@/components/app/NewMenu";
import { useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CheckCircle2, BarChart3, BriefcaseBusiness, ChevronDown, ChevronsDownUp, ChevronsUpDown, CircleHelp, FolderKanban, LayoutDashboard, MessagesSquare, Search, Settings2, Sparkles, Star, Users, X } from "lucide-react";
import { canAccessRoute, getRoleNav, type RoleNavItem } from "@/lib/roles";
import { activeWorkspace, workspacePageHref } from "@/lib/navigation-workspaces";
import { menuItems, menuLabel, menuMatches, menuPages, moduleLandingNavigation } from "@/lib/navigation-menu";
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

export default function ModuleNavigation({ collapsed = false, onNavigate, workspaceId, modulePath, customItems, quickActions = [] }: {
  collapsed?: boolean; onNavigate: () => void; workspaceId?: number; modulePath?: string; customItems?: RoleNavItem[]; quickActions?: NewAction[];
}) {
  const location = useLocation(), id = useId();
  const user = useAuthStore(state => state.user);
  const moduleKey = (modulePath || location.pathname).split("/")[1] || "suite";
  const catalogPath = ["crm", "hrms", "pms", "srm", "fam"].includes(moduleKey) ? `/${moduleKey}` : modulePath || location.pathname;
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const preferences = useSuitePreferences(state => state.contexts[scope] || defaultSuitePreferences);
  const update = useSuitePreferences(state => state.update);
  const [query, setQuery] = useState("");
  const [submenus, setSubmenus] = useState<Record<string, boolean>>({});
  // Custom catalogs are already filtered by their server-side application permissions.
  const available = customItems ? [...customItems] : getRoleNav(user?.role, user?.is_superuser, catalogPath)
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
  const supplemental = location.pathname.startsWith("/admin/customization")
    ? [["/admin/customization/fields", "Fields"], ["/admin/customization/modules", "Modules"], ["/admin/customization/layouts", "Layouts"], ["/admin/customization/views", "Saved views"], ["/admin/customization/kanban", "Kanban boards"], ["/admin/customization/validation-rules", "Validation rules"], ["/admin/customization/buttons", "Record actions"], ["/admin/customization/related-lists", "Related lists"], ["/admin/customization/picklists", "Picklists"]]
    : moduleKey === "analytics" ? [["/analytics/reports", "Reports"], ["/analytics/report-builder", "Report builder"], ["/analytics/scheduled-reports", "Report schedules"]] : [];
  for (const [to, label] of supplemental) {
    if (!customItems && !available.some(item => item.to === to) && canAccessRoute(to, user?.role, user?.is_superuser)) available.push({to, label, icon: Settings2, group:moduleKey === "analytics" ? "Reports & insights" : "Customization Studio"});
  }
  const landing = moduleLandingNavigation(available, moduleKey);
  const consolidated = [...landing.direct, ...menuItems(landing.grouped)];
  const current = activeWorkspace(consolidated, location.pathname) || available.filter(item =>
    location.pathname === item.to.split("?")[0] || location.pathname.startsWith(item.to.split("?")[0] + "/"))
    .sort((a, b) => b.to.length - a.to.length)[0];
  const activeGroup = current?.group;
  const displayLabel = (item: {to:string;label:string}) => preferences.menuItems?.[item.to.split(/[?#]/)[0]]?.label || menuLabel(item);
  const items = query.trim() ? available.filter(item => menuMatches(item, query) || displayLabel(item).toLowerCase().includes(query.trim().toLowerCase())) : consolidated;
  const directItems = items.filter(item => landing.direct.some(link => link.to === item.to));
  const groupedItems = items.filter(item => !landing.direct.some(link => link.to === item.to)
    && !([`/${moduleKey}`, `/${moduleKey}/dashboard`].includes(item.to)));
  const groups = [...new Set(groupedItems.map(item => item.group || "Workspace"))];
  const allGroups = [...new Set(landing.grouped.map(item => item.group || "Workspace"))];
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
  return <ModuleNewMenu>{moduleActions => { const createActions = [...moduleActions, ...quickActions]; return <div className={`module-menu ${collapsed ? "is-collapsed" : ""}`} data-module={moduleKey}>
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
    {directItems.length > 0 && <ul className="module-menu-landing" aria-label="Application landing pages">{directItems.map(item => {
      const itemPath = item.to.split(/[?#]/)[0].replace(/\/$/, "");
      const primary = itemPath === `/${moduleKey}` || itemPath === `/${moduleKey}/dashboard`;
      const selected = primary ? location.pathname === `/${moduleKey}` || location.pathname === `/${moduleKey}/dashboard` : isCurrent(item.to);
      const label = displayLabel(item);
      return <li key={item.to}><div className={`module-menu-row ${selected ? "is-active" : ""}`}>
        <Link to={workspacePageHref(item.to, location.search, workspaceId)} onClick={onNavigate} title={label} aria-label={label} aria-current={selected ? "page" : undefined}>
          <MenuItemIcon path={item.to} fallback={item.icon}/>{!collapsed && <span>{label}</span>}
        </Link>
        {!collapsed && <MenuQuickAdd actions={createActions} paths={menuPages(item).map(page=>page.to)} label={label} onNavigate={onNavigate}/>}
        {!collapsed && <MenuItemMore path={workspacePageHref(item.to, location.search, workspaceId)} label={label} originalLabel={menuLabel(item)} actions={createActions} available={available} onNavigate={onNavigate}/>}
      </div></li>;
    })}</ul>}
    {!collapsed && !query.trim() && preferences.favorites.some(path=>available.some(item=>item.to.split(/[?#]/)[0]===path.split(/[?#]/)[0])) && <ul className="module-menu-favorites" aria-label="Favorite menu pages"><li><p>Favorites</p></li>{preferences.favorites.flatMap(path=>{
      const item=available.find(item=>item.to.split(/[?#]/)[0]===path.split(/[?#]/)[0]);
      if(!item)return []; const label=displayLabel(item);
      return [<li key={path}><div className="module-menu-row"><Link to={path} onClick={onNavigate} title={label}><Star size={15}/><span>{label}</span></Link><MenuQuickAdd actions={createActions} paths={[path]} label={label} onNavigate={onNavigate}/><MenuItemMore path={path} label={label} originalLabel={menuLabel(item)} actions={createActions} available={available} onNavigate={onNavigate}/></div></li>];
    })}</ul>}
    <ul className="module-menu-categories">{groups.map((group, index) => {
      const children = groupedItems.filter(item => (item.group || "Workspace") === group);
      const expanded = collapsed || !!query.trim() || (preferences.groups[key(group)] ?? (activeGroup ? group === activeGroup : index === 0));
      const Icon = categoryIcon(group), panel = `${id}-category-${index}`;
      return <li className={`module-menu-category ${group === activeGroup ? "is-current" : ""}`} key={group}>
        {!collapsed && <button type="button" className="module-menu-heading" aria-expanded={expanded} aria-controls={panel}
          onClick={() => update(scope, { groups: { ...preferences.groups, [key(group)]: !expanded } })}>
          <span className="module-menu-category-icon"><Icon size={16} /></span><span className="module-menu-category-name">{group}</span>
          <span className="module-menu-count">{children.length}</span><ChevronDown className="module-menu-chevron" size={14} />
        </button>}
        {expanded && <ul id={panel} className="module-menu-links">{children.map(item => {
          const pages = menuPages(item), label = displayLabel(item), selected = isCurrent(item.to) || (!query.trim() && current?.to === item.to);
          const submenuId = `${panel}-${encodeURIComponent(item.to)}`;
          const submenuOpen = submenus[item.to] ?? (selected || pages.some(page => isCurrent(page.to)));
          return <li key={item.to + item.label}>
            <div className={`module-menu-row ${selected ? "is-active" : ""}`}>
              <Link to={workspacePageHref(item.to, location.search, workspaceId)} onClick={() => {
                if (pages.length > 1) setSubmenus(previous => ({ ...previous, [item.to]: true }));
                onNavigate();
              }} title={label} aria-label={label} aria-current={selected ? "page" : undefined}>
                <MenuItemIcon path={item.to} fallback={item.icon}/>{!collapsed && <span>{label}</span>}
              </Link>
              {!collapsed && <MenuQuickAdd actions={createActions} paths={pages.map(page => page.to)} label={label} onNavigate={onNavigate} />}
              {!collapsed && <MenuItemMore path={workspacePageHref(item.to, location.search, workspaceId)} paths={pages.map(page=>page.to)} label={label} originalLabel={menuLabel(item)} actions={createActions} available={available.map(page=>({...page,to:workspacePageHref(page.to,location.search,workspaceId)}))} onNavigate={onNavigate}/>}
              {!collapsed && !query.trim() && pages.length > 1 && <button type="button" className="module-menu-subtoggle" aria-label={`${submenuOpen ? "Collapse" : "Expand"} ${label} pages`} aria-expanded={submenuOpen} aria-controls={submenuId}
                onClick={() => setSubmenus(previous => ({ ...previous, [item.to]: !submenuOpen }))}><ChevronDown size={13} /></button>}
            </div>
            {!collapsed && !query.trim() && pages.length > 1 && submenuOpen && <ul id={submenuId} className="module-menu-pages">{pages.filter(page => page.to !== item.to).map(page =>
              <li key={page.to} className="module-menu-page-row"><Link to={workspacePageHref(page.to, location.search, workspaceId)} onClick={onNavigate} aria-current={isCurrent(page.to) ? "page" : undefined}>{displayLabel(page)}</Link><MenuQuickAdd actions={createActions} paths={[page.to]} label={displayLabel(page)} onNavigate={onNavigate} /><MenuItemMore path={workspacePageHref(page.to,location.search,workspaceId)} label={displayLabel(page)} originalLabel={menuLabel(page)} actions={createActions} available={available} onNavigate={onNavigate}/></li>)}</ul>}
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
  </div>; }}</ModuleNewMenu>;
}
