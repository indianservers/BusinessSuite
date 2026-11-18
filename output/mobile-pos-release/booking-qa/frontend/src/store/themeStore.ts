import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "light" | "dark" | "system";
export const palettes = [
  { id: "violet", name: "Karya Violet", color: "258 70% 54%" },
  { id: "ocean", name: "Ocean Blue", color: "213 85% 43%" },
  { id: "forest", name: "Forest Green", color: "160 76% 29%" },
  { id: "rose", name: "Rose", color: "335 72% 43%" },
  { id: "sunset", name: "Sunset", color: "22 86% 37%" },
  { id: "slate", name: "Minimal Slate", color: "215 25% 35%" },
] as const;
export type Palette = (typeof palettes)[number]["id"];

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  density: "comfortable" | "compact";
  setDensity: (density: "comfortable" | "compact") => void;
  palette: Palette;
  setPalette: (palette: Palette) => void;
}

export function getResolvedTheme(theme: Theme) {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme) {
  const root = window.document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(getResolvedTheme(theme));
  root.style.colorScheme = getResolvedTheme(theme);
  root.dataset.palette = useThemeStore.getState().palette;
  root.dataset.density = useThemeStore.getState().density || "comfortable";
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "light",
      palette: "violet",
      density: "comfortable",
      setDensity: (density) => { set({density}); applyTheme(useThemeStore.getState().theme); },
      setPalette: (palette) => {
        if (!palettes.some((p) => p.id === palette)) return;
        set({ palette });
        applyTheme(useThemeStore.getState().theme);
      },
      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
    }),
    { name: "hrms-theme" }
  )
);
