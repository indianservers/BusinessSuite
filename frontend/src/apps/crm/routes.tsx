import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const CRMWorkspacePage = React.lazy(() => import("./CRMWorkspacePage"));
const CRMRecordDetailPage = React.lazy(() => import("./CRMRecordDetailPage"));
const ModuleProfilePage = React.lazy(() => import("@/pages/ModuleProfilePage"));

export const crmRoutes: FrontendRoute[] = [
  { path: "crm", element: <CRMWorkspacePage kind="dashboard" /> },
  { path: "crm/profile", element: <ModuleProfilePage /> },
  { path: "crm/leads", element: <CRMWorkspacePage kind="leads" /> },
  { path: "crm/leads/:id", element: <CRMRecordDetailPage kind="leads" /> },
  { path: "crm/contacts", element: <CRMWorkspacePage kind="contacts" /> },
  { path: "crm/contacts/:id", element: <CRMRecordDetailPage kind="contacts" /> },
  { path: "crm/accounts", element: <CRMWorkspacePage kind="companies" /> },
  { path: "crm/accounts/:id", element: <CRMRecordDetailPage kind="accounts" /> },
  { path: "crm/companies", element: <CRMWorkspacePage kind="companies" /> },
  { path: "crm/companies/:id", element: <CRMRecordDetailPage kind="accounts" /> },
  { path: "crm/deals", element: <CRMWorkspacePage kind="deals" /> },
  { path: "crm/deals/:id", element: <CRMRecordDetailPage kind="deals" /> },
  { path: "crm/pipeline", element: <CRMWorkspacePage kind="pipeline" /> },
  { path: "crm/pipeline-settings", element: <CRMWorkspacePage kind="pipelineSettings" /> },
  { path: "crm/activities", element: <CRMWorkspacePage kind="activities" /> },
  { path: "crm/tasks", element: <CRMWorkspacePage kind="tasks" /> },
  { path: "crm/calendar", element: <CRMWorkspacePage kind="calendar" /> },
  { path: "crm/calendar-integrations", element: <CRMWorkspacePage kind="calendarIntegrations" /> },
  { path: "crm/webhooks", element: <CRMWorkspacePage kind="webhooks" /> },
  { path: "crm/campaigns", element: <CRMWorkspacePage kind="campaigns" /> },
  { path: "crm/products", element: <CRMWorkspacePage kind="products" /> },
  { path: "crm/quotations", element: <CRMWorkspacePage kind="quotations" /> },
  { path: "crm/quotations/:id", element: <CRMRecordDetailPage kind="quotations" /> },
  { path: "crm/approval-settings", element: <CRMWorkspacePage kind="approvalSettings" /> },
  { path: "crm/my-approvals", element: <CRMWorkspacePage kind="myApprovals" /> },
  { path: "crm/duplicates", element: <CRMWorkspacePage kind="duplicates" /> },
  { path: "crm/territories", element: <CRMWorkspacePage kind="territories" /> },
  { path: "crm/tickets", element: <CRMWorkspacePage kind="tickets" /> },
  { path: "crm/files", element: <CRMWorkspacePage kind="files" /> },
  { path: "crm/reports", element: <CRMWorkspacePage kind="reports" /> },
  { path: "crm/automation", element: <CRMWorkspacePage kind="automation" /> },
  { path: "crm/lead-to-cash", element: <CRMWorkspacePage kind="leadCash" /> },
  { path: "crm/forecasting", element: <CRMWorkspacePage kind="forecasting" /> },
  { path: "crm/customer-360", element: <CRMWorkspacePage kind="customer360" /> },
  { path: "crm/import-export", element: <CRMWorkspacePage kind="importExport" /> },
  { path: "crm/settings", element: <CRMWorkspacePage kind="settings" /> },
  { path: "crm/lead-scoring", element: <CRMWorkspacePage kind="leadScoring" /> },
  { path: "crm/feature-checklist", element: <CRMWorkspacePage kind="featureChecklist" /> },
  { path: "crm/admin", element: <CRMWorkspacePage kind="admin" /> },
];
