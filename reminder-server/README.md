# 선택 시간 운동 기록 리마인더

앱 1.0.127에 연결된 알림 서버 코드다. **Cloudflare 배포·앱 URL 연결·스케줄 활성화 전에는 실제 자동 알림을 보내지 않는다.** 기존 FCM 연결은 앱의 `reminderApiUrl`이 비어 있는 동안 유지한다. 취소한 Google 관리자 JSON/Firestore 서버 접근 방식은 사용하지 않는다.

## 동작

- 설정 → 알림에서 저장한 한국시간에, 알림을 허용한 로그인 iOS 기기에만 보낸다. 기본값은 오후 10시다.
- 오전/오후·시·분 다이얼과 저장하기는 서버 연결 전에도 기기에서 사용할 수 있다. 서버 연결 후 개인별 시간이 계정에 반영된다. 같은 날짜·기기·설정 시간에는 한 번만 시도한다. 이미 알림을 받았더라도 다른 미래 시간으로 변경하면 그 시간에 다시 발송한다. 같은 시간을 다시 저장하거나 이미 처리된 시간으로 되돌리면 중복 발송하지 않는다. 이미 지난 시각을 저장하면 내일부터 적용한다.
- 오늘 저장된 실제 3대/OHP/보조·맨몸 기본운동 세트 또는 완료된 맨몸 루틴이 하나라도 있으면 제외한다. 달력 체크, 식단, 앱 실행, 운동 계획은 운동 기록으로 세지 않는다.
- 본문: `오늘은 운동을 가지 않으셨군요. 내일은 분발하세요.`
- 마지막 실제 세트를 삭제하면 기록 없음으로 되돌린다. 세트가 남아 있으면 제외 상태를 유지한다.
- 여러 기기의 Firestore 기록 상태는 두 기록 컬렉션의 성공한 서버 동기화 기준 시각 중 이른 시각으로 비교한다. 오래된 기기의 상태가 새 상태를 덮어쓰지 못한다. 로컬 전용 맨몸 루틴은 기기별 유무를 합쳐 다른 기기의 빈 상태가 지우지 못하게 한다.
- 기기·날짜·설정 시간별 SQL 원자적 예약으로 중복 실행을 막는다. 접수 성공은 실제 배너 표시 보장이 아니다. 일시 오류나 애매한 네트워크 실패는 같은 날짜·설정 시간에 자동 재전송하지 않는다. 기기 구독의 404/410은 해당 구독이 여전히 같은 경우만 정리한다.
- 하루의 판정은 기기가 서버에 마지막으로 전달한 상태를 기준으로 한다. **기록 저장 후 동기화 전에 앱을 강제 종료하거나 오프라인이면 잘못된 알림이 갈 수 있다.** 기기만 아는 기록을 서버가 알아낼 수는 없다. 22시 판정과 동시에 기록하는 경우도 처리 순서에 따른다.

## 접근 범위와 저장 정보

Cloudflare Worker에는 Google 서비스 계정/Firestore 관리자 인증을 넣지 않는다. Google 공개 서명 키로 **우리 Firebase 프로젝트의 로그인 토큰**만 검증하고, 인증된 UID에 대한 요청만 처리한다. Firebase Auth 프로젝트 API나 Firestore를 서버에서 조회하지 않는다.

D1에 저장하는 것은 UID, 무작위 기기 ID, Web Push 구독(endpoint·암호화 키), 날짜별 기록 유무/로컬 루틴 유무/동기화 시각, 개인별 알림 시간(한국시간 분 단위), 날짜·설정 시간별 발송 상태뿐이다. 무게·횟수·종목명·운동 내역을 알림 서버에 전달하지 않는다. 날짜별 상태와 발송 기록은 14일 보관 후 정리한다. 최초 초기화 UID와 기기 구독은 연결 해제/회원탈퇴까지 보관한다. 로그아웃은 현재 기기만 해제하고 회원탈퇴는 해당 UID의 모든 알림 데이터를 지운다. 오프라인/서버 장애로 정리가 실패하면 원격 정리가 지연될 수 있으며 브라우저 구독 해제/만료로 더 이상 전달되지 않게 한다.

