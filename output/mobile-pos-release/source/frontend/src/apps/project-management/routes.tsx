import { Navigate, useLocation } from "react-router-dom";
import { lazyRoute } from "@/lib/lazy-route";
import ModuleWorkspaceFrame from "@/shared/workspace/ModuleWorkspaceFrame";
import { ProjectDetailFrame } from "./components/ProjectDetailHeader";
import React from "react";
const ImportWorkspace = lazyRoute(() => import("@/shared/data-transfer/ImportWorkspace"));
const FollowUpsPage = lazyRoute(() => import("@/shared/follow-ups/FollowUpsPage"));
import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
const DashboardsPage = lazyRoute(() => import("./pages/DashboardsPage"));
import type { FrontendRoute } from "@/appRegistry";
const WorkforceOperationsPage = lazyRoute(() => import("@/components/workforce/WorkforceOperationsPage"));
const MyNoticesPage = lazyRoute(() => import("./pages/MyNoticesPage"));

const ManagementHomePage = lazyRoute(() => import("./pages/ManagementHomePage"));
const WorkflowSchemesPage = lazyRoute(() => import("./pages/WorkflowSchemesPage"));
const TransitionApprovalInbox = lazyRoute(() => import("./pages/TransitionApprovalInbox"));
const MyWorkPage = lazyRoute(() => import("./pages/MyWorkPage"));
const MemberManagementPage = lazyRoute(() => import("./pages/MemberManagementPage"));
const PeopleDirectoryProfile = lazyRoute(() => import("./pages/PeopleDirectoryProfile"));
const PeopleDirectoryPage = lazyRoute(() => import("./pages/PeopleManagementDirectory"));
const WorkspaceDirectoryPage = lazyRoute(() => import("./pages/WorkspaceDirectoryPage"));
const WorkspacesPage = lazyRoute(() => import("./pages/WorkspacesPage"));
const AIOperatorPage = lazyRoute(() => import("./pages/AIOperatorPage"));
const AssistantStudio = lazyRoute(() => import("./pages/AssistantStudio"));
const OperatorProviderSettings = lazyRoute(() => import("@/pages/ai-agents/OperatorProviderSettings"));

const DirectMessagesPage = lazyRoute(() => import("./pages/DirectMessagesPage"));
const CustomFieldManagerPage = lazyRoute(() => import("./pages/CustomFieldManagerPage"));
const DocsPage = lazyRoute(() => import("./pages/DocsPage"));
const NotesPage = lazyRoute(() => import("./pages/NotesPage"));
const TaskTypesPage = lazyRoute(() => import("./pages/TaskTypesPage"));
const TagManagerPage = lazyRoute(() => import("./pages/TagManagerPage"));
const PlansPage = lazyRoute(() => import("./pages/PlansPage"));
const AuditLogsPage = lazyRoute(() => import("./pages/AuditLogsPage"));
const AnalyticsPage = lazyRoute(() => import("./pages/AnalyticsPage"));
const OrgChartPage = lazyRoute(() => import("./pages/OrgChartPage"));
const TeamsPage = lazyRoute(() => import("./pages/TeamsPage"));
const WorkspaceAdminPage = lazyRoute(() => import("./pages/WorkspaceAdminPage"));
const RecoveryPage = lazyRoute(() => import("./pages/RecoveryPage"));
const TrashPage = lazyRoute(() => import("./pages/TrashPage"));

