import type React from "react";

export type FrontendAppKey =
  | "hrms"
  | "crm"
  | "project_management"
  | "srm"
  | "fam"
  | "ai"
  | "portals"
  | "communication";

export type FrontendRoute = {
  path: string;
  element: React.ReactNode;
  caseSensitive?: boolean;
};

export type FrontendAppModule = {
  key: FrontendAppKey;
  label: string;
  basePath: string;
  routes: FrontendRoute[];
};

const rawInstalledApps =
  import.meta.env.VITE_INSTALLED_APPS || "hrms,crm,project_management,srm,fam,ai,portals,communication";
const validAppKeys: FrontendAppKey[] = [
  "hrms",
  "crm",
  "project_management",
  "srm",
  "fam",
  "ai",
  "portals",
  "communication",
];
const storageKey = "bos-enabled-modules";

export function normalizeAppKey(value: string) {
  return value.trim().toLowerCase().replace(/-/g, "_");
}

export function getInstalledAppKeys(): FrontendAppKey[] {
  const raw = typeof window !== "undefined" ? window.localStorage.getItem(storageKey) || rawInstalledApps : rawInstalledApps;
  return raw
    .split(",")
    .map(normalizeAppKey)
    .filter((key: string): key is FrontendAppKey => validAppKeys.includes(key as FrontendAppKey));
}

export function setBusinessOsEnabledModules(moduleKeys: string[]) {
  const normalized = moduleKeys
    .map(normalizeAppKey)
    .filter((key: string): key is FrontendAppKey => validAppKeys.includes(key as FrontendAppKey));
  window.localStorage.setItem(storageKey, normalized.join(","));
  window.dispatchEvent(new CustomEvent("business-os-modules-changed", { detail: normalized }));
}

export function isFrontendModuleEnabled(moduleKey: string) {
  return getInstalledAppKeys().includes(normalizeAppKey(moduleKey) as FrontendAppKey);
}
