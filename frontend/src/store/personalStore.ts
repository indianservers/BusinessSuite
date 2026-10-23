import { create } from "zustand";
import { persist } from "zustand/middleware";
export type PersonalPreferences = {
  status: string;
  availability: "available" | "away" | "busy";
  statusUntil: number;
  mutedUntil: number;
  notes: string;
  pins: string[];
};
export const defaultPersonal: PersonalPreferences = {
  status: "",
  availability: "available",
  statusUntil: 0,
  mutedUntil: 0,
  notes: "",
  pins: ["task", "work", "time"],
};
export const usePersonalStore = create<{
  users: Record<string, PersonalPreferences>;
  update: (id: number, patch: Partial<PersonalPreferences>) => void;
}>()(
  persist(
    (set) => ({
      users: {},
      update: (id, patch) =>
        set((state) => ({
          users: {
            ...state.users,
            [id]: { ...defaultPersonal, ...state.users[id], ...patch },
          },
        })),
    }),
    { name: "karyaflow-personal-preferences-v1" },
  ),
);
export function notificationsMuted(id?: number) {
  return (
    !!id &&
    (usePersonalStore.getState().users[id]?.mutedUntil || 0) > Date.now()
  );
}
