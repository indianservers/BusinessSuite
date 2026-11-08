import { lazyRoute } from "@/lib/lazy-route";
const OperationalWorkspaceDirectory = lazyRoute(() => import("@/shared/workspace/OperationalWorkspaceDirectory"));
import React from "react";
const ImportWorkspace = lazyRoute(() => import("@/shared/data-transfer/ImportWorkspace"));
import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
const UserAccountsPage = lazyRoute(() => import("@/apps/hrms/pages/employees/UserAccountsPage"));
const CommunicationWorkspace = lazyRoute(() => import("@/shared/communication/CommunicationWorkspace"));
const ModuleGanttPage = lazyRoute(() => import("@/components/scheduling/ModuleGanttPage"));
import { Navigate, useLocation } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
const WorkforceOperationsPage = lazyRoute(() => import("@/components/workforce/WorkforceOperationsPage"));

const InternApplicationsPage = lazyRoute(() => import("@/apps/hrms/pages/interns/InternApplicationsPage"));
const HRDailyWork = lazyRoute(() => import("./workbench/HRDailyWork"));
const DashboardPage = lazyRoute(() => import("@/apps/hrms/pages/dashboard/DashboardPage"));
const RoleWorkspacePage = lazyRoute(() => import("@/apps/hrms/pages/dashboard/RoleWorkspacePage"));
const ManagerDashboardPage = lazyRoute(() => import("@/apps/hrms/pages/dashboard/ManagerDashboardPage"));
const EmployeesPage = lazyRoute(() => import("@/apps/hrms/pages/employees/EmployeesPage"));
const EmployeeDirectoryPage = lazyRoute(() => import("@/components/PeopleDirectoryPage"));
const EmployeeDetailPage = lazyRoute(() => import("@/apps/hrms/pages/employees/EmployeeDetailPage"));
const AddEmployeePage = lazyRoute(() => import("@/apps/hrms/pages/employees/AddEmployeePage"));
const ProbationPage = lazyRoute(() => import("@/apps/hrms/pages/employees/ProbationPage"));
const AttendancePage = lazyRoute(() => import("@/apps/hrms/pages/attendance/AttendancePage"));
const MyAttendancePage = lazyRoute(() => import("@/apps/hrms/pages/attendance/MyAttendancePage"));
const ShiftRosterPage = lazyRoute(() => import("@/apps/hrms/pages/attendance/ShiftRosterPage"));
const MyRosterPage = lazyRoute(() => import("@/apps/hrms/pages/attendance/MyRosterPage"));
const TimesheetsPage = lazyRoute(() => import("@/apps/hrms/pages/timesheets/TimesheetsPage"));
const ApprovalOsPage = lazyRoute(() => import("@/apps/hrms/pages/workflow/ApprovalOsPage"));
const WorkflowInboxPage = lazyRoute(() => import("@/apps/hrms/pages/workflow/WorkflowInboxPage"));
const WorkflowDesignerPage = lazyRoute(() => import("@/apps/hrms/pages/workflow/WorkflowDesignerPage"));
const NotificationsPage = lazyRoute(() => import("@/apps/hrms/pages/notifications/NotificationsPage"));
const LeavePage = lazyRoute(() => import("@/apps/hrms/pages/leave/LeavePage"));
const PayrollPage = lazyRoute(() => import("@/apps/hrms/pages/payroll/PayrollPage"));
const MyPayslipsPage = lazyRoute(() => import("@/apps/hrms/pages/profile/MyPayslipsPage"));
const FnFSettlementPage = lazyRoute(() => import("@/apps/hrms/pages/payroll/FnFSettlementPage"));
const InvestmentDeclarationPage = lazyRoute(() => import("@/apps/hrms/pages/payroll/InvestmentDeclarationPage"));
const RecruitmentPage = lazyRoute(() => import("@/apps/hrms/pages/recruitment/RecruitmentPage"));
const PerformancePage = lazyRoute(() => import("@/apps/hrms/pages/performance/PerformancePage"));
const HelpdeskPage = lazyRoute(() => import("@/apps/hrms/pages/helpdesk/HelpdeskPage"));
const ReportsPage = lazyRoute(() => import("@/apps/hrms/pages/reports/ReportsPage"));
const AdvancedAnalyticsPage = lazyRoute(() => import("@/apps/hrms/pages/analytics/AdvancedAnalyticsPage"));
const AdminLogsPage = lazyRoute(() => import("@/apps/hrms/pages/logs/AdminLogsPage"));
const CompanyPage = lazyRoute(() => import("@/apps/hrms/pages/company/CompanyPage"));
const OrgChartPage = lazyRoute(() => import("@/apps/hrms/pages/company/OrgChartPage"));
const AIAssistantPage = lazyRoute(() => import("@/apps/hrms/pages/ai/AIAssistantPage"));
const ProfilePage = lazyRoute(() => import("@/apps/hrms/pages/profile/ProfilePage"));
const SharedProfilePage = lazyRoute(() => import("@/features/profiles/ProfilePage"));
const SharedProfileManagementPage = lazyRoute(() => import("@/features/profiles/ProfilePage").then(module => ({ default: module.SharedProfileManagementPage })));
const ESSPortalPage = lazyRoute(() => import("@/apps/hrms/pages/profile/ESSPortalPage"));
const AssetsPage = lazyRoute(() => import("@/apps/hrms/pages/assets/AssetsPage"));
const ExpensesPage = lazyRoute(() => import("@/apps/hrms/pages/expenses/ExpensesPage"));
const OnboardingPage = lazyRoute(() => import("@/apps/hrms/pages/onboarding/OnboardingPage"));
const DocumentsPage = lazyRoute(() => import("@/apps/hrms/pages/documents/DocumentsPage"));
const DocumentStudioPage = lazyRoute(() => import("@/apps/hrms/pages/documents/DocumentStudioPage"));
const ExitPage = lazyRoute(() => import("@/apps/hrms/pages/exit/ExitPage"));
const SettingsPage = lazyRoute(() => import("@/apps/hrms/pages/settings/SettingsPage"));
const EngagementPage = lazyRoute(() => import("@/apps/hrms/pages/engagement/EngagementPage"));
const BenefitsPage = lazyRoute(() => import("@/apps/hrms/pages/benefits/BenefitsPage"));
const LMSPage = lazyRoute(() => import("@/apps/hrms/pages/lms/LMSPage"));
const StatutoryCompliancePage = lazyRoute(() => import("@/apps/hrms/pages/compliance/StatutoryCompliancePage"));
const BackgroundVerificationPage = lazyRoute(() => import("@/apps/hrms/pages/compliance/BackgroundVerificationPage"));
const WhatsAppESSPage = lazyRoute(() => import("@/apps/hrms/pages/platform/WhatsAppESSPage"));
const CustomFieldsPage = lazyRoute(() => import("@/apps/hrms/pages/platform/CustomFieldsPage"));
const EnterprisePage = lazyRoute(() => import("@/apps/hrms/pages/platform/EnterprisePage"));

