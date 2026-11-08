/** Task pages use the PMS workspace, including its own navigation and header. */
export function isSharedTaskWorkspace(pathname: string, search = "") {
  const params = new URLSearchParams(search);
  const operation = params.get("operation") || pathname;
  if (params.get("workspaceView") === "notes") return false;
  return operation === "/crm/tasks" || pathname === "/pms/tasks" || pathname === "/pms/tasks/new" || /^\/pms\/tasks\/\d+\/edit$/.test(pathname);
}