// Lazy load components
const ProjectManagementHomePage = lazyRoute(() => import("./ProjectManagementHomePage"));
const ProjectBillingPage = lazyRoute(() => import("./pages/ProjectBillingPage"));
const ProjectDashboard = lazyRoute(() => import("./pages/ProjectDashboard"));
const ProjectCommunicationPage = lazyRoute(() => import("./pages/ProjectCommunicationPage"));
const TeamCommunicationPage = lazyRoute(() => import("./pages/TeamCommunicationPage"));
const KanbanBoard = lazyRoute(() => import("./pages/KanbanBoard"));
const ProjectsList = lazyRoute(() => import("./pages/ProjectsList"));
const CreateProjectPage = lazyRoute(() => import("./pages/CreateProjectPage"));
const Record360Page = lazyRoute(() => import("@/shared/records/Record360Page"));
const TasksFollowUpsPage = lazyRoute(() => import("./pages/TasksFollowUpsPage"));
const TaskExperiencePage = lazyRoute(() => import("./pages/TaskExperiencePage"));
const TasksReferencePage = lazyRoute(() => import("./pages/TasksReferencePage"));
const TaskListPage = lazyRoute(() => import("./pages/TaskListPage"));
const TaskWorkspacePage = lazyRoute(() => import("./pages/TaskWorkspacePage"));
const TaskDetail = lazyRoute(() => import("./pages/TaskDetail"));
const MilestonesPage = lazyRoute(() => import("./pages/MilestonesPage"));
const TimeTrackingPage = lazyRoute(() => import("./pages/TimeTrackingPage"));
const TimesheetsPage = lazyRoute(() => import("./pages/TimesheetsPage"));
const ReportsPage = lazyRoute(() => import("./pages/ReportsPage"));
const CalendarPage = lazyRoute(() => import("./pages/CalendarPage"));
const GanttPage = lazyRoute(() => import("./pages/GanttPage"));
const SprintsPage = lazyRoute(() => import("./pages/SprintsPage"));
const BacklogPage = lazyRoute(() => import("./pages/BacklogPage"));
const RoadmapPage = lazyRoute(() => import("./pages/RoadmapPage"));
const WorkloadPage = lazyRoute(() => import("./pages/WorkloadPage"));
const FilesPage = lazyRoute(() => import("./pages/FilesPage"));
const ClientsPage = lazyRoute(() => import("./pages/ClientsPage"));
const ClientPortalPage = lazyRoute(() => import("./pages/ClientPortalPage"));
const AdminPage = lazyRoute(() => import("./pages/AdminPage"));
const SettingsPage = lazyRoute(() => import("./pages/SettingsPage"));
const SoftwarePlanningPage = lazyRoute(() => import("./pages/SoftwarePlanningPage"));
const LiveWorkManagementPage = lazyRoute(() => import("./pages/LiveWorkManagementPage"));
const ImpactWorkHubPage = lazyRoute(() => import("./pages/ImpactWorkHubPage"));
const TimelineDependenciesPage = lazyRoute(() => import("./pages/TimelineDependenciesPage"));
const AutomationAIPage = lazyRoute(() => import("./pages/AutomationAIPage"));
const FormsPage = lazyRoute(() => import("./pages/FormsPage"));
const CommandCenterPage = lazyRoute(() => import("./pages/CommandCenterPage"));
const EnterpriseEnginePage = lazyRoute(() => import("./pages/EnterpriseEnginePage"));
const ProductLaunchPage = lazyRoute(() => import("./pages/ProductLaunchPage"));
const PMSOperationsPage = lazyRoute(() => import("./pages/PMSOperationsPage"));
const PortfolioPage = lazyRoute(() => import("./pages/PortfolioPage"));
const RisksPage = lazyRoute(() => import("./pages/RisksPage"));
const ModuleProfilePage = lazyRoute(() => import("@/pages/ModuleProfilePage"));

/**
 * KaryaFlow Routes
 * Complete routing for Project Management module
 */
