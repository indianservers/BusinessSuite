import { WorkIssues, workReleases, teamMembers, type WorkIssue } from "./workData";

export type EnterpriseIssue = WorkIssue & {
  initiative: string;
  parentKey?: string;
  component: string;
  severity?: "S1" | "S2" | "S3" | "S4";
  environment?: string;
  affectedVersion?: string;
  fixVersion?: string;
  regression?: boolean;
  originalEstimate: number;
  remainingEstimate: number;
  plannedStart: string;
  plannedEnd: string;
  rank: number;
  security: "Internal" | "Client Visible" | "Private";
  development: { branch?: string; commits: number; prs: number; deployments: number; build: "Passing" | "Failing" | "Pending" };
};

export type SavedView = {
  id: string;
  name: string;
  query: string;
  columns: string[];
  subscription: "None" | "Daily" | "Weekly";
};

const issueEnhancements = [
  { initiative: "Customer Experience", component: "Portal", severity: undefined, environment: "Production", affectedVersion: "v2.2", fixVersion: "v2.3", regression: false, start: "2026-05-08", end: "2026-05-22", remaining: 21 },
  { initiative: "Customer Experience", component: "Approvals", severity: undefined, environment: "Staging", affectedVersion: "v2.2", fixVersion: "v2.3", regression: false, start: "2026-05-07", end: "2026-05-13", remaining: 8 },
  { initiative: "Reliability", component: "Board", severity: "S1" as const, environment: "Production", affectedVersion: "v2.2.1", fixVersion: "v2.2.1", regression: true, start: "2026-05-06", end: "2026-05-10", remaining: 5 },
  { initiative: "Planning", component: "Timeline", severity: undefined, environment: "Staging", affectedVersion: "v2.3", fixVersion: "v2.4", regression: false, start: "2026-05-20", end: "2026-06-02", remaining: 13 },
  { initiative: "Admin Scale", component: "Import", severity: undefined, environment: "Dev", affectedVersion: "v2.3", fixVersion: "v2.4", regression: false, start: "2026-05-25", end: "2026-06-08", remaining: 16 },
  { initiative: "Automation", component: "Rules", severity: undefined, environment: "Staging", affectedVersion: "v2.2", fixVersion: "v2.3", regression: false, start: "2026-05-09", end: "2026-05-17", remaining: 9 },
  { initiative: "Reliability", component: "Calendar", severity: "S1" as const, environment: "Production", affectedVersion: "v2.2.1", fixVersion: "v2.2.1", regression: true, start: "2026-05-05", end: "2026-05-09", remaining: 2 },
  { initiative: "Reports", component: "Reports", severity: undefined, environment: "Production", affectedVersion: "v2.2", fixVersion: "v2.2", regression: false, start: "2026-04-26", end: "2026-05-02", remaining: 0 },
];

export const enterpriseIssues: EnterpriseIssue[] = WorkIssues.map((issue, index) => ({
  ...issue,
  initiative: issueEnhancements[index].initiative,
  parentKey: issue.type === "Sub-task" ? "KAR-101" : issue.type === "Epic" ? undefined : `EPIC-${issue.epic.toUpperCase().replace(/\s+/g, "-")}`,
  component: issueEnhancements[index].component,
  severity: issueEnhancements[index].severity,
  environment: issueEnhancements[index].environment,
  affectedVersion: issueEnhancements[index].affectedVersion,
  fixVersion: issueEnhancements[index].fixVersion,
  regression: issueEnhancements[index].regression,
  originalEstimate: issue.storyPoints * 6,
  remainingEstimate: issueEnhancements[index].remaining,
  plannedStart: issueEnhancements[index].start,
  plannedEnd: issueEnhancements[index].end,
  rank: index + 1,
  security: issue.priority === "Critical" ? "Internal" : issue.key === "KAR-102" ? "Client Visible" : "Private",
  development: {
    branch: issue.status === "Backlog" ? undefined : `feature/${issue.key.toLowerCase()}`,
    commits: (issue.id * 2) % 9,
    prs: issue.status === "In Review" || issue.status === "Done" ? 1 : 0,
    deployments: issue.status === "Done" ? 1 : 0,
    build: issue.priority === "Critical" ? "Failing" : issue.status === "Done" ? "Passing" : "Pending",
  },
}));

