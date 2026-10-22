import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

// Keep accounts independent across tabs, including after a reload. Move an
// existing browser-wide session once so an upgrade does not sign its user out.
const authStorage = createJSONStorage(() => {
  const key = "hrms-auth";
  const previous = localStorage.getItem(key);
  if (!sessionStorage.getItem(key) && previous) sessionStorage.setItem(key, previous);
  if (previous) localStorage.removeItem(key);
  return sessionStorage;
});

export interface AuthUser {
  id: number;
  email: string;
  name?: string | null;
  role: string | null;
  is_superuser: boolean;
  employee_id?: number | null;
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

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),
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