서버의 VAPID 비공개 키는 **이 알림 발송만 인증**한다. 개인 운동 DB 접근 권한이 없다. 기존 Firebase VAPID 공개 키와는 새 키 쌍이므로 앱 URL 연결 시 기기 구독을 한 번 교체하고 본인 계정의 이전 FCM 토큰 문서를 정리한다. OS의 기존 허용 여부는 유지한다.

## 최초 배포 (한 번)

1. Cloudflare → Workers & Pages → 새 Worker `ttt-workout-reminder` 생성.
2. Worker 편집기에 이 폴더의 **`worker.bundle.mjs` 전체**를 넣고 Deploy. 이 파일은 의존성을 포함한 빌드 결과로, npm/CLI 없이 대시보드에서 사용할 수 있다. 기존 AI Worker는 변경하지 않는다.
3. Cloudflare → D1 → 데이터베이스 `ttt-workout-reminder` 생성 → Console에서 `schema.sql` 전체 실행.
4. Worker → Settings → Bindings → D1 Database → 변수 이름 **`DB`**로 위 DB 연결.
5. [키 생성 도구](https://kimsco.github.io/reminder-server/keys.html)에서 키 쌍 생성. 브라우저 내부에서만 생성하며 외부로 전송하지 않는다.
   - Worker의 Variables and Secrets에 `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`를 각각 Secret으로 넣는다.
   - Google 관리자 JSON이 아니다. 비공개 키는 채팅/공개 코드에 넣지 않는다.
6. Worker 일반 변수 `REMINDERS_ENABLED`는 먼저 **`false`**로 설정.
7. Worker 주소만 공유하여 `js/push-config.js`의 `reminderApiUrl`에 연결하고 앱을 배포한다. 비공개 키는 공유하지 않는다.
8. 아이폰 홈 화면 앱에서 로그인·알림 허용 상태로 앱을 다시 열어 첫 상태 동기화를 마친다. 이미 허용했다면 재허용을 요구하지 않는다. Android도 본인 계정 운동 여부만 전달할 수 있지만 푸시 기기 등록은 하지 않는다.
9. Cloudflare Cron Trigger를 **`* * * * *` (매분)**로 추가하고 `REMINDERS_ENABLED`를 **`true`**로 바꾼다. 자동 발송 사용이 확정된 뒤 활성화한다.

CLI 사용자는 `wrangler.toml`의 D1 ID를 채우고 원격 스키마 적용 및 `wrangler secret put`을 사용해 같은 구성을 배포할 수 있다. 현재 이 실행 환경에는 Cloudflare 배포 인증이 없으므로 실제 서버 배포는 수행하지 않았다.

## 시간·무료 한도

각 분에 한국시간으로 환산하여 계정별 선택 시간이 된 기기를 찾는다. 기본값인 한국시간 22:00은 UTC 13:00이다. 한 번에 최대 10기기를 처리하고 다음 분에 다음 묶음을 처리한다. 선택 시간부터 최대 59분까지 같은 날의 대기 기기를 처리하며, 자정을 넘겨 전날 분량을 새로 보내지는 않는다. 한 시간에 최대 600기기이며 그 이상의 규모는 별도 큐/발송 용량 설계가 필요하다. 정각 도착이나 오프라인 폰의 즉시 수신을 보장하지 않는다.

Cloudflare Workers/D1 무료 제공량 안에서 사용할 수 있지만 사용량 제한이 있다. 이 코드는 유료 요금제 전환이나 유료 Firebase 기능을 활성화하지 않는다. 앱은 운동 기록 유무가 바뀌는 시점/날짜 초기화 때만 상태를 보낸다. 같은 유무에서는 세트마다 서버에 전송하지 않는다. 상태 전환 확인에는 기존 Firestore 델타 동기화를 사용하므로 두 기록 컬렉션의 변경 조회가 추가될 수 있으며, 비어 있는 쿼리도 최소 읽기 비용이 있다. 과거 기록 전체를 다시 읽지 않는다.

## API

모든 요청의 Origin은 `https://kimsco.github.io`이다. `/config` 외에는 Firebase ID token을 `Authorization: Bearer ...`로 전달한다. 임의 UID를 요청 본문에서 받지 않는다.

- `GET /config`: 준비 여부, VAPID 공개 키. 비공개 키를 반환하지 않는다.
- `PUT /device`: `{id, subscription}`. iOS Apple endpoint만 허용하고 임의 호스트는 거부하고 리다이렉트를 따라가지 않는다. Workers가 지원하는 `redirect: "manual"`을 사용한다. 계정당 최대 10기기.
- `DELETE /device`: `{id}`. 본인의 해당 기기만 해제.
- `POST /activity`: `{day, hasRecord, hasLocalRecord, deviceId, basis}`. 한국시간 오늘과 최근 동기화 기준 시각만 허용. 무게 등 추가 필드를 거부한다.
- `GET /preferences`: 본인 알림 시간. 미설정이면 `{minuteOfDay:1320}`.
- `PUT /preferences`: `{minuteOfDay}` (0~1439 정수). 본인 시간만 저장한다.
- `DELETE /account`: 본인의 구독과 날짜별 상태/발송 기록 및 시간 설정 삭제.

## 검증

```sh
npm ci --ignore-scripts --prefix reminder-server
npm run build --prefix reminder-server
node --test tests/reminder-server.test.mjs tests/workout-reminder.test.cjs tests/push-devices.test.cjs tests/push-worker.test.cjs tests/core.test.cjs
python tests/workout-reminder-smoke.py
python tests/notification-settings-smoke.py
python tests/notification-time-smoke.py
```

SQLite 실제 SQL로 대상 필터·상태 역전·동시 중복 예약·기기별 루틴·오류/만료 정리·여러 묶음을 검증한다. Web Crypto 키로 Apple 호환 aes128gcm/VAPID 전송 본문 생성도 검증한다. 브라우저는 격리된 Firebase와 알림 서버만 사용하며 실제 개인 기록을 읽거나 푸시를 보내지 않는다. 실제 Cloudflare 배포와 iOS 수신은 최초 연결 후 별도로 확인한다.

## 시간 설정 화면 (126)

설정의 알림 행은 화면 이동만 수행하며 OS 권한 요청은 화면 안의 알림 허용 버튼에서만 한다. 이전 진단 문구는 표시하지 않는다. 시·분은 1분 단위로 선택하고 저장하기를 눌러야 확정한다. 뒤로가기는 미저장 선택을 버린다. 게스트와 사용자별 기기 저장 키를 분리하며, 서버 연결 시 성공 전까지 변경 사항을 dirty로 보관하고 온라인 복귀/재시도로 반영한다. 다른 기기의 시간은 화면 진입 시 다시 확인하며 미저장 다이얼 선택을 덮어쓰지 않는다. 기존 DB를 갱신할 때는 새 스키마의 preferences 테이블을 먼저 적용하고 Cron을 매분으로 변경한다.

## 기존 서버를 시간별 중복 방지로 갱신

1. `REMINDERS_ENABLED`를 잠시 `false`로 바꿔 저장/배포한다. 갱신 중 앱의 알림 시간은 바꾸지 않는다.
2. D1 Console에서 `migrate-per-time.sql` 전체를 실행한다. 새 `delivery_slots` 표를 만들고 기존 발송 상태를 보존한다. 기존 기록에는 발송 시간이 없으므로 현재 저장된 시간은 이미 처리한 것으로 옮긴다. 이후 다른 미래 시간을 저장하면 다시 받을 수 있다. 재실행해도 같은 과거 기록을 새 시간으로 재해석하지 않는다. 원래 `deliveries` 표는 지우지 않는다.
3. Worker 편집기 전체를 최신 `worker.bundle.mjs`로 교체하고 Deploy한다. 파일 첫 줄의 `// @ts-nocheck`는 번들 라이브러리의 편집기 타입 경고를 끈다.
4. `REMINDERS_ENABLED=true`로 저장/배포한 뒤 앱에서 새 미래 시간을 저장한다. DB·키·기기 구독·앱 URL은 그대로 사용한다. 앱 파일 변경이나 재설치는 필요 없다.

발송 결과는 `SELECT day,minute_of_day,status FROM delivery_slots ORDER BY day DESC,minute_of_day DESC;`로 확인한다. `failed-prepare-*`는 발송 준비 실패, `failed-fetch-*`는 전송 단계 예외이며 로그에 단계와 오류 종류만 기록한다. 키/구독 URL/예외 원문은 로그에 남기지 않는다. HTTP 응답 실패는 `failed-상태코드`이다.
