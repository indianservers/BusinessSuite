import React, { Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { Toaster } from "@/components/ui/toaster";
import { useAuthStore } from "@/store/authStore";
import AppLayout from "@/components/layout/AppLayout";
import { canAccessRoute } from "@/lib/roles";
import { getInstalledAppKeys, setBusinessOsEnabledModules, type FrontendRoute } from "@/appRegistry";
import { api } from "@/services/api";
import { BUSINESS_SUITE_DISPLAY_NAME, getLoginPathForContext } from "@/lib/products";
import { hrmsRoutes } from "@/apps/hrms/routes";
import { crmRoutes } from "@/apps/crm/routes";
import { projectManagementRoutes } from "@/apps/project-management/routes";
import { srmRoutes } from "@/apps/srm/routes";
import { famRoutes } from "@/apps/fam/routes";
import { inventoryRoutes } from "@/apps/inventory/routes";
import InventoryBridgePage from "@/apps/inventory/InventoryBridgePage";
import { aiAgentRoutes } from "@/pages/ai-agents/routes";
import { aiCopilotRoutes } from "@/apps/ai-copilot/routes";
import { adminSecurityRoutes } from "@/apps/admin-security/routes";
import { PortalPage, saasRoutes } from "@/apps/saas/routes";
import PMSRealtimeBridge from "@/apps/project-management/PMSRealtimeBridge";

const LoginPage = React.lazy(() => import("@/pages/auth/LoginPage"));
const ModuleIndexPage = React.lazy(() => import("@/pages/ModuleIndexPage"));
const AccessDeniedPage = React.lazy(() => import("@/pages/AccessDeniedPage"));
const AutomationStudioPage = React.lazy(() => import("@/apps/automation/AutomationStudioPage"));
const CustomizationStudioPage = React.lazy(() => import("@/apps/customization/CustomizationStudioPage"));
const AnalyticsPage = React.lazy(() => import("@/apps/analytics/AnalyticsPage"));
const BusinessOSAdminPage = React.lazy(() => import("@/apps/business-os/BusinessOSAdminPage"));
const BusinessOSWorkspacePage = React.lazy(() => import("@/apps/business-os/BusinessOSWorkspacePage"));

const appRoutes: Record<string, FrontendRoute[]> = {
  hrms: hrmsRoutes,
  crm: crmRoutes,
  project_management: projectManagementRoutes,
  srm: srmRoutes,
  fam: famRoutes,
  inventory: inventoryRoutes,
};

function getEnabledRoutes() {
  return getInstalledAppKeys().flatMap((key) => appRoutes[key] || []);
}

function LoadingFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 dark:bg-background">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Sparkles className="h-7 w-7" />
        </div>
        <div>
          <p className="text-lg font-semibold">{BUSINESS_SUITE_DISPLAY_NAME}</p>
          <p className="text-sm text-muted-foreground">Loading your workspace...</p>
        </div>
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { isAuthenticated, isHydrated, user } = useAuthStore();
  if (!isHydrated) return <LoadingFallback />;
  if (!isAuthenticated) return <Navigate to={getLoginPathForContext(location.pathname, user?.role, user?.is_superuser)} replace />;
  if (!user) return <LoadingFallback />;
  if (!canAccessRoute(location.pathname, user?.role, user?.is_superuser)) {
    return <AccessDeniedPage />;
  }
  return <>{children}</>;
}

