import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type PmsPage = { path: string; label: string };
type Navigation = { favorites: PmsPage[]; recent: PmsPage[]; visits: Record<string, number> };
export const emptyPmsNavigation: Navigation = { favorites: [], recent: [], visits: {} };
export const usePmsNavigation = create<{
  contexts: Record<string, Navigation>;
  visit: (scope: string, page: PmsPage, userId?: number) => void;
  pin: (scope: string, page: PmsPage) => void;
  move: (scope: string, path: string, direction: number) => void;
}>()(persist((set) => ({
  contexts: {},
  visit: (scope, page, userId) => set(state => {
    let current = state.contexts[scope];
    if (!current) {
      let legacy = emptyPmsNavigation;
      try {
        const saved = JSON.parse(localStorage.getItem(`kf-navigation-${userId}`) || "{}");
        const otherKnownCompany = Object.keys(state.contexts).some(key => key.startsWith(`${userId}:`) && key !== `${userId}:0`);
        if (!otherKnownCompany) legacy = state.contexts[`${userId}:0`] || { favorites: [], recent: Array.isArray(saved.recent) ? saved.recent.filter((p: PmsPage) => typeof p?.path === "string" && p.path.startsWith("/pms")) : [], visits: Object.fromEntries(Object.entries(saved.visits || {}).filter(([path, count]) => path.startsWith("/pms") && typeof count === "number" && count > 0)) as Record<string, number> };
      } catch { /* First visit or unavailable browser storage. */ }
      current = legacy;
    }
    if (current.recent[0]?.path === page.path) return state.contexts[scope] ? state : { contexts: { ...state.contexts, [scope]: current } };
    return { contexts: { ...state.contexts, [scope]: { ...current, recent: [page, ...current.recent.filter(p => p.path !== page.path)].slice(0, 20), visits: { ...current.visits, [page.path]: (current.visits[page.path] || 0) + 1 } } } };
  }),
  pin: (scope, page) => set(state => {
    const current = state.contexts[scope] || emptyPmsNavigation;
    return { contexts: { ...state.contexts, [scope]: { ...current, favorites: current.favorites.some(p => p.path === page.path) ? current.favorites.filter(p => p.path !== page.path) : [...current.favorites, page] } } };
  }),
  move: (scope, path, direction) => set(state => {
    const current = state.contexts[scope] || emptyPmsNavigation;
    const favorites = [...current.favorites], index = favorites.findIndex(p => p.path === path), next = index + direction;
    if (index < 0 || next < 0 || next >= favorites.length) return state;
    [favorites[index], favorites[next]] = [favorites[next], favorites[index]];
    return { contexts: { ...state.contexts, [scope]: { ...current, favorites } } };
  }),
}), { name: "pms-personal-navigation-v1", storage: createJSONStorage(() => ({
  getItem: key => { try { return localStorage.getItem(key); } catch { return null; } },
  setItem: (key, value) => { try { localStorage.setItem(key, value); } catch { /* Session preferences remain available. */ } },
  removeItem: key => { try { localStorage.removeItem(key); } catch { /* No persisted state. */ } },
})) }));
