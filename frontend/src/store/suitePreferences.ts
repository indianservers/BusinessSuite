import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { safeSuiteDestination } from "@/lib/suiteNavigation";

export type SuitePreferences = {
  favorites: string[];
  recent: string[];
  compact: boolean;
  groups: Record<string, boolean>;
};
const defaults: SuitePreferences = {
  favorites: [],
  recent: [],
  compact: false,
  groups: {},
};
export const suiteScope = (userId?: number, companyId?: number) =>
  `${userId || 0}:${companyId || 0}`;
export const useSuitePreferences = create<{
  contexts: Record<string, SuitePreferences>;
  update: (scope: string, patch: Partial<SuitePreferences>) => void;
  visit: (scope: string, path: string) => void;
}>()(
  persist(
    (set) => ({
      contexts: {},
      update: (scope, patch) =>
        set((state) => ({
          contexts: {
            ...state.contexts,
            [scope]: { ...defaults, ...state.contexts[scope], ...patch },
          },
        })),
      visit: (scope, path) => {
        const safe = safeSuiteDestination(path);
        if (!safe) return;
        set((state) => {
          const current = state.contexts[scope] || defaults;
          if (current.recent[0] === safe) return state;
          return {
            contexts: {
              ...state.contexts,
              [scope]: {
                ...current,
                recent: [
                  safe,
                  ...current.recent.filter((p) => p !== safe),
                ].slice(0, 5),
              },
            },
          };
        });
      },
    }),
    {
      name: "suite-navigation-preferences-v1",
      storage: createJSONStorage(() => ({
        getItem: (key) => {
          try {
            return localStorage.getItem(key);
          } catch {
            return null;
          }
        },
        setItem: (key, value) => {
          try {
            localStorage.setItem(key, value);
          } catch {
            /* Preferences remain available for this visit. */
          }
        },
        removeItem: (key) => {
          try {
            localStorage.removeItem(key);
          } catch {
            /* Storage may be disabled. */
          }
        },
      })),
    },
  ),
);
export const defaultSuitePreferences = defaults;