export default function App() {
  const { isAuthenticated, isHydrated } = useAuthStore();
  const [moduleVersion, setModuleVersion] = useState(0);
  useEffect(() => {
    const onChange = () => setModuleVersion((value) => value + 1);
    window.addEventListener("business-os-modules-changed", onChange as EventListener);
    return () => window.removeEventListener("business-os-modules-changed", onChange as EventListener);
  }, []);
  useEffect(() => {
    if (!isHydrated || !isAuthenticated) return;
    api.get("/business-os/modules").then((response) => {
      setBusinessOsEnabledModules(response.data.enabled_modules || []);
    }).catch(() => undefined);
  }, [isHydrated, isAuthenticated]);
  const enabledRoutes = getEnabledRoutes();
  const commonRoutes: FrontendRoute[] = [
    { path: "admin/automation", element: <AutomationStudioPage /> },
    { path: "admin/automation/workflows", element: <AutomationStudioPage /> },
    { path: "admin/automation/workflows/:id", element: <AutomationStudioPage /> },
    { path: "admin/automation/blueprints", element: <AutomationStudioPage /> },
    { path: "admin/automation/approvals", element: <AutomationStudioPage /> },
    { path: "admin/automation/assignment-rules", element: <AutomationStudioPage /> },
    { path: "admin/automation/cadences", element: <AutomationStudioPage /> },
    { path: "admin/automation/webhooks", element: <AutomationStudioPage /> },
    { path: "admin/automation/logs", element: <AutomationStudioPage /> },
    { path: "admin/customization", element: <CustomizationStudioPage /> },
    { path: "admin/customization/modules", element: <CustomizationStudioPage /> },
    { path: "admin/customization/modules/:id", element: <CustomizationStudioPage /> },
    { path: "admin/customization/fields", element: <CustomizationStudioPage /> },
    { path: "admin/customization/layouts", element: <CustomizationStudioPage /> },
    { path: "admin/customization/views", element: <CustomizationStudioPage /> },
    { path: "admin/customization/kanban", element: <CustomizationStudioPage /> },
    { path: "admin/customization/validation-rules", element: <CustomizationStudioPage /> },
    { path: "admin/customization/buttons", element: <CustomizationStudioPage /> },
    { path: "admin/customization/picklists", element: <CustomizationStudioPage /> },
    { path: "admin/customization/formulas", element: <CustomizationStudioPage /> },
    { path: "admin/customization/rollups", element: <CustomizationStudioPage /> },
    { path: "admin/customization/audit", element: <CustomizationStudioPage /> },
    { path: "admin/business-os/modules", element: <BusinessOSAdminPage /> },
    { path: "admin/business-os/integrations", element: <BusinessOSAdminPage /> },
    { path: "admin/business-os/lifecycle", element: <BusinessOSAdminPage /> },
    { path: "business-os", element: <BusinessOSWorkspacePage /> },
    { path: "business-os/dashboard", element: <BusinessOSWorkspacePage /> },
    { path: "business-os/customer-720", element: <BusinessOSWorkspacePage /> },
    { path: "business-os/reports", element: <BusinessOSWorkspacePage /> },
    { path: "business-os/ai", element: <BusinessOSWorkspacePage /> },
    { path: "analytics", element: <AnalyticsPage /> },
    { path: "analytics/report-builder", element: <AnalyticsPage /> },
    { path: "analytics/reports", element: <AnalyticsPage /> },
    { path: "analytics/reports/:id", element: <AnalyticsPage /> },
    { path: "analytics/dashboards", element: <AnalyticsPage /> },
    { path: "analytics/dashboards/:id", element: <AnalyticsPage /> },
    { path: "analytics/scheduled-reports", element: <AnalyticsPage /> },
    { path: "analytics/exports", element: <AnalyticsPage /> },
    { path: "analytics/funnel", element: <AnalyticsPage /> },
    { path: "analytics/forecast", element: <AnalyticsPage /> },
    { path: "analytics/profitability", element: <AnalyticsPage /> },
    { path: "analytics/collections", element: <AnalyticsPage /> },
    { path: "analytics/campaigns", element: <AnalyticsPage /> },
    { path: "analytics/anomalies", element: <AnalyticsPage /> },
  ];
  const routes = [...enabledRoutes, ...commonRoutes, ...aiAgentRoutes, ...aiCopilotRoutes, ...adminSecurityRoutes, ...saasRoutes];
  void moduleVersion;

  return (
    <>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/reset-password" element={<LoginPage />} />
          <Route path="/hrms/login" element={<LoginPage />} />
          <Route path="/crm/login" element={<LoginPage />} />
          <Route path="/pms/login" element={<LoginPage />} />
          <Route path="/srm/login" element={<LoginPage />} />
          <Route path="/fam/login" element={<LoginPage />} />
          <Route path="/portal/customer/login" element={<PortalPage />} />
          <Route path="/portal/customer/*" element={<PortalPage />} />
          <Route path="/portal/partner/login" element={<PortalPage />} />
          <Route path="/portal/partner/*" element={<PortalPage />} />
          <Route path="/Inventory" element={<Navigate to="/inventory" replace />} caseSensitive />
          <Route path="/Inventory/dashboard" element={<Navigate to="/inventory/dashboard" replace />} caseSensitive />
          <Route path="/inventory" element={<InventoryBridgePage />} caseSensitive />
          <Route path="/inventory/dashboard" element={<InventoryBridgePage />} caseSensitive />
          <Route path="/" element={<ModuleIndexPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            {routes.map((route) => (
              <Route key={route.path} path={route.path} element={route.element} caseSensitive={route.caseSensitive} />
            ))}
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      {isHydrated && isAuthenticated ? <PMSRealtimeBridge /> : null}
      <Toaster />
    </>
  );
}
