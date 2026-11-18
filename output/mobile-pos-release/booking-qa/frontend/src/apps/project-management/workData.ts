export type WorkIssue = {
  id: number;
  key: string;
  type: "Epic" | "Story" | "Task" | "Bug" | "Sub-task";
  summary: string;
  status: "Backlog" | "Selected" | "In Progress" | "In Review" | "Done";
  priority: "Low" | "Medium" | "High" | "Critical";
  assignee: string;
  reporter: string;
  storyPoints: number;
  sprint: string;
  epic: string;
  release: string;
  dueDate: string;
};

export const WorkIssues: WorkIssue[] = [
  { id: 1, key: "KAR-101", type: "Epic", summary: "Client portal approval workflow", status: "Selected", priority: "High", assignee: "Maya Nair", reporter: "Arjun Mehta", storyPoints: 13, sprint: "Sprint 24", epic: "Client Experience", release: "v2.3", dueDate: "2026-05-22" },
  { id: 2, key: "KAR-102", type: "Story", summary: "Submit milestone for client approval", status: "In Progress", priority: "High", assignee: "Isha Rao", reporter: "Maya Nair", storyPoints: 5, sprint: "Sprint 24", epic: "Client Experience", release: "v2.3", dueDate: "2026-05-13" },
  { id: 3, key: "KAR-103", type: "Bug", summary: "Blocked task count not updating after drag", status: "In Review", priority: "Critical", assignee: "Dev Patel", reporter: "Isha Rao", storyPoints: 3, sprint: "Sprint 24", epic: "Board Reliability", release: "v2.2.1", dueDate: "2026-05-10" },
  { id: 4, key: "KAR-104", type: "Story", summary: "Gantt dependency reschedule warning", status: "Backlog", priority: "Medium", assignee: "Nora Khan", reporter: "Maya Nair", storyPoints: 8, sprint: "Backlog", epic: "Planning", release: "v2.4", dueDate: "2026-06-02" },
  { id: 5, key: "KAR-105", type: "Task", summary: "Create CSV import mapping screen", status: "Backlog", priority: "Medium", assignee: "Rahul Shah", reporter: "Arjun Mehta", storyPoints: 5, sprint: "Backlog", epic: "Admin", release: "v2.4", dueDate: "2026-06-08" },
  { id: 6, key: "KAR-106", type: "Story", summary: "Automation rule: notify owner when task blocked", status: "Selected", priority: "High", assignee: "Dev Patel", reporter: "Maya Nair", storyPoints: 5, sprint: "Sprint 24", epic: "Automation", release: "v2.3", dueDate: "2026-05-17" },
  { id: 7, key: "KAR-107", type: "Bug", summary: "Calendar drag moves milestone by one day in IST", status: "In Progress", priority: "Critical", assignee: "Nora Khan", reporter: "Isha Rao", storyPoints: 2, sprint: "Sprint 24", epic: "Calendar", release: "v2.2.1", dueDate: "2026-05-09" },
  { id: 8, key: "KAR-108", type: "Story", summary: "Add saved filters for project risk views", status: "Done", priority: "Low", assignee: "Rahul Shah", reporter: "Maya Nair", storyPoints: 3, sprint: "Sprint 23", epic: "Reports", release: "v2.2", dueDate: "2026-05-02" },
];

export const workReleases = [
  { name: "v2.2.1", status: "In Progress", date: "2026-05-15", issues: 2, risk: "Critical bug fix release" },
  { name: "v2.3", status: "Planning", date: "2026-05-31", issues: 4, risk: "Client approval scope active" },
  { name: "v2.4", status: "Backlog", date: "2026-06-21", issues: 7, risk: "Dependency mapping pending" },
];

export const workAutomationRules = [
  { rule: "When issue moves to Blocked", trigger: "Status changed", action: "Notify project manager", status: "Active" },
  { rule: "When critical bug is created", trigger: "Issue created", action: "Create incident task", status: "Active" },
  { rule: "When PR merged", trigger: "Development event", action: "Move issue to In Review", status: "Active" },
  { rule: "When sprint ends", trigger: "Sprint completed", action: "Generate retrospective notes", status: "Draft" },
];

