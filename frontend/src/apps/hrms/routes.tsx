import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";

const DashboardPage = React.lazy(() => import("@/apps/hrms/pages/dashboard/DashboardPage"));
const RoleWorkspacePage = React.lazy(() => import("@/apps/hrms/pages/dashboard/RoleWorkspacePage"));
const ManagerDashboardPage = React.lazy(() => import("@/apps/hrms/pages/dashboard/ManagerDashboardPage"));
const EmployeesPage = React.lazy(() => import("@/apps/hrms/pages/employees/EmployeesPage"));
const EmployeeDirectoryPage = React.lazy(() => import("@/apps/hrms/pages/employees/EmployeeDirectoryPage"));
const EmployeeDetailPage = React.lazy(() => import("@/apps/hrms/pages/employees/EmployeeDetailPage"));
const AddEmployeePage = React.lazy(() => import("@/apps/hrms/pages/employees/AddEmployeePage"));
const ProbationPage = React.lazy(() => import("@/apps/hrms/pages/employees/ProbationPage"));
const AttendancePage = React.lazy(() => import("@/apps/hrms/pages/attendance/AttendancePage"));
const MyAttendancePage = React.lazy(() => import("@/apps/hrms/pages/attendance/MyAttendancePage"));
const ShiftRosterPage = React.lazy(() => import("@/apps/hrms/pages/attendance/ShiftRosterPage"));
const MyRosterPage = React.lazy(() => import("@/apps/hrms/pages/attendance/MyRosterPage"));
const TimesheetsPage = React.lazy(() => import("@/apps/hrms/pages/timesheets/TimesheetsPage"));
const WorkflowInboxPage = React.lazy(() => import("@/apps/hrms/pages/workflow/WorkflowInboxPage"));
const WorkflowDesignerPage = React.lazy(() => import("@/apps/hrms/pages/workflow/WorkflowDesignerPage"));
const NotificationsPage = React.lazy(() => import("@/apps/hrms/pages/notifications/NotificationsPage"));
const LeavePage = React.lazy(() => import("@/apps/hrms/pages/leave/LeavePage"));
const PayrollPage = React.lazy(() => import("@/apps/hrms/pages/payroll/PayrollPage"));
const MyPayslipsPage = React.lazy(() => import("@/apps/hrms/pages/profile/MyPayslipsPage"));
const FnFSettlementPage = React.lazy(() => import("@/apps/hrms/pages/payroll/FnFSettlementPage"));
const InvestmentDeclarationPage = React.lazy(() => import("@/apps/hrms/pages/payroll/InvestmentDeclarationPage"));
const RecruitmentPage = React.lazy(() => import("@/apps/hrms/pages/recruitment/RecruitmentPage"));
const PerformancePage = React.lazy(() => import("@/apps/hrms/pages/performance/PerformancePage"));
const HelpdeskPage = React.lazy(() => import("@/apps/hrms/pages/helpdesk/HelpdeskPage"));
const ReportsPage = React.lazy(() => import("@/apps/hrms/pages/reports/ReportsPage"));
const AdvancedAnalyticsPage = React.lazy(() => import("@/apps/hrms/pages/analytics/AdvancedAnalyticsPage"));
const AdminLogsPage = React.lazy(() => import("@/apps/hrms/pages/logs/AdminLogsPage"));
const CompanyPage = React.lazy(() => import("@/apps/hrms/pages/company/CompanyPage"));
const OrgChartPage = React.lazy(() => import("@/apps/hrms/pages/company/OrgChartPage"));
const AIAssistantPage = React.lazy(() => import("@/apps/hrms/pages/ai/AIAssistantPage"));
const ProfilePage = React.lazy(() => import("@/apps/hrms/pages/profile/ProfilePage"));
const ESSPortalPage = React.lazy(() => import("@/apps/hrms/pages/profile/ESSPortalPage"));
const AssetsPage = React.lazy(() => import("@/apps/hrms/pages/assets/AssetsPage"));
const OnboardingPage = React.lazy(() => import("@/apps/hrms/pages/onboarding/OnboardingPage"));
const DocumentsPage = React.lazy(() => import("@/apps/hrms/pages/documents/DocumentsPage"));
const ExitPage = React.lazy(() => import("@/apps/hrms/pages/exit/ExitPage"));
const SettingsPage = React.lazy(() => import("@/apps/hrms/pages/settings/SettingsPage"));
const EngagementPage = React.lazy(() => import("@/apps/hrms/pages/engagement/EngagementPage"));
const BenefitsPage = React.lazy(() => import("@/apps/hrms/pages/benefits/BenefitsPage"));
const LMSPage = React.lazy(() => import("@/apps/hrms/pages/lms/LMSPage"));
const StatutoryCompliancePage = React.lazy(() => import("@/apps/hrms/pages/compliance/StatutoryCompliancePage"));
const BackgroundVerificationPage = React.lazy(() => import("@/apps/hrms/pages/compliance/BackgroundVerificationPage"));
const WhatsAppESSPage = React.lazy(() => import("@/apps/hrms/pages/platform/WhatsAppESSPage"));
const CustomFieldsPage = React.lazy(() => import("@/apps/hrms/pages/platform/CustomFieldsPage"));
const EnterprisePage = React.lazy(() => import("@/apps/hrms/pages/platform/EnterprisePage"));

