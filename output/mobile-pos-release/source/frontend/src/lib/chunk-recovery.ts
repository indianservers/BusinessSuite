/** Keep the existing document on transient chunk failures. The content boundary
 * offers Retry and an explicit Reload application action for obsolete deployments.
 * Returning false lets Vite propagate the original error to that boundary. */
export function recoverChunkLoad(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  if (
    /Failed to fetch dynamically imported module|Loading chunk|Importing a module script failed|Unable to preload CSS/i.test(
      message,
    )
  ) {
    window.dispatchEvent(new Event("suite:route-code-unavailable"));
  }
  return false;
}
