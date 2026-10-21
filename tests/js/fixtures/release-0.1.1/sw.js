// SPDX-License-Identifier: Apache-2.0
// Minimal service worker: keeps the static app shell (CSS, JS, icons) cached so
// the app opens instantly from the share sheet. Pages and API calls always go
// to the network, so authentication and results are never served stale.
const CACHE = "sharewerk-v3";
const SHELL = [
  "/static/theme.js",
  "/static/azentrius/tokens.css",
  "/static/azentrius/bundle.css",
  "/static/azentrius/fonts/DMSans-VF.woff2",
  "/static/azentrius/fonts/DMSerifDisplay-Regular.woff2",
  "/static/app.css",
  "/static/icons.js",
  "/static/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/sharewerk-favicon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

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
        .then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