const moduleRoutes: FrontendRoute[] = [
  { path: "dashboard", element: <DashboardPage /> },
  { path: "role-home", element: <RoleWorkspacePage /> },
  { path: "admin-home", element: <RoleWorkspacePage /> },
  { path: "hr-home", element: <RoleWorkspacePage /> },
  { path: "executive-home", element: <RoleWorkspacePage /> },
  { path: "manager-dashboard", element: <ManagerDashboardPage /> },
  { path: "ess", element: <ESSPortalPage /> },
  { path: "employee-directory", element: <EmployeeDirectoryPage /> },
  { path: "employees", element: <EmployeesPage /> },
  { path: "employees/new", element: <AddEmployeePage /> },
  { path: "employees/:id", element: <EmployeeDetailPage /> },
  { path: "probation", element: <ProbationPage /> },
  { path: "attendance", element: <AttendancePage /> },
  { path: "my-attendance", element: <MyAttendancePage /> },
  { path: "attendance/shift-roster", element: <ShiftRosterPage /> },
  { path: "my-roster", element: <MyRosterPage /> },
  { path: "timesheets", element: <TimesheetsPage /> },
  { path: "workflow", element: <WorkflowInboxPage /> },
  { path: "workflow-designer", element: <WorkflowDesignerPage /> },
  { path: "notifications", element: <NotificationsPage /> },
  { path: "leave", element: <LeavePage /> },
  { path: "payroll", element: <PayrollPage /> },
  { path: "my-payslips", element: <MyPayslipsPage /> },
  { path: "fnf-settlements", element: <FnFSettlementPage /> },
  { path: "investment-declaration", element: <InvestmentDeclarationPage /> },
  { path: "recruitment", element: <RecruitmentPage /> },
  { path: "performance", element: <PerformancePage /> },
  { path: "benefits", element: <BenefitsPage /> },
  { path: "lms", element: <LMSPage /> },
  { path: "statutory-compliance", element: <StatutoryCompliancePage /> },
  { path: "background-verification", element: <BackgroundVerificationPage /> },
  { path: "whatsapp-ess", element: <WhatsAppESSPage /> },
  { path: "custom-fields", element: <CustomFieldsPage /> },
  { path: "enterprise", element: <EnterprisePage /> },
  { path: "engagement", element: <EngagementPage /> },
  { path: "helpdesk", element: <HelpdeskPage /> },
  { path: "reports", element: <ReportsPage /> },
  { path: "advanced-analytics", element: <AdvancedAnalyticsPage /> },
  { path: "logs", element: <AdminLogsPage /> },
  { path: "company", element: <CompanyPage /> },
  { path: "org-chart", element: <OrgChartPage /> },
  { path: "settings", element: <SettingsPage /> },
  { path: "assets", element: <AssetsPage /> },
  { path: "onboarding", element: <OnboardingPage /> },
  { path: "documents", element: <DocumentsPage /> },
  { path: "exit", element: <ExitPage /> },
  { path: "ai-assistant", element: <AIAssistantPage /> },
  { path: "profile", element: <ProfilePage /> },
];

function LegacyHrmsRedirect() {
  const location = useLocation();
  return <Navigate to={`/hrms${location.pathname}${location.search}${location.hash}`} replace />;
}

export const hrmsRoutes: FrontendRoute[] = [
  { path: "hrms", element: <DashboardPage /> },
  ...moduleRoutes.map((route) => ({
    ...route,
    path: `hrms/${route.path}`,
  })),
  ...moduleRoutes.map((route) => ({
    path: route.path,
    element: <LegacyHrmsRedirect />,
  })),
];

