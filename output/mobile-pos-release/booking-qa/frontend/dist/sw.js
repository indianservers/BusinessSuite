const CACHE_VERSION = "business-suite-shell-v6";
const SHELL_ASSETS = ["/", "/app-config.js", "/manifest.webmanifest"];
const MAX_ASSETS = 1000;
const flights = new Map();
const isAsset = url => url.origin === self.location.origin && url.pathname.startsWith("/assets/") && /\.(?:m?js|css|woff2?|ttf|otf|png|jpe?g|gif|ico|svg|webp|avif|wasm)$/.test(url.pathname) && !url.search;
async function asset(request) {
  const key = typeof request === "string" ? new URL(request, self.location.origin).href : request.url;
  if (!flights.has(key)) {
    const flight = (async () => {
      const cache = await caches.open(CACHE_VERSION).catch(() => undefined);
      const cached = await cache?.match(request).catch(() => undefined);
      if (cached) return cached;
      const response = await fetch(request);
      if (cache && response.ok && response.type !== "opaque" && !/no-store/i.test(response.headers.get("cache-control") || "")) {
        try {
          await cache.put(request, response.clone());
          const keys = await cache.keys();
          for (const old of keys.filter(r => !SHELL_ASSETS.includes(new URL(r.url).pathname)).slice(0, Math.max(0, keys.length - MAX_ASSETS))) await cache.delete(old);
        } catch { /* Storage pressure must not break a successful page load. */ }
      }
      return response;
    })();
    flights.set(key, flight);
    flight.finally(() => { if (flights.get(key) === flight) flights.delete(key); }).catch(() => undefined);
  }
  return (await flights.get(key)).clone();
}
self.addEventListener("message", event => {
  if (event.data?.type === "SKIP_WAITING") { self.skipWaiting(); return; }
  if (event.data?.type !== "CACHE_VISITED_ASSETS" || !Array.isArray(event.data.urls)) return;
  if (!event.source?.url || new URL(event.source.url).origin !== self.location.origin) return;
  const urls = [...new Set(event.data.urls.filter(value => typeof value === "string").filter(value => { try { return isAsset(new URL(value, self.location.origin)); } catch { return false; } }))].slice(0, MAX_ASSETS);
  event.waitUntil((async () => { for (let i = 0; i < urls.length; i += 4) await Promise.allSettled(urls.slice(i, i + 4).map(url => asset(url))); })());
});
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_VERSION).then(cache => Promise.all(SHELL_ASSETS.map(async url => {
    const response = await fetch(url);
    if (response.ok && !/no-store/i.test(response.headers.get("cache-control") || "")) await cache.put(url, response);
  }))).catch(() => undefined));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("business-suite-shell-") && key !== CACHE_VERSION).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  // Authenticated data is exclusively managed by the scoped IndexedDB layer.
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  const immutableAsset = isAsset(url);
  if (immutableAsset) {
    event.respondWith(asset(event.request));
  } else if (event.request.mode === "navigate" || SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(fetch(event.request).catch(async () => (await caches.match(event.request)) || (event.request.mode === "navigate" ? await caches.match("/") : undefined) || Response.error()));
  }
});
