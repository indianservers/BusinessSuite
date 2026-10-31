import { api } from "@/services/api";
export const directoryRoot = "/project-management/people-workspace";
export type DirectoryPerson = {
  id: number;
  name: string;
  email: string;
  role: string;
  classification: string;
  status: string;
  employment_status?: string;
  projects?: { id: number; name: string }[];
  workspaces?: { id: number; name: string }[];
  photo_url?: string | null;
  employee_code?: string;
  department?: string;
  skills: string[];
  teams: { id: number; name: string; workspace_id: number }[];
  batches: { id: number; name: string }[];
  registered_at: string;
  can_manage: boolean;
};
export type DirectoryPage = {
  items: DirectoryPerson[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
export type Group = {
  id: number;
  name: string;
  members: number;
  workspace_id?: number;
  project_id?: number;
  avatars?: DirectoryPerson[];
  status?: string;
  start_date?: string;
  end_date?: string;
  can_manage?: boolean;
};
export type GroupPage = {
  items: Group[];
  total: number;
  page: number;
  pages: number;
};
export type DirectoryReference = {
  stats: {
    total: number;
    active: number;
    inactive: number;
    teams: number;
    batches: number;
  };
  roles: string[];
  departments: { id: number; name: string }[];
  workspaces: { id: number; name: string; can_manage: boolean }[];
  organizations: { id: number; name: string }[];
  can_create_user: boolean;
  can_export: boolean;
  can_manage_batches: boolean;
  can_manage_people: boolean;
};
export const directoryGet = async <T>(
  path: string,
  params?: Record<string, unknown>,
) => (await api.get<T>(directoryRoot + path, { params })).data;
export const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((value) => value[0])
    .join("")
    .toUpperCase();
export const csvEscape = (value: string) => {
  const safe = /^[=+@\-\t\r]/.test(value) ? "'" + value : value;
  return '"' + safe.replace(/"/g, '""') + '"';
};

export function directoryTaskHref(
  kind: "people" | "teams" | "batches",
  ids: number[],
) {
  return `/pms/tasks/new?${new URLSearchParams({ [kind]: ids.join(",") })}`;
}
