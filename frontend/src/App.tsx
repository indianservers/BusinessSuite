import { useQueryClient } from "@tanstack/react-query";
import { accessQueryOptions } from "@/features/access/access-query";
import RoutePrefetch from "@/components/app/RoutePrefetch";
import { lazyRoute } from "@/lib/lazy-route";
import { LoadingState } from "@/components/ui/state";
import { ActionTooltipProvider } from "@/components/actions";
import SetupReadiness from "@/components/suite/SetupReadiness";
import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
import OperationsWorkspace from "@/components/layout/OperationsWorkspace";
import { getOperationWorkspace } from "@/lib/navigation-workspaces";
import { PendingPageProgress } from "./components/app/RouteProgress";
import React, { Suspense, useEffect, useState } from "react";
const StatisticsAuditPage=lazyRoute(()=>import("@/features/access/StatisticsAuditPage"));
const PersonManagementHost = lazyRoute(() => import("@/apps/project-management/components/people/PersonManagementHost"));
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
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
import SuiteNavigationTracker from "@/components/suite/SuiteNavigationTracker";
import PMSRealtimeBridge from "@/apps/project-management/PMSRealtimeBridge";
import { SmartCreationProvider } from "@/shared/creation/SmartCreationProvider";
import ErrorBoundary from "@/components/app/ErrorBoundary";

const AutomationRuntimePage = lazyRoute(() => import("@/apps/power-apps/applications/automations/AutomationRuntimePage"));
const AutomationEditorPage = lazyRoute(() => import("@/apps/power-apps/applications/automations/AutomationEditorPage"));
const ApprovalsPage = lazyRoute(() => import("@/apps/power-apps/applications/approvals/ApprovalsPage"));
const SuiteWelcomePage = lazyRoute(() => import("@/pages/SuiteWelcomePage"));
const SuiteNotificationsPage = lazyRoute(() => import("@/pages/SuiteNotificationsPage"));
const SuiteAccountPage = lazyRoute(() => import("@/pages/SuiteAccountPage"));
const SuiteHelpPage = lazyRoute(() => import("@/pages/SuiteHelpPage"));
const PostLoginPage = lazyRoute(() => import("@/pages/PostLoginPage"));
const SettingsHubPage = lazyRoute(() => import("@/pages/SettingsHubPage"));
const CompanyAdminPage = lazyRoute(() => import("@/pages/CompanyAdminPage"));
const ModuleDashboardPage = lazyRoute(() => import("@/pages/ModuleDashboardPage"));
const IntegrationsPage = lazyRoute(() => import("@/apps/power-apps/applications/integrations/IntegrationsPage"));
const ConnectorCatalog = lazyRoute(() => import("@/shared/ConnectorCatalog"));
const PowerAppsPage = lazyRoute(() => import("@/apps/power-apps/PowerAppsPage"));
const SharedFormsPage = lazyRoute(() => import("@/features/forms/FormsPage"));
const PublicFormPage = lazyRoute(() => import("@/features/forms/PublicFormPage"));
const PublicCustomerForm = lazyRoute(() => import("@/apps/communication/center/PublicCustomerForm"));
const SignupPage = lazyRoute(() => import("@/pages/auth/SignupPage"));
const LoginPage = lazyRoute(() => import("@/pages/auth/LoginPage"));
const WorkspaceInvitationPage = lazyRoute(() => import("@/pages/auth/WorkspaceInvitationPage"));
const AccessDeniedPage = lazyRoute(() => import("@/pages/AccessDeniedPage"));
const AutomationStudioPage = lazyRoute(() => import("@/apps/automation/AutomationStudioPage"));
const CustomizationStudioPage = lazyRoute(() => import("@/apps/customization/CustomizationStudioPage"));
const AnalyticsPage = lazyRoute(() => import("@/apps/analytics/AnalyticsPage"));
const BusinessOSAdminPage = lazyRoute(() => import("@/apps/business-os/BusinessOSAdminPage"));
const BusinessOSWorkspacePage = lazyRoute(() => import("@/apps/business-os/BusinessOSWorkspacePage"));
const AiSecurityPage = lazyRoute(() => import("@/features/access/AiSecurityPage"));
const EnterprisePage = lazyRoute(() => import("@/features/access/EnterprisePage"));
const SharedServicesPage = lazyRoute(() => import("@/features/access/SharedServicesPage"));
const ControlCenter = lazyRoute(() => import("@/features/access/ControlCenter"));
const UserAccess360 = lazyRoute(() => import("@/features/access/ControlCenter").then(m => ({ default: m.UserAccess360 })));
const UsersAccessPage = lazyRoute(() => import("@/features/access/UsersAccessPage"));
const AccessInvitationPage = lazyRoute(() => import("@/features/access/UsersAccessPage").then(m => ({ default: m.AccessInvitationPage })));

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
  return <div className="p-4 sm:p-6"><LoadingState /></div>;
}

