import RouteContent from "@/components/app/RouteContent";
import PageWorkTools from "@/components/app/PageWorkTools";
import { isSharedTaskWorkspace } from "@/lib/task-workspace";
import FormDefaultsGate from "@/components/forms/FormDefaultsGate";
import SetupReadiness from "@/components/suite/SetupReadiness";
import "@/components/visuals/suite-visuals.css";
import { useMobile } from "@/components/mobile/useMobile";
import { LoadingState } from "@/components/ui/state";
import SuiteContextBar from "@/components/suite/SuiteContextBar";
import PageContextMenu from "@/components/app/PageContextMenu";
import ActionBot from "@/components/ai-agents/ActionBot";
import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import MobileModuleDock from "./MobileModuleDock";
import Topbar from "./Topbar";
import BackToTop from "@/components/app/BackToTop";
import Breadcrumbs from "@/components/app/Breadcrumbs";
import ErrorBoundary from "@/components/app/ErrorBoundary";
import SessionTimeoutWarning from "@/components/app/SessionTimeoutWarning";
import WorkspaceEnhancements from "@/components/app/WorkspaceEnhancements";
import { useAuthStore } from "@/store/authStore";
import { getProductForContext } from "@/lib/products";
import "./mobile-workspaces.css";

export default function AppLayout() { return <><AppLayoutContent/><ActionBot/></>; }

function AppLayoutContent() {
  const location = useLocation();
  const mobileLead = useMobile() && /^\/crm\/leads\/\d+\/?$/.test(location.pathname);
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const isWorkspaceDirectory = /^\/(pms|crm|hrms|srm|fam)\/workspaces\/?$/.test(location.pathname);
  const isDealCollection = /^\/crm\/(deals|pipeline)\/?$/.test(location.pathname);
  const isPeopleDirectory = location.pathname === "/pms/people" || location.pathname === "/pms/directory" || /^\/pms\/people\/\d+$/.test(location.pathname);
  const isMessaging = /^\/(pms|crm|hrms|srm|fam)\/messages\/?$/.test(location.pathname) || /^\/crm\/whatsapp\/inbox\/?$/.test(location.pathname);
  const isPosTerminal = location.pathname === "/srm/pos" || location.pathname === "/srm/pos/terminal";
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebarCollapsed") === "true");

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  if (location.pathname === "/power-apps" || location.pathname.startsWith("/power-apps/")) {
    return <div className="flex h-dvh min-w-0 flex-col overflow-hidden"><SuiteContextBar /><div className="min-h-0 flex-1 overflow-auto"><ErrorBoundary resetKey={location.pathname+location.search}><Suspense fallback={<LoadingState />}><FormDefaultsGate><PageWorkTools /><Outlet /></FormDefaultsGate></Suspense></ErrorBoundary></div><SessionTimeoutWarning /></div>;
  }

  if (isSharedTaskWorkspace(location.pathname, location.search)) {
    return <div className="mobile-dock-fullscreen mobile-dock-tasks"><ErrorBoundary resetKey={location.pathname+location.search}><Suspense fallback={<LoadingState />}><FormDefaultsGate><PageWorkTools /><Outlet /></FormDefaultsGate></Suspense></ErrorBoundary><SessionTimeoutWarning /><MobileModuleDock /></div>;
  }

  if (["/pms", "/pms/"].includes(location.pathname) || (location.pathname === "/pms/workspaces" && (["workspace","task","invite"].some(key=>new URLSearchParams(location.search).has(key)) || new URLSearchParams(location.search).has("new") && new URLSearchParams(location.search).get("new") !== "workspace"))) {
    return <div className="mobile-dock-fullscreen flex h-dvh flex-col overflow-hidden" style={{"--pms-assistant-left":"274px"} as import("react").CSSProperties}><div className="pms-workspace-host min-h-0 flex-1 overflow-hidden"><PageContextMenu /><ErrorBoundary resetKey={location.pathname+location.search}><Suspense fallback={<LoadingState />}><FormDefaultsGate><Outlet /></FormDefaultsGate></Suspense></ErrorBoundary></div><SessionTimeoutWarning /><MobileModuleDock /></div>;
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
        {!mobileLead && <Topbar onMenuClick={() => setSidebarOpen(true)} />}
        <main id="suite-main" tabIndex={-1} className={`kf-main suite-page-surface min-w-0 flex-1 overflow-y-auto overflow-x-hidden animate-fade-in ${mobileLead || isPeopleDirectory || isWorkspaceDirectory ? "p-0" : isPosTerminal ? "bg-slate-950 p-0" : isMessaging ? "p-3" : isDealCollection ? "px-3 py-2 pb-24 lg:px-6" : "p-4 pb-24 md:p-5 md:pb-24 lg:p-6 lg:pb-24"}`}>
          {mobileLead || isPosTerminal || isMessaging || isPeopleDirectory || isWorkspaceDirectory || isDealCollection ? null : <Breadcrumbs />}
          {!mobileLead && !isMessaging && !isPeopleDirectory && <WorkspaceEnhancements terminal={isPosTerminal} />}
          <SetupReadiness embedded />
          <ErrorBoundary resetKey={location.pathname+location.search}>
            <RouteContent><Suspense fallback={<LoadingState />}><FormDefaultsGate><PageWorkTools /><Outlet /></FormDefaultsGate></Suspense></RouteContent>
          </ErrorBoundary>
        </main>
        {!mobileLead && <BackToTop />}
      </div>
      <SessionTimeoutWarning />

      {!mobileLead && <MobileModuleDock />}
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}
