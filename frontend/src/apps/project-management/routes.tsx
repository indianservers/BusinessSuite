import DashboardsPage from "./pages/DashboardsPage";
import React from "react";
import type { FrontendRoute } from "@/appRegistry";
const WorkforceOperationsPage = React.lazy(() => import("@/components/workforce/WorkforceOperationsPage"));
const MyNoticesPage = React.lazy(() => import("./pages/MyNoticesPage"));

const MemberManagementPage = React.lazy(() => import("./pages/MemberManagementPage"));
const PeopleDirectoryPage = React.lazy(() => import("@/components/PeopleDirectoryPage"));
const WorkspacesPage = React.lazy(() => import("./pages/WorkspacesPage"));
const AIOperatorPage = React.lazy(() => import("./pages/AIOperatorPage"));
const AssistantStudio = React.lazy(() => import("./pages/AssistantStudio"));
const OperatorProviderSettings = React.lazy(() => import("@/pages/ai-agents/OperatorProviderSettings"));

const DirectMessagesPage = React.lazy(() => import("./pages/DirectMessagesPage"));
const CustomFieldManagerPage = React.lazy(() => import("./pages/CustomFieldManagerPage"));
const DocsPage = React.lazy(() => import("./pages/DocsPage"));
const NotesPage = React.lazy(() => import("./pages/NotesPage"));
const TaskTypesPage = React.lazy(() => import("./pages/TaskTypesPage"));
const TagManagerPage = React.lazy(() => import("./pages/TagManagerPage"));
const PlansPage = React.lazy(() => import("./pages/PlansPage"));
const AuditLogsPage = React.lazy(() => import("./pages/AuditLogsPage"));
const AnalyticsPage = React.lazy(() => import("./pages/AnalyticsPage"));
const OrgChartPage = React.lazy(() => import("./pages/OrgChartPage"));
const TeamsPage = React.lazy(() => import("./pages/TeamsPage"));
const WorkspaceAdminPage = React.lazy(() => import("./pages/WorkspaceAdminPage"));
const RecoveryPage = React.lazy(() => import("./pages/RecoveryPage"));
const TrashPage = React.lazy(() => import("./pages/TrashPage"));

// Lazy load components
const ProjectManagementHomePage = React.lazy(() => import("./ProjectManagementHomePage"));
const ProjectBillingPage = React.lazy(() => import("./pages/ProjectBillingPage"));
const ProjectDashboard = React.lazy(() => import("./pages/ProjectDashboard"));
const KanbanBoard = React.lazy(() => import("./pages/KanbanBoard"));
const ProjectsList = React.lazy(() => import("./pages/ProjectsList"));
const CreateProjectPage = React.lazy(() => import("./pages/CreateProjectPage"));
const TaskListPage = React.lazy(() => import("./pages/TaskListPage"));
const TaskDetail = React.lazy(() => import("./pages/TaskDetail"));
const MilestonesPage = React.lazy(() => import("./pages/MilestonesPage"));
const TimeTrackingPage = React.lazy(() => import("./pages/TimeTrackingPage"));
const TimesheetsPage = React.lazy(() => import("./pages/TimesheetsPage"));
const ReportsPage = React.lazy(() => import("./pages/ReportsPage"));
const CalendarPage = React.lazy(() => import("./pages/CalendarPage"));
const GanttPage = React.lazy(() => import("./pages/GanttPage"));
const SprintsPage = React.lazy(() => import("./pages/SprintsPage"));
const BacklogPage = React.lazy(() => import("./pages/BacklogPage"));
const RoadmapPage = React.lazy(() => import("./pages/RoadmapPage"));
const WorkloadPage = React.lazy(() => import("./pages/WorkloadPage"));
const FilesPage = React.lazy(() => import("./pages/FilesPage"));
const ClientPortalPage = React.lazy(() => import("./pages/ClientPortalPage"));
const AdminPage = React.lazy(() => import("./pages/AdminPage"));
const SettingsPage = React.lazy(() => import("./pages/SettingsPage"));
const SoftwarePlanningPage = React.lazy(() => import("./pages/SoftwarePlanningPage"));
const LiveWorkManagementPage = React.lazy(() => import("./pages/LiveWorkManagementPage"));
const ImpactWorkHubPage = React.lazy(() => import("./pages/ImpactWorkHubPage"));
const TimelineDependenciesPage = React.lazy(() => import("./pages/TimelineDependenciesPage"));
const AutomationAIPage = React.lazy(() => import("./pages/AutomationAIPage"));
const FormsPage = React.lazy(() => import("./pages/FormsPage"));
const CommandCenterPage = React.lazy(() => import("./pages/CommandCenterPage"));
const EnterpriseEnginePage = React.lazy(() => import("./pages/EnterpriseEnginePage"));
const ProductLaunchPage = React.lazy(() => import("./pages/ProductLaunchPage"));
const PMSOperationsPage = React.lazy(() => import("./pages/PMSOperationsPage"));
const PortfolioPage = React.lazy(() => import("./pages/PortfolioPage"));
const RisksPage = React.lazy(() => import("./pages/RisksPage"));
const ModuleProfilePage = React.lazy(() => import("@/pages/ModuleProfilePage"));

/**
 * KaryaFlow Routes
 * Complete routing for Project Management module
 */
