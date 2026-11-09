/** Include assets loaded before the service worker took control of the first page. */
export function cacheVisitedAssets(worker: ServiceWorker | null) {
  if (!worker) return;
  const urls = performance.getEntriesByType("resource").map(entry => entry.name).filter(name => {
    try { const url = new URL(name); return url.origin === location.origin && url.pathname.startsWith("/assets/"); } catch { return false; }
  });
  worker.postMessage({ type: "CACHE_VISITED_ASSETS", urls: [...new Set(urls)] });
}
