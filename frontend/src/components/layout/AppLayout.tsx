import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import BackToTop from "@/components/app/BackToTop";
import Breadcrumbs from "@/components/app/Breadcrumbs";
import ErrorBoundary from "@/components/app/ErrorBoundary";
import SessionTimeoutWarning from "@/components/app/SessionTimeoutWarning";
import { useAuthStore } from "@/store/authStore";
import { getProductForContext } from "@/lib/products";

export default function AppLayout() {
  const location = useLocation();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebarCollapsed") === "true");

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  return (
    <div className={`product-shell ${product.themeClass} flex h-screen overflow-hidden bg-background`} data-product={product.key}>
      {/* Sidebar */}
      <Sidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      {/* Main content */}
      <div
        className={`flex flex-1 flex-col overflow-hidden transition-all duration-300 ${
          sidebarCollapsed ? "lg:ml-16" : "lg:ml-64"
        }`}
      >
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-5 lg:p-8 animate-fade-in">
          <Breadcrumbs />
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <BackToTop />
      </div>
      <SessionTimeoutWarning />

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
