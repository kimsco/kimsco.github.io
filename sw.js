const CACHE = "mf-v17"; // 🔥 배포 직후 자동 새로고침이 부팅 스플래시 페이드와 겹쳐 이중 로고/회색 번쩍임 생기던 문제 수정 — 캐시 이름을 다시 올려서 새로 받아오게 함
const ASSETS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/sw.js",
  "/food-db-full.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
  "/icons/splash/1290x2796.png",
  "/icons/splash/1206x2622.png",
  "/icons/splash/1179x2556.png",
  "/icons/splash/1284x2778.png",
  "/icons/splash/1170x2532.png",
  "/icons/splash/1125x2436.png",
  "/icons/splash/1242x2688.png",
  "/icons/splash/828x1792.png",
  "/icons/splash/750x1334.png",
  "/icons/splash/640x1136.png"
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
    // 🔥 index.html 캐시 저장을 항상 "/"와 "/index.html" 두 키에 동시에 저장 — manifest의
    //    start_url("/")로 열 때와 직접 "/index.html"로 열 때가 각자 다른 캐시 항목을 쓰다보니,
    //    한쪽만 갱신되고 다른 쪽은 install 시점 그대로 멈춰있는(=구버전 홈화면 아이콘에서
    //    화면모드 토글 시 옛날 버전이 나오던) 문제가 있었음 — 두 키를 항상 같이 갱신해서
    //    어느 경로로 접속하든 항상 같은(최신) 캐시를 보게 함.
    function cacheAppShell(res) {
      const clone = res.clone();
      return caches.open(CACHE).then(c => Promise.all([
        c.put("/", clone.clone()),
        c.put("/index.html", clone),
      ]));
    }
    // 🔥 화면모드(다크/라이트) 토글 리로드(?modeswitch=1): 방금까지 쓰던 것과 같은 HTML을
    //    다시 여는 것뿐이라 캐시 우선으로 즉시 응답해서 토글 딜레이를 없애고 싶지만, 캐시가
    //    실제로 최신인지 100% 보장할 수 없으므로(위 이유 등) 아주 짧게(180ms)만 네트워크를
    //    기다려보고, 그 안에 응답이 오면 그걸 쓰고(가장 신선함) 없으면 캐시로 즉시 폴백 —
    //    느린 네트워크에서도 체감 딜레이 없이, 빠른 네트워크에서는 항상 최신을 보장.
    //    이 쿼리는 로드 직후 index.html 쪽 JS가 주소에서 지워주므로, 사용자가 직접 하는
    //    새로고침/재실행은 여전히 네트워크 우선(최신 배포 반영)으로 동작함.
    if (url.includes("modeswitch=1")) {
      const networkPromise = fetch(url.split("?")[0], { cache: "no-store" }).then(res => {
        e.waitUntil(cacheAppShell(res.clone()));
        return res;
      }).catch(() => null);
      const timeoutPromise = new Promise(resolve => setTimeout(() => resolve(null), 180));
      return e.respondWith(
        Promise.race([networkPromise, timeoutPromise]).then(res =>
          res || caches.match("/", { ignoreSearch: true })
            .then(r => r || caches.match("/index.html"))
            .then(r => r || networkPromise)
            .then(r => r || fetch(e.request))
        )
      );
    }
    return e.respondWith(
      fetch(e.request)
        .then(res => {
          // 🔥 e.waitUntil로 감싸지 않으면 respondWith의 res를 반환한 직후 브라우저가
          //    SW를 바로 종료시켜버릴 수 있어 캐시 저장이 중간에 끊길 수 있음(fire-and-forget).
          //    waitUntil로 감싸 캐시 저장이 항상 끝까지 완료되도록 보장.
          e.waitUntil(cacheAppShell(res.clone()));
          return res;
        })
        .catch(() => caches.match(e.request, { ignoreSearch: true }))
    );
  }

  // 나머지(아이콘, 음식DB 등 잘 안 바뀌는 파일)는 캐시 우선.
  // 🔥 캐시에 없어서 네트워크로 받아온 같은 출처(GET) 파일은 캐시에 저장(런타임 캐싱) —
  //    ?v= 캐시버스터가 붙은 설정 아이콘들도 한 번 받은 뒤엔 리로드 때 즉시 표시됨.
  //    (Firestore 등 외부 API 응답은 출처가 달라 저장 대상에서 자동 제외됨)
  e.respondWith(
    caches.match(e.request).then(r => {
      if (r) return r;
      return fetch(e.request).then(res => {
        if (e.request.method === "GET" && res && res.ok && new URL(url).origin === self.location.origin) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      });
    })
  );
});
