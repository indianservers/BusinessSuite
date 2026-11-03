import { Settings as SettingsIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  LogOut,
  Sparkles,
  UserCircle,
  X,
} from "lucide-react";
import { useCompanyBranding } from "@/features/access/useCompanyBranding";
import ModuleSwitcher from "./ModuleSwitcher";
import ModuleNavigation from "./ModuleNavigation";
import { useSignOut } from "@/hooks/use-sign-out";
import { assetUrl, cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { getRoleLabel } from "@/lib/roles";
import { getProductDisplayName, getProductForContext } from "@/lib/products";
import "@/components/suite/suite.css";

type Props = {
  embedded?: boolean;
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
};
export default function Sidebar({
  open,
  embedded = false,
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
  const aside = useRef<HTMLElement>(null);
  const signOut = useSignOut("/login");
  const close = useRef(onClose);
  close.current = onClose;
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
        "suite-sidebar z-50 flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:z-30",
        embedded ? "suite-sidebar-embedded" : "fixed inset-y-0 left-0",
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
          className="mx-3 mt-2 rounded-lg border border-sidebar-border px-3 py-2 text-xs"
        >
          Users & access
        </Link>
      )}
      <nav
        aria-label="Module navigation"
        className="min-h-0 flex-1 overflow-y-auto py-3"
      >
        <ModuleNavigation collapsed={collapsed} onNavigate={onClose} />
      <Link to="/settings" className={cn("nav-link nav-link-inactive mx-2 mt-3 flex items-center gap-2", collapsed && "justify-center")} title="Suite settings" onClick={onClose}><SettingsIcon className="h-4 w-4" />{!collapsed && "Suite settings"}</Link>
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
        <div className={cn(!collapsed && "flex items-center")}><Link
          to="/help"
          className={cn(
            "nav-link min-h-9 flex-1 text-xs",
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
            "nav-link min-h-9 flex-1 text-xs text-red-400",
            collapsed && "justify-center",
          )}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut size={17} />
          {!collapsed && "Sign out"}
        </button></div>
      </div>
    </aside>
  );
}
