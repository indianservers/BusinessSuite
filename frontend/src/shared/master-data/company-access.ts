import type { AuthUser } from "@/store/authStore";

/** The same module permissions used by the shared master-data create endpoint. */
export function companyCreateAccess(user: AuthUser | null, source: string): boolean | undefined {
  if (!user) return false;
  if (user.access?.companyDisabledModules?.includes(source)) return false;
  if (user.is_superuser) return true;
  if (!user.access) return undefined;
  const grant = user.access.grants[source];
  const permissions: Record<string, string[]> = {
    crm: ["crm_manage", "crm_admin", "crm_companies_manage", "crm_accounts_manage"],
    srm: ["srm_manage", "srm_admin"],
    project_management: ["pms_manage_projects", "pms_admin"],
    hrms: ["employee_update", "employee_create"],
  };
  return Boolean(grant?.enabled && grant.actions.includes("create") &&
    grant.permissions.some(permission => permissions[source]?.includes(permission)));
}
