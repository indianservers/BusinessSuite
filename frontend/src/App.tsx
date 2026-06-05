import React, { Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { Toaster } from "@/components/ui/toaster";
import { useAuthStore } from "@/store/authStore";
import AppLayout from "@/components/layout/AppLayout";
import { canAccessRoute } from "@/lib/roles";
import { getInstalledAppKeys, type FrontendRoute } from "@/appRegistry";
import { getLoginPathForContext } from "@/lib/products";
import { hrmsRoutes } from "@/apps/hrms/routes";
import { crmRoutes } from "@/apps/crm/routes";
import { projectManagementRoutes } from "@/apps/project-management/routes";
import { srmRoutes } from "@/apps/srm/routes";
import { aiAgentRoutes } from "@/pages/ai-agents/routes";
import PMSRealtimeBridge from "@/apps/project-management/PMSRealtimeBridge";

const LoginPage = React.lazy(() => import("@/pages/auth/LoginPage"));
const ModuleIndexPage = React.lazy(() => import("@/pages/ModuleIndexPage"));
const AccessDeniedPage = React.lazy(() => import("@/pages/AccessDeniedPage"));

const appRoutes: Record<string, FrontendRoute[]> = {
  hrms: hrmsRoutes,
  crm: crmRoutes,
  project_management: projectManagementRoutes,
  srm: srmRoutes,
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
          <p className="text-lg font-semibold">Business Suite</p>
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
  const enabledRoutes = getEnabledRoutes();
  const routes = [...enabledRoutes, ...aiAgentRoutes];

  return (
    <>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/hrms/login" element={<LoginPage />} />
          <Route path="/crm/login" element={<LoginPage />} />
          <Route path="/pms/login" element={<LoginPage />} />
          <Route path="/srm/login" element={<LoginPage />} />
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
              <Route key={route.path} path={route.path} element={route.element} />
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
