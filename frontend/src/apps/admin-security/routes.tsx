import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const AdminSecurityPage = React.lazy(() => import("./AdminSecurityPage"));

export const adminSecurityRoutes: FrontendRoute[] = [
  { path: "admin/security", element: <AdminSecurityPage /> },
  { path: "admin/profiles", element: <AdminSecurityPage /> },
  { path: "admin/roles", element: <AdminSecurityPage /> },
  { path: "admin/field-security", element: <AdminSecurityPage /> },
  { path: "admin/record-sharing", element: <AdminSecurityPage /> },
  { path: "admin/data-sharing", element: <AdminSecurityPage /> },
  { path: "admin/ip-restrictions", element: <AdminSecurityPage /> },
  { path: "admin/audit-logs", element: <AdminSecurityPage /> },
  { path: "admin/import", element: <AdminSecurityPage /> },
  { path: "admin/duplicates", element: <AdminSecurityPage /> },
  { path: "admin/export-control", element: <AdminSecurityPage /> },
  { path: "admin/backups", element: <AdminSecurityPage /> },
  { path: "admin/compliance", element: <AdminSecurityPage /> },
  { path: "admin/data-retention", element: <AdminSecurityPage /> },
];
