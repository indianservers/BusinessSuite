import { Fragment } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Sparkles, UserCircle, X, LogOut } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { getRoleLabel, getRoleNav } from "@/lib/roles";
import { getProductForContext } from "@/lib/products";

interface SidebarProps {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
}

export default function Sidebar({ open, collapsed, onClose, onToggleCollapse }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const navItems = getRoleNav(user?.role, user?.is_superuser, location.pathname);
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const profilePath = location.pathname.startsWith("/hrms")
    ? "/hrms/profile"
    : location.pathname.startsWith("/crm")
      ? "/crm/profile"
      : location.pathname.startsWith("/pms")
        ? "/pms/profile"
        : "/";
  const handleLogout = () => {
    logout();
    navigate(product.loginPath, { replace: true });
  };

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
                <p className="text-[10px] text-sidebar-foreground/50">{roleLabel}</p>
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
        <nav className="flex-1 overflow-y-auto py-4">
          <ul className={cn("px-2", collapsed ? "space-y-0.5" : "space-y-1")}>
            {navItems.map((item, index) => {
              const showGroup = !collapsed && item.group && item.group !== navItems[index - 1]?.group;
              return (
                <Fragment key={item.to}>
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
        </nav>

        {/* User section */}
        <div className="border-t border-sidebar-border p-4">
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
