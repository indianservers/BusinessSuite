import { Settings as SettingsIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  LogOut,
  Search,
  Sparkles,
  UserCircle,
  X,
} from "lucide-react";
import { useCompanyBranding } from "@/features/access/useCompanyBranding";
import ModuleSwitcher from "./ModuleSwitcher";
import PMSPersonalNavigation from "./PMSPersonalNavigation";
import { useSignOut } from "@/hooks/use-sign-out";
import { assetUrl, cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleLabel, getRoleNav } from "@/lib/roles";
import { getProductDisplayName, getProductForContext } from "@/lib/products";
import {
  defaultSuitePreferences,
  suiteScope,
  useSuitePreferences,
} from "@/store/suitePreferences";
import "@/components/suite/suite.css";

type Props = {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
};
export default function Sidebar({
  open,
  collapsed,
  onClose,
  onToggleCollapse,
}: Props) {
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const companyBrand = useCompanyBranding(location.pathname);
  const product = getProductForContext(
    location.pathname,
    user?.role,
    user?.is_superuser,
  );
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const preferences = useSuitePreferences(
    (s) => s.contexts[scope] || defaultSuitePreferences,
  );
  const update = useSuitePreferences((s) => s.update);
  const [query, setQuery] = useState("");
  const aside = useRef<HTMLElement>(null);
  const signOut = useSignOut("/login");
  const moduleKey = location.pathname.split("/")[1];
  const allItems = getRoleNav(
    user?.role,
    user?.is_superuser,
    location.pathname,
  ).filter((item) =>
    canAccessRoute(item.to.split("?")[0], user?.role, user?.is_superuser),
  );
  const items = allItems.filter(
    (item) =>
      !query.trim() ||
      `${item.label} ${item.group || ""}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const groups = Array.from(
    new Set(items.map((item) => item.group || "Workspace")),
  );
  const active = allItems
    .filter(
      (item) =>
        location.pathname === item.to.split("?")[0] ||
        location.pathname.startsWith(item.to.split("?")[0] + "/"),
    )
    .sort((a, b) => b.to.length - a.to.length)[0];
  const activeGroup = active?.group || "Workspace";
  const previousPath = useRef(location.pathname);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    setQuery("");
  }, [moduleKey]);
  useEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    const current =
      useSuitePreferences.getState().contexts[scope] || defaultSuitePreferences;
    const key = `${moduleKey}:${activeGroup}`;
    if (current.groups[key] === false)
      update(scope, { groups: { ...current.groups, [key]: true } });
  }, [location.pathname, moduleKey, activeGroup, scope, update]);
  useEffect(() => {
    if (!open || !aside.current) return;
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        aside.current!.querySelectorAll<HTMLElement>(
          "a[href],button:not([disabled]),input,select",
        ),
      ).filter((el) => el.getClientRects().length > 0);
    focusable()[0]?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key === "Tab") {
        const elements = focusable();
        const first = elements[0],
          last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [open]);
  return (
    <aside
      ref={aside}
      aria-label="Application navigation"
      role={open ? "dialog" : undefined}
      aria-modal={open ? true : undefined}
      className={cn(
        "suite-sidebar fixed inset-y-0 left-0 z-30 flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground",
        collapsed ? "w-16" : "w-64",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        !open && "invisible lg:visible",
      )}
    >
      <div
        className={cn(
          "flex h-16 shrink-0 items-center gap-2 border-b border-sidebar-border px-3",
          collapsed ? "justify-center" : "justify-between",
        )}
      >
        <Link
          to="/dashboard"
          onClick={onClose}
          className="flex min-w-0 items-center gap-2"
          aria-label="Business Suite home"
        >
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-sidebar-primary">
            {companyBrand.logo ? (
              <img
                src={assetUrl(companyBrand.logo)}
                alt=""
                className="h-8 w-8 rounded-lg bg-white object-contain"
              />
            ) : (
              <Sparkles size={17} className="text-white" />
            )}
          </span>
          {!collapsed && (
            <span className="min-w-0">
              <strong className="block truncate text-sm">
                {user?.access?.companyName || companyBrand.name || product.name}
              </strong>
              <small className="block truncate text-[10px] opacity-70">
                {getProductDisplayName(product)} · {roleLabel}
              </small>
            </span>
          )}
        </Link>
        {!collapsed && (
          <>
            <button
              className="hidden h-11 w-8 shrink-0 items-center justify-center lg:flex"
              aria-label="Collapse navigation"
              onClick={onToggleCollapse}
            >
              <ChevronLeft size={18} />
            </button>
            <button
              className="grid h-11 w-8 shrink-0 place-items-center lg:hidden"
              aria-label="Close navigation"
              onClick={onClose}
            >
              <X size={19} />
            </button>
          </>
        )}
      </div>
      {collapsed && (
        <button
          className="mx-auto mt-1 grid h-11 w-11 place-items-center"
          aria-label="Expand navigation"
          onClick={onToggleCollapse}
        >
          <ChevronRight size={18} />
        </button>
      )}
      <Link
        to="/dashboard"
        className="suite-shell-home"
        onClick={onClose}
        aria-label="All applications"
        title="All applications"
      >
        <LayoutGrid size={18} />
        {!collapsed && "All applications"}
      </Link>
      {!collapsed && (
        <div className="px-3">
          <ModuleSwitcher />
        </div>
      )}
      {!collapsed && (user?.is_superuser || user?.access?.isAccessAdmin) && (
        <Link
          to="/admin/access"
          onClick={onClose}
          className="mx-3 mt-2 rounded-lg border border-sidebar-border px-3 py-3 text-xs"
        >
          Users & access
        </Link>
      )}
      <nav
        aria-label="Module navigation"
        className="min-h-0 flex-1 overflow-y-auto py-3"
      >
        {!collapsed && (
          <label className="mx-3 mb-3 flex min-h-11 items-center gap-2 rounded-md border border-sidebar-border px-2">
            <Search size={15} className="shrink-0 opacity-70" />
            <input
              aria-label="Find a page in this application"
              placeholder="Find a page…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setQuery("");
              }}
              className="min-w-0 w-full bg-transparent py-3 text-xs outline-none"
            />
          </label>
        )}
        {moduleKey === "pms" && !query && <div className="px-2"><PMSPersonalNavigation collapsed={collapsed} onNavigate={onClose} /></div>}
        <ul className="px-2">
          {groups.map((group, groupIndex) => {
            const key = `${moduleKey}:${group}`;
            const expanded =
              !!query ||
              collapsed ||
              (preferences.groups[key] ??
                (group === activeGroup || groupIndex === 0));
            return (
              <li key={group}>
                {!collapsed && (
                  <button
                    className="suite-nav-group"
                    aria-expanded={expanded}
                    aria-controls={`nav-group-${groupIndex}`}
                    onClick={() =>
                      update(scope, {
                        groups: { ...preferences.groups, [key]: !expanded },
                      })
                    }
                  >
                    <span>{group}</span>
                    <ChevronDown size={14} />
                  </button>
                )}
                {expanded && (
                  <ul
                    id={`nav-group-${groupIndex}`}
                    className="suite-nav-sublist"
                  >
                    {items
                      .filter((item) => (item.group || "Workspace") === group)
                      .map((item) => (
                        <li key={item.to + item.label}>
                          <NavLink
                            to={item.to}
                            end={item.exact || item.to.split("/").length === 2}
                            title={collapsed ? item.label : undefined}
                            aria-label={item.label}
                            onClick={onClose}
                            className={({ isActive }) =>
                              cn(
                                "nav-link min-h-11",
                                isActive &&
                                  (!item.to.includes("?") ||
                                    location.search ===
                                      "?" + item.to.split("?")[1])
                                  ? "nav-link-active"
                                  : "nav-link-inactive",
                                collapsed && "justify-center px-2",
                              )
                            }
                          >
                            <item.icon size={17} className="shrink-0" />
                            {!collapsed && <span>{item.label}</span>}
                          </NavLink>
                          {item.to === "/hrms/interns" && !collapsed && (
                            <details className="ml-5">
                              <summary className="cursor-pointer py-3 text-xs">
                                Intern management pages
                              </summary>
                              <ul>
                                {[
                                  ["operations", "Profiles & work"],
                                  ["dashboard", "Dashboard"],
                                  ["applications", "Signups & approvals"],
                                  ["list", "All interns"],
                                  ["batches", "Batches"],
                                  ["tasks", "Task assignment"],
                                  ["reviews", "Daily reports & reviews"],
                                  ["performance", "Performance & completion"],
                                ].map(([path, label]) => (
                                  <li key={path}>
                                    <NavLink
                                      to={`/hrms/interns/${path}`}
                                      onClick={onClose}
                                      className="nav-link min-h-11 text-xs"
                                    >
                                      {label}
                                    </NavLink>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </li>
                      ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
        {!items.length && (
          <p className="px-4 py-3 text-xs opacity-70" role="status">
            No matching pages. Try another name.
          </p>
        )}
      <Link to="/settings" className={cn("nav-link nav-link-inactive mx-2 mt-3 flex items-center gap-2", collapsed && "justify-center")} title="Settings" onClick={onClose}><SettingsIcon className="h-4 w-4" />{!collapsed && "Settings"}</Link>
      </nav>
      <div className="shrink-0 border-t border-sidebar-border p-2">
        <Link
          to="/account"
          className={cn("nav-link min-h-11", collapsed && "justify-center")}
          aria-label="My account"
          title="My account"
          onClick={onClose}
        >
          <UserCircle size={18} />
          {!collapsed && (
            <span className="truncate text-xs">{user?.email}</span>
          )}
        </Link>
        <Link
          to="/help"
          className={cn(
            "nav-link min-h-11 text-xs",
            collapsed && "justify-center",
          )}
          onClick={onClose}
          aria-label="Help and support"
        >
          {collapsed ? "?" : "Help & support"}
        </Link>
        <button
          onClick={() => void signOut()}
          className={cn(
            "nav-link min-h-11 w-full text-red-400",
            collapsed && "justify-center",
          )}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut size={17} />
          {!collapsed && "Sign out"}
        </button>
      </div>
    </aside>
  );
}
