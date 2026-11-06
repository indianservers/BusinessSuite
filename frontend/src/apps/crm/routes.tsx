import React from "react";
const WhatsAppCommunicationPage = React.lazy(() => import("@/apps/communication/WhatsAppCommunicationPage"));
const ImportWorkspace = React.lazy(() => import("@/shared/data-transfer/ImportWorkspace"));
const FollowUpSummary = React.lazy(() => import("@/shared/follow-ups/FollowUpSummary"));
const FollowUpsPage = React.lazy(() => import("@/shared/follow-ups/FollowUpsPage"));
import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
const Deal360Page = React.lazy(() => import("./deals/Deal360Page"));
const CommunicationWorkspace = React.lazy(() => import("@/shared/communication/CommunicationWorkspace"));
const Record360Page = React.lazy(() => import("@/shared/records/Record360Page"));
const PaymentRequestsPage = React.lazy(() => import("@/shared/payments/PaymentRequestsPage"));
const ModuleGanttPage = React.lazy(() => import("@/components/scheduling/ModuleGanttPage"));
import type { FrontendRoute } from "@/appRegistry";

const CRMStatisticsWorklist=React.lazy(()=>import("./CRMStatisticsWorklist"));
const CRMSalesHome = React.lazy(() => import("./CRMSalesHome"));
const CRMActivitiesWorkspace = React.lazy(() => import("./CRMActivitiesWorkspace"));
const CRMWorkspacePage = React.lazy(() => import("./CRMWorkspacePage"));
const CRMRecordDetailPage = React.lazy(() => import("./CRMRecordDetailPage"));
const LeadManagementPage = React.lazy(() => import("./leads/LeadManagementPage"));
const CommunicationHubPage = React.lazy(() => import("@/apps/communication/CommunicationHubPage"));
const ModuleProfilePage = React.lazy(() => import("@/pages/ModuleProfilePage"));