function LegacyModuleLogin() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const query = params.toString();
  return <Navigate to={`/login${query ? `?${query}` : ""}${location.hash}`} replace />;
}

function ProtectedRoute({ children, sessionOnly=false }: { children: React.ReactNode;sessionOnly?:boolean }) {
  const location = useLocation();
  const { isAuthenticated, isHydrated, user } = useAuthStore();
  const roleAllowed = canAccessRoute(location.pathname, user?.role, user?.is_superuser);
  const membershipPath = /^\/pms\/projects(?:\/|$)/.test(location.pathname) || /^\/pms\/tasks\/\d+$/.test(location.pathname);
  const accessKey = `${user?.id}:${location.pathname}`;
  const [workspaceAccess, setWorkspaceAccess] = useState<{ key: string; allowed: boolean } | null>(null);
  useEffect(() => {
    if (sessionOnly || !isHydrated || !isAuthenticated || !user || roleAllowed || !membershipPath) return;
    let active = true;
    api.get("/project-management/workspaces").then(({ data }) => {
      if (active) setWorkspaceAccess({ key: accessKey, allowed: data.length > 0 });
    }).catch(() => { if (active) setWorkspaceAccess({ key: accessKey, allowed: false }); });
    return () => { active = false; };
  }, [isHydrated, isAuthenticated, user?.id, roleAllowed, membershipPath, accessKey, sessionOnly]);
  if (!isHydrated) return <LoadingFallback />;
  if (!isAuthenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`} replace />;
  }
  if (!user) return <LoadingFallback />;
  if (sessionOnly) return <>{children}</>;
  if (!roleAllowed) {
    if (!membershipPath) return <AccessDeniedPage />;
    if (workspaceAccess?.key !== accessKey) return <LoadingFallback />;
    if (!workspaceAccess.allowed) return <AccessDeniedPage />;
  }
  return <>{children}</>;
}

export default function App() {
  const queryClient=useQueryClient();
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
    const load = () => {
      const options=accessQueryOptions();
      return queryClient.fetchQuery(options).then(data=>{
        if(typeof data.managed!=="boolean"||JSON.stringify(options.queryKey)!==JSON.stringify(accessQueryOptions().queryKey))return;
        const state=useAuthStore.getState();if(state.user)state.setUser({...state.user,access:data});
      }).catch(()=>undefined);
    };
    load();
    const timer = window.setInterval(()=>{if(document.visibilityState!=="hidden")void load();}, 45000);
    window.addEventListener("focus", load);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", load); };
  }, [isHydrated, isAuthenticated]);
  const enabledRoutes = getEnabledRoutes();
  const commonRoutes: FrontendRoute[] = [
    { path: "connectors", element: <ConnectorCatalog /> },
    ...["crm", "pms", "hrms", "srm", "fam"].map(module => ({ path: `${module}/connectors`, element: <ConnectorCatalog /> })),
    { path: "power-apps", element: <PowerAppsPage /> },
    { path: "power-apps/connectors", element: <PowerAppsPage><IntegrationsPage /></PowerAppsPage> },
    { path: "power-apps/integrations", element: <PowerAppsPage><IntegrationsPage /></PowerAppsPage> },
    { path: "power-apps/approvals", element: <PowerAppsPage><ApprovalsPage embedded /></PowerAppsPage> },
    { path: "power-apps/approvals/:section", element: <PowerAppsPage><ApprovalsPage embedded /></PowerAppsPage> },
    { path: "power-apps/approvals/designer/:id", element: <PowerAppsPage><ApprovalsPage embedded /></PowerAppsPage> },
    { path: "power-apps/automations/executions", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/executions/:runId", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/:resourceId/runtime", element: <AutomationRuntimePage /> },
    { path: "power-apps/automations/new", element: <AutomationEditorPage /> },
    ...["edit", "versions", "settings"].map(section => ({ path: `power-apps/automations/:resourceId/${section}`, element: <AutomationEditorPage /> })),
    { path: "power-apps/automations/:resourceId", element: <AutomationEditorPage /> },
    ...applicationRoutes.filter(id => id !== "connectors").map(id => ({ path: `power-apps/${id}`, element: <PowerAppsPage /> })),
    { path: "admin/access", element: <CentralSettingsRedirect section="users" /> },
    { path: "admin/control/statistics", element: <StatisticsAuditPage /> },
    { path: "admin/control/ai-security", element: <AiSecurityPage /> },
    { path: "admin/control/enterprise/:section", element: <EnterprisePage /> },
    ...[{path:"connections",section:"connections"},{path:"delivery",section:"communication"},{path:"settings",section:"global"},{path:"webhooks",section:"webhooks"}].map(item=>({path:`admin/control/services/${item.path}`,element:<CentralSettingsRedirect section={item.section}/>})),
    { path: "admin/control/services/:section", element: <SharedServicesPage /> },
    ...["dashboard", "organizations", "modules", "security", "audit"].map(page => ({ path: `admin/control/${page}`, element: ["modules", "security", "audit"].includes(page) ? <CentralSettingsRedirect section={page}/> : <ControlCenter /> })),
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
    { path: "admin/customization/entities", element: <Navigate to="/admin/customization/modules" replace /> },
    { path: "admin/customization/modules/:id", element: <CustomizationStudioPage /> },
    { path: "admin/customization/fields", element: <CustomizationStudioPage /> },
    { path: "admin/customization/layouts", element: <CustomizationStudioPage /> },
    { path: "admin/customization/views", element: <CustomizationStudioPage /> },
    { path: "admin/customization/kanban", element: <CustomizationStudioPage /> },
    { path: "admin/customization/validation-rules", element: <CustomizationStudioPage /> },
    { path: "admin/customization/buttons", element: <CustomizationStudioPage /> },
    { path: 'admin/customization/related-lists', element: <CustomizationStudioPage /> },
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
    { path: "company-admin", element: <CompanyAdminPage /> },
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
    <SmartCreationProvider routes={routes}>
      <RoutePrefetch routes={routes} />
      <SetupReadiness />
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          <Route path="/f/:slug" element={<PublicFormPage />} />
          <Route path="/forms/communication/:slug" element={<PublicCustomerForm />} />
          <Route path="/admin/signup-requests" element={<Navigate to="/platform/signup-requests" replace />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<ModuleDashboardPage />} />
          <Route path="/settings/company/profile" element={<CentralSettingsRedirect section="company-profile" />} />
          <Route path="/settings/:section?" element={<SettingsHubPage />} />
          <Route path="/continue" element={<PostLoginPage />} />
          <Route path="/help" element={<SuiteHelpPage />} />
          <Route path="/account" element={<ProtectedRoute><SuiteAccountPage /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><SuiteNotificationsPage /></ProtectedRoute>} />
          <Route path="/reset-password" element={<LoginPage />} />
          <Route path="/invite-access" element={<AccessInvitationPage />} />
          <Route path="/hrms/login" element={<LegacyModuleLogin />} />
          <Route path="/crm/login" element={<LegacyModuleLogin />} />
          <Route path="/pms/login" element={<LegacyModuleLogin />} />
          <Route path="/pms/invitation" element={<WorkspaceInvitationPage />} />
          <Route path="/srm/login" element={<LegacyModuleLogin />} />
          <Route path="/fam/login" element={<LegacyModuleLogin />} />
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
          <Route path="/" element={!isHydrated ? <LoadingFallback /> : isAuthenticated ? <Navigate to="/dashboard" replace /> : <SuiteWelcomePage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute sessionOnly>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="setup-guide" element={<ProtectedRoute><></></ProtectedRoute>} />
            {routes.map((route) => (
              <Route key={route.path} path={route.path} element={<ProtectedRoute><Suspense fallback={<LoadingFallback />}>{getOperationWorkspace(`/${route.path}`) ? <OperationsWorkspace key={route.path} route={route} routes={routes} /> : route.element}</Suspense></ProtectedRoute>} caseSensitive={route.caseSensitive} />
            ))}
            <Route path="*" element={<div role="alert" className="rounded-xl border p-6"><h1 className="text-lg font-semibold">Page not found</h1><p>This page is unavailable. Choose a page from the menu or <Link className="underline" to="/dashboard">open all applications</Link>.</p></div>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      {isHydrated && isAuthenticated ? <PMSRealtimeBridge /> : null}
      <SuiteNavigationTracker />
      <Toaster />
      <ActionTooltipProvider />
      {isAuthenticated && <ErrorBoundary resetKey={location.pathname}><Suspense fallback={null}><PersonManagementHost /></Suspense></ErrorBoundary>}
    </SmartCreationProvider>
  );
}
