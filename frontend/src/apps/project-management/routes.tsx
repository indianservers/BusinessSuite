import React from "react";
import type { FrontendRoute } from "@/appRegistry";

// Lazy load components
const ProjectManagementHomePage = React.lazy(() => import("./ProjectManagementHomePage"));
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
export const projectManagementRoutes: FrontendRoute[] = [
  // Home / Dashboard
  { path: "pms", element: <ProjectManagementHomePage /> },
  { path: "pms/profile", element: <ModuleProfilePage /> },
  { path: "pms/command-center", element: <CommandCenterPage /> },
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
  
  // Project Dashboard & Views
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
  { path: "pms/ai-planner", element: <ImpactWorkHubPage /> },
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
  { path: "pms/forms", element: <CommandCenterPage /> },
  { path: "pms/templates", element: <CommandCenterPage /> },
  { path: "pms/components", element: <CommandCenterPage /> },
  { path: "pms/workflows", element: <CommandCenterPage /> },
  { path: "pms/security", element: <CommandCenterPage /> },
  { path: "pms/dependencies", element: <CommandCenterPage /> },
  { path: "pms/navigator", element: <CommandCenterPage /> },
  { path: "pms/apps", element: <CommandCenterPage /> },
  { path: "pms/dashboards", element: <CommandCenterPage /> },
  { path: "pms/plans", element: <CommandCenterPage /> },
  { path: "pms/issue-navigator-pro", element: <EnterpriseEnginePage /> },
  { path: "pms/backlog-grooming", element: <EnterpriseEnginePage /> },
  { path: "pms/sprint-lifecycle", element: <EnterpriseEnginePage /> },
  { path: "pms/blueprints", element: <EnterpriseEnginePage /> },
  { path: "pms/resource-utilization", element: <EnterpriseEnginePage /> },
  
  // Module-level workspaces
  { path: "pms/calendar", element: <CalendarPage /> },
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

