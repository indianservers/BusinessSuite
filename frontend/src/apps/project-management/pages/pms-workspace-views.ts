import { FolderKanban, Layers3, ListTodo, Users, CalendarDays, Activity, Settings2 } from "lucide-react";
export const pmsWorkspaceViews = [
  { id: "projects", label: "Projects", href: "/pms/projects", icon: FolderKanban, description: "Portfolio, delivery health and milestones" },
  { id: "tasks", label: "Tasks", href: "/pms/tasks", icon: ListTodo, description: "Task execution and assignments" },
  { id: "board", label: "Board", href: "/pms/workspaces?view=board", icon: Layers3, description: "Existing workspace board and list views" },
  { id: "timeline", label: "Timeline", href: "/pms/gantt", icon: CalendarDays, description: "Schedules and dependencies" },
  { id: "workload", label: "Workload", href: "/pms/workspaces?view=workload", icon: Users, description: "Capacity and availability" },
  { id: "team", label: "People", href: "/pms/people", icon: Users, description: "People, roles and handovers" },
  { id: "activity", label: "Activity", href: "/pms/workspaces?view=activity", icon: Activity, description: "Workspace activity and delivery views" },
  { id: "settings", label: "Project settings", href: "/pms/settings", icon: Settings2, description: "Existing project configuration" },
];
