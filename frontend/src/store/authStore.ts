import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

// Keep accounts independent across tabs, including after a reload. Move an
// existing browser-wide session once so an upgrade does not sign its user out.
export function setRememberSession(remember: boolean) {
  localStorage.setItem("suite-remember-session", String(remember));
  if (!remember) localStorage.removeItem("suite-remembered-auth");
  else { const current = sessionStorage.getItem("hrms-auth"); if (current) localStorage.setItem("suite-remembered-auth", current); }
}
const authStorage = createJSONStorage(() => ({
  getItem: (key: string) => {
    const legacy = localStorage.getItem(key);
    if (legacy) { if (!sessionStorage.getItem(key)) sessionStorage.setItem(key, legacy); localStorage.removeItem(key); }
    return sessionStorage.getItem(key) || (localStorage.getItem("suite-remember-session") === "true" ? localStorage.getItem("suite-remembered-auth") : null);
  },
  setItem: (key: string, value: string) => {
    sessionStorage.setItem(key, value);
    if (localStorage.getItem("suite-remember-session") === "true") localStorage.setItem("suite-remembered-auth", value);
  },
  removeItem: (key: string) => { sessionStorage.removeItem(key); localStorage.removeItem("suite-remembered-auth"); },
}));

export interface AuthUser {
  id: number;
  email: string;
  name?: string | null;
  role: string | null;
  primary_role?: string | null;
  is_superuser: boolean;
  employee_id?: number | null;
  access?: { managed: boolean; companyId: number; grants: Record<string, { enabled: boolean; role: string; scope: string; permissions: string[]; actions: string[] }>; modules: { key: string; route: string; label: string; navigationPaths?: string[] }[]; isAccessAdmin: boolean; isGlobalAdmin: boolean; memberships: number[] };
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
  setHydrated: (isHydrated: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      isHydrated: false,

      setTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken, isAuthenticated: true }),

      setUser: (user) => set({ user }),
      setHydrated: (isHydrated) => set({ isHydrated }),

      logout: () => {
        sessionStorage.removeItem("suite-organization");
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        });
      },
      }),
    {
      name: "hrms-auth",
      storage: authStorage,
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