export const enterpriseDependencies = [
  { from: "KAR-103", to: "KAR-104", type: "blocks", lagDays: 2 },
  { from: "KAR-106", to: "KAR-102", type: "relates", lagDays: 0 },
  { from: "KAR-107", to: "KAR-103", type: "blocks", lagDays: 1 },
];

export const enterpriseSprints = [
  { id: "sprint-24", name: "Sprint 24", goal: "Stabilize approval and calendar workflows", status: "Active", start: "2026-05-06", end: "2026-05-20", committedPoints: 33, completedPoints: 3, scopeChanges: 2, carriedOver: ["KAR-103"], velocityHistory: [24, 28, 31, 33] },
  { id: "sprint-25", name: "Sprint 25", goal: "Release admin import and timeline planning", status: "Planned", start: "2026-05-21", end: "2026-06-04", committedPoints: 21, completedPoints: 0, scopeChanges: 0, carriedOver: [], velocityHistory: [28, 31, 33] },
];

export const enterpriseGoals = [
  { id: "goal-1", name: "Ship client approval workflow", target: "2026-05-31", issueKeys: ["KAR-101", "KAR-102", "KAR-106"], milestoneProgress: 70, release: "v2.3" },
  { id: "goal-2", name: "Reduce board and calendar defects", target: "2026-05-15", issueKeys: ["KAR-103", "KAR-107"], milestoneProgress: 42, release: "v2.2.1" },
  { id: "goal-3", name: "Improve planning operations", target: "2026-06-15", issueKeys: ["KAR-104", "KAR-105", "KAR-108"], milestoneProgress: 55, release: "v2.4" },
];

export const enterpriseReleases = workReleases.map((release) => ({
  ...release,
  fixVersions: enterpriseIssues.filter((issue) => issue.fixVersion === release.name).map((issue) => issue.key),
  readiness: release.status === "In Progress" ? 67 : release.status === "Planning" ? 48 : 22,
  notes: `${release.name} release includes ${release.issues} tracked work items and shared launch-date coordination.`,
  launchDateShared: true,
}));

export const workflowDefinitions = [
  { workType: "Bug", statuses: ["Triage", "Selected", "In Progress", "Fix Review", "Done"], validators: ["Severity required", "Affected version required"], postFunctions: ["Notify component lead", "Create regression test"], approvals: ["QA Lead"] },
  { workType: "Story", statuses: ["Backlog", "Selected", "In Progress", "In Review", "Done"], validators: ["Epic required", "Story points required"], postFunctions: ["Update epic rollup"], approvals: ["Product Owner"] },
  { workType: "Deliverable", statuses: ["Draft", "Submitted", "Client Review", "Approved", "Rejected"], validators: ["Client visibility required"], postFunctions: ["Notify client"], approvals: ["Client"] },
];

export const automationRules = [
  { name: "Critical bug escalation", trigger: "Issue created", condition: "type = Bug AND priority = Critical", action: "Notify manager and create incident task", executions: 6, lastRun: "4 min ago", active: true },
  { name: "Dependency unblocked", trigger: "Status changed to Done", condition: "has dependents", action: "Move dependents to Selected and notify owners", executions: 12, lastRun: "21 min ago", active: true },
  { name: "Missing estimate warning", trigger: "Sprint started", condition: "storyPoints is EMPTY", action: "Comment and assign to project manager", executions: 3, lastRun: "1 hour ago", active: true },
  { name: "Quote billable export", trigger: "Timesheet approved", condition: "billable = true", action: "Add line to invoice draft", executions: 18, lastRun: "Yesterday", active: false },
];

export const blueprintFlows = [
  { name: "Client deliverable approval", stages: ["Draft", "Internal review", "Client review", "Approved", "Invoice ready"], owner: "Maya Nair", sla: "5 business days" },
  { name: "Bug triage blueprint", stages: ["Submitted", "Severity check", "Assigned", "Fix review", "Regression test", "Closed"], owner: "Nora Khan", sla: "2 business days" },
  { name: "Project template launch", stages: ["Template selected", "Team assigned", "Board generated", "Automation enabled", "Kickoff"], owner: "Dev Patel", sla: "1 business day" },
];

export const budgetForecast = {
  planned: 180000,
  actual: 126500,
  billableApproved: 84200,
  resourceCost: 97100,
  forecastAtCompletion: 194400,
  margin: 0.23,
};