export const workReports = [
  { name: "Burndown", metric: "23 points remaining", status: "On track" },
  { name: "Velocity", metric: "31 avg points", status: "Stable" },
  { name: "Cumulative flow", metric: "Review queue rising", status: "Attention" },
  { name: "Cycle time", metric: "3.8 days median", status: "Good" },
  { name: "Deployment frequency", metric: "4/week", status: "Good" },
];

export const workGoals = [
  { goal: "Ship client approval workflow", owner: "Product", target: "2026-05-31", progress: "68%", linkedIssues: 12, status: "At Risk" },
  { goal: "Reduce cycle time below 4 days", owner: "Engineering", target: "2026-06-15", progress: "74%", linkedIssues: 9, status: "On Track" },
  { goal: "Close critical calendar defects", owner: "QA", target: "2026-05-12", progress: "50%", linkedIssues: 4, status: "At Risk" },
];

export const workForms = [
  { form: "Bug intake", fields: 9, routedTo: "Triage", sla: "1 business day", status: "Published" },
  { form: "Feature request", fields: 12, routedTo: "Product backlog", sla: "3 business days", status: "Published" },
  { form: "Access request", fields: 6, routedTo: "Admin queue", sla: "4 hours", status: "Draft" },
];

export const workTemplates = [
  { template: "Scrum software project", includes: "Backlog, sprint board, reports", status: "Ready" },
  { template: "Kanban software project", includes: "Continuous board, WIP, control chart", status: "Ready" },
  { template: "Bug tracking project", includes: "Triage workflow, severity fields", status: "Ready" },
  { template: "Cross-functional launch", includes: "Timeline, dependencies, approvals", status: "Ready" },
];

export const workComponents = [
  { component: "Frontend", lead: "Nora Khan", defaultAssignee: "Component lead", openIssues: 9 },
  { component: "API", lead: "Dev Patel", defaultAssignee: "Component lead", openIssues: 7 },
  { component: "Calendar", lead: "Isha Rao", defaultAssignee: "Project default", openIssues: 4 },
  { component: "Reports", lead: "Rahul Shah", defaultAssignee: "Unassigned", openIssues: 5 },
];

export const workWorkflowSchemes = [
  { workType: "Bug", workflow: "Triage -> In Progress -> Fix Review -> Done", requiredFields: "Severity, component", status: "Active" },
  { workType: "Story", workflow: "Backlog -> Selected -> In Progress -> Review -> Done", requiredFields: "Epic, story points", status: "Active" },
  { workType: "Approval", workflow: "Draft -> Submitted -> Approved/Rejected", requiredFields: "Approver, due date", status: "Draft" },
];

export const workSecurityRows = [
  { scheme: "Project roles", scope: "Admin, Manager, Member, Viewer, Client", status: "Active" },
  { scheme: "Issue security", scope: "Internal, client-visible, private", status: "Active" },
  { scheme: "Notification scheme", scope: "Created, assigned, mentioned, resolved", status: "Active" },
  { scheme: "Permission scheme", scope: "Browse, edit, transition, comment, administer", status: "Active" },
];

export const workAdvancedPlanning = [
  { plan: "Team capacity", signal: "Maya team over capacity by 18%", action: "Move 5 pts to next sprint" },
  { plan: "Dependency map", signal: "KAR-104 blocked by KAR-103", action: "Prioritize critical bug" },
  { plan: "Scenario planning", signal: "v2.3 slips 4 days if QA stays fixed", action: "Add reviewer or reduce scope" },
  { plan: "Cross-project roadmap", signal: "Project release dates overlap", action: "Stagger launch comms" },
];

export const workNavigatorFilters = [
  { name: "Critical open bugs", query: "type = Bug AND priority = Critical AND status != Done", count: 2 },
  { name: "My sprint work", query: "assignee = currentUser() AND sprint = Sprint 24", count: 4 },
  { name: "Unreleased v2.3 scope", query: "fixVersion = v2.3 AND status != Done", count: 5 },
  { name: "No estimate", query: "storyPoints is EMPTY AND sprint != Backlog", count: 3 },
];

