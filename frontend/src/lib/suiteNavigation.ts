import { modules } from "./moduleCatalog";

/** Accept only known, same-origin application paths, never auth/reset URLs. */
export function safeSuiteDestination(
  value: string | null | undefined,
): string | null {
  if (
    !value ||
    !value.startsWith("/") ||
    /[\\\s]/.test(value) ||
    value.startsWith("//") ||
    [...value].some(
      (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
    )
  )
    return null;
  try {
    const url = new URL(value, "https://suite.invalid");
    const decoded = decodeURIComponent(url.pathname);
    if (
      url.origin !== "https://suite.invalid" ||
      /[\\\s]/.test(decoded) ||
      decoded.startsWith("//") ||
      [...decoded].some(
        (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
      )
    )
      return null;
    const known = [
      "/dashboard",
      "/account",
      "/notifications",
      "/help",
      ...modules.map((m) => m.homePath),
    ];
    if (
      !known.some(
        (path) =>
          url.pathname === path ||
          (modules.some((m) => m.homePath === path) &&
            url.pathname.startsWith(path + "/")),
      )
    )
      return null;
    if (/\/(login|reset-password)(\/|$)/.test(decoded)) return null;
    return url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

export function suitePageLabel(path: string) {
  const module = modules.find(
    (m) => path === m.homePath || path.startsWith(m.homePath + "/"),
  );
  const segments = path.split("?")[0].split("/").filter(Boolean);
  const tail = segments
    .slice(1)
    .map((part) =>
      part
        .replace(/-/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase()),
    )
    .join(" / ");
  return module
    ? `${module.name}${tail ? ` · ${tail}` : ""}`
    : "All applications";
}

export const moduleFeaturePaths: Record<string, Record<string, string>> = {
  power_apps: {
    Apps: "/power-apps/app-builder",
    Approvals: "/power-apps/approvals",
    Automations: "/power-apps/automations",
  },
  hrms: {
    People: "/hrms/employees",
    Payroll: "/hrms/payroll",
    Attendance: "/hrms/attendance",
  },
  crm: { Leads: "/crm/leads", Deals: "/crm/deals", Customers: "/crm/contacts" },
  pms: { Projects: "/pms/projects", Tasks: "/pms/tasks", Teams: "/pms/teams" },
  srm: {
    Orders: "/srm/sales-orders",
    Stock: "/srm/inventory",
    POS: "/srm/pos",
  },
  fam: {
    Invoices: "/fam/ar",
    Ledgers: "/fam/ledgers",
    Reports: "/fam/day-book",
  },
};
