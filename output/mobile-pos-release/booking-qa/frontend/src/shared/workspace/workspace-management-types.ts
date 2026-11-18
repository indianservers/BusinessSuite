import type { AuthUser } from "@/store/authStore";
export type WorkspaceModule = "pms" | "crm" | "hrms" | "srm" | "fam";
export type SavedWorkspace = { id: string; name: string; description: string; icon: string; color: string; visibility: "private" | "organization"; views: string[]; members: { user_id: number; role: "Admin" | "Member" | "Guest" }[]; member_details?: { user_id: number; role: string; email?: string }[]; owner_id?: number; owners?: string[]; role: string; version: number; status: "Active" | "Archived"; created_at?: string; updated_at?: string; member_count?: number; project_count?: number; task_count?: number; completed_task_count?: number; can_manage: boolean; can_archive: boolean };
export type WorkspaceDraft = Pick<SavedWorkspace, "name" | "description" | "icon" | "color" | "visibility" | "views" | "members" | "status"> & { expected_version?: number; expected_status?: "Active" | "Archived" };
export type WorkspaceActivity = { id: number | string; summary: string; actor?: string; created_at?: string };
export const workspaceApiBase = (module: WorkspaceModule) => `/${module === "pms" ? "project-management" : module}/workspace-directory`;

export function workspaceDataScope(user: AuthUser | null) {
  return JSON.stringify([user?.id, user?.access?.companyId, sessionStorage.getItem("suite-tenant"), sessionStorage.getItem("suite-organization"), sessionStorage.getItem("suite-branch"), user?.role, user?.is_superuser, user?.access?.companyDisabledModules, user?.access?.grants]);
}
export function workspaceSelectionKey(user: AuthUser | null, module: WorkspaceModule) {
  return `suite:workspace-selected:v1:${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-organization") || ""}:${sessionStorage.getItem("suite-branch") || ""}:${module}`;
}
