import type { WorkTask } from "./workspaceTypes";

export type WorkFocus = "all" | "overdue" | "today" | "blocked" | "unassigned" | "unscheduled";
export const workFocusOptions = [
  { id: "all", label: "All work" },
  { id: "overdue", label: "Overdue" },
  { id: "today", label: "Due today" },
  { id: "blocked", label: "Blocked" },
  { id: "unassigned", label: "Unassigned" },
  { id: "unscheduled", label: "Unscheduled" },
] as const;

export function localWorkDate(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function matchesWorkFocus(task: WorkTask, focus: WorkFocus, today = localWorkDate()): boolean {
  if (focus === "all") return true;
  // Cancelled work must not appear as outstanding, even though it has no done lane.
  if (["done", "completed", "closed", "resolved", "cancelled", "canceled"].includes(task.status.trim().toLowerCase())) return false;
  const due = task.due_date?.slice(0, 10);
  switch (focus) {
    case "overdue": return !!due && due < today;
    case "today": return due === today;
    case "blocked": return task.status.trim().toLowerCase() === "blocked";
    case "unassigned": return !(task.assignee_user_ids ?? (task.assignee_user_id ? [task.assignee_user_id] : [])).length;
    case "unscheduled": return !due;
  }
}
