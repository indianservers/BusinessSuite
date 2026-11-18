import type { AuthUser } from "@/store/authStore";

const canonical = (value: unknown): unknown => value === undefined ? null : Array.isArray(value)
  ? value.map(canonical).sort((a,b)=>(JSON.stringify(a) ?? "").localeCompare(JSON.stringify(b) ?? ""))
  : value && typeof value === "object" ? Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)])) : value;
const fields = (source: Record<string, unknown> | undefined, names: string[]) => Object.fromEntries(names.map(key=>[key,source?.[key] ?? null]));
/** Cache ownership only: never grants authority. Excludes presentation labels/defaults. */
export function securityAuthStamp(user: AuthUser | null | undefined) {
  const source = user as unknown as Record<string, unknown> | undefined;
  const access = user?.access as unknown as Record<string, unknown> | undefined;
  const packs = access?.businessPacks as Record<string, unknown> | undefined;
  const contexts = Array.isArray(packs?.contexts) ? packs.contexts.map(item=>fields(item as Record<string,unknown>,["contextId","branchId","packKey","packVersion","role","contextRevision","grantRevision","activationRevision"])) : [];
  return JSON.stringify(canonical(["security-v1",user?.primary_role === undefined ? user?.role : user.primary_role,user?.is_superuser,
    fields(source,["employee_id","permissions","disabled","is_active","readOnly","read_only"]),
    fields(access,["grants","permissions","companyDisabledModules","readOnlyModules","disabled","readOnly","read_only","managed","isAccessAdmin","isGlobalAdmin","memberships"]),
    Array.isArray(access?.modules) ? access.modules.map(item=>fields(item as Record<string,unknown>,["key","enabled","permissions","actions","readOnly"])) : null,
    packs ? [fields(packs,["state","hasMore","selectorRequired","selectedContextId","selectionState"]),contexts] : null]));
}

