/** The server authorizes aggregate reads and resolves a concrete branch for writes. */
export function selectedBranch(): string | null {
  return sessionStorage.getItem("suite-branch");
}
