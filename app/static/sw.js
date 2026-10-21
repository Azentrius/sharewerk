// SPDX-License-Identifier: Apache-2.0
// Minimal service worker: keeps the static app shell (CSS, JS, icons) cached so the app opens
// instantly from the share sheet. Pages and API calls always go to the network, so
// authentication and results are never served stale.
// The pages ask for every script and stylesheet as /static/<file>?v=<hash of its content>
// (app/assets.py). A cached copy therefore always belongs to the page that asks for it, also
// when an older worker still runs after an update; a new version of a file is a new URL.
const CACHE = "sharewerk-v4";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || !url.pathname.startsWith("/static/")) {
    return; // let the browser handle it normally
  }
  // Stale-while-revalidate for static assets.
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(event.request);
      const network = fetch(event.request)
        .then(async (response) => {
          if (response.ok) {
            await cache.put(event.request, response.clone());
            // Other versions of the same file belong to pages that are gone.
            for (const key of await cache.keys()) {
              const other = new URL(key.url);
              if (other.pathname === url.pathname && other.search !== url.search) await cache.delete(key);
            }
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
