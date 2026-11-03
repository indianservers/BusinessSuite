import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const SaaSWorkspacePage = React.lazy(() => import("./SaaSWorkspacePage"));

export const saasRoutes: FrontendRoute[] = [
  { path: "mobile", element: <SaaSWorkspacePage /> },
  { path: "mobile/leads", element: <SaaSWorkspacePage /> },
  { path: "mobile/deals", element: <SaaSWorkspacePage /> },
  { path: "mobile/activities", element: <SaaSWorkspacePage /> },
  { path: "mobile/check-in", element: <SaaSWorkspacePage /> },
  { path: "developer", element: <SaaSWorkspacePage /> },
  { path: "developer/api-keys", element: <CentralSettingsRedirect section="api-credentials" /> },
  { path: "developer/webhooks", element: <CentralSettingsRedirect section="webhooks" /> },
  { path: "developer/api-logs", element: <SaaSWorkspacePage /> },
  { path: "developer/docs", element: <SaaSWorkspacePage /> },
  { path: "marketplace", element: <SaaSWorkspacePage /> },
  { path: "marketplace/apps", element: <SaaSWorkspacePage /> },
  { path: "marketplace/installed", element: <SaaSWorkspacePage /> },
  { path: "admin/sandbox", element: <SaaSWorkspacePage /> },
  { path: "admin/company-settings", element: <CentralSettingsRedirect section="company-profile" /> },
  { path: "admin/feature-flags", element: <SaaSWorkspacePage /> },
  { path: "admin/subscription", element: <SaaSWorkspacePage /> },
  { path: "admin/usage", element: <SaaSWorkspacePage /> },
];

export const PortalPage = React.lazy(() => import("./PortalPage"));
