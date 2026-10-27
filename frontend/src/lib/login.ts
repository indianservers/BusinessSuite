// Accept only internal application destinations; never redirect to a supplied host.
export function loginDestination(value: string | null): string {
  if (
    !value ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    [...value].some((character) => character.charCodeAt(0) < 32)
  )
    return "/dashboard";
  const url = new URL(value, "https://suite.invalid");
  if (
    url.origin !== "https://suite.invalid" ||
    !/^\/(dashboard|hrms|crm|pms|srm|fam|power-apps|admin)(?:\/|$)/.test(
      url.pathname,
    ) ||
    /\/login\/?$/.test(url.pathname)
  )
    return "/dashboard";
  return url.pathname + url.search + url.hash;
}