export const timesheetApprovals = [
  { user: "Maya Nair", week: "2026-W19", hours: 32, billable: 24, status: "Submitted", rejectionComment: "" },
  { user: "Dev Patel", week: "2026-W19", hours: 38, billable: 30, status: "Approved", rejectionComment: "" },
  { user: "Isha Rao", week: "2026-W19", hours: 29, billable: 18, status: "Rejected", rejectionComment: "Missing task notes for 4 hours." },
];

export const invoiceDrafts = [
  { id: "INV-DRAFT-104", client: "Apex Digital", source: "Approved billable timesheets", amount: 84200, status: "Ready to review" },
  { id: "INV-DRAFT-105", client: "BrightPath Academy", source: "Milestone approval", amount: 42000, status: "Waiting approval" },
];

export const resourceAllocations = teamMembers.map((member, index) => ({
  ...member,
  plannedHours: member.capacity,
  actualHours: member.capacity - 4 + index * 2,
  utilization: Math.round(((member.capacity - 4 + index * 2) / member.capacity) * 100),
  holidays: index === 3 ? 1 : 0,
}));

export const commentsThreads = [
  { issue: "KAR-102", pinned: true, visibility: "Client Visible", body: "@Maya Client approval copy is ready for review.", edits: 1, replies: 3 },
  { issue: "KAR-103", pinned: false, visibility: "Internal", body: "@Dev dependency reorder patch needs regression testing.", edits: 0, replies: 5 },
];

export const wikiPages = [
  { title: "Approval workflow specification", type: "Spec", owner: "Maya Nair", linked: "KAR-101" },
  { title: "Calendar defect decision log", type: "Decision", owner: "Nora Khan", linked: "KAR-107" },
  { title: "Sprint 24 learnings", type: "Retrospective", owner: "Rahul Shah", linked: "Sprint 24" },
];

export const intakeForms = [
  { name: "Bug intake", routesTo: "Triage", fields: ["Severity", "Environment", "Steps", "Affected version"], creates: "Bug" },
  { name: "Client deliverable request", routesTo: "Client review", fields: ["Client", "Due date", "Visibility"], creates: "Deliverable" },
  { name: "Feature idea", routesTo: "Product backlog", fields: ["Goal", "Impact", "Effort"], creates: "Story" },
];

export const fileVersions = [
  { file: "Approval-spec.pdf", versions: 4, visibility: "Client Visible", virusScan: "Clean", preview: "PDF", permission: "Project team + client" },
  { file: "Calendar-debug.mov", versions: 2, visibility: "Internal", virusScan: "Clean", preview: "Video", permission: "Engineers only" },
];

export const notificationPreferences = [
  { event: "Mention", inApp: true, email: true, digest: false },
  { event: "Due soon", inApp: true, email: false, digest: true },
  { event: "Assignment", inApp: true, email: true, digest: false },
  { event: "Status changed", inApp: true, email: false, digest: true },
];

export const adminSchemes = [
  { type: "Permission scheme", name: "Software delivery", controls: "Browse, edit, transition, comment, upload, administer" },
  { type: "Issue security", name: "Delivery visibility", controls: "Internal, client-visible, private" },
  { type: "Custom fields", name: "Delivery fields", controls: "Severity, environment, fix version, story points, customer impact" },
  { type: "Project template", name: "Client launch template", controls: "Boards, workflows, forms, roles, automations" },
  { type: "Marketplace app", name: "GitHub + Figma + Slack", controls: "Branches, designs, alerts, webhooks" },
];

export function runKQL(query: string, issues: EnterpriseIssue[] = enterpriseIssues) {
  const clauses = query
    .split(/\s+AND\s+/i)
    .map((part) => part.trim())
    .filter(Boolean);
  return issues.filter((issue) =>
    clauses.every((clause) => {
      const notEqual = clause.match(/^(\w+)\s*!=\s*(.+)$/i);
      const equal = clause.match(/^(\w+)\s*=\s*(.+)$/i);
      const contains = clause.match(/^text\s*~\s*"(.+)"$/i);
      if (contains) return `${issue.key} ${issue.summary} ${issue.component}`.toLowerCase().includes(contains[1].toLowerCase());
      const [, field, rawValue] = notEqual || equal || [];
      if (!field) return true;
      const expected = rawValue.replace(/^"|"$/g, "").trim();
      const actual = fieldValue(issue, field);
      return notEqual ? String(actual) !== expected : String(actual) === expected;
    }),
  );
}

