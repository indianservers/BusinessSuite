/** Read-only landing pages navigate to separate creation routes before mounting forms. */
export function requiresFormDefaultsForRoute(pathname: string, search = "", hash = "") {
  if (/^\/hrms\/helpdesk\/?$/.test(pathname)) return false;
  return !(/^\/(crm|srm)(\/dashboard)?\/?$/.test(pathname) && !search && !hash);
}