const InternManagementPage = lazyRoute(() => import("./pages/interns/InternManagementPage"));

const MyAssignmentsPage=lazyRoute(()=>import("@/apps/project-management/pages/MyAssignmentsPage"));
const moduleRoutes: FrontendRoute[] = [
  {path:"daily-work",element:<HRDailyWork/>},
  {path:"my-assignments",element:<React.Suspense><MyAssignmentsPage/></React.Suspense>},
  { path: "dashboard", element: <DashboardPage /> },
  { path: "role-home", element: <HRDailyWork /> },
  { path: "admin-home", element: <HRDailyWork /> },
  { path: "hr-home", element: <HRDailyWork /> },
  { path: "executive-home", element: <RoleWorkspacePage /> },
  { path: "manager-dashboard", element: <ManagerDashboardPage /> },
  { path: "ess", element: <ESSPortalPage /> },
  { path: "employee-directory", element: <EmployeeDirectoryPage /> },
  { path: "interns/applications", element: <InternApplicationsPage /> },
  { path: "interns/list", element: <InternManagementPage page="batches" /> },
  { path: "interns/operations", element: <WorkforceOperationsPage context="interns" /> },
  { path: "people-work", element: <WorkforceOperationsPage /> },
  { path: "interns-hub/applications", element: <InternApplicationsPage /> },
  { path: "interns-hub", element: <InternManagementPage page="dashboard" /> },
  { path: "interns", element: <InternManagementPage page="dashboard" /> },
  { path: "interns/dashboard", element: <InternManagementPage page="dashboard" /> },
  { path: "interns/batches", element: <InternManagementPage page="batches" /> },
  { path: "interns/tasks", element: <InternManagementPage page="tasks" /> },
  { path: "interns/reviews", element: <InternManagementPage page="reviews" /> },
  { path: "interns/performance", element: <InternManagementPage page="performance" /> },

  { path: "users", element: <UserAccountsPage /> },
  { path: "employees", element: <EmployeesPage /> },
  { path: "employees/new", element: <AddEmployeePage /> },
  { path: "employees/:id", element: <EmployeeDetailPage /> },
  { path: "probation", element: <ProbationPage /> },
  { path: "attendance", element: <AttendancePage /> },
  { path: "my-attendance", element: <MyAttendancePage /> },
  { path: "attendance/shift-roster", element: <ShiftRosterPage /> },
  { path: "my-roster", element: <MyRosterPage /> },
  { path: "timesheets", element: <TimesheetsPage /> },
  { path: "approval-os", element: <ApprovalOsPage /> },
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
  { path: "company", element: <CentralSettingsRedirect section="company-profile" /> },
  { path: "org-chart", element: <OrgChartPage /> },
  { path: "settings", element: <Navigate to="/settings" replace /> },
  { path: "assets", element: <AssetsPage /> },
  { path: "expenses", element: <ExpensesPage /> },
  { path: "onboarding", element: <OnboardingPage /> },
  { path: "documents", element: <DocumentsPage /> },
  { path: "letters-certificates", element: <DocumentStudioPage /> },
  { path: "exit", element: <ExitPage /> },
  { path: "ai-assistant", element: <AIAssistantPage /> },
  { path: "profile", element: <SharedProfilePage /> },
  { path: "profile/security", element: <ProfilePage /> },
  { path: "profile-management", element: <SharedProfileManagementPage /> },
  { path: "interns/profiles", element: <SharedProfileManagementPage /> },
];

function LegacyHrmsRedirect() {
  const location = useLocation();
  return <Navigate to={`/hrms${location.pathname}${location.search}${location.hash}`} replace />;
}

const BirthdaysPage = lazyRoute(()=>import("@/shared/master-data/BirthdaysPage"));
export const hrmsRoutes: FrontendRoute[] = [
  { path: "hrms/workspaces", element: <OperationalWorkspaceDirectory module="hrms" /> },
  {path:"hrms/import-data",element:<ImportWorkspace module="hrms"/>},
 {path:"hrms/birthdays",element:<BirthdaysPage source="hrms"/>},
 { path: "hrms/messages", element: <CommunicationWorkspace module="HRMS" /> },
  { path: "hrms/leave/gantt", element: <ModuleGanttPage key="hrms" module="hrms" /> },
  { path: "hrms", element: <HRDailyWork /> },
  ...moduleRoutes.map((route) => ({
    ...route,
    path: `hrms/${route.path}`,
  })),
  ...moduleRoutes.map((route) => ({
    path: route.path,
    element: <LegacyHrmsRedirect />,
  })),
];