const BatchWorkspacePage=lazyRoute(()=>import("./pages/BatchWorkspacePage"));
const MyAssignmentsPage=lazyRoute(()=>import("./pages/MyAssignmentsPage"));
const AssignmentControlsPage=lazyRoute(()=>import("./pages/AssignmentControlsPage"));
const WorkReviewsPage = lazyRoute(() => import("./pages/WorkReviewsPage"));
const SharedCatalogPage = lazyRoute(() => import("@/shared/catalog/CatalogPage"));
function PmsNavigationRedirect({to="/pms/workspace-tools"}: {to?:string}) {
  const location=useLocation();
  return <Navigate replace to={`${to}${location.search}${location.hash}`}/>;
}
export const projectManagementRoutes: FrontendRoute[] = [
  {path:"pms/import-data",element:<ImportWorkspace module="pms"/>},
 {path:"pms/tasks-follow-ups",element:<TasksFollowUpsPage/>},
 {path:"pms/customers/:id/360",element:<Record360Page/>},
 {path:"pms/follow-ups",element:<FollowUpsPage/>},
 {path:"pms/follow-ups/directory",element:<FollowUpsPage/>},
 {path:"pms/follow-ups/calendar",element:<FollowUpsPage/>},
 {path:"pms/follow-ups/:id",element:<FollowUpsPage/>},
 {path:"pms/products-services",element:<SharedCatalogPage source="pms"/>},
 {path:"pms/products",element:<SharedCatalogPage source="pms"/>},
 {path:"pms/management",element:<ManagementHomePage/>},
 {path:"pms/workflow-schemes",element:<WorkflowSchemesPage/>},
 {path:"pms/transition-approvals",element:<TransitionApprovalInbox/>},
 {path:"pms/admin/configuration",element:<AdminPage/>},
 {path:"pms/my-work",element:<MyWorkPage/>},
 {path:"pms/members",element:<MemberManagementPage/>},
 {path:"pms/projects/:projectId/members",element:<ProjectDetailFrame><MemberManagementPage /></ProjectDetailFrame>},
 {path:"pms/people",element:<PeopleDirectoryPage/>},
 {path:"pms/people/:personId",element:<PeopleDirectoryProfile/>},
 {path:"pms/directory",element:<PeopleDirectoryPage/>},
 {path:"pms/people-work",element:<WorkforceOperationsPage/>},
 {path:"pms/my-notices",element:<MyNoticesPage/>},
 {path:"pms/batches",element:<BatchWorkspacePage/>},
 {path:"pms/batch-tasks",element:<BatchWorkspacePage mode="tasks"/>},
 {path:"pms/my-assignments",element:<MyAssignmentsPage/>},
 {path:"pms/assignment-controls",element:<AssignmentControlsPage/>},
  { path: "pms/reviews", element: <WorkReviewsPage /> },
  { path: "pms/admin/workspaces", element: <WorkspaceAdminPage /> },
  { path: "pms/recovery", element: <RecoveryPage /> },
  { path: "pms/audit-logs", element: <AuditLogsPage /> },
  { path: "pms/analytics/team", element: <AnalyticsPage mode="team" /> },
  { path: "pms/analytics/projects", element: <AnalyticsPage mode="project" /> },
  { path: "pms/projects/:projectId/analytics", element: <AnalyticsPage mode="project" /> },
  { path: "pms/operator", element: <AIOperatorPage /> },
  { path: "pms/assistant", element: <AssistantStudio /> },
  { path: "pms/settings/ai/:provider", element: <OperatorProviderSettings /> },
  { path: "pms/workspaces", element: <WorkspaceDirectoryPage /> },
  // Home / Dashboard
  { path: "pms", element: <WorkspacesPage /> },
  { path: "pms/overview", element: <ProjectManagementHomePage /> },
  { path: "pms/profile", element: <ModuleProfilePage /> },
  { path: "pms/command-center", element: <CommandCenterPage /> },
  { path: "pms/workspace-tools", element: <CommandCenterPage /> },
  { path: "pms/enterprise-engine", element: <EnterpriseEnginePage /> },
  { path: "pms/product-launch", element: <ProductLaunchPage /> },
  { path: "pms/portfolio", element: <PortfolioPage /> },
  { path: "pms/dependency-management", element: <PMSOperationsPage mode="dependencies" /> },
  { path: "pms/resource-planning", element: <PMSOperationsPage mode="resources" /> },
  { path: "pms/agile-execution", element: <PMSOperationsPage mode="agile" /> },
  { path: "pms/project-financials", element: <PMSOperationsPage mode="financials" /> },
  { path: "pms/risk-register", element: <RisksPage /> },
  { path: "pms/risks", element: <RisksPage /> },
  
  // Projects
  { path: "pms/projects", element: <ProjectsList /> },
  { path: "pms/projects/classic", element: <ProjectsList /> },
  { path: "pms/projects/new", element: <CreateProjectPage /> },
  { path: "pms/projects/:projectId/edit", element: <CreateProjectPage /> },
  
  // Project Dashboard & Views
  { path: "pms/projects/:projectId/billing", element: <ProjectDetailFrame><ProjectBillingPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId", element: <ProjectDashboard /> },
  { path: "pms/projects/:projectId/communication", element: <ProjectCommunicationPage /> },
  { path: "pms/projects/:projectId/board", element: <ProjectDetailFrame><KanbanBoard /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/timeline", element: <ProjectDetailFrame><GanttPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/gantt", element: <ProjectDetailFrame><GanttPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/milestones", element: <ProjectDetailFrame><MilestonesPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/files", element: <ProjectDetailFrame><FilesPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/reports", element: <ProjectDetailFrame><ReportsPage /></ProjectDetailFrame> },
  { path: "pms/projects/:projectId/risks", element: <ProjectDetailFrame><RisksPage /></ProjectDetailFrame> },
  
  // Tasks
  { path: "pms/tasks", element: <TaskExperiencePage /> },
  { path: "pms/tasks/advanced", element: <TaskListPage /> },
  { path: "pms/tasks/new", element: <TasksReferencePage /> },
  { path: "pms/tasks/:taskId", element: <TaskWorkspacePage /> },
  { path: "pms/tasks/:taskId/edit", element: <TasksReferencePage /> },
  { path: "pms/tasks/:taskId/classic", element: <TaskDetail /> },
  { path: "pms/projects/:projectId/tasks/:taskId", element: <TaskWorkspacePage /> },

  // KaryaFlow software delivery workspaces
  { path: "pms/work-hub", element: <ImpactWorkHubPage /> },
  { path: "pms/impact", element: <ImpactWorkHubPage /> },
  { path: "pms/ai-planner", element: <PmsNavigationRedirect to="/pms/operator" /> },
  { path: "pms/timeline-plus", element: <TimelineDependenciesPage /> },
  { path: "pms/dependency-timeline", element: <TimelineDependenciesPage /> },
  { path: "pms/automation-ai", element: <AutomationAIPage /> },
  { path: "pms/software", element: <SoftwarePlanningPage /> },
  { path: "pms/live", element: <LiveWorkManagementPage /> },
  { path: "pms/teams-live", element: <LiveWorkManagementPage /> },
  { path: "pms/backlog", element: <BacklogPage /> },
  { path: "pms/issues", element: <PmsNavigationRedirect to="/pms/software" /> },
  { path: "pms/roadmap", element: <RoadmapPage /> },
  { path: "pms/workload", element: <WorkloadPage /> },
  { path: "pms/capacity", element: <WorkloadPage /> },
  { path: "pms/releases", element: <PmsNavigationRedirect to="/pms/software" /> },
  { path: "pms/automation", element: <AutomationAIPage /> },
  { path: "pms/goals", element: <CommandCenterPage /> },
  { path: "pms/forms", element: <FormsPage /> },
  { path: "pms/messages", element: <DirectMessagesPage /> },
  { path: "pms/team-communication", element: <TeamCommunicationPage /> },
  { path: "pms/custom-fields", element: <CustomFieldManagerPage /> },
  { path: "pms/teams", element: <TeamsPage /> },
  { path: "pms/org-chart", element: <OrgChartPage /> },
  { path: "pms/trash", element: <TrashPage /> },
  { path: "pms/templates", element: <CommandCenterPage /> },
  { path: "pms/components", element: <PmsNavigationRedirect /> },
  { path: "pms/workflows", element: <PmsNavigationRedirect /> },
  { path: "pms/security", element: <PmsNavigationRedirect /> },
  { path: "pms/dependencies", element: <PmsNavigationRedirect to="/pms/roadmap" /> },
  { path: "pms/navigator", element: <TaskListPage /> },
  { path: "pms/apps", element: <PmsNavigationRedirect /> },
  { path: "pms/dashboards", element: <DashboardsPage /> },
  { path: "pms/docs", element: <DocsPage /> },
  { path: "pms/notes", element: <NotesPage /> },
  { path: "pms/projects/:projectId/notes", element: <ProjectDetailFrame><NotesPage /></ProjectDetailFrame> },
  { path: "pms/task-types", element: <TaskTypesPage /> },
  { path: "pms/tags", element: <TagManagerPage /> },
  { path: "pms/plans", element: <PlansPage /> },
  { path: "pms/issue-navigator-pro", element: <PmsNavigationRedirect to="/pms/navigator" /> },
  { path: "pms/backlog-grooming", element: <PmsNavigationRedirect to="/pms/backlog" /> },
  { path: "pms/sprint-lifecycle", element: <PmsNavigationRedirect to="/pms/backlog" /> },
  { path: "pms/blueprints", element: <EnterpriseEnginePage /> },
  { path: "pms/resource-utilization", element: <PmsNavigationRedirect to="/pms/workload" /> },
  
  // Module-level workspaces
  { path: "pms/calendar", element: <CalendarPage /> },
  { path: "pms/planner", element: <PmsNavigationRedirect to="/pms/calendar" /> },
  { path: "pms/gantt", element: <GanttPage /> },
  { path: "pms/sprints", element: <SprintsPage /> },
  { path: "pms/files", element: <FilesPage /> },
  { path: "pms/time-tracking", element: <TimeTrackingPage /> },
  { path: "pms/timesheets", element: <TimesheetsPage /> },
  { path: "pms/reports", element: <ReportsPage /> },
  { path: "pms/clients", element: <ClientsPage /> },
  { path: "pms/client-portal", element: <ClientPortalPage /> },
  { path: "pms/settings", element: <CentralSettingsRedirect section="pms" /> },
  { path: "pms/admin", element: <ManagementHomePage /> },
].map(route => ({...route, element: <ModuleWorkspaceFrame module="pms">{route.element}</ModuleWorkspaceFrame>}));

