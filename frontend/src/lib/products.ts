export type ProductKey = "hrms" | "crm" | "project_management" | "srm" | "fam" | "inventory";

export type ProductMeta = {
  key: ProductKey;
  name: string;
  shortName: string;
  loginPath: string;
  homePath: string;
  themeClass: string;
  searchPlaceholder: string;
};

export const products: Record<ProductKey, ProductMeta> = {
  hrms: {
    key: "hrms",
    name: "AI HRMS",
    shortName: "HRMS",
    loginPath: "/hrms/login",
    homePath: "/hrms",
    themeClass: "product-hrms",
    searchPlaceholder: "Search employees, payroll, policies...  Cmd+K",
  },
  crm: {
    key: "crm",
    name: "VyaparaCRM",
    shortName: "CRM",
    loginPath: "/crm/login",
    homePath: "/crm",
    themeClass: "product-crm",
    searchPlaceholder: "Search leads, deals, contacts...  Cmd+K",
  },
  project_management: {
    key: "project_management",
    name: "KaryaFlow PMS",
    shortName: "PMS",
    loginPath: "/pms/login",
    homePath: "/pms",
    themeClass: "product-pms",
    searchPlaceholder: "Search projects, issues, sprints...  Cmd+K",
  },
  srm: {
    key: "srm",
    name: "RevenueFlow SRM",
    shortName: "SRM",
    loginPath: "/srm/login",
    homePath: "/srm",
    themeClass: "product-srm",
    searchPlaceholder: "Search orders, invoices, collections...  Cmd+K",
  },
  fam: {
    key: "fam",
    name: "FinanceFlow FAM",
    shortName: "FAM",
    loginPath: "/fam/login",
    homePath: "/fam",
    themeClass: "product-fam",
    searchPlaceholder: "Search ledgers, groups, balances...  Cmd+K",
  },
  inventory: {
    key: "inventory",
    name: "Vyapara ERP Inventory",
    shortName: "Inventory",
    loginPath: "/login",
    homePath: "/Inventory",
    themeClass: "product-inventory",
    searchPlaceholder: "Search products, stock, invoices...  Cmd+K",
  },
};

export function normalizeRole(role?: string | null) {
  return (role || "").toLowerCase().replace(/\s+/g, "_");
}

export function getProductKeyFromPath(pathname: string): ProductKey | null {
  const normalizedPathname = pathname.toLowerCase();
  if (pathname.startsWith("/crm")) return "crm";
  if (pathname.startsWith("/pms")) return "project_management";
  if (pathname.startsWith("/srm")) return "srm";
  if (pathname.startsWith("/fam")) return "fam";
  if (normalizedPathname.startsWith("/inventory")) return "inventory";
  if (pathname.startsWith("/hrms")) return "hrms";
  return null;
}

export function getProductKeyForRole(role?: string | null, isSuperuser = false): ProductKey {
  const value = normalizeRole(role);
  if (value.startsWith("crm_")) return "crm";
  if (value.startsWith("pms_")) return "project_management";
  if (value.startsWith("srm_")) return "srm";
  if (value.startsWith("fam_") || ["accountant", "auditor"].includes(value)) return "fam";
  if (isSuperuser || value) return "hrms";
  return "hrms";
}

export function getProductForContext(pathname: string, role?: string | null, isSuperuser = false) {
  return products[getProductKeyFromPath(pathname) || getProductKeyForRole(role, isSuperuser)];
}

export function getDefaultPathForUser(role?: string | null, isSuperuser = false) {
  const value = normalizeRole(role);
  const productKey = getProductKeyForRole(role, isSuperuser);

  if (productKey !== "hrms") return products[productKey].homePath;
  if (isSuperuser || ["super_admin", "admin"].includes(value)) return "/hrms/admin-home";
  if (["hr_manager", "hr_admin", "hr", "hr_company_admin", "hr_workflow_admin", "hr_custom_field_admin"].includes(value)) return "/hrms/hr-home";
  if (["ceo", "founder", "director", "executive"].includes(value)) return "/hrms/executive-home";
  if (["manager", "team_lead", "department_head"].includes(value)) return "/hrms/manager-dashboard";
  if (value === "employee") return "/hrms/ess";

  return products[productKey].homePath;
}

export function getLoginPathForContext(pathname: string, role?: string | null, isSuperuser = false) {
  const productKey = getProductKeyFromPath(pathname) || getProductKeyForRole(role, isSuperuser);
  return products[productKey].loginPath;
}
