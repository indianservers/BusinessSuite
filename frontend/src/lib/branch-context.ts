/** Migrate the retired aggregate selection before any request or socket opens. */
export function selectedBranch(): string | null {
  const branch = sessionStorage.getItem("suite-branch");
  if (branch === "all") {
    sessionStorage.removeItem("suite-branch");
    return null;
  }
  return branch;
}
