const CACHE = "mf-v5"; // 🔥 정적 파일이 바뀔 때마다 버전을 올려야 기존 캐시가 갱신됨 — 이번엔 index.html 캐시가 옛 버전에 갇혀있던 걸 강제로 비우기 위해 올림
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
    // 🔥 화면모드(다크/라이트) 토글 리로드(?modeswitch=1): 방금까지 쓰던 것과 같은 HTML을
    //    다시 여는 것뿐이므로 네트워크를 기다릴 이유가 없음 — 캐시 우선으로 즉시 응답해서
    //    토글 딜레이를 없앰(쿼리스트링은 무시하고 매칭). 캐시가 없을 때만 네트워크 폴백.
    //    이 쿼리는 로드 직후 index.html 쪽 JS가 주소에서 지워주므로, 사용자가 직접 하는
    //    새로고침/재실행은 여전히 네트워크 우선(최신 배포 반영)으로 동작함.
    if (url.includes("modeswitch=1")) {
      return e.respondWith(
        caches.match(e.request, { ignoreSearch: true })
          .then(r => r || caches.match("/index.html"))
          .then(r => r || fetch(e.request))
      );
    }
    return e.respondWith(
      fetch(e.request)
        .then(res => {
          // 🔥 e.waitUntil로 감싸지 않으면 respondWith의 res를 반환한 직후 브라우저가
          //    SW를 바로 종료시켜버릴 수 있어 캐시 저장이 중간에 끊길 수 있음(fire-and-forget).
          //    그 결과 index.html 캐시가 install 시점(오래된 버전)에 멈춰있게 되고,
          //    ?modeswitch=1(화면모드 토글) 리로드는 캐시 우선이라 그 옛날 버전을 계속 보여주게 됨.
          //    waitUntil로 감싸 캐시 저장이 항상 끝까지 완료되도록 보장.
          e.waitUntil(caches.open(CACHE).then(c => c.put(e.request, res.clone())));
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
