import MessagingNavLink from "./MessagingNavLink";
import PMSMoreMenu from "./PMSMoreMenu";
import { useSignOut } from "@/hooks/use-sign-out";
import { Fragment, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Sparkles, UserCircle, X, LogOut, Search, MoreHorizontal } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { getRoleLabel, getRoleNav } from "@/lib/roles";
import { BUSINESS_SUITE_DISPLAY_NAME, getProductDisplayName, getProductForContext } from "@/lib/products";

interface SidebarProps {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
}

export default function Sidebar({ open, collapsed, onClose, onToggleCollapse }: SidebarProps) {
  const location = useLocation();
  const { user } = useAuthStore();
  const roleNav = getRoleNav(user?.role, user?.is_superuser, location.pathname);
  const primaryPaths: Record<string, string[]> = {
    hrms: ["/hrms", "/hrms/employees", "/hrms/attendance", "/hrms/leave", "/hrms/payroll", "/hrms/recruitment"],
    crm: ["/crm", "/crm/leads", "/crm/contacts", "/crm/deals", "/crm/pipeline", "/crm/tasks"],
    pms: ["/pms", "/pms/workspaces", "/pms/projects", "/pms/tasks", "/pms/calendar", "/pms/timesheets"],
    srm: ["/srm", "/srm/sales-orders", "/srm/invoices", "/srm/collections", "/srm/inventory", "/srm/pos"],
    fam: ["/fam", "/fam/vouchers", "/fam/ar", "/fam/ap", "/fam/bank-reconciliation", "/fam/ledgers"],
  };
  const priorities = primaryPaths[location.pathname.split("/")[1]] || [];
  const rank = (path: string) => priorities.includes(path) ? priorities.indexOf(path) : priorities.length;
  const allNavItems = [...roleNav].sort((a, b) => rank(a.to) - rank(b.to));
  const [showAll, setShowAll] = useState(false);
  const [query, setQuery] = useState("");
  const moduleKey = location.pathname.split("/")[1];
  useEffect(() => { setShowAll(false); setQuery(""); }, [moduleKey]);
  const matchingItems = allNavItems.filter(item => !query || `${item.label} ${item.group || ""}`.toLowerCase().includes(query.toLowerCase()));
  const navItems = showAll || query ? matchingItems : matchingItems.filter((item, index) => index < 6 || (item.to !== "/" && (location.pathname === item.to || (!item.exact && item.to.split("/").length > 2 && location.pathname.startsWith(`${item.to}/`)))));
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const profilePath = location.pathname.startsWith("/hrms")
    ? "/hrms/profile"
    : location.pathname.startsWith("/crm")
      ? "/crm/profile"
      : location.pathname.startsWith("/pms")
        ? "/pms/profile"
        : location.pathname.startsWith("/srm")
          ? "/srm/profile"
          : location.pathname.startsWith("/fam") ? "/fam/profile" : "/";
  const handleLogout = useSignOut(product.loginPath);

  return (
    <>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex flex-col transition-all duration-300",
          "bg-sidebar text-sidebar-foreground border-r border-sidebar-border",
          collapsed ? "w-16" : "w-64",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Header */}
        <div className={cn(
          "flex h-16 items-center border-b border-sidebar-border px-4",
          collapsed ? "justify-center" : "justify-between"
        )}>
          {!collapsed && (
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
                <Sparkles className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-bold text-sidebar-foreground">{product.name}</p>
                <p className="text-[10px] text-sidebar-foreground/50">{getProductDisplayName(product)} / {roleLabel}</p>
              </div>
            </div>
          )}
          {collapsed && (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
          )}
          <div className="flex items-center gap-1">
            {!collapsed && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent lg:flex hidden"
                onClick={onToggleCollapse}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent lg:hidden"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Collapse toggle when collapsed */}
        {collapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="mx-auto mt-2 h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent hidden lg:flex"
            onClick={onToggleCollapse}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}

        {/* Navigation */}
        <nav aria-label="Module navigation" className="flex-1 overflow-y-auto py-4">
          {!collapsed && <label className="mx-3 mb-3 flex items-center gap-2 rounded-md border border-sidebar-border px-2 py-2"><Search className="h-3.5 w-3.5 shrink-0 opacity-50" /><input aria-label="Find a page" placeholder="Find a page…" value={query} onChange={e => setQuery(e.target.value)} className="min-w-0 w-full bg-transparent text-xs outline-none" /></label>}
          <ul className={cn("px-2", collapsed ? "space-y-0.5" : "space-y-1")}>
            {navItems.map((item, index) => {
              const showGroup = !collapsed && (showAll || Boolean(query)) && item.group && item.group !== navItems[index - 1]?.group;
              return (
                <Fragment key={`${item.to}:${item.label}`}>
                  {showGroup && (
                    <li className={cn(index > 0 && "pt-3")}>
                      {index > 0 && <hr className="mb-3 border-sidebar-border" />}
                      <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wide text-sidebar-foreground/45">
                        {item.group}
                      </p>
                    </li>
                  )}
                  <li>
                    <NavLink
                      to={item.to}
                      end={item.exact}
                      className={({ isActive }) =>
                        cn(
                          "nav-link",
                          isActive ? "nav-link-active" : "nav-link-inactive",
                          collapsed && "justify-center px-2"
                        )
                      }
                      title={collapsed ? item.label : undefined}
                      onClick={onClose}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      {!collapsed && (
                        <span className="flex-1">{item.label}</span>
                      )}
                      {!collapsed && item.badge && (
                        <span className="rounded-full bg-sidebar-primary px-1.5 py-0.5 text-[10px] font-bold text-white">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  </li>
                </Fragment>
              );
            })}
          </ul>
          {!navItems.length && <p className="px-5 py-3 text-xs text-sidebar-foreground/60">No matching pages.</p>}
          {moduleKey === "pms" && <MessagingNavLink collapsed={collapsed} className="nav-link nav-link-inactive mx-2 mt-3 flex items-center gap-2 text-xs" />}
          {moduleKey === "pms" && <PMSMoreMenu collapsed={collapsed} className="nav-link nav-link-inactive mx-2 mt-3 flex items-center gap-2 text-xs" />}
          {moduleKey !== "pms" && allNavItems.length > 6 && !query && <button type="button" aria-label={showAll ? "Show fewer pages" : "Show all pages"} aria-expanded={showAll} onClick={() => setShowAll(value => !value)} className="nav-link nav-link-inactive mx-2 mt-3 flex items-center gap-2 text-xs"><MoreHorizontal className="h-4 w-4" />{!collapsed && (showAll ? "Show fewer" : `More pages (${allNavItems.length - navItems.length})`)}</button>}
        </nav>

        {/* User section */}
        <div className="border-t border-sidebar-border p-4">
          {!collapsed && (
            <div className="mb-3 rounded-md border border-sidebar-border/70 px-3 py-2 text-[10px] font-medium text-sidebar-foreground/55">
              {BUSINESS_SUITE_DISPLAY_NAME}
            </div>
          )}
          <NavLink
            to={profilePath}
            end
            className={({ isActive }) =>
              cn(
                "nav-link",
                isActive ? "nav-link-active" : "nav-link-inactive",
                collapsed && "justify-center px-2"
              )
            }
            onClick={onClose}
          >
            <UserCircle className="h-4 w-4 shrink-0" />
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{user?.email}</p>
                <p className="text-[10px] text-sidebar-foreground/50 capitalize">
                  {roleLabel}
                </p>
              </div>
            )}
          </NavLink>
          <button
            onClick={handleLogout}
            className={cn(
              "nav-link nav-link-inactive mt-1 w-full text-red-500 hover:bg-red-100 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-900/20 dark:hover:text-red-300",
              collapsed && "justify-center px-2"
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
