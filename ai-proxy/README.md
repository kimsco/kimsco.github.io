# AI 챗봇 프록시 배포 가이드

`index.html`의 "식단 > 설정" 탭에 있는 AI 챗봇은 Google Gemini API를 호출합니다.
이 앱은 서버 없는 정적 GitHub Pages 사이트라서 API 키를 `index.html`에 직접 넣으면
누구나 페이지 소스에서 볼 수 있습니다. 그래서 Gemini API 키는 이 폴더의
`worker.js`(Cloudflare Workers에 배포하는 작은 중계 서버)에만 두고, 앱은 그
Worker의 주소만 호출하도록 만들었습니다.

아래 순서대로 따라 하면 됩니다. 전부 무료입니다.

## 1. Gemini API 키 발급받기

1. https://aistudio.google.com/apikey 접속 (구글 계정으로 로그인)
2. "Create API key" 클릭 → 키가 생성되면 복사해서 잠깐 메모장에 보관
   (`AIzaSy...` 형태의 문자열)

무료 한도(2026년 기준, 카드 등록 불필요):
- `gemini-2.5-flash-lite`: 하루 1,000회
- 다른 모델로 바꾸고 싶으면 `worker.js` 맨 위 `MODEL` 상수만 수정하면 됩니다.

## 2. Cloudflare Workers에 프록시 배포하기

1. https://dash.cloudflare.com/sign-up 에서 무료 계정 생성 (이메일만 있으면 됨)
2. 로그인 후 왼쪽 메뉴에서 **Workers & Pages** 클릭
3. **Create** → **Workers** → **Create Worker** 선택
4. 이름은 아무거나 지정 가능 (예: `muscleflow-ai-proxy`) → **Deploy** 클릭
   (일단 기본 예제 코드로 배포됨 — 다음 단계에서 코드를 교체할 것)
5. 배포된 Worker 페이지에서 **Edit code** 클릭
6. 에디터에 있던 기본 코드를 전부 지우고, 이 폴더의 `worker.js` 파일 내용을
   그대로 복사해서 붙여넣기
7. 오른쪽 위 **Deploy** 클릭

## 3. API 키를 Secret으로 등록하기

1. 방금 만든 Worker의 대시보드로 이동
2. **Settings** 탭 → **Variables and Secrets**
3. **Add** 클릭 → 이름은 정확히 `GEMINI_API_KEY`, 값은 1단계에서 복사해둔 키 입력
4. Type을 **Secret**으로 선택 (Text 아님 — Secret으로 해야 나중에도 값이 안 보임)
5. **Save and deploy** 클릭

## 4. Worker 주소를 앱에 연결하기

1. Worker 대시보드 상단에 `https://muscleflow-ai-proxy.<계정이름>.workers.dev`
   같은 형태의 주소가 보입니다. 이 전체 주소를 복사하세요.
2. `index.html`에서 `AI_CHAT_PROXY_URL` 상수를 찾아서
   (`https://REPLACE-ME.workers.dev` 부분) 방금 복사한 주소로 교체
3. 저장하고 커밋/푸시하면 앱의 AI 챗봇이 실제로 동작합니다.

## 참고 / 한계

- 이 Worker의 주소 자체는 `index.html` 안에 그대로 남아있기 때문에(정적 사이트라
  어쩔 수 없음), 이론적으로는 그 주소를 알아낸 사람이 직접 호출해서 무료 한도를
  같이 소진시킬 수 있습니다. Gemini API 키 자체가 노출되는 것보다는 훨씬 안전하지만,
  완벽한 남용 방지는 아닙니다. 개인용으로 쓰기엔 충분한 수준입니다.
- 무료 한도를 넘기면 Worker가 502 에러를 반환하고, 앱에는 "잠시 후 다시
  시도해주세요" 같은 안내 메시지가 표시됩니다.
