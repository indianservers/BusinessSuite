const CACHE_VERSION = "business-suite-shell-v4";
const SHELL_ASSETS = ["/", "/app-config.js", "/manifest.webmanifest"];
self.addEventListener("message", event => { if (event.data?.type === "SKIP_WAITING") self.skipWaiting(); });
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_VERSION).then(cache => Promise.all(SHELL_ASSETS.map(async url => {
    const response = await fetch(url);
    if (response.ok && !/no-store/i.test(response.headers.get("cache-control") || "")) await cache.put(url, response);
  }))).catch(() => undefined));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("business-suite-shell-") && key !== CACHE_VERSION).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  // Authenticated data is exclusively managed by the scoped IndexedDB layer.
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  const immutableAsset = url.pathname.startsWith("/assets/") && /\.(?:js|css|woff2?|png|svg|webp)$/.test(url.pathname) && !url.search;
  if (immutableAsset) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION).catch(() => undefined);
      const cached = await cache?.match(event.request).catch(() => undefined);
      if (cached) return cached;
      const response = await fetch(event.request);
      if (cache && response.ok && !/no-store/i.test(response.headers.get("cache-control") || "")) {
        try {
          await cache.put(event.request, response.clone());
          const keys = await cache.keys();
          if (keys.length > 100) await cache.delete(keys.find(request => !SHELL_ASSETS.includes(new URL(request.url).pathname)) || keys[0]);
        } catch { /* A cache quota failure must not break a successful network read. */ }
      }
      return response;
    })());
  } else if (event.request.mode === "navigate" || SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(fetch(event.request).catch(async () => (await caches.match(event.request)) || (event.request.mode === "navigate" ? await caches.match("/") : undefined) || Response.error()));
  }
});
