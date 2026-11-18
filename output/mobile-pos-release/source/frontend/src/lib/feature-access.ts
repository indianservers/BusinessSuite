import type { AuthUser } from "@/store/authStore";

/** Match a shared feature's native module grant, rather than its host app URL. */
export function canUseFeature(user: {access?:AuthUser["access"];is_superuser?:boolean}|null|undefined, module: string, permission?: string) {
  if(user?.access?.companyDisabledModules?.includes(module))return false;
  if(user?.is_superuser || !user?.access)return true;
  const grant=user.access.grants[module];
  return Boolean(grant?.enabled && grant.actions.includes("view") && (permission ? grant.permissions.includes(permission) : grant.permissions.length>0));
}
