export type WorkspaceMember = { id: number; user_id: number; email: string; role: string };
export type WorkspaceProject = { id: number; name: string; project_key: string };
export type WorkTask = { id: number; project_id: number; task_key: string; title: string; description?: string; status: string; priority: string; assignee_user_id?: number | null; start_date?: string; due_date?: string; position: number; comments_count: number };
export const workspaceBase = "/project-management";
export const personName = (email: string) => email.split("@")[0].replace(/[._-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
export const tones = ["lilac", "mint", "peach", "blue", "rose"];
export const taskBucket = (s: string) => ["Done", "Completed", "Closed", "Resolved"].includes(s) ? "Done" : ["In Progress", "Blocked"].includes(s) ? "In Progress" : s === "In Review" ? s : "To Do";
export const workspaceError = (e: any) => typeof e.response?.data?.detail === "string" ? e.response.data.detail : Array.isArray(e.response?.data?.detail) ? e.response.data.detail.map((d: any) => d.msg).join(". ") : "Something went wrong. Please try again.";
