/** Integration references, not standalone copies of Suite records or schemas. */
export const productivityReferences = [
  {
    id: "calendar", name: "Calendar", icon: "CalendarDays", route: "/pms/calendar",
    description: "Calendar views with application-owned events, scheduling and access rules.",
    source: "frontend/src/apps/project-management/pages/CalendarPage.tsx",
    integration: ["Map application records to events and retain original record identifiers.", "Supply timezone, date ranges, visibility, scheduling and conflict rules.", "Connect event actions, reminders and linked records through the host API."],
    preserve: "Suite task dates, project links, calendar settings and scheduling behavior remain owned by PMS.",
  },
  {
    id: "notes", name: "Notes", icon: "FileText", route: "/pms/notes",
    description: "Rich notes and notebook presentation with application-owned persistence.",
    source: "frontend/src/shared/productivity/NotesWorkspace.tsx",
    integration: ["Reuse NoteEditor for controlled editing or NotesWorkspace for browser-local notebooks.", "Provide attachment and reference callbacks plus application-specific persistence.", "Scope browser drafts by application, company, branch and user; remount when scope changes."],
    preserve: "PMS private notes, project/task references, attachment authorization and API persistence stay in PMS adapters.",
  },
  {
    id: "tasks", name: "Tasks", icon: "ClipboardList", route: "/pms/tasks",
    description: "Task workspace reference with application-specific columns and actions.",
    source: "frontend/src/apps/project-management/pages/TaskExperiencePage.tsx",
    integration: ["Map the host task model explicitly, including statuses, assignments and related records.", "Supply columns, saved views, filters and actions for the receiving application.", "Integrate creation, review, dependencies, notifications and realtime updates with host services."],
    preserve: "Existing PMS columns, custom fields, assignment/review rules, saved views and business integrations remain unchanged.",
  },
  {
    id: "workflow-automation", name: "Workflow Automation", icon: "Workflow", route: "/pms/workflows",
    description: "Workflow reference with explicit host triggers, conditions and authorized actions.",
    source: "frontend/src/apps/project-management/pages/CommandCenterPage.tsx",
    integration: ["Register the receiving application's triggers, event payloads, conditions and actions.", "Enforce host permissions, tenant scope, approvals and credential access on the server.", "Connect execution, retry/idempotency rules and audit history before enabling workflows."],
    preserve: "PMS workflow subscriptions and Suite actions remain in their existing services; references install no subscriptions.",
  },
] as const;

export type ProductivityReferenceId = typeof productivityReferences[number]["id"];

/** Hosts keep their full record and column types; no normalized PMS schema is imposed. */
export interface ProductivityIntegration<RecordType, ColumnType, ActionType> {
  reference: ProductivityReferenceId;
  scope: { application: string; companyId: string; branchId: string; userId: string };
  records: readonly RecordType[];
  columns: readonly ColumnType[];
  actions: readonly ActionType[];
  getRecordId: (record: RecordType) => string;
  canPerform: (action: ActionType, record: RecordType) => boolean;
}
