# 수동 알림 발송

GitHub Actions의 **알림 보내기**를 수동 실행한다. 별도 상시 서버나 Firebase Functions는 쓰지 않는다. **현재 코드만 준비된 상태이며 아래 인증·색인 설정 전에는 발송할 수 없다.** 앱은 1.0.124 그대로이며 알림은 iOS 홈 화면 앱에 한정한다.

## 최초 연결

1. Google Cloud 프로젝트 `rmpj-7ca13`에 발송 전용 서비스 계정을 만든다.
   - [서비스 계정](https://console.cloud.google.com/iam-admin/serviceaccounts?project=rmpj-7ca13)
   - 역할: `Firebase Cloud Messaging API Admin` (`roles/firebasecloudmessaging.admin`), `Cloud Datastore User` (`roles/datastore.user`). 소유자 역할은 필요 없다.
   - 해당 서비스 계정 → 키 → 키 추가 → 새 키 만들기 → JSON.
2. [GitHub Actions Secrets](https://github.com/kimsco/kimsco.github.io/settings/secrets/actions) → New repository secret:
   - 이름: `FIREBASE_SERVICE_ACCOUNT_JSON`
   - 값: JSON 파일의 **전체 내용**. 비공개 키이며 채팅·코드·워크플로 입력에 넣지 않는다.
   - 비밀은 워크플로의 발송 프로세스에만 환경변수로 전달하며 저장·출력하지 않는다.
3. [GitHub Actions Variables](https://github.com/kimsco/kimsco.github.io/settings/variables/actions) → New repository variable:
   - 이름: `PUSH_TEST_UID`
   - 값: Firebase Authentication 사용자 목록에서 확인한 **테스트받을 본인 계정 UID**. 기기 문서 ID나 FCM 토큰이 아니다.
4. `firestore.indexes.json`에 추가한 `pushDevices`의 두 복합 색인을 Firebase에 적용한다. 모두 `platform ASC`, `enabled ASC`, `__name__ ASC`이며 조회 범위는 각각 `COLLECTION`, `COLLECTION_GROUP`이다. 기존 색인은 보존한다. Firebase 콘솔 → Firestore → 색인에서 만들어도 된다.
   - CLI를 쓸 경우 임시 설정 파일에서 이 저장소의 색인 파일을 지정하고, `firebase deploy --only firestore:indexes --project rmpj-7ca13 --config <설정 파일>`을 실행한다. 아직 인증된 CLI/배포 경로가 없으므로 이 작업은 자동 적용하지 않았다.
5. 클라이언트에서 루트 `pushCampaigns/{campaignId}` 및 그 하위 문서에 접근할 수 없어야 한다. 기존 규칙이 `users/{uid}/...`의 본인 데이터만 허용한다면 이 루트는 기본 거부된다. 발송을 위해 전체 공개 규칙을 추가하지 않는다. 서버는 서비스 계정 IAM으로 접근한다.

이 환경에는 Google 발송 인증이 없고, 현재 GitHub 연결은 Secrets/Variables API 접근이 403이므로 2~3은 소유자가 설정 화면에서 한 번 수행해야 한다. 설정 전에는 테스트 발송도 실행하지 않는다.

## 1. 내 폰 테스트

[알림 보내기](https://github.com/kimsco/kimsco.github.io/actions/workflows/notifications.yml) → Run workflow:

- Branch: `main`
- mode: `test`
- title, body: 보낼 문구
- test_run_id, approval: 공백

`PUSH_TEST_UID` 계정의 현재 활성 iOS 기기에만 보낸다. 토큰은 등록 문서에서 직접 찾으므로 복사가 필요 없다. 실제 기기가 여러 대면 그 계정의 활성 iOS 기기 각각에 간다. 실행 요약의 `test-실행번호`와 접수 결과를 확인하고 **실제로 폰에 도착한 내용**을 확인한다. FCM 접수 성공은 기기 수신 보장이 아니다.

## 2. 확인한 내용 전체 발송

폰 수신 및 문구를 확인한 소유자가 **별도로** Run workflow를 실행한다.

- mode: `approved-broadcast`
- test_run_id: 위 테스트 실행 번호의 숫자 부분
- approval: `SEND`
- title, body: 공백 (넣더라도 사용하지 않음)

해당 테스트가 FCM에 접수된 상태여야 하며 테스트 계정 설정도 같아야 한다. Firestore에 기록된 **그 테스트의 제목·본문**만 iOS 활성 기기에 보낸다. 사용자당 한 번이 아니라 등록 기기당 한 번이다. 테스트 수신자도 전체 발송 대상에 포함된다. 현재 예약 발송이나 운동 여부 판단은 없다.

채팅에서 대신 실행을 요청할 때도 먼저 테스트를 요청하고, 수신 확인 후 특정 테스트 실행 번호의 전체 발송을 승인한다. 이 구현 작업 자체는 전체 발송 승인이 아니다.

## 재실행·오류 처리

- 소유자 `kimsco`의 `main` 수동 실행만 허용한다. PR, push, 스케줄은 발송하지 않는다.
- 전체 실행을 직렬화하며 테스트 실행 번호를 캠페인 ID로 사용한다.
- 동일 테스트의 rerun은 중복 전송을 막기 위해 거부한다. 테스트가 필요하면 새 workflow_dispatch를 시작한다.
- 전체 발송은 트랜잭션으로 1회 승인하고 각 기기 전송 전에 전달 예약을 기록한다. 네트워크 응답이 애매하면 자동 재전송하지 않는다. 일부 접수 후 장애/취소 시 미발송이 남을 수 있으며, 전체를 재실행해 중복 전송하지 않는다. 새 캠페인을 명시적으로 만들기 전에 기존 요약을 확인한다. FCM·브라우저 자체의 중복/지연까지 정확히 한 번을 보장하지 않는다.
- 조회 이후 토큰이 바뀌었을 수 있으므로 전송 직전 기기 문서를 트랜잭션으로 다시 읽는다.
- 명시적인 `registration-token-not-registered`에만 현재 토큰을 비교해 무효 문서를 삭제한다. 네트워크·권한·요청 오류에서는 토큰을 삭제하지 않는다.
- 전송 기록에는 토큰 원문을 저장하지 않으며 로그에는 접수/실패 건수만 남긴다. 캠페인에는 제목·본문·테스트 UID·상태와 기기별 해시 ID의 결과를 저장한다. 사용자 앱에서 조회하지 않는다.
- 운영자가 더 이상 필요 없는 캠페인 기록을 삭제할 때는 하위 `testDeliveries`, `broadcastDeliveries`도 함께 삭제한다. 자동 보관 만료나 서버 캠페인과 사용자 탈퇴의 연동은 아직 없다.

## 사용량

FCM 메시지 전송 자체는 무료다. 이 수동 방식은 Firestore의 대상 기기 조회·전송 전 재확인과 캠페인/전달 상태 쓰기가 추가된다. 실패한 토큰 삭제도 쓰기 사용량에 해당한다. 운동 기록은 조회하지 않는다. GitHub Actions는 저장소 및 계정의 제공 한도를 따른다. 유료 Firebase 요금제로 전환하거나 예약 서버를 활성화하지 않는다.

## 검증

```sh
node --test tests/notification-sender.test.mjs
npm ci --ignore-scripts --prefix notification-server
```

자동 테스트는 트랜잭션·페이지 조회·FCM을 격리한 모형으로 실행하며 실제 사용자 문서를 읽거나 알림을 보내지 않는다. 실제 IAM·색인·FCM 통합 확인은 최초 연결 후 본인 계정 테스트로 수행한다.
