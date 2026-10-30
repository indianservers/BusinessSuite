import SuiteContextBar from "@/components/suite/SuiteContextBar";
import PageContextMenu from "@/components/app/PageContextMenu";
import PMSAssistant from "@/apps/project-management/components/PMSAssistant";
import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import BackToTop from "@/components/app/BackToTop";
import Breadcrumbs from "@/components/app/Breadcrumbs";
import ErrorBoundary from "@/components/app/ErrorBoundary";
import SessionTimeoutWarning from "@/components/app/SessionTimeoutWarning";
import WorkspaceEnhancements from "@/components/app/WorkspaceEnhancements";
import { useAuthStore } from "@/store/authStore";
import { getProductForContext } from "@/lib/products";

export default function AppLayout() {
  const location = useLocation();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const isMessaging = /^\/(pms|crm|hrms|srm|fam)\/messages\/?$/.test(location.pathname);
  const isPosTerminal = location.pathname === "/srm/pos" || location.pathname === "/srm/pos/terminal";
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebarCollapsed") === "true");

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  if (location.pathname === "/power-apps" || location.pathname.startsWith("/power-apps/")) {
    return <div className="flex h-dvh min-w-0 flex-col overflow-hidden"><SuiteContextBar /><div className="min-h-0 flex-1 overflow-auto"><ErrorBoundary><Outlet /></ErrorBoundary></div><SessionTimeoutWarning /></div>;
  }

  if (location.pathname === "/pms/tasks" || location.pathname === "/pms/tasks/new" || /^\/pms\/tasks\/\d+$/.test(location.pathname)) {
    return <><ErrorBoundary><Outlet /></ErrorBoundary><SessionTimeoutWarning /></>;
  }

  if (["/pms", "/pms/", "/pms/workspaces"].includes(location.pathname)) {
    return <div className="flex h-dvh flex-col overflow-hidden" style={{"--pms-assistant-left":"274px"} as import("react").CSSProperties}><SuiteContextBar /><div className="min-h-0 flex-1 overflow-hidden"><PageContextMenu /><ErrorBoundary><Outlet /></ErrorBoundary></div><SessionTimeoutWarning /><PMSAssistant /></div>;
  }

  return (
    <div className={`product-shell ${product.themeClass} flex h-screen overflow-hidden bg-background`} data-product={product.key} style={{"--pms-assistant-left":sidebarCollapsed ? "80px" : "272px"} as import("react").CSSProperties}>

      <a className="suite-skip" href="#suite-main">Skip to content</a>
      <PageContextMenu />
      {/* Sidebar */}
      <Sidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed && !sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      {/* Main content */}
      <div
        className={`flex min-w-0 flex-1 flex-col overflow-hidden transition-all duration-300 ${
          sidebarCollapsed ? "lg:ml-16" : "lg:ml-64"
        }`}
      >
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main id="suite-main" tabIndex={-1} className={`kf-main min-w-0 flex-1 overflow-y-auto overflow-x-hidden animate-fade-in ${isPosTerminal ? "bg-slate-950 p-0" : isMessaging ? "p-3" : "p-4 pb-24 md:p-5 md:pb-24 lg:p-6 lg:pb-24"}`}>
          {isPosTerminal || isMessaging ? null : <Breadcrumbs />}
          {!isMessaging && <WorkspaceEnhancements terminal={isPosTerminal} />}
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <BackToTop />
      </div>
      <SessionTimeoutWarning />
      <PMSAssistant />

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}
