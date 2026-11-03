/* Makes the Studio installable and lets the app shell open instantly. Only the built, hashed files are cached:
   the API, media, and live preview are always fetched fresh (they depend on the local server). */
const CACHE = "vt-shell-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/manifest.webmanifest", "/icon-192.png"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (/^\/(api|media|bundled|ws)\b/.test(u.pathname)) return;
  if (u.pathname.startsWith("/assets/")) {            // hashed build output never changes: cache first
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r; })));
    return;
  }
  if (e.request.mode === "navigate") {                // app shell: network first so updates show, cache when the server is slow/off
    e.respondWith(fetch(e.request).catch(() => caches.match("/")));
  }
});
