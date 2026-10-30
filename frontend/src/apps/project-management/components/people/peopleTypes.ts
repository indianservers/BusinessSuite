import { create } from "zustand";
export const peopleBase = "/project-management/people-management";
export type Person = { id: number; user_id?: number; name: string; email: string; role: string; status: "active" | "suspended" | "terminated" | "invited"; photo_url?: string | null; availability?: string; workspace_id?: number; workspace?: string };
export type Membership = { id: number; workspace_id?: number; project_id?: number; name: string; role: string; source?: string; can_remove?: boolean; unavailable_reason?: string };
export type Destinations = { workspaces: { id: number; name: string; role: string; can_appoint_admin: boolean }[]; projects: { id: number; name: string; project_key?: string; workspace_id?: number }[]; organization_admin: boolean };
export type Context = { userId: number; workspaceId?: number; projectId?: number };
export const usePersonManagement = create<{ context?: Context; open: (context: Context) => void; close: () => void }>(set => ({ context: undefined, open: context => set({ context }), close: () => set({ context: undefined }) }));
export function openPerson(context: Context) { usePersonManagement.getState().open(context); }
export function peopleChanged() { window.dispatchEvent(new Event("pms:people-changed")); }