const ProductCustomersPage = React.lazy(() => import("./product-customers/ProductCustomersPage"));
const GrowthWorkspace = React.lazy(() => import("./GrowthWorkspace"));
const FollowUpWorkspace = React.lazy(() => import("./FollowUpWorkspace"));
const SharedCatalogPage = React.lazy(() => import("@/shared/catalog/CatalogPage"));
const CRMRecordsPage = React.lazy(() => import("./CRMRecordsPage"));
const CRMMetadataPage = React.lazy(() => import("./CRMWorkspacePage").then(module => ({ default: module.CustomFieldsSettingsPage })));
const CompaniesPage = React.lazy(()=>import("@/shared/master-data/CompaniesPage"));
export const crmRoutes: FrontendRoute[] = [
  { path: "crm/whatsapp-communication", element: <WhatsAppCommunicationPage /> },
  {path:"crm/import-data",element:<ImportWorkspace module="crm"/>},
 {path:"crm/customers/:id/360",element:<React.Suspense fallback={<p>Loading customer…</p>}><Record360Page/></React.Suspense>},
 {path:"crm/payment-requests",element:<PaymentRequestsPage/>},
 {path:"crm/birthdays",element:<CommunicationHubPage/>},
 {path:"crm/company-directory",element:<CentralSettingsRedirect section="shared-companies"/>},
  { path: "crm/records", element: <CRMRecordsPage /> },
  { path: "crm/record-metadata", element: <CRMMetadataPage /> },
  {path:"crm/product-customers",element:<ProductCustomersPage/>},
  {path:"crm/customer-follow-ups",element:<FollowUpWorkspace/>},
  {path:"crm/greetings",element:<GrowthWorkspace key="greetings" mode="greetings"/>},
 {path:"crm/follow-ups/directory",element:<FollowUpsPage/>},
 {path:"crm/follow-ups/calendar",element:<FollowUpsPage/>},
 {path:"crm/follow-ups/:id",element:<FollowUpsPage/>},
  {path:"crm/products-services",element:<SharedCatalogPage source="crm"/>},
  {path:"crm/statistics/:kind",element:<CRMStatisticsWorklist/>},
 { path: "crm/messages", element: <CommunicationWorkspace module="CRM" /> },
  { path: "crm/gantt", element: <ModuleGanttPage key="crm" module="crm" /> },
  { path: "crm", element: <><FollowUpSummary base="/crm/follow-ups"/><CRMWorkspacePage kind="dashboard" /></> },
  { path: "crm/sales-home", element: <CRMSalesHome /> },
  { path: "crm/follow-ups", element: <FollowUpsPage /> },
  { path: "crm/dashboard", element: <><FollowUpSummary base="/crm/follow-ups"/><CRMWorkspacePage kind="dashboard" /></> },
  { path: "crm/profile", element: <ModuleProfilePage /> },
  { path: "crm/potential-clients", element: <LeadManagementPage potential /> },
  { path: "crm/leads", element: <LeadManagementPage /> },
  { path: "crm/leads/classic", element: <CRMWorkspacePage kind="leads" /> },
  { path: "crm/leads/workbench", element: <LeadManagementPage /> },
  { path: "crm/leads/:id", element: <CRMRecordDetailPage kind="leads" /> },
  { path: "crm/contacts", element: <CRMWorkspacePage kind="contacts" /> },
  { path: "crm/contacts/:id", element: <CRMRecordDetailPage kind="contacts" /> },
  { path: "crm/accounts", element: <CompaniesPage role="Customer" /> },
  { path: "crm/accounts/:id", element: <CRMRecordDetailPage kind="accounts" /> },
  { path: "crm/companies", element: <CompaniesPage /> },
  { path: "crm/customers", element: <CompaniesPage role="Customer" /> },
  { path: "crm/vendors", element: <CompaniesPage role="Vendor" /> },
  { path: "crm/companies/:id", element: <CRMRecordDetailPage kind="accounts" /> },
  { path: "crm/deals", element: <CRMWorkspacePage kind="deals" /> },
  { path: "crm/deals/:id", element: <Deal360Page /> },
  { path: "crm/pipeline", element: <CRMWorkspacePage kind="pipeline" /> },
  { path: "crm/templates", element: <CRMWorkspacePage kind="pipeline" /> },
  { path: "crm/pipeline-settings", element: <CentralSettingsRedirect section="crm-pipelines" /> },
  { path: "crm/pipelines", element: <CRMWorkspacePage kind="pipelineSettings" /> },
  { path: "crm/pipelines/:id", element: <CRMWorkspacePage kind="pipelineSettings" /> },
  { path: "crm/activities", element: <CRMWorkspacePage kind="activities" /> },
  { path: "crm/tasks", element: <CRMActivitiesWorkspace /> },
  { path: "crm/calendar", element: <CRMWorkspacePage kind="calendar" /> },
  { path: "crm/calendar-integrations", element: <CRMWorkspacePage kind="calendarIntegrations" /> },
  { path: "crm/webhooks", element: <CentralSettingsRedirect section="crm-webhooks" /> },
  { path: "crm/send-reminders", element: <CommunicationHubPage /> },
  { path: "crm/communication-hub", element: <CommunicationHubPage /> },
  { path: "crm/email-templates", element: <CommunicationHubPage /> },
  { path: "crm/emails", element: <CommunicationHubPage /> },
  { path: "crm/webforms", element: <CommunicationHubPage /> },
  { path: "crm/webforms/:id", element: <CommunicationHubPage /> },
  { path: "crm/campaigns", element: <CommunicationHubPage /> },
  { path: "crm/campaigns/:id", element: <CommunicationHubPage /> },
  { path: "crm/consents", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp/inbox", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp/sent", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp/templates", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp/profile", element: <CommunicationHubPage /> },
  { path: "crm/whatsapp/settings", element: <CommunicationHubPage /> },
  { path: "crm/auto-responses", element: <CommunicationHubPage /> },
  { path: "crm/delivery-logs", element: <CommunicationHubPage /> },
  { path: "crm/communication-timeline", element: <CommunicationHubPage /> },
  { path: "crm/products", element: <SharedCatalogPage source="crm" /> },
  { path: "crm/products/:id", element: <SharedCatalogPage source="crm" /> },
  { path: "crm/services", element: <SharedCatalogPage source="crm" /> },
  { path: "crm/services/:id", element: <SharedCatalogPage source="crm" /> },
  { path: "crm/price-books", element: <CRMWorkspacePage kind="priceBooks" /> },
  { path: "crm/price-books/:id", element: <CRMWorkspacePage kind="priceBooks" /> },
  { path: "crm/quotes", element: <CRMWorkspacePage kind="quotes" /> },
  { path: "crm/quotes/:id", element: <CRMWorkspacePage kind="quoteBuilder" /> },
  { path: "crm/quotes/:id/builder", element: <CRMWorkspacePage kind="quoteBuilder" /> },
  { path: "crm/quote-approvals", element: <CRMWorkspacePage kind="quoteApprovals" /> },
  { path: "crm/cpq", element: <CRMWorkspacePage kind="cpq" /> },
  { path: "crm/guided-selling", element: <CRMWorkspacePage kind="guidedSelling" /> },
  { path: "crm/quotations", element: <CRMWorkspacePage kind="quotations" /> },
  { path: "crm/quotations/:id", element: <CRMRecordDetailPage kind="quotations" /> },
  { path: "crm/approval-settings", element: <CentralSettingsRedirect section="crm-approvals" /> },
  { path: "crm/my-approvals", element: <CRMWorkspacePage kind="myApprovals" /> },
  { path: "crm/duplicates", element: <CRMWorkspacePage kind="duplicates" /> },
  { path: "crm/territories", element: <CentralSettingsRedirect section="crm-territories" /> },
  { path: "crm/tickets", element: <CRMWorkspacePage kind="tickets" /> },
  { path: "crm/files", element: <CRMWorkspacePage kind="files" /> },
  { path: "crm/reports", element: <CRMWorkspacePage kind="reports" /> },
  { path: "crm/automation", element: <CentralSettingsRedirect section="crm-automation" /> },
  { path: "crm/lead-to-cash", element: <CRMWorkspacePage kind="leadCash" /> },
  { path: "crm/forecasting", element: <CRMWorkspacePage kind="forecasting" /> },
  { path: "crm/forecasts", element: <CRMWorkspacePage kind="forecasting" /> },
  { path: "crm/targets", element: <CRMWorkspacePage kind="targets" /> },
  { path: "crm/sales-performance", element: <CRMWorkspacePage kind="salesPerformance" /> },
  { path: "crm/funnel", element: <CRMWorkspacePage kind="funnel" /> },
  { path: "crm/lost-analysis", element: <CRMWorkspacePage kind="lostAnalysis" /> },
  { path: "crm/customer-360", element: <CRMWorkspacePage kind="customer360" /> },
  { path: "crm/import-export", element: <CRMWorkspacePage kind="importExport" /> },
  { path: "crm/settings", element: <CentralSettingsRedirect section="crm" /> },
  { path: "crm/lead-scoring", element: <CentralSettingsRedirect section="crm-scoring" /> },
  { path: "crm/feature-checklist", element: <CRMWorkspacePage kind="featureChecklist" /> },
  { path: "crm/admin", element: <CRMWorkspacePage kind="admin" /> },
];
