export function pmsPageResource(path: string) {
  const [pathname, search = ""] = path.split("?");
  const params = new URLSearchParams(search);
  const person = pathname.match(/^\/pms\/people\/(\d+)$/);
  if (person) return { key: `person:${person[1]}`, endpoint: `/project-management/people-workspace/people/${person[1]}`, fallback: `Person #${person[1]}` };
  const project = pathname.match(/^\/pms\/projects\/(\d+)(?:\/|$)/);
  if (project) return { key: `project:${project[1]}`, endpoint: `/project-management/projects/${project[1]}`, fallback: `Project #${project[1]}` };
  const task = pathname.match(/^\/pms\/tasks\/(\d+)$/);
  if (task) return { key: `task:${task[1]}`, endpoint: `/project-management/tasks/${task[1]}`, fallback: `Task #${task[1]}` };
  const workspaceId = params.get("workspace");
  if (["/pms", "/pms/workspaces"].includes(pathname) && workspaceId && /^\d+$/.test(workspaceId))
    return { key: `workspace:${workspaceId}`, endpoint: `/project-management/workspaces/${workspaceId}/overview`, fallback: `Workspace #${workspaceId}` };
}

export function pmsPageLabel(path: string, knownLabel?: string, names: Record<string, string> = {}) {
  const [pathname, search = ""] = path.split("?");
  const params = new URLSearchParams(search);
  const operation = params.get("operation");
  if (operation?.startsWith("/pms/")) return pmsPageLabel(operation.split("?")[0], undefined, names);
  const resource = pmsPageResource(path);
  if (resource) {
    const name = names[resource.key] || (knownLabel && !["Workspace", "Person profile"].includes(knownLabel) ? knownLabel.split(" · ")[0] : resource.fallback);
    const section = resource.key.startsWith("person:") ? params.get("tab") || "overview" : pathname.split("/").slice(4).join(" ");
    const label = section === "batches" ? "Intern batch" : section ? section[0].toUpperCase() + section.slice(1).replace(/-/g, " ") : "";
    return label ? `${name} · ${label}` : name;
  }
  if (knownLabel && knownLabel !== "Workspace") return knownLabel;
  if (params.get("mine")) return "My Tasks";
  if (pathname === "/pms" || pathname === "/pms/workspaces") return "Workspace board";
  const segment = pathname.split("/").filter(Boolean).pop() || "PMS";
  return segment.replace(/-/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function groupPmsRecents<T extends { path: string }>(pages: readonly T[]): T[] {
  const seen = new Set<string>();
  return pages.filter(page => {
    const pathname = page.path.split("?")[0];
    const canonical = pathname === "/pms/timesheets" ? "/pms/time-tracking" : ["/pms/navigator", "/pms/issue-navigator-pro"].includes(pathname) ? "/pms/tasks" : pathname;
    const key = pmsPageResource(page.path)?.key || canonical;
    if (seen.has(key)) return false;
    seen.add(key); return true;
  });
}