export const teamMembers = [
  { id: 1, name: "Maya Nair", role: "Project Manager", team: "Delivery", capacity: 34 },
  { id: 2, name: "Dev Patel", role: "Backend Engineer", team: "Platform", capacity: 28 },
  { id: 3, name: "Isha Rao", role: "Frontend Engineer", team: "Experience", capacity: 30 },
  { id: 4, name: "Nora Khan", role: "QA Lead", team: "Quality", capacity: 24 },
  { id: 5, name: "Rahul Shah", role: "Analyst", team: "Delivery", capacity: 20 },
];

export const projectStatusCards = [
  { id: 1, name: "Client Portal Upgrade", status: "Planned", manager: "Maya Nair", health: "Good", progress: 22 },
  { id: 2, name: "Calendar Reliability", status: "Active", manager: "Nora Khan", health: "At Risk", progress: 61 },
  { id: 3, name: "Reports Redesign", status: "Active", manager: "Rahul Shah", health: "Good", progress: 48 },
  { id: 4, name: "Automation Rules", status: "On Hold", manager: "Dev Patel", health: "Blocked", progress: 36 },
  { id: 5, name: "Mobile App Delivery", status: "Completed", manager: "Isha Rao", health: "Good", progress: 100 },
];

export const ticketCards = [
  { id: 1, key: "SUP-201", title: "Client cannot approve milestone", status: "Open", priority: "Critical", owner: "Nora Khan" },
  { id: 2, key: "SUP-202", title: "Time log export missing billable flag", status: "In Progress", priority: "High", owner: "Rahul Shah" },
  { id: 3, key: "SUP-203", title: "Invite email copy needs update", status: "Waiting", priority: "Medium", owner: "Maya Nair" },
  { id: 4, key: "SUP-204", title: "Shared file download permission", status: "Resolved", priority: "High", owner: "Dev Patel" },
];

export const timelineItems = [
  { id: 1, key: "TBT-1", title: "Campaign strategy", owner: "Maya Nair", start: 0, span: 0, color: "bg-slate-600", done: false },
  { id: 2, key: "TBT-11", title: "Budget planning", owner: "Dev Patel", start: 28, span: 34, color: "bg-blue-700", done: true },
  { id: 3, key: "TBT-13", title: "Content calendar", owner: "Isha Rao", start: 42, span: 42, color: "bg-green-700", done: true },
  { id: 4, key: "TBT-14", title: "Asset creation", owner: "Nora Khan", start: 44, span: 30, color: "bg-green-700", done: true },
  { id: 5, key: "TBT-3", title: "Launch landing page", owner: "Rahul Shah", start: 66, span: 38, color: "bg-violet-700", done: false },
  { id: 6, key: "TBT-35", title: "Align web campaign", owner: "Maya Nair", start: 12, span: 22, color: "bg-green-700", done: true },
  { id: 7, key: "TBT-36", title: "Plan launch timing", owner: "Dev Patel", start: 74, span: 20, color: "bg-blue-700", done: false },
];

export const dependencyLinks = [
  { from: "TBT-14", to: "TBT-3", type: "blocks", offset: 48 },
  { from: "TBT-35", to: "TBT-36", type: "blocks", offset: 72 },
];

export const automationTemplates = [
  { title: "Transition linked issues", description: "When a blocker is completed, move dependent work to ready.", category: "Workflow" },
  { title: "Create new issues", description: "Create subtasks from a request form and assign by component.", category: "Issue ops" },
  { title: "Email ticket owners", description: "Notify owners when a ticket is close to SLA breach.", category: "Support" },
  { title: "Release notes", description: "Create release notes in Confluence when epic is ready.", category: "Release" },
  { title: "Slack release update", description: "Send a Slack message when a version is released.", category: "Integrations" },
  { title: "Due date by priority", description: "Set due date based on severity when a bug is created.", category: "Planning" },
];

export const automationAuditRows = [
  { rule: "Critical bug escalation", actor: "System", result: "Created incident task", time: "2 min ago" },
  { rule: "PR merged transition", actor: "GitHub", result: "Moved KAR-103 to In Review", time: "18 min ago" },
  { rule: "Quote expiry reminder", actor: "Scheduler", result: "Notified owner", time: "1 hour ago" },
];

