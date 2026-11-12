export type WorkspaceMember = { id: number; user_id: number; email: string; role: string; name?: string; photo_url?: string; availability?: string };
export type WorkspaceProject = { id: number; name: string; project_key: string };
export type WorkTask = { updated_at?:string|null; work_type?:string; id: number; project_id: number; task_key: string; title: string; description?: string; status: string; priority: string; assignee_user_id?: number | null; assignee_user_ids?: number[]; estimated_hours?: number; start_date?: string|null; due_date?: string|null; position: number; comments_count: number };
export const workspaceBase = "/project-management";
export const personName = (email: string) => email.split("@")[0].replace(/[._-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
export const tones = ["lilac", "mint", "peach", "blue", "rose"];
export const taskBucket = (s: string) => ["Done", "Completed", "Closed", "Resolved"].includes(s) ? "Done" : ["In Progress", "Blocked"].includes(s) ? "In Progress" : s === "In Review" ? s : "To Do";
export function workspaceError(error: unknown): string {
  const fallback = "Something went wrong. Please try again.";
  if (!error || typeof error !== "object") return fallback;
  const e = error as {response?:{data?:{detail?:unknown}};code?:string;isAxiosError?:boolean;message?:string};
  const detail = e.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => item && typeof item.msg === "string" ? [item.msg] : []);
    if (messages.length) return messages.join(". ");
  }
  if (e.code === "ECONNABORTED" || e.code === "ETIMEDOUT") return "The server took too long to confirm. Refresh the workspace and check whether your changes were saved before trying again.";
  if (e.code === "ERR_NETWORK") return "Cannot reach the server. Check your connection, then refresh to confirm whether your changes were saved.";
  // Locally raised validation errors contain the recovery instruction the user needs.
  if (error instanceof Error && !e.isAxiosError && !e.response && e.message?.trim()) return e.message;
  return fallback;
}

export const taskAssignees = (task: { assignee_user_ids?: number[]; assignee_user_id?: number | null }) => task.assignee_user_ids ?? (task.assignee_user_id ? [task.assignee_user_id] : []);