function fieldValue(issue: EnterpriseIssue, field: string) {
  const normalized = field.toLowerCase();
  if (normalized === "type") return issue.type;
  if (normalized === "priority") return issue.priority;
  if (normalized === "status") return issue.status;
  if (normalized === "assignee") return issue.assignee;
  if (normalized === "sprint") return issue.sprint;
  if (normalized === "fixversion") return issue.fixVersion;
  if (normalized === "component") return issue.component;
  if (normalized === "security") return issue.security;
  return "";
}

export function calculateGoalProgress(goal: (typeof enterpriseGoals)[number], issues: EnterpriseIssue[] = enterpriseIssues) {
  const linked = issues.filter((issue) => goal.issueKeys.includes(issue.key));
  const totalPoints = linked.reduce((sum, issue) => sum + issue.storyPoints, 0) || 1;
  const donePoints = linked.filter((issue) => issue.status === "Done").reduce((sum, issue) => sum + issue.storyPoints, 0);
  const progress = Math.round((donePoints / totalPoints) * 70 + goal.milestoneProgress * 0.3);
  const status = progress >= 70 ? "On track" : progress >= 45 ? "At risk" : "Off track";
  return { linked, progress, status };
}

export function detectDependencyWarnings(issues: EnterpriseIssue[] = enterpriseIssues) {
  return enterpriseDependencies.map((dependency) => {
    const from = issues.find((issue) => issue.key === dependency.from);
    const to = issues.find((issue) => issue.key === dependency.to);
    const invalid = Boolean(from && to && from.status !== "Done" && new Date(to.plannedStart) <= new Date(from.plannedEnd));
    return {
      ...dependency,
      from,
      to,
      warning: invalid ? `${dependency.to} starts before blocker ${dependency.from} is done` : "No schedule conflict",
      critical: invalid && from?.priority === "Critical",
    };
  });
}

export function calculateReportDepth(issues: EnterpriseIssue[] = enterpriseIssues) {
  const total = issues.reduce((sum, issue) => sum + issue.storyPoints, 0);
  const done = issues.filter((issue) => issue.status === "Done").reduce((sum, issue) => sum + issue.storyPoints, 0);
  const remaining = total - done;
  return {
    burndown: `${remaining} pts remaining`,
    burnup: `${done}/${total} pts delivered`,
    velocity: `${Math.round(enterpriseSprints[0].velocityHistory.reduce((a, b) => a + b, 0) / enterpriseSprints[0].velocityHistory.length)} avg pts`,
    cumulativeFlow: `${issues.filter((issue) => issue.status === "In Review").length} in review`,
    controlChart: "3.8 days median cycle time",
    releaseBurndown: `${enterpriseReleases[1].readiness}% v2.3 readiness`,
    workload: `${resourceAllocations.filter((resource) => resource.utilization > 90).length} over-utilized`,
  };
}

export function recalculatePlan(delayIssueKey: string, delayDays: number, issues: EnterpriseIssue[] = enterpriseIssues) {
  return issues.map((issue) => {
    const blocked = enterpriseDependencies.some((dependency) => dependency.from === delayIssueKey && dependency.to === issue.key);
    if (!blocked) return issue;
    return { ...issue, plannedStart: shiftDate(issue.plannedStart, delayDays), plannedEnd: shiftDate(issue.plannedEnd, delayDays) };
  });
}

function shiftDate(value: string, days: number) {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export const defaultSavedViews: SavedView[] = [
  { id: "critical-bugs", name: "Critical bugs", query: "type = Bug AND priority = Critical AND status != Done", columns: ["key", "summary", "severity", "fixVersion", "assignee"], subscription: "Daily" },
  { id: "client-visible", name: "Client visible work", query: "security = Client Visible", columns: ["key", "summary", "status", "dueDate"], subscription: "Weekly" },
  { id: "v23-scope", name: "v2.3 release scope", query: "fixVersion = v2.3 AND status != Done", columns: ["key", "summary", "status", "storyPoints"], subscription: "None" },
];

