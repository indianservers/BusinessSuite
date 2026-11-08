/** Visible labels are supplied by existing navigation metadata; API names are never displayed. */
let routeContext = { title: "Workspace", module: "" };
export function setProgressContext(context: typeof routeContext) {
  routeContext = context;
}
export function getProgressContext() {
  return routeContext;
}
export function operationTitle(
  action:
    | "navigation"
    | "fetch"
    | "save"
    | "upload"
    | "download"
    | "import"
    | "export"
    | "generate"
    | "sync"
    | "process",
  resource = routeContext.title,
) {
  const verbs = {
    navigation: "Loading",
    fetch: "Loading",
    save: "Saving",
    upload: "Uploading",
    download: "Downloading",
    import: "Importing",
    export: "Exporting",
    generate: "Generating",
    sync: "Syncing",
    process: "Updating",
  };
  return `${verbs[action]} ${resource}`;
}
