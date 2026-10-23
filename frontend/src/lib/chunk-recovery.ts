export function recoverChunkLoad(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  if (!/Failed to fetch dynamically imported module|Loading chunk|Importing a module script failed|Unable to preload CSS/i.test(message)) return false;
  try {
    const key = `chunk-recovery:${location.pathname}`;
    const last = Number(sessionStorage.getItem(key) || 0);
    if (Date.now() - last < 60000) return false;
    sessionStorage.setItem(key, String(Date.now()));
    location.reload();
    return true;
  } catch { return false; }
}
