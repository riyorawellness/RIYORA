// RIYORA WELLNESS - Service Worker
//
// Strategy:
//   • Navigations / HTML  → NETWORK-FIRST (never serve stale app shell)
//   • Hashed JS/CSS       → NETWORK-FIRST with cache fallback (avoids stale chunk mismatch)
//   • Fonts/images        → CACHE-FIRST (long-lived)
//   • API                 → NEVER touched
//
// Cache name is bumped on every deploy that changes SW logic; old caches are
// purged on activate.

const CACHE = "riyora-v3";
const OFFLINE_URL = "/offline";

const isHtml = (req) =>
  req.mode === "navigate" ||
  (req.headers.get("accept") || "").includes("text/html");

const isStaticAsset = (url) =>
  /\.(png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf|eot)$/i.test(url.pathname);

const isJsCss = (url) => /\.(js|css)$/i.test(url.pathname);

self.addEventListener("install", (event) => {
  // Activate the new SW immediately.
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Purge all previous caches so any stale HTML/JS is gone.
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Never intercept API or non-GET calls.
  if (request.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) return;
  if (url.origin !== self.location.origin) return;

  // NETWORK-FIRST for HTML pages — always fresh app shell.
  if (isHtml(request)) {
    event.respondWith(networkFirst(request, true));
    return;
  }

  // NETWORK-FIRST for JS/CSS — prevents stale chunk mismatch after a rebuild.
  if (isJsCss(url)) {
    event.respondWith(networkFirst(request, false));
    return;
  }

  // CACHE-FIRST for immutable static assets (fonts, images).
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  // Everything else: pass through.
});

async function networkFirst(request, isHtmlReq) {
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, fresh.clone()).catch(() => {});
    }
    return fresh;
  } catch (_) {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (isHtmlReq) {
      const offline = await caches.match(OFFLINE_URL);
      if (offline) return offline;
    }
    return new Response("Offline", { status: 503, statusText: "Offline" });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, fresh.clone()).catch(() => {});
    }
    return fresh;
  } catch (_) {
    return new Response("Offline", { status: 503 });
  }
}

// Manual "please refresh" trigger — clients can post {type:'SKIP_WAITING'} to
// force an immediate SW upgrade if we ever need to push one.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
