const CACHE = "mf-v1";
const ASSETS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/sw.js",
  "/food-db-full.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png"
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener("fetch", e => {
  // Worker API는 항상 네트워크에서 받기 (캐시 무시)
  if (e.request.url.includes(".workers.dev")) {
    return e.respondWith(fetch(e.request));
  }
  // 나머지 요청은 캐시 우선
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
