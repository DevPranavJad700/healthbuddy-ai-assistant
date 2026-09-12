// HealthBuddy AI — Service Worker for offline capability
const CACHE_NAME = "healthbuddy-v1";
const OFFLINE_URL = "/offline.html";

const PRECACHE_ASSETS = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/liquid-theme.js",
  "/static/manifest.json",
];

// Install — precache shell assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn("[SW] Precache partial failure:", err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch — network-first for API, cache-first for static assets
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never cache API calls or streaming endpoints
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // Cache-first for static assets
  if (
    url.pathname.startsWith("/static/") ||
    url.pathname === "/" ||
    url.pathname === "/index.html"
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const networkFetch = fetch(event.request)
          .then((response) => {
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, clone);
              });
            }
            return response;
          })
          .catch(() => cached);

        return cached || networkFetch;
      })
    );
    return;
  }
});
