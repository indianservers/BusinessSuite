import { PendingPageProgress } from "./components/app/RouteProgress";
import React, { Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { Toaster } from "@/components/ui/toaster";
import { useAuthStore } from "@/store/authStore";
import AppLayout from "@/components/layout/AppLayout";
import { canAccessRoute, effectiveModuleDisplayRole } from "@/lib/roles";
import { getInstalledAppKeys, setBusinessOsEnabledModules, type FrontendRoute } from "@/appRegistry";
import { api } from "@/services/api";
import { BUSINESS_SUITE_DISPLAY_NAME } from "@/lib/products";
import { hrmsRoutes } from "@/apps/hrms/routes";
import { crmRoutes } from "@/apps/crm/routes";
import { projectManagementRoutes } from "@/apps/project-management/routes";
import { srmRoutes } from "@/apps/srm/routes";
import { famRoutes } from "@/apps/fam/routes";
import { aiAgentRoutes } from "@/pages/ai-agents/routes";
import { aiCopilotRoutes } from "@/apps/ai-copilot/routes";
import { adminSecurityRoutes } from "@/apps/admin-security/routes";
import { PortalPage, saasRoutes } from "@/apps/saas/routes";
import { applicationRoutes } from "@/apps/power-apps/registry";
import PMSRealtimeBridge from "@/apps/project-management/PMSRealtimeBridge";

const AutomationRuntimePage = React.lazy(() => import("@/apps/power-apps/applications/automations/AutomationRuntimePage"));
const AutomationEditorPage = React.lazy(() => import("@/apps/power-apps/applications/automations/AutomationEditorPage"));
const ApprovalsPage = React.lazy(() => import("@/apps/power-apps/applications/approvals/ApprovalsPage"));
const ModuleDashboardPage = React.lazy(() => import("@/pages/ModuleDashboardPage"));
const PowerAppsPage = React.lazy(() => import("@/apps/power-apps/PowerAppsPage"));
const SharedFormsPage = React.lazy(() => import("@/features/forms/FormsPage"));
const PublicFormPage = React.lazy(() => import("@/features/forms/PublicFormPage"));
const LoginPage = React.lazy(() => import("@/pages/auth/LoginPage"));
const WorkspaceInvitationPage = React.lazy(() => import("@/pages/auth/WorkspaceInvitationPage"));
const AccessDeniedPage = React.lazy(() => import("@/pages/AccessDeniedPage"));
const AutomationStudioPage = React.lazy(() => import("@/apps/automation/AutomationStudioPage"));
const CustomizationStudioPage = React.lazy(() => import("@/apps/customization/CustomizationStudioPage"));
const AnalyticsPage = React.lazy(() => import("@/apps/analytics/AnalyticsPage"));
const BusinessOSAdminPage = React.lazy(() => import("@/apps/business-os/BusinessOSAdminPage"));
const BusinessOSWorkspacePage = React.lazy(() => import("@/apps/business-os/BusinessOSWorkspacePage"));
const AiSecurityPage = React.lazy(() => import("@/features/access/AiSecurityPage"));
const EnterprisePage = React.lazy(() => import("@/features/access/EnterprisePage"));
const SharedServicesPage = React.lazy(() => import("@/features/access/SharedServicesPage"));
const ControlCenter = React.lazy(() => import("@/features/access/ControlCenter"));
const UserAccess360 = React.lazy(() => import("@/features/access/ControlCenter").then(m => ({ default: m.UserAccess360 })));
const UsersAccessPage = React.lazy(() => import("@/features/access/UsersAccessPage"));
const AccessInvitationPage = React.lazy(() => import("@/features/access/UsersAccessPage").then(m => ({ default: m.AccessInvitationPage })));

const appRoutes: Record<string, FrontendRoute[]> = {
  hrms: hrmsRoutes,
  crm: crmRoutes,
  project_management: projectManagementRoutes,
  srm: srmRoutes,
  fam: famRoutes,
};

function getEnabledRoutes() {
  return getInstalledAppKeys().flatMap((key) => appRoutes[key] || []);
}

function LoadingFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 dark:bg-background">
      <PendingPageProgress />
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

function LegacyModuleLogin({ home }: { home: string }) {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  if (!params.has("next")) params.set("next", home);
  return <Navigate to={`/login?${params.toString()}${location.hash}`} replace />;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { isAuthenticated, isHydrated, user } = useAuthStore();
  const roleAllowed = canAccessRoute(location.pathname, user?.role, user?.is_superuser);
  const membershipPath = /^\/pms\/projects(?:\/|$)/.test(location.pathname) || /^\/pms\/tasks\/\d+$/.test(location.pathname);
  const accessKey = `${user?.id}:${location.pathname}`;
  const [workspaceAccess, setWorkspaceAccess] = useState<{ key: string; allowed: boolean } | null>(null);
  useEffect(() => {
    if (!isHydrated || !isAuthenticated || !user || roleAllowed || !membershipPath) return;
    let active = true;
    api.get("/project-management/workspaces").then(({ data }) => {
      if (active) setWorkspaceAccess({ key: accessKey, allowed: data.length > 0 });
    }).catch(() => { if (active) setWorkspaceAccess({ key: accessKey, allowed: false }); });
    return () => { active = false; };
  }, [isHydrated, isAuthenticated, user?.id, roleAllowed, membershipPath, accessKey]);
  if (!isHydrated) return <LoadingFallback />;
  if (!isAuthenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`} replace />;
  }
  if (!user) return <LoadingFallback />;
  if (!roleAllowed) {
    if (!membershipPath) return <AccessDeniedPage />;
    if (workspaceAccess?.key !== accessKey) return <LoadingFallback />;
    if (!workspaceAccess.allowed) return <AccessDeniedPage />;
  }
  return <>{children}</>;
}

export default function App() {
  const location = useLocation();
  const currentUser = useAuthStore(s => s.user);
  const { isAuthenticated, isHydrated } = useAuthStore();
  const [moduleVersion, setModuleVersion] = useState(0);
  useEffect(() => {
    if (!currentUser?.access) return;
    const role = effectiveModuleDisplayRole(location.pathname, currentUser);
    if (currentUser.primary_role === undefined || currentUser.role !== role) {
      useAuthStore.getState().setUser({ ...currentUser, primary_role: currentUser.primary_role === undefined ? currentUser.role : currentUser.primary_role, role });
    }
  }, [location.pathname, currentUser]);
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
  useEffect(() => {
    if (!isHydrated || !isAuthenticated) return;
    const load = () => api.get("/access/me").then(({data}) => {
      if (typeof data.managed !== "boolean") return;
      const state = useAuthStore.getState();
      if (state.user) state.setUser({ ...state.user, access: data });
    }).catch(() => undefined);
    load();
    const timer = window.setInterval(load, 45000);
    window.addEventListener("focus", load);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", load); };
  }, [isHydrated, isAuthenticated]);
  const enabledRoutes = getEnabledRoutes();
  const commonRoutes: FrontendRoute[] = [
    { path: "power-apps", element: <PowerAppsPage /> },
    { path: "power-apps/approvals", element: <ApprovalsPage /> },
    { path: "power-apps/approvals/:section", element: <ApprovalsPage /> },
    { path: "power-apps/approvals/designer/:id", element: <ApprovalsPage /> },
    { path: "power-apps/automations/executions", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/executions/:runId", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/:resourceId/runtime", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/new", element: <AutomationEditorPage /> },
    ...["edit", "versions", "settings"].map(section => ({ path: `power-apps/automations/:resourceId/${section}`, element: <AutomationEditorPage /> })),
    { path: "power-apps/automations/:resourceId", element: <AutomationEditorPage /> },
    ...applicationRoutes.map(id => ({ path: `power-apps/${id}`, element: <PowerAppsPage /> })),
    { path: "admin/access", element: <UsersAccessPage /> },
    { path: "admin/control/ai-security", element: <AiSecurityPage /> },
    { path: "admin/control/enterprise/:section", element: <EnterprisePage /> },
    { path: "admin/control/services/:section", element: <SharedServicesPage /> },
    ...["dashboard", "organizations", "modules", "security", "audit"].map(page => ({ path: `admin/control/${page}`, element: <ControlCenter /> })),
    { path: "admin/control/users/:id", element: <UserAccess360 /> },
    ...["pms","crm","srm","hrms","fam"].flatMap(module=>["published","responses","custom-fields","new",":formId/edit",":formId/responses"].map(path=>({path:`${module}/forms/${path}`,element:<SharedFormsPage/>}))),
    ...["pms","crm","srm","hrms","fam"].map(module=>({path:`${module}/forms/:formId/view`,element:<PublicFormPage internal/>})),
    ...["crm","srm","hrms","fam"].map(module=>({path:`${module}/forms`,element:<SharedFormsPage/>})),
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
          <Route path="/f/:slug" element={<PublicFormPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<ModuleDashboardPage />} />
          <Route path="/reset-password" element={<LoginPage />} />
          <Route path="/invite-access" element={<AccessInvitationPage />} />
          <Route path="/hrms/login" element={<LegacyModuleLogin home="/hrms" />} />
          <Route path="/crm/login" element={<LegacyModuleLogin home="/crm" />} />
          <Route path="/pms/login" element={<LegacyModuleLogin home="/pms" />} />
          <Route path="/pms/invitation" element={<WorkspaceInvitationPage />} />
          <Route path="/srm/login" element={<LegacyModuleLogin home="/srm" />} />
          <Route path="/fam/login" element={<LegacyModuleLogin home="/fam" />} />
          <Route path="/portal/customer/login" element={<PortalPage />} />
          <Route path="/portal/customer/*" element={<PortalPage />} />
          <Route path="/portal/partner/login" element={<PortalPage />} />
          <Route path="/portal/partner/*" element={<PortalPage />} />
          <Route path="/Inventory/login" element={<Navigate to="/srm/login" replace />} caseSensitive />
          <Route path="/inventory/login" element={<Navigate to="/srm/login" replace />} caseSensitive />
          <Route path="/Inventory" element={<Navigate to="/srm/inventory" replace />} caseSensitive />
          <Route path="/Inventory/*" element={<Navigate to="/srm/inventory" replace />} caseSensitive />
          <Route path="/inventory" element={<Navigate to="/srm/inventory" replace />} caseSensitive />
          <Route path="/inventory/*" element={<Navigate to="/srm/inventory" replace />} caseSensitive />
          <Route path="/" element={!isHydrated ? <LoadingFallback /> : <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
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
