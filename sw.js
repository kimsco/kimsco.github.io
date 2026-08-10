const CACHE = "mf-v3"; // 🔥 정적 파일이 바뀔 때마다 버전을 올려야 기존 캐시가 갱신됨
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
  self.skipWaiting(); // 🔥 새 버전이 배포되면 열려있는 탭을 안 닫아도 바로 활성화되도록
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener("activate", e => {
  // 🔥 이전 버전(mf-v1 등) 캐시는 삭제 — 이게 없으면 CACHE 이름을 바꿔도 옛 캐시가 계속 남아있음
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = e.request.url;

  // Worker API는 항상 네트워크에서 받기 (캐시 무시)
  if (url.includes(".workers.dev")) {
    return e.respondWith(fetch(e.request));
  }

  // 🔥 index.html(및 "/")은 네트워크 우선 — 캐시 버전을 깜빡 안 올려도 최신 코드가 바로 반영되게.
  //    네트워크 실패(오프라인) 시에만 캐시로 폴백.
  const isAppShell = e.request.mode === "navigate" || url.endsWith("/index.html") || url.endsWith("/");
  if (isAppShell) {
    return e.respondWith(
      fetch(e.request)
        .then(res => {
          caches.open(CACHE).then(c => c.put(e.request, res.clone()));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
  }

  // 나머지(아이콘, 음식DB 등 잘 안 바뀌는 파일)는 캐시 우선
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