const BatchWorkspacePage=React.lazy(()=>import("./pages/BatchWorkspacePage"));
const MyAssignmentsPage=React.lazy(()=>import("./pages/MyAssignmentsPage"));
const AssignmentControlsPage=React.lazy(()=>import("./pages/AssignmentControlsPage"));
const WorkReviewsPage = React.lazy(() => import("./pages/WorkReviewsPage"));
export const projectManagementRoutes: FrontendRoute[] = [
 {path:"pms/members",element:<MemberManagementPage/>},
 {path:"pms/projects/:projectId/members",element:<MemberManagementPage/>},
 {path:"pms/people",element:<PeopleDirectoryPage/>},
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
  { path: "pms/workspaces", element: <WorkspacesPage /> },
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
  { path: "pms/projects/new", element: <CreateProjectPage /> },
  { path: "pms/projects/:projectId/edit", element: <CreateProjectPage /> },
  
  // Project Dashboard & Views
  { path: "pms/projects/:projectId/billing", element: <ProjectBillingPage /> },
  { path: "pms/projects/:projectId", element: <ProjectDashboard /> },
  { path: "pms/projects/:projectId/board", element: <KanbanBoard /> },
  { path: "pms/projects/:projectId/timeline", element: <GanttPage /> },
  { path: "pms/projects/:projectId/gantt", element: <GanttPage /> },
  { path: "pms/projects/:projectId/milestones", element: <MilestonesPage /> },
  { path: "pms/projects/:projectId/files", element: <FilesPage /> },
  { path: "pms/projects/:projectId/reports", element: <ReportsPage /> },
  { path: "pms/projects/:projectId/risks", element: <RisksPage /> },
  
  // Tasks
  { path: "pms/tasks", element: <TaskListPage /> },
  { path: "pms/tasks/:taskId", element: <TaskDetail /> },
  { path: "pms/projects/:projectId/tasks/:taskId", element: <TaskDetail /> },

  // KaryaFlow software delivery workspaces
  { path: "pms/work-hub", element: <ImpactWorkHubPage /> },
  { path: "pms/impact", element: <ImpactWorkHubPage /> },
  { path: "pms/ai-planner", element: <AIOperatorPage /> },
  { path: "pms/timeline-plus", element: <TimelineDependenciesPage /> },
  { path: "pms/dependency-timeline", element: <TimelineDependenciesPage /> },
  { path: "pms/automation-ai", element: <AutomationAIPage /> },
  { path: "pms/software", element: <SoftwarePlanningPage /> },
  { path: "pms/live", element: <LiveWorkManagementPage /> },
  { path: "pms/teams-live", element: <LiveWorkManagementPage /> },
  { path: "pms/backlog", element: <BacklogPage /> },
  { path: "pms/issues", element: <SoftwarePlanningPage /> },
  { path: "pms/roadmap", element: <RoadmapPage /> },
  { path: "pms/workload", element: <WorkloadPage /> },
  { path: "pms/capacity", element: <WorkloadPage /> },
  { path: "pms/releases", element: <SoftwarePlanningPage /> },
  { path: "pms/automation", element: <AutomationAIPage /> },
  { path: "pms/goals", element: <CommandCenterPage /> },
  { path: "pms/forms", element: <FormsPage /> },
  { path: "pms/messages", element: <DirectMessagesPage /> },
  { path: "pms/custom-fields", element: <CustomFieldManagerPage /> },
  { path: "pms/teams", element: <TeamsPage /> },
  { path: "pms/org-chart", element: <OrgChartPage /> },
  { path: "pms/trash", element: <TrashPage /> },
  { path: "pms/templates", element: <CommandCenterPage /> },
  { path: "pms/components", element: <CommandCenterPage /> },
  { path: "pms/workflows", element: <CommandCenterPage /> },
  { path: "pms/security", element: <CommandCenterPage /> },
  { path: "pms/dependencies", element: <RoadmapPage /> },
  { path: "pms/navigator", element: <TaskListPage /> },
  { path: "pms/apps", element: <CommandCenterPage /> },
  { path: "pms/dashboards", element: <DashboardsPage /> },
  { path: "pms/docs", element: <DocsPage /> },
  { path: "pms/notes", element: <NotesPage /> },
  { path: "pms/projects/:projectId/notes", element: <NotesPage /> },
  { path: "pms/task-types", element: <TaskTypesPage /> },
  { path: "pms/tags", element: <TagManagerPage /> },
  { path: "pms/plans", element: <PlansPage /> },
  { path: "pms/issue-navigator-pro", element: <TaskListPage /> },
  { path: "pms/backlog-grooming", element: <BacklogPage /> },
  { path: "pms/sprint-lifecycle", element: <BacklogPage /> },
  { path: "pms/blueprints", element: <EnterpriseEnginePage /> },
  { path: "pms/resource-utilization", element: <WorkloadPage /> },
  
  // Module-level workspaces
  { path: "pms/calendar", element: <CalendarPage /> },
  { path: "pms/planner", element: <CalendarPage /> },
  { path: "pms/gantt", element: <GanttPage /> },
  { path: "pms/sprints", element: <SprintsPage /> },
  { path: "pms/files", element: <FilesPage /> },
  { path: "pms/time-tracking", element: <TimeTrackingPage /> },
  { path: "pms/timesheets", element: <TimesheetsPage /> },
  { path: "pms/reports", element: <ReportsPage /> },
  { path: "pms/client-portal", element: <ClientPortalPage /> },
  { path: "pms/settings", element: <SettingsPage /> },
  { path: "pms/admin", element: <AdminPage /> },
];

